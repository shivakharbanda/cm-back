"""Bio card management routes."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DBSession
from app.models import BioCard
from app.schemas.bio_card import BioCardCreate, BioCardUpdate, BioCardResponse
from app.services.bio_card_service import BioCardService

router = APIRouter(prefix="/bio-pages/{page_id}/cards", tags=["bio-cards"])


@router.post("", response_model=BioCardResponse, status_code=status.HTTP_201_CREATED)
async def create_bio_card(
    page_id: UUID,
    data: BioCardCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> BioCard:
    """Create a new bio card."""
    service = BioCardService(db)

    try:
        card, position = await service.create(page_id, data, current_user.id)
        return card
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("", response_model=list[BioCardResponse])
async def list_bio_cards(
    page_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> list[BioCard]:
    """List all cards for a bio page."""
    service = BioCardService(db)

    try:
        return await service.list_for_page(page_id, current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put("/{card_id}", response_model=BioCardResponse)
async def update_bio_card(
    page_id: UUID,
    card_id: UUID,
    data: BioCardUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> BioCard:
    """Update a bio card."""
    service = BioCardService(db)
    card = await service.update(card_id, data, current_user.id)

    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bio card not found",
        )

    return card


@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bio_card(
    page_id: UUID,
    card_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> None:
    """Delete a bio card."""
    service = BioCardService(db)
    deleted = await service.delete(card_id, current_user.id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bio card not found",
        )
