"""
Репозиторий проверенных работ.

Сохраняет текст работы в OpenSearch (шинглы) и Qdrant (эмбеддинги) с
source_type="repository" и source_url="repo://{org_id}/{repo_doc_id}".

Это позволяет обычной цепочке антиплагиата (plagiarism + semantic)
автоматически находить совпадения с репозиторием без изменения
основного пайплайна.

При отображении: если source_url.startswith("repo://") и org_id отличается
от org_id текущей проверки → показываем "Работа из другой организации".
"""
from __future__ import annotations

import re


def _repo_url(org_id: str, repo_doc_id: str) -> str:
    return f"repo://{org_id}/{repo_doc_id}"


def parse_repo_url(source_url: str) -> tuple[str, str] | None:
    """Return (org_id, repo_doc_id) or None if URL is not a repo URL."""
    m = re.match(r"^repo://([^/]+)/(.+)$", source_url or "")
    if not m:
        return None
    return m.group(1), m.group(2)


def index_to_repository(
    repo_doc_id: str,
    org_id: str,
    work_title: str,
    text: str,
    language: str,
) -> None:
    """
    Index a work into OpenSearch corpus as source_type='repository'.
    Silently skips on any error (graceful degradation).
    """
    try:
        from app.services import corpus as corpus_service
        corpus_service.index_document(
            repo_doc_id,
            work_title or "Работа из репозитория",
            text,
            _repo_url(org_id, repo_doc_id),
            language or "unknown",
            "repository",
        )
    except Exception:
        pass

    # Also index embeddings for semantic search
    try:
        from app.services import embedder as embedder_service
        embedder_service.index_corpus_doc(
            repo_doc_id,
            work_title or "Работа из репозитория",
            text,
            _repo_url(org_id, repo_doc_id),
            language or "unknown",
        )
    except Exception:
        pass


def delete_from_repository(repo_doc_id: str) -> None:
    """Remove a repository document from OpenSearch and Qdrant."""
    try:
        from app.services import corpus as corpus_service
        corpus_service.delete_document(repo_doc_id)
    except Exception:
        pass
    try:
        from app.services import embedder as embedder_service
        embedder_service.delete_corpus_doc(repo_doc_id)
    except Exception:
        pass
