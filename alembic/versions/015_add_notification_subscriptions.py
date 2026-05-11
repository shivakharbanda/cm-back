"""Add notification_subscriptions table.

Revision ID: 015_notification_subscriptions
Revises: 014_add_contact_submissions
Create Date: 2026-05-11 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "015_notification_subscriptions"
down_revision: Union[str, None] = "014_add_contact_submissions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", "notification_type", name="uq_notification_subscription_email_type"),
    )
    op.create_index("ix_notification_subscriptions_email", "notification_subscriptions", ["email"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_notification_subscriptions_email", table_name="notification_subscriptions")
    op.drop_table("notification_subscriptions")
