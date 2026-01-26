"""Service for bio page operations."""

import re
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BioPage, User, RESERVED_SLUGS
from app.models.social_link import SocialLink
from app.schemas.bio_page import BioPageCreate, BioPageUpdate


class BioPageService:
    """Service for bio page CRUD operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def validate_slug(
        self, slug: str, exclude_page_id: UUID | None = None
    ) -> tuple[bool, str | None]:
        """
        Validate a slug is available.
        Returns (is_valid, error_message).
        """
        # Check reserved slugs
        if slug.lower() in RESERVED_SLUGS:
            return False, f"'{slug}' is a reserved slug"

        # Check valid format (alphanumeric, underscores, hyphens)
        if not re.match(r"^[a-zA-Z0-9_-]+$", slug):
            return False, "Slug can only contain letters, numbers, underscores, and hyphens"

        # Check not taken by active page
        query = select(BioPage).where(
            BioPage.slug == slug,
            BioPage.deleted_at.is_(None),
        )
        if exclude_page_id:
            query = query.where(BioPage.id != exclude_page_id)

        result = await self.db.execute(query)
        if result.scalar_one_or_none():
            return False, f"'{slug}' is already taken"

        # Check not in soft-delete hold period (30 days)
        hold_cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        query = select(BioPage).where(
            BioPage.slug == slug,
            BioPage.deleted_at.is_not(None),
            BioPage.deleted_at > hold_cutoff,
        )
        if exclude_page_id:
            query = query.where(BioPage.id != exclude_page_id)

        result = await self.db.execute(query)
        if result.scalar_one_or_none():
            return False, f"'{slug}' is reserved (recently deleted)"

        return True, None

    async def _generate_slug(self, user: User) -> str:
        """Generate a unique slug for a user."""
        # Use email prefix as base slug
        base_slug = user.email.split("@")[0].lower()
        # Clean up the slug (only keep alphanumeric, underscores, hyphens)
        base_slug = re.sub(r"[^a-z0-9_-]", "", base_slug)
        if not base_slug:
            base_slug = "user"

        slug = base_slug
        counter = 1

        while True:
            is_valid, _ = await self.validate_slug(slug)
            if is_valid:
                break
            slug = f"{base_slug}{counter}"
            counter += 1

        return slug

    async def create(self, data: BioPageCreate, user_id: UUID) -> BioPage:
        """Create a new bio page for a user."""
        # Check if user already has a bio page
        result = await self.db.execute(
            select(BioPage).where(
                BioPage.user_id == user_id,
                BioPage.deleted_at.is_(None),
            )
        )
        if result.scalar_one_or_none():
            raise ValueError("User already has a bio page")

        # Get user for slug generation
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("User not found")

        # Use provided slug or generate one
        if data.slug:
            is_valid, error = await self.validate_slug(data.slug)
            if not is_valid:
                raise ValueError(error)
            slug = data.slug
        else:
            slug = await self._generate_slug(user)

        bio_page = BioPage(
            user_id=user_id,
            slug=slug,
            display_name=user.email.split("@")[0],
        )

        self.db.add(bio_page)
        await self.db.flush()
        await self.db.refresh(bio_page)

        return bio_page

    async def get_by_id(self, page_id: UUID, user_id: UUID) -> BioPage | None:
        """Get a bio page by ID if it belongs to the user."""
        result = await self.db.execute(
            select(BioPage).where(
                BioPage.id == page_id,
                BioPage.user_id == user_id,
                BioPage.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> BioPage | None:
        """Get a bio page by slug (for public access)."""
        result = await self.db.execute(
            select(BioPage).where(
                BioPage.slug == slug,
                BioPage.deleted_at.is_(None),
                BioPage.is_published == True,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: UUID) -> list[BioPage]:
        """List all bio pages for a user."""
        result = await self.db.execute(
            select(BioPage)
            .where(
                BioPage.user_id == user_id,
                BioPage.deleted_at.is_(None),
            )
            .order_by(BioPage.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(
        self, page_id: UUID, data: BioPageUpdate, user_id: UUID
    ) -> BioPage | None:
        """Update a bio page."""
        bio_page = await self.get_by_id(page_id, user_id)

        if not bio_page:
            return None

        try:
            # Update bio page fields (exclude social_links)
            update_data = data.model_dump(exclude_unset=True, exclude={"social_links"})

            # Validate slug if changing
            if "slug" in update_data and update_data["slug"] != bio_page.slug:
                is_valid, error = await self.validate_slug(update_data["slug"], page_id)
                if not is_valid:
                    raise ValueError(error)

            for field, value in update_data.items():
                setattr(bio_page, field, value)

            # Handle social links if provided
            if data.social_links is not None:
                # Delete existing social links for this page
                await self.db.execute(
                    delete(SocialLink).where(SocialLink.bio_page_id == page_id)
                )

                # Create new social links with positions
                for position, link_data in enumerate(data.social_links):
                    social_link = SocialLink(
                        bio_page_id=page_id,
                        platform=link_data.platform,
                        url=link_data.url,
                        is_active=link_data.is_active,
                        position=position,
                    )
                    self.db.add(social_link)

            # Commit transaction - all or nothing
            await self.db.commit()
            await self.db.refresh(bio_page)
            return bio_page

        except IntegrityError as e:
            await self.db.rollback()
            # Surface the error, don't fail silently
            if "slug" in str(e):
                raise ValueError("This URL slug is already taken")
            if "platform" in str(e):
                raise ValueError("Duplicate social platform not allowed")
            raise ValueError(f"Failed to save: {str(e)}")
        except ValueError:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            raise ValueError(f"Failed to save settings: {str(e)}")

    async def delete(self, page_id: UUID, user_id: UUID) -> bool:
        """Soft delete a bio page."""
        bio_page = await self.get_by_id(page_id, user_id)

        if not bio_page:
            return False

        # Soft delete - set deleted_at
        bio_page.deleted_at = datetime.now(timezone.utc)
        bio_page.is_published = False

        await self.db.flush()
        return True

    async def publish(self, page_id: UUID, user_id: UUID) -> BioPage | None:
        """Publish a bio page."""
        bio_page = await self.get_by_id(page_id, user_id)

        if not bio_page:
            return None

        bio_page.is_published = True
        await self.db.flush()
        await self.db.refresh(bio_page)

        return bio_page

    async def unpublish(self, page_id: UUID, user_id: UUID) -> BioPage | None:
        """Unpublish a bio page."""
        bio_page = await self.get_by_id(page_id, user_id)

        if not bio_page:
            return None

        bio_page.is_published = False
        await self.db.flush()
        await self.db.refresh(bio_page)

        return bio_page
