import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error


def calculate_metrics(y_true, y_pred) -> dict[str, float]:
    actual = np.asarray(y_true, dtype=float)
    predicted = np.asarray(y_pred, dtype=float)

    mae = mean_absolute_error(actual, predicted)
    rmse = np.sqrt(mean_squared_error(actual, predicted))

    non_zero = actual != 0
    if non_zero.any():
        mape = np.mean(
            np.abs((actual[non_zero] - predicted[non_zero]) / actual[non_zero])
        ) * 100
    else:
        mape = 0.0

    denominator = np.abs(actual).sum()
    wape = np.abs(actual - predicted).sum() / denominator * 100 if denominator else 0.0
    bias = np.mean(predicted - actual)

    return {
        "mae": float(mae),
        "rmse": float(rmse),
        "mape": float(mape),
        "wape": float(wape),
        "bias": float(bias),
    }


def pinball_loss(y_true, y_pred, quantile: float) -> float:
    actual = np.asarray(y_true, dtype=float)
    predicted = np.asarray(y_pred, dtype=float)
    error = actual - predicted
    return float(np.mean(np.maximum(quantile * error, (quantile - 1) * error)))


def evaluate_forecast(
    actual: pd.Series,
    predicted: pd.Series,
) -> dict[str, float]:
    comparison = pd.DataFrame(
        {
            "actual": actual,
            "predicted": predicted,
        }
    ).dropna()

    if comparison.empty:
        raise ValueError("Aucune prédiction ne peut être évaluée.")

    return calculate_metrics(comparison["actual"], comparison["predicted"])
