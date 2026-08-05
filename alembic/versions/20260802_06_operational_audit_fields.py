"""Add soft deletion and authorship to operational entities.

Revision ID: 20260802_06
Revises: 20260802_05
Create Date: 2026-08-02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260802_06"
down_revision: str | None = "20260802_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOFT_DELETABLE_TABLES = ("products", "customers", "suppliers", "sales", "purchase_receipts")
AUTHOR_TABLES = (*SOFT_DELETABLE_TABLES, "stock_movements")


def upgrade() -> None:
    for table in AUTHOR_TABLES:
        op.add_column(table, sa.Column("created_by_user_id", sa.BigInteger(), nullable=True))
        op.add_column(table, sa.Column("updated_by_user_id", sa.BigInteger(), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_created_by_user",
            table,
            "accounts_user",
            ["created_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            f"fk_{table}_updated_by_user",
            table,
            "accounts_user",
            ["updated_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )

    for table in SOFT_DELETABLE_TABLES:
        op.add_column(table, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column("deleted_by_user_id", sa.BigInteger(), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_deleted_by_user",
            table,
            "accounts_user",
            ["deleted_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(f"ix_{table}_company_deleted", table, ["company_id", "deleted_at"])

    op.add_column(
        "stock_movements",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )


def downgrade() -> None:
    op.drop_column("stock_movements", "updated_at")
    for table in reversed(SOFT_DELETABLE_TABLES):
        op.drop_index(f"ix_{table}_company_deleted", table_name=table)
        op.drop_constraint(f"fk_{table}_deleted_by_user", table, type_="foreignkey")
        op.drop_column(table, "deleted_by_user_id")
        op.drop_column(table, "deleted_at")
    for table in reversed(AUTHOR_TABLES):
        op.drop_constraint(f"fk_{table}_updated_by_user", table, type_="foreignkey")
        op.drop_constraint(f"fk_{table}_created_by_user", table, type_="foreignkey")
        op.drop_column(table, "updated_by_user_id")
        op.drop_column(table, "created_by_user_id")
