"""Public contact form submission endpoint."""

from fastapi import APIRouter, Request, status

from app.api.deps import DBSession
from app.api.limiter import limiter
from app.schemas.contact_submission import ContactSubmissionCreate, ContactSubmissionResponse
from app.services.contact_submission_service import ContactSubmissionService

router = APIRouter(prefix="/contact-submissions", tags=["contact"])


@router.post("", response_model=ContactSubmissionResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def submit_contact_form(
    body: ContactSubmissionCreate,
    request: Request,
    db: DBSession,
) -> ContactSubmissionResponse:
    """Submit the public contact form. No authentication required."""
    service = ContactSubmissionService(db)
    submission = await service.create(body)
    return ContactSubmissionResponse.model_validate(submission)
