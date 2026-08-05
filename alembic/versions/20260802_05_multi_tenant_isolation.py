"""Add tenant ownership and PostgreSQL row-level security.

Revision ID: 20260802_05
Revises: 20260716_04
Create Date: 2026-08-02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260802_05"
down_revision: str | None = "20260716_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_COMPANY_ID = "00000000-0000-4000-8000-000000000001"

TENANT_TABLES = (
    "product_categories",
    "customer_types",
    "products",
    "customers",
    "suppliers",
    "import_batches",
    "import_batch_errors",
    "sales",
    "sale_items",
    "purchase_receipts",
    "purchase_receipt_items",
    "stock_movements",
    "daily_stocks",
    "model_runs",
    "forecasts",
    "forecast_results",
    "forecast_result_evaluations",
    "forecast_evaluations",
    "model_performance_reviews",
    "anomalies",
)

GLOBAL_UNIQUES = {
    "product_categories": (("code",), ("name",)),
    "customer_types": (("code",), ("name",)),
    "products": (("code",),),
    "customers": (("code",),),
    "suppliers": (("code",),),
    "import_batches": (("batch_number",),),
    "sales": (("sale_number",),),
    "purchase_receipts": (("receipt_number",),),
    "stock_movements": (("movement_number",),),
    "daily_stocks": (("stock_date", "product_id"),),
    "model_runs": (("run_number",),),
    "forecasts": (("forecast_number",),),
    "anomalies": (("anomaly_number",),),
}


def _constraint_name(table: str, columns: tuple[str, ...]) -> str:
    return f"{table}_{'_'.join(columns)}_key"


def _tenant_constraint_name(table: str, columns: tuple[str, ...]) -> str:
    return f"uq_{table}_company_{'_'.join(columns)}"


def upgrade() -> None:
    op.execute("""
        INSERT INTO companies (
            id, code, name, email, phone, city, currency, timezone,
            status, created_at, updated_at
        ) VALUES (
            '00000000-0000-4000-8000-000000000001',
            'depot-historique',
            'Dépôt historique',
            '', '', 'Bamako', 'XOF', 'Africa/Bamako', 'ACTIVE', NOW(), NOW()
        )
        ON CONFLICT (id) DO NOTHING
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION app_current_company_id()
        RETURNS UUID
        LANGUAGE SQL
        STABLE
        AS $$
            SELECT NULLIF(current_setting('app.current_company_id', TRUE), '')::UUID
        $$
    """)

    for table in TENANT_TABLES:
        op.add_column(
            table,
            sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.execute(
            f"UPDATE {table} SET company_id = '{LEGACY_COMPANY_ID}' "
            "WHERE company_id IS NULL"
        )
        op.create_foreign_key(
            f"fk_{table}_company",
            table,
            "companies",
            ["company_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.alter_column(
            table,
            "company_id",
            nullable=False,
            server_default=sa.text("app_current_company_id()"),
        )
        op.create_index(f"ix_{table}_company", table, ["company_id"])

    op.drop_constraint("uq_sales_external_reference", "sales", type_="unique")
    op.create_unique_constraint(
        "uq_sales_company_external_reference",
        "sales",
        ["company_id", "external_reference"],
    )

    for table, unique_sets in GLOBAL_UNIQUES.items():
        for columns in unique_sets:
            op.drop_constraint(_constraint_name(table, columns), table, type_="unique")
            op.create_unique_constraint(
                _tenant_constraint_name(table, columns),
                table,
                ("company_id", *columns),
            )

    op.drop_index("uq_products_business_identity", table_name="products")
    op.execute("""
        CREATE UNIQUE INDEX uq_products_company_business_identity
        ON products (
            company_id,
            LOWER(TRIM(name)),
            LOWER(TRIM(COALESCE(brand, ''))),
            COALESCE(volume_value, -1),
            LOWER(TRIM(COALESCE(volume_unit, ''))),
            LOWER(TRIM(package_type))
        )
    """)
    op.drop_index("uq_customers_normalized_phone", table_name="customers")
    op.execute("""
        CREATE UNIQUE INDEX uq_customers_company_normalized_phone
        ON customers (
            company_id,
            NULLIF(REGEXP_REPLACE(phone, '[^0-9]', '', 'g'), '')
        )
        WHERE NULLIF(REGEXP_REPLACE(phone, '[^0-9]', '', 'g'), '') IS NOT NULL
    """)

    op.create_index("ix_sales_company_date", "sales", ["company_id", "sale_date"])
    op.create_index(
        "ix_daily_stocks_company_product_date",
        "daily_stocks",
        ["company_id", "product_id", "stock_date"],
    )
    op.create_index(
        "ix_forecasts_company_status_end",
        "forecasts",
        ["company_id", "status", "forecast_end_date"],
    )

    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
            USING (company_id = app_current_company_id())
            WITH CHECK (company_id = app_current_company_id())
        """)

    # PostgreSQL superusers always bypass RLS. Docker local starts with the
    # postgres superuser, so create a restricted runtime role and let the
    # Streamlit session switch to it inside every transaction. Managed cloud
    # roles are normally non-superusers and simply skip this block.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_roles
                WHERE rolname = CURRENT_USER AND rolsuper = TRUE
            ) THEN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_roles
                    WHERE rolname = 'sales_predictive_tenant_runtime'
                ) THEN
                    CREATE ROLE sales_predictive_tenant_runtime NOLOGIN NOSUPERUSER NOBYPASSRLS;
                END IF;
                EXECUTE format(
                    'GRANT sales_predictive_tenant_runtime TO %I',
                    CURRENT_USER
                );
                GRANT USAGE ON SCHEMA public TO sales_predictive_tenant_runtime;
                GRANT SELECT, INSERT, UPDATE, DELETE
                    ON ALL TABLES IN SCHEMA public
                    TO sales_predictive_tenant_runtime;
                GRANT USAGE, SELECT
                    ON ALL SEQUENCES IN SCHEMA public
                    TO sales_predictive_tenant_runtime;
                ALTER DEFAULT PRIVILEGES IN SCHEMA public
                    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES
                    TO sales_predictive_tenant_runtime;
                ALTER DEFAULT PRIVILEGES IN SCHEMA public
                    GRANT USAGE, SELECT ON SEQUENCES
                    TO sales_predictive_tenant_runtime;
            END IF;
        END
        $$
    """)

    op.execute("DROP VIEW IF EXISTS v_sales_analysis")
    op.execute("""
        CREATE VIEW v_sales_analysis WITH (security_invoker = TRUE) AS
        SELECT
            s.company_id,
            s.sale_date,
            s.sale_number,
            s.customer_id,
            c.code AS customer_code,
            c.name AS customer_name,
            ct.name AS customer_type,
            c.zone,
            si.product_id,
            p.code AS product_code,
            p.name AS product_name,
            p.brand,
            pc.name AS category,
            si.quantity_packages,
            si.quantity_units,
            si.unit_price,
            si.discount_amount,
            si.total_amount,
            si.unit_cost,
            si.gross_margin,
            s.promotion_applied,
            s.payment_method,
            s.salesperson_name
        FROM sale_items si
        JOIN sales s ON s.id = si.sale_id AND s.company_id = si.company_id
        JOIN products p ON p.id = si.product_id AND p.company_id = si.company_id
        JOIN product_categories pc
          ON pc.id = p.category_id AND pc.company_id = si.company_id
        LEFT JOIN customers c
          ON c.id = s.customer_id AND c.company_id = si.company_id
        LEFT JOIN customer_types ct
          ON ct.id = c.customer_type_id AND ct.company_id = si.company_id
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_sales_analysis")
    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_forecasts_company_status_end", table_name="forecasts")
    op.drop_index("ix_daily_stocks_company_product_date", table_name="daily_stocks")
    op.drop_index("ix_sales_company_date", table_name="sales")
    op.drop_index("uq_customers_company_normalized_phone", table_name="customers")
    op.drop_index("uq_products_company_business_identity", table_name="products")

    for table, unique_sets in GLOBAL_UNIQUES.items():
        for columns in unique_sets:
            op.drop_constraint(_tenant_constraint_name(table, columns), table, type_="unique")
            op.create_unique_constraint(_constraint_name(table, columns), table, columns)

    op.drop_constraint("uq_sales_company_external_reference", "sales", type_="unique")
    op.create_unique_constraint("uq_sales_external_reference", "sales", ["external_reference"])

    for table in reversed(TENANT_TABLES):
        op.drop_index(f"ix_{table}_company", table_name=table)
        op.drop_constraint(f"fk_{table}_company", table, type_="foreignkey")
        op.drop_column(table, "company_id")

    op.execute("DROP FUNCTION IF EXISTS app_current_company_id()")
