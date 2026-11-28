"""Insert a completed high-score showcase check for Markly demos."""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ssl as sslmod

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.check import Check, CheckDocument, CheckFlag
from app.models.match import CheckMatch  # noqa: F401
from app.models.user import User

TEXT = Path(__file__).with_name("showcase_check.txt").read_text(encoding="utf-8")


def _at(sub: str) -> tuple[int, int]:
    i = TEXT.find(sub)
    if i < 0:
        return 0, min(80, len(TEXT))
    return i, i + len(sub)


def _async_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    u = urlparse(url)
    q = {k: v for k, v in parse_qsl(u.query) if k not in {"sslmode", "ssl"}}
    return urlunparse(u._replace(query=urlencode(q)))


async def main() -> None:
    raw = os.environ.get("DATABASE_URL", "")
    if not raw:
        raise SystemExit("DATABASE_URL required")
    ssl_ctx = sslmod.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = sslmod.CERT_NONE
    engine = create_async_engine(
        _async_url(raw),
        connect_args={"ssl": ssl_ctx},
    )
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        admin = (
            await db.execute(select(User).where(User.email == "admin@antiplagiat.uz"))
        ).scalar_one()
        if not admin.org_id:
            raise SystemExit("admin has no org_id")

        check_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        spans = [
            ("Малый и средний бизнес является основой экономики большинства стран.", "МСФО для малого и среднего бизнеса: обзор", "https://example.org/ifrs-sme-overview", 0.96),
            ("В Узбекистане улучшение финансовой отчётности является приоритетом", "Внедрение МСФО в Узбекистане", "https://example.org/ifrs-uzbekistan", 0.93),
            ("Искусственный интеллект постепенно меняет сферу образования.", "Искусственный интеллект в образовании", "https://example.org/ai-education", 0.95),
            ("Институциональная теория объясняет, как законы, профессиональные привычки", "Институциональная теория и ресурсный подход", "https://example.org/institutional-rbv", 0.91),
            ("Цифровизация открывает новые возможности для малого бизнеса", "Цифровая экономика и малый бизнес", "https://example.org/digital-economy-sme", 0.89),
        ]

        check = Check(
            id=check_id,
            org_id=admin.org_id,
            submitted_by=admin.id,
            filename="МСФО_и_ИИ_демонстрация_Markly.txt",
            file_size=len(TEXT.encode("utf-8")),
            file_path=f"seed/{check_id}.txt",
            status="done",
            word_count=len(TEXT.split()),
            language="ru",
            similarity_percent=91.0,
            similarity_sources_count=5,
            ai_percent=93.0,
            ai_model_version="heuristic-v1",
            mt_flag=True,
            mt_percent=28.0,
            stylometry_score=0.81,
            work_title="МСФО и ИИ: демонстрация Markly",
            student_name="Жасур Рахимов",
            student_id="2024-0881",
            group_name="ФК-21",
            exclude_bibliography=True,
            created_at=now,
            completed_at=now,
        )
        db.add(check)
        db.add(
            CheckDocument(
                check_id=check_id,
                raw_text=TEXT,
                normalized_text=TEXT,
                position_map={},
            )
        )

        for typ, sev, count, details in [
            ("homoglyph", "high", 7, {"word_count": 7, "examples": [{"word": "инфoрмация"}, {"word": "кoмпании"}]}),
            ("invisible_char", "high", 12, {"count": 12, "kinds": ["zero_width_space", "soft_hyphen"]}),
            ("spaced_text", "medium", 3, {"spans": 3}),
            ("quote_abuse", "medium", 1, {"quoted_percent": 27.0}),
        ]:
            db.add(CheckFlag(id=uuid.uuid4(), check_id=check_id, type=typ, severity=sev, count=count, details=details))

        for sub, title, url, score in spans:
            start, end = _at(sub)
            # extend span a bit for nicer highlight
            end = min(len(TEXT), end + 160)
            db.add(
                CheckMatch(
                    id=uuid.uuid4(),
                    check_id=check_id,
                    start_char=start,
                    end_char=end,
                    matched_text=TEXT[start:end][:500],
                    source_title=title,
                    source_url=url,
                    source_lang="ru",
                    match_kind="exact",
                    score=score,
                )
            )

        await db.commit()
        print(f"OK https://markly.study/checks/{check_id}")
        print(f"sim=91 ai=93 flags=4 matches={len(spans)}")


if __name__ == "__main__":
    asyncio.run(main())
