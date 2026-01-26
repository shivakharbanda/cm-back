"""Page items (unified ordering) routes."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DBSession
from app.schemas.page_item import PageItemsResponse, ReorderRequest, PageItemWithData
from app.services.page_item_service import PageItemService

router = APIRouter(prefix="/bio-pages/{page_id}/items", tags=["page-items"])


@router.get("", response_model=PageItemsResponse)
async def get_ordered_items(
    page_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> PageItemsResponse:
    """Get all items (links + cards) in display order."""
    service = PageItemService(db)

    try:
        items = await service.get_ordered_items(page_id, current_user.id)
        return PageItemsResponse(
            items=[PageItemWithData(**item) for item in items]
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put("/reorder", status_code=status.HTTP_200_OK)
async def reorder_items(
    page_id: UUID,
    data: ReorderRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> dict:
    """Reorder page items."""
    service = PageItemService(db)

    try:
        await service.reorder(page_id, data, current_user.id)
        return {"success": True}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
