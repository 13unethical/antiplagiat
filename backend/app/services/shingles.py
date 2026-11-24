"""
Генерация шинглов и разбиение текста на предложения/параграфы.

Шингл — перекрывающаяся последовательность из N слов (sliding window).
Используется для поиска совпадений в OpenSearch.
"""
from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# Разбиение текста
# ---------------------------------------------------------------------------

_SENT_SPLIT = re.compile(r"(?<=[.!?…])\s+|(?<=\n)\s*")


def split_sentences(text: str) -> list[str]:
    """Делит текст на предложения по знакам препинания и переносам строк."""
    sentences = _SENT_SPLIT.split(text)
    return [s.strip() for s in sentences if s.strip()]


def split_paragraphs(text: str) -> list[str]:
    """Делит текст на параграфы (разделитель — двойной или одиночный перенос строки)."""
    paras = re.split(r"\n{2,}|\n", text)
    return [p.strip() for p in paras if p.strip()]


# ---------------------------------------------------------------------------
# Шинглы
# ---------------------------------------------------------------------------

def get_shingles(text: str, min_size: int = 5, max_size: int = 8) -> list[str]:
    """
    Возвращает все шинглы длиной от min_size до max_size слов.
    Текст нормализуется к lowercase перед разбиением.
    """
    words = text.lower().split()
    if len(words) < min_size:
        return []

    shingles: list[str] = []
    for size in range(min_size, min(max_size + 1, len(words) + 1)):
        for i in range(len(words) - size + 1):
            shingles.append(" ".join(words[i : i + size]))
    return shingles


def get_query_windows(text: str, window_words: int = 30, step_words: int = 15) -> list[str]:
    """
    Делит текст на перекрывающиеся окна для запросов к OpenSearch.
    Возвращает только окна длиннее 8 слов.
    """
    words = text.split()
    windows: list[str] = []
    for i in range(0, max(1, len(words) - window_words + 1), step_words):
        window = " ".join(words[i : i + window_words])
        if len(window.split()) >= 8:
            windows.append(window)
    return windows or ([text] if len(words) >= 8 else [])
