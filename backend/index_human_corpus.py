"""
Индексация среза human_corpus в Postgres + in-memory кэш шинглов.

Срез для демо (8 ГБ RAM):
  - 1500 файлов из ru/
  - 1500 файлов из uz_latin/
  - все файлы из uz_cyrillic/

Запуск из backend/:
  .venv/bin/python index_human_corpus.py
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from pathlib import Path

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.corpus import CorpusDocument
from app.services import corpus as corpus_service

CORPUS_ROOT = Path.home() / "Desktop" / "human_corpus"
LIMITS = {
    "ru": 1500,
    "uz_latin": 1500,
    "uz_cyrillic": None,  # все
}
LANG_MAP = {
    "ru": "ru",
    "uz_latin": "uz-Latn",
    "uz_cyrillic": "uz-Cyrl",
}


def _load_manifest() -> dict[str, dict]:
    path = CORPUS_ROOT / "manifest.jsonl"
    out: dict[str, dict] = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            file_key = row.get("file")
            if file_key:
                out[file_key] = row
    return out


def _pick_files(bucket: str, limit: int | None) -> list[Path]:
    folder = CORPUS_ROOT / bucket
    files = sorted(folder.glob("*.txt"))
    if limit is not None:
        files = files[:limit]
    return files


async def main() -> None:
    if not CORPUS_ROOT.is_dir():
        raise SystemExit(f"Corpus not found: {CORPUS_ROOT}")

    manifest = _load_manifest()
    selected: list[tuple[str, str, str, str]] = []  # title, lang, url, content

    for bucket, limit in LIMITS.items():
        files = _pick_files(bucket, limit)
        lang = LANG_MAP[bucket]
        print(f"{bucket}: selected {len(files)} files")
        for path in files:
            rel = f"{bucket}/{path.name}"
            meta = manifest.get(rel, {})
            try:
                content = path.read_text(encoding="utf-8-sig").strip()
            except Exception as exc:
                print(f"  skip {rel}: {exc}")
                continue
            if len(content.split()) < 30:
                continue
            title = (meta.get("url") or path.stem)[:500]
            if meta.get("url") and "article/n/" in meta["url"]:
                # shorter title from cyberleninka slug
                slug = meta["url"].rstrip("/").split("/")[-1]
                title = slug.replace("-", " ")[:500]
            elif bucket.startswith("uz"):
                title = path.stem
            url = meta.get("url") or f"file://human_corpus/{rel}"
            selected.append((title, lang, url, content))

    print(f"Total readable docs: {len(selected)}")

    async with AsyncSessionLocal() as db:
        existing = set(
            (await db.execute(select(CorpusDocument.content_hash))).scalars().all()
        )
        added = 0
        batch = 0
        for title, lang, url, content in selected:
            h = hashlib.sha256(content.encode("utf-8")).hexdigest()
            if h in existing:
                continue
            existing.add(h)
            doc_id = uuid.uuid4()
            db.add(
                CorpusDocument(
                    id=doc_id,
                    title=title,
                    url=url,
                    language=lang,
                    source_type="human_corpus",
                    content_hash=h,
                    content=content,
                    word_count=len(content.split()),
                    opensearch_id=str(doc_id),
                )
            )
            added += 1
            batch += 1
            if batch >= 100:
                await db.commit()
                print(f"  committed +{added} …")
                batch = 0
        if batch:
            await db.commit()
        print(f"Added to Postgres: {added}")

        rows = (await db.execute(select(CorpusDocument))).scalars().all()
        n = corpus_service.load_cache(rows)
        print(f"In-memory shingle cache: {n} documents")


if __name__ == "__main__":
    asyncio.run(main())
