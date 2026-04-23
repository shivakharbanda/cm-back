"""Comment processor service for handling Instagram comment webhooks."""

import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload


# Refresh a long-lived Instagram token if it expires within this window.
# IG long-lived tokens last ~60 days; refreshing at T-7d is a generous buffer.
TOKEN_REFRESH_THRESHOLD = timedelta(days=7)

from app.models import Automation, CommentReplyLog, DMSentLog, InstagramAccount
from app.models.automation import (
    DM_STATUS_FAILED,
    DM_STATUS_PENDING,
    DM_STATUS_PERMANENT_FAILURE,
    DM_STATUS_SENT,
    MessageType,
    TriggerType,
)
from app.services.instagram_client import (
    PermanentGraphAPIError,
    RetryableGraphAPIError,
    instagram_client,
)

logger = logging.getLogger(__name__)


@dataclass
class DMSendResult:
    """Outcome of a single Graph-API DM attempt.

    `retryable=True` means the worker should nack+requeue after the status
    row has been finalized to 'failed' (so the next delivery's dedup claim
    can re-acquire this slot).
    """

    status: str
    error_message: str | None = None
    error_code: int | None = None
    error_subcode: int | None = None
    retryable: bool = False


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
        envelope_id = payload.get("id")
        account_id = payload.get("account_id")
        try:
            raw = payload.get("raw_payload", {})
            changes = raw.get("changes", [])

            if not changes:
                logger.warning(
                    "webhook payload has no changes "
                    f"envelope_id={envelope_id} account_id={account_id}"
                )
                return None

            change = changes[0]
            if change.get("field") != "comments":
                logger.warning(
                    f"unexpected field type: {change.get('field')} "
                    f"envelope_id={envelope_id} account_id={account_id}"
                )
                return None

            value = change.get("value", {})
            from_data = value.get("from", {})
            media_data = value.get("media", {})

            return cls(
                message_id=envelope_id or "",
                account_id=account_id or "",
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
        except (KeyError, ValueError, TypeError, AttributeError):
            logger.exception(
                f"failed to parse webhook payload "
                f"envelope_id={envelope_id} account_id={account_id}"
            )
            return None


class CommentProcessor:
    """Processes comment events and sends DMs based on active automations.

    Owns commit/rollback for the session passed in. The worker MUST NOT commit
    after process() returns — mid-flow commits here are what make dedup work.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def process(self, payload: dict[str, Any]) -> bool:
        """Process a comment webhook event.

        Returns True if processed successfully, False otherwise.
        """
        event = CommentEvent.from_webhook_payload(payload)
        if not event:
            return True  # Ack — malformed payload won't improve on retry.

        if not event.commenter_id or not event.comment_id:
            logger.warning(
                f"dropping comment with missing id fields "
                f"envelope_id={event.message_id} commenter_id={event.commenter_id!r} "
                f"comment_id={event.comment_id!r}"
            )
            return True

        logger.info(
            f"Processing comment: {event.comment_id} on post {event.media_id} "
            f"from @{event.commenter_username}"
        )

        automations = await self._get_active_automations(event.media_id, event.account_id)
        if not automations:
            logger.debug(
                f"No active automations for post {event.media_id} "
                f"under account {event.account_id}"
            )
            return True

        for automation in automations:
            account = automation.instagram_account
            if not account:
                logger.warning(
                    f"Automation {automation.id} has no linked Instagram account"
                )
                continue
            await self._process_automation(event, automation, account)

        return True

    async def _get_active_automations(
        self, post_id: str, account_id: str
    ) -> list[Automation]:
        """Fetch active automations for this post owned by the account.

        Scopes by account so that stale automations on a post that was reconnected
        under a different IG account, or collab posts, don't fire the wrong
        business's automation.
        """
        result = await self.db.execute(
            select(Automation)
            .join(InstagramAccount, Automation.instagram_account_id == InstagramAccount.id)
            .options(joinedload(Automation.instagram_account))
            .where(
                Automation.post_id == post_id,
                Automation.is_active == True,  # noqa: E712
                InstagramAccount.instagram_user_id == account_id,
            )
        )
        return list(result.scalars().unique().all())

    async def _process_automation(
        self,
        event: CommentEvent,
        automation: Automation,
        account: InstagramAccount,
    ) -> None:
        """Process a single automation for a comment event.

        Commits mid-flow — the 'pending' row MUST land before the Graph API call.
        """
        logger.info(f"Checking automation: {automation.name} (ID: {automation.id})")

        if not self._should_trigger(event, automation):
            logger.debug(
                f"Automation {automation.id} trigger condition not met for comment"
            )
            return

        # Self-comment guard — don't DM yourself.
        if event.commenter_id == account.instagram_user_id:
            logger.info(
                f"Skipping self-comment by business account "
                f"{account.instagram_user_id} on automation {automation.id}"
            )
            return

        # Validate content.
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
        if (
            automation.message_type == MessageType.BUTTON
            and not automation.button_template
        ):
            logger.warning(
                f"Automation {automation.id} is button-based but has no template."
            )
            return

        # Refresh token if it's near expiry. A single refresh per automation is
        # fine: this hot path is already rate-limited by IG webhook volume.
        await self._ensure_fresh_token(account)

        commenter_profile = await self._fetch_commenter_profile(event, account)

        # Claim the dedup slot. On conflict, DB tells us whether to proceed or skip.
        log_id = await self._claim_dm_slot(
            automation_id=automation.id,
            event=event,
            commenter_profile=commenter_profile,
        )
        if log_id is None:
            logger.info(
                f"DM already attempted for @{event.commenter_username} "
                f"on automation {automation.id} — skipping"
            )
            return

        # Row is committed as 'pending'. The Graph API call is now the only
        # side effect that can still fail, and we've guaranteed at-most-once
        # against concurrent workers.
        result = await self._send_dm(event, automation, account)
        await self._finalize_dm_status(
            log_id,
            result.status,
            error_message=result.error_message,
            error_code=result.error_code,
            error_subcode=result.error_subcode,
        )
        if result.retryable:
            # The row is now 'failed', so the next delivery's ON CONFLICT can
            # re-claim this slot (the claim WHERE filters on status='failed').
            # Raise so the worker nacks the message for retry.
            raise RetryableGraphAPIError(result.error_message or "retry")

        # Comment-reply is independent of DM success. A commenter may have
        # restricted DMs from businesses (very common), but the public reply
        # has no such restriction — so we should still post it if configured.
        if (
            automation.comment_reply_enabled
            and automation.comment_reply_template
        ):
            reply_success = await self._reply_to_comment(event, automation, account)
            await self._log_comment_reply(
                automation_id=automation.id,
                post_id=event.media_id,
                comment_id=event.comment_id,
                commenter_user_id=event.commenter_id,
                commenter_profile=commenter_profile,
                status="sent" if reply_success else "failed",
            )

    def _should_trigger(self, event: CommentEvent, automation: Automation) -> bool:
        """Check if the automation should trigger for this comment."""
        if automation.trigger_type == TriggerType.ALL_COMMENTS:
            return True

        if automation.trigger_type == TriggerType.KEYWORD:
            if not automation.keywords:
                logger.warning(
                    f"Automation {automation.id} is keyword-triggered but has no keywords"
                )
                return False

            # NFC-normalize both sides so composed vs decomposed unicode matches.
            # Word boundaries prevent "price" from matching "priceless".
            text = unicodedata.normalize("NFC", event.comment_text)
            for raw_kw in automation.keywords:
                if not raw_kw:
                    continue
                kw = unicodedata.normalize("NFC", raw_kw)
                pattern = rf"\b{re.escape(kw)}\b"
                if re.search(pattern, text, flags=re.IGNORECASE):
                    return True
            return False

        return False

    async def _claim_dm_slot(
        self,
        automation_id: UUID,
        event: CommentEvent,
        commenter_profile: CommenterProfile,
    ) -> UUID | None:
        """Atomically reserve a dedup slot for this (automation, commenter, post).

        Uses INSERT ... ON CONFLICT. If no prior row exists, inserts a 'pending'
        row. If a prior row exists with status='failed', upgrades it back to
        'pending' (retryable). If the prior row is 'sent', 'pending', or
        'permanent_failure', returns None — caller must skip.

        Returns the DMSentLog id on success (caller must update status later),
        or None if dedup fired.
        """
        stmt = (
            pg_insert(DMSentLog)
            .values(
                automation_id=automation_id,
                post_id=event.media_id,
                commenter_user_id=event.commenter_id,
                comment_id=event.comment_id,
                status=DM_STATUS_PENDING,
                commenter_username=commenter_profile.username,
                commenter_name=commenter_profile.name,
                commenter_biography=commenter_profile.biography,
                commenter_followers_count=commenter_profile.followers_count,
                commenter_media_count=commenter_profile.media_count,
                commenter_profile_picture_url=commenter_profile.profile_picture_url,
            )
        )
        # Re-claim rows that previously failed transiently. Anything else stays
        # locked (the WHERE filters the update out, so no row is returned).
        stmt = stmt.on_conflict_do_update(
            constraint="uq_dm_sent_log_dedup",
            set_={
                "status": DM_STATUS_PENDING,
                "comment_id": stmt.excluded.comment_id,
                "commenter_username": stmt.excluded.commenter_username,
                "commenter_name": stmt.excluded.commenter_name,
                "commenter_biography": stmt.excluded.commenter_biography,
                "commenter_followers_count": stmt.excluded.commenter_followers_count,
                "commenter_media_count": stmt.excluded.commenter_media_count,
                "commenter_profile_picture_url": (
                    stmt.excluded.commenter_profile_picture_url
                ),
            },
            where=(DMSentLog.status == DM_STATUS_FAILED),
        ).returning(DMSentLog.id)

        result = await self.db.execute(stmt)
        log_id = result.scalar_one_or_none()
        await self.db.commit()
        return log_id

    async def _finalize_dm_status(
        self,
        log_id: UUID,
        status: str,
        error_message: str | None = None,
        error_code: int | None = None,
        error_subcode: int | None = None,
    ) -> None:
        """Update the DMSentLog row to its terminal status + error context.

        Always writes all four fields. On 'sent' the three error columns
        clear back to NULL, wiping any stale retry error from an earlier
        attempt on the same row.
        """
        await self.db.execute(
            update(DMSentLog).where(DMSentLog.id == log_id).values(
                status=status,
                error_message=error_message,
                error_code=error_code,
                error_subcode=error_subcode,
            )
        )
        await self.db.commit()

    async def _ensure_fresh_token(self, account: InstagramAccount) -> None:
        """Refresh the account's long-lived token if it's near expiry.

        No-ops if token_expires_at is NULL (legacy rows) or not within the
        refresh threshold. Any failure is logged and swallowed — the DM
        attempt that follows will surface the real error classification.
        """
        if account.token_expires_at is None:
            return
        now = datetime.now(timezone.utc)
        if account.token_expires_at - now > TOKEN_REFRESH_THRESHOLD:
            return

        try:
            current_plaintext = instagram_client.decrypt_token(account.access_token)
            refreshed = await instagram_client.refresh_long_lived_token(
                current_plaintext
            )
            account.access_token = instagram_client.encrypt_token(
                refreshed["access_token"]
            )
            account.token_expires_at = refreshed["expires_at"]
            self.db.add(account)
            await self.db.commit()
            logger.info(
                f"Refreshed Instagram access token for account "
                f"{account.instagram_user_id}; new expiry={account.token_expires_at}"
            )
        except Exception as e:
            logger.warning(
                f"Failed to refresh token for account "
                f"{account.instagram_user_id}: {e}"
            )
            # Roll back any partial session state before the send attempts DB work.
            await self.db.rollback()

    async def _send_dm(
        self,
        event: CommentEvent,
        automation: Automation,
        account: InstagramAccount,
    ) -> DMSendResult:
        """Attempt to send a DM and return the classified outcome.

        Never raises — the Meta error detail is packaged into DMSendResult
        so the caller can persist it to dm_sent_log before deciding whether
        to nack the message (retryable=True) or ack it.
        """
        try:
            access_token = instagram_client.decrypt_token(account.access_token)

            if (
                automation.message_type == MessageType.CAROUSEL
                and automation.carousel_elements
            ):
                response = await instagram_client.send_carousel(
                    access_token=access_token,
                    recipient_id=event.comment_id,
                    elements=automation.carousel_elements,
                    reply_to="COMMENT",
                )
            elif (
                automation.message_type == MessageType.BUTTON
                and automation.button_template
            ):
                response = await instagram_client.send_button_template(
                    access_token=access_token,
                    recipient_id=event.comment_id,
                    text=automation.button_template["text"],
                    buttons=automation.button_template["buttons"],
                    reply_to="COMMENT",
                )
            else:
                response = await instagram_client.send_message(
                    access_token=access_token,
                    recipient_id=event.comment_id,
                    text=automation.dm_message_template,
                    reply_to="COMMENT",
                )

            message_id = response.get("message_id") if isinstance(response, dict) else None
            logger.info(
                f"DM sent to @{event.commenter_username} message_id={message_id}"
            )
            return DMSendResult(status=DM_STATUS_SENT)

        except PermanentGraphAPIError as e:
            logger.warning(
                f"Permanent DM failure for @{event.commenter_username}: "
                f"status={e.status_code} meta_code={e.meta_code} "
                f"meta_subcode={e.meta_subcode} msg={e}"
            )
            return DMSendResult(
                status=DM_STATUS_PERMANENT_FAILURE,
                error_message=str(e),
                error_code=e.meta_code,
                error_subcode=e.meta_subcode,
            )

        except RetryableGraphAPIError as e:
            logger.warning(
                f"Retryable DM failure for @{event.commenter_username}: "
                f"status={e.status_code} meta_code={e.meta_code} "
                f"meta_subcode={e.meta_subcode} msg={e}"
            )
            return DMSendResult(
                status=DM_STATUS_FAILED,
                error_message=str(e),
                error_code=e.meta_code,
                error_subcode=e.meta_subcode,
                retryable=True,
            )

        except Exception as e:
            logger.error(
                f"Unclassified DM failure for @{event.commenter_username}: {e}",
                exc_info=True,
            )
            return DMSendResult(status=DM_STATUS_FAILED, error_message=str(e))

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
            if not profile.username:
                profile.username = data.get("username", "")
        except Exception as e:
            logger.warning(
                f"Failed to fetch profile for {event.commenter_username}: {e}"
            )

        return profile

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
        await self.db.commit()

        logger.info(
            f"Logged comment reply: automation={automation_id}, "
            f"comment={comment_id}, status={status}"
        )
