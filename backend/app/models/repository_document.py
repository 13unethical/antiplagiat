import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class RepositoryDocument(Base):
    """
    Метаданные работы, сохранённой в репозиторий школы.
    Текст хранится в OpenSearch с source_type="repository"
    и source_url="repo://{org_id}/{id}".
    """
    __tablename__ = "repository_documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    check_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("checks.id"), nullable=False, unique=True)
    submitted_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    work_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    student_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    group_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    word_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
