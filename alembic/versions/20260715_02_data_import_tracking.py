"""Add detailed data import tracking.

Revision ID: 20260715_02
Revises: 20260715_01
Create Date: 2026-07-15
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260715_02"
down_revision: str | None = "20260715_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "import_batches",
        sa.Column("file_hash", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_import_batches_file_hash",
        "import_batches",
        ["file_hash"],
    )
    op.create_table(
        "import_batch_errors",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "import_batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("import_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False),
        sa.Column("error_messages", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_import_batch_errors_batch",
        "import_batch_errors",
        ["import_batch_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_import_batch_errors_batch",
        table_name="import_batch_errors",
    )
    op.drop_table("import_batch_errors")
    op.drop_index("ix_import_batches_file_hash", table_name="import_batches")
    op.drop_column("import_batches", "file_hash")
