"""
Управление корпусом документов (только superadmin).

POST   /api/v1/corpus          — добавить документ
GET    /api/v1/corpus          — список документов (пагинация)
DELETE /api/v1/corpus/{id}     — удалить документ
GET    /api/v1/corpus/stats    — размер корпуса
"""
from __future__ import annotations

import hashlib
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import superadmin_only
from app.database import get_db
from app.models.corpus import CorpusDocument
from app.schemas.corpus import CorpusDocumentIn, CorpusDocumentOut
from app.services import corpus as corpus_service
from app.services import embedder as embedder_service

router = APIRouter(prefix="/corpus", tags=["corpus"])


@router.get("/stats")
async def corpus_stats(_: None = Depends(superadmin_only)):
    count = await _run_sync(corpus_service.get_document_count)
    return {"opensearch_count": count}


@router.get("", response_model=list[CorpusDocumentOut])
async def list_corpus(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(superadmin_only),
):
    result = await db.execute(
        select(CorpusDocument).order_by(CorpusDocument.created_at.desc()).offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.post("", response_model=CorpusDocumentOut, status_code=201)
async def add_corpus_document(
    payload: CorpusDocumentIn,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(superadmin_only),
):
    content_hash = hashlib.sha256(payload.content.encode()).hexdigest()

    # Проверка дубликатов
    existing = await db.execute(
        select(CorpusDocument).where(CorpusDocument.content_hash == content_hash)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Document with this content already exists")

    doc_id = uuid.uuid4()
    word_count = len(payload.content.split())

    doc = CorpusDocument(
        id=doc_id,
        title=payload.title,
        url=payload.url,
        language=payload.language,
        source_type=payload.source_type,
        content_hash=content_hash,
        word_count=word_count,
        opensearch_id=str(doc_id),
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    import asyncio
    # Индексируем в OpenSearch (шинглы для точного поиска)
    await asyncio.to_thread(
        corpus_service.index_document,
        str(doc_id), payload.title, payload.content,
        payload.url, payload.language, payload.source_type,
    )
    # Индексируем в Qdrant (эмбеддинги для семантического поиска)
    await asyncio.to_thread(
        embedder_service.index_corpus_doc,
        str(doc_id), payload.title, payload.content,
        payload.url, payload.language,
    )

    return doc


@router.delete("/{doc_id}", status_code=204)
async def delete_corpus_document(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(superadmin_only),
):
    result = await db.execute(select(CorpusDocument).where(CorpusDocument.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    import asyncio
    await asyncio.to_thread(corpus_service.delete_document, str(doc_id))
    await asyncio.to_thread(embedder_service.delete_corpus_doc, str(doc_id))

    await db.delete(doc)
    await db.commit()


async def _run_sync(fn):
    import asyncio
    return await asyncio.to_thread(fn)
