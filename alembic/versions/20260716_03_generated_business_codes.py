"""Generate internal codes and enforce business uniqueness.

Revision ID: 20260716_03
Revises: 20260715_02
Create Date: 2026-07-16
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260716_03"
down_revision: str | None = "20260715_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE product_code_seq")
    op.execute("CREATE SEQUENCE customer_code_seq")
    op.execute("CREATE SEQUENCE sale_number_seq")
    op.execute("""
        SELECT setval(
            'product_code_seq',
            COALESCE((
                SELECT MAX(substring(code FROM '[0-9]+$')::BIGINT)
                FROM products
                WHERE code ~ '^PRD-[0-9]+$'
            ), 0) + 1,
            FALSE
        )
    """)
    op.execute("""
        SELECT setval(
            'customer_code_seq',
            COALESCE((
                SELECT MAX(substring(code FROM '[0-9]+$')::BIGINT)
                FROM customers
                WHERE code ~ '^CLI-[0-9]+$'
            ), 0) + 1,
            FALSE
        )
    """)
    op.execute("""
        SELECT setval(
            'sale_number_seq',
            COALESCE((
                SELECT MAX(substring(sale_number FROM '[0-9]+$')::BIGINT)
                FROM sales
                WHERE sale_number ~ '^VTE-[0-9]+$'
            ), 0) + 1,
            FALSE
        )
    """)

    op.alter_column(
        "products",
        "code",
        server_default=sa.text(
            "'PRD-' || LPAD(nextval('product_code_seq')::TEXT, 6, '0')"
        ),
    )
    op.alter_column(
        "customers",
        "code",
        server_default=sa.text(
            "'CLI-' || LPAD(nextval('customer_code_seq')::TEXT, 6, '0')"
        ),
    )
    op.alter_column(
        "sales",
        "sale_number",
        server_default=sa.text(
            "'VTE-' || LPAD(nextval('sale_number_seq')::TEXT, 9, '0')"
        ),
    )
    op.add_column(
        "sales",
        sa.Column("external_reference", sa.String(100), nullable=True),
    )
    op.create_unique_constraint(
        "uq_sales_external_reference",
        "sales",
        ["external_reference"],
    )
    op.execute("""
        CREATE UNIQUE INDEX uq_products_business_identity
        ON products (
            LOWER(TRIM(name)),
            LOWER(TRIM(COALESCE(brand, ''))),
            COALESCE(volume_value, -1),
            LOWER(TRIM(COALESCE(volume_unit, ''))),
            LOWER(TRIM(package_type))
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_customers_normalized_phone
        ON customers (
            NULLIF(REGEXP_REPLACE(phone, '[^0-9]', '', 'g'), '')
        )
        WHERE NULLIF(REGEXP_REPLACE(phone, '[^0-9]', '', 'g'), '') IS NOT NULL
    """)


def downgrade() -> None:
    op.drop_index("uq_customers_normalized_phone", table_name="customers")
    op.drop_index("uq_products_business_identity", table_name="products")
    op.drop_constraint(
        "uq_sales_external_reference",
        "sales",
        type_="unique",
    )
    op.drop_column("sales", "external_reference")
    op.alter_column("sales", "sale_number", server_default=None)
    op.alter_column("customers", "code", server_default=None)
    op.alter_column("products", "code", server_default=None)
    op.execute("DROP SEQUENCE sale_number_seq")
    op.execute("DROP SEQUENCE customer_code_seq")
    op.execute("DROP SEQUENCE product_code_seq")
