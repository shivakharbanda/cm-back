"""Add social_links table.

Revision ID: 005_add_social_links
Revises: 004_add_user_id_to_bio_pages
Create Date: 2024-01-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "005_add_social_links"
down_revision: Union[str, None] = "004_add_user_id_to_bio_pages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum type
    social_platform_enum = postgresql.ENUM(
        'instagram', 'twitter', 'youtube', 'tiktok', 'linkedin', 'website',
        name='social_platform_enum',
        create_type=False
    )
    social_platform_enum.create(op.get_bind(), checkfirst=True)

    # Create social_links table
    op.create_table(
        'social_links',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('bio_page_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            'platform',
            postgresql.ENUM(
                'instagram', 'twitter', 'youtube', 'tiktok', 'linkedin', 'website',
                name='social_platform_enum',
                create_type=False
            ),
            nullable=False
        ),
        sa.Column('url', sa.String(500), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, default=0),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['bio_page_id'], ['bio_pages.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('bio_page_id', 'platform', name='uq_social_link_platform'),
    )
    op.create_index('ix_social_links_bio_page_id', 'social_links', ['bio_page_id'], unique=False)


def downgrade() -> None:
    op.drop_table('social_links')
    op.execute('DROP TYPE IF EXISTS social_platform_enum')
