"""
Нормализация текста (раздел 2, шаг 3 ТЗ):
1. NFC — каноническая декомпозиция + каноническая композиция
2. Единые апострофы узбекского: ' ' ʻ ʼ ' ` → ʻ (U+02BB)
3. Удаление невидимых символов
4. Нормализация гомоглифов: привести буквы к основной письменности документа
"""
from __future__ import annotations

import re
import unicodedata

from app.services.flagged import INVISIBLE_CHARS

# Апострофы, которые приводим к единому виду ʻ (U+02BB)
APOSTROPHE_VARIANTS = ["\u2018", "\u2019", "\u02BC", "\u0060", "\u0027"]
CANONICAL_APOSTROPHE = "\u02BB"

# Таблица конфузаблов: латинский символ → его кириллический двойник
# Используется для приведения гомоглифов в кириллическом тексте
_LAT_TO_CYR: dict[str, str] = {
    "a": "а", "A": "А",
    "e": "е", "E": "Е",
    "o": "о", "O": "О",
    "p": "р", "P": "Р",
    "c": "с", "C": "С",
    "x": "х", "X": "Х",
    "y": "у", "Y": "У",
    "B": "В",
    "H": "Н",
    "T": "Т",
    "K": "К",
    "M": "М",
}

# Обратная таблица: кириллический → латинский (для латинского текста)
_CYR_TO_LAT: dict[str, str] = {v: k for k, v in _LAT_TO_CYR.items()}


def _dominant_script(text: str) -> str:
    """Определяет преобладающую письменность: 'latin', 'cyrillic' или 'mixed'."""
    lat = sum(1 for c in text if (0x0041 <= ord(c) <= 0x005A) or (0x0061 <= ord(c) <= 0x007A))
    cyr = sum(1 for c in text if 0x0400 <= ord(c) <= 0x04FF)
    if lat + cyr == 0:
        return "other"
    if lat / (lat + cyr) > 0.7:
        return "latin"
    if cyr / (lat + cyr) > 0.7:
        return "cyrillic"
    return "mixed"


def normalize_apostrophes(text: str) -> str:
    """Приводит все варианты апострофов к ʻ (U+02BB)."""
    for variant in APOSTROPHE_VARIANTS:
        text = text.replace(variant, CANONICAL_APOSTROPHE)
    return text


def remove_invisible(text: str) -> str:
    """Удаляет невидимые и управляющие символы."""
    for char in INVISIBLE_CHARS:
        text = text.replace(char, "")
    return text


def fix_homoglyphs(text: str, script: str) -> str:
    """
    Приводит конфузабельные символы к письменности документа.
    Если документ кириллический — латинские a/e/o/p/c/x/y внутри слов заменяются на кириллические.
    Если латинский — наоборот.
    Работает посимвольно внутри слов.
    """
    if script == "mixed" or script == "other":
        return text

    table = _LAT_TO_CYR if script == "cyrillic" else _CYR_TO_LAT

    # Заменяем только внутри «слов» (последовательностей букв)
    word_re = re.compile(r"[a-zA-Z\u00C0-\u024F\u0400-\u04FF\u02BB\u02BC]+")

    def replace_word(m: re.Match) -> str:
        word = m.group()
        return "".join(table.get(c, c) for c in word)

    return word_re.sub(replace_word, text)


def normalize_text(raw_text: str) -> str:
    """Полная нормализация текста по порядку из ТЗ."""
    text = unicodedata.normalize("NFC", raw_text)
    text = normalize_apostrophes(text)
    text = remove_invisible(text)
    script = _dominant_script(text)
    text = fix_homoglyphs(text, script)
    return text
