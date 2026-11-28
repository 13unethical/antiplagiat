"""
EN AI detector via DocMaxxing DeBERTa inference (HTTP POST /score).

Port of academic-doc-formatter/services/ai_detector.py windowing + word-% score.
Graceful: returns None if URL/key missing or remote fails.

Live contract (GCP L4 ``docmaxxing-detector`` on :8081):
  POST {URL}/score  Authorization: Bearer <AI_DETECTOR_API_KEY>
    body:  {"texts": [str, ...]}   # each item ≤ tokenizer max_length 384
    resp:  {"probs": [float, ...], "model": "<VERSION>", "threshold": <float>}
  GET  {URL}/healthz → {"ok", "device", "model", "threshold", "zg_loaded"?}

Windowing must stay aligned with DocMaxxing / Turnitin-style labels: 6 sentences
(clamped 5–8), stride one scored sentence. Threshold comes from the response
(``THRESHOLD`` next to weights; currently 0.35) unless DOCMAXXING_AI_THRESHOLD > 0.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

import httpx

from app.config import settings

log = logging.getLogger(__name__)

# Keep in sync with academic-doc-formatter/services/ai_detector.py
WINDOW_SENTENCES = 6
MIN_WINDOW_SENTENCES = 5
MAX_WINDOW_SENTENCES = 8
MIN_SCORED_WORDS = 40
_SENT = re.compile(r"(?<=[.!?])[\"'”’)]*\s+(?=[A-Z\"“(])")
_REFERENCE_HINT = re.compile(r"https?://|doi\.org|\bdoi:|\(\d{4}[a-z]?\)\.|Retrieved from", re.I)

_served_threshold: float | None = None
_served_model: str | None = None


@dataclass
class EnAiResult:
    ai_percent: float
    model_version: str
    spans: list[tuple[int, int]]


@dataclass
class _Sentence:
    start: int
    end: int
    text: str
    words: int
    scored: bool
    prob: float | None = None


def is_configured() -> bool:
    return bool(
        settings.DOCMAXXING_AI_ENABLED
        and settings.DOCMAXXING_AI_URL.strip()
        and settings.DOCMAXXING_AI_KEY.strip()
    )


def _threshold() -> float:
    if settings.DOCMAXXING_AI_THRESHOLD > 0:
        return settings.DOCMAXXING_AI_THRESHOLD
    # Prod serves 0.35 with auto_20261117_* weights; keep that until /score|/healthz answers.
    return _served_threshold or 0.35


def _split_sentences(text: str) -> list[_Sentence]:
    out: list[_Sentence] = []
    for line in re.finditer(r"[^\n]+", text):
        base, body = line.start(), line.group()
        reference_entry = bool(_REFERENCE_HINT.search(body)) and len(body.split()) <= 60
        cuts = [0, len(body)] if reference_entry else [0, *(m.end() for m in _SENT.finditer(body)), len(body)]
        for a, b in zip(cuts, cuts[1:]):
            chunk = body[a:b]
            stripped = chunk.strip()
            if not stripped:
                continue
            start = base + a + (len(chunk) - len(chunk.lstrip()))
            words = len(stripped.split())
            scored = words >= 4 and not _REFERENCE_HINT.search(stripped)
            out.append(_Sentence(start, start + len(stripped), stripped, words, scored))
    return out


def _windows(sentences: list[_Sentence]) -> list[tuple[int, int]]:
    idx = [k for k, s in enumerate(sentences) if s.scored]
    if not idx:
        return []
    n = len(idx)
    size = max(1, min(MAX_WINDOW_SENTENCES, WINDOW_SENTENCES))
    min_size = 1 if size < MIN_WINDOW_SENTENCES else MIN_WINDOW_SENTENCES
    if n < min_size:
        return [(idx[0], idx[-1] + 1)]
    out: list[tuple[int, int]] = []
    for a in range(n):
        b = min(a + size, n)
        if b - a < min_size:
            break
        out.append((idx[a], idx[b - 1] + 1))
        if b == n:
            break
    return out


def _remember_served(body: dict) -> None:
    global _served_threshold, _served_model
    served = body.get("threshold")
    if isinstance(served, (int, float)) and 0 < float(served) < 1:
        _served_threshold = float(served)
    model = body.get("model")
    if isinstance(model, str) and model.strip():
        _served_model = model.strip()


def _score_remote(texts: list[str]) -> tuple[list[float], str]:
    url = settings.DOCMAXXING_AI_URL.strip().rstrip("/")
    key = settings.DOCMAXXING_AI_KEY.strip()
    with httpx.Client(timeout=90.0) as client:
        res = client.post(
            f"{url}/score",
            json={"texts": texts},
            headers={"Authorization": f"Bearer {key}"},
        )
        res.raise_for_status()
        body = res.json()
    if not isinstance(body, dict):
        raise RuntimeError("bad detector response")
    probs = body.get("probs")
    if not isinstance(probs, list) or len(probs) != len(texts):
        raise RuntimeError("bad detector response")
    _remember_served(body)
    return [float(p) for p in probs], str(body.get("model") or _served_model or "deberta")


def detect_en(text: str) -> Optional[EnAiResult]:
    """Return EN AI score or None if not configured / too short / remote error."""
    if not is_configured() or not text or len(text.strip()) < 100:
        return None
    try:
        sentences = _split_sentences(text)
        spans_idx = _windows(sentences)
        if sum(s.words for s in sentences if s.scored) < MIN_SCORED_WORDS or not spans_idx:
            return EnAiResult(ai_percent=0.0, model_version="docmaxxing-too-short", spans=[])
        texts = [" ".join(s.text for s in sentences[a:b] if s.scored) for a, b in spans_idx]
        probs, model = _score_remote(texts)
        sums: dict[int, list[float]] = {}
        for (a, b), p in zip(spans_idx, probs):
            for k in range(a, b):
                if sentences[k].scored:
                    sums.setdefault(k, []).append(p)
        for k, ps in sums.items():
            sentences[k].prob = sum(ps) / len(ps)

        cut = _threshold()
        scored_words = sum(s.words for s in sentences if s.prob is not None)
        flagged_words = sum(s.words for s in sentences if s.prob is not None and s.prob > cut)
        ai_percent = round(100 * flagged_words / scored_words, 1) if scored_words else 0.0
        flagged_spans = [
            (s.start, s.end)
            for s in sentences
            if s.prob is not None and s.prob > cut
        ]
        ver = model if model.startswith("docmaxxing") else f"docmaxxing-{model or 'deberta'}"
        return EnAiResult(ai_percent=ai_percent, model_version=ver, spans=flagged_spans)
    except Exception as exc:  # noqa: BLE001
        log.warning("DocMaxxing EN detector failed: %s", exc)
        return None


def ping_en_detector() -> tuple[str, str]:
    """Return (status, detail) for admin status page."""
    if not settings.DOCMAXXING_AI_ENABLED:
        return "warn", "Выключен (DOCMAXXING_AI_ENABLED=false)"
    if not settings.DOCMAXXING_AI_URL.strip() or not settings.DOCMAXXING_AI_KEY.strip():
        return "warn", "Не настроен · нужен DOCMAXXING_AI_URL + KEY"
    url = settings.DOCMAXXING_AI_URL.strip().rstrip("/")
    key = settings.DOCMAXXING_AI_KEY.strip()
    try:
        with httpx.Client(timeout=5.0) as client:
            # Prefer /healthz (no GPU batch); fall back to a tiny /score probe.
            hz = client.get(f"{url}/healthz")
            if hz.status_code == 200 and isinstance(hz.json(), dict):
                body = hz.json()
                _remember_served(body)
                model = body.get("model") or _served_model or "ok"
                thr = body.get("threshold")
                thr_s = f", thr={thr}" if isinstance(thr, (int, float)) else ""
                device = body.get("device")
                dev_s = f", {device}" if device else ""
                return "ok", f"Модель: {model}{thr_s}{dev_s}"
            res = client.post(
                f"{url}/score",
                json={"texts": ["This is a short English probe sentence for health check only."]},
                headers={"Authorization": f"Bearer {key}"},
            )
            if res.status_code == 200 and isinstance(res.json(), dict):
                body = res.json()
                _remember_served(body)
                model = body.get("model") or "ok"
                thr = body.get("threshold")
                thr_s = f", thr={thr}" if isinstance(thr, (int, float)) else ""
                return "ok", f"Модель: {model}{thr_s}"
            return "error", f"HTTP {res.status_code}"
    except Exception as exc:  # noqa: BLE001
        return "error", str(exc)[:120]
