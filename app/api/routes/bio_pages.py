"""Bio page management routes."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DBSession
from app.models import BioPage
from app.schemas.bio_page import BioPageCreate, BioPageUpdate, BioPageResponse
from app.services.bio_page_service import BioPageService

router = APIRouter(prefix="/bio-pages", tags=["bio-pages"])


@router.post("", response_model=BioPageResponse, status_code=status.HTTP_201_CREATED)
async def create_bio_page(
    data: BioPageCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> BioPage:
    """Create a bio page for the current user."""
    service = BioPageService(db)

    try:
        bio_page = await service.create(data, current_user.id)
        return bio_page
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("", response_model=list[BioPageResponse])
async def list_bio_pages(
    current_user: CurrentUser,
    db: DBSession,
) -> list[BioPage]:
    """List all bio pages for the current user."""
    service = BioPageService(db)
    return await service.list_for_user(current_user.id)


@router.get("/{page_id}", response_model=BioPageResponse)
async def get_bio_page(
    page_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> BioPage:
    """Get a specific bio page."""
    service = BioPageService(db)
    bio_page = await service.get_by_id(page_id, current_user.id)

    if not bio_page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bio page not found",
        )

    return bio_page


@router.put("/{page_id}", response_model=BioPageResponse)
async def update_bio_page(
    page_id: UUID,
    data: BioPageUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> BioPage:
    """Update a bio page."""
    service = BioPageService(db)

    try:
        bio_page = await service.update(page_id, data, current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if not bio_page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bio page not found",
        )

    return bio_page


@router.delete("/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bio_page(
    page_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> None:
    """Delete a bio page."""
    service = BioPageService(db)
    deleted = await service.delete(page_id, current_user.id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bio page not found",
        )


@router.post("/{page_id}/publish", response_model=BioPageResponse)
async def publish_bio_page(
    page_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> BioPage:
    """Publish a bio page."""
    service = BioPageService(db)
    bio_page = await service.publish(page_id, current_user.id)

    if not bio_page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bio page not found",
        )

    return bio_page


@router.post("/{page_id}/unpublish", response_model=BioPageResponse)
async def unpublish_bio_page(
    page_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> BioPage:
    """Unpublish a bio page."""
    service = BioPageService(db)
    bio_page = await service.unpublish(page_id, current_user.id)

    if not bio_page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bio page not found",
        )

    return bio_page
