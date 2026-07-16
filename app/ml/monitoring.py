import numpy as np
import pandas as pd


def evaluate_forecast_rows(rows: list[dict]) -> dict:
    data = pd.DataFrame(rows)
    if data.empty:
        raise ValueError("Aucun résultat journalier à évaluer.")

    data["predicted_quantity"] = data["predicted_quantity"].astype(float)
    data["actual_quantity"] = data["actual_quantity"].astype(float)
    errors = data["actual_quantity"] - data["predicted_quantity"]
    data["absolute_error"] = errors.abs()
    data["squared_error"] = errors**2
    data["absolute_percentage_error"] = np.where(
        data["actual_quantity"] != 0,
        data["absolute_error"] / data["actual_quantity"].abs() * 100,
        np.nan,
    )

    mae = float(data["absolute_error"].mean())
    rmse = float(np.sqrt(data["squared_error"].mean()))
    mape_values = data["absolute_percentage_error"].dropna()
    mape = float(mape_values.mean()) if not mape_values.empty else None
    actual_total = float(data["actual_quantity"].sum())
    predicted_total = float(data["predicted_quantity"].sum())
    normalized_mae = mae / max(float(data["actual_quantity"].mean()), 1.0)

    if normalized_mae <= 0.15:
        performance_status = "GOOD"
    elif normalized_mae <= 0.30:
        performance_status = "WATCH"
    else:
        performance_status = "POOR"

    return {
        "daily": data.to_dict("records"),
        "predicted_quantity": predicted_total,
        "actual_quantity": actual_total,
        "absolute_error": abs(actual_total - predicted_total),
        "mae": mae,
        "rmse": rmse,
        "mape": mape,
        "performance_status": performance_status,
    }


def calculate_drift(
    evaluations: list[dict],
) -> dict:
    if not evaluations:
        return {
            "current_mae": None,
            "previous_mae": None,
            "drift_status": "INSUFFICIENT_DATA",
        }

    data = pd.DataFrame(evaluations)
    data["forecast_end_date"] = pd.to_datetime(data["forecast_end_date"])
    latest_date = data["forecast_end_date"].max()
    current_start = latest_date - pd.Timedelta(days=29)
    previous_start = current_start - pd.Timedelta(days=30)

    current = data[data["forecast_end_date"] >= current_start]
    previous = data[
        (data["forecast_end_date"] >= previous_start)
        & (data["forecast_end_date"] < current_start)
    ]

    current_mae = float(current["mae"].mean()) if not current.empty else None
    previous_mae = float(previous["mae"].mean()) if not previous.empty else None

    if current_mae is None or previous_mae is None or previous_mae == 0:
        drift_status = "INSUFFICIENT_DATA"
    elif current_mae > previous_mae * 1.20:
        drift_status = "DECLINING"
    elif current_mae < previous_mae * 0.80:
        drift_status = "IMPROVING"
    else:
        drift_status = "STABLE"

    return {
        "current_mae": current_mae,
        "previous_mae": previous_mae,
        "drift_status": drift_status,
    }
