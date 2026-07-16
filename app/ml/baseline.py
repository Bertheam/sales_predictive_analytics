from collections.abc import Callable

import numpy as np
import pandas as pd


def predict_lag_7(values: pd.Series) -> pd.Series:
    return values.shift(7).clip(lower=0)


def predict_moving_average_7(values: pd.Series) -> pd.Series:
    return values.shift(1).rolling(7).mean().clip(lower=0)


def forecast_lag_7(history: pd.Series, horizon: int) -> list[float]:
    values = [float(value) for value in history]
    forecasts: list[float] = []

    for _ in range(horizon):
        prediction = values[-7] if len(values) >= 7 else np.mean(values)
        prediction = max(0.0, float(prediction))
        forecasts.append(prediction)
        values.append(prediction)

    return forecasts


def forecast_moving_average_7(
    history: pd.Series,
    horizon: int,
) -> list[float]:
    values = [float(value) for value in history]
    forecasts: list[float] = []

    for _ in range(horizon):
        prediction = float(np.mean(values[-7:]))
        prediction = max(0.0, prediction)
        forecasts.append(prediction)
        values.append(prediction)

    return forecasts


BASELINES: dict[str, dict[str, Callable]] = {
    "Décalage de 7 jours": {
        "predict": predict_lag_7,
        "forecast": forecast_lag_7,
    },
    "Moyenne mobile 7 jours": {
        "predict": predict_moving_average_7,
        "forecast": forecast_moving_average_7,
    },
}
