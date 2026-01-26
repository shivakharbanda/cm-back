"""Social link management routes."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DBSession
from app.models.social_link import SocialLink
from app.schemas.social_link import (
    SocialLinkCreate,
    SocialLinkUpdate,
    SocialLinkResponse,
    SocialLinkReorderRequest,
)
from app.services.social_link_service import SocialLinkService

router = APIRouter(prefix="/bio-pages/{page_id}/social-links", tags=["social-links"])


@router.post("", response_model=SocialLinkResponse, status_code=status.HTTP_201_CREATED)
async def create_social_link(
    page_id: UUID,
    data: SocialLinkCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> SocialLink:
    """Create a new social link."""
    service = SocialLinkService(db)

    try:
        return await service.create(page_id, data, current_user.id)
    except ValueError as e:
        error_message = str(e)
        if "already exists" in error_message:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_message,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message,
        )


@router.get("", response_model=list[SocialLinkResponse])
async def list_social_links(
    page_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> list[SocialLink]:
    """List all social links for a bio page."""
    service = SocialLinkService(db)

    try:
        return await service.list_for_page(page_id, current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put("/{social_link_id}", response_model=SocialLinkResponse)
async def update_social_link(
    page_id: UUID,
    social_link_id: UUID,
    data: SocialLinkUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> SocialLink:
    """Update a social link."""
    service = SocialLinkService(db)
    social_link = await service.update(social_link_id, data, current_user.id)

    if not social_link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Social link not found",
        )

    return social_link


@router.delete("/{social_link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_social_link(
    page_id: UUID,
    social_link_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> None:
    """Delete a social link."""
    service = SocialLinkService(db)
    deleted = await service.delete(social_link_id, current_user.id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Social link not found",
        )


@router.put("/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_social_links(
    page_id: UUID,
    data: SocialLinkReorderRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> None:
    """Reorder social links."""
    service = SocialLinkService(db)

    try:
        await service.reorder(page_id, data, current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
