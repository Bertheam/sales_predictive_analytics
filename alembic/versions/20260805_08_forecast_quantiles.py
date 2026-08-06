"""Persist P50, P80 and P90 forecast quantiles.

Revision ID: 20260805_08
Revises: 20260802_07
Create Date: 2026-08-05
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260805_08"
down_revision: str | None = "20260802_07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    existing_columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("forecast_results")
    }
    quantile_columns = {"predicted_p50", "predicted_p80", "predicted_p90"}

    # Fresh installations load the current SQL schema before Alembic runs. In
    # that case the quantile columns and their checks already exist, while
    # upgraded installations still need this revision to add them.
    if quantile_columns.issubset(existing_columns):
        return

    for column in ("predicted_p50", "predicted_p80", "predicted_p90"):
        if column in existing_columns:
            continue
        op.add_column(
            "forecast_results",
            sa.Column(column, sa.Numeric(16, 2), nullable=True),
        )
        op.create_check_constraint(
            f"ck_forecast_results_{column}_nonnegative",
            "forecast_results",
            f"{column} IS NULL OR {column} >= 0",
        )
    op.create_check_constraint(
        "ck_forecast_results_quantile_order_50_80",
        "forecast_results",
        "predicted_p50 IS NULL OR predicted_p80 IS NULL OR predicted_p80 >= predicted_p50",
    )
    op.create_check_constraint(
        "ck_forecast_results_quantile_order_80_90",
        "forecast_results",
        "predicted_p80 IS NULL OR predicted_p90 IS NULL OR predicted_p90 >= predicted_p80",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_forecast_results_quantile_order_80_90", "forecast_results", type_="check"
    )
    op.drop_constraint(
        "ck_forecast_results_quantile_order_50_80", "forecast_results", type_="check"
    )
    for column in reversed(("predicted_p50", "predicted_p80", "predicted_p90")):
        op.drop_constraint(
            f"ck_forecast_results_{column}_nonnegative",
            "forecast_results",
            type_="check",
        )
        op.drop_column("forecast_results", column)
