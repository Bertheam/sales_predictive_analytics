from uuid import UUID

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.ml.baseline import (
    BASELINES,
    predict_lag_7,
    predict_moving_average_7,
)
from app.ml.dataset_builder import SalesDatasetBuilder
from app.ml.evaluation import calculate_metrics, evaluate_forecast
from app.ml.features import (
    add_calendar_features,
    add_lag_features,
    add_stock_features,
)
from app.ml.models import (
    FEATURE_COLUMNS,
    MODEL_LABELS,
    PREDICTION_COLUMNS,
    build_regressors,
)
from app.ml.time_series import classify_demand, forecast_ets, forecast_tsb, prepare_demand_series


def evaluate_baselines(
    dataset: pd.DataFrame,
    test_days: int = 60,
) -> dict:
    if test_days <= 0:
        raise ValueError("La période de test doit être supérieure à zéro.")

    if len(dataset) <= test_days + 14:
        raise ValueError(
            "Pas assez de données pour entraîner et évaluer les modèles."
        )

    data = dataset.copy()
    data["prediction_lag_7"] = predict_lag_7(data["quantity_sold"])
    data["prediction_ma_7"] = predict_moving_average_7(
        data["quantity_sold"]
    )

    test_data = data.tail(test_days).copy()

    return {
        "test_data": test_data,
        "models": {
            "lag_7": calculate_metrics(
                test_data["quantity_sold"],
                test_data["prediction_lag_7"],
            ),
            "moving_average_7": calculate_metrics(
                test_data["quantity_sold"],
                test_data["prediction_ma_7"],
            ),
        },
    }


def compare_models(
    dataset: pd.DataFrame,
    test_days: int = 60,
) -> dict:
    if test_days <= 0:
        raise ValueError("La période de test doit être supérieure à zéro.")

    missing_features = set(FEATURE_COLUMNS) - set(dataset.columns)
    if missing_features:
        raise ValueError(
            "Variables manquantes pour les modèles : "
            + ", ".join(sorted(missing_features))
        )

    if len(dataset) <= test_days + 28:
        raise ValueError(
            "Pas assez de données pour entraîner et comparer les modèles."
        )

    data = dataset.sort_values("date").reset_index(drop=True).copy()
    data["prediction_lag_7"] = predict_lag_7(data["quantity_sold"])
    data["prediction_ma_7"] = predict_moving_average_7(
        data["quantity_sold"]
    )

    test_start_date = data.iloc[-test_days]["date"]
    model_data = data.dropna(subset=FEATURE_COLUMNS).copy()
    train_data = model_data[model_data["date"] < test_start_date].copy()
    test_data = model_data[model_data["date"] >= test_start_date].copy()

    train_stockout = (
        train_data["stockout_flag"].astype(bool)
        | (train_data["stock_available"] <= 0)
    )
    test_stockout = (
        test_data["stockout_flag"].astype(bool)
        | (test_data["stock_available"] <= 0)
    )
    clean_train = train_data.loc[~train_stockout].copy()
    evaluation_data = test_data.loc[~test_stockout].copy()

    if len(clean_train) < 60 or evaluation_data.empty:
        raise ValueError(
            "Pas assez de jours hors rupture pour entraîner et évaluer "
            "les modèles."
        )

    metrics = {
        "lag_7": calculate_metrics(
            evaluation_data["quantity_sold"],
            evaluation_data["prediction_lag_7"],
        ),
        "moving_average_7": calculate_metrics(
            evaluation_data["quantity_sold"],
            evaluation_data["prediction_ma_7"],
        ),
    }

    demand_profile = classify_demand(clean_train["quantity_sold"])
    historical_demand = prepare_demand_series(
        train_data["quantity_sold"], train_stockout
    )

    if not demand_profile["is_intermittent"] and len(historical_demand) >= 28:
        try:
            test_data[PREDICTION_COLUMNS["ets"]] = forecast_ets(
                historical_demand, len(test_data)
            )
            metrics["ets"] = calculate_metrics(
                evaluation_data["quantity_sold"],
                test_data.loc[evaluation_data.index, PREDICTION_COLUMNS["ets"]],
            )
        except (ValueError, np.linalg.LinAlgError):
            pass

    if demand_profile["is_intermittent"]:
        test_data[PREDICTION_COLUMNS["croston_tsb"]] = forecast_tsb(
            historical_demand, len(test_data)
        )
        metrics["croston_tsb"] = calculate_metrics(
            evaluation_data["quantity_sold"],
            test_data.loc[
                evaluation_data.index, PREDICTION_COLUMNS["croston_tsb"]
            ],
        )

    x_train = clean_train[FEATURE_COLUMNS].astype(float)
    y_train = clean_train["quantity_sold"].astype(float)
    x_test = test_data[FEATURE_COLUMNS].astype(float)

    for model_name, model in build_regressors().items():
        model.fit(x_train, y_train)
        prediction = model.predict(x_test).clip(min=0)
        prediction_column = PREDICTION_COLUMNS[model_name]
        test_data[prediction_column] = prediction
        evaluation_prediction = test_data.loc[
            evaluation_data.index,
            prediction_column,
        ]
        metrics[model_name] = calculate_metrics(
            evaluation_data["quantity_sold"],
            evaluation_prediction,
        )

    ranking = sorted(
        (
            {
                "model": model_name,
                "label": MODEL_LABELS[model_name],
                **model_metrics,
            }
            for model_name, model_metrics in metrics.items()
        ),
        key=lambda row: (row["mae"], row["rmse"], row["mape"]),
    )
    for rank, row in enumerate(ranking, start=1):
        row["rank"] = rank

    return {
        "test_data": test_data,
        "models": metrics,
        "ranking": ranking,
        "best_model": ranking[0]["model"],
        "prediction_columns": PREDICTION_COLUMNS,
        "training_rows": len(clean_train),
        "test_rows": len(evaluation_data),
        "excluded_train_stockouts": int(train_stockout.sum()),
        "excluded_test_stockouts": int(test_stockout.sum()),
        "demand_profile": demand_profile,
    }


class ForecastTrainingService:
    """Prépare les données, évalue les baselines et génère une prévision."""

    def __init__(self, db: Session):
        self.dataset_builder = SalesDatasetBuilder(db)

    def get_products(self) -> list[dict]:
        return self.dataset_builder.get_products()

    def get_available_date_range(self) -> dict:
        return self.dataset_builder.get_available_date_range()

    def prepare_dataset(self, product_id: UUID) -> pd.DataFrame:
        dataset = self.dataset_builder.build_product_daily_sales(product_id)
        if dataset.empty:
            return dataset

        dataset = add_calendar_features(
            dataset,
            self.dataset_builder.get_calendar_features(),
        )
        dataset = add_stock_features(
            dataset,
            self.dataset_builder.get_stock_features(product_id),
        )

        return add_lag_features(dataset)

    def train_and_forecast(
        self,
        product_id: UUID,
        horizon: int = 7,
    ) -> dict:
        if horizon <= 0:
            raise ValueError("L'horizon doit être supérieur à zéro.")

        dataset = self.prepare_dataset(product_id)
        if len(dataset) < 35:
            raise ValueError(
                "Au moins 35 jours d'historique sont nécessaires."
            )

        test_size = min(90, max(30, round(len(dataset) * 0.2)))
        split_index = len(dataset) - test_size
        train_data = dataset.iloc[:split_index]
        test_data = dataset.iloc[split_index:]

        evaluations: dict[str, dict[str, float]] = {}
        predictions: dict[str, pd.Series] = {}

        for name, baseline in BASELINES.items():
            full_prediction = baseline["predict"](dataset["quantity_sold"])
            test_prediction = full_prediction.iloc[split_index:]
            evaluations[name] = evaluate_forecast(
                test_data["quantity_sold"],
                test_prediction,
            )
            predictions[name] = test_prediction

        best_model = min(
            evaluations,
            key=lambda name: evaluations[name]["mae"],
        )
        forecast_values = BASELINES[best_model]["forecast"](
            dataset["quantity_sold"],
            horizon,
        )
        forecast_dates = pd.date_range(
            dataset["date"].max() + pd.Timedelta(days=1),
            periods=horizon,
            freq="D",
        )

        forecast = pd.DataFrame(
            {
                "date": forecast_dates,
                "predicted_quantity": forecast_values,
            }
        )
        history = dataset[["date", "quantity_sold"]].tail(90).copy()

        return {
            "best_model": best_model,
            "metrics": evaluations[best_model],
            "all_metrics": evaluations,
            "history": history,
            "forecast": forecast,
            "training_start_date": train_data["date"].min().date(),
            "training_end_date": train_data["date"].max().date(),
            "test_start_date": test_data["date"].min().date(),
            "test_end_date": test_data["date"].max().date(),
            "dataset_start_date": dataset["date"].min().date(),
            "dataset_end_date": dataset["date"].max().date(),
            "dataset_rows": len(dataset),
            "test_rows": len(test_data),
            "feature_count": len(dataset.columns),
        }
