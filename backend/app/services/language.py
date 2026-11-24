"""
Определение языка и письменности (раздел 2, шаг 4 ТЗ).

Возвращаемые значения:
  uz-Latn  — узбекский латиница
  uz-Cyrl  — узбекский кириллица
  ru       — русский
  mixed    — смешанный (несколько языков/письменностей)
  other    — другое

Алгоритм без внешних зависимостей (fastText/GlotLID — этап 7):
1. Соотношение латинских и кириллических символов → определяем письменность
2. Для кириллического текста: наличие уникальных узбекских букв ў қ ғ ҳ → uz-Cyrl, иначе ru
3. Для латинского: наличие ʻ, oʻ, gʻ → uz-Latn
"""
from __future__ import annotations

import re


# Буквы, характерные только для узбекского кириллического алфавита
_UZ_CYRL_SPECIFIC = set("ўқғҳ")

# Паттерн для узбекских латинских сочетаний
_UZ_LATN_PATTERN = re.compile(r"[og]\u02BB|sh|ch|ng", re.IGNORECASE)


def detect_language(text: str) -> str:
    if not text or not text.strip():
        return "other"

    # Подсчёт букв по письменностям
    latin_chars = [
        c for c in text
        if (0x0041 <= ord(c) <= 0x005A) or (0x0061 <= ord(c) <= 0x007A) or (0x00C0 <= ord(c) <= 0x024F)
    ]
    cyrillic_chars = [c for c in text if 0x0400 <= ord(c) <= 0x04FF]

    lat_count = len(latin_chars)
    cyr_count = len(cyrillic_chars)
    total = lat_count + cyr_count

    if total == 0:
        return "other"

    lat_ratio = lat_count / total
    cyr_ratio = cyr_count / total

    # Смешанный текст
    if 0.2 <= lat_ratio <= 0.8:
        return "mixed"

    # Преимущественно латиница
    if lat_ratio > 0.8:
        if _UZ_LATN_PATTERN.search(text) or any(c == "\u02BB" for c in text):
            return "uz-Latn"
        return "uz-Latn"  # Латиница без спецификов — всё равно uz-Latn (вероятнее всего)

    # Преимущественно кириллица
    if cyr_ratio > 0.8:
        uz_specific = sum(1 for c in text if c in _UZ_CYRL_SPECIFIC)
        if uz_specific > 0:
            return "uz-Cyrl"
        return "ru"

    return "other"


LANGUAGE_LABELS: dict[str, str] = {
    "uz-Latn": "Узбекский (латиница)",
    "uz-Cyrl": "Узбекский (кириллица)",
    "ru": "Русский",
    "mixed": "Смешанный",
    "other": "Другой",
}
