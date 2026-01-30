"""Add carousel message support to automations.

Revision ID: 008_add_carousel_support
Revises: 007_add_commenter_details
Create Date: 2026-01-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision: str = "008_add_carousel_support"
down_revision: Union[str, None] = "007_add_commenter_details"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Create the message_type enum
    message_type_enum = sa.Enum('text', 'carousel', name='message_type_enum')
    message_type_enum.create(conn, checkfirst=True)

    # Check if message_type column exists
    result = conn.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='automations' AND column_name='message_type'"
        )
    ).scalar_one_or_none()

    if result is None:
        # Add message_type column with default 'text' for existing rows
        op.add_column(
            'automations',
            sa.Column(
                'message_type',
                message_type_enum,
                nullable=False,
                server_default='text',
            ),
        )

    # Check if carousel_elements column exists
    result = conn.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='automations' AND column_name='carousel_elements'"
        )
    ).scalar_one_or_none()

    if result is None:
        # Add carousel_elements JSON column
        op.add_column(
            'automations',
            sa.Column('carousel_elements', JSON, nullable=True),
        )

    # Make dm_message_template nullable (not needed for carousel type)
    op.alter_column(
        'automations',
        'dm_message_template',
        existing_type=sa.Text(),
        nullable=True,
    )


def downgrade() -> None:
    conn = op.get_bind()

    # Make dm_message_template non-nullable again
    op.alter_column(
        'automations',
        'dm_message_template',
        existing_type=sa.Text(),
        nullable=False,
    )

    # Check if carousel_elements column exists before dropping
    result = conn.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='automations' AND column_name='carousel_elements'"
        )
    ).scalar_one_or_none()

    if result is not None:
        op.drop_column('automations', 'carousel_elements')

    # Check if message_type column exists before dropping
    result = conn.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='automations' AND column_name='message_type'"
        )
    ).scalar_one_or_none()

    if result is not None:
        op.drop_column('automations', 'message_type')

    # Drop the enum type
    sa.Enum(name='message_type_enum').drop(conn, checkfirst=True)
