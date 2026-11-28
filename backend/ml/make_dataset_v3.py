#!/usr/bin/env python3
"""
Датасет v3 для XLM-RoBERTa (SPEC §3): обёртка над make_dataset_v2.

Отличия v3:
  - дефолты: --human data/human, --ai data/ai_v2, --out data/v3;
  - --exclude-generator NAME → holdout.jsonl (leave-one-model-out);
  - meta.json помечает version=v3 и recommended_model=xlm-roberta-base.

Пример полного цикла:
  python ingest_human_corpus.py --src ~/Desktop/human_corpus --out data/human
  python make_dataset_v3.py --human data/human --ai data/ai_v2 --out data/v3 --per-lang 2500
  python make_dataset_v3.py --human data/human --ai data/ai_v2 --out data/v3-lomo \\
      --exclude-generator gpt-4o-mini
  python train.py --data data/v3 --model xlm-roberta-base --epochs 3 --out runs/ai-v3
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Переиспользуем логику v2
sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_dataset_v2 as v2  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Build AI-detector dataset v3 (XLM-R)")
    ap.add_argument("--human", default="data/human", help="после ingest_human_corpus.py")
    ap.add_argument("--ai", default="data/ai_v2", dest="ai_dir")
    ap.add_argument("--out", default="data/v3")
    ap.add_argument("--per-lang", type=int, default=2500)
    ap.add_argument("--dry-ratio", type=float, default=0.55)
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--test-frac", type=float, default=0.10)
    ap.add_argument(
        "--exclude-generator",
        default="",
        help="Убрать генератор из train/val/test → holdout.jsonl (LOMO)",
    )
    args = ap.parse_args()

    human_root = Path(args.human).expanduser()
    ai_dir = Path(args.ai_dir).expanduser()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # v2 ждёт corpus с подпапками ru/uz_latin/uz_cyrillic — data/human так и устроен
    print("Human chunks:")
    human = v2._read_human(human_root, args.per_lang, args.dry_ratio)
    print("AI chunks:")
    ai = v2._read_ai(ai_dir, args.per_lang)

    exclude = (args.exclude_generator or "").strip()
    holdout: list[dict] = []
    if exclude:
        holdout = [r for r in ai if r.get("generator") == exclude]
        ai = [r for r in ai if r.get("generator") != exclude]
        print(f"LOMO: exclude={exclude} holdout={len(holdout)} ai_remain={len(ai)}")

    rows = human + ai
    if not rows:
        raise SystemExit("Нет данных для dataset_v3 — сначала ingest_human_corpus.py и AI-тексты")

    train, val, test = v2._split_by_doc(rows, args.val_frac, args.test_frac)
    v2._write_jsonl(out / "train.jsonl", train)
    v2._write_jsonl(out / "val.jsonl", val)
    v2._write_jsonl(out / "test.jsonl", test)
    if holdout:
        v2._write_jsonl(out / "holdout.jsonl", holdout)

    meta = {
        "version": "v3",
        "recommended_model": "xlm-roberta-base",
        "per_lang": args.per_lang,
        "dry_ratio": args.dry_ratio,
        "window_words": v2.WINDOW_WORDS,
        "langs": list(v2.LANGS),
        "exclude_generator": exclude or None,
        "counts": {
            "train": len(train),
            "val": len(val),
            "test": len(test),
            "holdout": len(holdout),
            "human": sum(1 for r in rows if r["label"] == 0),
            "ai": sum(1 for r in rows if r["label"] == 1),
        },
    }
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    v2._summary("train", train)
    v2._summary("val", val)
    v2._summary("test", test)
    if holdout:
        v2._summary("holdout", holdout)
    print("Готово →", out)
    print("Дальше: python train.py --data", out, "--model xlm-roberta-base --out runs/ai-v3")


if __name__ == "__main__":
    main()
