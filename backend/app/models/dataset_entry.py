import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class DatasetEntry(Base):
    """Запись в обучающем датасете — создаётся при вердикте 'added_to_dataset' в споре."""
    __tablename__ = "dataset_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dispute_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("disputes.id"), nullable=False)
    check_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("checks.id"), nullable=False)
    # human_written | ai_generated | machine_translated
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    # SHA-256 нормализованного текста — уникальный, защита от дублей
    text_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
