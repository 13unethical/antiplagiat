"""
Эндпоинты только для superadmin:
  - Управление организациями
  - Приглашение school_admin
  - Список всех пользователей
  - Управление спорами (disputes)
"""
import hashlib
import os
import secrets
import shutil
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import superadmin_only
from app.config import settings
from app.database import get_db
from app.services.email import send_invitation_email

from app.core.security import create_access_token, hash_password
from app.models.api_key import ApiKey
from app.models.api_request_log import ApiRequestLog
from app.models.audit_log import AuditLog
from app.models.check import Check, CheckDocument, CheckFlag
from app.models.dataset_entry import DatasetEntry
from app.models.dispute import Dispute
from app.models.model_version import ModelVersion
from app.models.repository_document import RepositoryDocument
from app.models.web_search_log import WebSearchLog
from app.models.invitation import Invitation
from app.models.organization import Organization
from app.models.user import User
from app.schemas.auth import UserOut
from app.schemas.invitation import InvitationCreate, InvitationOut
from app.schemas.organization import OrganizationCreate, OrganizationOut, OrganizationUpdate

router = APIRouter(prefix="/admin", tags=["admin"])

# ---------------------------------------------------------------------------
# Статистика платформы
# ---------------------------------------------------------------------------


@router.get("/stats")
async def platform_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(superadmin_only),
):
    """Общая статистика платформы."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    orgs_q = await db.execute(select(func.count()).select_from(Organization))
    teachers_q = await db.execute(
        select(func.count()).where(User.role == "teacher", User.status == "active")
    )
    admins_q = await db.execute(
        select(func.count()).where(User.role == "school_admin", User.status == "active")
    )
    checks_q = await db.execute(
        select(func.count()).where(Check.created_at >= month_start)
    )
    flagged_q = await db.execute(
        select(func.count(func.distinct(CheckFlag.check_id)))
        .join(Check, Check.id == CheckFlag.check_id)
        .where(Check.created_at >= month_start)
    )
    web_queries_q = await db.execute(
        select(func.coalesce(func.sum(WebSearchLog.queries_count), 0))
        .where(WebSearchLog.created_at >= month_start)
    )
    web_urls_q = await db.execute(
        select(func.coalesce(func.sum(WebSearchLog.urls_fetched), 0))
        .where(WebSearchLog.created_at >= month_start)
    )
    web_matches_q = await db.execute(
        select(func.coalesce(func.sum(WebSearchLog.matches_found), 0))
        .where(WebSearchLog.created_at >= month_start)
    )

    return {
        "orgs_total": orgs_q.scalar() or 0,
        "teachers_total": teachers_q.scalar() or 0,
        "admins_total": admins_q.scalar() or 0,
        "checks_this_month": checks_q.scalar() or 0,
        "flagged_this_month": flagged_q.scalar() or 0,
        "web_queries_this_month": int(web_queries_q.scalar() or 0),
        "web_urls_fetched_this_month": int(web_urls_q.scalar() or 0),
        "web_matches_this_month": int(web_matches_q.scalar() or 0),
    }


# ---------------------------------------------------------------------------
# Организации
# ---------------------------------------------------------------------------


@router.post("/organizations", response_model=OrganizationOut, status_code=201)
async def create_organization(
    data: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(superadmin_only),
):
    org = Organization(**data.model_dump())
    db.add(org)
    await db.flush()  # get ID before commit
    await _log(db, current_user, "create_organization", "organization", org.id, {"name": org.name})
    await db.commit()
    await db.refresh(org)
    return org


@router.get("/organizations", response_model=list[OrganizationOut])
async def list_organizations(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(superadmin_only),
):
    result = await db.execute(select(Organization).order_by(Organization.created_at.desc()))
    return result.scalars().all()


@router.get("/organizations/{org_id}", response_model=OrganizationOut)
async def get_organization(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(superadmin_only),
):
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.patch("/organizations/{org_id}", response_model=OrganizationOut)
async def update_organization(
    org_id: uuid.UUID,
    data: OrganizationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(superadmin_only),
):
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    changes = data.model_dump(exclude_none=True)
    for field, value in changes.items():
        setattr(org, field, value)
    await _log(db, current_user, "update_organization", "organization", org.id, changes)
    await db.commit()
    await db.refresh(org)
    return org


# ---------------------------------------------------------------------------
# Создание school_admin сразу с паролем (логин = email)
# ---------------------------------------------------------------------------


def _gen_password() -> str:
    # Читаемый пароль: 12 символов без неоднозначных
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(12))


class CreateAdminIn(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None


class CredentialsOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    password: str  # показывается один раз


@router.post("/organizations/{org_id}/admins", response_model=CredentialsOut, status_code=201)
async def create_school_admin(
    org_id: uuid.UUID,
    data: CreateAdminIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(superadmin_only),
):
    """Создать админа школы сразу: вернуть email + пароль (показать один раз)."""
    org_result = await db.execute(select(Organization).where(Organization.id == org_id))
    if not org_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Organization not found")

    email = data.email.lower().strip()
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Пользователь с этим email уже есть")

    # Один активный school_admin на школу — если уже есть, не блокируем, но предупреждаем в UI
    raw = _gen_password()
    name = (data.full_name or "").strip() or email.split("@")[0]
    user = User(
        email=email,
        hashed_password=hash_password(raw),
        full_name=name,
        role="school_admin",
        org_id=org_id,
        status="active",
    )
    db.add(user)
    await db.flush()
    await _log(db, current_user, "create_school_admin", "user", user.id, {"email": email, "org_id": str(org_id)})
    await db.commit()
    await db.refresh(user)
    return CredentialsOut(
        id=user.id, email=user.email, full_name=user.full_name, role=user.role, password=raw
    )


@router.post("/users/{user_id}/reset-password", response_model=CredentialsOut)
async def reset_user_password(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(superadmin_only),
):
    """Перевыпустить пароль school_admin / teacher (показывается один раз)."""
    user = await db.get(User, user_id)
    if not user or user.role not in ("school_admin", "teacher"):
        raise HTTPException(status_code=404, detail="User not found")
    raw = _gen_password()
    user.hashed_password = hash_password(raw)
    await _log(db, current_user, "reset_password", "user", user.id, {"email": user.email})
    await db.commit()
    return CredentialsOut(
        id=user.id, email=user.email, full_name=user.full_name, role=user.role, password=raw
    )


# ---------------------------------------------------------------------------
# Приглашения (ссылка — опциональный старый путь)
# ---------------------------------------------------------------------------


@router.post("/invitations", response_model=InvitationOut, status_code=201)
async def invite_school_admin(
    data: InvitationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(superadmin_only),
):
    if data.role != "school_admin":
        raise HTTPException(status_code=400, detail="superadmin can only invite school_admin here")
    if not data.org_id:
        raise HTTPException(status_code=422, detail="org_id is required")

    org_result = await db.execute(select(Organization).where(Organization.id == data.org_id))
    if not org_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Organization not found")

    existing_user = await db.execute(select(User).where(User.email == data.email))
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Пользователь с этим email уже зарегистрирован — используйте «Создать админа» / «Войти как»",
        )

    dup = await db.execute(
        select(Invitation).where(
            Invitation.email == data.email,
            Invitation.org_id == data.org_id,
            Invitation.status == "pending",
        )
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Pending invitation already exists for this email")

    invitation = Invitation(
        email=data.email,
        org_id=data.org_id,
        invited_by=current_user.id,
        role="school_admin",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)

    await send_invitation_email(
        to_email=data.email,
        role="school_admin",
        invite_url=f"{settings.FRONTEND_URL}/invite/{invitation.token}",
    )

    return invitation


# ---------------------------------------------------------------------------
# Пользователи
# ---------------------------------------------------------------------------


@router.get("/users", response_model=list[UserOut])
async def list_all_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(superadmin_only),
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Споры (disputes)
# ---------------------------------------------------------------------------

class DisputeAdminOut(BaseModel):
    id: uuid.UUID
    check_id: uuid.UUID
    submitted_by: uuid.UUID
    comment: str
    status: str
    verdict: Optional[str]
    created_at: datetime
    resolved_at: Optional[datetime]

    model_config = {"from_attributes": True}


class DisputeVerdict(BaseModel):
    verdict: str  # human_written | keep_ai | added_to_dataset


@router.get("/disputes", response_model=list[DisputeAdminOut])
async def list_disputes(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(superadmin_only),
):
    """Список всех споров. Опциональный фильтр по status=pending|reviewed."""
    q = select(Dispute).order_by(Dispute.created_at.desc())
    if status:
        q = q.where(Dispute.status == status)
    result = await db.execute(q)
    return result.scalars().all()


@router.patch("/disputes/{dispute_id}", response_model=DisputeAdminOut)
async def resolve_dispute(
    dispute_id: uuid.UUID,
    data: DisputeVerdict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(superadmin_only),
):
    """Вынести вердикт по спору."""
    allowed = {"human_written", "keep_ai", "added_to_dataset"}
    if data.verdict not in allowed:
        raise HTTPException(status_code=400, detail=f"verdict must be one of: {allowed}")

    result = await db.execute(select(Dispute).where(Dispute.id == dispute_id))
    dispute = result.scalar_one_or_none()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")

    dispute.verdict = data.verdict
    dispute.status = "reviewed"
    dispute.resolved_at = datetime.now(timezone.utc)
    dispute.resolved_by = current_user.id

    # Если вердикт added_to_dataset — создать запись в датасете
    if data.verdict == "added_to_dataset":
        # Получаем нормализованный текст проверки
        doc_q = await db.execute(
            select(CheckDocument).where(CheckDocument.check_id == dispute.check_id)
        )
        doc = doc_q.scalar_one_or_none()
        if doc:
            text_hash = hashlib.sha256(doc.normalized_text.encode()).hexdigest()
            # Проверяем на дубль
            dup = await db.execute(
                select(DatasetEntry).where(DatasetEntry.text_hash == text_hash)
            )
            if not dup.scalar_one_or_none():
                # Определяем метку: если ИИ ошибся → human_written, иначе → ai_generated
                label = "human_written"  # при added_to_dataset судьёй означает: это реальный человек
                db.add(DatasetEntry(
                    dispute_id=dispute.id,
                    check_id=dispute.check_id,
                    label=label,
                    text_hash=text_hash,
                    created_by=current_user.id,
                ))

    await _log(db, current_user, "resolve_dispute", "dispute", dispute.id,
               {"verdict": data.verdict, "check_id": str(dispute.check_id)})
    await db.commit()
    await db.refresh(dispute)
    return dispute


# ---------------------------------------------------------------------------
# Версии моделей (model_versions)
# ---------------------------------------------------------------------------

class ModelVersionOut(BaseModel):
    id: uuid.UUID
    model_type: str
    version: str
    description: Optional[str]
    is_active: bool
    metrics: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class ModelVersionCreate(BaseModel):
    model_type: str         # ai_detector | mt_detector
    version: str
    description: Optional[str] = None
    metrics: dict = {}


@router.get("/model-versions", response_model=list[ModelVersionOut])
async def list_model_versions(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(superadmin_only),
):
    result = await db.execute(
        select(ModelVersion).order_by(ModelVersion.created_at.desc())
    )
    return result.scalars().all()


@router.post("/model-versions", response_model=ModelVersionOut, status_code=201)
async def create_model_version(
    data: ModelVersionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(superadmin_only),
):
    if data.model_type not in {"ai_detector", "mt_detector"}:
        raise HTTPException(status_code=400, detail="model_type must be ai_detector or mt_detector")
    mv = ModelVersion(
        model_type=data.model_type,
        version=data.version,
        description=data.description,
        metrics=data.metrics,
        is_active=False,
        created_by=current_user.id,
    )
    db.add(mv)
    await db.commit()
    await db.refresh(mv)
    return mv


@router.patch("/model-versions/{version_id}/activate", response_model=ModelVersionOut)
async def activate_model_version(
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(superadmin_only),
):
    """Деактивировать все версии того же типа, активировать указанную."""
    result = await db.execute(select(ModelVersion).where(ModelVersion.id == version_id))
    mv = result.scalar_one_or_none()
    if not mv:
        raise HTTPException(status_code=404, detail="ModelVersion not found")

    # Деактивируем все версии того же типа
    all_q = await db.execute(
        select(ModelVersion).where(
            ModelVersion.model_type == mv.model_type,
            ModelVersion.is_active.is_(True),
        )
    )
    for other in all_q.scalars().all():
        other.is_active = False

    mv.is_active = True
    await _log(db, current_user, "activate_model_version", "model_version", mv.id,
               {"version": mv.version, "model_type": mv.model_type})
    await db.commit()
    await db.refresh(mv)
    return mv


# ---------------------------------------------------------------------------
# Датасет (dataset_entries)
# ---------------------------------------------------------------------------

class DatasetEntryOut(BaseModel):
    id: uuid.UUID
    check_id: uuid.UUID
    label: str
    text_hash: str
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/dataset", response_model=list[DatasetEntryOut])
async def list_dataset_entries(
    skip: int = 0,
    limit: int = 100,
    label: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(superadmin_only),
):
    """Список записей обучающего датасета."""
    q = select(DatasetEntry).order_by(DatasetEntry.created_at.desc()).offset(skip).limit(limit)
    if label:
        q = q.where(DatasetEntry.label == label)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/dataset/stats")
async def dataset_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(superadmin_only),
):
    """Статистика датасета по меткам."""
    result = await db.execute(
        select(DatasetEntry.label, func.count().label("count"))
        .group_by(DatasetEntry.label)
    )
    rows = result.all()
    return {r.label: r.count for r in rows}


# ---------------------------------------------------------------------------
# Репозиторий работ
# ---------------------------------------------------------------------------

class RepositoryDocOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    check_id: uuid.UUID
    work_title: Optional[str]
    student_name: Optional[str]
    group_name: Optional[str]
    word_count: Optional[int]
    language: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/repository", response_model=list[RepositoryDocOut])
async def list_repository(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(superadmin_only),
):
    """Список всех работ в репозиториях (суперадмин видит все организации)."""
    result = await db.execute(
        select(RepositoryDocument)
        .order_by(RepositoryDocument.created_at.desc())
        .offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.get("/repository/stats")
async def repository_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(superadmin_only),
):
    total_q = await db.execute(select(func.count()).select_from(RepositoryDocument))
    return {"total": total_q.scalar() or 0}


# ---------------------------------------------------------------------------
# Аудит-лог
# ---------------------------------------------------------------------------

class AuditLogOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    action: str
    resource_type: str
    resource_id: Optional[uuid.UUID]
    details: dict
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/audit-log", response_model=list[AuditLogOut])
async def get_audit_log(
    skip: int = 0,
    limit: int = 100,
    action: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(superadmin_only),
):
    """Журнал действий суперадмина."""
    q = select(AuditLog).order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
    if action:
        q = q.where(AuditLog.action == action)
    result = await db.execute(q)
    return result.scalars().all()


# ---------------------------------------------------------------------------
# API request log
# ---------------------------------------------------------------------------


class ApiLogEntryOut(BaseModel):
    id: uuid.UUID
    org_name: Optional[str]
    key_prefix: Optional[str]
    method: str
    path: str
    status_code: int
    response_ms: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/api-log", response_model=list[ApiLogEntryOut])
async def get_api_request_log(
    skip: int = 0,
    limit: int = 200,
    org_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(superadmin_only),
):
    """Журнал запросов через API-ключи школ."""
    q = (
        select(ApiRequestLog, Organization.name.label("org_name"), ApiKey.key_prefix.label("key_prefix"))
        .outerjoin(Organization, Organization.id == ApiRequestLog.org_id)
        .outerjoin(ApiKey, ApiKey.id == ApiRequestLog.api_key_id)
        .order_by(ApiRequestLog.created_at.desc())
        .offset(skip).limit(limit)
    )
    if org_id:
        q = q.where(ApiRequestLog.org_id == org_id)
    result = await db.execute(q)
    rows = result.all()
    out = []
    for log, org_name, key_prefix in rows:
        out.append(ApiLogEntryOut(
            id=log.id,
            org_name=org_name,
            key_prefix=key_prefix,
            method=log.method,
            path=log.path,
            status_code=log.status_code,
            response_ms=log.response_ms,
            created_at=log.created_at,
        ))
    return out


@router.get("/api-log/stats")
async def api_log_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(superadmin_only),
):
    """Агрегированная статистика API-запросов за сегодня."""
    from datetime import date
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    total_q = await db.execute(
        select(func.count()).select_from(ApiRequestLog)
        .where(ApiRequestLog.created_at >= today_start)
    )
    errors_q = await db.execute(
        select(func.count()).select_from(ApiRequestLog)
        .where(ApiRequestLog.created_at >= today_start, ApiRequestLog.status_code >= 400)
    )
    limit_q = await db.execute(
        select(func.count()).select_from(ApiRequestLog)
        .where(ApiRequestLog.created_at >= today_start, ApiRequestLog.status_code == 429)
    )
    avg_ms_q = await db.execute(
        select(func.avg(ApiRequestLog.response_ms))
        .where(ApiRequestLog.created_at >= today_start, ApiRequestLog.response_ms.isnot(None))
    )
    return {
        "requests_today": total_q.scalar() or 0,
        "errors_today": errors_q.scalar() or 0,
        "limit_hits_today": limit_q.scalar() or 0,
        "avg_response_ms": int(avg_ms_q.scalar() or 0),
    }


# ---------------------------------------------------------------------------
# Имперсонация (войти как school_admin)
# ---------------------------------------------------------------------------


class ImpersonateOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    target_email: str
    target_name: str


@router.post("/impersonate/{user_id}", response_model=ImpersonateOut)
async def impersonate_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(superadmin_only),
):
    """Войти как school_admin — генерирует токен от его имени. Записывается в audit log."""
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.role not in ("school_admin", "teacher"):
        raise HTTPException(status_code=400, detail="Can only impersonate school_admin or teacher")
    if target.status != "active":
        raise HTTPException(status_code=400, detail="Target user is inactive")

    token = create_access_token({
        "sub": str(target.id),
        "impersonated_by": str(current_user.id),
    })
    await _log(db, current_user, "impersonate", "user", target.id,
               {"target_email": target.email, "target_name": target.full_name})
    await db.commit()
    return ImpersonateOut(
        access_token=token,
        target_email=target.email,
        target_name=target.full_name,
    )


# ---------------------------------------------------------------------------
# Состояние системы (health check)
# ---------------------------------------------------------------------------


@router.get("/status")
async def system_status(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(superadmin_only),
):
    """Проверка доступности всех компонентов системы."""
    services = []

    # 1. API (self)
    services.append({
        "name": "API (FastAPI)",
        "status": "ok",
        "latency": "1мс",
        "detail": "v1.0.0",
    })

    # 2. PostgreSQL
    t0 = time.monotonic()
    try:
        await db.execute(text("SELECT 1"))
        pg_ms = int((time.monotonic() - t0) * 1000)
        services.append({
            "name": "База данных (PostgreSQL)",
            "status": "ok",
            "latency": f"{pg_ms}мс",
            "detail": "Подключение активно",
        })
    except Exception as exc:
        services.append({
            "name": "База данных (PostgreSQL)",
            "status": "error",
            "detail": str(exc)[:100],
        })

    # 3. OpenSearch
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get("http://localhost:9200/_cluster/health")
            os_ms = int((time.monotonic() - t0) * 1000)
            if r.status_code == 200:
                h = r.json()
                try:
                    r2 = await client.get("http://localhost:9200/_cat/count?format=json")
                    doc_count = r2.json()[0].get("count", "?") if r2.status_code == 200 else "?"
                except Exception:
                    doc_count = "?"
                stat = h.get("status", "unknown")
                services.append({
                    "name": "OpenSearch",
                    "status": "ok" if stat in ("green", "yellow") else "error",
                    "latency": f"{os_ms}мс",
                    "detail": f"Статус: {stat} · {doc_count} документов",
                })
            else:
                services.append({
                    "name": "OpenSearch",
                    "status": "error",
                    "detail": f"HTTP {r.status_code}",
                })
    except Exception:
        services.append({
            "name": "OpenSearch",
            "status": "warn",
            "detail": "Недоступен",
        })

    # 4. Qdrant
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{settings.QDRANT_URL}/collections")
            q_ms = int((time.monotonic() - t0) * 1000)
            if r.status_code == 200:
                colls = r.json().get("result", {}).get("collections", [])
                services.append({
                    "name": "Qdrant (эмбеддинги)",
                    "status": "ok",
                    "latency": f"{q_ms}мс",
                    "detail": f"{len(colls)} коллекций",
                })
            else:
                services.append({
                    "name": "Qdrant (эмбеддинги)",
                    "status": "warn",
                    "detail": f"HTTP {r.status_code}",
                })
    except Exception:
        services.append({
            "name": "Qdrant (эмбеддинги)",
            "status": "warn",
            "detail": "Не настроен · нужен для семантического поиска",
        })

    # 5. Storage
    try:
        upload_dir = settings.UPLOAD_DIR
        os.makedirs(upload_dir, exist_ok=True)
        usage = shutil.disk_usage(upload_dir)
        used_gb = usage.used / (1024 ** 3)
        total_gb = usage.total / (1024 ** 3)
        file_count = sum(1 for p in Path(upload_dir).rglob("*") if p.is_file())
        services.append({
            "name": "Хранилище файлов",
            "status": "ok",
            "detail": f"{used_gb:.1f}ГБ / {total_gb:.0f}ГБ · {file_count} файлов",
        })
    except Exception as exc:
        services.append({
            "name": "Хранилище файлов",
            "status": "warn",
            "detail": str(exc)[:100],
        })

    # 6. Worker queue depth
    try:
        pending_q = await db.execute(select(func.count()).where(Check.status == "pending"))
        processing_q = await db.execute(select(func.count()).where(Check.status == "processing"))
        pending = pending_q.scalar() or 0
        processing = processing_q.scalar() or 0
        services.append({
            "name": "Worker (проверки)",
            "status": "ok",
            "detail": f"В очереди: {pending} · Обрабатывается: {processing}",
        })
    except Exception:
        services.append({
            "name": "Worker (проверки)",
            "status": "warn",
            "detail": "Нет данных",
        })

    # 7. Brave Search (без live-запроса — status поллится каждые 30с)
    if not settings.WEB_SEARCH_ENABLED:
        services.append({
            "name": "Brave Search",
            "status": "warn",
            "detail": "Выключен (WEB_SEARCH_ENABLED=false)",
        })
    elif not settings.BRAVE_API_KEY.strip():
        services.append({
            "name": "Brave Search",
            "status": "warn",
            "detail": "Не настроен · нужен BRAVE_API_KEY · smoke: python scripts/smoke_brave.py",
        })
    else:
        services.append({
            "name": "Brave Search",
            "status": "ok",
            "detail": "Ключ задан · smoke: python scripts/smoke_brave.py",
        })

    # 8. DocMaxxing EN AI (конфиг; live-probe не на каждый poll)
    from app.services.en_ai_detector import is_configured
    if not settings.DOCMAXXING_AI_ENABLED:
        services.append({
            "name": "DocMaxxing AI (EN)",
            "status": "warn",
            "detail": "Выключен (DOCMAXXING_AI_ENABLED=false)",
        })
    elif not is_configured():
        services.append({
            "name": "DocMaxxing AI (EN)",
            "status": "warn",
            "detail": "Не настроен · DOCMAXXING_AI_URL + DOCMAXXING_AI_KEY",
        })
    else:
        services.append({
            "name": "DocMaxxing AI (EN)",
            "status": "ok",
            "detail": settings.DOCMAXXING_AI_URL.strip().rstrip("/"),
        })

    # 9. Local AI ONNX (RU/UZ)
    model_dir = (settings.AI_MODEL_DIR or "").strip()
    if not model_dir:
        services.append({
            "name": "AI ONNX (RU/UZ)",
            "status": "warn",
            "detail": "AI_MODEL_DIR пуст · heuristic fallback",
        })
    else:
        onnx_path = Path(model_dir) / "model.onnx"
        if onnx_path.is_file():
            services.append({
                "name": "AI ONNX (RU/UZ)",
                "status": "ok",
                "detail": str(onnx_path),
            })
        else:
            services.append({
                "name": "AI ONNX (RU/UZ)",
                "status": "warn",
                "detail": f"Нет model.onnx в {model_dir}",
            })

    return {
        "services": services,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Flagged — проверки с попытками обхода
# ---------------------------------------------------------------------------

_SEV_ORDER = {"high": 3, "medium": 2, "low": 1}


@router.get("/flagged")
async def list_flagged(
    skip: int = 0,
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(superadmin_only),
):
    """Список всех проверок с флагами (попытки обхода) по всем организациям."""
    # Distinct check IDs with flags, ordered by most recent
    flagged_ids_q = await db.execute(
        select(func.distinct(CheckFlag.check_id))
    )
    all_flagged_ids = flagged_ids_q.scalars().all()
    if not all_flagged_ids:
        return []

    # Paginate on check level
    checks_q = await db.execute(
        select(Check, User.email.label("teacher_email"), Organization.name.label("org_name"))
        .outerjoin(User, User.id == Check.submitted_by)
        .outerjoin(Organization, Organization.id == Check.org_id)
        .where(Check.id.in_(all_flagged_ids))
        .order_by(Check.created_at.desc())
        .offset(skip).limit(limit)
    )
    checks_rows = checks_q.all()

    if not checks_rows:
        return []

    page_ids = [row[0].id for row in checks_rows]

    flags_q = await db.execute(
        select(CheckFlag).where(CheckFlag.check_id.in_(page_ids))
    )
    all_flags = flags_q.scalars().all()

    flags_by_check: dict[str, list] = {}
    for flag in all_flags:
        key = str(flag.check_id)
        flags_by_check.setdefault(key, []).append(flag)

    out = []
    for check, teacher_email, org_name in checks_rows:
        check_flags = flags_by_check.get(str(check.id), [])
        flag_types = list({f.type for f in check_flags})
        severity = max(
            (f.severity for f in check_flags),
            key=lambda s: _SEV_ORDER.get(s, 0),
            default="low",
        )
        out.append({
            "id": str(check.id),
            "work_title": check.work_title or check.filename,
            "student_name": check.student_name,
            "org_name": org_name,
            "teacher_email": teacher_email,
            "flags": flag_types,
            "severity": severity,
            "created_at": check.created_at.isoformat(),
        })
    return out


@router.get("/flagged/stats")
async def flagged_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(superadmin_only),
):
    """Агрегированная статистика flagged за текущий месяц."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_q = await db.execute(
        select(func.count(func.distinct(CheckFlag.check_id)))
        .join(Check, Check.id == CheckFlag.check_id)
        .where(Check.created_at >= month_start)
    )
    high_q = await db.execute(
        select(func.count(func.distinct(CheckFlag.check_id)))
        .join(Check, Check.id == CheckFlag.check_id)
        .where(Check.created_at >= month_start, CheckFlag.severity == "high")
    )
    orgs_q = await db.execute(
        select(func.count(func.distinct(Check.org_id)))
        .join(CheckFlag, CheckFlag.check_id == Check.id)
        .where(Check.created_at >= month_start)
    )
    return {
        "flagged_this_month": total_q.scalar() or 0,
        "high_severity_this_month": high_q.scalar() or 0,
        "orgs_with_flagged": orgs_q.scalar() or 0,
    }


# ---------------------------------------------------------------------------
# Вспомогательная функция логирования (используется в этом модуле)
# ---------------------------------------------------------------------------

async def _log(
    db: AsyncSession,
    user: User,
    action: str,
    resource_type: str,
    resource_id=None,
    details: dict | None = None,
) -> None:
    db.add(AuditLog(
        user_id=user.id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
    ))
