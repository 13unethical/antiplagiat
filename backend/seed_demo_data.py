#!/usr/bin/env python3
"""Наполнение реальной БД красивыми демо-данными для учителя teacher@test.uz."""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, text
from app.database import AsyncSessionLocal as async_session_maker
from app.models.user import User
from app.models.group import Group, Student
from app.models.check import Check, CheckFlag

NOW = datetime.now(timezone.utc)

GROUPS = {
    "ФК-21": ["Иван Петров", "Мадина Каримова", "Алишер Усмонов"],
    "ФК-22": ["Дильноза Рахимова", "Тимур Саидов"],
    "Информатика 10-А": ["Азиза Юлдашева", "Руслан Ким", "Нигора Абдуллаева"],
}

# (title, student, group, sim%, sources, ai%, flags, words, lang, days_ago, mt_flag, mt%)
CHECKS = [
    ("МСФО для малого бизнеса", "Иван Петров", "ФК-21", 14.0, 3, 78.0, 2, 3735, "ru", 0, True, 11.0),
    ("ИИ в образовании", "Мадина Каримова", "ФК-21", 6.0, 1, 91.0, 1, 1920, "uz-Latn", 1, False, 0.0),
    ("Курсовая работа по экономике", "Алишер Усмонов", "ФК-22", 31.0, 7, 22.0, 0, 5120, "ru", 2, False, 0.0),
    ("Цифровизация МСП в Узбекистане", "Иван Петров", "ФК-21", 12.0, 2, 64.0, 1, 2840, "ru", 3, True, 8.0),
    ("Роль блокчейна в финансах", "Дильноза Рахимова", "ФК-22", 9.0, 2, 11.0, 0, 3100, "ru", 4, False, 0.0),
    ("Mustaqillik va iqtisodiyot", "Азиза Юлдашева", "Информатика 10-А", 7.0, 1, 83.0, 1, 1650, "uz-Latn", 5, False, 0.0),
    ("Анализ рынка труда", "Тимур Саидов", "ФК-22", 22.0, 5, 5.0, 0, 4200, "ru", 6, False, 0.0),
    ("Экология городов Центральной Азии", "Руслан Ким", "Информатика 10-А", 18.0, 4, 47.0, 0, 2300, "ru", 8, False, 0.0),
    ("Банковская система Республики", "Мадина Каримова", "ФК-21", 27.0, 6, 34.0, 1, 3950, "ru", 10, True, 6.0),
    ("Zamonaviy ta'lim texnologiyalari", "Нигора Абдуллаева", "Информатика 10-А", 5.0, 1, 72.0, 0, 1480, "uz-Latn", 12, False, 0.0),
    ("Малый бизнес и налогообложение", "Алишер Усмонов", "ФК-22", 16.0, 3, 19.0, 0, 2760, "ru", 14, False, 0.0),
    ("Инвестиции в стартапы", "Иван Петров", "ФК-21", 11.0, 2, 58.0, 1, 3320, "ru", 16, False, 0.0),
]

FLAG_KINDS = [
    ("homoglyph", "high"),
    ("invisible_chars", "medium"),
    ("hidden_text", "high"),
]


async def main():
    async with async_session_maker() as db:
        teacher = (await db.execute(select(User).where(User.email == "teacher@test.uz"))).scalar_one()
        tid, oid = teacher.id, teacher.org_id
        print("teacher:", teacher.email, "org:", oid)

        # 1. чистим старые проверки учителя (и зависимые строки)
        old_ids = [r[0] for r in (await db.execute(select(Check.id).where(Check.submitted_by == tid))).all()]
        if old_ids:
            for tbl in ("check_flags", "check_documents", "check_matches", "mt_segments",
                        "disputes", "dataset_entries", "repository_documents", "web_search_logs"):
                try:
                    await db.execute(text(f"delete from {tbl} where check_id = any(:ids)"), {"ids": old_ids})
                except Exception as e:
                    print(f"  skip {tbl}: {e}")
            await db.execute(text("delete from checks where submitted_by = :t"), {"t": tid})
            print(f"  удалено старых проверок: {len(old_ids)}")

        # 2. чистим и пересоздаём группы учителя
        old_groups = [r[0] for r in (await db.execute(select(Group.id).where(Group.teacher_id == tid))).all()]
        if old_groups:
            await db.execute(text("delete from students where group_id = any(:ids)"), {"ids": old_groups})
            await db.execute(text("delete from groups where teacher_id = :t"), {"t": tid})
        for gname, students in GROUPS.items():
            g = Group(id=uuid.uuid4(), org_id=oid, teacher_id=tid, name=gname)
            db.add(g)
            await db.flush()
            for sname in students:
                db.add(Student(id=uuid.uuid4(), group_id=g.id, name=sname))
        print(f"  групп создано: {len(GROUPS)}")

        # 3. вставляем красивые проверки
        for (title, student, group, sim, srcs, ai, flags, words, lang, days, mt_flag, mt_pct) in CHECKS:
            created = NOW - timedelta(days=days, hours=2)
            completed = created + timedelta(minutes=1)
            c = Check(
                id=uuid.uuid4(), org_id=oid, submitted_by=tid,
                filename=f"{title}.docx", file_size=words * 6, file_path=f"seed/{uuid.uuid4().hex}.docx",
                status="done", word_count=words, language=lang,
                similarity_percent=sim, similarity_sources_count=srcs,
                ai_percent=ai, ai_model_version="distilbert-ml-onnx-v1",
                mt_flag=mt_flag, mt_percent=mt_pct, stylometry_score=0.3 + (ai / 300),
                work_title=title, student_name=student, group_name=group,
                exclude_bibliography=True, created_at=created, completed_at=completed,
            )
            db.add(c)
            await db.flush()
            for i in range(flags):
                kind, sev = FLAG_KINDS[i % len(FLAG_KINDS)]
                db.add(CheckFlag(id=uuid.uuid4(), check_id=c.id, type=kind, severity=sev,
                                 count=2 + i, details={"examples": []}))
        await db.commit()
        print(f"  проверок вставлено: {len(CHECKS)}")
    print("Готово.")


if __name__ == "__main__":
    asyncio.run(main())
