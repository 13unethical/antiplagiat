"""
Парсинг DOCX и PDF файлов.

Извлекает:
- raw_text: исходный текст (до нормализации)
- position_map: карта позиций параграфов/страниц для подсветки
- hidden_paragraphs: скрытый текст в DOCX (w:vanish, белый цвет, размер ≤ 2pt)
- page_count: число страниц (PDF)
- ocr_used: был ли задействован OCR (Tesseract, опционально)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParseResult:
    raw_text: str
    position_map: list[dict]
    file_type: str
    page_count: int | None = None
    hidden_paragraphs: list[str] = field(default_factory=list)
    ocr_used: bool = False


def _parse_docx(path: str) -> ParseResult:
    from docx import Document
    from docx.oxml.ns import qn

    doc = Document(path)
    paragraphs: list[str] = []
    hidden_paras: list[str] = []
    position_map: list[dict] = []
    char_offset = 0

    for i, para in enumerate(doc.paragraphs):
        visible_parts: list[str] = []
        hidden_parts: list[str] = []

        for run in para.runs:
            rpr = run._r.find(qn("w:rPr"))
            is_run_hidden = False

            if rpr is not None:
                # w:vanish — hidden attribute
                if rpr.find(qn("w:vanish")) is not None:
                    is_run_hidden = True

                # White text colour
                color_el = rpr.find(qn("w:color"))
                if color_el is not None:
                    val = color_el.get(qn("w:val"), "").upper().replace(" ", "")
                    if val in ("FFFFFF",):
                        is_run_hidden = True

                # Font size ≤ 2pt (sz value is in half-points, so ≤ 4)
                sz_el = rpr.find(qn("w:sz"))
                if sz_el is not None:
                    try:
                        if int(sz_el.get(qn("w:val"), "24")) <= 4:
                            is_run_hidden = True
                    except ValueError:
                        pass

            if is_run_hidden:
                hidden_parts.append(run.text)
            else:
                visible_parts.append(run.text)

        para_text = "".join(visible_parts)
        hidden_text = "".join(hidden_parts)

        if hidden_text.strip():
            hidden_paras.append(hidden_text.strip())

        if para_text:
            start = char_offset
            end = char_offset + len(para_text)
            position_map.append(
                {"para_idx": i, "start": start, "end": end, "preview": para_text[:80]}
            )
            paragraphs.append(para_text)
            char_offset = end + 1

    raw_text = "\n".join(paragraphs)
    return ParseResult(
        raw_text=raw_text,
        position_map=position_map,
        file_type="docx",
        hidden_paragraphs=hidden_paras,
    )


def _parse_pdf(path: str) -> ParseResult:
    from pypdf import PdfReader

    reader = PdfReader(path)
    pages: list[str] = []
    position_map: list[dict] = []
    char_offset = 0
    ocr_used = False

    for page_num, page in enumerate(reader.pages):
        text = page.extract_text() or ""

        # If page has very little text, try OCR (optional — requires Tesseract)
        if len(text.strip()) < 50:
            try:
                import io
                import pytesseract
                from PIL import Image

                # pypdf doesn't render pages to images; skip OCR here
                # OCR will be added in a future stage with a rendering library
                pass
            except Exception:
                pass

        if text.strip():
            start = char_offset
            end = char_offset + len(text)
            position_map.append(
                {"page": page_num + 1, "start": start, "end": end, "preview": text[:80]}
            )
            pages.append(text)
            char_offset = end + 1

    raw_text = "\n".join(pages)
    return ParseResult(
        raw_text=raw_text,
        position_map=position_map,
        file_type="pdf",
        page_count=len(reader.pages),
        ocr_used=ocr_used,
    )


def _parse_txt(path: str) -> ParseResult:
    """Парсинг обычного текстового файла (вставка текста пользователем)."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    paragraphs = [p.strip() for p in text.splitlines() if p.strip()]
    position_map: list[dict] = []
    char_offset = 0
    for i, para in enumerate(paragraphs):
        position_map.append(
            {"para_idx": i, "start": char_offset, "end": char_offset + len(para), "preview": para[:80]}
        )
        char_offset += len(para) + 1
    return ParseResult(
        raw_text="\n".join(paragraphs),
        position_map=position_map,
        file_type="txt",
    )


def parse_file(path: str, filename: str) -> ParseResult:
    """Определяет тип файла и вызывает нужный парсер."""
    suffix = Path(filename).suffix.lower()
    if suffix == ".docx":
        return _parse_docx(path)
    elif suffix == ".pdf":
        return _parse_pdf(path)
    elif suffix == ".txt":
        return _parse_txt(path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}. Supported: .docx, .pdf, .txt")
