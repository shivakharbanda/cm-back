"""Routing rules management routes."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DBSession
from app.models import RoutingRule
from app.schemas.routing_rule import (
    RoutingRuleCreate,
    RoutingRuleUpdate,
    RoutingRuleResponse,
)
from app.services.routing_service import RoutingService

router = APIRouter(prefix="/bio-links/{link_id}/rules", tags=["routing-rules"])


@router.post("", response_model=RoutingRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_routing_rule(
    link_id: UUID,
    data: RoutingRuleCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> RoutingRule:
    """Create a new routing rule for a smart link."""
    service = RoutingService(db)

    try:
        rule = await service.create_rule(link_id, data, current_user.id)
        return rule
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("", response_model=list[RoutingRuleResponse])
async def list_routing_rules(
    link_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> list[RoutingRule]:
    """List all routing rules for a link."""
    service = RoutingService(db)

    try:
        return await service.list_rules(link_id, current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put("/{rule_id}", response_model=RoutingRuleResponse)
async def update_routing_rule(
    link_id: UUID,
    rule_id: UUID,
    data: RoutingRuleUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> RoutingRule:
    """Update a routing rule."""
    service = RoutingService(db)
    rule = await service.update_rule(rule_id, data, current_user.id)

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Routing rule not found",
        )

    return rule


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_routing_rule(
    link_id: UUID,
    rule_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> None:
    """Delete a routing rule."""
    service = RoutingService(db)
    deleted = await service.delete_rule(rule_id, current_user.id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Routing rule not found",
        )
