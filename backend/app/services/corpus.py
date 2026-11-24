"""
Корпус для точного/почти-точного поиска плагиата — без Docker/OpenSearch.

Полный текст документов хранится в PostgreSQL (CorpusDocument.content),
а для быстрого поиска кандидатов в памяти держится индекс шинглов
(хэши 5-словных окон). Семантический слой (перефраз/межъязыковое) —
отдельно в embedder.py (Qdrant, локальный режим).

Публичный API синхронный (вызывается из потоков через asyncio.to_thread):
  index_document(...)      — добавить/обновить документ в кэше
  search_similar(...)      — кандидаты по пересечению шинглов
  delete_document(id)      — убрать документ из кэша
  get_document_count()     — размер корпуса в памяти
  load_cache(rows)         — загрузить кэш из строк Postgres (при старте)
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"\w+", re.UNICODE)
_SHINGLE_SIZE = 5
_MASK = (1 << 64) - 1

# Кэш: doc_id(str) -> {title, url, language, content, shingles:set[int]}
_CACHE: dict[str, dict] = {}


def _shingle_hashes(text: str, size: int = _SHINGLE_SIZE) -> set[int]:
    words = _WORD_RE.findall(text.lower())
    if len(words) < size:
        return set()
    return {
        hash(" ".join(words[i : i + size])) & _MASK
        for i in range(len(words) - size + 1)
    }


def index_document(
    doc_id: str,
    title: str,
    content: str,
    url: str | None,
    language: str,
    source_type: str,
) -> bool:
    """Добавляет/обновляет документ в кэше шинглов. Persist в Postgres делает вызывающий код."""
    if not content:
        return False
    _CACHE[str(doc_id)] = {
        "title": title,
        "url": url or "",
        "language": language,
        "source_type": source_type,
        "content": content,
        "shingles": _shingle_hashes(content),
    }
    return True


def delete_document(doc_id: str) -> bool:
    return _CACHE.pop(str(doc_id), None) is not None


def get_document_count() -> int:
    return len(_CACHE)


def load_cache(rows) -> int:
    """Загружает кэш из строк CorpusDocument (ожидаются поля id,title,url,language,content,source_type)."""
    _CACHE.clear()
    n = 0
    for r in rows:
        content = getattr(r, "content", None)
        if not content:
            continue
        index_document(
            str(getattr(r, "id")),
            getattr(r, "title", "") or "",
            content,
            getattr(r, "url", None),
            getattr(r, "language", "ru") or "ru",
            getattr(r, "source_type", "web") or "web",
        )
        n += 1
    logger.info("Corpus cache loaded: %d documents", n)
    return n


def search_similar(
    query_text: str,
    language: str | None = None,
    top_k: int = 10,
) -> list[dict]:
    """
    Возвращает кандидатов по пересечению шинглов:
      [{doc_id, title, url, language, content, score}]
    score — число совпавших шинглов (для ранжирования).
    """
    qh = _shingle_hashes(query_text)
    if not qh or not _CACHE:
        return []

    scored: list[tuple[int, str, dict]] = []
    for doc_id, entry in _CACHE.items():
        if language and language not in ("mixed", "other") and entry["language"] not in (language, "mixed"):
            # мягкий фильтр: разрешаем совпадение и при несовпадении языка (межъязыковое ловит embedder),
            # но для точного поиска приоритет тому же языку — не отбрасываем полностью
            pass
        overlap = len(qh & entry["shingles"])
        if overlap > 0:
            scored.append((overlap, doc_id, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for overlap, doc_id, entry in scored[:top_k]:
        out.append({
            "doc_id": doc_id,
            "title": entry["title"],
            "url": entry["url"],
            "language": entry["language"],
            "content": entry["content"],
            "score": overlap,
        })
    return out


# Совместимость со старым API (OpenSearch): no-op
def ensure_index() -> bool:
    return True
