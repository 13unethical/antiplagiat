"""
Управление корпусом документов через OpenSearch.

Индекс `antiplagiat_corpus`:
  - Шингловый анализатор (5-8 слов) для быстрого поиска совпадений
  - more_like_this запросы для нахождения кандидатов-плагиата
  - Graceful degradation: если OpenSearch недоступен — возвращаем пустые результаты
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

INDEX_NAME = "antiplagiat_corpus"

INDEX_SETTINGS = {
    "settings": {
        "analysis": {
            "filter": {
                "shingle_5_8": {
                    "type": "shingle",
                    "min_shingle_size": 5,
                    "max_shingle_size": 8,
                    "output_unigrams": False,
                }
            },
            "analyzer": {
                "shingle_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "shingle_5_8"],
                }
            },
        }
    },
    "mappings": {
        "properties": {
            "doc_id": {"type": "keyword"},
            "title": {"type": "text"},
            "url": {"type": "keyword"},
            "language": {"type": "keyword"},
            "source_type": {"type": "keyword"},
            "content": {
                "type": "text",
                "analyzer": "shingle_analyzer",
                "store": True,
            },
            "content_plain": {
                "type": "text",
                "store": True,
            },
        }
    },
}


def _get_client():
    """Возвращает синхронный клиент OpenSearch или None если недоступен."""
    try:
        from opensearchpy import OpenSearch

        client = OpenSearch(
            hosts=[{"host": "localhost", "port": 9200}],
            http_compress=True,
            timeout=10,
            max_retries=1,
            retry_on_timeout=False,
        )
        client.info()  # проверка соединения
        return client
    except Exception as exc:
        logger.warning("OpenSearch unavailable: %s", exc)
        return None


def ensure_index() -> bool:
    """Создаёт индекс если не существует. Возвращает True при успехе."""
    client = _get_client()
    if client is None:
        return False
    try:
        if not client.indices.exists(index=INDEX_NAME):
            client.indices.create(index=INDEX_NAME, body=INDEX_SETTINGS)
            logger.info("Created OpenSearch index: %s", INDEX_NAME)
        return True
    except Exception as exc:
        logger.error("Failed to create index: %s", exc)
        return False


def index_document(
    doc_id: str,
    title: str,
    content: str,
    url: str | None,
    language: str,
    source_type: str,
) -> bool:
    """Добавляет документ в OpenSearch. Возвращает True при успехе."""
    client = _get_client()
    if client is None:
        return False
    ensure_index()
    try:
        client.index(
            index=INDEX_NAME,
            id=doc_id,
            body={
                "doc_id": doc_id,
                "title": title,
                "url": url or "",
                "language": language,
                "source_type": source_type,
                "content": content,
                "content_plain": content,
            },
        )
        return True
    except Exception as exc:
        logger.error("Failed to index document %s: %s", doc_id, exc)
        return False


def delete_document(doc_id: str) -> bool:
    """Удаляет документ из OpenSearch."""
    client = _get_client()
    if client is None:
        return False
    try:
        client.delete(index=INDEX_NAME, id=doc_id, ignore=[404])
        return True
    except Exception as exc:
        logger.error("Failed to delete document %s: %s", doc_id, exc)
        return False


def search_similar(
    query_text: str,
    language: str | None = None,
    top_k: int = 10,
) -> list[dict]:
    """
    Ищет документы, похожие на query_text, через more_like_this.
    Возвращает список: [{doc_id, title, url, language, content, score}]
    """
    client = _get_client()
    if client is None:
        return []

    mlt_query: dict = {
        "query": {
            "bool": {
                "must": [
                    {
                        "more_like_this": {
                            "fields": ["content"],
                            "like": query_text,
                            "min_term_freq": 1,
                            "max_query_terms": 30,
                            "min_doc_freq": 1,
                            "minimum_should_match": "25%",
                        }
                    }
                ],
                "filter": [],
            }
        },
        "size": top_k,
        "stored_fields": ["content_plain"],
        "_source": ["doc_id", "title", "url", "language"],
    }

    # Фильтр по языку (опционально)
    if language and language not in ("mixed", "other"):
        mlt_query["query"]["bool"]["filter"].append(
            {"term": {"language": language}}
        )

    try:
        resp = client.search(index=INDEX_NAME, body=mlt_query)
        results = []
        for hit in resp["hits"]["hits"]:
            src = hit["_source"]
            # Извлекаем хранимое поле content_plain
            stored = hit.get("fields", {})
            content_parts = stored.get("content_plain", [])
            content = content_parts[0] if content_parts else ""
            results.append(
                {
                    "doc_id": src.get("doc_id", hit["_id"]),
                    "title": src.get("title", ""),
                    "url": src.get("url", ""),
                    "language": src.get("language", ""),
                    "content": content,
                    "score": hit["_score"],
                }
            )
        return results
    except Exception as exc:
        logger.warning("OpenSearch search failed: %s", exc)
        return []


def get_document_count() -> int:
    """Возвращает количество документов в корпусе."""
    client = _get_client()
    if client is None:
        return 0
    try:
        resp = client.count(index=INDEX_NAME)
        return resp.get("count", 0)
    except Exception:
        return 0
