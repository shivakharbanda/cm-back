"""Comment processor service for handling Instagram comment webhooks."""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import Automation, DMSentLog, InstagramAccount
from app.models.automation import TriggerType
from app.services.instagram_client import instagram_client

logger = logging.getLogger(__name__)


@dataclass
class CommentEvent:
    """Parsed comment event from webhook payload."""

    message_id: str
    account_id: str
    comment_id: str
    comment_text: str
    commenter_id: str
    commenter_username: str
    media_id: str
    media_type: str
    timestamp: datetime

    @classmethod
    def from_webhook_payload(cls, payload: dict[str, Any]) -> "CommentEvent | None":
        """Parse webhook payload into CommentEvent.

        Expected payload structure:
        {
            "id": "message-uuid",
            "timestamp": "2026-01-18T12:11:04.631004Z",
            "source": "instagram",
            "event_type": "comments",
            "account_id": "17841477945568576",
            "raw_payload": {
                "id": "17841477945568576",
                "time": 1768738264,
                "changes": [{
                    "value": {
                        "from": {"id": "2151717415361060", "username": "user123"},
                        "media": {"id": "18332496949209541", "media_product_type": "REELS"},
                        "id": "18008498738674951",
                        "text": "Location"
                    },
                    "field": "comments"
                }]
            }
        }
        """
        try:
            raw = payload.get("raw_payload", {})
            changes = raw.get("changes", [])

            if not changes:
                logger.warning("No changes in webhook payload")
                return None

            # Get first comment change
            change = changes[0]
            if change.get("field") != "comments":
                logger.warning(f"Unexpected field type: {change.get('field')}")
                return None

            value = change.get("value", {})
            from_data = value.get("from", {})
            media_data = value.get("media", {})

            return cls(
                message_id=payload.get("id", ""),
                account_id=payload.get("account_id", ""),
                comment_id=value.get("id", ""),
                comment_text=value.get("text", ""),
                commenter_id=from_data.get("id", ""),
                commenter_username=from_data.get("username", ""),
                media_id=media_data.get("id", ""),
                media_type=media_data.get("media_product_type", ""),
                timestamp=datetime.fromisoformat(
                    payload.get("timestamp", datetime.now(timezone.utc).isoformat())
                    .replace("Z", "+00:00")
                ),
            )
        except Exception as e:
            logger.error(f"Failed to parse webhook payload: {e}")
            return None


class CommentProcessor:
    """Processes comment events and sends DMs based on active automations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def process(self, payload: dict[str, Any]) -> bool:
        """Process a comment webhook event.

        Returns True if processed successfully, False otherwise.
        """
        # Parse the event
        event = CommentEvent.from_webhook_payload(payload)
        if not event:
            logger.warning("Failed to parse comment event")
            return True  # Ack message - malformed payload won't improve on retry

        logger.info(
            f"Processing comment: {event.comment_id} on post {event.media_id} "
            f"from @{event.commenter_username}"
        )

        # Find active automations for this post (with account loaded)
        automations = await self._get_active_automations(event.media_id)
        if not automations:
            logger.debug(f"No active automations for post: {event.media_id}")
            return True  # Not an error, just no automation configured

        # Process each automation using its linked account
        for automation in automations:
            account = automation.instagram_account
            if not account:
                logger.warning(f"Automation {automation.id} has no linked Instagram account")
                continue
            await self._process_automation(event, automation, account)

        return True

    async def _get_active_automations(self, post_id: str) -> list[Automation]:
        """Fetch all active automations for a given post ID with instagram_account loaded."""
        result = await self.db.execute(
            select(Automation)
            .options(joinedload(Automation.instagram_account))
            .where(
                Automation.post_id == post_id,
                Automation.is_active == True,  # noqa: E712
            )
        )
        return list(result.scalars().unique().all())

    async def _process_automation(
        self,
        event: CommentEvent,
        automation: Automation,
        account: InstagramAccount,
    ) -> None:
        """Process a single automation for a comment event."""
        logger.info(f"Checking automation: {automation.name} (ID: {automation.id})")

        # Check if we should trigger based on type
        if not self._should_trigger(event, automation):
            logger.debug(
                f"Automation {automation.id} trigger condition not met for comment"
            )
            return

        # Check for deduplication
        if await self._already_sent(automation.id, event.media_id, event.commenter_id):
            logger.info(
                f"DM already sent to {event.commenter_username} for this automation"
            )
            return

        # Send the DM
        success = await self._send_dm(event, automation, account)

        # Log the result
        await self._log_dm_sent(
            automation_id=automation.id,
            post_id=event.media_id,
            commenter_user_id=event.commenter_id,
            comment_id=event.comment_id,
            status="sent" if success else "failed",
        )

    def _should_trigger(self, event: CommentEvent, automation: Automation) -> bool:
        """Check if the automation should trigger for this comment."""
        if automation.trigger_type == TriggerType.ALL_COMMENTS:
            return True

        if automation.trigger_type == TriggerType.KEYWORD:
            if not automation.keywords:
                return False

            comment_lower = event.comment_text.lower()
            return any(keyword.lower() in comment_lower for keyword in automation.keywords)

        return False

    async def _already_sent(
        self, automation_id: UUID, post_id: str, commenter_user_id: str
    ) -> bool:
        """Check if we've already sent a DM for this automation + post + user combo."""
        result = await self.db.execute(
            select(DMSentLog).where(
                DMSentLog.automation_id == automation_id,
                DMSentLog.post_id == post_id,
                DMSentLog.commenter_user_id == commenter_user_id,
                DMSentLog.status == "sent",
            )
        )
        return result.scalar_one_or_none() is not None

    async def _send_dm(
        self,
        event: CommentEvent,
        automation: Automation,
        account: InstagramAccount,
    ) -> bool:
        """Send a DM to the commenter."""
        try:
            # Decrypt the access token
            access_token = instagram_client.decrypt_token(account.access_token)

            # Send the message
            response = await instagram_client.send_message(
                access_token=access_token,
                sender_id=account.instagram_user_id,
                recipient_id=event.comment_id,
                text=automation.dm_message_template,
                reply_to="COMMENT"
            )

            logger.info(
                f"DM sent successfully to @{event.commenter_username}: {response}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to send DM to @{event.commenter_username}: {e}"
            )
            return False

    async def _log_dm_sent(
        self,
        automation_id: UUID,
        post_id: str,
        commenter_user_id: str,
        comment_id: str,
        status: str,
    ) -> None:
        """Log a DM send attempt for deduplication and analytics."""
        log_entry = DMSentLog(
            automation_id=automation_id,
            post_id=post_id,
            commenter_user_id=commenter_user_id,
            comment_id=comment_id,
            status=status,
        )
        self.db.add(log_entry)
        await self.db.flush()

        logger.info(
            f"Logged DM send: automation={automation_id}, "
            f"commenter={commenter_user_id}, status={status}"
        )
