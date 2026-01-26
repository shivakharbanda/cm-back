"""Add user_id to bio_pages table.

Revision ID: 004_add_user_id_to_bio_pages
Revises: 003_add_link_in_bio
Create Date: 2024-01-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "004_add_user_id_to_bio_pages"
down_revision: Union[str, None] = "003_add_link_in_bio"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add user_id column (nullable initially)
    op.add_column(
        "bio_pages",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # Populate user_id from instagram_accounts
    op.execute("""
        UPDATE bio_pages
        SET user_id = (
            SELECT user_id FROM instagram_accounts
            WHERE instagram_accounts.id = bio_pages.instagram_account_id
        )
    """)

    # Make user_id not null
    op.alter_column("bio_pages", "user_id", nullable=False)

    # Drop the existing foreign key on instagram_account_id
    op.drop_constraint(
        "bio_pages_instagram_account_id_fkey", "bio_pages", type_="foreignkey"
    )

    # Make instagram_account_id nullable
    op.alter_column("bio_pages", "instagram_account_id", nullable=True)

    # Re-add foreign key with SET NULL on delete
    op.create_foreign_key(
        "bio_pages_instagram_account_id_fkey",
        "bio_pages",
        "instagram_accounts",
        ["instagram_account_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Add unique constraint and index on user_id
    op.create_index("ix_bio_pages_user_id", "bio_pages", ["user_id"], unique=True)

    # Add foreign key for user_id
    op.create_foreign_key(
        "bio_pages_user_id_fkey",
        "bio_pages",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # Drop user_id foreign key
    op.drop_constraint("bio_pages_user_id_fkey", "bio_pages", type_="foreignkey")

    # Drop user_id index
    op.drop_index("ix_bio_pages_user_id", table_name="bio_pages")

    # Drop the SET NULL foreign key on instagram_account_id
    op.drop_constraint(
        "bio_pages_instagram_account_id_fkey", "bio_pages", type_="foreignkey"
    )

    # Make instagram_account_id not null (will fail if there are null values)
    op.alter_column("bio_pages", "instagram_account_id", nullable=False)

    # Re-add original foreign key with CASCADE on delete
    op.create_foreign_key(
        "bio_pages_instagram_account_id_fkey",
        "bio_pages",
        "instagram_accounts",
        ["instagram_account_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Drop user_id column
    op.drop_column("bio_pages", "user_id")
