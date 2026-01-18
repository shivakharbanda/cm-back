from app.api.routes.auth import router as auth_router
from app.api.routes.instagram import router as instagram_router
from app.api.routes.automations import router as automations_router

__all__ = ["auth_router", "instagram_router", "automations_router"]
