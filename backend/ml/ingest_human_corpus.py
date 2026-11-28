#!/usr/bin/env python3
"""
Подключает Desktop/human_corpus к backend/ml/data/human для цикла обучения.

По умолчанию создаёт симлинки (быстро, без копирования):
  data/human/ru          -> <src>/ru
  data/human/uz_latin    -> <src>/uz_latin
  data/human/uz_cyrillic -> <src>/uz_cyrillic
  data/human/manifest.jsonl -> <src>/manifest.jsonl

Пример:
  python ingest_human_corpus.py --src ~/Desktop/human_corpus --out data/human
  python ingest_human_corpus.py --src ~/Desktop/human_corpus --out data/human --copy
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

BUCKETS = ("ru", "uz_latin", "uz_cyrillic")


def _link_or_copy(src: Path, dst: Path, copy: bool) -> None:
    if dst.exists() or dst.is_symlink():
        if dst.is_symlink() or dst.is_file():
            dst.unlink()
        else:
            shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if copy:
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        print(f"  copy {src} -> {dst}")
    else:
        dst.symlink_to(src.resolve())
        print(f"  link {dst} -> {src.resolve()}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=Path.home() / "Desktop" / "human_corpus")
    ap.add_argument("--out", type=Path, default=Path("data/human"))
    ap.add_argument("--copy", action="store_true", help="Копировать вместо симлинков")
    args = ap.parse_args()

    if not args.src.is_dir():
        raise SystemExit(f"Нет корпуса: {args.src}")

    args.out.mkdir(parents=True, exist_ok=True)
    print(f"Ingest {args.src} -> {args.out}")

    for name in BUCKETS:
        src = args.src / name
        if not src.is_dir():
            print(f"  ! пропуск {name}: нет папки")
            continue
        n = sum(1 for _ in src.glob("*.txt"))
        _link_or_copy(src, args.out / name, args.copy)
        print(f"    ({n} .txt)")

    manifest = args.src / "manifest.jsonl"
    if manifest.is_file():
        _link_or_copy(manifest, args.out / "manifest.jsonl", args.copy)
    else:
        print("  ! нет manifest.jsonl")

    print("Готово. Дальше: python make_dataset_v3.py --human data/human --ai data/ai_v2 --out data/v3")


if __name__ == "__main__":
    main()
