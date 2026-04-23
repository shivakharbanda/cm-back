"""Add button-template message type to automations.

Revision ID: 011_add_button_template
Revises: 010_add_ig_app_scoped_id
Create Date: 2026-04-23 00:00:00.000000

Changes:
- Append 'button' to `message_type_enum`.
- Add nullable JSON column `automations.button_template` storing
  `{"text": str, "buttons": [{type, title, url?, payload?}, ...]}`
  per Meta's Instagram button template spec.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


revision: str = "011_add_button_template"
down_revision: Union[str, None] = "010_add_ig_app_scoped_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Postgres 12+ allows ADD VALUE inside a transaction; the new value can't
    # be used until the transaction commits, which is fine — nothing in this
    # migration inserts a 'button' row.
    op.execute("ALTER TYPE message_type_enum ADD VALUE IF NOT EXISTS 'button'")

    op.add_column(
        "automations",
        sa.Column("button_template", JSON, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("automations", "button_template")
    # Postgres has no DROP VALUE for enums. Leaving 'button' in the enum is
    # harmless — rows using it were deleted by the column drop above.
