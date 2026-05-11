"""Service for contact form submissions."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact_submission import ContactSubmission
from app.schemas.contact_submission import ContactSubmissionCreate


class ContactSubmissionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: ContactSubmissionCreate) -> ContactSubmission:
        submission = ContactSubmission(**data.model_dump())
        self.db.add(submission)
        await self.db.flush()
        await self.db.refresh(submission)
        return submission
