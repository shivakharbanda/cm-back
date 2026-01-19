"""Authentication routes."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession
from app.config import settings
from app.models import User
from app.schemas.auth import (
    UserCreate,
    UserLogin,
    UserResponse,
)
from app.services.auth import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

# Cookie settings
ACCESS_TOKEN_MAX_AGE = 1800  # 30 minutes
REFRESH_TOKEN_MAX_AGE = 604800  # 7 days


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Set HTTP-only authentication cookies."""
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=not settings.is_development,  # True for HTTPS in production
        samesite="lax",
        max_age=ACCESS_TOKEN_MAX_AGE,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=not settings.is_development,  # True for HTTPS in production
        samesite="lax",
        max_age=REFRESH_TOKEN_MAX_AGE,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    """Clear authentication cookies."""
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(user_data: UserCreate, db: DBSession) -> User:
    """Register a new user."""
    # Check if user already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create new user
    hashed_password = auth_service.hash_password(user_data.password)
    user = User(
        email=user_data.email,
        hashed_password=hashed_password,
    )

    db.add(user)
    await db.flush()
    await db.refresh(user)

    return user


@router.post("/login", response_model=UserResponse)
async def login(user_data: UserLogin, response: Response, db: DBSession) -> User:
    """Login and set HTTP-only cookies."""
    # Find user by email
    result = await db.execute(select(User).where(User.email == user_data.email))
    user = result.scalar_one_or_none()

    if not user or not auth_service.verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    # Generate tokens
    access_token = auth_service.create_access_token(user.id, user.email)
    refresh_token = auth_service.create_refresh_token(user.id, user.email)

    # Set cookies
    set_auth_cookies(response, access_token, refresh_token)

    return user


@router.post("/refresh", response_model=UserResponse)
async def refresh_token(request: Request, response: Response, db: DBSession) -> User:
    """Refresh access token using refresh token from cookie."""
    refresh_token_value = request.cookies.get("refresh_token")

    if not refresh_token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided",
        )

    payload = auth_service.verify_refresh_token(refresh_token_value)

    if payload is None:
        clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_id = payload.get("sub")
    email = payload.get("email")

    if not user_id or not email:
        clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # Verify user still exists and is active
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    # Generate new tokens
    new_access_token = auth_service.create_access_token(user.id, user.email)
    new_refresh_token = auth_service.create_refresh_token(user.id, user.email)

    # Set new cookies
    set_auth_cookies(response, new_access_token, new_refresh_token)

    return user


@router.post("/logout")
async def logout(response: Response) -> dict:
    """Logout and clear authentication cookies."""
    clear_auth_cookies(response)
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: CurrentUser) -> User:
    """Get current authenticated user info."""
    return current_user
