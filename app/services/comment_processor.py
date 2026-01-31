"""Comment processor service for handling Instagram comment webhooks."""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import Automation, DMSentLog, InstagramAccount, CommentReplyLog
from app.models.automation import MessageType, TriggerType
from app.services.instagram_client import instagram_client

logger = logging.getLogger(__name__)


@dataclass
class CommenterProfile:
    """Profile data fetched from Instagram API."""

    username: str
    name: str | None = None
    biography: str | None = None
    followers_count: int | None = None
    media_count: int | None = None
    profile_picture_url: str | None = None


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

        # Validate that we have content to send
        if (
            automation.message_type == MessageType.TEXT
            and not automation.dm_message_template
        ):
            logger.warning(
                f"Automation {automation.id} is text-based but has no message template."
            )
            return
        if (
            automation.message_type == MessageType.CAROUSEL
            and not automation.carousel_elements
        ):
            logger.warning(
                f"Automation {automation.id} is carousel-based but has no elements."
            )
            return

        # Fetch commenter profile from Instagram API
        commenter_profile = await self._fetch_commenter_profile(event, account)

        # Send the DM
        dm_success = await self._send_dm(event, automation, account)

        # Reply to comment if enabled and DM succeeded
        if dm_success and automation.comment_reply_enabled and automation.comment_reply_template:
            reply_success = await self._reply_to_comment(event, automation, account)
            # Log the comment reply
            await self._log_comment_reply(
                automation_id=automation.id,
                post_id=event.media_id,
                comment_id=event.comment_id,
                commenter_user_id=event.commenter_id,
                commenter_profile=commenter_profile,
                status="sent" if reply_success else "failed",
            )

        # Log the result
        await self._log_dm_sent(
            automation_id=automation.id,
            post_id=event.media_id,
            commenter_user_id=event.commenter_id,
            commenter_profile=commenter_profile,
            comment_id=event.comment_id,
            status="sent" if dm_success else "failed",
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
        """Send a DM to the commenter (text or carousel based on message_type)."""
        try:
            access_token = instagram_client.decrypt_token(account.access_token)

            if automation.message_type == MessageType.CAROUSEL and automation.carousel_elements:
                response = await instagram_client.send_carousel(
                    access_token=access_token,
                    sender_id=account.instagram_user_id,
                    recipient_id=event.comment_id,
                    elements=automation.carousel_elements,
                    reply_to="COMMENT",
                )
            else:
                response = await instagram_client.send_message(
                    access_token=access_token,
                    sender_id=account.instagram_user_id,
                    recipient_id=event.comment_id,
                    text=automation.dm_message_template,
                    reply_to="COMMENT",
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

    async def _reply_to_comment(
        self,
        event: CommentEvent,
        automation: Automation,
        account: InstagramAccount,
    ) -> bool:
        """Reply to the comment publicly."""
        try:
            access_token = instagram_client.decrypt_token(account.access_token)

            response = await instagram_client.reply_to_comment(
                access_token=access_token,
                comment_id=event.comment_id,
                message=automation.comment_reply_template,
            )

            logger.info(
                f"Comment reply sent to @{event.commenter_username}: {response}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to reply to comment from @{event.commenter_username}: {e}"
            )
            return False

    async def _fetch_commenter_profile(
        self, event: CommentEvent, account: InstagramAccount
    ) -> CommenterProfile:
        """Fetch commenter's profile data from Instagram API."""
        # Start with username from webhook
        profile = CommenterProfile(username=event.commenter_username)

        try:
            access_token = instagram_client.decrypt_token(account.access_token)
            data = await instagram_client.get_commenter_profile(
                access_token, event.commenter_id
            )
            profile.name = data.get("name")
            profile.biography = data.get("biography")
            profile.followers_count = data.get("followers_count")
            profile.media_count = data.get("media_count")
            profile.profile_picture_url = data.get("profile_picture_url")
        except Exception as e:
            logger.warning(f"Failed to fetch profile for {event.commenter_username}: {e}")

        return profile

    async def _log_dm_sent(
        self,
        automation_id: UUID,
        post_id: str,
        commenter_user_id: str,
        commenter_profile: CommenterProfile,
        comment_id: str,
        status: str,
    ) -> None:
        """Log a DM send attempt for deduplication and analytics."""
        log_entry = DMSentLog(
            automation_id=automation_id,
            post_id=post_id,
            commenter_user_id=commenter_user_id,
            commenter_username=commenter_profile.username,
            commenter_name=commenter_profile.name,
            commenter_biography=commenter_profile.biography,
            commenter_followers_count=commenter_profile.followers_count,
            commenter_media_count=commenter_profile.media_count,
            commenter_profile_picture_url=commenter_profile.profile_picture_url,
            comment_id=comment_id,
            status=status,
        )
        self.db.add(log_entry)
        await self.db.flush()

        logger.info(
            f"Logged DM send: automation={automation_id}, "
            f"commenter={commenter_user_id}, status={status}"
        )

    async def _log_comment_reply(
        self,
        automation_id: UUID,
        post_id: str,
        comment_id: str,
        commenter_user_id: str,
        commenter_profile: CommenterProfile,
        status: str,
    ) -> None:
        """Log a comment reply attempt for analytics."""
        log_entry = CommentReplyLog(
            automation_id=automation_id,
            post_id=post_id,
            comment_id=comment_id,
            commenter_user_id=commenter_user_id,
            commenter_username=commenter_profile.username,
            commenter_name=commenter_profile.name,
            commenter_biography=commenter_profile.biography,
            commenter_followers_count=commenter_profile.followers_count,
            commenter_media_count=commenter_profile.media_count,
            commenter_profile_picture_url=commenter_profile.profile_picture_url,
            status=status,
        )
        self.db.add(log_entry)
        await self.db.flush()

        logger.info(
            f"Logged comment reply: automation={automation_id}, "
            f"comment={comment_id}, status={status}"
        )
