"""
Публичные эндпоинты (без авторизации):
  - Просмотр приглашения по токену
  - Принятие приглашения (создание аккаунта)
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.database import get_db
from app.models.invitation import Invitation
from app.models.user import User
from app.schemas.invitation import AcceptInvitation, InvitationOut

router = APIRouter(prefix="/invitations", tags=["invitations"])


@router.get("/{token}", response_model=InvitationOut)
async def get_invitation(token: str, db: AsyncSession = Depends(get_db)):
    """Возвращает детали приглашения. Используется фронтендом для отображения формы регистрации."""
    result = await db.execute(select(Invitation).where(Invitation.token == token))
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if inv.status != "pending":
        raise HTTPException(status_code=400, detail=f"Invitation is already {inv.status}")
    if inv.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        inv.status = "expired"
        await db.commit()
        raise HTTPException(status_code=400, detail="Invitation has expired")
    return inv


@router.post("/{token}/accept")
async def accept_invitation(
    token: str,
    data: AcceptInvitation,
    db: AsyncSession = Depends(get_db),
):
    """Пользователь устанавливает имя и пароль, получает аккаунт."""
    result = await db.execute(select(Invitation).where(Invitation.token == token))
    inv = result.scalar_one_or_none()
    if not inv or inv.status != "pending":
        raise HTTPException(status_code=400, detail="Invalid or already used invitation")
    if inv.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        inv.status = "expired"
        await db.commit()
        raise HTTPException(status_code=400, detail="Invitation has expired")

    # Email уже зарегистрирован?
    existing = await db.execute(select(User).where(User.email == inv.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email is already registered")

    if len(data.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    user = User(
        email=inv.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role=inv.role,
        org_id=inv.org_id,
        status="active",
    )
    db.add(user)
    inv.status = "accepted"
    await db.commit()

    return {"message": "Account created. You can now log in.", "email": inv.email}
