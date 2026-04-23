"""Add error reason fields to dm_sent_log.

Revision ID: 012_add_dm_error_reason
Revises: 011_add_button_template
Create Date: 2026-04-23 00:00:00.000000

Changes:
- Add nullable Text column `error_message` and Integer columns `error_code`
  and `error_subcode` to `dm_sent_log`. Populated whenever the Meta Graph
  API returns a classified error (RetryableGraphAPIError or
  PermanentGraphAPIError). Lets the UI surface the actual reason a DM
  failed instead of showing a bare "failed" badge.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "012_add_dm_error_reason"
down_revision: Union[str, None] = "011_add_button_template"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("dm_sent_log", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("dm_sent_log", sa.Column("error_code", sa.Integer(), nullable=True))
    op.add_column("dm_sent_log", sa.Column("error_subcode", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("dm_sent_log", "error_subcode")
    op.drop_column("dm_sent_log", "error_code")
    op.drop_column("dm_sent_log", "error_message")
