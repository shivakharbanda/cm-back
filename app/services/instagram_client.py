"""Instagram OAuth and Graph API client."""

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet

from app.config import settings

MEDIA_FIELDS = "id,caption,media_type,media_url,permalink,thumbnail_url,timestamp,username"


class GraphAPIError(Exception):
    """Base class for classified Graph API errors.

    Carries the HTTP status code and Meta's error envelope so callers can
    decide whether to retry, mark permanent, or surface to the user.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        meta_code: int | None = None,
        meta_subcode: int | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.meta_code = meta_code
        self.meta_subcode = meta_subcode


class RetryableGraphAPIError(GraphAPIError):
    """Transient — worker should nack+requeue (up to the delivery cap)."""


class PermanentGraphAPIError(GraphAPIError):
    """Won't succeed on retry — worker should log and ack.

    Examples: expired/invalid token (190), bad recipient (400 with certain
    subcodes), post deleted, user blocked the business (403).
    """


def _classify_http_error(err: httpx.HTTPStatusError) -> GraphAPIError:
    """Map an httpx error into a retryable or permanent GraphAPIError.

    Meta's error envelope looks like:
      {"error": {"message": "...", "code": 190, "error_subcode": 460, ...}}
    """
    status = err.response.status_code
    meta_code: int | None = None
    meta_subcode: int | None = None
    message = f"HTTP {status}"
    try:
        body = err.response.json()
        error_obj = body.get("error") if isinstance(body, dict) else None
        if isinstance(error_obj, dict):
            meta_code = error_obj.get("code")
            meta_subcode = error_obj.get("error_subcode")
            message = error_obj.get("message") or message
    except Exception:
        pass

    if status == 429 or 500 <= status < 600:
        return RetryableGraphAPIError(
            message,
            status_code=status,
            meta_code=meta_code,
            meta_subcode=meta_subcode,
        )

    # 4xx other than 429: auth/bad-request/forbidden/not-found → permanent.
    if 400 <= status < 500:
        return PermanentGraphAPIError(
            message,
            status_code=status,
            meta_code=meta_code,
            meta_subcode=meta_subcode,
        )

    # 3xx/1xx and anything unexpected: be conservative, treat as retryable.
    return RetryableGraphAPIError(
        message,
        status_code=status,
        meta_code=meta_code,
        meta_subcode=meta_subcode,
    )


class InstagramClient:
    """Client for Instagram OAuth and Graph API."""

    def __init__(self):
        self.base_url = settings.instagram_graph_api_url
        self.client_id = settings.instagram_client_id
        self.client_secret = settings.instagram_client_secret
        self.redirect_uri = settings.instagram_redirect_uri
        self._cipher = None

    @property
    def cipher(self) -> Fernet:
        """Lazy-load the Fernet cipher for token encryption."""
        if self._cipher is None:
            if not settings.encryption_key:
                raise ValueError("ENCRYPTION_KEY environment variable is required")
            self._cipher = Fernet(settings.encryption_key.encode())
        return self._cipher

    def encrypt_token(self, token: str) -> str:
        """Encrypt an access token for storage."""
        return self.cipher.encrypt(token.encode()).decode()

    def decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt a stored access token."""
        return self.cipher.decrypt(encrypted_token.encode()).decode()

    def get_authorization_url(self, state: str | None = None) -> str:
        """Generate Instagram OAuth authorization URL."""
        params = [
            ("force_reauth", "true"),
            ("client_id", self.client_id),
            ("redirect_uri", self.redirect_uri),
            ("response_type", "code"),
            ("scope", "instagram_business_basic,instagram_business_manage_messages,instagram_business_manage_comments,instagram_business_content_publish,instagram_business_manage_insights"),
        ]
        if state:
            params.append(("state", state))

        return f"https://www.instagram.com/oauth/authorize?{urlencode(params)}"

    async def exchange_code_for_token(self, code: str) -> dict[str, Any]:
        """Exchange authorization code for access token.

        Raises:
            ValueError: With sanitized error message (safe to expose to users)
        """
        async with httpx.AsyncClient() as client:
            # Exchange code for short-lived token
            try:
                response = await client.post(
                    "https://api.instagram.com/oauth/access_token",
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "grant_type": "authorization_code",
                        "redirect_uri": self.redirect_uri,
                        "code": code,
                    },
                )
                response.raise_for_status()
                short_lived_data = response.json()
            except httpx.HTTPStatusError as e:
                # Extract Instagram's error message without exposing request details
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error_message", "Token exchange failed")
                except Exception:
                    error_msg = "Token exchange failed"
                raise ValueError(error_msg) from None

            # Exchange for long-lived token
            try:
                long_lived_response = await client.get(
                    f"{self.base_url}/access_token",
                    params={
                        "grant_type": "ig_exchange_token",
                        "client_secret": self.client_secret,
                        "access_token": short_lived_data["access_token"],
                    },
                )
                long_lived_response.raise_for_status()
                long_lived_data = long_lived_response.json()
            except httpx.HTTPStatusError as e:
                # Extract Instagram's error message without exposing request details
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error_message", "Long-lived token exchange failed")
                except Exception:
                    error_msg = "Long-lived token exchange failed"
                raise ValueError(error_msg) from None

            # Calculate expiry
            expires_in = long_lived_data.get("expires_in", 5184000)  # Default 60 days
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            # Fetch the professional account ID (IG_ID) + username via /me.
            # /oauth/access_token returns only the app-scoped id; Meta's
            # webhook payloads use the IG_ID, so we need both.
            long_lived_token = long_lived_data["access_token"]
            try:
                me_response = await client.get(
                    f"{self.base_url}/me",
                    params={
                        "fields": "user_id,username",
                        "access_token": long_lived_token,
                    },
                )
                me_response.raise_for_status()
                me_data = me_response.json()
            except httpx.HTTPStatusError:
                raise ValueError("Failed to fetch Instagram account profile") from None

            return {
                "access_token": long_lived_token,
                "ig_id": str(me_data["user_id"]),
                "app_scoped_id": str(short_lived_data["user_id"]),
                "username": me_data.get("username", ""),
                "expires_at": expires_at,
            }

    async def get_commenter_profile(self, access_token: str, user_id: str) -> dict[str, Any]:
        """Fetch full profile details for a commenter.

        Returns dict with: id, username, name, biography, followers_count, media_count, profile_picture_url
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/{user_id}",
                params={
                    "fields": "id,username,name,biography,followers_count,media_count,profile_picture_url",
                    "access_token": access_token,
                },
            )
            response.raise_for_status()
            return response.json()

    async def get_user_media(
        self, access_token: str, after_cursor: str | None = None
    ) -> dict[str, Any]:
        """Fetch authenticated account's media posts via the /me shortcut."""
        params: dict[str, str] = {
            "fields": MEDIA_FIELDS,
            "access_token": access_token,
        }
        if after_cursor:
            params["after"] = after_cursor

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/me/media",
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def refresh_long_lived_token(self, access_token: str) -> dict[str, Any]:
        """Refresh a long-lived access token."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/refresh_access_token",
                params={
                    "grant_type": "ig_refresh_token",
                    "access_token": access_token,
                },
            )
            response.raise_for_status()
            data = response.json()

            expires_in = data.get("expires_in", 5184000)
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            return {
                "access_token": data["access_token"],
                "expires_at": expires_at,
            }

    async def send_message(
        self, access_token: str, recipient_id: str, text: str, reply_to: str
    ) -> dict[str, Any]:
        """Send a DM to a user via the /me/messages shortcut."""

        if reply_to.lower() == "comment":
            recipient_id_name = "comment_id"
        else:
            recipient_id_name = "id"
        payload = {
            "recipient": {recipient_id_name: recipient_id},
            "message": {"text": text},
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/me/messages",
                    headers={"Authorization": f"Bearer {access_token}"},
                    json=payload,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                raise _classify_http_error(e) from e

    async def subscribe_app(
        self,
        instagram_user_id: str,
        access_token: str,
        subscribed_fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Enable webhook delivery for an IG pro account.

        Without this call, Meta delivers no webhooks for the account even
        after app-level URL verification. Idempotent — safe to re-invoke.
        """
        fields = subscribed_fields or ["comments"]
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/{instagram_user_id}/subscribed_apps",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params={"subscribed_fields": ",".join(fields)},
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                raise _classify_http_error(e) from e

    async def send_carousel(
        self,
        access_token: str,
        recipient_id: str,
        elements: list[dict[str, Any]],
        reply_to: str,
    ) -> dict[str, Any]:
        """Send a carousel (generic template) DM via the /me/messages shortcut."""
        if reply_to.lower() == "comment":
            recipient_key = "comment_id"
        else:
            recipient_key = "id"

        payload = {
            "recipient": {recipient_key: recipient_id},
            "message": {
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "generic",
                        "elements": elements,
                    },
                }
            },
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/me/messages",
                    headers={"Authorization": f"Bearer {access_token}"},
                    json=payload,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                raise _classify_http_error(e) from e

    async def send_button_template(
        self,
        access_token: str,
        recipient_id: str,
        text: str,
        buttons: list[dict[str, Any]],
        reply_to: str,
    ) -> dict[str, Any]:
        """Send a button-template DM via /me/messages."""
        recipient_key = "comment_id" if reply_to.lower() == "comment" else "id"
        payload = {
            "recipient": {recipient_key: recipient_id},
            "message": {
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "button",
                        "text": text,
                        "buttons": buttons,
                    },
                }
            },
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/me/messages",
                    headers={"Authorization": f"Bearer {access_token}"},
                    json=payload,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                raise _classify_http_error(e) from e

    async def reply_to_comment(
        self, access_token: str, comment_id: str, message: str
    ) -> dict:
        """
        Reply to an Instagram comment.

        POST /{ig-comment-id}/replies?message={message}

        Limitations:
        - Can only reply to top-level comments
        - Cannot reply to hidden comments
        - Cannot reply to comments on live videos
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/{comment_id}/replies",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params={"message": message},
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                raise _classify_http_error(e) from e

    async def get_comment_replies(
        self, access_token: str, comment_id: str
    ) -> dict:
        """
        Get all replies on an Instagram comment.

        GET /{ig-comment-id}/replies

        Returns list of comments with timestamp, text, and id.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/{comment_id}/replies",
                    params={"access_token": access_token},
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            try:
                error_data = e.response.json()
                error_msg = error_data.get("error", {}).get(
                    "message", "Failed to get comment replies"
                )
            except Exception:
                error_msg = "Failed to get comment replies"
            raise ValueError(error_msg)


instagram_client = InstagramClient()
