"""Enforce same-company references for tenant business tables.

Revision ID: 20260812_09
Revises: 20260805_08
Create Date: 2026-08-12
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260812_09"
down_revision: str | None = "20260805_08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PARENT_TABLES = (
    "product_categories",
    "customer_types",
    "products",
    "customers",
    "suppliers",
    "import_batches",
    "sales",
    "purchase_receipts",
    "model_runs",
    "forecasts",
    "forecast_results",
)


# name, child table, child identifier, parent table, delete behavior
TENANT_FOREIGN_KEYS = (
    ("fk_products_tenant_category", "products", "category_id", "product_categories", None),
    ("fk_customers_tenant_type", "customers", "customer_type_id", "customer_types", None),
    ("fk_import_errors_tenant_batch", "import_batch_errors", "import_batch_id", "import_batches", "CASCADE"),
    ("fk_sales_tenant_customer", "sales", "customer_id", "customers", None),
    ("fk_sales_tenant_import_batch", "sales", "import_batch_id", "import_batches", None),
    ("fk_sale_items_tenant_sale", "sale_items", "sale_id", "sales", "CASCADE"),
    ("fk_sale_items_tenant_product", "sale_items", "product_id", "products", None),
    ("fk_receipts_tenant_supplier", "purchase_receipts", "supplier_id", "suppliers", None),
    ("fk_receipt_items_tenant_receipt", "purchase_receipt_items", "purchase_receipt_id", "purchase_receipts", "CASCADE"),
    ("fk_receipt_items_tenant_product", "purchase_receipt_items", "product_id", "products", None),
    ("fk_movements_tenant_product", "stock_movements", "product_id", "products", None),
    ("fk_daily_stocks_tenant_product", "daily_stocks", "product_id", "products", None),
    ("fk_forecasts_tenant_product", "forecasts", "product_id", "products", None),
    ("fk_forecasts_tenant_category", "forecasts", "category_id", "product_categories", None),
    ("fk_forecasts_tenant_model_run", "forecasts", "model_run_id", "model_runs", None),
    ("fk_forecast_results_tenant_forecast", "forecast_results", "forecast_id", "forecasts", "CASCADE"),
    ("fk_result_evaluations_tenant_result", "forecast_result_evaluations", "forecast_result_id", "forecast_results", "CASCADE"),
    ("fk_result_evaluations_tenant_forecast", "forecast_result_evaluations", "forecast_id", "forecasts", "CASCADE"),
    ("fk_forecast_evaluations_tenant_forecast", "forecast_evaluations", "forecast_id", "forecasts", "CASCADE"),
    ("fk_forecast_evaluations_tenant_product", "forecast_evaluations", "product_id", "products", None),
    ("fk_forecast_evaluations_tenant_model", "forecast_evaluations", "model_run_id", "model_runs", None),
    ("fk_model_reviews_tenant_product", "model_performance_reviews", "product_id", "products", None),
    ("fk_anomalies_tenant_product", "anomalies", "product_id", "products", None),
    ("fk_anomalies_tenant_sale", "anomalies", "sale_id", "sales", None),
)


def _parent_constraint(table: str) -> str:
    return f"uq_tenant_{table}_company_id_id"


def upgrade() -> None:
    for table in PARENT_TABLES:
        op.create_unique_constraint(
            _parent_constraint(table),
            table,
            ["company_id", "id"],
        )

    for name, child, child_id, parent, ondelete in TENANT_FOREIGN_KEYS:
        op.create_foreign_key(
            name,
            child,
            parent,
            ["company_id", child_id],
            ["company_id", "id"],
            ondelete=ondelete,
        )


def downgrade() -> None:
    for name, child, _, _, _ in reversed(TENANT_FOREIGN_KEYS):
        op.drop_constraint(name, child, type_="foreignkey")

    for table in reversed(PARENT_TABLES):
        op.drop_constraint(_parent_constraint(table), table, type_="unique")
