#!/usr/bin/env python3
"""
Smoke: Brave Search + сравнение фрагмента с Wikipedia.

Запуск из backend/:
  python scripts/smoke_brave.py
  BRAVE_API_KEY=... python scripts/smoke_brave.py "фраза для поиска"
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.services.web_search import run_web_search  # noqa: E402


def main() -> None:
    phrase = " ".join(sys.argv[1:]).strip() or (
        "Tashkent is the capital and largest city of Uzbekistan"
    )
    if not settings.BRAVE_API_KEY.strip():
        print("FAIL: BRAVE_API_KEY пуст. Ключ: https://brave.com/search/api/")
        print("Пропиши в backend/.env и повтори.")
        sys.exit(1)
    if not settings.WEB_SEARCH_ENABLED:
        print("FAIL: WEB_SEARCH_ENABLED=false")
        sys.exit(1)

    text = (
        f"Introduction. {phrase}. "
        "This paragraph is long enough for the rare-fragment selector to pick "
        "the sentence above and query Brave Search for web plagiarism matches."
    )
    print(f"Query text length={len(text)} key={'set' if settings.BRAVE_API_KEY else 'missing'}")
    result = run_web_search(text, language="en", already_covered=set())
    print(
        f"queries={result.queries_count} urls={result.urls_fetched} "
        f"matches={result.matches_found}"
    )
    for m in result.matches[:5]:
        print(f"  [{m.score:.0f}] {m.source_title or '-'} | {m.source_url}")
    if result.matches_found == 0:
        print("WARN: совпадений нет (квота/сеть/фраза). Слой при этом живой.")
        sys.exit(0)
    print("OK")


if __name__ == "__main__":
    main()
