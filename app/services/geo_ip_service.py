"""Service for GeoIP lookup and device detection."""

import re
from typing import Any

from app.config import settings


class GeoIPService:
    """Service for IP geolocation and device detection."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or settings.geoip_database_path
        self._reader = None

    @property
    def reader(self):
        """Lazy load the GeoIP database reader."""
        if self._reader is None:
            try:
                import geoip2.database
                self._reader = geoip2.database.Reader(self.db_path)
            except Exception:
                # Return None if database not available
                return None
        return self._reader

    def get_country_code(self, ip: str) -> str | None:
        """
        Get ISO country code from IP address.
        Returns None if lookup fails or database not available.
        """
        if not self.reader:
            return None

        try:
            response = self.reader.country(ip)
            return response.country.iso_code
        except Exception:
            return None

    @staticmethod
    def parse_device_type(user_agent: str) -> str:
        """
        Parse device type from user agent string.
        Returns 'mobile', 'tablet', or 'desktop'.
        """
        if not user_agent:
            return "desktop"

        user_agent_lower = user_agent.lower()

        # Check for tablets first (more specific)
        tablet_patterns = [
            r"ipad",
            r"android(?!.*mobile)",
            r"tablet",
            r"kindle",
            r"playbook",
            r"silk",
        ]
        for pattern in tablet_patterns:
            if re.search(pattern, user_agent_lower):
                return "tablet"

        # Check for mobile
        mobile_patterns = [
            r"mobile",
            r"iphone",
            r"ipod",
            r"android.*mobile",
            r"blackberry",
            r"windows phone",
            r"opera mini",
            r"opera mobi",
        ]
        for pattern in mobile_patterns:
            if re.search(pattern, user_agent_lower):
                return "mobile"

        return "desktop"

    @staticmethod
    def parse_browser(user_agent: str) -> str:
        """Parse browser name from user agent string."""
        if not user_agent:
            return "unknown"

        user_agent_lower = user_agent.lower()

        if "edg" in user_agent_lower:
            return "edge"
        elif "chrome" in user_agent_lower:
            return "chrome"
        elif "firefox" in user_agent_lower:
            return "firefox"
        elif "safari" in user_agent_lower:
            return "safari"
        elif "opera" in user_agent_lower or "opr" in user_agent_lower:
            return "opera"
        elif "msie" in user_agent_lower or "trident" in user_agent_lower:
            return "ie"

        return "other"

    def build_visitor_data(
        self,
        ip: str | None = None,
        user_agent: str | None = None,
        referrer: str | None = None,
    ) -> dict[str, Any]:
        """Build visitor data dictionary from request information."""
        data = {}

        if ip:
            data["ip"] = ip
            country = self.get_country_code(ip)
            if country:
                data["country"] = country

        if user_agent:
            data["user_agent"] = user_agent
            data["device_type"] = self.parse_device_type(user_agent)
            data["browser"] = self.parse_browser(user_agent)

        if referrer:
            data["referrer"] = referrer

        return data


# Singleton instance
geo_ip_service = GeoIPService()
