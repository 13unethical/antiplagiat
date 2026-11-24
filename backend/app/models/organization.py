import uuid
from datetime import datetime, date
from typing import Optional

from sqlalchemy import Boolean, String, Integer, Date, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    seats_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    monthly_quota: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    plan: Mapped[str] = mapped_column(String(50), nullable=False, default="standard")
    valid_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Default check settings (school_admin can configure)
    default_exclude_quotes: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    default_exclude_bibliography: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    default_save_to_repository: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default_min_match_words: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    require_student_name: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    require_group: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    report_footer: Mapped[str] = mapped_column(String(255), nullable=False, default="")
