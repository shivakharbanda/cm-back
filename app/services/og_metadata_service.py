"""Service for fetching Open Graph metadata from URLs."""

import asyncio
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup


@dataclass
class OGMetadata:
    """Open Graph metadata from a URL."""

    title: str | None = None
    description: str | None = None
    image: str | None = None
    site_name: str | None = None
    url: str | None = None


class OGMetadataService:
    """Service for fetching Open Graph metadata."""

    TIMEOUT = 10.0  # seconds
    MAX_CONTENT_LENGTH = 1_000_000  # 1MB max

    USER_AGENT = (
        "Mozilla/5.0 (compatible; LinkPreviewBot/1.0; "
        "+https://example.com/bot)"
    )

    @classmethod
    async def fetch(cls, url: str) -> OGMetadata:
        """
        Fetch Open Graph metadata from a URL.

        Returns OGMetadata with available fields, or empty if fetch fails.
        """
        try:
            # Validate URL
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return OGMetadata()

            async with httpx.AsyncClient(
                timeout=cls.TIMEOUT,
                follow_redirects=True,
                max_redirects=5,
            ) as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": cls.USER_AGENT,
                        "Accept": "text/html,application/xhtml+xml",
                    },
                )

                if response.status_code != 200:
                    return OGMetadata()

                # Check content type
                content_type = response.headers.get("content-type", "")
                if "text/html" not in content_type and "application/xhtml" not in content_type:
                    return OGMetadata()

                # Check content length
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > cls.MAX_CONTENT_LENGTH:
                    return OGMetadata()

                html = response.text
                return cls._parse_html(html, url)

        except (httpx.HTTPError, asyncio.TimeoutError, Exception):
            return OGMetadata()

    @classmethod
    def _parse_html(cls, html: str, original_url: str) -> OGMetadata:
        """Parse HTML and extract Open Graph metadata."""
        soup = BeautifulSoup(html, "html.parser")

        def get_meta(property_name: str) -> str | None:
            """Get meta tag content by property or name."""
            # Try og: prefix first
            tag = soup.find("meta", property=property_name)
            if tag and tag.get("content"):
                return tag["content"].strip()

            # Try without prefix
            tag = soup.find("meta", attrs={"name": property_name})
            if tag and tag.get("content"):
                return tag["content"].strip()

            return None

        # Get OG metadata
        og_image = get_meta("og:image")
        og_title = get_meta("og:title")
        og_description = get_meta("og:description")
        og_site_name = get_meta("og:site_name")
        og_url = get_meta("og:url")

        # Fallbacks for title
        if not og_title:
            title_tag = soup.find("title")
            if title_tag:
                og_title = title_tag.get_text().strip()

        # Fallbacks for description
        if not og_description:
            og_description = get_meta("description")

        # Fallbacks for image (twitter:image)
        if not og_image:
            og_image = get_meta("twitter:image")

        # Make image URL absolute
        if og_image and not og_image.startswith(("http://", "https://")):
            parsed = urlparse(original_url)
            if og_image.startswith("//"):
                og_image = f"{parsed.scheme}:{og_image}"
            elif og_image.startswith("/"):
                og_image = f"{parsed.scheme}://{parsed.netloc}{og_image}"
            else:
                og_image = f"{parsed.scheme}://{parsed.netloc}/{og_image}"

        return OGMetadata(
            title=og_title,
            description=og_description,
            image=og_image,
            site_name=og_site_name,
            url=og_url or original_url,
        )


# Singleton instance
og_metadata_service = OGMetadataService()
