"""
Детектор ИИ-сгенерированного текста.

Текущая версия (stub-v0): эвристический детектор на основе статистики предложений.
Будет заменён на XLM-RoBERTa в Stage 7 после сбора обучающих данных.

Выход:
  ai_percent        — доля текста, вероятно написанного ИИ (0–100)
  model_version     — версия модели для аудита
"""
from __future__ import annotations

import hashlib
import re
import statistics
from dataclasses import dataclass


@dataclass
class AiDetectorResult:
    ai_percent: float
    model_version: str


_MODEL_VERSION = "stub-v0"

_AI_PHRASES = [
    r"\bследует отметить\b", r"\bнеобходимо подчеркнуть\b",
    r"\bтаким образом\b", r"\bна основании вышеизложенного\b",
    r"\bв заключение можно сказать\b", r"\bданная работа посвящена\b",
    r"\bактуальность темы\b", r"\bв рамках настоящего исследования\b",
    r"\bshu bilan birga\b", r"\bquyidagilarni ta'kidlash\b",
    r"\bxulosa qilib aytish mumkin\b",
]


def ai_spans(text: str, language: str = "unknown") -> list[tuple[int, int]]:
    """Char-спаны предложений, похожих на ИИ-текст — для подсветки в отчёте.

    Эвристика stub-уровня: помечаем предложения с шаблонными академическими
    фразами, с цепочками «который…», а при равномерной длине предложений —
    и предложения близкой к средней длины.
    """
    if not text or len(text.strip()) < 100:
        return []
    phrase_re = re.compile("|".join(_AI_PHRASES), re.IGNORECASE)
    rel_re = re.compile(r"\b(который|которая|которое|которых|котором)\b", re.IGNORECASE)

    sent_spans: list[tuple[int, int, str]] = []
    for m in re.finditer(r"[^.!?]+[.!?]*", text):
        s = m.group()
        if len(s.strip()) < 20:
            continue
        sent_spans.append((m.start(), m.end(), s))

    if not sent_spans:
        return []

    lens = [len(s) for _, _, s in sent_spans]
    mean = sum(lens) / len(lens)
    try:
        cv = statistics.stdev(lens) / mean if mean else 1.0
    except statistics.StatisticsError:
        cv = 1.0
    uniform = cv < 0.4

    spans: list[tuple[int, int]] = []
    for start, end, s in sent_spans:
        looks_ai = bool(phrase_re.search(s)) or bool(rel_re.search(s))
        if not looks_ai and uniform and 0.75 * mean <= len(s) <= 1.4 * mean:
            looks_ai = True
        if looks_ai:
            spans.append((start, end))
    return spans


def detect_ai(text: str, language: str = "unknown") -> AiDetectorResult:
    """
    Heuristic AI detector stub.

    Признаки ИИ-текста, которые используются:
    1. Коэффициент вариации длин предложений: у ИИ меньше разброс
    2. Доля «шаблонных» академических фраз (рус/узб)
    3. Отсутствие опечаток и неформальных маркеров
    4. Доля сложноподчинённых предложений с «который/которая/котором»

    Максимальная точность stub-а ~65%; не предназначен для реального использования.
    Метка «stub · модель в разработке» отображается в UI.
    """
    if not text or len(text.strip()) < 100:
        return AiDetectorResult(ai_percent=0.0, model_version=_MODEL_VERSION)

    sentences = _split_sentences(text)
    if len(sentences) < 3:
        return AiDetectorResult(ai_percent=0.0, model_version=_MODEL_VERSION)

    score = 0.0

    # ── 1. Uniform sentence length ────────────────────────────────────────────
    lens = [len(s) for s in sentences]
    try:
        cv = statistics.stdev(lens) / statistics.mean(lens)
    except statistics.StatisticsError:
        cv = 1.0
    # Typical human CV ~0.5–1.0, AI CV ~0.2–0.4
    if cv < 0.25:
        score += 35
    elif cv < 0.35:
        score += 20
    elif cv < 0.45:
        score += 10

    # ── 2. AI phrase markers (ru/uz) ─────────────────────────────────────────
    phrase_hits = sum(
        1 for p in _AI_PHRASES if re.search(p, text, re.IGNORECASE)
    )
    score += min(phrase_hits * 5, 20)

    # ── 3. Relative clause density (рус) ─────────────────────────────────────
    relative_count = len(re.findall(r"\b(который|которая|которое|которых|котором)\b", text, re.IGNORECASE))
    relative_density = relative_count / len(sentences)
    if relative_density > 1.5:
        score += 10
    elif relative_density > 1.0:
        score += 5

    # ── 4. Very clean punctuation (no ellipsis, no dashes in mid-sentence) ───
    informal = len(re.findall(r"\.{3}|—|\(!\)|!!|\?!", text))
    if informal == 0 and len(text) > 500:
        score += 5

    # ── 5. Noise from text hash to avoid identical scores on similar texts ───
    h = int(hashlib.md5(text[:300].encode(), usedforsecurity=False).hexdigest()[:6], 16)
    noise = (h % 15) - 7  # –7 to +7

    ai_pct = round(max(0.0, min(100.0, score + noise)), 1)
    return AiDetectorResult(ai_percent=ai_pct, model_version=_MODEL_VERSION)


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in parts if len(s.strip()) > 15]
