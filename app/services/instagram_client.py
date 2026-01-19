"""Instagram OAuth and Graph API client."""

import base64
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet

from app.config import settings

MEDIA_FIELDS = "id,caption,media_type,media_url,permalink,thumbnail_url,timestamp,username"


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
                key = Fernet.generate_key()
            else:
                key = settings.encryption_key.encode()
                if len(base64.urlsafe_b64decode(key)) != 32:
                    key = Fernet.generate_key()
            self._cipher = Fernet(key)
        return self._cipher

    def encrypt_token(self, token: str) -> str:
        """Encrypt an access token for storage."""
        return self.cipher.encrypt(token.encode()).decode()

    def decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt a stored access token."""
        return self.cipher.decrypt(encrypted_token.encode()).decode()

    def get_authorization_url(self, state: str | None = None) -> str:
        """Generate Instagram OAuth authorization URL."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "instagram_business_basic,instagram_business_manage_messages,instagram_business_manage_comments,instagram_business_content_publish,instagram_business_manage_insights",
            "response_type": "code",
            "force_reauth": "true",
        }
        if state:
            params["state"] = state

        return f"https://www.instagram.com/oauth/authorize?{urlencode(params)}"

    async def exchange_code_for_token(self, code: str) -> dict[str, Any]:
        """Exchange authorization code for access token."""
        async with httpx.AsyncClient() as client:
            # Exchange code for short-lived token
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

            # Exchange for long-lived token
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

            # Calculate expiry
            expires_in = long_lived_data.get("expires_in", 5184000)  # Default 60 days
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            return {
                "access_token": long_lived_data["access_token"],
                "user_id": str(short_lived_data["user_id"]),
                "expires_at": expires_at,
            }

    async def get_user_profile(self, access_token: str, user_id: str) -> dict[str, Any]:
        """Get Instagram user profile."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/{user_id}",
                params={
                    "fields": "id,username",
                    "access_token": access_token,
                },
            )
            response.raise_for_status()
            return response.json()

    async def get_user_media(
        self, access_token: str, user_id: str, after_cursor: str | None = None
    ) -> dict[str, Any]:
        """Fetch user's media posts."""
        params: dict[str, str] = {
            "fields": MEDIA_FIELDS,
            "access_token": access_token,
        }
        if after_cursor:
            params["after"] = after_cursor

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/{user_id}/media",
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
        self, access_token: str, sender_id: str, recipient_id: str, text: str, reply_to:str
    ) -> dict[str, Any]:
        """Send a DM to a user.

        Args:
            access_token: The Instagram account's access token
            sender_id: The Instagram account ID sending the message
            recipient_id: The recipient's Instagram-scoped user ID
            text: The message text to send

        Returns:
            API response with message_id on success
        """

        if reply_to.lower()=="COMMENT".lower():
            recipient_id_name = "comment_id"
        else:
            recipient_id_name = "id"
        payload = {
            "recipient": {recipient_id_name: recipient_id},
            "message": {"text": text},
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/{sender_id}/messages",
                headers={"Authorization": f"Bearer {access_token}"},
                json=payload,
            )
            response.raise_for_status()
            return response.json()


instagram_client = InstagramClient()
