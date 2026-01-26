"""Leads management routes."""

import math
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, DBSession
from app.schemas.lead import LeadResponse, LeadListResponse
from app.services.lead_service import LeadService

router = APIRouter(prefix="/bio-pages/{page_id}/leads", tags=["leads"])


@router.get("", response_model=LeadListResponse)
async def list_leads(
    page_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    page: int = 1,
    limit: int = 50,
    card_id: UUID | None = None,
) -> LeadListResponse:
    """List leads for a bio page with pagination."""
    service = LeadService(db)

    try:
        leads, total = await service.list_leads(
            page_id, current_user.id, page, limit, card_id
        )
        pages = math.ceil(total / limit) if total > 0 else 1
        return LeadListResponse(
            leads=[LeadResponse.model_validate(lead) for lead in leads],
            total=total,
            page=page,
            pages=pages,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/export")
async def export_leads(
    page_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> StreamingResponse:
    """Export leads as CSV."""
    service = LeadService(db)

    try:
        csv_data = await service.export_csv(page_id, current_user.id)
        return StreamingResponse(
            iter([csv_data]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=leads_{page_id}.csv"
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    page_id: UUID,
    lead_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> None:
    """Delete a lead."""
    service = LeadService(db)
    deleted = await service.delete_lead(lead_id, current_user.id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )
