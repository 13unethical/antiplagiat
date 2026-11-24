import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class WebSearchLog(Base):
    __tablename__ = "web_search_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    check_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("checks.id"), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    queries_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    urls_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    matches_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
