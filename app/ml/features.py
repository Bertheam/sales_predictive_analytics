import pandas as pd


def add_time_features(dataset: pd.DataFrame) -> pd.DataFrame:
    result = dataset.copy()
    result["date"] = pd.to_datetime(result["date"])
    result["day_of_week"] = result["date"].dt.dayofweek
    result["day_of_month"] = result["date"].dt.day
    result["month"] = result["date"].dt.month
    result["week_of_year"] = (
        result["date"].dt.isocalendar().week.astype(int)
    )
    result["is_weekend"] = result["day_of_week"].isin([5, 6]).astype(int)

    return result


def add_calendar_features(
    dataset: pd.DataFrame,
    calendar_features: pd.DataFrame,
) -> pd.DataFrame:
    result = dataset.copy()
    result["date"] = pd.to_datetime(result["date"])

    if not calendar_features.empty:
        result = result.merge(calendar_features, on="date", how="left")

    iso_calendar = result["date"].dt.isocalendar()
    derived_features = {
        "day_of_week": result["date"].dt.dayofweek + 1,
        "week_number": iso_calendar.week.astype(int),
        "month_number": result["date"].dt.month,
        "quarter_number": result["date"].dt.quarter,
        "is_weekend": result["date"].dt.dayofweek >= 5,
        "is_end_of_month": result["date"].dt.is_month_end,
        "is_start_of_month": result["date"].dt.is_month_start,
    }

    for column, values in derived_features.items():
        if column not in result:
            result[column] = values
        else:
            result[column] = result[column].fillna(values)

    boolean_columns = [
        "is_weekend",
        "is_public_holiday",
        "is_ramadan_period",
        "is_tabaski_period",
        "is_end_of_month",
        "is_start_of_month",
    ]
    for column in boolean_columns:
        if column not in result:
            result[column] = False
        result[column] = result[column].fillna(False).astype(bool)

    return result


def add_stock_features(
    dataset: pd.DataFrame,
    stock_features: pd.DataFrame,
) -> pd.DataFrame:
    result = dataset.copy()

    if stock_features.empty:
        stock_columns = [
            "opening_stock",
            "quantity_received",
            "quantity_damaged",
            "closing_stock",
            "minimum_stock",
        ]
        for column in stock_columns:
            result[column] = 0.0
        result["stock_available"] = 0.0
        result["stockout_flag"] = False
        return result

    result = result.merge(stock_features, on="date", how="left")
    stock_columns = [
        "opening_stock",
        "quantity_received",
        "quantity_damaged",
        "closing_stock",
        "minimum_stock",
    ]
    result[stock_columns] = result[stock_columns].fillna(0).astype(float)
    # Le stock d'ouverture est connu avant les ventes du jour. Utiliser le
    # stock de clôture introduirait la quantité vendue dans les features.
    result["stock_available"] = result["opening_stock"]
    result["stockout_flag"] = result["stockout_flag"].fillna(False).astype(bool)

    return result


def add_lag_features(
    dataset: pd.DataFrame,
    target_column: str = "quantity_sold",
) -> pd.DataFrame:
    result = dataset.sort_values("date").reset_index(drop=True).copy()

    for lag in (1, 7, 14, 21, 28):
        result[f"lag_{lag}"] = result[target_column].shift(lag)

    past_values = result[target_column].shift(1)
    result["rolling_mean_7"] = past_values.rolling(7).mean()
    result["rolling_mean_14"] = past_values.rolling(14).mean()
    result["rolling_mean_28"] = past_values.rolling(28).mean()
    result["rolling_std_7"] = past_values.rolling(7).std()

    return result
