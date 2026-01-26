"""Public bio page routes (no authentication required)."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import DBSession
from app.schemas.analytics import ViewRequest, ClickRequest, ClickResponse
from app.schemas.bio_card import CardSubmitRequest, CardSubmitResponse
from app.services.page_item_service import PageItemService
from app.services.bio_page_service import BioPageService
from app.services.bio_card_service import BioCardService
from app.services.analytics_service import AnalyticsService
from app.services.lead_service import LeadService
from app.services.routing_service import RoutingService
from app.services.geo_ip_service import geo_ip_service

router = APIRouter(prefix="/public/bio", tags=["public-bio"])


def get_client_ip(request: Request) -> str | None:
    """Extract client IP from request headers."""
    # Check X-Forwarded-For first (for proxies/load balancers)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    # Fall back to X-Real-IP
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fall back to direct client
    if request.client:
        return request.client.host

    return None


@router.get("/{slug}")
async def get_public_bio_page(
    slug: str,
    db: DBSession,
) -> dict[str, Any]:
    """
    Get public bio page with items in order.

    NOTE: This endpoint does NOT track page views.
    Frontend should call POST /view separately after page renders.
    """
    service = PageItemService(db)
    result = await service.get_public_page_items(slug)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bio page not found",
        )

    return result


@router.post("/{slug}/view")
async def track_page_view(
    slug: str,
    data: ViewRequest,
    request: Request,
    db: DBSession,
) -> dict:
    """
    Track a page view.

    Called by frontend after page renders to filter bot traffic.
    """
    # Get bio page
    page_service = BioPageService(db)
    bio_page = await page_service.get_by_slug(slug)

    if not bio_page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bio page not found",
        )

    # Build visitor data
    client_ip = get_client_ip(request)
    visitor_data = geo_ip_service.build_visitor_data(
        ip=client_ip,
        user_agent=data.user_agent or request.headers.get("User-Agent"),
        referrer=data.referrer or request.headers.get("Referer"),
    )

    # Track the view
    analytics_service = AnalyticsService(db)
    await analytics_service.track_page_view(bio_page.id, visitor_data)

    return {"success": True}


@router.post("/{slug}/click/{link_id}", response_model=ClickResponse)
async def track_link_click(
    slug: str,
    link_id: UUID,
    data: ClickRequest,
    request: Request,
    db: DBSession,
) -> ClickResponse:
    """
    Track a link click and get redirect URL.

    For smart links, applies routing rules based on visitor data.
    """
    # Get bio page
    page_service = BioPageService(db)
    bio_page = await page_service.get_by_slug(slug)

    if not bio_page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bio page not found",
        )

    # Build visitor data
    client_ip = get_client_ip(request)
    visitor_data = geo_ip_service.build_visitor_data(
        ip=client_ip,
        user_agent=data.user_agent or request.headers.get("User-Agent"),
    )

    # Track the click
    analytics_service = AnalyticsService(db)
    await analytics_service.track_link_click(bio_page.id, link_id, visitor_data)

    # Get redirect URL (applies smart routing if applicable)
    routing_service = RoutingService(db)
    try:
        redirect_url = await routing_service.resolve_destination(link_id, visitor_data)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found",
        )

    return ClickResponse(redirect_url=redirect_url)


@router.post("/{slug}/card/{card_id}/submit", response_model=CardSubmitResponse)
async def submit_card_lead(
    slug: str,
    card_id: UUID,
    data: CardSubmitRequest,
    request: Request,
    db: DBSession,
) -> CardSubmitResponse:
    """
    Submit email for card lead capture.

    Returns success message and destination URL.
    """
    # Get bio page
    page_service = BioPageService(db)
    bio_page = await page_service.get_by_slug(slug)

    if not bio_page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bio page not found",
        )

    # Get card
    card_service = BioCardService(db)
    card = await card_service.get_by_id_public(card_id)

    if not card or card.bio_page_id != bio_page.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found",
        )

    # Build metadata
    client_ip = get_client_ip(request)
    metadata = geo_ip_service.build_visitor_data(
        ip=client_ip,
        user_agent=request.headers.get("User-Agent"),
        referrer=request.headers.get("Referer"),
    )

    # Capture lead
    lead_service = LeadService(db)
    try:
        await lead_service.capture(bio_page.id, card_id, data.email, metadata)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Track submission
    analytics_service = AnalyticsService(db)
    await analytics_service.track_card_submission(bio_page.id, card_id)

    return CardSubmitResponse(
        success=True,
        success_message=card.success_message,
        destination_url=card.destination_url,
    )
