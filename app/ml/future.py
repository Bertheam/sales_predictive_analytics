import math

import pandas as pd

from app.ml.baseline import forecast_lag_7, forecast_moving_average_7
from app.ml.models import FEATURE_COLUMNS, build_regressors


def _monthly_median(dataset: pd.DataFrame, column: str, month: int) -> float:
    monthly_values = dataset.loc[dataset["month"] == month, column].dropna()
    values = monthly_values if not monthly_values.empty else dataset[column].dropna()
    return float(values.median()) if not values.empty else 0.0


def _seasonal_flag(dataset: pd.DataFrame, column: str, forecast_date) -> bool:
    same_period = dataset[
        (dataset["date"].dt.month == forecast_date.month)
        & (dataset["date"].dt.day == forecast_date.day)
    ]
    if same_period.empty or column not in same_period:
        return False
    return bool(same_period[column].fillna(False).astype(bool).any())


def _lag(values: list[float], days: int) -> float:
    return float(values[-days]) if len(values) >= days else 0.0


def generate_iterative_forecast(
    *,
    dataset: pd.DataFrame,
    model_name: str,
    horizon: int,
    residual_std: float,
    selling_price: float,
    confidence_z: float = 1.96,
) -> dict:
    if horizon < 1 or horizon > 7:
        raise ValueError("L'horizon doit être compris entre 1 et 7 jours.")

    usable_data = dataset.dropna(subset=FEATURE_COLUMNS).copy()
    stockout = (
        usable_data["stockout_flag"].astype(bool)
        | (usable_data["stock_available"] <= 0)
    )
    training_data = usable_data.loc[~stockout].copy()
    if len(training_data) < 60:
        raise ValueError(
            "Pas assez de jours hors rupture pour réentraîner le modèle."
        )

    fitted_model = None
    if model_name not in {"lag_7", "moving_average_7"}:
        fitted_model = build_regressors()[model_name]
        fitted_model.fit(
            training_data[FEATURE_COLUMNS].astype(float),
            training_data["quantity_sold"].astype(float),
        )

    quantities = [float(value) for value in dataset["quantity_sold"]]
    latest_row = dataset.iloc[-1]
    simulated_stock = max(0.0, float(latest_row.get("closing_stock", 0)))
    current_stock = simulated_stock
    forecast_rows = []

    for step in range(1, horizon + 1):
        forecast_date = dataset["date"].max() + pd.Timedelta(days=step)
        rolling_7 = float(pd.Series(quantities[-7:]).mean())
        rolling_14 = float(pd.Series(quantities[-14:]).mean())
        rolling_28 = float(pd.Series(quantities[-28:]).mean())

        features = {
            "lag_1": _lag(quantities, 1),
            "lag_7": _lag(quantities, 7),
            "lag_14": _lag(quantities, 14),
            "lag_21": _lag(quantities, 21),
            "lag_28": _lag(quantities, 28),
            "rolling_mean_7": rolling_7,
            "rolling_mean_14": rolling_14,
            "rolling_mean_28": rolling_28,
            "day_of_week": forecast_date.dayofweek,
            "month": forecast_date.month,
            "week_of_year": int(forecast_date.isocalendar().week),
            "is_weekend": int(forecast_date.dayofweek in (5, 6)),
            "temperature_average": _monthly_median(
                dataset,
                "temperature_average",
                forecast_date.month,
            ),
            "rainfall": _monthly_median(
                dataset,
                "rainfall",
                forecast_date.month,
            ),
            "is_ramadan_period": int(
                _seasonal_flag(dataset, "is_ramadan_period", forecast_date)
            ),
            "is_tabaski_period": int(
                _seasonal_flag(dataset, "is_tabaski_period", forecast_date)
            ),
            "stock_available": simulated_stock,
            "stockout_flag": int(simulated_stock <= 0),
        }

        if model_name == "lag_7":
            prediction = forecast_lag_7(pd.Series(quantities), 1)[0]
        elif model_name == "moving_average_7":
            prediction = forecast_moving_average_7(
                pd.Series(quantities),
                1,
            )[0]
        else:
            feature_frame = pd.DataFrame([features])[FEATURE_COLUMNS]
            prediction = float(
                fitted_model.predict(feature_frame.astype(float))[0]
            )

        prediction = max(0.0, prediction)
        margin = confidence_z * residual_std * math.sqrt(step)
        lower_bound = max(0.0, prediction - margin)
        upper_bound = max(prediction, prediction + margin)

        stock_need = max(0.0, upper_bound - simulated_stock)
        stock_after_replenishment = simulated_stock + stock_need
        projected_closing_stock = max(
            0.0,
            stock_after_replenishment - prediction,
        )

        forecast_rows.append(
            {
                "date": forecast_date,
                "predicted_quantity": prediction,
                "lower_bound": lower_bound,
                "upper_bound": upper_bound,
                "stock_available": simulated_stock,
                "stock_need": stock_need,
                "projected_closing_stock": projected_closing_stock,
                "predicted_revenue": prediction * selling_price,
            }
        )

        quantities.append(prediction)
        simulated_stock = projected_closing_stock

    return {
        "forecast": pd.DataFrame(forecast_rows),
        "current_stock": current_stock,
        "training_rows": len(training_data),
        "training_start_date": training_data["date"].min().date(),
        "training_end_date": training_data["date"].max().date(),
    }
