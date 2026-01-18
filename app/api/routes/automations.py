"""Automation management routes."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DBSession
from app.models import Automation
from app.schemas.automation import AutomationCreate, AutomationResponse, AutomationUpdate
from app.services.automation_repository import AutomationRepository

router = APIRouter(prefix="/automations", tags=["automations"])


@router.post("", response_model=AutomationResponse, status_code=status.HTTP_201_CREATED)
async def create_automation(
    data: AutomationCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> Automation:
    """Create a new automation."""
    repo = AutomationRepository(db)

    try:
        automation = await repo.create(data, current_user.id)
        return automation
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("", response_model=list[AutomationResponse])
async def list_automations(
    current_user: CurrentUser,
    db: DBSession,
    instagram_account_id: UUID | None = None,
) -> list[Automation]:
    """List all automations for the current user."""
    repo = AutomationRepository(db)

    if instagram_account_id:
        try:
            return await repo.list_for_account(instagram_account_id, current_user.id)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

    return await repo.list_for_user(current_user.id)


@router.get("/{automation_id}", response_model=AutomationResponse)
async def get_automation(
    automation_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> Automation:
    """Get a specific automation."""
    repo = AutomationRepository(db)
    automation = await repo.get_by_id(automation_id, current_user.id)

    if not automation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automation not found",
        )

    return automation


@router.put("/{automation_id}", response_model=AutomationResponse)
async def update_automation(
    automation_id: UUID,
    data: AutomationUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> Automation:
    """Update an automation."""
    repo = AutomationRepository(db)
    automation = await repo.update(automation_id, data, current_user.id)

    if not automation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automation not found",
        )

    return automation


@router.delete("/{automation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_automation(
    automation_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> None:
    """Delete an automation."""
    repo = AutomationRepository(db)
    deleted = await repo.delete(automation_id, current_user.id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automation not found",
        )


@router.post("/{automation_id}/activate", response_model=AutomationResponse)
async def activate_automation(
    automation_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> Automation:
    """Activate an automation."""
    repo = AutomationRepository(db)
    automation = await repo.activate(automation_id, current_user.id)

    if not automation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automation not found",
        )

    return automation


@router.post("/{automation_id}/deactivate", response_model=AutomationResponse)
async def deactivate_automation(
    automation_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> Automation:
    """Deactivate an automation."""
    repo = AutomationRepository(db)
    automation = await repo.deactivate(automation_id, current_user.id)

    if not automation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automation not found",
        )

    return automation
