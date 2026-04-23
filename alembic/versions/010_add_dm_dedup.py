"""Add DM dedup unique constraint and widen commenter_profile_picture_url.

Revision ID: 009_add_dm_dedup
Revises: 008_add_carousel_support
Create Date: 2026-04-23 00:00:00.000000

Changes:
- Deduplicate existing dm_sent_log rows on (automation_id, commenter_user_id, post_id),
  keeping the earliest sent_at.
- Add UNIQUE constraint on (automation_id, commenter_user_id, post_id) to prevent
  race-condition duplicate DMs between concurrent workers.
- Add composite index (automation_id, post_id, commenter_user_id) to accelerate dedup
  lookups.
- Widen commenter_profile_picture_url from String(500) to Text on both dm_sent_log
  and comment_reply_log (Instagram signed CDN URLs frequently exceed 500 chars,
  causing DataError on flush after the DM was already sent -> duplicate DM on retry).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "009_add_dm_dedup"
down_revision: Union[str, None] = "008_add_carousel_support"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Deduplicate existing rows. Keep the oldest sent_at per key.
    conn.execute(
        sa.text(
            """
            DELETE FROM dm_sent_log
            WHERE id IN (
                SELECT id FROM (
                    SELECT id,
                           ROW_NUMBER() OVER (
                               PARTITION BY automation_id, commenter_user_id, post_id
                               ORDER BY sent_at ASC, id ASC
                           ) AS rn
                    FROM dm_sent_log
                ) ranked
                WHERE rn > 1
            )
            """
        )
    )

    # 2. Unique constraint for dedup.
    op.create_unique_constraint(
        "uq_dm_sent_log_dedup",
        "dm_sent_log",
        ["automation_id", "commenter_user_id", "post_id"],
    )

    # 3. Composite index for the dedup SELECT path.
    op.create_index(
        "ix_dm_sent_log_dedup_lookup",
        "dm_sent_log",
        ["automation_id", "post_id", "commenter_user_id"],
    )

    # 4. Widen pfp URL on both log tables.
    op.alter_column(
        "dm_sent_log",
        "commenter_profile_picture_url",
        existing_type=sa.String(length=500),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "comment_reply_log",
        "commenter_profile_picture_url",
        existing_type=sa.String(length=500),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "comment_reply_log",
        "commenter_profile_picture_url",
        existing_type=sa.Text(),
        type_=sa.String(length=500),
        existing_nullable=True,
    )
    op.alter_column(
        "dm_sent_log",
        "commenter_profile_picture_url",
        existing_type=sa.Text(),
        type_=sa.String(length=500),
        existing_nullable=True,
    )
    op.drop_index("ix_dm_sent_log_dedup_lookup", table_name="dm_sent_log")
    op.drop_constraint("uq_dm_sent_log_dedup", "dm_sent_log", type_="unique")
