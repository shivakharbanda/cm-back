"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    auth_router,
    automations_router,
    instagram_router,
    bio_pages_router,
    bio_links_router,
    bio_cards_router,
    page_items_router,
    routing_rules_router,
    leads_router,
    analytics_router,
    public_bio_router,
    social_links_router,
    utils_router,
)
from app.config import settings
from app.db import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    yield
    await engine.dispose()


app = FastAPI(
    title="Instagram Automation Service",
    description="Backend service for Instagram Auto-DM automation",
    version="0.1.0",
    lifespan=lifespan,
)

# Log environment settings on startup
print(f"[CONFIG] is_development: {settings.is_development}")
print(f"[CONFIG] Cookies secure flag: {not settings.is_development}")
print(f"[CONFIG] Frontend URL: {settings.frontend_url}")

# CORS middleware (can't use allow_origins=["*"] with allow_credentials=True)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(instagram_router, prefix="/api/v1")
app.include_router(automations_router, prefix="/api/v1")

# Link-in-Bio routers
app.include_router(bio_pages_router, prefix="/api/v1")
app.include_router(bio_links_router, prefix="/api/v1")
app.include_router(bio_cards_router, prefix="/api/v1")
app.include_router(page_items_router, prefix="/api/v1")
app.include_router(routing_rules_router, prefix="/api/v1")
app.include_router(leads_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(public_bio_router, prefix="/api/v1")
app.include_router(social_links_router, prefix="/api/v1")
app.include_router(utils_router, prefix="/api/v1")


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "service": "automation-service"}


@app.get("/")
async def root() -> dict:
    """Root endpoint."""
    return {
        "service": "Instagram Automation Service",
        "version": "0.1.0",
        "docs": "/docs",
    }
