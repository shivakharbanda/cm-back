"""Add comment reply fields to automation.

Revision ID: 002_add_comment_reply_fields
Revises: 001_initial
Create Date: 2026-01-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "002_add_comment_reply_fields"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "automations",
        sa.Column("comment_reply_enabled", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "automations",
        sa.Column("comment_reply_template", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("automations", "comment_reply_template")
    op.drop_column("automations", "comment_reply_enabled")
