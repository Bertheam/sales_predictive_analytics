import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing


def prepare_demand_series(values, stockout_mask=None) -> pd.Series:
    series = pd.Series(values, dtype=float).reset_index(drop=True).clip(lower=0)
    if stockout_mask is not None:
        mask = pd.Series(stockout_mask, dtype=bool).reset_index(drop=True)
        series = series.mask(mask)
    return series.interpolate(limit_direction="both").fillna(0.0)


def forecast_ets(values, horizon: int, seasonal_periods: int = 7) -> np.ndarray:
    series = prepare_demand_series(values)
    if len(series) < seasonal_periods * 4:
        raise ValueError("ETS nécessite au moins quatre cycles saisonniers.")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = ExponentialSmoothing(
            series,
            trend="add",
            seasonal="add",
            seasonal_periods=seasonal_periods,
            initialization_method="estimated",
        ).fit(optimized=True, remove_bias=True)
    return np.clip(np.asarray(model.forecast(horizon), dtype=float), 0, None)


def forecast_tsb(
    values,
    horizon: int,
    demand_alpha: float = 0.2,
    probability_alpha: float = 0.1,
) -> np.ndarray:
    """Teunter-Syntetos-Babai forecast for intermittent demand."""
    series = prepare_demand_series(values)
    non_zero = series[series > 0]
    if non_zero.empty:
        return np.zeros(horizon, dtype=float)

    demand_size = float(non_zero.iloc[0])
    probability = 1.0 / max(int((series > 0).idxmax()) + 1, 1)
    for value in series:
        occurred = float(value > 0)
        probability += probability_alpha * (occurred - probability)
        if occurred:
            demand_size += demand_alpha * (float(value) - demand_size)
    return np.full(horizon, max(0.0, probability * demand_size), dtype=float)


def classify_demand(values) -> dict:
    series = prepare_demand_series(values)
    zero_ratio = float((series <= 0).mean()) if len(series) else 0.0
    return {
        "zero_ratio": zero_ratio,
        "is_intermittent": zero_ratio >= 0.40,
        "label": "INTERMITTENTE" if zero_ratio >= 0.40 else "RÉGULIÈRE",
    }
