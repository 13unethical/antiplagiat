"""
Детектор машинного перевода — heuristic v0.

Определяет, является ли текст (или его фрагменты) машинным переводом.
Возвращает процент подозрительных фрагментов и список сегментов.

Эвристические сигналы:
  1. Калькированные конструкции (буквальный перевод типичных фраз RU→UZ)
  2. Русизмы в узбекском тексте: суффиксы -tsiya/-siya/-izm/-izatsiya/-ifikatsiya
  3. Однородность длин предложений (CV < 0.25 → MT-подобно)
  4. Нехватка союзов и дискурсивных маркеров
  5. Подозрительно регулярная пунктуация

Архитектура идентична ai_detector: синхронная функция, вызывать через to_thread.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MTSegmentResult:
    start_char: int
    end_char: int
    probability: float
    mt_kind: str = "generic"


@dataclass
class MTDetectorResult:
    mt_percent: float           # 0–100
    segments: list[MTSegmentResult] = field(default_factory=list)
    model_version: str = "mt-heuristic-v0"


# ---------------------------------------------------------------------------
# Linguistic patterns
# ---------------------------------------------------------------------------

# Characteristic endings of Russian loanwords commonly preserved verbatim by MT
_RU_LOAN_PATTERN = re.compile(
    r"\b\w+(?:tsiya|siya|izm|izatsiya|ifikatsiya|logiya|grafiya|nomiya|metrika)\b",
    re.IGNORECASE,
)

# Calque constructions in Uzbek that are literal translations from Russian
_CALQUE_PATTERNS_UZ = [
    r"\bko[\''ʻ]rib chiq",          # "рассмотреть" → ko'rib chiqish
    r"\be[\''ʻ]tibor berish",        # "обратить внимание"
    r"\bamалga oshirish",            # "осуществить"
    r"\bta[\''ʻ]minlash maqsadida",  # "в целях обеспечения"
    r"\bquyidagilarni amalga",
    r"\bta[\''ʻ]kidlash lozim",
]
_CALQUE_RX_UZ = [re.compile(p, re.IGNORECASE) for p in _CALQUE_PATTERNS_UZ]

# Natural discourse connectors — real writing uses these; MT often drops them
_DISCOURSE_MARKERS_UZ = {
    "ammo", "lekin", "biroq", "shuning uchun", "shuningdek", "bundan tashqari",
    "ya'ni", "masalan", "xususan", "jumladan", "natijada",
}
_DISCOURSE_MARKERS_RU = {
    "однако", "тем не менее", "поэтому", "следовательно", "таким образом",
    "при этом", "в частности", "например", "в результате", "следует отметить",
}


def _sentence_split(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?…])\s+", text) if len(s.strip()) > 20]


def _word_count(s: str) -> int:
    return len(s.split())


def _cv(values: list[float]) -> float:
    if len(values) < 3:
        return 1.0
    mean = statistics.mean(values)
    if mean == 0:
        return 1.0
    return statistics.stdev(values) / mean


# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------

def _score_sentence(sentence: str, language: str) -> tuple[float, str]:
    """
    Return (probability 0-1, mt_kind) for a single sentence.
    """
    score = 0.0
    mt_kind = "generic"
    lower = sentence.lower()
    words = sentence.split()

    if not words:
        return 0.0, mt_kind

    # Signal 1: Russian loanword density in Uzbek text
    if "uz" in language.lower():
        loans = len(_RU_LOAN_PATTERN.findall(sentence))
        loan_ratio = loans / len(words)
        if loan_ratio > 0.12:
            score += 0.3
            mt_kind = "ru_to_uz"
        elif loan_ratio > 0.06:
            score += 0.15

    # Signal 2: Calque constructions
    if "uz" in language.lower():
        calques = sum(1 for rx in _CALQUE_RX_UZ if rx.search(lower))
        if calques >= 2:
            score += 0.3
            mt_kind = "ru_to_uz"
        elif calques == 1:
            score += 0.15

    # Signal 3: Absence of discourse markers (penalise only if sentence is long enough)
    if len(words) >= 15:
        markers = _DISCOURSE_MARKERS_RU if "ru" in language.lower() else _DISCOURSE_MARKERS_UZ
        has_marker = any(m in lower for m in markers)
        if not has_marker:
            score += 0.08

    # Signal 4: Comma density — MT tends toward uniform punctuation
    comma_count = sentence.count(",")
    if len(words) >= 20 and comma_count == 0:
        score += 0.1
    if len(words) >= 10 and comma_count / len(words) > 0.25:
        score += 0.08

    # Signal 5: Overly long compound clauses (many "and" connectors = literal translation)
    conj_count = sum(1 for w in words if w.lower() in {"va", "и", "and", "hem"})
    if conj_count / max(len(words), 1) > 0.1:
        score += 0.1

    return min(score, 1.0), mt_kind


def detect_mt(text: str, language: str = "unknown") -> MTDetectorResult:
    """
    Run MT detection heuristics on the full text.
    Returns MTDetectorResult with percent and segments.
    """
    sentences = _sentence_split(text)
    if not sentences:
        return MTDetectorResult(mt_percent=0.0)

    # Document-level signal: sentence length uniformity
    lengths = [float(_word_count(s)) for s in sentences]
    cv = _cv(lengths)
    doc_uniformity_bonus = max(0.0, (0.35 - cv) / 0.35) * 0.2  # up to +0.20 for very uniform text

    segments: list[MTSegmentResult] = []
    flagged = 0

    # Map sentences back to char positions
    pos = 0
    for sent in sentences:
        idx = text.find(sent, pos)
        if idx == -1:
            pos = min(pos + len(sent) + 5, len(text))
            continue
        end = idx + len(sent)

        prob, mt_kind = _score_sentence(sent, language)
        prob = min(prob + doc_uniformity_bonus, 1.0)

        if prob >= 0.35:
            flagged += 1
            segments.append(MTSegmentResult(
                start_char=idx,
                end_char=end,
                probability=round(prob, 3),
                mt_kind=mt_kind,
            ))
        pos = end

    mt_percent = round(flagged / len(sentences) * 100, 1) if sentences else 0.0

    return MTDetectorResult(
        mt_percent=mt_percent,
        segments=segments,
        model_version="mt-heuristic-v0",
    )
