"""Add email outbox, verification tokens, and email/password columns to users.

Revision ID: 013_add_email_and_verification
Revises: 012_add_dm_error_reason
Create Date: 2026-05-01 00:00:00.000000

Changes:
- Add nullable `email_verified_at` (TIMESTAMP WITH TIME ZONE) to users
- Add `password_changed_at` (TIMESTAMP WITH TIME ZONE, NOT NULL DEFAULT now()) to users
  — access tokens issued before this value are rejected, enabling post-reset invalidation
- Create `verification_tokens` table (password-reset + email-verification one-time tokens)
- Create `email_outbox` table (transactional outbox for durable async email delivery)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "013_add_email_and_verification"
down_revision: Union[str, None] = "012_add_dm_error_reason"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users: new columns ---
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "password_changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # --- ENUM types (idempotent — safe to re-run if a prior attempt left orphan types) ---
    op.execute(sa.text(
        "DO $$ BEGIN "
        "CREATE TYPE token_purpose AS ENUM ('password_reset', 'email_verification'); "
        "EXCEPTION WHEN duplicate_object THEN null; "
        "END $$"
    ))
    op.execute(sa.text(
        "DO $$ BEGIN "
        "CREATE TYPE outbox_status AS ENUM ('pending', 'sending', 'sent', 'failed'); "
        "EXCEPTION WHEN duplicate_object THEN null; "
        "END $$"
    ))

    # --- verification_tokens ---
    op.create_table(
        "verification_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "purpose",
            postgresql.ENUM("password_reset", "email_verification", name="token_purpose", create_type=False),
            nullable=False,
        ),
        sa.Column("secret_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("request_ip", postgresql.INET(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_verification_tokens_user_id", "verification_tokens", ["user_id"])
    op.create_index("ix_verification_tokens_secret_hash", "verification_tokens", ["secret_hash"])
    op.create_index(
        "ix_verification_tokens_user_purpose_consumed",
        "verification_tokens",
        ["user_id", "purpose", "consumed_at"],
    )

    # --- email_outbox ---
    op.create_table(
        "email_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("to_address", sa.String(320), nullable=False),
        sa.Column("template_name", sa.String(64), nullable=False),
        sa.Column("context_json", postgresql.JSONB(), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("pending", "sending", "sent", "failed", name="outbox_status", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_message_id", sa.String(128), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(
        "ix_email_outbox_status_next_attempt", "email_outbox", ["status", "next_attempt_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_email_outbox_status_next_attempt", table_name="email_outbox")
    op.drop_table("email_outbox")

    op.drop_index("ix_verification_tokens_user_purpose_consumed", table_name="verification_tokens")
    op.drop_index("ix_verification_tokens_secret_hash", table_name="verification_tokens")
    op.drop_index("ix_verification_tokens_user_id", table_name="verification_tokens")
    op.drop_table("verification_tokens")

    sa.Enum(name="outbox_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="token_purpose").drop(op.get_bind(), checkfirst=True)

    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "email_verified_at")
