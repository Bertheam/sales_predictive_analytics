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
    for column in ("predicted_p50", "predicted_p80", "predicted_p90"):
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
