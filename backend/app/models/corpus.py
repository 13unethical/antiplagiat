import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class CorpusDocument(Base):
    """Метаданные документа корпуса. Полный текст хранится в OpenSearch."""

    __tablename__ = "corpus_documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    # uz-Latn | uz-Cyrl | ru | other
    language: Mapped[str] = mapped_column(String(50), nullable=False, default="ru")
    # wiki | web | submitted
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="web")
    # SHA-256 контента для дедупликации
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # ID документа в OpenSearch-индексе (совпадает со str(id))
    opensearch_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
