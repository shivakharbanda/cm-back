"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth_router, automations_router, instagram_router
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
