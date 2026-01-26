"""Analytics routes."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, DBSession
from app.schemas.analytics import (
    PageAnalyticsResponse,
    ItemAnalyticsResponse,
    AnalyticsDatePoint,
    LinkAnalyticsItem,
    CardAnalyticsItem,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/bio-pages/{page_id}/analytics", tags=["analytics"])


@router.get("", response_model=PageAnalyticsResponse)
async def get_page_analytics(
    page_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    granularity: str = Query("daily", description="Granularity: daily, weekly, monthly"),
) -> PageAnalyticsResponse:
    """Get page analytics for a date range."""
    service = AnalyticsService(db)

    try:
        data = await service.get_page_analytics(
            page_id, current_user.id, start_date, end_date, granularity
        )
        return PageAnalyticsResponse(
            total_views=data["total_views"],
            total_clicks=data["total_clicks"],
            ctr=data["ctr"],
            views_by_date=[
                AnalyticsDatePoint(date=d["date"], value=d["value"])
                for d in data["views_by_date"]
            ],
            clicks_by_date=[
                AnalyticsDatePoint(date=d["date"], value=d["value"])
                for d in data["clicks_by_date"]
            ],
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/items", response_model=ItemAnalyticsResponse)
async def get_item_analytics(
    page_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
) -> ItemAnalyticsResponse:
    """Get per-item (links and cards) analytics."""
    service = AnalyticsService(db)

    try:
        data = await service.get_item_analytics(
            page_id, current_user.id, start_date, end_date
        )
        return ItemAnalyticsResponse(
            links=[
                LinkAnalyticsItem(
                    id=link["id"],
                    title=link["title"],
                    clicks=link["clicks"],
                    ctr=link["ctr"],
                )
                for link in data["links"]
            ],
            cards=[
                CardAnalyticsItem(
                    id=card["id"],
                    headline=card["headline"],
                    views=card["views"],
                    submissions=card["submissions"],
                    conversion_rate=card["conversion_rate"],
                )
                for card in data["cards"]
            ],
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/export")
async def export_analytics(
    page_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
) -> StreamingResponse:
    """Export analytics as CSV."""
    service = AnalyticsService(db)

    try:
        csv_data = await service.export_csv(
            page_id, current_user.id, start_date, end_date
        )
        return StreamingResponse(
            iter([csv_data]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=analytics_{page_id}.csv"
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
