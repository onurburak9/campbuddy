"""add availability lifecycle to scan_results

Revision ID: 1630918bdc90
Revises: e48548624895
Create Date: 2026-07-01 16:05:41.725258

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1630918bdc90'
down_revision: Union[str, None] = 'e48548624895'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_available NOT NULL with a server-side default so existing rows get True.
    # Add last_seen_at nullable first; backfill from first_seen_at; then enforce NOT NULL.
    with op.batch_alter_table("scan_results") as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_available",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
        batch_op.add_column(
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True)
        )

    op.execute("UPDATE scan_results SET last_seen_at = first_seen_at WHERE last_seen_at IS NULL")

    with op.batch_alter_table("scan_results") as batch_op:
        batch_op.alter_column(
            "last_seen_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("scan_results") as batch_op:
        batch_op.drop_column("last_seen_at")
        batch_op.drop_column("is_available")
