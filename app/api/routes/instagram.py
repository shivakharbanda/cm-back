"""Instagram account management routes (single account per user)."""

import logging

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession
from app.models import InstagramAccount
from app.schemas.instagram import (
    InstagramAccountResponse,
    InstagramAuthURL,
    InstagramCallbackRequest,
    InstagramPostResponse,
    InstagramPostsListResponse,
)
from app.services.instagram_client import GraphAPIError, instagram_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/instagram", tags=["instagram"])


async def get_user_instagram_account(
    current_user: CurrentUser, db: DBSession
) -> InstagramAccount:
    """Get the user's linked Instagram account or raise 404."""
    result = await db.execute(
        select(InstagramAccount).where(InstagramAccount.user_id == current_user.id)
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Instagram account linked",
        )
    return account


@router.get("/auth-url", response_model=InstagramAuthURL)
async def get_auth_url(current_user: CurrentUser) -> InstagramAuthURL:
    """Get Instagram OAuth authorization URL."""
    auth_url = instagram_client.get_authorization_url(state=str(current_user.id))
    return InstagramAuthURL(auth_url=auth_url)


@router.post("/callback", response_model=InstagramAccountResponse)
async def oauth_callback(
    request: InstagramCallbackRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> InstagramAccount:
    """Handle Instagram OAuth callback and store tokens."""
    try:
        # Exchange code for token. Returns both the IG professional account ID
        # (used for webhook matching) and the app-scoped ID, plus username.
        token_data = await instagram_client.exchange_code_for_token(request.code)

        # Check if user already has an account linked
        result = await db.execute(
            select(InstagramAccount).where(InstagramAccount.user_id == current_user.id)
        )
        existing_account = result.scalar_one_or_none()

        if existing_account:
            # Update existing account (replace with new one)
            existing_account.instagram_user_id = token_data["ig_id"]
            existing_account.instagram_app_scoped_id = token_data["app_scoped_id"]
            existing_account.access_token = instagram_client.encrypt_token(
                token_data["access_token"]
            )
            existing_account.token_expires_at = token_data["expires_at"]
            existing_account.username = token_data["username"]
            await db.flush()
            await db.refresh(existing_account)

            await instagram_client.subscribe_app(
                instagram_user_id=existing_account.instagram_user_id,
                access_token=token_data["access_token"],
                subscribed_fields=["comments"],
            )
            logger.info(
                "instagram_webhook_subscribed ig_id=%s fields=%s",
                existing_account.instagram_user_id,
                ["comments"],
            )
            return existing_account

        # Create new account
        account = InstagramAccount(
            user_id=current_user.id,
            instagram_user_id=token_data["ig_id"],
            instagram_app_scoped_id=token_data["app_scoped_id"],
            username=token_data["username"],
            access_token=instagram_client.encrypt_token(token_data["access_token"]),
            token_expires_at=token_data["expires_at"],
        )

        db.add(account)
        await db.flush()
        await db.refresh(account)

        await instagram_client.subscribe_app(
            instagram_user_id=account.instagram_user_id,
            access_token=token_data["access_token"],
            subscribed_fields=["comments"],
        )
        logger.info(
            "instagram_webhook_subscribed ig_id=%s fields=%s",
            account.instagram_user_id,
            ["comments"],
        )

        return account

    except ValueError as e:
        # Sanitized error from instagram_client
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except GraphAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to enable Instagram webhook subscription: {e}",
        )
    except Exception:
        # Unknown error - don't expose details
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to link Instagram account",
        )


@router.get("/account", response_model=InstagramAccountResponse)
async def get_account(current_user: CurrentUser, db: DBSession) -> InstagramAccount:
    """Get the linked Instagram account."""
    return await get_user_instagram_account(current_user, db)


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_account(current_user: CurrentUser, db: DBSession) -> None:
    """Unlink the Instagram account."""
    account = await get_user_instagram_account(current_user, db)
    await db.delete(account)


@router.get("/posts", response_model=InstagramPostsListResponse)
async def list_posts(
    current_user: CurrentUser,
    db: DBSession,
    after: str | None = None,
) -> InstagramPostsListResponse:
    """List posts from linked Instagram account."""
    account = await get_user_instagram_account(current_user, db)

    try:
        access_token = instagram_client.decrypt_token(account.access_token)
        media_data = await instagram_client.get_user_media(access_token, after)

        posts = [
            InstagramPostResponse(
                id=post["id"],
                caption=post.get("caption"),
                media_type=post["media_type"],
                media_url=post.get("media_url"),
                permalink=post.get("permalink"),
                thumbnail_url=post.get("thumbnail_url"),
                timestamp=post.get("timestamp"),
                username=post.get("username"),
            )
            for post in media_data.get("data", [])
        ]

        next_cursor = None
        if "paging" in media_data and "cursors" in media_data["paging"]:
            next_cursor = media_data["paging"]["cursors"].get("after")

        return InstagramPostsListResponse(posts=posts, next_cursor=next_cursor)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch posts: {str(e)}",
        )
