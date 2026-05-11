"""Public notification subscription endpoint — capture emails for specific notification types."""

from fastapi import APIRouter, Request, status

from app.api.deps import DBSession
from app.api.limiter import limiter
from app.schemas.notification_subscription import (
    NotificationSubscriptionCreate,
    NotificationSubscriptionResponse,
)
from app.services.notification_subscription_service import NotificationSubscriptionService

router = APIRouter(prefix="/notification-subscriptions", tags=["notifications"])


@router.post("", response_model=NotificationSubscriptionResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def subscribe(
    body: NotificationSubscriptionCreate,
    request: Request,
    db: DBSession,
) -> NotificationSubscriptionResponse:
    """Subscribe an email for a specific notification type. No auth required."""
    service = NotificationSubscriptionService(db)
    sub = await service.subscribe(body)
    return NotificationSubscriptionResponse.model_validate(sub)
