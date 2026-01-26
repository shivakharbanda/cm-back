"""Add Link-in-Bio tables.

Revision ID: 003_add_link_in_bio
Revises: 002_add_comment_reply_fields
Create Date: 2024-01-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003_add_link_in_bio"
down_revision: Union[str, None] = "002_add_comment_reply_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enums
    link_type_enum = postgresql.ENUM(
        "standard", "smart", name="link_type_enum", create_type=False
    )
    link_type_enum.create(op.get_bind(), checkfirst=True)

    item_type_enum = postgresql.ENUM(
        "link", "card", name="item_type_enum", create_type=False
    )
    item_type_enum.create(op.get_bind(), checkfirst=True)

    rule_type_enum = postgresql.ENUM(
        "country", "device", "time", name="rule_type_enum", create_type=False
    )
    rule_type_enum.create(op.get_bind(), checkfirst=True)

    source_type_enum = postgresql.ENUM(
        "card", "whatsapp", "other", name="source_type_enum", create_type=False
    )
    source_type_enum.create(op.get_bind(), checkfirst=True)

    event_type_enum = postgresql.ENUM(
        "page_view", "link_click", "card_view", "card_submit",
        name="event_type_enum", create_type=False
    )
    event_type_enum.create(op.get_bind(), checkfirst=True)

    aggregate_type_enum = postgresql.ENUM(
        "daily", "weekly", "monthly", name="aggregate_type_enum", create_type=False
    )
    aggregate_type_enum.create(op.get_bind(), checkfirst=True)

    # Create bio_pages table
    op.create_table(
        "bio_pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instagram_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=True),
        sa.Column("bio_text", sa.Text(), nullable=True),
        sa.Column("profile_image_url", sa.String(500), nullable=True),
        sa.Column("theme_config", postgresql.JSONB(), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, default=False),
        sa.Column("seo_title", sa.String(70), nullable=True),
        sa.Column("seo_description", sa.String(160), nullable=True),
        sa.Column("og_image_url", sa.String(500), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
    op.create_index("ix_bio_pages_slug", "bio_pages", ["slug"], unique=True)
    op.create_index(
        "ix_bio_pages_instagram_account_id",
        "bio_pages",
        ["instagram_account_id"],
        unique=True,
    )

    # Create bio_links table
    op.create_table(
        "bio_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bio_page_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column(
            "link_type",
            postgresql.ENUM("standard", "smart", name="link_type_enum", create_type=False),
            nullable=False,
            server_default="standard",
        ),
        sa.Column("position", sa.Integer(), nullable=False, default=0),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("visible_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("visible_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("thumbnail_url", sa.String(500), nullable=True),
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
        sa.ForeignKeyConstraint(["bio_page_id"], ["bio_pages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bio_links_bio_page_id", "bio_links", ["bio_page_id"], unique=False)

    # Create bio_cards table
    op.create_table(
        "bio_cards",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bio_page_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("badge_text", sa.String(30), nullable=True),
        sa.Column("headline", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("background_color", sa.String(7), nullable=False, server_default="#000000"),
        sa.Column("background_image_url", sa.String(500), nullable=True),
        sa.Column("cta_text", sa.String(50), nullable=False),
        sa.Column("destination_url", sa.String(2048), nullable=False),
        sa.Column("success_message", sa.String(200), nullable=True),
        sa.Column("requires_email", sa.Boolean(), nullable=False, default=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("visible_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("visible_until", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["bio_page_id"], ["bio_pages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bio_cards_bio_page_id", "bio_cards", ["bio_page_id"], unique=False)

    # Create page_items table (unified ordering)
    op.create_table(
        "page_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bio_page_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "item_type",
            postgresql.ENUM("link", "card", name="item_type_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, default=0),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["bio_page_id"], ["bio_pages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_page_items_bio_page_id", "page_items", ["bio_page_id"], unique=False)
    op.create_index("ix_page_items_position", "page_items", ["position"], unique=False)
    op.create_unique_constraint(
        "uq_page_items_bio_page_item",
        "page_items",
        ["bio_page_id", "item_type", "item_id"],
    )

    # Create routing_rules table
    op.create_table(
        "routing_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bio_link_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "rule_type",
            postgresql.ENUM("country", "device", "time", name="rule_type_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("rule_config", postgresql.JSONB(), nullable=False),
        sa.Column("destination_url", sa.String(2048), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, default=0),
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
        sa.ForeignKeyConstraint(["bio_link_id"], ["bio_links.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_routing_rules_bio_link_id", "routing_rules", ["bio_link_id"], unique=False)

    # Create leads table
    op.create_table(
        "leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bio_page_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bio_card_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column(
            "source_type",
            postgresql.ENUM("card", "whatsapp", "other", name="source_type_enum", create_type=False),
            nullable=False,
            server_default="card",
        ),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["bio_page_id"], ["bio_pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["bio_card_id"], ["bio_cards.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_leads_bio_page_id", "leads", ["bio_page_id"], unique=False)
    op.create_index("ix_leads_bio_card_id", "leads", ["bio_card_id"], unique=False)
    op.create_index("ix_leads_email", "leads", ["email"], unique=False)

    # Create analytics_events table
    op.create_table(
        "analytics_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bio_page_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bio_link_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("bio_card_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "event_type",
            postgresql.ENUM(
                "page_view", "link_click", "card_view", "card_submit",
                name="event_type_enum", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("visitor_data", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(["bio_page_id"], ["bio_pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["bio_link_id"], ["bio_links.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["bio_card_id"], ["bio_cards.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analytics_events_bio_page_id", "analytics_events", ["bio_page_id"], unique=False)
    op.create_index("ix_analytics_events_bio_link_id", "analytics_events", ["bio_link_id"], unique=False)
    op.create_index("ix_analytics_events_bio_card_id", "analytics_events", ["bio_card_id"], unique=False)
    op.create_index("ix_analytics_events_occurred_at", "analytics_events", ["occurred_at"], unique=False)
    # GIN index for JSONB queries
    op.execute(
        "CREATE INDEX ix_analytics_events_visitor_data ON analytics_events USING GIN (visitor_data)"
    )

    # Create analytics_aggregates table
    op.create_table(
        "analytics_aggregates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bio_page_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bio_link_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("bio_card_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "aggregate_type",
            postgresql.ENUM("daily", "weekly", "monthly", name="aggregate_type_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("page_views", sa.Integer(), nullable=False, default=0),
        sa.Column("link_clicks", sa.Integer(), nullable=False, default=0),
        sa.Column("card_views", sa.Integer(), nullable=False, default=0),
        sa.Column("card_submits", sa.Integer(), nullable=False, default=0),
        sa.Column("unique_visitors", sa.Integer(), nullable=False, default=0),
        sa.Column("breakdown_data", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(["bio_page_id"], ["bio_pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["bio_link_id"], ["bio_links.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["bio_card_id"], ["bio_cards.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analytics_aggregates_bio_page_id", "analytics_aggregates", ["bio_page_id"], unique=False)
    op.create_unique_constraint(
        "uq_analytics_aggregates_period",
        "analytics_aggregates",
        ["bio_page_id", "bio_link_id", "bio_card_id", "aggregate_type", "period_start"],
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("analytics_aggregates")
    op.drop_table("analytics_events")
    op.drop_table("leads")
    op.drop_table("routing_rules")
    op.drop_table("page_items")
    op.drop_table("bio_cards")
    op.drop_table("bio_links")
    op.drop_table("bio_pages")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS aggregate_type_enum")
    op.execute("DROP TYPE IF EXISTS event_type_enum")
    op.execute("DROP TYPE IF EXISTS source_type_enum")
    op.execute("DROP TYPE IF EXISTS rule_type_enum")
    op.execute("DROP TYPE IF EXISTS item_type_enum")
    op.execute("DROP TYPE IF EXISTS link_type_enum")
