"""
Стилометрия: сравнение стиля текущей работы с предыдущими работами того же студента/учителя.

Если стиль резко отличается — это дополнительный сигнал.

Метрики:
  1. Средняя длина предложения (слова)
  2. CV длин предложений (разброс)
  3. TTR — type-token ratio (разнообразие лексики)
  4. Частота союзов и предлогов
  5. Плотность знаков препинания

Возвращает: StylometryResult(score 0-1, alert, details)
  score = 1.0 → стиль идентичен предыдущим работам
  score = 0.0 → стиль полностью другой
  alert = True если score < 0.45 и есть хотя бы 2 предыдущих работы

Вызывать через asyncio.to_thread.
"""
from __future__ import annotations

import math
import re
import statistics
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StylometryResult:
    score: float              # 0.0 – 1.0
    alert: bool
    details: dict = field(default_factory=dict)


# Function words common in RU/UZ writing
_FUNCTION_WORDS_RU = {"и", "в", "на", "с", "по", "за", "из", "к", "от", "до", "не", "а", "но"}
_FUNCTION_WORDS_UZ = {"va", "bu", "u", "bilan", "uchun", "da", "ga", "ni", "dan", "ham", "lekin"}


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?…])\s+", text) if len(s.strip()) > 10]


def _words(text: str) -> list[str]:
    return re.findall(r"[a-zA-ZаАёЁа-яА-Яa-zA-Z'ʻʼ]+", text.lower())


def _extract_features(text: str) -> dict:
    sents = _sentences(text)
    words = _words(text)

    if not sents or not words:
        return {}

    sent_lens = [len(s.split()) for s in sents]
    mean_sent = statistics.mean(sent_lens)
    cv_sent = (statistics.stdev(sent_lens) / mean_sent) if len(sent_lens) >= 3 and mean_sent else 0.0

    unique_words = len(set(words))
    ttr = unique_words / len(words) if words else 0.0

    # Function word frequency
    func_words = _FUNCTION_WORDS_RU | _FUNCTION_WORDS_UZ
    fw_count = sum(1 for w in words if w in func_words)
    fw_ratio = fw_count / len(words) if words else 0.0

    # Punctuation density (commas and semicolons per sentence)
    punct_count = text.count(",") + text.count(";")
    punct_per_sent = punct_count / len(sents) if sents else 0.0

    # Avg word length
    avg_word_len = sum(len(w) for w in words) / len(words) if words else 0.0

    return {
        "mean_sent_len": mean_sent,
        "cv_sent_len": cv_sent,
        "ttr": ttr,
        "fw_ratio": fw_ratio,
        "punct_per_sent": punct_per_sent,
        "avg_word_len": avg_word_len,
    }


def _feature_distance(f1: dict, f2: dict) -> float:
    """Normalized distance between two feature vectors (0 = identical, 1 = very different)."""
    if not f1 or not f2:
        return 0.5  # unknown → neutral

    # Weights reflect diagnostic importance
    comparisons = [
        ("mean_sent_len", 10.0, 0.25),
        ("cv_sent_len", 0.4, 0.20),
        ("ttr", 0.3, 0.20),
        ("fw_ratio", 0.08, 0.15),
        ("punct_per_sent", 2.0, 0.10),
        ("avg_word_len", 1.5, 0.10),
    ]

    weighted_dist = 0.0
    for key, scale, weight in comparisons:
        v1 = f1.get(key)
        v2 = f2.get(key)
        if v1 is None or v2 is None:
            continue
        d = abs(v1 - v2) / max(scale, 1e-6)
        weighted_dist += min(d, 1.0) * weight

    return min(weighted_dist, 1.0)


def compute_stylometry(
    current_text: str,
    previous_texts: list[str],
) -> StylometryResult:
    """
    Compare current text features to previous works.
    Returns StylometryResult.
    """
    if not previous_texts or len(previous_texts) < 2:
        # Not enough history to draw conclusions
        return StylometryResult(score=1.0, alert=False, details={"note": "insufficient_history"})

    current_features = _extract_features(current_text)
    if not current_features:
        return StylometryResult(score=1.0, alert=False, details={"note": "empty_text"})

    # Average features across previous works
    prev_feature_list = [_extract_features(t) for t in previous_texts if t]
    prev_feature_list = [f for f in prev_feature_list if f]
    if not prev_feature_list:
        return StylometryResult(score=1.0, alert=False, details={"note": "empty_history"})

    all_keys = set(current_features.keys())
    avg_prev: dict = {}
    for key in all_keys:
        vals = [f[key] for f in prev_feature_list if key in f]
        if vals:
            avg_prev[key] = sum(vals) / len(vals)

    dist = _feature_distance(current_features, avg_prev)
    score = round(1.0 - dist, 3)
    alert = score < 0.45

    return StylometryResult(
        score=score,
        alert=alert,
        details={
            "current": {k: round(v, 3) for k, v in current_features.items()},
            "previous_avg": {k: round(v, 3) for k, v in avg_prev.items()},
            "distance": round(dist, 3),
        },
    )
