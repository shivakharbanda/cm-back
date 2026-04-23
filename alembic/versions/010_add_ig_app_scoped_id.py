"""Add instagram_app_scoped_id to instagram_accounts.

Revision ID: 010_add_ig_app_scoped_id
Revises: 009_add_dm_dedup
Create Date: 2026-04-23 00:00:00.000000

Changes:
- Add nullable String(100) column `instagram_app_scoped_id` to `instagram_accounts`.
  Stores the app-scoped user id returned by /oauth/access_token (distinct from
  the Instagram professional account id stored in `instagram_user_id`, which is
  the one Meta puts into webhook `entry.id`).
- Index the column for lookup parity with `instagram_user_id`.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "010_add_ig_app_scoped_id"
down_revision: Union[str, None] = "009_add_dm_dedup"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "instagram_accounts",
        sa.Column("instagram_app_scoped_id", sa.String(length=100), nullable=True),
    )
    op.create_index(
        "ix_instagram_accounts_instagram_app_scoped_id",
        "instagram_accounts",
        ["instagram_app_scoped_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_instagram_accounts_instagram_app_scoped_id",
        table_name="instagram_accounts",
    )
    op.drop_column("instagram_accounts", "instagram_app_scoped_id")
