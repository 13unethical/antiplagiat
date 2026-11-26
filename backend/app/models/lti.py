import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class LtiPlatform(Base):
    __tablename__ = "lti_platforms"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # canvas | moodle | generic
    platform_type: Mapped[str] = mapped_column(String(50), nullable=False, default="canvas")
    issuer: Mapped[str] = mapped_column(String(500), nullable=False)
    client_id: Mapped[str] = mapped_column(String(255), nullable=False)
    deployment_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    jwks_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    auth_login_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    auth_token_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    api_base_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class LtiSubmission(Base):
    __tablename__ = "lti_submissions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    platform_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lti_platforms.id", ondelete="CASCADE"), nullable=False
    )
    check_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("checks.id", ondelete="SET NULL"), nullable=True
    )
    external_assignment_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_submission_id: Mapped[str] = mapped_column(String(255), nullable=False)
    student_lms_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    student_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # pending | processing | reported | failed
    report_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    canvas_report_url: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
