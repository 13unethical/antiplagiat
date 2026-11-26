"""
Эндпоинты для работы с проверками:
  POST /api/v1/checks                      — загрузить файл, запустить обработку
  GET  /api/v1/checks                      — список проверок
  GET  /api/v1/checks/{id}                 — детали проверки
  GET  /api/v1/checks/{id}/report          — отчёт (format=html|json|text)
"""
import csv
import html as html_lib
import io
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import re

from docx import Document as DocxDocument
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import any_authenticated, get_current_user
from app.config import settings
from app.services.repository import parse_repo_url
from app.database import get_db
from app.models.check import Check, CheckDocument, CheckFlag
from app.models.dispute import Dispute
from app.models.match import CheckMatch
from app.models.mt_segment import MTSegment
from app.models.organization import Organization
from app.models.user import User
from app.schemas.check import CheckDetailOut, CheckOut, FlagOut, MTSegmentOut
from app.schemas.match import MatchOut
from app.services.processor import process_check
from app.services.ai_detector import ai_spans

router = APIRouter(prefix="/checks", tags=["checks"])

ALLOWED_EXTENSIONS = {".docx", ".pdf"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


@router.post("", status_code=201)
async def create_check(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    text_content: Optional[str] = Form(None),
    work_title: Optional[str] = Form(None),
    student_name: Optional[str] = Form(None),
    student_id: Optional[str] = Form(None),
    group_name: Optional[str] = Form(None),
    webhook_url: Optional[str] = Form(None),
    save_to_repository: bool = Form(False),
    exclude_quotes: bool = Form(False),
    exclude_bibliography: bool = Form(True),
    min_match_words: int = Form(8),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(any_authenticated),
):
    """Загрузить файл (.docx или .pdf) ИЛИ вставить текст и запустить обработку в фоне."""
    # Если у пользователя нет организации (например, дефолтный суперадмин),
    # привязываем его к демо-школе, чтобы проверка работала в демо-режиме.
    if not current_user.org_id:
        demo_result = await db.execute(
            select(Organization).where(Organization.name == "Демо-школа")
        )
        demo = demo_result.scalar_one_or_none()
        if not demo:
            demo = Organization(name="Демо-школа")
            db.add(demo)
            await db.flush()
        await db.execute(
            update(User).where(User.id == current_user.id).values(org_id=demo.id)
        )
        await db.commit()
        current_user.org_id = demo.id

    if not file and not text_content:
        raise HTTPException(status_code=400, detail="Provide either 'file' or 'text_content'")
    if file and text_content:
        raise HTTPException(status_code=400, detail="Provide either 'file' or 'text_content', not both")

    # ── Определяем контент ───────────────────────────────────────────────────
    if file:
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{suffix}'. Allowed: .docx, .pdf",
            )
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File too large (max 50 MB)")
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="File is empty")
        filename = file.filename or f"file{suffix}"
    else:
        # Text input path
        text_stripped = (text_content or "").strip()
        if len(text_stripped) < 50:
            raise HTTPException(status_code=400, detail="Text is too short (minimum 50 characters)")
        if len(text_stripped) > 500_000:
            raise HTTPException(status_code=400, detail="Text is too long (max 500,000 characters)")
        content = text_stripped.encode("utf-8")
        filename = work_title.strip()[:60] + ".txt" if work_title else "text_input.txt"

    # ── Проверяем лимиты ─────────────────────────────────────────────────────
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    org_result = await db.execute(select(Organization).where(Organization.id == current_user.org_id))
    org = org_result.scalar_one_or_none()
    if org:
        org_checks_q = await db.execute(
            select(func.count()).where(
                Check.org_id == current_user.org_id,
                Check.created_at >= month_start,
            )
        )
        if (org_checks_q.scalar() or 0) >= org.monthly_quota:
            raise HTTPException(
                status_code=429,
                detail=f"Monthly quota exceeded ({org.monthly_quota} checks/month). Contact your administrator.",
            )

    # Личный лимит учителя
    if current_user.role == "teacher" and current_user.personal_quota:
        teacher_checks_q = await db.execute(
            select(func.count()).where(
                Check.submitted_by == current_user.id,
                Check.created_at >= month_start,
            )
        )
        if (teacher_checks_q.scalar() or 0) >= current_user.personal_quota:
            raise HTTPException(
                status_code=429,
                detail=f"Personal quota exceeded ({current_user.personal_quota} checks/month).",
            )

    check_id = uuid.uuid4()
    upload_dir = Path(settings.UPLOAD_DIR) / str(check_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / filename
    file_path.write_bytes(content)

    check = Check(
        id=check_id,
        org_id=current_user.org_id,
        submitted_by=current_user.id,
        filename=filename,
        file_size=len(content),
        file_path=str(file_path),
        status="processing",
        work_title=work_title,
        student_name=student_name,
        student_id=student_id,
        group_name=group_name,
        webhook_url=webhook_url,
        save_to_repository=save_to_repository,
        exclude_quotes=exclude_quotes,
        exclude_bibliography=exclude_bibliography,
        min_match_words=max(1, min(50, min_match_words)),
    )
    db.add(check)
    await db.commit()

    background_tasks.add_task(process_check, check_id)

    return {"id": str(check_id), "status": "processing", "filename": check.filename}


@router.get("", response_model=list[CheckOut])
async def list_checks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(any_authenticated),
):
    if current_user.role == "teacher":
        q = select(Check).where(Check.submitted_by == current_user.id)
    else:
        q = select(Check).where(Check.org_id == current_user.org_id)

    result = await db.execute(q.order_by(Check.created_at.desc()))
    checks = result.scalars().all()

    if not checks:
        return []

    check_ids = [c.id for c in checks]
    flags_q = await db.execute(
        select(CheckFlag.check_id, func.count().label("cnt"))
        .where(CheckFlag.check_id.in_(check_ids))
        .group_by(CheckFlag.check_id)
    )
    flag_counts: dict = {row.check_id: row.cnt for row in flags_q.all()}

    out = []
    for check in checks:
        co = CheckOut.model_validate(check)
        co.flag_count = flag_counts.get(check.id, 0)
        out.append(co)
    return out


@router.get("/export")
async def export_checks_csv(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(any_authenticated),
):
    """Экспорт проверок (status=done) в CSV, кодировка UTF-8 BOM (Excel-совместимая)."""
    if current_user.role == "teacher":
        q = select(Check).where(Check.submitted_by == current_user.id, Check.status == "done")
    else:
        q = select(Check).where(Check.org_id == current_user.org_id, Check.status == "done")

    result = await db.execute(q.order_by(Check.created_at.desc()))
    checks = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Работа", "Студент", "ID студента", "Группа", "Совпадения %", "ИИ %", "Слов", "Язык", "Дата"])
    for c in checks:
        writer.writerow([
            str(c.id)[:8].upper(),
            c.work_title or c.filename,
            c.student_name or "",
            c.student_id or "",
            c.group_name or "",
            f"{c.similarity_percent:.1f}" if c.similarity_percent is not None else "",
            f"{c.ai_percent:.0f}" if c.ai_percent is not None else "",
            c.word_count or "",
            c.language or "",
            c.created_at.strftime("%d.%m.%Y"),
        ])

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=checks.csv"},
    )


@router.delete("/{check_id}", status_code=204)
async def delete_check(
    check_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(any_authenticated),
):
    """Удалить проверку. Учитель — только свою; school_admin — любую в своей организации."""
    result = await db.execute(select(Check).where(Check.id == check_id))
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="Check not found")

    if current_user.role == "teacher":
        if check.submitted_by != current_user.id:
            raise HTTPException(status_code=403, detail="Cannot delete another teacher's check")
    else:
        if check.org_id != current_user.org_id:
            raise HTTPException(status_code=403, detail="Check not in your organization")

    await db.delete(check)
    await db.commit()
    return Response(status_code=204)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _apply_match_filters(
    matches: list[MatchOut],
    check_org_id,
    excluded_sources: list,
    min_match_words: int,
) -> tuple[list[MatchOut], float, int]:
    """
    Apply per-check filters:
      - Mask cross-org repo matches
      - Remove excluded sources
      - Remove matches shorter than min_match_words
    Returns (filtered_matches, recalculated_similarity_percent, sources_count).
    """
    total_text_len = max(1, max((m.end_char for m in matches), default=1))
    filtered: list[MatchOut] = []

    for m in matches:
        # Mask cross-org repository matches
        if m.source_url and m.source_url.startswith("repo://"):
            parsed = parse_repo_url(m.source_url)
            if parsed:
                match_org_id, _ = parsed
                if match_org_id != str(check_org_id):
                    # Cross-org: mask details
                    m = m.model_copy(update={
                        "source_title": "Работа из другой организации",
                        "source_url": None,
                    })

        # Skip excluded sources
        if m.source_title in (excluded_sources or []):
            continue

        # Skip matches shorter than min_match_words (approximate: 5 chars/word)
        char_len = m.end_char - m.start_char
        if char_len < min_match_words * 5:
            continue

        filtered.append(m)

    # Recalculate coverage
    covered: set[int] = set()
    for m in filtered:
        covered.update(range(m.start_char, m.end_char))

    sim = round(len(covered) / total_text_len * 100, 2) if covered else 0.0
    sources = len({m.source_title for m in filtered if m.source_title})
    return filtered, sim, sources


# ─── общий загрузчик деталей ─────────────────────────────────────────────────

async def _load_check_detail(check_id: uuid.UUID, current_user: User, db: AsyncSession):
    result = await db.execute(select(Check).where(Check.id == check_id))
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="Check not found")
    if current_user.role == "teacher" and check.submitted_by != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if current_user.role == "school_admin" and check.org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="Access denied")

    flags_result = await db.execute(select(CheckFlag).where(CheckFlag.check_id == check_id))
    flags = [FlagOut.model_validate(f) for f in flags_result.scalars().all()]

    matches_result = await db.execute(
        select(CheckMatch)
        .where(CheckMatch.check_id == check_id)
        .order_by(CheckMatch.score.desc())
        .limit(50)
    )
    matches = [MatchOut.model_validate(m) for m in matches_result.scalars().all()]

    mt_segs_result = await db.execute(
        select(MTSegment)
        .where(MTSegment.check_id == check_id)
        .order_by(MTSegment.start_char)
    )
    mt_segments = [MTSegmentOut.model_validate(s) for s in mt_segs_result.scalars().all()]

    text_preview = None
    full_text = None
    if check.status == "done":
        doc_result = await db.execute(select(CheckDocument).where(CheckDocument.check_id == check_id))
        doc = doc_result.scalar_one_or_none()
        if doc:
            text_preview = doc.normalized_text[:400]
            full_text = doc.normalized_text

    return check, flags, matches, mt_segments, text_preview, full_text


@router.get("/{check_id}", response_model=CheckDetailOut)
async def get_check(
    check_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(any_authenticated),
):
    check, flags, matches, mt_segments, text_preview, full_text = await _load_check_detail(check_id, current_user, db)
    matches, sim, srcs = _apply_match_filters(
        matches, check.org_id, check.excluded_sources, check.min_match_words
    )
    out = CheckOut.model_validate(check).model_dump()
    out["flag_count"] = len(flags)
    if check.excluded_sources:
        out["similarity_percent"] = sim
        out["similarity_sources_count"] = srcs
    return CheckDetailOut(
        **out,
        flags=flags,
        matches=matches,
        mt_segments=mt_segments,
        text_preview=text_preview,
        full_text=full_text,
        ocr_used=False,
    )


# ─── Отчёт ───────────────────────────────────────────────────────────────────

FLAG_LABELS = {
    "homoglyph": "Подмена букв (гомоглифы)",
    "invisible_char": "Невидимые символы",
    "hidden_text": "Скрытый текст",
    "spaced_text": "Разрядка",
    "quote_abuse": "Злоупотребление кавычками",
}

LANG_LABELS = {
    "uz-Latn": "узбекский (латиница)",
    "uz-Cyrl": "узбекский (кириллица)",
    "ru": "русский",
    "mixed": "смешанный",
}


def _build_highlighted_html(text: str, matches: list[MatchOut]) -> str:
    """Возвращает HTML-строку с подсвеченными совпадениями."""
    ranges = sorted(
        [
            (m.start_char, min(m.end_char, len(text)), m.match_kind)
            for m in matches
            if m.start_char < len(text) and m.end_char > m.start_char
        ],
        key=lambda x: x[0],
    )

    result = []
    pos = 0
    for start, end, kind in ranges:
        if start < pos:
            continue
        if start > pos:
            result.append(html_lib.escape(text[pos:start]))
        color = "#fecaca" if kind == "exact" else "#e9d5ff" if kind == "cross_lingual" else "#fef08a"
        result.append(
            f'<mark style="background:{color};padding:1px 2px;border-radius:2px;">'
            f"{html_lib.escape(text[start:end])}</mark>"
        )
        pos = end
    if pos < len(text):
        result.append(html_lib.escape(text[pos:]))

    return "".join(result)


def _render_html_report(check: Check, flags: list[FlagOut], matches: list[MatchOut], full_text: Optional[str]) -> str:
    date_str = check.completed_at.strftime("%d.%m.%Y %H:%M") if check.completed_at else "—"
    created_str = check.created_at.strftime("%d.%m.%Y") if check.created_at else "—"
    sim_pct = f"{check.similarity_percent:.1f}%" if check.similarity_percent is not None else "—"
    sim_color = (
        "#dc2626" if (check.similarity_percent or 0) >= 50
        else "#d97706" if (check.similarity_percent or 0) >= 20
        else "#16a34a"
    )
    check_id_short = str(check.id).upper()[:8]

    # Флаги
    flags_html = ""
    if flags:
        items = "".join(
            f'<div style="margin:6px 0;padding:8px 12px;border-radius:6px;border:1px solid #fca5a5;background:#fef2f2;">'
            f'<strong>{html_lib.escape(FLAG_LABELS.get(f.type, f.type))}</strong>'
            f' &mdash; {html_lib.escape(f.severity)} · {f.count} шт.</div>'
            for f in flags
        )
        flags_html = f"""
        <div style="margin-top:24px;">
          <h2 style="font-size:14px;font-weight:600;margin-bottom:10px;color:#111;">
            Flagged — попытки обхода ({len(flags)})
          </h2>
          {items}
        </div>"""

    # Источники
    matches_html = ""
    if matches:
        rows = "".join(
            f"""<tr>
              <td style="padding:6px 10px;border-bottom:1px solid #f3f4f6;">{i + 1}</td>
              <td style="padding:6px 10px;border-bottom:1px solid #f3f4f6;">{html_lib.escape(m.source_title)}</td>
              <td style="padding:6px 10px;border-bottom:1px solid #f3f4f6;color:#6b7280;font-size:11px;">{html_lib.escape(m.source_url or "—")}</td>
              <td style="padding:6px 10px;border-bottom:1px solid #f3f4f6;">{'Точное' if m.match_kind == 'exact' else 'Перефраз'}</td>
              <td style="padding:6px 10px;border-bottom:1px solid #f3f4f6;font-weight:600;">{int(m.score * 100)}%</td>
            </tr>"""
            for i, m in enumerate(matches)
        )
        matches_html = f"""
        <div style="margin-top:24px;">
          <h2 style="font-size:14px;font-weight:600;margin-bottom:10px;color:#111;">
            Источники совпадений ({len(matches)})
          </h2>
          <table style="width:100%;border-collapse:collapse;font-size:12px;">
            <thead>
              <tr style="background:#f9fafb;">
                <th style="text-align:left;padding:6px 10px;color:#6b7280;">#</th>
                <th style="text-align:left;padding:6px 10px;color:#6b7280;">Источник</th>
                <th style="text-align:left;padding:6px 10px;color:#6b7280;">URL</th>
                <th style="text-align:left;padding:6px 10px;color:#6b7280;">Тип</th>
                <th style="text-align:left;padding:6px 10px;color:#6b7280;">Сходство</th>
              </tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
        </div>"""

    # Текст с подсветкой
    text_html = ""
    if full_text:
        body = _build_highlighted_html(full_text, matches) if matches else html_lib.escape(full_text)
        legend = ""
        if matches:
            legend = """
            <div style="margin-bottom:8px;font-size:11px;color:#6b7280;display:flex;gap:12px;">
              <span><mark style="background:#fecaca;padding:1px 4px;border-radius:2px;">Точное совпадение</mark></span>
              <span><mark style="background:#fef08a;padding:1px 4px;border-radius:2px;">Перефраз</mark></span>
              <span><mark style="background:#e9d5ff;padding:1px 4px;border-radius:2px;">Межъязыковое</mark></span>
            </div>"""
        text_html = f"""
        <div style="margin-top:24px;">
          <h2 style="font-size:14px;font-weight:600;margin-bottom:10px;color:#111;">Текст с подсветкой</h2>
          {legend}
          <div style="font-size:12px;line-height:1.7;white-space:pre-wrap;padding:14px;background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;">
            {body}
          </div>
        </div>"""

    meta_parts = []
    if check.student_name:
        meta_parts.append(f"Студент: <strong>{html_lib.escape(check.student_name)}</strong>")
    if check.student_id:
        meta_parts.append(f"ID студента: <strong>{html_lib.escape(check.student_id)}</strong>")
    if check.group_name:
        meta_parts.append(f"Группа: <strong>{html_lib.escape(check.group_name)}</strong>")
    if check.language:
        meta_parts.append(f"Язык: {html_lib.escape(LANG_LABELS.get(check.language, check.language))}")
    if check.word_count:
        meta_parts.append(f"{check.word_count} слов")
    meta_line = " &nbsp;·&nbsp; ".join(meta_parts)

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <title>Отчёт {check_id_short}</title>
  <style>
    @page {{ margin: 2cm; }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: Arial, Helvetica, sans-serif; font-size: 13px; color: #111; line-height: 1.5; }}
    @media screen {{ body {{ max-width: 860px; margin: 32px auto; padding: 0 24px; }} }}
  </style>
</head>
<body>
  <!-- Шапка -->
  <div style="border-bottom:2px solid #2563eb;padding-bottom:14px;margin-bottom:20px;">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;">
      <div>
        <div style="font-size:18px;font-weight:700;color:#1d4ed8;">Антиплагиат</div>
        <div style="font-size:11px;color:#6b7280;margin-top:2px;">
          Проверка {check_id_short} &nbsp;·&nbsp; {created_str}
        </div>
      </div>
      <div style="text-align:right;font-size:11px;color:#6b7280;">
        Завершено: {date_str}
      </div>
    </div>
    <div style="margin-top:10px;">
      <div style="font-size:15px;font-weight:600;">{html_lib.escape(check.work_title or check.filename)}</div>
      {f'<div style="font-size:11px;color:#6b7280;margin-top:3px;">{meta_line}</div>' if meta_line else ''}
    </div>
  </div>

  <!-- Статистика -->
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:20px;">
    <div style="border:1px solid #e5e7eb;border-radius:8px;padding:14px;text-align:center;">
      <div style="font-size:28px;font-weight:700;color:{sim_color};">{sim_pct}</div>
      <div style="font-size:11px;color:#6b7280;margin-top:4px;">Совпадения</div>
      {f'<div style="font-size:11px;color:#9ca3af;">{check.similarity_sources_count} источн.</div>' if check.similarity_sources_count else ''}
    </div>
    <div style="border:1px solid #e5e7eb;border-radius:8px;padding:14px;text-align:center;">
      {'<div style="font-size:28px;font-weight:700;color:' + ("#f97316" if (check.ai_percent or 0) >= 50 else "#d97706" if (check.ai_percent or 0) >= 25 else "#374151") + ';">' + (f"{check.ai_percent:.0f}%" if check.ai_percent is not None else "—") + '</div>' if check.ai_percent is not None else '<div style="font-size:28px;font-weight:700;color:#d1d5db;">—</div>'}
      <div style="font-size:11px;color:#6b7280;margin-top:4px;">Вероятный ИИ-текст</div>
      <div style="font-size:11px;color:#d1d5db;">{check.ai_model_version or "stub · модель в разработке"}</div>
    </div>
    <div style="border:1px solid #e5e7eb;border-radius:8px;padding:14px;text-align:center;">
      <div style="font-size:28px;font-weight:700;color:{'#f97316' if flags else '#d1d5db'};">{len(flags)}</div>
      <div style="font-size:11px;color:#6b7280;margin-top:4px;">Flagged</div>
    </div>
  </div>

  <!-- Дисклеймер -->
  <div style="font-size:11px;color:#9ca3af;background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;padding:10px 14px;margin-bottom:4px;">
    ИИ-оценка — вероятность, а не доказательство. Перед выводами откройте подсвеченные фрагменты и поговорите со студентом.
  </div>

  {flags_html}
  {matches_html}
  {text_html}

  <!-- Подвал -->
  <div style="margin-top:32px;padding-top:12px;border-top:1px solid #e5e7eb;font-size:10px;color:#9ca3af;display:flex;justify-content:space-between;align-items:center;">
    <div>
      <div>ID: {str(check.id)}</div>
      <div style="margin-top:3px;">
        Проверьте подлинность:
        <a href="{settings.FRONTEND_URL}/verify/{str(check.id)}" style="color:#2563eb;">
          antiplagiat.uz/verify/{check_id_short}
        </a>
      </div>
    </div>
    <span>Сгенерировано автоматически · antiplagiat.uz</span>
  </div>
</body>
</html>"""


def _render_text_report(check: Check, flags: list[FlagOut], matches: list[MatchOut], mt_segments: list[MTSegmentOut] = []) -> str:
    date_str = check.completed_at.strftime("%d.%m.%Y") if check.completed_at else "—"
    lines = [
        f"Проверка {str(check.id).upper()[:8]} · {date_str}",
        f"Работа: {check.work_title or check.filename}"
        + (f" · {LANG_LABELS.get(check.language, check.language)}" if check.language else "")
        + (f" · {check.word_count} слов" if check.word_count else ""),
    ]
    if check.student_name:
        lines.append(f"Студент: {check.student_name}" + (f" · {check.group_name}" if check.group_name else ""))
    lines += [
        f"Совпадения: {f'{check.similarity_percent:.1f}%' if check.similarity_percent is not None else '—'}"
        + (f" ({check.similarity_sources_count} источников)" if check.similarity_sources_count else ""),
        f"Вероятный ИИ-текст: {f'{check.ai_percent:.1f}%' if check.ai_percent is not None else '—'}"
        + (f" ({check.ai_model_version})" if check.ai_model_version else " (модель в разработке)"),
        (f"Машинный перевод: вероятно, {len(mt_segments)} фрагментов"
         if check.mt_flag else ""),
        (f"Стилометрия: резкое отличие от предыдущих работ (score={check.stylometry_score:.2f})"
         if check.stylometry_score is not None and check.stylometry_score < 0.45 else ""),
        f"Flagged: {len(flags)}"
        + ((" — " + ", ".join(FLAG_LABELS.get(f.type, f.type) for f in flags)) if flags else ""),
        "",
        "ИИ-оценка — вероятность, а не доказательство.",
        f"Полный отчёт: {settings.FRONTEND_URL}/checks/{check.id}",
        f"Верификация: {settings.FRONTEND_URL}/verify/{check.id}",
    ]
    return "\n".join(filter(None, lines))


def _shade_cell(cell, fill_hex: str) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill_hex)
    tcPr.append(shd)


def _no_borders(table) -> None:
    tblPr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "none")
        borders.append(e)
    tblPr.append(borders)


def _small(p, color="808080", size=9, bold=False):
    for r in p.runs:
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.color.rgb = RGBColor.from_string(color)
    return p


MATCH_KIND_LABELS = {
    "exact": "Дословные совпадения",
    "paraphrase": "Перефразирование",
    "crosslingual": "Межъязыковые совпадения",
    "web": "Веб-источники",
}

FLAG_HOW = {
    "homoglyph": "Буквы заменены на похожие из другого алфавита (кириллица ↔ латиница): слово выглядит прежним, но не совпадает при поиске.",
    "invisible_char": "В текст вставлены невидимые символы нулевой ширины, разбивающие слова, чтобы обойти поиск совпадений.",
    "hidden_text": "В документе есть скрытый текст (белый цвет, крошечный кегль, w:vanish): не виден при чтении, но влияет на объём.",
    "spaced_text": "Буквы в словах разделены пробелами («р а з р я д к а»), чтобы слово не распознавалось целиком.",
    "quote_abuse": "Слишком большая доля текста заключена в кавычки, чтобы исключить её из проверки как цитаты.",
}


def _flag_where(f: FlagOut) -> str:
    d = f.details or {}
    if f.type == "homoglyph":
        exs = d.get("examples") or []
        parts = [f"«{e.get('word')}» (поз. {e.get('position')})" for e in exs[:6] if isinstance(e, dict)]
        return "; ".join(parts)
    if f.type == "invisible_char":
        bt = d.get("by_type") or {}
        return ", ".join(f"{k}: {v}×" for k, v in bt.items())
    if f.type in ("spaced_text",):
        exs = d.get("examples") or []
        return "; ".join(f"«{e}»" for e in exs[:5])
    if f.type == "hidden_text":
        exs = d.get("examples") or []
        return " / ".join(str(e)[:80] for e in exs[:3])
    if f.type == "quote_abuse":
        return f"В кавычках {d.get('quoted_percent', '—')}% текста (порог 25%)"
    return ""


def _add_flags_section(doc, flags: list[FlagOut]) -> None:
    doc.add_heading(f"Flagged — попытки обхода ({len(flags)})", level=1)
    if not flags:
        _small(doc.add_paragraph("Подозрительных приёмов не обнаружено."), size=10)
        return
    for f in flags:
        p = doc.add_paragraph()
        run = p.add_run(f"● {FLAG_LABELS.get(f.type, f.type)}")
        run.bold = True
        run.font.size = Pt(11)
        sev = p.add_run(f"   {f.severity} · {f.count} шт.")
        sev.font.size = Pt(9)
        sev.font.color.rgb = RGBColor.from_string("B45309")
        where = _flag_where(f)
        if where:
            w = doc.add_paragraph(f"Где: {where}")
            _small(w, color="374151", size=10)
        how = FLAG_HOW.get(f.type)
        if how:
            h = doc.add_paragraph(f"Как обходит: {how}")
            _small(h, color="6B7280", size=9)
    doc.add_paragraph()


def _add_cover(doc, check: Check, kind_title: str) -> None:
    now_str = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M")
    date_str = (check.completed_at or check.created_at).strftime("%d.%m.%Y %H:%M")

    head = doc.add_paragraph()
    r = head.add_run("Антиплагиат")
    r.bold = True
    r.font.size = Pt(11)
    r.font.color.rgb = RGBColor.from_string("2563EB")
    head.add_run(f"    ·    {kind_title}")
    _small(doc.add_paragraph(f"ID проверки: {str(check.id).upper()[:8]}"), size=9)

    doc.add_paragraph()
    doc.add_paragraph()
    doc.add_heading(check.work_title or check.filename or "Документ", 0)
    _small(doc.add_paragraph("Антиплагиат · отчёт о проверке"), size=10)

    doc.add_paragraph()
    doc.add_heading("Детали документа", level=1)

    tbl = doc.add_table(rows=1, cols=2)
    _no_borders(tbl)
    left, right = tbl.rows[0].cells

    def field(label: str, value: str):
        lp = left.add_paragraph()
        lr = lp.add_run(label)
        lr.font.size = Pt(9)
        lr.font.color.rgb = RGBColor.from_string("808080")
        vp = left.add_paragraph()
        vr = vp.add_run(value)
        vr.font.size = Pt(10)
        vr.bold = True

    field("ID проверки", str(check.id).upper()[:8])
    field("Дата проверки", date_str)
    field("Дата скачивания", now_str)
    field("Имя файла", check.filename or "—")
    field("Размер файла", f"{(check.file_size or 0) / 1024:.1f} KB")

    _shade_cell(right, "F3F4F6")
    stats = [
        (str(check.word_count), "слов") if check.word_count else None,
        (LANG_LABELS.get(check.language or "", check.language or "—"), "язык"),
    ]
    if check.student_name:
        stats.insert(0, (check.student_name, "студент"))
    if check.student_id:
        stats.insert(1, (check.student_id, "ID студента"))
    for val, cap in [s for s in stats if s]:
        sp = right.add_paragraph()
        sr = sp.add_run(str(val))
        sr.bold = True
        sr.font.size = Pt(11)
        cr = sp.add_run(f"  {cap}")
        cr.font.size = Pt(9)
        cr.font.color.rgb = RGBColor.from_string("6B7280")


def _add_blue_box(doc, title: str, body: str) -> None:
    tbl = doc.add_table(rows=1, cols=1)
    _no_borders(tbl)
    cell = tbl.rows[0].cells[0]
    _shade_cell(cell, "DBEAFE")
    tp = cell.paragraphs[0]
    tr = tp.add_run(title)
    tr.bold = True
    tr.font.size = Pt(10)
    bp = cell.add_paragraph()
    br = bp.add_run(body)
    br.font.size = Pt(9)
    br.font.color.rgb = RGBColor.from_string("1E3A8A")


# ── Подсветка полного текста ─────────────────────────────────────────────────

# hex без '#'
HL = {
    "exact": "FECACA",        # красный — дословное
    "paraphrase": "FEF08A",   # жёлтый — перефраз
    "cross_lingual": "E9D5FF",  # фиолетовый — межъязыковое
    "web": "FED7AA",          # оранжевый — веб
    "quote": "BBF7D0",        # зелёный — цитата
    "ai": "BAE6FD",           # голубой — вероятно ИИ
}


def _quote_spans(text: str) -> list[tuple[int, int]]:
    """Спаны процитированных фрагментов: «…», "…", “…”."""
    spans: list[tuple[int, int]] = []
    for m in re.finditer(r"«[^»]{3,}»|\"[^\"]{3,}\"|“[^”]{3,}”", text):
        spans.append((m.start(), m.end()))
    return spans


def _highlight_spans(
    kind: str, check: Check, matches: list[MatchOut], text: str
) -> tuple[list[tuple[int, int, str, str]], list[tuple[str, str]]]:
    """Возвращает (спаны [start,end,hex,label], легенда [(hex,label)])."""
    spans: list[tuple[int, int, str, str]] = []
    used_labels: dict[str, str] = {}

    if kind == "ai":
        for s, e in ai_spans(text, check.language or "unknown"):
            spans.append((s, e, HL["ai"], "Вероятно ИИ"))
        used_labels[HL["ai"]] = "Вероятно ИИ"
    else:
        for m in matches:
            if m.start_char >= len(text) or m.end_char <= m.start_char:
                continue
            if m.source_url:
                color, label = HL["web"], "Веб-источник"
            elif m.match_kind == "exact":
                color, label = HL["exact"], "Дословное"
            elif m.match_kind == "cross_lingual":
                color, label = HL["cross_lingual"], "Межъязыковое"
            else:
                color, label = HL["paraphrase"], "Перефраз"
            spans.append((m.start_char, min(m.end_char, len(text)), color, label))
            used_labels[color] = label
        for s, e in _quote_spans(text):
            spans.append((s, e, HL["quote"], "Цитата"))
            used_labels[HL["quote"]] = "Цитата"

    legend = list(dict.fromkeys(used_labels.items()))
    legend = [(c, l) for c, l in used_labels.items()]
    return spans, legend


def _segmentize(text: str, spans: list[tuple[int, int, str, str]]) -> list[tuple[str, str | None]]:
    """Режет текст на сегменты (кусок, hex|None) по неперекрывающимся спанам."""
    ordered = sorted(spans, key=lambda x: x[0])
    segs: list[tuple[str, str | None]] = []
    pos = 0
    for start, end, color, _label in ordered:
        if start < pos or start >= len(text):
            continue
        if start > pos:
            segs.append((text[pos:start], None))
        segs.append((text[start:min(end, len(text))], color))
        pos = min(end, len(text))
    if pos < len(text):
        segs.append((text[pos:], None))
    return segs


def _add_highlighted_text_docx(doc, text: str, spans, legend, title: str) -> None:
    doc.add_page_break()
    doc.add_heading(title, level=1)
    if legend:
        lp = doc.add_paragraph()
        for color, label in legend:
            run = lp.add_run(f"  {label}  ")
            run.font.size = Pt(9)
            _shade_run(run, color)
            lp.add_run("  ")
    para = doc.add_paragraph()
    for seg_text, color in _segmentize(text, spans):
        parts = seg_text.split("\n")
        for i, part in enumerate(parts):
            if i > 0:
                para = doc.add_paragraph()
            if part:
                run = para.add_run(part)
                run.font.size = Pt(10)
                if color:
                    _shade_run(run, color)


def _shade_run(run, fill_hex: str) -> None:
    rPr = run._element.get_or_add_rPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill_hex)
    rPr.append(shd)


def _render_docx_report(
    check: Check,
    flags: list[FlagOut],
    matches: list[MatchOut],
    mt_segments: list[MTSegmentOut],
    kind: str = "full",
    full_text: Optional[str] = None,
) -> bytes:
    doc = DocxDocument()
    kind_title = {"plagiarism": "Отчёт антиплагиата", "ai": "Отчёт ИИ-детектора",
                  "flagged": "Отчёт по обходу"}.get(kind, "Отчёт о проверке")

    # ── Cover page ───────────────────────────────────────────────────────────
    _add_cover(doc, check, kind_title)
    doc.add_page_break()

    if kind == "ai":
        # ── AI Writing Overview ──────────────────────────────────────────────
        ai_pct = check.ai_percent if check.ai_percent is not None else 0
        h = doc.add_heading(f"{ai_pct:.0f}% определено как ИИ", 0)
        _small(
            doc.add_paragraph(
                "Процент показывает долю текста, вероятно сгенерированного ИИ "
                "или сгенерированного и затем переработанного ИИ."
            ),
            size=10,
        )
        doc.add_paragraph()
        _add_blue_box(
            doc,
            "Внимание: требуется проверка человеком.",
            "Оценка ИИ — вероятность, а не доказательство. Поймите ограничения "
            "детектора, прежде чем делать выводы о работе студента.",
        )
        doc.add_paragraph()
        p = doc.add_paragraph()
        pr = p.add_run(f"AI-generated   {ai_pct:.0f}%")
        pr.bold = True
        pr.font.size = Pt(11)
        _small(
            doc.add_paragraph("Вероятно сгенерировано или переработано ИИ."),
            size=10,
        )
        if check.mt_flag:
            doc.add_paragraph()
            mp = doc.add_paragraph()
            mr = mp.add_run("Машинный перевод: ")
            mr.bold = True
            mp.add_run(
                f"вероятно · {len(mt_segments)} фрагментов "
                f"({check.mt_percent:.0f}% текста)" if check.mt_percent is not None else "вероятно"
            )
        if check.stylometry_score is not None:
            sp = doc.add_paragraph()
            sr = sp.add_run("Стилометрия: ")
            sr.bold = True
            sp.add_run(f"{check.stylometry_score:.2f} (аномалии стиля)")
        doc.add_paragraph()
        disc = doc.add_paragraph(
            "Дисклеймер. Оценка ИИ-детектора помогает выявить текст, возможно "
            "подготовленный генеративным ИИ. Она не всегда точна и не должна быть "
            "единственным основанием для решений в отношении студента; требуется "
            "дополнительная проверка и человеческое суждение."
        )
        _small(disc, color="9CA3AF", size=8)

    elif kind == "flagged":
        # ── Flagged / попытки обхода ─────────────────────────────────────────
        doc.add_heading(f"{len(flags)} попыток обхода", 0)
        _small(
            doc.add_paragraph(
                "Отчёт по приёмам маскировки текста: подмена букв, невидимые символы, "
                "скрытый текст, разрядка. Их наличие — повод присмотреться к работе."
            ),
            size=10,
        )
        doc.add_paragraph()
        _add_flags_section(doc, flags)

    else:
        # ── Integrity / Similarity Overview ──────────────────────────────────
        sim = check.similarity_percent if check.similarity_percent is not None else 0
        doc.add_heading(f"{sim:.0f}%  Общее сходство", 0)
        _small(
            doc.add_paragraph(
                "Суммарный объём всех совпадений, включая пересекающиеся источники, "
                "по всем базам."
            ),
            size=10,
        )
        doc.add_paragraph()

        tbl = doc.add_table(rows=1, cols=2)
        _no_borders(tbl)
        left, right = tbl.rows[0].cells

        # Match groups (by kind)
        lh = left.paragraphs[0].add_run("Группы совпадений")
        lh.bold = True
        lh.font.size = Pt(12)
        kinds: dict[str, int] = {}
        for m in matches:
            key = "web" if m.source_url else m.match_kind
            kinds[key] = kinds.get(key, 0) + 1
        if not kinds:
            _small(left.add_paragraph("Совпадений не найдено."), size=10)
        for k, cnt in kinds.items():
            gp = left.add_paragraph()
            gr = gp.add_run(f"{cnt}  {MATCH_KIND_LABELS.get(k, k)}")
            gr.bold = True
            gr.font.size = Pt(10)

        # Top sources
        rh = right.paragraphs[0].add_run("Топ источников")
        rh.bold = True
        rh.font.size = Pt(12)
        top = sorted(matches, key=lambda m: m.score, reverse=True)[:8]
        if not top:
            _small(right.add_paragraph("—"), size=10)
        for m in top:
            sp = right.add_paragraph()
            pr = sp.add_run(f"{int(m.score * 100)}%  ")
            pr.bold = True
            pr.font.size = Pt(10)
            tr = sp.add_run((m.source_title or "Источник")[:60])
            tr.font.size = Pt(10)
            if m.source_url:
                _small(right.add_paragraph(m.source_url[:80]), color="2563EB", size=8)

        doc.add_paragraph()
        _add_flags_section(doc, flags)

    # ── Полный текст с пометками ─────────────────────────────────────────────
    if full_text:
        if kind == "flagged":
            spans, legend = [], []
        else:
            spans, legend = _highlight_spans(kind, check, matches, full_text)
        title = (
            "Текст работы · выделено ИИ" if kind == "ai"
            else "Текст работы" if kind == "flagged"
            else "Текст работы · выделены совпадения и цитаты"
        )
        _add_highlighted_text_docx(doc, full_text, spans, legend, title)

    # ── Footer: verification ─────────────────────────────────────────────────
    doc.add_paragraph()
    vp = doc.add_paragraph()
    vp.add_run("Проверка подлинности: ").bold = True
    vp.add_run(f"{settings.FRONTEND_URL}/verify/{check.id}")
    _small(vp, color="6B7280", size=9)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


def _render_pdf_report(
    check: Check,
    flags: list[FlagOut],
    matches: list[MatchOut],
    mt_segments: list[MTSegmentOut],
    full_text: Optional[str],
    kind: str,
) -> bytes:
    from app.services.pdf_report import render_pdf_report

    return render_pdf_report(
        check,
        flags,
        matches,
        mt_segments,
        full_text,
        kind,
        highlight_spans_fn=_highlight_spans,
        segmentize_fn=_segmentize,
    )


def _pdf_download_name(check_id: uuid.UUID, kind: str) -> str:
    id_short = str(check_id).upper()[:8]
    kind_label = {
        "plagiarism": "совпадения",
        "ai": "ИИ",
        "flagged": "обход",
    }.get(kind, "отчёт")
    return f"Антиплагиат-{kind_label}-{id_short}.pdf"


@router.get("/{check_id}/report")
async def get_report(
    check_id: uuid.UUID,
    format: str = Query("html", pattern="^(html|json|text|pdf)$"),
    kind: str = Query("full", pattern="^(full|plagiarism|ai|flagged)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(any_authenticated),
):
    """Скачать отчёт в формате html, json, text или pdf.

    Параметр kind выбирает вид отчёта:
    full — полный, plagiarism — только антиплагиат, ai — только ИИ-детектор.
    pdf включает обложку с метриками на 1-й странице и полный текст с пометками.
    """
    check, flags, matches, mt_segments, _, full_text = await _load_check_detail(check_id, current_user, db)

    if check.status != "done":
        raise HTTPException(status_code=400, detail="Check is not done yet")

    id_short = str(check_id).upper()[:8]

    if format == "pdf":
        try:
            pdf_bytes = _render_pdf_report(check, flags, matches, mt_segments, full_text, kind)
        except ModuleNotFoundError:
            raise HTTPException(
                status_code=503,
                detail="PDF-движок не установлен. Выполните: pip install reportlab",
            )
        from urllib.parse import quote

        filename = _pdf_download_name(check_id, kind)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f"attachment; filename=\"report-{id_short}.pdf\"; "
                    f"filename*=UTF-8''{quote(filename)}"
                )
            },
        )

    if format == "text":
        return PlainTextResponse(
            _render_text_report(check, flags, matches, mt_segments),
            headers={"Content-Disposition": f'attachment; filename="report-{id_short}.txt"'},
        )

    if format == "json":
        payload = CheckDetailOut(
            **CheckOut.model_validate(check).model_dump(),
            flags=flags,
            matches=matches,
            mt_segments=mt_segments,
            full_text=full_text,
            ocr_used=False,
        )
        return JSONResponse(
            content=json.loads(payload.model_dump_json()),
            headers={"Content-Disposition": f'attachment; filename="report-{id_short}.json"'},
        )

    # HTML (default)
    html_content = _render_html_report(check, flags, matches, full_text)
    return HTMLResponse(
        content=html_content,
        headers={"Content-Disposition": f'inline; filename="report-{id_short}.html"'},
    )


# ─── Исключение источника ────────────────────────────────────────────────────

class ExcludeSourceIn(BaseModel):
    source_title: str


class ExcludeSourceOut(BaseModel):
    similarity_percent: float
    similarity_sources_count: int
    excluded_sources: list


@router.post("/{check_id}/exclude-source", response_model=ExcludeSourceOut)
async def exclude_source(
    check_id: uuid.UUID,
    data: ExcludeSourceIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(any_authenticated),
):
    """
    Добавить источник в список исключённых и пересчитать similarity_percent.
    Учитель может вызывать на своих проверках.
    """
    result = await db.execute(select(Check).where(Check.id == check_id))
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="Check not found")
    if current_user.role == "teacher" and check.submitted_by != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if check.status != "done":
        raise HTTPException(status_code=400, detail="Check is not done yet")

    # Update excluded list
    excluded = list(check.excluded_sources or [])
    if data.source_title not in excluded:
        excluded.append(data.source_title)
        check.excluded_sources = excluded

    # Recalculate with all matches
    matches_q = await db.execute(
        select(CheckMatch).where(CheckMatch.check_id == check_id)
    )
    all_matches = [MatchOut.model_validate(m) for m in matches_q.scalars().all()]
    filtered, sim, srcs = _apply_match_filters(all_matches, check.org_id, excluded, check.min_match_words)

    check.similarity_percent = sim
    check.similarity_sources_count = srcs
    await db.commit()

    return ExcludeSourceOut(
        similarity_percent=sim,
        similarity_sources_count=srcs,
        excluded_sources=excluded,
    )


# ─── Публичная верификация ────────────────────────────────────────────────────

@router.get("/{check_id}/verify")
async def verify_check(
    check_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Публичный endpoint для проверки подлинности отчёта.
    Не требует авторизации — встраивается в QR-код PDF.
    """
    result = await db.execute(select(Check).where(Check.id == check_id))
    check = result.scalar_one_or_none()
    if not check or check.status != "done":
        raise HTTPException(status_code=404, detail="Report not found")

    return {
        "id": str(check.id),
        "id_short": str(check.id).upper()[:8],
        "is_authentic": True,
        "status": check.status,
        "work_title": check.work_title or check.filename,
        "similarity_percent": check.similarity_percent,
        "ai_percent": check.ai_percent,
        "word_count": check.word_count,
        "language": check.language,
        "completed_at": check.completed_at.isoformat() if check.completed_at else None,
    }


# ─── Споры (disputes) ────────────────────────────────────────────────────────

class DisputeCreate(BaseModel):
    comment: str


class DisputeOut(BaseModel):
    id: uuid.UUID
    check_id: uuid.UUID
    comment: str
    status: str
    verdict: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


@router.post("/{check_id}/dispute", response_model=DisputeOut, status_code=201)
async def create_dispute(
    check_id: uuid.UUID,
    data: DisputeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(any_authenticated),
):
    """Оспорить результат проверки."""
    if not data.comment.strip():
        raise HTTPException(status_code=400, detail="Comment cannot be empty")

    result = await db.execute(select(Check).where(Check.id == check_id))
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="Check not found")
    if current_user.role == "teacher" and check.submitted_by != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if current_user.role == "school_admin" and check.org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Не позволяем спамить одинаковыми спорами
    existing = await db.execute(
        select(Dispute).where(
            Dispute.check_id == check_id,
            Dispute.submitted_by == current_user.id,
            Dispute.status == "pending",
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="You already have a pending dispute for this check")

    dispute = Dispute(
        check_id=check_id,
        submitted_by=current_user.id,
        comment=data.comment.strip(),
    )
    db.add(dispute)
    await db.commit()
    await db.refresh(dispute)
    return dispute
