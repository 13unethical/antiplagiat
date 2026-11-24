"""
Семантический антиплагиат через Qdrant + fastembed (BGE-M3).

Дополняет шингловый поиск (OpenSearch) двумя типами совпадений:
  paraphrase      — перефраз на том же языке (сходство ≥ 0.82)
  cross_lingual   — совпадение при смене языка, напр. RU→UZ (сходство ≥ 0.78)
                   подсвечивается фиолетовым в отчёте.

Работает синхронно — вызывать через asyncio.to_thread.
Если Qdrant или модель недоступны — возвращает пустой список (graceful degradation).
"""
from __future__ import annotations

import uuid
from typing import Optional

from app.services.embedder import search_similar_chunks
from app.services.plagiarism import MatchResult


def detect_semantic_plagiarism(
    normalized_text: str,
    language: str,
    already_covered: set[int] | None = None,
) -> list[MatchResult]:
    """
    Find semantically similar passages in the corpus.

    already_covered: set of char positions already matched by shingle detection.
    Skips chunks where >50% positions are already covered to avoid duplicates.
    """
    hits = search_similar_chunks(normalized_text, language)
    if not hits:
        return []

    results: list[MatchResult] = []
    for hit in hits:
        start, end = hit["start_char"], hit["end_char"]

        # Skip if already well-covered by shingle matches
        if already_covered and end > start:
            span = end - start
            overlap = sum(1 for i in range(start, min(end, start + 300)) if i in already_covered)
            if overlap > span * 0.5:
                continue

        try:
            corp_id: Optional[uuid.UUID] = uuid.UUID(hit["corpus_doc_id"]) if hit.get("corpus_doc_id") else None
        except (ValueError, AttributeError):
            corp_id = None

        match_kind = "cross_lingual" if hit["is_cross_lingual"] else "paraphrase"

        results.append(MatchResult(
            start_char=start,
            end_char=end,
            matched_text=hit["chunk_text"][:500],
            source_title=hit["source_title"],
            source_url=hit["source_url"],
            source_lang=hit["source_lang"],
            corpus_doc_id=corp_id,
            match_kind=match_kind,
            score=hit["score"],
        ))

    return results
