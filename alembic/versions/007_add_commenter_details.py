"""Add commenter profile fields to dm_sent_log and comment_reply_log.

Revision ID: 007_add_commenter_details
Revises: 006_add_comment_reply_log
Create Date: 2024-01-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "007_add_commenter_details"
down_revision: Union[str, None] = "006_add_comment_reply_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # DMSentLog columns
    op.add_column('dm_sent_log', sa.Column('commenter_username', sa.String(100), nullable=True))
    op.add_column('dm_sent_log', sa.Column('commenter_name', sa.String(255), nullable=True))
    op.add_column('dm_sent_log', sa.Column('commenter_biography', sa.Text(), nullable=True))
    op.add_column('dm_sent_log', sa.Column('commenter_followers_count', sa.Integer(), nullable=True))
    op.add_column('dm_sent_log', sa.Column('commenter_media_count', sa.Integer(), nullable=True))
    op.add_column('dm_sent_log', sa.Column('commenter_profile_picture_url', sa.String(500), nullable=True))

    # CommentReplyLog columns
    op.add_column('comment_reply_log', sa.Column('commenter_username', sa.String(100), nullable=True))
    op.add_column('comment_reply_log', sa.Column('commenter_name', sa.String(255), nullable=True))
    op.add_column('comment_reply_log', sa.Column('commenter_biography', sa.Text(), nullable=True))
    op.add_column('comment_reply_log', sa.Column('commenter_followers_count', sa.Integer(), nullable=True))
    op.add_column('comment_reply_log', sa.Column('commenter_media_count', sa.Integer(), nullable=True))
    op.add_column('comment_reply_log', sa.Column('commenter_profile_picture_url', sa.String(500), nullable=True))


def downgrade() -> None:
    # CommentReplyLog columns
    op.drop_column('comment_reply_log', 'commenter_profile_picture_url')
    op.drop_column('comment_reply_log', 'commenter_media_count')
    op.drop_column('comment_reply_log', 'commenter_followers_count')
    op.drop_column('comment_reply_log', 'commenter_biography')
    op.drop_column('comment_reply_log', 'commenter_name')
    op.drop_column('comment_reply_log', 'commenter_username')

    # DMSentLog columns
    op.drop_column('dm_sent_log', 'commenter_profile_picture_url')
    op.drop_column('dm_sent_log', 'commenter_media_count')
    op.drop_column('dm_sent_log', 'commenter_followers_count')
    op.drop_column('dm_sent_log', 'commenter_biography')
    op.drop_column('dm_sent_log', 'commenter_name')
    op.drop_column('dm_sent_log', 'commenter_username')
