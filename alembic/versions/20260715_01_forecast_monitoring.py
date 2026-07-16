"""Add forecast monitoring and model performance tables.

Revision ID: 20260715_01
Revises:
Create Date: 2026-07-15
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260715_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "forecasts",
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "forecasts",
        sa.Column(
            "status_updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_forecasts_status_end_date",
        "forecasts",
        ["status", "forecast_end_date"],
    )

    op.create_table(
        "forecast_result_evaluations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "forecast_result_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("forecast_results.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "forecast_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("forecasts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("actual_quantity", sa.Numeric(16, 2), nullable=False),
        sa.Column("absolute_error", sa.Numeric(16, 2), nullable=False),
        sa.Column("squared_error", sa.Numeric(20, 4), nullable=False),
        sa.Column(
            "absolute_percentage_error",
            sa.Numeric(18, 6),
            nullable=True,
        ),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_forecast_result_evaluations_forecast",
        "forecast_result_evaluations",
        ["forecast_id"],
    )

    op.create_table(
        "forecast_evaluations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "forecast_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("forecasts.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id"),
            nullable=False,
        ),
        sa.Column(
            "model_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("model_runs.id"),
            nullable=True,
        ),
        sa.Column("predicted_quantity", sa.Numeric(18, 2), nullable=False),
        sa.Column("actual_quantity", sa.Numeric(18, 2), nullable=False),
        sa.Column("absolute_error", sa.Numeric(18, 2), nullable=False),
        sa.Column("mae", sa.Numeric(18, 6), nullable=False),
        sa.Column("rmse", sa.Numeric(18, 6), nullable=False),
        sa.Column("mape", sa.Numeric(18, 6), nullable=True),
        sa.Column("performance_status", sa.String(20), nullable=False),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_forecast_evaluations_product_date",
        "forecast_evaluations",
        ["product_id", "evaluated_at"],
    )

    op.create_table(
        "model_performance_reviews",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id"),
            nullable=False,
        ),
        sa.Column("review_date", sa.Date(), nullable=False),
        sa.Column("period_start_date", sa.Date(), nullable=False),
        sa.Column("period_end_date", sa.Date(), nullable=False),
        sa.Column("previous_model", sa.String(100), nullable=True),
        sa.Column("recommended_model", sa.String(100), nullable=False),
        sa.Column(
            "metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_model_performance_reviews_product_date",
        "model_performance_reviews",
        ["product_id", "review_date"],
    )

    op.execute("""
        UPDATE forecasts
        SET status = 'ACTIVE', status_updated_at = NOW()
        WHERE status = 'COMPLETED'
    """)


def downgrade() -> None:
    op.drop_index(
        "ix_model_performance_reviews_product_date",
        table_name="model_performance_reviews",
    )
    op.drop_table("model_performance_reviews")
    op.drop_index(
        "ix_forecast_evaluations_product_date",
        table_name="forecast_evaluations",
    )
    op.drop_table("forecast_evaluations")
    op.drop_index(
        "ix_forecast_result_evaluations_forecast",
        table_name="forecast_result_evaluations",
    )
    op.drop_table("forecast_result_evaluations")
    op.drop_index("ix_forecasts_status_end_date", table_name="forecasts")
    op.drop_column("forecasts", "status_updated_at")
    op.drop_column("forecasts", "evaluated_at")
