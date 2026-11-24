import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class Check(Base):
    __tablename__ = "checks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    submitted_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    # pending | processing | done | failed
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    word_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # uz-Latn | uz-Cyrl | ru | mixed | other
    language: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # Антиплагиат: % совпавших слов
    similarity_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    similarity_sources_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ai_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ai_model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    mt_flag: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    mt_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stylometry_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Check options
    save_to_repository: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    excluded_sources: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    exclude_quotes: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    exclude_bibliography: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    min_match_words: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    work_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    student_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    student_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    group_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    webhook_url: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class CheckDocument(Base):
    __tablename__ = "check_documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    check_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("checks.id"), nullable=False, unique=True
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    position_map: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CheckFlag(Base):
    __tablename__ = "check_flags"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    check_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("checks.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
