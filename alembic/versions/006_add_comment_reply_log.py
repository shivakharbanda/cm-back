"""Add comment_reply_log table.

Revision ID: 006_add_comment_reply_log
Revises: 005_add_social_links
Create Date: 2024-01-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "006_add_comment_reply_log"
down_revision: Union[str, None] = "005_add_social_links"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'comment_reply_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('automation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('post_id', sa.String(100), nullable=False),
        sa.Column('comment_id', sa.String(100), nullable=False),
        sa.Column('commenter_user_id', sa.String(100), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column(
            'sent_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['automation_id'], ['automations.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_comment_reply_log_automation_id', 'comment_reply_log', ['automation_id'], unique=False)
    op.create_index('ix_comment_reply_log_post_id', 'comment_reply_log', ['post_id'], unique=False)
    op.create_index('ix_comment_reply_log_comment_id', 'comment_reply_log', ['comment_id'], unique=False)
    op.create_index('ix_comment_reply_log_commenter_user_id', 'comment_reply_log', ['commenter_user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_comment_reply_log_commenter_user_id', table_name='comment_reply_log')
    op.drop_index('ix_comment_reply_log_comment_id', table_name='comment_reply_log')
    op.drop_index('ix_comment_reply_log_post_id', table_name='comment_reply_log')
    op.drop_index('ix_comment_reply_log_automation_id', table_name='comment_reply_log')
    op.drop_table('comment_reply_log')
