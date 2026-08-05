"""Add supplier codes and supplier business uniqueness.

Revision ID: 20260802_07
Revises: 20260802_06
Create Date: 2026-08-02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260802_07"
down_revision: str | None = "20260802_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE supplier_code_seq")
    op.execute("""
        SELECT setval(
            'supplier_code_seq',
            COALESCE((
                SELECT MAX(substring(code FROM '[0-9]+$')::BIGINT)
                FROM suppliers
                WHERE code ~ '^FRS-[0-9]+$'
            ), 0) + 1,
            FALSE
        )
    """)
    op.alter_column(
        "suppliers",
        "code",
        server_default=sa.text(
            "'FRS-' || LPAD(nextval('supplier_code_seq')::TEXT, 6, '0')"
        ),
    )
    op.execute("""
        CREATE UNIQUE INDEX uq_suppliers_company_normalized_name_active
        ON suppliers (company_id, LOWER(TRIM(name)))
        WHERE deleted_at IS NULL
    """)


def downgrade() -> None:
    op.drop_index(
        "uq_suppliers_company_normalized_name_active", table_name="suppliers"
    )
    op.alter_column("suppliers", "code", server_default=None)
    op.execute("DROP SEQUENCE supplier_code_seq")
