"""
Эндпоинты для school_admin:
  - Список учителей своей организации
  - Статистика мест (seats)
  - Приглашение учителей (с проверкой лимита 10)
  - Включение / отключение учителя
  - API-ключ организации
"""
import asyncio
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import school_admin_only, any_authenticated
from app.config import settings
from app.database import get_db
from app.services.email import send_invitation_email
from app.models.api_key import ApiKey
from app.models.check import Check, CheckFlag
from app.models.invitation import Invitation
from app.models.lti import LtiPlatform, LtiSubmission
from app.models.organization import Organization
from app.models.repository_document import RepositoryDocument
from app.models.user import User
from app.schemas.auth import UserOut
from app.schemas.invitation import InvitationCreate, InvitationOut
from app.services.repository import delete_from_repository

router = APIRouter(prefix="/org", tags=["org"])


async def _get_seat_counts(db: AsyncSession, org_id: uuid.UUID) -> tuple[int, int, int]:
    """Возвращает (active_teachers, pending_invitations, seats_limit)."""
    active_q = await db.execute(
        select(func.count()).where(
            User.org_id == org_id,
            User.role == "teacher",
            User.status == "active",
        )
    )
    active = active_q.scalar() or 0

    pending_q = await db.execute(
        select(func.count()).where(
            Invitation.org_id == org_id,
            Invitation.role == "teacher",
            Invitation.status == "pending",
        )
    )
    pending = pending_q.scalar() or 0

    org_q = await db.execute(select(Organization).where(Organization.id == org_id))
    org = org_q.scalar_one_or_none()
    seats_limit = org.seats_limit if org else 10

    return active, pending, seats_limit


class OrgCheckOut(BaseModel):
    id: uuid.UUID
    filename: str
    work_title: Optional[str]
    student_name: Optional[str]
    group_name: Optional[str]
    status: str
    word_count: Optional[int]
    similarity_percent: Optional[float]
    created_at: datetime
    teacher_email: Optional[str] = None

    model_config = {"from_attributes": True}


@router.get("/checks", response_model=list[OrgCheckOut])
async def list_org_checks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(school_admin_only),
):
    """Все проверки организации с email учителя."""
    result = await db.execute(
        select(Check, User.email.label("teacher_email"))
        .outerjoin(User, User.id == Check.submitted_by)
        .where(Check.org_id == current_user.org_id)
        .order_by(Check.created_at.desc())
    )
    rows = result.all()
    out = []
    for check, teacher_email in rows:
        out.append(OrgCheckOut(
            id=check.id,
            filename=check.filename,
            work_title=check.work_title,
            student_name=check.student_name,
            group_name=check.group_name,
            status=check.status,
            word_count=check.word_count,
            similarity_percent=check.similarity_percent,
            created_at=check.created_at,
            teacher_email=teacher_email,
        ))
    return out


@router.get("/stats")
async def org_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(school_admin_only),
):
    """Статистика организации: места + проверки за текущий месяц."""
    active, pending, seats_limit = await _get_seat_counts(db, current_user.org_id)

    org_q = await db.execute(select(Organization).where(Organization.id == current_user.org_id))
    org = org_q.scalar_one_or_none()
    monthly_quota = org.monthly_quota if org else 1000

    # Проверки за текущий месяц
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    checks_q = await db.execute(
        select(func.count()).where(
            Check.org_id == current_user.org_id,
            Check.created_at >= month_start,
        )
    )
    checks_this_month = checks_q.scalar() or 0

    # Flagged за текущий месяц (кол-во уникальных проверок с флагами)
    flagged_q = await db.execute(
        select(func.count(func.distinct(CheckFlag.check_id)))
        .join(Check, Check.id == CheckFlag.check_id)
        .where(
            Check.org_id == current_user.org_id,
            Check.created_at >= month_start,
        )
    )
    flagged_this_month = flagged_q.scalar() or 0

    return {
        "active": active,
        "pending_invitations": pending,
        "used": active + pending,
        "seats_limit": seats_limit,
        "available": seats_limit - active - pending,
        "monthly_quota": monthly_quota,
        "checks_this_month": checks_this_month,
        "flagged_this_month": flagged_this_month,
    }


@router.get("/teachers/stats")
async def teacher_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(school_admin_only),
):
    active, pending, seats_limit = await _get_seat_counts(db, current_user.org_id)
    return {
        "active": active,
        "pending_invitations": pending,
        "used": active + pending,
        "seats_limit": seats_limit,
        "available": seats_limit - active - pending,
    }


@router.get("/teachers/checks-stats")
async def teacher_checks_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(school_admin_only),
):
    """Количество проверок каждого учителя за текущий месяц."""
    from app.models.check import Check
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(Check.submitted_by, func.count().label("cnt"))
        .join(User, User.id == Check.submitted_by)
        .where(
            User.org_id == current_user.org_id,
            Check.created_at >= month_start,
        )
        .group_by(Check.submitted_by)
    )
    return {str(row.submitted_by): row.cnt for row in result.all()}


@router.get("/repository/stats")
async def org_repository_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(school_admin_only),
):
    """Количество работ в репозитории организации."""
    result = await db.execute(
        select(func.count()).where(RepositoryDocument.org_id == current_user.org_id)
    )
    return {"total": result.scalar() or 0}


@router.get("/teachers", response_model=list[UserOut])
async def list_teachers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(school_admin_only),
):
    result = await db.execute(
        select(User)
        .where(User.org_id == current_user.org_id, User.role == "teacher")
        .order_by(User.created_at.desc())
    )
    return result.scalars().all()


@router.post("/invitations", response_model=InvitationOut, status_code=201)
async def invite_teacher(
    data: InvitationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(school_admin_only),
):
    """Пригласить учителя. Лимит: seats_limit на организацию (по умолчанию 10).
    Отключённые учителя (inactive) место не занимают. Приглашённые — занимают.
    """
    if data.role != "teacher":
        raise HTTPException(status_code=400, detail="school_admin can only invite teachers")

    active, pending, seats_limit = await _get_seat_counts(db, current_user.org_id)
    if active + pending >= seats_limit:
        raise HTTPException(
            status_code=400,
            detail=f"Seats limit reached ({seats_limit}). Deactivate a teacher to free a seat.",
        )

    # Проверяем дубликат приглашения
    dup = await db.execute(
        select(Invitation).where(
            Invitation.email == data.email,
            Invitation.org_id == current_user.org_id,
            Invitation.status == "pending",
        )
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Pending invitation already exists for this email")

    invitation = Invitation(
        email=data.email,
        org_id=current_user.org_id,
        invited_by=current_user.id,
        role="teacher",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)

    await send_invitation_email(
        to_email=data.email,
        role="teacher",
        invite_url=f"{settings.FRONTEND_URL}/invite/{invitation.token}",
    )

    return invitation


# ─── API-ключ организации ─────────────────────────────────────────────────────

class ApiKeyOut(BaseModel):
    id: uuid.UUID
    key_prefix: str
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ApiKeyCreated(ApiKeyOut):
    """Возвращается только при создании/ротации — содержит полный ключ."""
    raw_key: str


@router.get("/api-key", response_model=Optional[ApiKeyOut])
async def get_api_key(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(school_admin_only),
):
    """Информация о текущем API-ключе (без секрета)."""
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.org_id == current_user.org_id, ApiKey.is_active == True)
        .order_by(ApiKey.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


@router.post("/api-key/rotate", response_model=ApiKeyCreated, status_code=201)
async def rotate_api_key(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(school_admin_only),
):
    """Выпустить новый API-ключ, отозвать старый. Секрет показывается один раз."""
    # Деактивируем старые ключи
    old_keys = await db.execute(
        select(ApiKey).where(ApiKey.org_id == current_user.org_id, ApiKey.is_active == True)
    )
    for key in old_keys.scalars().all():
        key.is_active = False

    # Генерируем новый
    raw_key = "sk-" + secrets.token_urlsafe(32)
    key_hash = sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:12] + "..."

    new_key = ApiKey(
        org_id=current_user.org_id,
        key_prefix=key_prefix,
        key_hash=key_hash,
        is_active=True,
        created_by=current_user.id,
    )
    db.add(new_key)
    await db.commit()
    await db.refresh(new_key)

    return ApiKeyCreated(
        id=new_key.id,
        key_prefix=new_key.key_prefix,
        is_active=new_key.is_active,
        created_at=new_key.created_at,
        last_used_at=new_key.last_used_at,
        raw_key=raw_key,
    )


@router.patch("/teachers/{user_id}/quota", response_model=UserOut)
async def set_teacher_quota(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(school_admin_only),
    personal_quota: Optional[int] = None,
):
    """Установить личный месячный лимит учителя (None — без лимита)."""
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.org_id == current_user.org_id,
            User.role == "teacher",
        )
    )
    teacher = result.scalar_one_or_none()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found in your organization")

    if personal_quota is not None and personal_quota < 0:
        raise HTTPException(status_code=400, detail="personal_quota must be >= 0")

    teacher.personal_quota = personal_quota
    await db.commit()
    await db.refresh(teacher)
    return teacher


@router.patch("/teachers/{user_id}/status", response_model=UserOut)
async def set_teacher_status(
    user_id: uuid.UUID,
    status: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(school_admin_only),
):
    if status not in ("active", "inactive"):
        raise HTTPException(status_code=400, detail="status must be 'active' or 'inactive'")

    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.org_id == current_user.org_id,
            User.role == "teacher",
        )
    )
    teacher = result.scalar_one_or_none()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found in your organization")

    teacher.status = status
    await db.commit()
    await db.refresh(teacher)
    return teacher


# ─── Репозиторий работ ────────────────────────────────────────────────────────

class OrgRepositoryDocOut(BaseModel):
    id: uuid.UUID
    check_id: uuid.UUID
    work_title: Optional[str]
    student_name: Optional[str]
    group_name: Optional[str]
    word_count: Optional[int]
    language: Optional[str]
    similarity_percent: Optional[float]
    created_at: datetime
    teacher_email: Optional[str] = None

    model_config = {"from_attributes": True}


@router.get("/repository", response_model=list[OrgRepositoryDocOut])
async def list_org_repository(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(school_admin_only),
):
    """Список работ в репозитории своей организации."""
    result = await db.execute(
        select(RepositoryDocument, User.email, Check.similarity_percent)
        .outerjoin(User, User.id == RepositoryDocument.submitted_by)
        .outerjoin(Check, Check.id == RepositoryDocument.check_id)
        .where(RepositoryDocument.org_id == current_user.org_id)
        .order_by(RepositoryDocument.created_at.desc())
        .offset(skip).limit(limit)
    )
    rows = result.all()
    out = []
    for doc, teacher_email, sim in rows:
        out.append(OrgRepositoryDocOut(
            id=doc.id,
            check_id=doc.check_id,
            work_title=doc.work_title,
            student_name=doc.student_name,
            group_name=doc.group_name,
            word_count=doc.word_count,
            language=doc.language,
            similarity_percent=sim,
            created_at=doc.created_at,
            teacher_email=teacher_email,
        ))
    return out


@router.delete("/repository/{doc_id}", status_code=204)
async def delete_from_org_repository(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(school_admin_only),
):
    """Удалить работу из репозитория (OpenSearch + Qdrant + БД)."""
    result = await db.execute(
        select(RepositoryDocument).where(
            RepositoryDocument.id == doc_id,
            RepositoryDocument.org_id == current_user.org_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    await asyncio.to_thread(delete_from_repository, str(doc_id))
    await db.delete(doc)
    await db.commit()
    return Response(status_code=204)


# ─── Настройки организации ────────────────────────────────────────────────────

class OrgSettingsOut(BaseModel):
    default_exclude_quotes: bool
    default_exclude_bibliography: bool
    default_save_to_repository: bool
    default_min_match_words: int
    require_student_name: bool
    require_group: bool
    report_footer: str

    model_config = {"from_attributes": True}


class OrgSettingsUpdate(BaseModel):
    default_exclude_quotes: Optional[bool] = None
    default_exclude_bibliography: Optional[bool] = None
    default_save_to_repository: Optional[bool] = None
    default_min_match_words: Optional[int] = None
    require_student_name: Optional[bool] = None
    require_group: Optional[bool] = None
    report_footer: Optional[str] = None


@router.get("/settings", response_model=OrgSettingsOut)
async def get_org_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(any_authenticated),
):
    """Настройки по умолчанию организации (доступно учителям для заполнения формы проверки)."""
    if not current_user.org_id:
        raise HTTPException(status_code=403, detail="User has no organization")
    org_q = await db.execute(select(Organization).where(Organization.id == current_user.org_id))
    org = org_q.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.patch("/settings", response_model=OrgSettingsOut)
async def update_org_settings(
    data: OrgSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(school_admin_only),
):
    """Обновить настройки по умолчанию организации."""
    org_q = await db.execute(select(Organization).where(Organization.id == current_user.org_id))
    org = org_q.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    for field, val in data.model_dump(exclude_none=True).items():
        setattr(org, field, val)
    await db.commit()
    await db.refresh(org)
    return org


# ─── LMS integrations (Moodle / Canvas / webhook secret) ──────────────────────

class WebhookSecretOut(BaseModel):
    webhook_secret: Optional[str] = None
    has_secret: bool = False


class WebhookSecretCreated(BaseModel):
    webhook_secret: str


class LtiPlatformOut(BaseModel):
    id: uuid.UUID
    name: str
    platform_type: str
    issuer: str
    client_id: str
    deployment_ids: list
    jwks_url: Optional[str] = None
    auth_login_url: Optional[str] = None
    auth_token_url: Optional[str] = None
    api_base_url: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class LtiPlatformCreate(BaseModel):
    name: str
    platform_type: str = "canvas"  # canvas | moodle | generic
    issuer: str
    client_id: str
    deployment_ids: list[str] = []
    jwks_url: Optional[str] = None
    auth_login_url: Optional[str] = None
    auth_token_url: Optional[str] = None
    api_base_url: Optional[str] = None


class LtiSubmissionOut(BaseModel):
    id: uuid.UUID
    platform_id: uuid.UUID
    check_id: Optional[uuid.UUID] = None
    external_assignment_id: str
    external_submission_id: str
    student_lms_id: Optional[str] = None
    student_name: Optional[str] = None
    report_status: str
    error_message: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class IntegrationsOverview(BaseModel):
    api_public_url: str
    frontend_url: str
    jwks_url: str
    oidc_login_url: str
    launch_url: str
    canvas_config_url: str
    webhook_secret_set: bool
    has_api_key: bool
    platforms: list[LtiPlatformOut]
    recent_submissions: list[LtiSubmissionOut]


@router.get("/integrations", response_model=IntegrationsOverview)
async def get_integrations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(school_admin_only),
):
    org_q = await db.execute(select(Organization).where(Organization.id == current_user.org_id))
    org = org_q.scalar_one()

    key_q = await db.execute(
        select(ApiKey)
        .where(ApiKey.org_id == current_user.org_id, ApiKey.is_active == True)  # noqa: E712
        .limit(1)
    )
    platforms_q = await db.execute(
        select(LtiPlatform)
        .where(LtiPlatform.org_id == current_user.org_id)
        .order_by(LtiPlatform.created_at.desc())
    )
    platforms = platforms_q.scalars().all()

    platform_ids = [p.id for p in platforms]
    recent: list[LtiSubmission] = []
    if platform_ids:
        sub_q = await db.execute(
            select(LtiSubmission)
            .where(LtiSubmission.platform_id.in_(platform_ids))
            .order_by(LtiSubmission.created_at.desc())
            .limit(20)
        )
        recent = list(sub_q.scalars().all())

    base = settings.API_PUBLIC_URL.rstrip("/")
    return IntegrationsOverview(
        api_public_url=base,
        frontend_url=settings.FRONTEND_URL.rstrip("/"),
        jwks_url=f"{base}/.well-known/jwks.json",
        oidc_login_url=f"{base}/api/v1/lti/oidc/login",
        launch_url=f"{base}/api/v1/lti/launch",
        canvas_config_url=f"{base}/api/v1/lti/config/canvas.json",
        webhook_secret_set=bool(org.webhook_secret),
        has_api_key=key_q.scalar_one_or_none() is not None,
        platforms=platforms,
        recent_submissions=recent,
    )


@router.get("/integrations/webhook-secret", response_model=WebhookSecretOut)
async def get_webhook_secret_meta(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(school_admin_only),
):
    org_q = await db.execute(select(Organization).where(Organization.id == current_user.org_id))
    org = org_q.scalar_one()
    # Secret is shown only right after rotation; meta endpoint never returns it again.
    return WebhookSecretOut(webhook_secret=None, has_secret=bool(org.webhook_secret))


@router.post("/integrations/webhook-secret/rotate", response_model=WebhookSecretCreated, status_code=201)
async def rotate_webhook_secret(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(school_admin_only),
):
    org_q = await db.execute(select(Organization).where(Organization.id == current_user.org_id))
    org = org_q.scalar_one()
    secret = "whsec_" + secrets.token_urlsafe(32)
    org.webhook_secret = secret
    await db.commit()
    return WebhookSecretCreated(webhook_secret=secret)


@router.get("/integrations/platforms", response_model=list[LtiPlatformOut])
async def list_lti_platforms(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(school_admin_only),
):
    result = await db.execute(
        select(LtiPlatform)
        .where(LtiPlatform.org_id == current_user.org_id)
        .order_by(LtiPlatform.created_at.desc())
    )
    return result.scalars().all()


@router.post("/integrations/platforms", response_model=LtiPlatformOut, status_code=201)
async def create_lti_platform(
    data: LtiPlatformCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(school_admin_only),
):
    if data.platform_type not in ("canvas", "moodle", "generic"):
        raise HTTPException(400, "platform_type must be canvas, moodle, or generic")
    platform = LtiPlatform(
        id=uuid.uuid4(),
        org_id=current_user.org_id,
        name=data.name.strip(),
        platform_type=data.platform_type,
        issuer=data.issuer.strip(),
        client_id=data.client_id.strip(),
        deployment_ids=data.deployment_ids or [],
        jwks_url=data.jwks_url,
        auth_login_url=data.auth_login_url,
        auth_token_url=data.auth_token_url,
        api_base_url=data.api_base_url,
    )
    db.add(platform)
    await db.commit()
    await db.refresh(platform)
    return platform


@router.delete("/integrations/platforms/{platform_id}", status_code=204)
async def delete_lti_platform(
    platform_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(school_admin_only),
):
    platform = await db.get(LtiPlatform, platform_id)
    if not platform or platform.org_id != current_user.org_id:
        raise HTTPException(404, "Platform not found")
    await db.delete(platform)
    await db.commit()
    return Response(status_code=204)


@router.get("/integrations/submissions", response_model=list[LtiSubmissionOut])
async def list_lti_submissions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(school_admin_only),
):
    platforms_q = await db.execute(
        select(LtiPlatform.id).where(LtiPlatform.org_id == current_user.org_id)
    )
    ids = [row[0] for row in platforms_q.all()]
    if not ids:
        return []
    result = await db.execute(
        select(LtiSubmission)
        .where(LtiSubmission.platform_id.in_(ids))
        .order_by(LtiSubmission.created_at.desc())
        .limit(50)
    )
    return result.scalars().all()
