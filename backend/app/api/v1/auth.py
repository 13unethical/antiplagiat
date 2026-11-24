import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from jose import JWTError
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import any_authenticated, get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.models.check import Check
from app.models.organization import Organization
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if user.status == "inactive":
        raise HTTPException(status_code=403, detail="Account is deactivated")

    token_data = {"sub": str(user.id)}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(data.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Not a refresh token")
        user_id: str | None = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or user.status == "inactive":
        raise HTTPException(status_code=401, detail="User not found or inactive")

    token_data = {"sub": str(user.id)}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None


@router.patch("/me", response_model=UserOut)
async def update_me(
    data: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(any_authenticated),
):
    """Изменить собственное имя и/или пароль."""
    if data.full_name is not None:
        data.full_name = data.full_name.strip()
        if not data.full_name:
            raise HTTPException(status_code=400, detail="full_name cannot be empty")
        current_user.full_name = data.full_name

    if data.new_password is not None:
        if not data.current_password:
            raise HTTPException(status_code=400, detail="current_password required to set new password")
        if not current_user.hashed_password or not verify_password(data.current_password, current_user.hashed_password):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        if len(data.new_password) < 8:
            raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
        current_user.hashed_password = hash_password(data.new_password)

    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.get("/me/stats")
async def get_my_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(any_authenticated),
):
    """Статистика текущего пользователя: проверки за месяц, лимит."""
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    cnt_q = await db.execute(
        select(func.count()).where(
            Check.submitted_by == current_user.id,
            Check.created_at >= month_start,
        )
    )
    checks_this_month = cnt_q.scalar() or 0

    # Personal quota overrides org quota; None = use org limit
    quota_limit: Optional[int] = current_user.personal_quota
    if quota_limit is None and current_user.org_id:
        org_q = await db.execute(select(Organization).where(Organization.id == current_user.org_id))
        org = org_q.scalar_one_or_none()
        if org:
            quota_limit = org.monthly_quota

    return {
        "checks_this_month": checks_this_month,
        "quota_limit": quota_limit,
        "personal_quota": current_user.personal_quota,
    }
