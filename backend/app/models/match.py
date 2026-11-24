import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class CheckMatch(Base):
    """Одно найденное совпадение между документом и источником в корпусе."""

    __tablename__ = "check_matches"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    check_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("checks.id"), nullable=False)
    # Может быть NULL если источник — веб-страница вне корпуса (будет в этапе 9)
    corpus_doc_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("corpus_documents.id"), nullable=True
    )
    # Позиции в нормализованном тексте проверяемого документа
    start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, nullable=False)
    # Первые 500 символов совпадающего фрагмента
    matched_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    source_lang: Mapped[str] = mapped_column(String(50), nullable=False, default="ru")
    # exact | paraphrase
    match_kind: Mapped[str] = mapped_column(String(50), nullable=False, default="exact")
    # 0.0 – 1.0
    score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
