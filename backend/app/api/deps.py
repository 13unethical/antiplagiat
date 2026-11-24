import uuid
from hashlib import sha256

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.database import get_db
from app.models.user import User

bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> User:
    # ── X-API-Key auth ────────────────────────────────────────────────────────
    if x_api_key:
        from app.models.api_key import ApiKey
        from datetime import datetime, timezone

        key_hash = sha256(x_api_key.encode()).hexdigest()
        result = await db.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active == True)
        )
        api_key = result.scalar_one_or_none()
        if not api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")

        # Update last_used_at
        api_key.last_used_at = datetime.now(timezone.utc)
        await db.commit()

        # Find the school_admin of this org to act as the requesting user
        user_result = await db.execute(
            select(User).where(
                User.org_id == api_key.org_id,
                User.role == "school_admin",
                User.status == "active",
            ).limit(1)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=403, detail="No active admin for this organization")
        return user

    # ── Bearer JWT auth ───────────────────────────────────────────────────────
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = credentials.credentials
    try:
        payload = decode_token(token)
        if payload.get("type") == "refresh":
            raise HTTPException(status_code=401, detail="Use access token, not refresh token")
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if user.status == "inactive":
        raise HTTPException(status_code=403, detail="Account is deactivated")
    return user


def require_role(*roles: str):
    """Returns a FastAPI dependency that checks the user's role."""

    async def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user

    return checker


superadmin_only = require_role("superadmin")
school_admin_only = require_role("school_admin")
admin_or_above = require_role("superadmin", "school_admin")
any_authenticated = require_role("superadmin", "school_admin", "teacher")
