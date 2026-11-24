"""
Слой векторного поиска: fastembed (ONNX, без PyTorch) + Qdrant.

Функции:
  ensure_collection()         — создать коллекцию при необходимости
  index_corpus_doc(...)       — нарезать на чанки, эмбеддировать, upsert в Qdrant
  delete_corpus_doc(doc_id)   — удалить все чанки документа из Qdrant
  search_similar_chunks(...)  — найти семантически близкие чанки к запросу

Модель (настраивается через EMBED_MODEL в .env):
  BAAI/bge-m3                 — 570M параметров, ONNX, ~1.1 GB (рек. для prod)
  BAAI/bge-small-en-v1.5     — 33 MB, только английский (для разработки)

Graceful degradation: если fastembed или Qdrant недоступны — функции
возвращают False/[] и не прерывают обработку проверки.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

COLLECTION_NAME = "corpus_embeddings"
_CHUNK_WINDOW = 3   # sentences per chunk
_CHUNK_STEP = 1     # sliding step

# ── Module-level singletons (lazy init) ──────────────────────────────────────
_model = None
_client = None
_vector_size: int | None = None


def _get_model():
    global _model
    if _model is not None:
        return _model
    try:
        from fastembed import TextEmbedding
        from app.config import settings
        _model = TextEmbedding(model_name=settings.EMBED_MODEL)
        logger.info("Loaded embedding model: %s", settings.EMBED_MODEL)
    except Exception as exc:
        logger.warning("Cannot load embedding model: %s", exc)
    return _model


def _get_client():
    global _client
    if _client is not None:
        return _client
    try:
        from qdrant_client import QdrantClient
        from app.config import settings
        if settings.QDRANT_URL:
            # Удалённый сервер Qdrant (например, через Docker)
            c = QdrantClient(url=settings.QDRANT_URL, timeout=5)
            c.get_collections()
        else:
            # Локальный режим на диске — без сервера и Docker
            c = QdrantClient(path=settings.QDRANT_PATH)
            c.get_collections()
        _client = c
    except Exception as exc:
        logger.warning("Qdrant unavailable: %s", exc)
    return _client


def _get_vector_size(model) -> int:
    global _vector_size
    if _vector_size is None:
        import numpy as np
        dummy = list(model.embed(["test"]))
        _vector_size = len(dummy[0])
    return _vector_size


# ── Collection setup ─────────────────────────────────────────────────────────

def ensure_collection() -> bool:
    """Create Qdrant collection if it doesn't exist. Returns True on success."""
    model = _get_model()
    client = _get_client()
    if model is None or client is None:
        return False
    try:
        from qdrant_client.models import Distance, VectorParams
        existing = {c.name for c in client.get_collections().collections}
        if COLLECTION_NAME not in existing:
            vec_size = _get_vector_size(model)
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=vec_size, distance=Distance.COSINE),
            )
            logger.info("Created Qdrant collection '%s' (dim=%d)", COLLECTION_NAME, vec_size)
        return True
    except Exception as exc:
        logger.error("ensure_collection failed: %s", exc)
        return False


# ── Chunking ─────────────────────────────────────────────────────────────────

def _chunk_with_positions(text: str) -> list[tuple[str, int, int]]:
    """
    Split text into overlapping sentence windows.
    Returns [(chunk_text, start_char, end_char), ...]
    """
    from app.services.shingles import split_sentences

    sentences = split_sentences(text)
    # Build char positions for each sentence
    pos_map: list[tuple[str, int, int]] = []
    pos = 0
    for sent in sentences:
        idx = text.find(sent, pos)
        if idx == -1:
            idx = pos
        pos_map.append((sent, idx, idx + len(sent)))
        pos = idx + len(sent)

    chunks: list[tuple[str, int, int]] = []
    n = len(pos_map)
    for i in range(0, max(1, n - _CHUNK_WINDOW + 1), _CHUNK_STEP):
        window = pos_map[i : i + _CHUNK_WINDOW]
        chunk_text = " ".join(s for s, _, _ in window)
        start = window[0][1]
        end = window[-1][2]
        if len(chunk_text.split()) >= 8:
            chunks.append((chunk_text, start, end))

    return chunks


def _chunk_id(corpus_doc_id: str, chunk_idx: int) -> str:
    """Deterministic UUID for a chunk."""
    return str(uuid.uuid5(uuid.NAMESPACE_OID, f"{corpus_doc_id}:{chunk_idx}"))


# ── Indexing ──────────────────────────────────────────────────────────────────

def index_corpus_doc(
    corpus_doc_id: str,
    title: str,
    content: str,
    url: Optional[str],
    language: str,
) -> bool:
    """Chunk content, embed, upsert all chunks into Qdrant."""
    model = _get_model()
    client = _get_client()
    if model is None or client is None:
        return False
    if not ensure_collection():
        return False

    try:
        from qdrant_client.models import PointStruct

        chunks = _chunk_with_positions(content)
        if not chunks:
            return False

        texts = [c[0] for c in chunks]
        embeddings = list(model.embed(texts))

        points = [
            PointStruct(
                id=_chunk_id(corpus_doc_id, idx),
                vector=emb.tolist(),
                payload={
                    "corpus_doc_id": corpus_doc_id,
                    "chunk_idx": idx,
                    "chunk_text": text[:400],
                    "source_title": title,
                    "source_url": url or "",
                    "source_lang": language,
                },
            )
            for idx, ((text, _s, _e), emb) in enumerate(zip(chunks, embeddings))
        ]

        # upsert in batches of 100
        for i in range(0, len(points), 100):
            client.upsert(collection_name=COLLECTION_NAME, points=points[i : i + 100])

        logger.info("Indexed %d chunks for corpus_doc %s", len(points), corpus_doc_id)
        return True
    except Exception as exc:
        logger.error("index_corpus_doc %s failed: %s", corpus_doc_id, exc)
        return False


def delete_corpus_doc(corpus_doc_id: str) -> bool:
    """Delete all Qdrant points belonging to a corpus document."""
    client = _get_client()
    if client is None:
        return False
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=Filter(
                must=[FieldCondition(key="corpus_doc_id", match=MatchValue(value=corpus_doc_id))]
            ),
        )
        return True
    except Exception as exc:
        logger.error("delete_corpus_doc %s failed: %s", corpus_doc_id, exc)
        return False


# ── Search ────────────────────────────────────────────────────────────────────

def _is_cross_lingual(doc_lang: str, source_lang: str) -> bool:
    """True if doc and source are in clearly different languages."""
    if not doc_lang or not source_lang or doc_lang == "mixed" or source_lang == "mixed":
        return False

    def base(lang: str) -> str:
        # uz-Latn and uz-Cyrl → "uz"
        return "uz" if lang.startswith("uz") else lang.split("-")[0]

    return base(doc_lang) != base(source_lang)


def search_similar_chunks(
    text: str,
    doc_language: str,
    threshold_same: float = 0.82,
    threshold_cross: float = 0.78,
    top_k: int = 5,
) -> list[dict]:
    """
    Find semantically similar corpus chunks for text.

    Returns list of:
      {start_char, end_char, chunk_text, score,
       source_title, source_url, source_lang, corpus_doc_id, is_cross_lingual}
    """
    model = _get_model()
    client = _get_client()
    if model is None or client is None:
        return []
    if not ensure_collection():
        return []

    chunks = _chunk_with_positions(text)
    if not chunks:
        return []

    results: list[dict] = []
    seen_ranges: set[tuple[int, int]] = set()

    for chunk_text, start, end in chunks:
        range_key = (start, end)
        if range_key in seen_ranges:
            continue
        try:
            vec = list(_get_model().embed([chunk_text]))[0].tolist()
            hits = client.search(
                collection_name=COLLECTION_NAME,
                query_vector=vec,
                limit=top_k,
                score_threshold=min(threshold_same, threshold_cross),
            )
            for hit in hits:
                payload = hit.payload or {}
                source_lang = payload.get("source_lang", "")
                cross = _is_cross_lingual(doc_language, source_lang)
                threshold = threshold_cross if cross else threshold_same

                if hit.score < threshold:
                    continue

                seen_ranges.add(range_key)
                results.append({
                    "start_char": start,
                    "end_char": end,
                    "chunk_text": chunk_text,
                    "score": float(hit.score),
                    "source_title": payload.get("source_title", ""),
                    "source_url": payload.get("source_url") or None,
                    "source_lang": source_lang,
                    "corpus_doc_id": payload.get("corpus_doc_id"),
                    "is_cross_lingual": cross,
                })
                break  # best hit per chunk position
        except Exception as exc:
            logger.warning("search_similar_chunks error at %d-%d: %s", start, end, exc)

    return results
