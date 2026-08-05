from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor


FEATURE_COLUMNS = [
    "lag_1",
    "lag_7",
    "lag_14",
    "lag_21",
    "lag_28",
    "rolling_mean_7",
    "rolling_mean_14",
    "rolling_mean_28",
    "day_of_week",
    "month",
    "week_of_year",
    "is_weekend",
    "temperature_average",
    "rainfall",
    "is_ramadan_period",
    "is_tabaski_period",
    "stock_available",
    "stockout_flag",
]

MODEL_LABELS = {
    "lag_7": "Vente J-7",
    "moving_average_7": "Moyenne mobile 7 jours",
    "linear_regression": "Régression linéaire",
    "random_forest": "Random Forest",
    "xgboost": "XGBoost",
    "ets": "Holt-Winters (ETS)",
    "croston_tsb": "Croston TSB",
}

PREDICTION_COLUMNS = {
    "lag_7": "prediction_lag_7",
    "moving_average_7": "prediction_ma_7",
    "linear_regression": "prediction_linear_regression",
    "random_forest": "prediction_random_forest",
    "xgboost": "prediction_xgboost",
    "ets": "prediction_ets",
    "croston_tsb": "prediction_croston_tsb",
}


def build_xgboost_quantile(alpha: float, random_state: int = 42):
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            (
                "model",
                XGBRegressor(
                    objective="reg:quantileerror",
                    quantile_alpha=alpha,
                    n_estimators=300,
                    max_depth=5,
                    learning_rate=0.05,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    random_state=random_state,
                    n_jobs=1,
                ),
            ),
        ]
    )


def build_regressors(random_state: int = 42) -> dict:
    return {
        "linear_regression": Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                ("model", LinearRegression()),
            ]
        ),
        "random_forest": Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "model",
                    RandomForestRegressor(
                        n_estimators=300,
                        min_samples_leaf=2,
                        random_state=random_state,
                        n_jobs=1,
                    ),
                ),
            ]
        ),
        "xgboost": Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "model",
                    XGBRegressor(
                        n_estimators=300,
                        max_depth=5,
                        learning_rate=0.05,
                        subsample=0.8,
                        colsample_bytree=0.8,
                        objective="reg:squarederror",
                        random_state=random_state,
                        n_jobs=4,
                    ),
                ),
            ]
        ),
    }
