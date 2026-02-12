"""JWT validation and authentication utilities."""

import uuid
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import get_logger
from app.db.base import get_db
from app.db.models import User

logger = get_logger(__name__)
security = HTTPBearer(auto_error=False)

# NextAuth session cookie names
NEXTAUTH_COOKIE_NAME = "next-auth.session-token"
NEXTAUTH_SECURE_COOKIE_NAME = "__Secure-next-auth.session-token"


def get_token_from_cookie(request: Request) -> Optional[str]:
    """Extract NextAuth session token from cookies."""
    # Try secure cookie first (production with HTTPS)
    token = request.cookies.get(NEXTAUTH_SECURE_COOKIE_NAME)
    if token:
        return token
    # Fall back to non-secure cookie (development)
    return request.cookies.get(NEXTAUTH_COOKIE_NAME)


class TokenPayload(BaseModel):
    """JWT token payload from NextAuth."""

    sub: str  # User ID (google_id)
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    iat: int
    exp: int


class CurrentUser(BaseModel):
    """Current authenticated user."""

    id: str
    email: str
    name: Optional[str] = None
    image: Optional[str] = None
    google_id: str


def decode_jwt(token: str) -> TokenPayload:
    """Decode and validate NextAuth JWT."""
    try:
        payload = jwt.decode(
            token,
            settings.nextauth_secret,
            algorithms=["HS256"],
            # Audience verification enabled; configure audience claim in JWT issuer if needed
        )
        return TokenPayload(**payload)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError as e:
        logger.warning("jwt_validation_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


async def get_or_create_user(db: AsyncSession, token_payload: TokenPayload) -> User:
    """Get existing user or create new one from token payload."""
    # Try to find existing user by google_id
    result = await db.execute(select(User).where(User.google_id == token_payload.sub))
    user = result.scalar_one_or_none()

    if user:
        # Update user info if changed
        if user.name != token_payload.name or user.image != token_payload.picture:
            user.name = token_payload.name
            user.image = token_payload.picture
            await db.commit()
        return user

    # Create new user
    user = User(
        id=str(uuid.uuid4()),
        email=token_payload.email,
        name=token_payload.name,
        image=token_payload.picture,
        google_id=token_payload.sub,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info("user_created", user_id=user.id, email=user.email)
    return user


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """Dependency to get current authenticated user.

    Accepts JWT token from:
    1. Authorization header (Bearer token)
    2. NextAuth session cookie (fallback for browser requests)
    """
    if not settings.auth_enabled:
        # Return a dummy user when auth is disabled (for development)
        return CurrentUser(
            id="dev-user",
            email="dev@example.com",
            name="Developer",
            image=None,
            google_id="dev-google-id",
        )

    # Try to get token from Authorization header first
    token: Optional[str] = None
    if credentials:
        token = credentials.credentials
    else:
        # Fall back to cookie-based authentication
        token = get_token_from_cookie(request)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_payload = decode_jwt(token)
    user = await get_or_create_user(db, token_payload)

    return CurrentUser(
        id=user.id,
        email=user.email,
        name=user.name,
        image=user.image,
        google_id=user.google_id,
    )


async def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[CurrentUser]:
    """Dependency to optionally get current user (no error if not authenticated)."""
    # Check if there's any token available
    token: Optional[str] = None
    if credentials:
        token = credentials.credentials
    else:
        token = get_token_from_cookie(request)

    if not token:
        return None

    try:
        return await get_current_user(request, credentials, db)
    except HTTPException:
        return None
