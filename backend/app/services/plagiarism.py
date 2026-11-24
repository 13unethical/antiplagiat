"""
Обнаружение плагиата на основе OpenSearch + rapidfuzz.

Алгоритм:
1. Разбиваем текст на скользящие окна (30 слов, шаг 15)
2. Ищем кандидатов через OpenSearch more_like_this
3. Для каждого кандидата делаем точечное выравнивание через rapidfuzz
4. Применяем исключения: цитаты, библиография, шаблонные фразы, < 8 слов
5. Считаем покрытие уникальных символов (без двойного счёта)
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Optional

from app.services import corpus as corpus_service
from app.services.shingles import split_sentences, get_query_windows


# ---------------------------------------------------------------------------
# Шаблонные исключения
# ---------------------------------------------------------------------------
_TEMPLATE_PHRASES = [
    "в данной работе", "целью данной работы", "в ходе работы",
    "данная работа посвящена", "в заключение можно сказать",
    "таким образом", "следует отметить", "необходимо отметить",
    "как известно", "в настоящее время", "в современных условиях",
    "ushbu ishda", "ushbu tadqiqot", "xulosa qilib aytish mumkin",
    "список литературы", "список использованных источников",
    "библиографический список", "references",
]

_BIBLIOGRAPHY_RE = re.compile(r"^\s*(\d+\.|[•\-\*]|\[\d+\])\s", re.IGNORECASE)
_QUOTE_RE = re.compile(r'^\s*[«»""\'"]')


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class MatchResult:
    start_char: int
    end_char: int
    matched_text: str
    source_title: str
    source_url: Optional[str]
    source_lang: str
    corpus_doc_id: Optional[uuid.UUID]
    match_kind: str  # exact | paraphrase
    score: float


@dataclass
class PlagiarismResult:
    similarity_percent: float
    sources_count: int
    matches: list[MatchResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Exclusion logic
# ---------------------------------------------------------------------------
def _is_excluded(sentence: str) -> bool:
    """True если предложение следует исключить из проверки плагиата."""
    s = sentence.strip()
    if len(s.split()) < 8:
        return True
    if _QUOTE_RE.match(s):
        return True
    if _BIBLIOGRAPHY_RE.match(s):
        return True
    s_lower = s.lower()
    return any(phrase in s_lower for phrase in _TEMPLATE_PHRASES)


# ---------------------------------------------------------------------------
# Core detection
# ---------------------------------------------------------------------------
def detect_plagiarism(
    normalized_text: str,
    language: Optional[str] = None,
    top_k: int = 10,
) -> PlagiarismResult:
    """
    Запускает антиплагиат для нормализованного текста.
    Работает синхронно — вызывать через asyncio.to_thread из async-кода.
    """
    if not normalized_text or len(normalized_text.split()) < 10:
        return PlagiarismResult(similarity_percent=0.0, sources_count=0)

    # 1. Собираем кандидатов из OpenSearch
    windows = get_query_windows(normalized_text, window_words=30, step_words=15)
    candidate_map: dict[str, dict] = {}  # doc_id → лучший hit

    for window in windows:
        hits = corpus_service.search_similar(window, language=language, top_k=top_k)
        for hit in hits:
            doc_id = hit["doc_id"]
            if doc_id not in candidate_map or hit["score"] > candidate_map[doc_id]["score"]:
                candidate_map[doc_id] = hit

    if not candidate_map:
        return PlagiarismResult(similarity_percent=0.0, sources_count=0)

    # 2. Детальное выравнивание через rapidfuzz
    try:
        from rapidfuzz import fuzz
        from rapidfuzz import process as rfprocess
    except ImportError:
        return PlagiarismResult(similarity_percent=0.0, sources_count=0)

    # Вычисляем позиции предложений в тексте
    query_sentences = split_sentences(normalized_text)
    sentence_positions: list[tuple[int, int]] = []
    pos = 0
    for sent in query_sentences:
        idx = normalized_text.find(sent, pos)
        if idx == -1:
            idx = pos
        sentence_positions.append((idx, idx + len(sent)))
        pos = idx + len(sent)

    all_matches: list[MatchResult] = []
    covered: set[int] = set()  # покрытые символьные позиции

    for candidate in candidate_map.values():
        corpus_text = candidate.get("content", "")
        if not corpus_text:
            continue

        corpus_sentences = split_sentences(corpus_text)
        if not corpus_sentences:
            continue

        for q_sent, (start, end) in zip(query_sentences, sentence_positions):
            if _is_excluded(q_sent):
                continue

            best = rfprocess.extractOne(
                q_sent,
                corpus_sentences,
                scorer=fuzz.token_sort_ratio,
                score_cutoff=70,
            )
            if best is None:
                continue

            matched_corpus_sent, score, _ = best
            score_norm = score / 100.0

            exact_score = fuzz.ratio(q_sent, matched_corpus_sent)
            match_kind = "exact" if exact_score >= 90 else "paraphrase"

            raw_id = candidate.get("doc_id", "")
            try:
                corp_doc_id = uuid.UUID(str(raw_id))
            except (ValueError, AttributeError):
                corp_doc_id = None

            all_matches.append(
                MatchResult(
                    start_char=start,
                    end_char=end,
                    matched_text=q_sent[:500],
                    source_title=candidate.get("title", ""),
                    source_url=candidate.get("url") or None,
                    source_lang=candidate.get("language", "ru"),
                    corpus_doc_id=corp_doc_id,
                    match_kind=match_kind,
                    score=score_norm,
                )
            )
            covered.update(range(start, end))

    # 3. Similarity %
    total_chars = len(normalized_text.strip())
    similarity_percent = (len(covered) / total_chars * 100) if total_chars > 0 else 0.0
    similarity_percent = round(min(similarity_percent, 100.0), 2)

    sources = {m.source_title for m in all_matches if m.source_title}

    return PlagiarismResult(
        similarity_percent=similarity_percent,
        sources_count=len(sources),
        matches=all_matches,
    )
