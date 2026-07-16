"""Generate receipt and movement numbers.

Revision ID: 20260716_04
Revises: 20260716_03
Create Date: 2026-07-16
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260716_04"
down_revision: str | None = "20260716_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE receipt_number_seq")
    op.execute("CREATE SEQUENCE movement_number_seq")
    op.execute("""
        SELECT setval(
            'receipt_number_seq',
            COALESCE((
                SELECT MAX(substring(receipt_number FROM '[0-9]+$')::BIGINT)
                FROM purchase_receipts
                WHERE receipt_number ~ '^REC-[0-9]+$'
            ), 0) + 1,
            FALSE
        )
    """)
    op.execute("""
        SELECT setval(
            'movement_number_seq',
            COALESCE((
                SELECT MAX(substring(movement_number FROM '[0-9]+$')::BIGINT)
                FROM stock_movements
                WHERE movement_number ~ '^MVT-[0-9]+$'
            ), 0) + 1,
            FALSE
        )
    """)
    op.alter_column(
        "purchase_receipts",
        "receipt_number",
        server_default=sa.text(
            "'REC-' || LPAD(nextval('receipt_number_seq')::TEXT, 7, '0')"
        ),
    )
    op.alter_column(
        "stock_movements",
        "movement_number",
        server_default=sa.text(
            "'MVT-' || LPAD(nextval('movement_number_seq')::TEXT, 9, '0')"
        ),
    )


def downgrade() -> None:
    op.alter_column("stock_movements", "movement_number", server_default=None)
    op.alter_column("purchase_receipts", "receipt_number", server_default=None)
    op.execute("DROP SEQUENCE movement_number_seq")
    op.execute("DROP SEQUENCE receipt_number_seq")
