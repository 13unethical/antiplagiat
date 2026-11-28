"""Markly-style PDF reports: cover + metrics on page 1, highlighted text after."""
from __future__ import annotations

import io
import xml.sax.saxutils as sx
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config import settings
from app.models.check import Check
from app.schemas.check import FlagOut, MTSegmentOut
from app.schemas.match import MatchOut

FLAG_LABELS = {
    "homoglyph": "Подмена букв (гомоглифы)",
    "invisible_char": "Невидимые символы",
    "hidden_text": "Скрытый текст",
    "spaced_text": "Разрядка",
    "quote_abuse": "Злоупотребление кавычками",
}

FLAG_HOW = {
    "homoglyph": "Буквы заменены похожими из других алфавитов, чтобы обойти текстовый поиск.",
    "invisible_char": "В текст вставлены невидимые символы, ломающие сравнение.",
    "hidden_text": "Текст спрятан цветом/размером, но читается парсером.",
    "spaced_text": "Буквы разнесены пробелами, чтобы скрыть слова от поиска.",
    "quote_abuse": "Слишком большая доля текста в кавычках — возможная маскировка заимствований.",
}

MATCH_KIND_LABELS = {
    "exact": "Точное совпадение",
    "near": "Близкое совпадение",
    "semantic": "Семантическое",
    "crosslang": "Межъязыковое",
    "web": "Интернет",
    "repo": "Репозиторий школы",
    "corpus": "Корпус",
}

LANG_LABELS = {
    "uz-Latn": "узбекский (латиница)",
    "uz-Cyrl": "узбекский (кириллица)",
    "ru": "русский",
    "en": "английский",
    "mixed": "смешанный",
    "other": "другой",
}

TEAL = "#0F766E"
TEAL_SOFT = "#CCFBF1"
TEAL_DARK = "#115E59"
INK = "#111827"
MUTED = "#6B7280"
LINE = "#E5E7EB"
BOX_BG = "#F3F4F6"
CAUTION_BG = "#ECFEFF"
CAUTION_BORDER = "#99F6E4"

_MONTHS_RU = (
    "", "янв.", "февр.", "мар.", "апр.", "мая", "июн.",
    "июл.", "авг.", "сент.", "окт.", "нояб.", "дек.",
)

_PDF_FONTS_READY = False


def _ensure_pdf_fonts() -> None:
    global _PDF_FONTS_READY
    if _PDF_FONTS_READY:
        return
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.pdfmetrics import registerFontFamily

    base = Path(__file__).resolve().parents[1] / "assets"
    pdfmetrics.registerFont(TTFont("DejaVu", str(base / "DejaVuSans.ttf")))
    bold = base / "DejaVuSans-Bold.ttf"
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(bold if bold.exists() else base / "DejaVuSans.ttf")))
    registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold", italic="DejaVu", boldItalic="DejaVu-Bold")
    _PDF_FONTS_READY = True


def _fmt_dt(dt: datetime) -> str:
    local = dt.astimezone() if dt.tzinfo else dt.replace(tzinfo=timezone.utc).astimezone()
    offset = local.utcoffset()
    hours = int(offset.total_seconds() // 3600) if offset else 5
    return f"{local.day} {_MONTHS_RU[local.month]} {local.year}, {local.strftime('%H:%M')} GMT+{hours}"


def _submission_id(check: Check) -> str:
    short = str(check.id).replace("-", "")[:8].upper()
    return f"MK-{short}"


def _flag_where(f: FlagOut) -> str:
    d = f.details or {}
    if f.type == "homoglyph":
        exs = d.get("examples") or []
        parts = [f"«{e.get('word')}» (поз. {e.get('position')})" for e in exs[:6] if isinstance(e, dict)]
        return "; ".join(parts)
    if f.type == "invisible_char":
        bt = d.get("by_type") or {}
        return ", ".join(f"{k}: {v}×" for k, v in bt.items())
    if f.type == "spaced_text":
        exs = d.get("examples") or []
        return "; ".join(f"«{e}»" for e in exs[:5])
    if f.type == "hidden_text":
        exs = d.get("examples") or []
        return " / ".join(str(e)[:80] for e in exs[:3])
    if f.type == "quote_abuse":
        return f"В кавычках {d.get('quoted_percent', '—')}% текста (порог 25%)"
    return ""


def _draw_markin_logo(canvas, x: float, y: float, size: float = 11, with_text: bool = True) -> None:
    from reportlab.lib.colors import HexColor, white

    canvas.setFillColor(HexColor(TEAL))
    canvas.roundRect(x, y - 1, size, size, 2, fill=1, stroke=0)
    canvas.setStrokeColor(white)
    canvas.setLineWidth(1.4)
    canvas.setLineCap(1)
    canvas.setLineJoin(1)
    canvas.line(x + size * 0.22, y + size * 0.42, x + size * 0.42, y + size * 0.22)
    canvas.line(x + size * 0.42, y + size * 0.22, x + size * 0.78, y + size * 0.68)
    if with_text:
        canvas.setFillColor(HexColor(INK))
        canvas.setFont("DejaVu", 9)
        canvas.drawString(x + size + 4, y + 1.5, "Markly")


def _page_section_title(kind: str, page: int) -> str:
    if page == 1:
        return "Cover & Overview"
    if kind == "ai":
        return "AI Writing Overview"
    if kind == "flagged":
        return "Integrity Flags"
    return "Match Overview"


class _MarklyDocTemplate:
    """Thin wrapper around BaseDocTemplate with Markly header/footer."""

    def __init__(self, buf, *, title: str, submission_id: str, kind: str):
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate

        self.submission_id = submission_id
        self.kind = kind
        self._mm = mm
        self._doc = BaseDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
            topMargin=22 * mm,
            bottomMargin=20 * mm,
            title=title,
            author="Markly",
        )
        frame = Frame(
            self._doc.leftMargin,
            self._doc.bottomMargin,
            self._doc.width,
            self._doc.height,
            id="normal",
            showBoundary=0,
        )
        self._doc.addPageTemplates([PageTemplate(id="markin", frames=frame, onPage=self._on_page)])

    def _on_page(self, canvas, doc):
        from reportlab.lib.colors import HexColor
        from reportlab.lib.pagesizes import A4

        mm = self._mm
        page = canvas.getPageNumber()
        w, h = A4
        section = _page_section_title(self.kind, page)
        label = f"Page {page} — {section}"

        _draw_markin_logo(canvas, 20 * mm, h - 16 * mm, size=12)
        canvas.setFillColor(HexColor(MUTED))
        canvas.setFont("DejaVu", 8)
        canvas.drawCentredString(w / 2, h - 14.5 * mm, label)
        canvas.setFont("DejaVu", 7.5)
        canvas.drawRightString(w - 20 * mm, h - 12.5 * mm, "Submission ID")
        canvas.setFillColor(HexColor(INK))
        canvas.setFont("DejaVu", 7.5)
        canvas.drawRightString(w - 20 * mm, h - 16 * mm, self.submission_id)

        canvas.setStrokeColor(HexColor(LINE))
        canvas.setLineWidth(0.6)
        canvas.line(20 * mm, h - 20 * mm, w - 20 * mm, h - 20 * mm)

        canvas.line(20 * mm, 14 * mm, w - 20 * mm, 14 * mm)
        _draw_markin_logo(canvas, 20 * mm, 8 * mm, size=10)
        canvas.setFillColor(HexColor(MUTED))
        canvas.setFont("DejaVu", 7.5)
        canvas.drawCentredString(w / 2, 9 * mm, label)
        canvas.setFont("DejaVu", 7)
        canvas.drawRightString(w - 20 * mm, 10.5 * mm, "Submission ID")
        canvas.setFillColor(HexColor(INK))
        canvas.drawRightString(w - 20 * mm, 7.5 * mm, self.submission_id)

    def build(self, story):
        self._doc.build(story)


def _styles():
    from reportlab.lib.colors import HexColor
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT

    # Turnitin-like: compact, light weight, little bold
    return {
        "title": ParagraphStyle(
            "mk_title", fontName="DejaVu", fontSize=15, leading=19,
            textColor=HexColor(INK), spaceAfter=3, spaceBefore=2,
        ),
        "brand_sub": ParagraphStyle(
            "mk_brand", fontName="DejaVu", fontSize=8, leading=10,
            textColor=HexColor(MUTED), spaceAfter=8,
        ),
        "section": ParagraphStyle(
            "mk_section", fontName="DejaVu", fontSize=8, leading=10,
            textColor=HexColor(MUTED), spaceBefore=2, spaceAfter=4,
        ),
        "label": ParagraphStyle(
            "mk_label", fontName="DejaVu", fontSize=6.5, leading=8,
            textColor=HexColor("#9CA3AF"), spaceBefore=4, spaceAfter=0,
        ),
        "value": ParagraphStyle(
            "mk_value", fontName="DejaVu", fontSize=8, leading=10,
            textColor=HexColor("#4B5563"), spaceAfter=1,
        ),
        "stat_num": ParagraphStyle(
            "mk_stat_n", fontName="DejaVu", fontSize=10, leading=12,
            textColor=HexColor("#4B5563"), spaceBefore=2, spaceAfter=0,
        ),
        "stat_cap": ParagraphStyle(
            "mk_stat_c", fontName="DejaVu", fontSize=7, leading=9,
            textColor=HexColor(MUTED), spaceAfter=5,
        ),
        "big": ParagraphStyle(
            "mk_big", fontName="DejaVu", fontSize=18, leading=22,
            textColor=HexColor(INK), spaceBefore=2, spaceAfter=3,
        ),
        "meta": ParagraphStyle(
            "mk_meta", fontName="DejaVu", fontSize=7.5, leading=10,
            textColor=HexColor(MUTED), spaceAfter=6,
        ),
        "h2": ParagraphStyle(
            "mk_h2", fontName="DejaVu", fontSize=8.5, leading=11,
            textColor=HexColor("#374151"), spaceBefore=8, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "mk_body", fontName="DejaVu", fontSize=8, leading=11,
            textColor=HexColor(INK), spaceAfter=3, alignment=TA_LEFT,
        ),
        "body_text": ParagraphStyle(
            "mk_body_text", fontName="DejaVu", fontSize=9.5, leading=14,
            textColor=HexColor(INK), spaceAfter=6, alignment=TA_LEFT,
        ),
        "small": ParagraphStyle(
            "mk_small", fontName="DejaVu", fontSize=6.5, leading=9,
            textColor=HexColor("#9CA3AF"), spaceBefore=6, spaceAfter=2,
        ),
        "caution": ParagraphStyle(
            "mk_caution", fontName="DejaVu", fontSize=7.5, leading=10,
            textColor=HexColor(TEAL_DARK), backColor=HexColor(CAUTION_BG),
            borderPadding=7, spaceBefore=2, spaceAfter=6,
        ),
        "source": ParagraphStyle(
            "mk_src", fontName="DejaVu", fontSize=7.5, leading=10,
            textColor=HexColor(INK), spaceBefore=2, spaceAfter=2,
        ),
        "em": ParagraphStyle(
            "mk_em", fontName="DejaVu", fontSize=8, leading=11,
            textColor=HexColor(INK), spaceAfter=3,
        ),
    }


def _cover_table(check: Check, full_text: Optional[str], st, esc) -> object:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm
    from reportlab.platypus import Table, TableStyle, Paragraph

    sid = _submission_id(check)
    submitted = _fmt_dt(check.completed_at or check.created_at)
    downloaded = _fmt_dt(datetime.now(timezone.utc))
    words = check.word_count or (len((full_text or "").split()) if full_text else 0)
    chars = len(full_text) if full_text else 0
    pages_est = max(1, round(words / 300)) if words else 1

    left_bits = []
    for label, value in [
        ("Submission ID", sid),
        ("Submission Date", submitted),
        ("Download Date", downloaded),
        ("File Name", check.filename or "—"),
        ("File Size", f"{(check.file_size or 0) / 1024:.1f} KB"),
    ]:
        left_bits.append(Paragraph(esc(label), st["label"]))
        left_bits.append(Paragraph(esc(value), st["value"]))
    if check.student_name:
        left_bits.append(Paragraph("Student", st["label"]))
        sn = check.student_name + (f" · ID {check.student_id}" if check.student_id else "")
        left_bits.append(Paragraph(esc(sn), st["value"]))
    if check.language:
        left_bits.append(Paragraph("Language", st["label"]))
        left_bits.append(Paragraph(esc(LANG_LABELS.get(check.language, check.language)), st["value"]))

    right_bits = [
        Paragraph(f"{pages_est}", st["stat_num"]),
        Paragraph("Pages (est.)", st["stat_cap"]),
        Paragraph(f"{words:,}".replace(",", " "), st["stat_num"]),
        Paragraph("Words", st["stat_cap"]),
        Paragraph(f"{chars:,}".replace(",", " ") if chars else "—", st["stat_num"]),
        Paragraph("Characters", st["stat_cap"]),
    ]

    right_inner = Table([[b] for b in right_bits], colWidths=[48 * mm])
    right_inner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor(BOX_BG)),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (0, 0), 8),
        ("BOTTOMPADDING", (0, -1), (0, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))

    left_tbl = Table([[b] for b in left_bits], colWidths=[100 * mm])
    left_tbl.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))

    outer = Table([[left_tbl, right_inner]], colWidths=[105 * mm, 52 * mm])
    outer.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return outer


def _overview_plagiarism(check, matches, flags, st, esc) -> list:
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm

    sim = check.similarity_percent if check.similarity_percent is not None else 0
    items: list = [
        Spacer(1, 6),
        HRFlowable(width="100%", thickness=0.4, color=HexColor(LINE), spaceBefore=2, spaceAfter=8),
        Paragraph(f"{sim:.0f}% Overall Similarity", st["big"]),
        Paragraph(
            "The combined total of all matches, including overlapping sources, for each database.",
            st["meta"],
        ),
        Spacer(1, 2),
    ]

    kinds: dict[str, int] = {}
    for m in matches:
        key = "web" if m.source_url else m.match_kind
        kinds[key] = kinds.get(key, 0) + 1

    left_rows = [Paragraph("Match Groups", st["h2"])]
    if not kinds:
        left_rows.append(Paragraph("No matches found.", st["body"]))
    else:
        colors_cycle = ["#EF4444", "#F97316", "#EAB308", "#22C55E", "#3B82F6"]
        for i, (k, cnt) in enumerate(kinds.items()):
            color = colors_cycle[i % len(colors_cycle)]
            left_rows.append(Paragraph(
                f'<font color="{color}" size="8">●</font>&nbsp;&nbsp;'
                f'{cnt}  {esc(MATCH_KIND_LABELS.get(k, k))}',
                st["body"],
            ))

    left_rows.append(Spacer(1, 4))
    left_rows.append(Paragraph("Integrity Flags", st["h2"]))
    left_rows.append(Paragraph(f"{len(flags)} Integrity Flags for Review", st["em"]))
    if not flags:
        left_rows.append(Paragraph("No suspicious text manipulations found.", st["body"]))
    else:
        for f in flags[:6]:
            left_rows.append(Paragraph(
                f'● {esc(FLAG_LABELS.get(f.type, f.type))}'
                f'  <font color="#9CA3AF" size="7">{esc(f.severity)} · {f.count}</font>',
                st["body"],
            ))

    right_rows = [Paragraph("Top Sources", st["h2"])]
    top = sorted(matches, key=lambda m: m.score, reverse=True)[:8]
    if not top:
        right_rows.append(Paragraph("—", st["body"]))
        right_rows.append(Spacer(1, 4))
        right_rows.append(Paragraph(
            "Our system's algorithms look deeply at a document for inconsistencies "
            "that would set it apart from a normal submission.",
            st["caution"],
        ))
    else:
        bucket = {"web": 0.0, "corpus": 0.0, "repo": 0.0}
        for m in matches:
            if m.source_url:
                bucket["web"] += m.score
            elif m.match_kind in ("repo",):
                bucket["repo"] += m.score
            else:
                bucket["corpus"] += m.score
        total = sum(bucket.values()) or 1
        right_rows.append(Paragraph(
            f'{min(100, int(100 * bucket["web"] / total))}%&nbsp;&nbsp;Internet sources', st["body"]))
        right_rows.append(Paragraph(
            f'{min(100, int(100 * bucket["corpus"] / total))}%&nbsp;&nbsp;Publications', st["body"]))
        right_rows.append(Paragraph(
            f'{min(100, int(100 * bucket["repo"] / total))}%&nbsp;&nbsp;Submitted works', st["body"]))
        right_rows.append(Spacer(1, 4))
        right_rows.append(Paragraph(
            "Percentage is the share of text matched to sources. "
            "Overlaps are counted once in the overall total.",
            st["caution"],
        ))

    left_tbl = Table([[x] for x in left_rows], colWidths=[88 * mm])
    right_tbl = Table([[x] for x in right_rows], colWidths=[66 * mm])
    for t in (left_tbl, right_tbl):
        t.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
    grid = Table([[left_tbl, right_tbl]], colWidths=[90 * mm, 68 * mm])
    grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    items.append(grid)

    if top:
        items.append(Spacer(1, 4))
        items.append(HRFlowable(width="100%", thickness=0.35, color=HexColor(LINE), spaceBefore=2, spaceAfter=4))
        items.append(Paragraph("Top Sources", st["h2"]))
        items.append(Paragraph(
            "Sources with the highest number of matches. Overlapping sources are not duplicated.",
            st["meta"],
        ))
        for i, m in enumerate(top[:6], 1):
            title = (m.source_title or m.source_url or "Источник")[:64]
            pct = int(m.score * 100)
            items.append(Paragraph(
                f'{i}.&nbsp;&nbsp;{pct}%&nbsp;&nbsp;{esc(title)}',
                st["source"],
            ))

    return items


def _overview_ai(check, mt_segments, st, esc) -> list:
    from reportlab.platypus import Paragraph, Spacer, HRFlowable, Table, TableStyle
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm

    ai_pct = check.ai_percent if check.ai_percent is not None else 0
    left = [
        Paragraph(f"{ai_pct:.0f}% detected as AI", st["big"]),
        Paragraph(
            "The percentage indicates the combined amount of likely AI-generated text "
            "as well as likely AI-generated text that was also likely revised.",
            st["meta"],
        ),
        Paragraph(
            f'<font color="{TEAL}" size="8">●</font>&nbsp;&nbsp;'
            f'AI-generated&nbsp;&nbsp;{ai_pct:.0f}% — likely generated or revised by AI.',
            st["body"],
        ),
    ]
    if check.mt_flag:
        mtp = f" ({check.mt_percent:.0f}%)" if check.mt_percent is not None else ""
        left.append(Paragraph(f"Machine translation likely · {len(mt_segments)} segments{mtp}", st["body"]))
    if check.stylometry_score is not None:
        left.append(Paragraph(f"Stylometry score: {check.stylometry_score:.2f}", st["body"]))

    caution = Paragraph(
        "Caution: Review required.<br/>"
        "It is essential to understand the limitations of AI detection before making "
        "decisions about a student's work.",
        st["caution"],
    )
    left_tbl = Table([[x] for x in left], colWidths=[95 * mm])
    right_tbl = Table([[caution]], colWidths=[58 * mm])
    for t in (left_tbl, right_tbl):
        t.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
    grid = Table([[left_tbl, right_tbl]], colWidths=[98 * mm, 60 * mm])
    grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))

    return [
        Spacer(1, 6),
        HRFlowable(width="100%", thickness=0.4, color=HexColor(LINE), spaceBefore=2, spaceAfter=8),
        grid,
        Paragraph("Disclaimer", st["h2"]),
        Paragraph(
            "Our AI writing assessment is designed to help educators identify text that might be "
            "prepared by a generative AI tool. It may not always be accurate and should not be "
            "used as the sole basis for adverse actions against a student.",
            st["small"],
        ),
    ]


def _overview_flagged(flags, st, esc) -> list:
    from reportlab.platypus import Paragraph, Spacer, HRFlowable
    from reportlab.lib.colors import HexColor

    items: list = [
        Spacer(1, 6),
        HRFlowable(width="100%", thickness=0.4, color=HexColor(LINE), spaceBefore=2, spaceAfter=8),
        Paragraph(f"{len(flags)} Integrity Flags for Review", st["big"]),
        Paragraph(
            "Suspicious text manipulations: homoglyphs, invisible characters, hidden text, spaced letters.",
            st["meta"],
        ),
        Spacer(1, 2),
    ]
    if not flags:
        items.append(Paragraph("No suspicious text manipulations found.", st["body"]))
        return items
    for f in flags:
        items.append(Paragraph(
            f'● {esc(FLAG_LABELS.get(f.type, f.type))}'
            f'  <font color="#9CA3AF" size="7">{esc(f.severity)} · {f.count}</font>',
            st["body"],
        ))
        where = _flag_where(f)
        if where:
            items.append(Paragraph(f'<font size="7" color="#6B7280">{esc(where)}</font>', st["body"]))
    return items


def render_pdf_report(
    check: Check,
    flags: list[FlagOut],
    matches: list[MatchOut],
    mt_segments: list[MTSegmentOut],
    full_text: Optional[str],
    kind: str,
    *,
    highlight_spans_fn=None,
    segmentize_fn=None,
) -> bytes:
    from reportlab.platypus import Paragraph, Spacer, PageBreak, HRFlowable
    from reportlab.lib.colors import HexColor

    _ensure_pdf_fonts()
    st = _styles()
    esc = sx.escape
    sid = _submission_id(check)

    kind_title = {
        "ai": "Отчёт ИИ-детектора",
        "flagged": "Отчёт по обходу",
    }.get(kind, "Отчёт антиплагиата")

    story: list = []

    # Page 1: cover + overview (Turnitin-like, compact)
    title = check.work_title or check.filename or "Документ"
    if len(title) > 72:
        title = title[:71] + "…"
    story.append(Paragraph(esc(title), st["title"]))
    story.append(Paragraph("Markly", st["brand_sub"]))
    story.append(HRFlowable(width="100%", thickness=0.4, color=HexColor(LINE), spaceBefore=1, spaceAfter=8))
    story.append(Paragraph("Document Details", st["section"]))
    story.append(_cover_table(check, full_text, st, esc))
    if kind == "ai":
        story.extend(_overview_ai(check, mt_segments, st, esc))
    elif kind == "flagged":
        story.extend(_overview_flagged(flags, st, esc))
    else:
        story.extend(_overview_plagiarism(check, matches, flags, st, esc))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Verify: {settings.FRONTEND_URL}/verify/{check.id}",
        st["small"],
    ))

    # Page 2+: highlighted full text
    if full_text and highlight_spans_fn and segmentize_fn:
        story.append(PageBreak())
        spans, legend = ([], []) if kind == "flagged" else highlight_spans_fn(kind, check, matches, full_text)
        story.append(Paragraph(
            "Текст работы · выделено ИИ" if kind == "ai"
            else "Текст работы" if kind == "flagged"
            else "Текст работы · выделены совпадения",
            st["h2"],
        ))
        if legend:
            leg = "  ".join(f'<font backColor="#{c}">&nbsp;{esc(l)}&nbsp;</font>' for c, l in legend)
            story.append(Paragraph(leg, st["body"]))
            story.append(Spacer(1, 6))

        para_markups = [""]
        for seg_text, color in segmentize_fn(full_text, spans):
            for i, part in enumerate(seg_text.split("\n")):
                if i > 0:
                    para_markups.append("")
                piece = esc(part)
                if color and part:
                    piece = f'<font backColor="#{color}">{piece}</font>'
                para_markups[-1] += piece
        for mk in para_markups:
            if mk.strip():
                story.append(Paragraph(mk, st["body_text"]))

    buf = io.BytesIO()
    doc = _MarklyDocTemplate(buf, title=f"Markly — {kind_title}", submission_id=sid, kind=kind)
    doc.build(story)
    buf.seek(0)
    return buf.getvalue()
