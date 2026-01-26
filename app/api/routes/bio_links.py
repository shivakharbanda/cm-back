"""Bio link management routes."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DBSession
from app.models import BioLink
from app.schemas.bio_link import (
    BioLinkCreate,
    BioLinkUpdate,
    BioLinkResponse,
    URLMetadataRequest,
    URLMetadataResponse,
)
from app.services.bio_link_service import BioLinkService
from app.services.og_metadata_service import OGMetadataService

router = APIRouter(prefix="/bio-pages/{page_id}/links", tags=["bio-links"])
utils_router = APIRouter(prefix="/utils", tags=["utils"])


@router.post("", response_model=BioLinkResponse, status_code=status.HTTP_201_CREATED)
async def create_bio_link(
    page_id: UUID,
    data: BioLinkCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> BioLink:
    """Create a new bio link."""
    service = BioLinkService(db)

    try:
        link, position = await service.create(page_id, data, current_user.id)
        return link
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("", response_model=list[BioLinkResponse])
async def list_bio_links(
    page_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> list[BioLink]:
    """List all links for a bio page."""
    service = BioLinkService(db)

    try:
        return await service.list_for_page(page_id, current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put("/{link_id}", response_model=BioLinkResponse)
async def update_bio_link(
    page_id: UUID,
    link_id: UUID,
    data: BioLinkUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> BioLink:
    """Update a bio link."""
    service = BioLinkService(db)
    link = await service.update(link_id, data, current_user.id)

    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bio link not found",
        )

    return link


@router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bio_link(
    page_id: UUID,
    link_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> None:
    """Delete a bio link."""
    service = BioLinkService(db)
    deleted = await service.delete(link_id, current_user.id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bio link not found",
        )


@utils_router.post("/url-metadata", response_model=URLMetadataResponse)
async def fetch_url_metadata(
    data: URLMetadataRequest,
    current_user: CurrentUser,
) -> URLMetadataResponse:
    """Fetch Open Graph metadata from a URL for preview."""
    metadata = await OGMetadataService.fetch(data.url)
    return URLMetadataResponse(
        title=metadata.title,
        description=metadata.description,
        image=metadata.image,
        site_name=metadata.site_name,
    )
