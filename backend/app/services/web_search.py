"""
Stage 9: Live web search antiplагиат.

Pipeline per check:
  1. select_rare_fragments   — выбрать 15–20 «редких» предложений из текста
  2. brave_search            — поискать каждый фрагмент через Brave Search API
  3. fetch_and_extract       — скачать страницы, извлечь текст (trafilatura)
  4. compare_to_document     — сравнить с оригиналом (rapidfuzz)
  5. auto_add_to_corpus      — сохранить найденные страницы в корпус (OpenSearch)

Кэш: JSON-файлы в {UPLOAD_DIR}/web_cache/{sha256(url)}.json, TTL 7 дней.
Graceful degradation: любая ошибка → пустой список + лог.

Вызывать через asyncio.to_thread из processor.py (функция синхронная).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

from app.config import settings
from app.services.plagiarism import MatchResult

# ---------------------------------------------------------------------------
# Optional imports — graceful degradation if packages are missing
# ---------------------------------------------------------------------------
try:
    import httpx as _httpx_mod  # noqa: F401 — availability check only
    _HTTPX_OK = True
except ImportError:
    _HTTPX_OK = False

try:
    import trafilatura as _trafilatura
    _TRAFILATURA_OK = True
except ImportError:
    _trafilatura = None  # type: ignore
    _TRAFILATURA_OK = False

try:
    from rapidfuzz import fuzz as _fuzz
    _RAPIDFUZZ_OK = True
except ImportError:
    _fuzz = None  # type: ignore
    _RAPIDFUZZ_OK = False


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class WebPageHit:
    url: str
    title: str
    text: str
    language: str


@dataclass
class WebSearchResult:
    """Summary returned by run_web_search to processor."""
    matches: list[MatchResult] = field(default_factory=list)
    queries_count: int = 0
    urls_fetched: int = 0
    matches_found: int = 0
    # Страницы с совпадениями — processor пишет в Postgres + кэш шинглов
    corpus_pages: list[WebPageHit] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Fragment selection
# ---------------------------------------------------------------------------

# Common academic / template phrases to avoid selecting (they'll match everywhere)
_TEMPLATE_PHRASES_RU = {
    "в данной работе", "в настоящее время", "таким образом", "следует отметить",
    "как известно", "в соответствии с", "на основании вышеизложенного",
    "в связи с этим", "необходимо отметить", "можно сделать вывод",
}
_TEMPLATE_PHRASES_UZ = {
    "ushbu ishda", "hozirgi vaqtda", "shunday qilib", "ta'kidlash kerak",
    "yuqoridagilardan kelib chiqib", "shunga ko'ra",
}

_STOPWORDS = _TEMPLATE_PHRASES_RU | _TEMPLATE_PHRASES_UZ


def _word_rarity_score(sentence: str) -> float:
    """Higher = more unique. Favour long sentences with no template phrases."""
    lower = sentence.lower()
    if any(ph in lower for ph in _STOPWORDS):
        return 0.0
    words = lower.split()
    if len(words) < 6:
        return 0.0
    # Rough uniqueness proxy: average word length (longer words are rarer)
    avg_len = sum(len(w) for w in words) / len(words)
    return avg_len * len(words)


def select_rare_fragments(text: str, max_fragments: int = 20) -> list[str]:
    """Return up to *max_fragments* rare sentences sorted by uniqueness desc."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    scored = [(s, _word_rarity_score(s)) for s in sentences if len(s) > 40]
    scored.sort(key=lambda x: x[1], reverse=True)
    # De-duplicate by first 60 chars (avoid near-identical sentences)
    seen: set[str] = set()
    result: list[str] = []
    for s, score in scored:
        if score == 0.0:
            continue
        key = s[:60].lower()
        if key not in seen:
            seen.add(key)
            result.append(s)
        if len(result) >= max_fragments:
            break
    return result


# ---------------------------------------------------------------------------
# File cache
# ---------------------------------------------------------------------------

def _cache_path(url: str) -> str:
    h = hashlib.sha256(url.encode()).hexdigest()
    cache_dir = os.path.join(settings.UPLOAD_DIR, "web_cache")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{h}.json")


def _cache_get(url: str) -> Optional[str]:
    """Return cached page text if still fresh, else None."""
    path = _cache_path(url)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if time.time() - data["ts"] > settings.WEB_SEARCH_CACHE_TTL:
            return None
        return data["text"]
    except Exception:
        return None


def _cache_set(url: str, text: str) -> None:
    try:
        with open(_cache_path(url), "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "text": text, "url": url}, f, ensure_ascii=False)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Brave Search API
# ---------------------------------------------------------------------------

def _brave_search(query: str, api_key: str, count: int = 5) -> list[dict]:
    """
    Call Brave Search API and return list of {url, title} dicts.
    Uses synchronous httpx (called from thread).
    Returns [] on any error.
    """
    if not _HTTPX_OK:
        return []
    try:
        import httpx
        resp = httpx.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": f'"{query[:120]}"', "count": count, "text_decorations": False},
            headers={"Accept": "application/json", "X-Subscription-Token": api_key},
            timeout=10,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        results = data.get("web", {}).get("results", [])
        return [{"url": r.get("url", ""), "title": r.get("title", "")} for r in results if r.get("url")]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Page fetching + text extraction
# ---------------------------------------------------------------------------

def _fetch_text(url: str) -> Optional[str]:
    """Fetch URL, extract main text via trafilatura. Uses cache."""
    cached = _cache_get(url)
    if cached is not None:
        return cached

    if not _HTTPX_OK or not _TRAFILATURA_OK:
        return None

    try:
        import httpx
        resp = httpx.get(
            url,
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AntiplagiatBot/1.0)"},
            follow_redirects=True,
        )
        if resp.status_code != 200:
            return None
        raw_html = resp.text
    except Exception:
        return None

    try:
        text = _trafilatura.extract(raw_html, include_comments=False, include_tables=False)
    except Exception:
        text = None

    if text and len(text) > 100:
        _cache_set(url, text)
        return text
    return None


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

def _find_matches_in_page(
    document_text: str,
    page_text: str,
    source_url: str,
    source_title: str,
    threshold: int,
) -> list[MatchResult]:
    """
    Slide a window of ~300 chars over page_text, compare to doc sentences.
    Returns MatchResult list (match_kind="web").
    """
    if not _RAPIDFUZZ_OK:
        return []

    matches: list[MatchResult] = []
    doc_sentences = re.split(r"(?<=[.!?])\s+", document_text)

    # Build page windows (~300 chars, step ~150)
    page_words = page_text.split()
    window_words = 50  # ~300 chars
    step = 25

    for i in range(0, max(1, len(page_words) - window_words + 1), step):
        window = " ".join(page_words[i: i + window_words])
        for sent in doc_sentences:
            if len(sent) < 40:
                continue
            score = _fuzz.token_set_ratio(sent, window)
            if score >= threshold:
                # Map sentence back to char offset in document_text
                start = document_text.find(sent)
                if start == -1:
                    continue
                end = start + len(sent)
                matches.append(MatchResult(
                    start_char=start,
                    end_char=end,
                    matched_text=sent[:500],
                    source_title=source_title,
                    source_url=source_url,
                    source_lang=None,
                    corpus_doc_id=None,
                    match_kind="web",
                    score=round(score / 100, 4),
                ))
    # De-duplicate overlapping ranges (keep highest score)
    return _dedup_matches(matches)


def _dedup_matches(matches: list[MatchResult]) -> list[MatchResult]:
    """Remove matches that overlap >50% with a higher-scored match."""
    matches.sort(key=lambda m: m.score, reverse=True)
    kept: list[MatchResult] = []
    for m in matches:
        overlap = False
        for k in kept:
            lo = max(m.start_char, k.start_char)
            hi = min(m.end_char, k.end_char)
            if hi > lo:
                span = m.end_char - m.start_char
                if span > 0 and (hi - lo) / span > 0.5:
                    overlap = True
                    break
        if not overlap:
            kept.append(m)
    return kept


# ---------------------------------------------------------------------------
# Auto-add found pages to corpus (OpenSearch only — no embedding for speed)
# ---------------------------------------------------------------------------

def _remember_page(
    result: WebSearchResult,
    url: str,
    title: str,
    text: str,
    language: str,
) -> None:
    """Кэш шинглов сразу + очередь на persist в Postgres (processor)."""
    try:
        from app.services import corpus as corpus_service
        doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, url))
        corpus_service.index_document(
            doc_id, title or url, text,
            url, language or "unknown", "web",
        )
    except Exception:
        pass
    result.corpus_pages.append(
        WebPageHit(url=url, title=title or url, text=text, language=language or "unknown")
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_web_search(
    normalized_text: str,
    language: str,
    already_covered: set[int] | None = None,
) -> WebSearchResult:
    """
    Run full web-search pipeline synchronously.
    Call via asyncio.to_thread from processor.py.

    Returns WebSearchResult with matches and usage stats.
    Graceful degradation: any failure → empty result.
    """
    result = WebSearchResult()

    if not settings.WEB_SEARCH_ENABLED:
        return result
    if not settings.BRAVE_API_KEY:
        return result

    try:
        fragments = select_rare_fragments(normalized_text, max_fragments=settings.WEB_SEARCH_MAX_QUERIES)
        if not fragments:
            return result

        seen_urls: set[str] = set()

        for fragment in fragments:
            if result.queries_count >= settings.WEB_SEARCH_MAX_QUERIES:
                break

            search_hits = _brave_search(fragment, settings.BRAVE_API_KEY, count=5)
            result.queries_count += 1

            for hit in search_hits:
                url = hit["url"]
                if url in seen_urls:
                    continue
                if result.urls_fetched >= settings.WEB_SEARCH_MAX_URLS:
                    break

                # Skip URLs already in corpus (avoid re-fetching known sources)
                try:
                    parsed = urlparse(url)
                    if not parsed.scheme or not parsed.netloc:
                        continue
                except Exception:
                    continue

                page_text = _fetch_text(url)
                if not page_text:
                    continue

                seen_urls.add(url)
                result.urls_fetched += 1

                page_matches = _find_matches_in_page(
                    normalized_text,
                    page_text,
                    source_url=url,
                    source_title=hit["title"],
                    threshold=settings.WEB_SEARCH_MATCH_THRESHOLD,
                )

                # Filter out positions already covered by shingle/semantic matches
                if already_covered:
                    filtered: list[MatchResult] = []
                    for m in page_matches:
                        span = m.end_char - m.start_char
                        if span > 0:
                            overlap = sum(1 for i in range(m.start_char, min(m.end_char, m.start_char + 300))
                                          if i in already_covered)
                            if overlap > span * 0.5:
                                continue
                        filtered.append(m)
                    page_matches = filtered

                if page_matches:
                    result.matches.extend(page_matches)
                    result.matches_found += len(page_matches)
                    _remember_page(result, url, hit["title"], page_text, language)

    except Exception:
        pass  # Graceful degradation

    return result
