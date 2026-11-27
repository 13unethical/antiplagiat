"""
Создаёт superadmin + демо-школу + showcase-проверку с высокими %.

Запуск (из папки backend/):
  python seed.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select

from app.core.security import hash_password
from app.database import AsyncSessionLocal
from app.models.check import Check, CheckDocument, CheckFlag
from app.models.match import CheckMatch
from app.models.organization import Organization
from app.models.user import User

SUPERADMIN_EMAIL = "admin@antiplagiat.uz"
SUPERADMIN_PASSWORD = "changeme123"
DEMO_ORG_NAME = "Демо-школа Markly"
SHOWCASE_TITLE = "МСФО и ИИ: демонстрация Markly"

_SHOWCASE_PATH = Path(__file__).parent / "scripts" / "showcase_check.txt"


def _showcase_text() -> str:
    if _SHOWCASE_PATH.exists():
        return _SHOWCASE_PATH.read_text(encoding="utf-8")
    return (
        "Данная работа посвящена анализу внедрения МСФО. Следует отметить актуальность. "
        "Малый и средний бизнес является основой экономики большинства стран. "
        "В Узбекистане улучшение финансовой отчётности является приоритетом. "
        "Искусственный интеллект постепенно меняет сферу образования. "
        "Институциональная теория объясняет, как законы, профессиональные привычки "
        "и отраслевые нормы заставляют предприятия менять правила учёта. "
        "Цифровизация открывает новые возможности для малого бизнеса. "
        "В заключение можно сказать, что на основании вышеизложенного тема важна."
    )


def _at(text: str, sub: str) -> tuple[int, int]:
    i = text.find(sub)
    if i < 0:
        return 0, min(80, len(text))
    return i, i + len(sub)


async def main():
    async with AsyncSessionLocal() as db:
        admin = (
            await db.execute(select(User).where(User.email == SUPERADMIN_EMAIL))
        ).scalar_one_or_none()
        if not admin:
            admin = User(
                email=SUPERADMIN_EMAIL,
                hashed_password=hash_password(SUPERADMIN_PASSWORD),
                full_name="Super Admin",
                role="superadmin",
                org_id=None,
                status="active",
            )
            db.add(admin)
            await db.flush()
            print(f"Superadmin created: {SUPERADMIN_EMAIL} / {SUPERADMIN_PASSWORD}")
        else:
            print(f"Superadmin already exists: {SUPERADMIN_EMAIL}")

        org = (
            await db.execute(select(Organization).where(Organization.name == DEMO_ORG_NAME))
        ).scalar_one_or_none()
        if not org:
            # fallback to older demo name
            org = (
                await db.execute(select(Organization).where(Organization.name == "Демо-школа"))
            ).scalar_one_or_none()
        if not org:
            org = Organization(name=DEMO_ORG_NAME, seats_limit=10, monthly_quota=500)
            db.add(org)
            await db.flush()
            print(f"Org created: {DEMO_ORG_NAME}")
        if admin.org_id is None:
            admin.org_id = org.id
            await db.flush()

        existing = (
            await db.execute(select(Check).where(Check.work_title == SHOWCASE_TITLE))
        ).scalar_one_or_none()
        if existing:
            print(f"Showcase already exists: https://markly.study/checks/{existing.id}")
            await db.commit()
            return

        text = _showcase_text()
        check_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        spans = [
            ("Малый и средний бизнес является основой экономики большинства стран.", "МСФО для малого и среднего бизнеса: обзор", "https://example.org/ifrs-sme-overview", 0.96),
            ("В Узбекистане улучшение финансовой отчётности является приоритетом", "Внедрение МСФО в Узбекистане", "https://example.org/ifrs-uzbekistan", 0.93),
            ("Искусственный интеллект постепенно меняет сферу образования.", "Искусственный интеллект в образовании", "https://example.org/ai-education", 0.95),
            ("Институциональная теория объясняет, как законы, профессиональные привычки", "Институциональная теория и ресурсный подход", "https://example.org/institutional-rbv", 0.91),
            ("Цифровизация открывает новые возможности для малого бизнеса", "Цифровая экономика и малый бизнес", "https://example.org/digital-economy-sme", 0.89),
        ]

        db.add(
            Check(
                id=check_id,
                org_id=org.id,
                submitted_by=admin.id,
                filename="МСФО_и_ИИ_демонстрация_Markly.txt",
                file_size=len(text.encode("utf-8")),
                file_path=f"seed/{check_id}.txt",
                status="done",
                word_count=len(text.split()),
                language="ru",
                similarity_percent=91.0,
                similarity_sources_count=5,
                ai_percent=93.0,
                ai_model_version="heuristic-v1",
                mt_flag=True,
                mt_percent=28.0,
                stylometry_score=0.81,
                work_title=SHOWCASE_TITLE,
                student_name="Жасур Рахимов",
                student_id="2024-0881",
                group_name="ФК-21",
                exclude_bibliography=True,
                created_at=now,
                completed_at=now,
            )
        )
        db.add(
            CheckDocument(
                check_id=check_id,
                raw_text=text,
                normalized_text=text,
                position_map=[],
            )
        )
        for typ, sev, count, details in [
            ("homoglyph", "high", 7, {"word_count": 7, "examples": [{"word": "инфoрмация"}, {"word": "кoмпании"}]}),
            ("invisible_char", "high", 12, {"count": 12, "kinds": ["zero_width_space", "soft_hyphen"]}),
            ("spaced_text", "medium", 3, {"spans": 3}),
            ("quote_abuse", "medium", 1, {"quoted_percent": 27.0}),
        ]:
            db.add(
                CheckFlag(
                    id=uuid.uuid4(),
                    check_id=check_id,
                    type=typ,
                    severity=sev,
                    count=count,
                    details=details,
                )
            )
        for sub, title, url, score in spans:
            start, end = _at(text, sub)
            end = min(len(text), end + 160)
            db.add(
                CheckMatch(
                    id=uuid.uuid4(),
                    check_id=check_id,
                    start_char=start,
                    end_char=end,
                    matched_text=text[start:end][:500],
                    source_title=title,
                    source_url=url,
                    source_lang="ru",
                    match_kind="exact",
                    score=score,
                )
            )

        await db.commit()
        print(f"Showcase created: https://markly.study/checks/{check_id}")
        print("  similarity=91%  ai=93%  flags=4  matches=5")


if __name__ == "__main__":
    asyncio.run(main())
