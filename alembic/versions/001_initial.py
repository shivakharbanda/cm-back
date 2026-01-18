"""Initial migration with all tables.

Revision ID: 001_initial
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create trigger_type enum
    trigger_type_enum = postgresql.ENUM(
        "all_comments", "keyword", name="trigger_type_enum", create_type=False
    )
    trigger_type_enum.create(op.get_bind(), checkfirst=True)

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # Create instagram_accounts table
    op.create_table(
        "instagram_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instagram_user_id", sa.String(100), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_instagram_accounts_user_id", "instagram_accounts", ["user_id"], unique=False
    )
    op.create_index(
        "ix_instagram_accounts_instagram_user_id",
        "instagram_accounts",
        ["instagram_user_id"],
        unique=False,
    )

    # Create automations table
    op.create_table(
        "automations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instagram_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("post_id", sa.String(100), nullable=False),
        sa.Column(
            "trigger_type",
            postgresql.ENUM("all_comments", "keyword", name="trigger_type_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("keywords", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("dm_message_template", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["instagram_account_id"], ["instagram_accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_automations_instagram_account_id",
        "automations",
        ["instagram_account_id"],
        unique=False,
    )
    op.create_index("ix_automations_post_id", "automations", ["post_id"], unique=False)

    # Create dm_sent_log table
    op.create_table(
        "dm_sent_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("automation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("post_id", sa.String(100), nullable=False),
        sa.Column("commenter_user_id", sa.String(100), nullable=False),
        sa.Column("comment_id", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["automation_id"], ["automations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_dm_sent_log_automation_id", "dm_sent_log", ["automation_id"], unique=False
    )
    op.create_index("ix_dm_sent_log_post_id", "dm_sent_log", ["post_id"], unique=False)
    op.create_index(
        "ix_dm_sent_log_commenter_user_id", "dm_sent_log", ["commenter_user_id"], unique=False
    )
    op.create_index("ix_dm_sent_log_comment_id", "dm_sent_log", ["comment_id"], unique=False)


def downgrade() -> None:
    op.drop_table("dm_sent_log")
    op.drop_table("automations")
    op.drop_table("instagram_accounts")
    op.drop_table("users")

    # Drop enum type
    op.execute("DROP TYPE IF EXISTS trigger_type_enum")
