"""
Оркестратор обработки одной проверки.

Порядок обработки:
1. Парсинг файла
2. Flagged-проверки на сыром тексте
3. Нормализация
4. Определение языка
5. Подсчёт слов
6. Антиплагиат (OpenSearch + rapidfuzz)
6b. ИИ-детектор
7. Семантический поиск (Qdrant + BGE-M3)
8. Веб-поиск (Brave Search API)
9. Детектор машинного перевода (heuristic)
10. Стилометрия (сравнение с предыдущими работами)
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.check import Check, CheckDocument, CheckFlag
from app.models.match import CheckMatch
from app.models.mt_segment import MTSegment
from app.models.organization import Organization
from app.models.repository_document import RepositoryDocument
from app.models.web_search_log import WebSearchLog
from app.services.ai_detector import detect_ai
from app.services.flagged import run_flagged_checks
from app.services.language import resolve_language
from app.services.mt_detector import detect_mt
from app.services.normalizer import normalize_text
from app.services.parser import parse_file
from app.services.plagiarism import detect_plagiarism
from app.services.repository import index_to_repository
from app.services.semantic_search import detect_semantic_plagiarism
from app.services.stylometry import compute_stylometry
from app.services.web_search import run_web_search
from app.services.webhook import build_check_payload, fire_webhook


async def process_check(check_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Check).where(Check.id == check_id))
        check = result.scalar_one_or_none()
        if not check:
            return

        try:
            # 1. Парсинг (CPU-bound → выносим в поток)
            parse_result = await asyncio.to_thread(parse_file, check.file_path, check.filename)

            # 2. Flagged-проверки на СЫРОМ тексте
            flags = await asyncio.to_thread(
                run_flagged_checks, parse_result.raw_text, parse_result
            )

            # 3. Нормализация
            normalized = await asyncio.to_thread(normalize_text, parse_result.raw_text)

            # 4. Язык (авто или ручная подсказка ru/uz/en с формы)
            language = await asyncio.to_thread(
                resolve_language, normalized, check.language
            )

            # 5. Слова (простой подсчёт)
            word_count = len(normalized.split())

            # 6. Антиплагиат
            plagiarism_result = await asyncio.to_thread(
                detect_plagiarism, normalized, language
            )

            # 6b. ИИ-детектор (stub-v0 → будет заменён реальной моделью в Stage 7)
            ai_result = await asyncio.to_thread(detect_ai, normalized, language)

            # 7. Семантический поиск (Qdrant + BGE-M3) — paraphrase + cross_lingual
            shingle_covered = {
                i for m in plagiarism_result.matches
                for i in range(m.start_char, m.end_char)
            }
            semantic_matches = await asyncio.to_thread(
                detect_semantic_plagiarism, normalized, language, shingle_covered
            )
            # Объединяем шинглы + семантику
            all_matches = plagiarism_result.matches + semantic_matches
            combined_covered = {
                i for m in all_matches
                for i in range(m.start_char, m.end_char)
            }

            # 8. Веб-поиск (Brave Search API + trafilatura)
            web_result = await asyncio.to_thread(
                run_web_search, normalized, language, combined_covered
            )
            if web_result.matches:
                all_matches = all_matches + web_result.matches

            # 8b. Brave-находки → Postgres корпус (дедуп по content_hash)
            if web_result.corpus_pages:
                import hashlib
                from app.models.corpus import CorpusDocument

                existing_hashes = set(
                    (
                        await db.execute(select(CorpusDocument.content_hash))
                    ).scalars().all()
                )
                for page in web_result.corpus_pages:
                    h = hashlib.sha256(page.text.encode("utf-8")).hexdigest()
                    if h in existing_hashes:
                        continue
                    existing_hashes.add(h)
                    doc_id = uuid.uuid5(uuid.NAMESPACE_URL, page.url)
                    db.add(
                        CorpusDocument(
                            id=doc_id,
                            title=(page.title or page.url)[:500],
                            url=page.url[:1000],
                            language=page.language or language or "other",
                            source_type="web",
                            content_hash=h,
                            content=page.text,
                            word_count=len(page.text.split()),
                            opensearch_id=str(doc_id),
                        )
                    )

            # Финальный пересчёт покрытия
            if all_matches:
                all_covered = {
                    i for m in all_matches
                    for i in range(m.start_char, m.end_char)
                }
                total_chars = len(normalized.strip())
                combined_sim = round(len(all_covered) / total_chars * 100, 2) if total_chars else 0.0
                combined_sources = len({m.source_title for m in all_matches if m.source_title})
            else:
                combined_sim = plagiarism_result.similarity_percent
                combined_sources = plagiarism_result.sources_count

            # 7. Сохраняем документ
            doc = CheckDocument(
                check_id=check_id,
                raw_text=parse_result.raw_text,
                normalized_text=normalized,
                position_map=parse_result.position_map,
            )
            db.add(doc)

            # Сохраняем флаги
            for flag in flags:
                db.add(
                    CheckFlag(
                        check_id=check_id,
                        type=flag.type,
                        severity=flag.severity,
                        count=flag.count,
                        details=flag.details,
                    )
                )

            # Сохраняем совпадения (шинглы + семантика)
            for match in all_matches:
                db.add(
                    CheckMatch(
                        check_id=check_id,
                        corpus_doc_id=match.corpus_doc_id,
                        start_char=match.start_char,
                        end_char=match.end_char,
                        matched_text=match.matched_text,
                        source_title=match.source_title,
                        source_url=match.source_url,
                        source_lang=match.source_lang,
                        match_kind=match.match_kind,
                        score=match.score,
                    )
                )

            # 9. Детектор машинного перевода
            mt_result = await asyncio.to_thread(detect_mt, normalized, language)

            # 10. Стилометрия — сравниваем с предыдущими работами того же автора
            prev_texts_q = await db.execute(
                select(CheckDocument.normalized_text)
                .join(Check, Check.id == CheckDocument.check_id)
                .where(
                    Check.submitted_by == check.submitted_by,
                    Check.id != check_id,
                    Check.status == "done",
                )
                .order_by(Check.completed_at.desc())
                .limit(5)
            )
            prev_texts = list(prev_texts_q.scalars().all())
            stylometry_result = await asyncio.to_thread(compute_stylometry, normalized, prev_texts)

            # Сохраняем лог веб-поиска (даже если 0 запросов)
            if web_result.queries_count > 0:
                db.add(WebSearchLog(
                    check_id=check_id,
                    org_id=check.org_id,
                    queries_count=web_result.queries_count,
                    urls_fetched=web_result.urls_fetched,
                    matches_found=web_result.matches_found,
                ))

            # Сохраняем сегменты машинного перевода
            for seg in mt_result.segments:
                db.add(MTSegment(
                    check_id=check_id,
                    start_char=seg.start_char,
                    end_char=seg.end_char,
                    probability=seg.probability,
                    mt_kind=seg.mt_kind,
                ))

            # Обновляем запись проверки
            check.status = "done"
            check.word_count = word_count
            check.language = language
            check.similarity_percent = combined_sim
            check.similarity_sources_count = combined_sources
            check.ai_percent = ai_result.ai_percent
            check.ai_model_version = ai_result.model_version
            check.mt_flag = mt_result.mt_percent >= 15.0
            check.mt_percent = mt_result.mt_percent
            check.stylometry_score = stylometry_result.score
            check.completed_at = datetime.now(timezone.utc)
            await db.commit()

            # Сохранить в репозиторий школы (после коммита, graceful)
            if check.save_to_repository:
                repo_doc_id = str(uuid.uuid5(uuid.NAMESPACE_OID, f"repo:{check_id}"))
                await asyncio.to_thread(
                    index_to_repository,
                    repo_doc_id,
                    str(check.org_id),
                    check.work_title or check.filename,
                    normalized,
                    language,
                )
                # Save repository metadata
                db.add(RepositoryDocument(
                    id=uuid.UUID(repo_doc_id),
                    org_id=check.org_id,
                    check_id=check_id,
                    submitted_by=check.submitted_by,
                    work_title=check.work_title,
                    student_name=check.student_name,
                    group_name=check.group_name,
                    word_count=word_count,
                    language=language,
                ))
                await db.commit()

            await _after_check(check)

        except Exception as exc:
            check.status = "failed"
            check.error_message = str(exc)[:500]
            await db.commit()

            await _after_check(check)


async def _after_check(check: Check) -> None:
    """Fire LMS webhook and push Canvas originality report if linked."""
    secret: str | None = None
    async with AsyncSessionLocal() as db:
        org_q = await db.execute(select(Organization).where(Organization.id == check.org_id))
        org = org_q.scalar_one_or_none()
        if org:
            secret = org.webhook_secret

    if check.webhook_url:
        await fire_webhook(check.webhook_url, build_check_payload(check), secret=secret)

    try:
        from app.services.canvas_report import push_originality_report
        await push_originality_report(check)
    except Exception as exc:  # noqa: BLE001
        print(f"[LTI] Canvas originality report failed for {check.id}: {exc}")
