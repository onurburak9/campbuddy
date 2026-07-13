"""add partial unique index on users.email for non-deleted rows

Revision ID: 9c8a6a399e34
Revises: 58ddbce58871
Create Date: 2026-07-09 15:31:43.467385

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c8a6a399e34'
down_revision: Union[str, None] = '58ddbce58871'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The original `users` table was created with a table-level UNIQUE(email)
# constraint (see d4b57c9112f7_initial.py). SQLite stores that as an
# unnamed constraint, so alembic's autogenerate can't detect its removal or
# drop it by name directly. We give it a deterministic name via
# naming_convention purely for this migration so batch mode (SQLite's
# "recreate table" strategy, required to alter/drop a table constraint) can
# reference it.
_NAMING_CONVENTION = {"uq": "uq_%(table_name)s_%(column_0_name)s"}


def upgrade() -> None:
    with op.batch_alter_table("users", naming_convention=_NAMING_CONVENTION) as batch_op:
        batch_op.drop_constraint("uq_users_email", type_="unique")

    op.create_index(
        "ix_users_email_active",
        "users",
        ["email"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_users_email_active", table_name="users", sqlite_where=sa.text("deleted_at IS NULL"))

    with op.batch_alter_table("users", naming_convention=_NAMING_CONVENTION) as batch_op:
        batch_op.create_unique_constraint("uq_users_email", ["email"])
