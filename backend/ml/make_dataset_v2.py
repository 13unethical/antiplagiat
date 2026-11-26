#!/usr/bin/env python3
"""
Сборка dataset_v2 для ИИ-детектора.

Отличия от v1:
  - явные языковые ветки ru / uz-Latn / uz-Cyrl с целевым числом чанков;
  - делёж train/val/test строго по doc_id (нет утечки документов);
  - human-класс предпочитает «сухие» академические тексты до 2022 (из manifest).

Формат строки JSONL:
  {"text","label","lang","generator","doc_id","year"}

Пример:
  python make_dataset_v2.py \\
    --corpus ~/Desktop/human_corpus \\
    --ai-dir data/ai \\
    --out data/v2 \\
    --per-lang 6000
"""
from __future__ import annotations

import argparse
import json
import random
import re
from collections import defaultdict
from pathlib import Path

random.seed(42)

WINDOW_WORDS = 120
MIN_WINDOW = 40
LANGS = ("ru", "uz-Latn", "uz-Cyrl")
BUCKET = {
    "ru": "ru",
    "uz-Latn": "uz_latin",
    "uz-Cyrl": "uz_cyrillic",
}


def _windows(text: str) -> list[str]:
    words = text.split()
    if len(words) < MIN_WINDOW:
        return []
    if len(words) <= WINDOW_WORDS:
        return [text.strip()]
    out = []
    for i in range(0, len(words), WINDOW_WORDS):
        chunk = " ".join(words[i : i + WINDOW_WORDS]).strip()
        if len(chunk.split()) >= MIN_WINDOW:
            out.append(chunk)
    return out


def _load_manifest(corpus: Path) -> dict[str, dict]:
    path = corpus / "manifest.jsonl"
    out: dict[str, dict] = {}
    if not path.is_file():
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
            key = row.get("file")
            if key:
                out[key] = row
    return out


def _is_dry_academic(meta: dict, text: str) -> bool:
    """Сухие официальные/академические тексты до 2022 — для снижения FP."""
    year = meta.get("year")
    try:
        year_ok = year is None or int(year) <= 2022
    except (TypeError, ValueError):
        year_ok = True
    source = (meta.get("source") or "").lower()
    academic_src = any(s in source for s in ("cyberleninka", "wiki", "wikisource", "uzwiki"))
    # эвристика «сухости»: мало местоимений 1-го лица, есть маркеры академического стиля
    low = text.lower()
    first_person = len(re.findall(r"\b(я|мы|меня|мне|наш|мне кажется|честно)\b", low))
    academic_marks = sum(
        1
        for m in (
            "следует отметить",
            "таким образом",
            "в данной работе",
            "исследование",
            "tadqiqot",
            "shuni ta'kidlash",
            "xulosa",
            "мақола",
        )
        if m in low
    )
    return year_ok and (academic_src or academic_marks >= 1) and first_person <= 2


def _read_human(corpus: Path, per_lang: int, dry_ratio: float) -> list[dict]:
    manifest = _load_manifest(corpus)
    by_lang: dict[str, list[dict]] = {lang: [] for lang in LANGS}

    for lang in LANGS:
        folder = corpus / BUCKET[lang]
        if not folder.is_dir():
            print(f"  ! нет папки {folder}")
            continue
        files = sorted(folder.glob("*.txt"))
        dry_pool: list[dict] = []
        other_pool: list[dict] = []
        for path in files:
            rel = f"{BUCKET[lang]}/{path.name}"
            meta = manifest.get(rel, {})
            try:
                text = path.read_text(encoding="utf-8-sig").strip()
            except Exception:
                continue
            doc_id = f"human:{rel}"
            year = meta.get("year")
            for w in _windows(text):
                row = {
                    "text": w,
                    "label": 0,
                    "lang": lang,
                    "generator": "human",
                    "doc_id": doc_id,
                    "year": year,
                }
                if _is_dry_academic(meta, w):
                    dry_pool.append(row)
                else:
                    other_pool.append(row)

        target = per_lang
        n_dry = int(target * dry_ratio)
        random.shuffle(dry_pool)
        random.shuffle(other_pool)
        selected = dry_pool[:n_dry]
        need = target - len(selected)
        selected += other_pool[: max(0, need)]
        # если dry мало — добираем из dry остатка / other
        if len(selected) < target:
            rest = dry_pool[n_dry:] + other_pool[max(0, need) :]
            selected += rest[: target - len(selected)]
        by_lang[lang] = selected[:target]
        print(
            f"  human {lang:8s}: dry={min(len(dry_pool), n_dry)} "
            f"other={len(selected) - min(len(dry_pool), n_dry)} total={len(by_lang[lang])}"
        )

    rows: list[dict] = []
    for lang in LANGS:
        rows.extend(by_lang[lang])
    return rows


def _read_ai(ai_dir: Path, per_lang: int) -> list[dict]:
    """Читает data/ai/<generator>/<lang_folder>/*.txt."""
    folder_lang = {
        "ru": "ru",
        "uz_latin": "uz-Latn",
        "uz-latn": "uz-Latn",
        "uz_cyrillic": "uz-Cyrl",
        "uz-cyrl": "uz-Cyrl",
    }
    by_lang: dict[str, list[dict]] = {lang: [] for lang in LANGS}
    if not ai_dir.is_dir():
        print(f"  ! нет AI-папки {ai_dir}")
        return []

    for gen_dir in sorted(p for p in ai_dir.iterdir() if p.is_dir()):
        generator = gen_dir.name
        for lang_dir in sorted(p for p in gen_dir.rglob("*") if p.is_dir()):
            key = lang_dir.name.lower()
            if key not in folder_lang:
                continue
            lang = folder_lang[key]
            for path in sorted(lang_dir.glob("*.txt")):
                try:
                    text = path.read_text(encoding="utf-8").strip()
                except Exception:
                    continue
                doc_id = f"ai:{generator}:{lang}:{path.stem}"
                for w in _windows(text):
                    by_lang[lang].append(
                        {
                            "text": w,
                            "label": 1,
                            "lang": lang,
                            "generator": generator,
                            "doc_id": doc_id,
                            "year": None,
                        }
                    )

    rows: list[dict] = []
    for lang in LANGS:
        pool = by_lang[lang]
        random.shuffle(pool)
        # баланс AI ≈ human: берём до per_lang
        chosen = pool[:per_lang]
        print(f"  ai    {lang:8s}: pool={len(pool)} selected={len(chosen)}")
        rows.extend(chosen)
    return rows


def _split_by_doc(
    rows: list[dict],
    val_frac: float,
    test_frac: float,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Делёж по doc_id стратифицированно по (lang, label)."""
    groups: dict[tuple[str, int], dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        groups[(r["lang"], int(r["label"]))][r["doc_id"]].append(r)

    train, val, test = [], [], []
    for key, docs in groups.items():
        doc_ids = list(docs.keys())
        random.shuffle(doc_ids)
        n = len(doc_ids)
        n_test = max(1, int(n * test_frac)) if n >= 5 else 0
        n_val = max(1, int(n * val_frac)) if n >= 5 else 0
        test_ids = set(doc_ids[:n_test])
        val_ids = set(doc_ids[n_test : n_test + n_val])
        for did in doc_ids:
            bucket = docs[did]
            if did in test_ids:
                test.extend(bucket)
            elif did in val_ids:
                val.extend(bucket)
            else:
                train.extend(bucket)
    random.shuffle(train)
    random.shuffle(val)
    random.shuffle(test)
    return train, val, test


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows),
        encoding="utf-8",
    )


def _summary(name: str, rows: list[dict]) -> None:
    from collections import Counter

    print(f"{name}: {len(rows)}")
    by = Counter((r["lang"], r["label"]) for r in rows)
    for lang in LANGS:
        h = by[(lang, 0)]
        a = by[(lang, 1)]
        print(f"  {lang:8s} human={h:5d}  ai={a:5d}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(Path.home() / "Desktop" / "human_corpus"))
    ap.add_argument("--ai-dir", default="data/ai", help="папка ИИ-текстов (v1 или v2)")
    ap.add_argument("--out", default="data/v2")
    ap.add_argument("--per-lang", type=int, default=6000, help="целевых чанков на язык (на класс)")
    ap.add_argument("--dry-ratio", type=float, default=0.55, help="доля сухих academic human")
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--test-frac", type=float, default=0.10)
    args = ap.parse_args()

    corpus = Path(args.corpus).expanduser()
    ai_dir = Path(args.ai_dir).expanduser()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print("Human chunks:")
    human = _read_human(corpus, args.per_lang, args.dry_ratio)
    print("AI chunks:")
    ai = _read_ai(ai_dir, args.per_lang)
    rows = human + ai
    if not rows:
        raise SystemExit("Нет данных для dataset_v2")

    train, val, test = _split_by_doc(rows, args.val_frac, args.test_frac)
    _write_jsonl(out / "train.jsonl", train)
    _write_jsonl(out / "val.jsonl", val)
    _write_jsonl(out / "test.jsonl", test)
    meta = {
        "per_lang": args.per_lang,
        "dry_ratio": args.dry_ratio,
        "window_words": WINDOW_WORDS,
        "langs": list(LANGS),
        "counts": {
            "train": len(train),
            "val": len(val),
            "test": len(test),
            "human": sum(1 for r in rows if r["label"] == 0),
            "ai": sum(1 for r in rows if r["label"] == 1),
        },
    }
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    _summary("train", train)
    _summary("val", val)
    _summary("test", test)
    print("Готово →", out)


if __name__ == "__main__":
    main()
