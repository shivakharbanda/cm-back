from app.api.routes.auth import router as auth_router
from app.api.routes.instagram import router as instagram_router
from app.api.routes.automations import router as automations_router
from app.api.routes.bio_pages import router as bio_pages_router
from app.api.routes.bio_links import router as bio_links_router
from app.api.routes.bio_links import utils_router
from app.api.routes.bio_cards import router as bio_cards_router
from app.api.routes.page_items import router as page_items_router
from app.api.routes.routing_rules import router as routing_rules_router
from app.api.routes.leads import router as leads_router
from app.api.routes.analytics import router as analytics_router
from app.api.routes.public_bio import router as public_bio_router
from app.api.routes.social_links import router as social_links_router

__all__ = [
    "auth_router",
    "instagram_router",
    "automations_router",
    # Link-in-Bio routers
    "bio_pages_router",
    "bio_links_router",
    "bio_cards_router",
    "page_items_router",
    "routing_rules_router",
    "leads_router",
    "analytics_router",
    "public_bio_router",
    "social_links_router",
    "utils_router",
]
