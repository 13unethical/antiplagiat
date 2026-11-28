"""
Определение языка и письменности (раздел 2, шаг 4 ТЗ).

Возвращаемые значения:
  uz-Latn  — узбекский латиница
  uz-Cyrl  — узбекский кириллица
  ru       — русский
  en       — английский (→ DocMaxxing AI)
  mixed    — смешанный (несколько языков/письменностей)
  other    — другое

Алгоритм без внешних зависимостей (fastText/GlotLID — этап 7):
1. Соотношение латинских и кириллических символов → определяем письменность
2. Для кириллического текста: наличие уникальных узбекских букв ў қ ғ ҳ → uz-Cyrl, иначе ru
3. Для латинского: маркеры uz vs английские function words → uz-Latn / en
"""
from __future__ import annotations

import re


# Буквы, характерные только для узбекского кириллического алфавита
_UZ_CYRL_SPECIFIC = set("ўқғҳ")

# Узбекская латиница: oʻ, gʻ, apostrophe forms, frequent uz function words
_UZ_LATN_MARK = re.compile(
    r"[og][\u02BBʻʼ']|[oO][\u2018\u2019']|[gG][\u2018\u2019']|"
    r"\b(va|bilan|uchun|bo'yicha|boʻyicha|qilish|qiladi|hamda|lekin|shuningdek|"
    r"muhim|asosida|mavjud|kerak|emas|uchun|o'zbek|oʻzbek)\b",
    re.IGNORECASE,
)
_EN_FUNC = re.compile(
    r"\b(the|and|of|to|in|is|that|for|with|as|on|are|this|was|be|have|from|"
    r"or|by|an|not|which|their|can|will|been|would|about|more|also)\b",
    re.IGNORECASE,
)


def detect_language(text: str) -> str:
    if not text or not text.strip():
        return "other"

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

    if 0.2 <= lat_ratio <= 0.8:
        return "mixed"

    if lat_ratio > 0.8:
        uz_hits = len(_UZ_LATN_MARK.findall(text))
        en_hits = len(_EN_FUNC.findall(text))
        if uz_hits >= 2 and uz_hits >= en_hits:
            return "uz-Latn"
        if en_hits >= 3 and en_hits > uz_hits:
            return "en"
        if uz_hits > 0:
            return "uz-Latn"
        return "en" if en_hits > 0 else "other"

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
    "en": "Английский",
    "mixed": "Смешанный",
    "other": "Другой",
}

# Подсказка с формы проверки: auto | ru | uz | en
_HINTS = frozenset({"auto", "ru", "uz", "en"})


def resolve_language(text: str, hint: str | None = None) -> str:
    """Авто-детект с опциональным ручным выбором (ru / uz / en)."""
    detected = detect_language(text)
    h = (hint or "auto").strip().lower()
    if h in ("", "auto", "none"):
        return detected
    if h not in _HINTS:
        return detected
    if h == "ru":
        return "ru"
    if h == "en":
        return "en"
    # uz: сохраняем Latn/Cyrl если уже узбекский, иначе по письменности текста
    if detected in ("uz-Latn", "uz-Cyrl"):
        return detected
    cyr = sum(1 for c in text if 0x0400 <= ord(c) <= 0x04FF)
    lat = sum(
        1
        for c in text
        if (0x0041 <= ord(c) <= 0x005A) or (0x0061 <= ord(c) <= 0x007A)
    )
    return "uz-Cyrl" if cyr > lat else "uz-Latn"
