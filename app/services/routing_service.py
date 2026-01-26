"""Service for routing rules and smart link resolution."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BioLink, BioPage, RoutingRule, RuleType
from app.schemas.routing_rule import RoutingRuleCreate, RoutingRuleUpdate


class RoutingService:
    """Service for routing rule operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_link(self, link_id: UUID, user_id: UUID) -> BioLink | None:
        """Get bio link if it belongs to user."""
        result = await self.db.execute(
            select(BioLink)
            .join(BioPage)
            .where(
                BioLink.id == link_id,
                BioPage.user_id == user_id,
                BioPage.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def create_rule(
        self, link_id: UUID, data: RoutingRuleCreate, user_id: UUID
    ) -> RoutingRule:
        """Create a routing rule for a smart link."""
        link = await self._get_link(link_id, user_id)
        if not link:
            raise ValueError("Bio link not found or doesn't belong to user")

        rule = RoutingRule(
            bio_link_id=link_id,
            rule_type=data.rule_type,
            rule_config=data.rule_config,
            destination_url=data.destination_url,
            priority=data.priority,
            is_active=data.is_active,
        )
        self.db.add(rule)
        await self.db.flush()
        await self.db.refresh(rule)

        return rule

    async def get_rule(self, rule_id: UUID, user_id: UUID) -> RoutingRule | None:
        """Get a routing rule by ID if it belongs to user."""
        result = await self.db.execute(
            select(RoutingRule)
            .join(BioLink)
            .join(BioPage)
            .where(
                RoutingRule.id == rule_id,
                BioPage.user_id == user_id,
                BioPage.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_rules(self, link_id: UUID, user_id: UUID) -> list[RoutingRule]:
        """List all routing rules for a link."""
        link = await self._get_link(link_id, user_id)
        if not link:
            raise ValueError("Bio link not found or doesn't belong to user")

        result = await self.db.execute(
            select(RoutingRule)
            .where(RoutingRule.bio_link_id == link_id)
            .order_by(RoutingRule.priority)
        )
        return list(result.scalars().all())

    async def update_rule(
        self, rule_id: UUID, data: RoutingRuleUpdate, user_id: UUID
    ) -> RoutingRule | None:
        """Update a routing rule."""
        rule = await self.get_rule(rule_id, user_id)
        if not rule:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(rule, field, value)

        await self.db.flush()
        await self.db.refresh(rule)

        return rule

    async def delete_rule(self, rule_id: UUID, user_id: UUID) -> bool:
        """Delete a routing rule."""
        rule = await self.get_rule(rule_id, user_id)
        if not rule:
            return False

        await self.db.delete(rule)
        await self.db.flush()

        return True

    async def resolve_destination(
        self, link_id: UUID, visitor_data: dict[str, Any]
    ) -> str:
        """Evaluate rules in priority order, return first match or fallback."""
        # Get link with its rules
        result = await self.db.execute(
            select(BioLink).where(BioLink.id == link_id)
        )
        link = result.scalar_one_or_none()

        if not link:
            raise ValueError("Link not found")

        # Get active rules ordered by priority
        result = await self.db.execute(
            select(RoutingRule)
            .where(
                RoutingRule.bio_link_id == link_id,
                RoutingRule.is_active == True,
            )
            .order_by(RoutingRule.priority)
        )
        rules = list(result.scalars().all())

        # Evaluate each rule
        for rule in rules:
            if self._matches_rule(rule, visitor_data):
                return rule.destination_url

        # Fallback to default URL
        return link.url

    def _matches_rule(
        self, rule: RoutingRule, visitor_data: dict[str, Any]
    ) -> bool:
        """Check if visitor data matches a routing rule."""
        config = rule.rule_config

        if rule.rule_type == RuleType.COUNTRY:
            countries = config.get("countries", [])
            visitor_country = visitor_data.get("country")
            return visitor_country in countries

        elif rule.rule_type == RuleType.DEVICE:
            devices = config.get("devices", [])
            visitor_device = visitor_data.get("device_type")
            return visitor_device in devices

        elif rule.rule_type == RuleType.TIME:
            return self._matches_time_rule(config, visitor_data)

        return False

    def _matches_time_rule(
        self, config: dict[str, Any], visitor_data: dict[str, Any]
    ) -> bool:
        """Check if current time matches a time-based rule."""
        try:
            import pytz
        except ImportError:
            # Fallback if pytz not available
            return False

        tz_name = config.get("timezone", "UTC")
        try:
            tz = pytz.timezone(tz_name)
        except pytz.UnknownTimeZoneError:
            tz = pytz.UTC

        now = datetime.now(tz)
        current_hour = now.hour
        current_weekday = now.isoweekday()  # 1=Monday, 7=Sunday

        start_hour = config.get("start_hour", 0)
        end_hour = config.get("end_hour", 24)
        days = config.get("days", [1, 2, 3, 4, 5, 6, 7])

        # Check day
        if current_weekday not in days:
            return False

        # Check hour
        if start_hour <= end_hour:
            # Normal range (e.g., 9-17)
            return start_hour <= current_hour < end_hour
        else:
            # Overnight range (e.g., 22-6)
            return current_hour >= start_hour or current_hour < end_hour
