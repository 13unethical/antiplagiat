"""
Flagged-модуль: проверки на попытки обхода на СЫРОМ тексте (до нормализации).

Реализованные проверки (раздел 6 ТЗ):
1. homoglyph       — смешение латиницы и кириллицы внутри одного слова
2. invisible_char  — невидимые символы (U+200B, U+200C, U+00AD и др.)
3. hidden_text     — скрытый текст в DOCX (передаётся из парсера)
4. spaced_text     — разрядка (р а з р я д к а)
5. quote_abuse     — злоупотребление кавычками (> 25% текста в кавычках)
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.parser import ParseResult


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _char_script(c: str) -> str:
    """Возвращает 'latin', 'cyrillic' или 'other'."""
    cp = ord(c)
    if (0x0041 <= cp <= 0x005A) or (0x0061 <= cp <= 0x007A) or (0x00C0 <= cp <= 0x024F):
        return "latin"
    if 0x0400 <= cp <= 0x04FF:
        return "cyrillic"
    return "other"


# Невидимые и необычные пробельные символы
INVISIBLE_CHARS: dict[str, str] = {
    "\u200B": "ZERO WIDTH SPACE",
    "\u200C": "ZERO WIDTH NON-JOINER",
    "\u200D": "ZERO WIDTH JOINER",
    "\u2060": "WORD JOINER",
    "\uFEFF": "ZERO WIDTH NO-BREAK SPACE (BOM)",
    "\u00AD": "SOFT HYPHEN",
    "\u2028": "LINE SEPARATOR",
    "\u2029": "PARAGRAPH SEPARATOR",
    "\u00A0": "NON-BREAKING SPACE",
    "\u2007": "FIGURE SPACE",
    "\u202F": "NARROW NO-BREAK SPACE",
}

# Символы узбекских апострофов — не являются смешением письменностей
UZ_APOSTROPHES = {"\u02BB", "\u02BC", "\u2018", "\u2019", "\u0027", "\u0060"}

# Узорные кавычки для поиска цитат
QUOTE_OPEN = "«\u201C\u2018\""
QUOTE_CLOSE = "»\u201D\u2019\""


# ---------------------------------------------------------------------------
# DataClass результата
# ---------------------------------------------------------------------------

@dataclass
class FlagResult:
    type: str
    severity: str
    count: int
    details: dict


# ---------------------------------------------------------------------------
# Проверки
# ---------------------------------------------------------------------------

def _check_homoglyphs(text: str) -> FlagResult | None:
    """
    Флаг: слово содержит буквы из обеих письменностей (латиница + кириллица).
    Исключение: апострофы oʻ / gʻ не считаются смешением.
    """
    # Ищем последовательности латинских и кириллических символов
    word_re = re.compile(r"[a-zA-Z\u00C0-\u024F\u0400-\u04FF\u02BB\u02BC]+")
    flagged: list[dict] = []

    for match in word_re.finditer(text):
        word = match.group()
        # Убираем апострофы из анализа
        chars = [c for c in word if c not in UZ_APOSTROPHES]

        has_latin = any(_char_script(c) == "latin" for c in chars)
        has_cyrillic = any(_char_script(c) == "cyrillic" for c in chars)

        if has_latin and has_cyrillic:
            details_chars = [
                {"char": c, "cp": f"U+{ord(c):04X}", "script": _char_script(c)}
                for c in chars
                if _char_script(c) in ("latin", "cyrillic")
            ]
            flagged.append(
                {"word": word, "position": match.start(), "chars": details_chars}
            )

    if not flagged:
        return None

    total_suspicious = sum(len(w["chars"]) for w in flagged)
    return FlagResult(
        type="homoglyph",
        severity="high",
        count=total_suspicious,
        details={"word_count": len(flagged), "examples": flagged[:10]},
    )


def _check_invisible_chars(text: str) -> FlagResult | None:
    """Флаг: в тексте есть невидимые символы."""
    found: dict[str, int] = {}
    for char, name in INVISIBLE_CHARS.items():
        cnt = text.count(char)
        if cnt:
            found[name] = cnt

    if not found:
        return None

    total = sum(found.values())
    # Строгость зависит от количества: единицы — medium, много — high
    severity = "high" if total > 5 else "medium" if total > 1 else "low"
    return FlagResult(
        type="invisible_char",
        severity=severity,
        count=total,
        details={"by_type": found},
    )


def _check_spaced_text(text: str) -> FlagResult | None:
    """
    Флаг: разрядка — слова, разбитые пробелами на отдельные буквы.
    Пример: «р а з р я д к а» или «s p a c e d».
    Ищем 3+ одиночных буквы подряд, разделённых пробелами.
    """
    # Одиночная буква (Latin или Cyrillic), за ней пробел, снова буква
    pattern = re.compile(
        r"(?<![^\s])[а-яёА-ЯЁa-zA-Z\u00C0-\u024F]"
        r"(?:\s[а-яёА-ЯЁa-zA-Z\u00C0-\u024F]){2,}(?![^\s])"
    )
    matches = pattern.findall(text)
    if not matches:
        return None

    return FlagResult(
        type="spaced_text",
        severity="medium",
        count=len(matches),
        details={"examples": matches[:10]},
    )


def _check_quote_abuse(text: str) -> FlagResult | None:
    """
    Флаг: в кавычках находится более 25% текста документа.
    В этом случае исключение цитат отключается.
    """
    # Находим всё содержимое в кавычках
    pattern = re.compile(r"[«\u201C\u2018\"][^»\u201D\u2019\"]{5,}[»\u201D\u2019\"]")
    quoted_parts = pattern.findall(text)
    quoted_len = sum(len(p) for p in quoted_parts)
    text_len = len(text.strip())

    if text_len == 0 or quoted_len == 0:
        return None

    ratio = quoted_len / text_len
    if ratio <= 0.25:
        return None

    return FlagResult(
        type="quote_abuse",
        severity="medium",
        count=len(quoted_parts),
        details={
            "quoted_percent": round(ratio * 100, 1),
            "note": "Citation exclusion disabled for this document",
        },
    )


def _check_hidden_text(hidden_paragraphs: list[str]) -> FlagResult | None:
    """Флаг из скрытых параграфов, найденных парсером DOCX."""
    if not hidden_paragraphs:
        return None
    total_chars = sum(len(p) for p in hidden_paragraphs)
    return FlagResult(
        type="hidden_text",
        severity="high",
        count=len(hidden_paragraphs),
        details={
            "paragraph_count": len(hidden_paragraphs),
            "total_chars": total_chars,
            "examples": [p[:100] for p in hidden_paragraphs[:5]],
        },
    )


# ---------------------------------------------------------------------------
# Главная функция
# ---------------------------------------------------------------------------

def run_flagged_checks(raw_text: str, parse_result: "ParseResult") -> list[FlagResult]:
    """
    Запускает все Flagged-проверки на сыром тексте.
    Возвращает список найденных флагов (пустой список = чисто).
    """
    flags: list[FlagResult] = []

    for check_fn in [
        lambda: _check_homoglyphs(raw_text),
        lambda: _check_invisible_chars(raw_text),
        lambda: _check_spaced_text(raw_text),
        lambda: _check_quote_abuse(raw_text),
        lambda: _check_hidden_text(parse_result.hidden_paragraphs),
    ]:
        result = check_fn()
        if result is not None:
            flags.append(result)

    return flags
