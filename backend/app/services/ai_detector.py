"""
Детектор ИИ-сгенерированного текста — усиленная эвристика (heuristic-v1).

Это НЕ обученная модель: оценка строится на наборе статистических признаков,
характерных для машинного текста, и объединяется логистической функцией.
Поддерживает русский и узбекский (латиница/кириллица). Для production-точности
нужен дообученный XLM-RoBERTa (см. SPEC.md разделы 3–4).

Выход:
  ai_percent     — 0..100, вероятная доля ИИ-текста
  model_version  — версия для аудита
"""
from __future__ import annotations

import math
import re
import statistics
from dataclasses import dataclass


@dataclass
class AiDetectorResult:
    ai_percent: float
    model_version: str


_MODEL_VERSION = "heuristic-v1"

# Шаблонные академические фразы (ru/uz) — частый маркер ИИ
_AI_PHRASES = [
    r"следует отметить", r"необходимо подчеркнуть", r"таким образом",
    r"на основании вышеизложенного", r"в заключение можно сказать",
    r"данная работа посвящена", r"актуальность (данной )?темы",
    r"в рамках настоящего исследования", r"играет важную роль",
    r"в современном мире", r"стоит отметить, что", r"важно отметить",
    r"с одной стороны", r"с другой стороны", r"кроме того",
    r"shu bilan birga", r"quyidagilarni ta'kidlash", r"xulosa qilib aytish mumkin",
    r"muhim ahamiyatga ega", r"shuni ta'kidlash joizki",
]
_AI_PHRASE_RE = re.compile("|".join(_AI_PHRASES), re.IGNORECASE)

# Связки/дискурсивные маркеры — ИИ любит их расставлять равномерно
_CONNECTIVES = [
    "однако", "таким образом", "следовательно", "кроме того", "поэтому",
    "тем не менее", "в частности", "более того", "в результате", "итак",
    "biroq", "shuningdek", "demak", "bundan tashqari", "natijada",
]
_CONN_RE = re.compile(r"\b(" + "|".join(_CONNECTIVES) + r")\b", re.IGNORECASE)

_WORD_RE = re.compile(r"\w+", re.UNICODE)
_SENT_RE = re.compile(r"[^.!?…]+[.!?…]*")


def _sentences(text: str) -> list[tuple[int, int, str]]:
    out = []
    for m in _SENT_RE.finditer(text):
        s = m.group().strip()
        if len(s) >= 15:
            out.append((m.start(), m.end(), s))
    return out


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _ngram_repetition(words: list[str], n: int) -> float:
    """Доля повторяющихся n-грамм (0..1). У ИИ часто выше."""
    if len(words) < n + 1:
        return 0.0
    grams = [" ".join(words[i : i + n]) for i in range(len(words) - n + 1)]
    if not grams:
        return 0.0
    uniq = len(set(grams))
    return 1.0 - uniq / len(grams)


def _logistic(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


def _features(text: str) -> dict[str, float]:
    sents = _sentences(text)
    words = _words(text)
    n_sent = len(sents)
    n_words = len(words)
    if n_sent < 2 or n_words < 40:
        return {}

    # 1. Burstiness: разброс длин предложений (в словах). Низкий → ИИ.
    lens = [len(_words(s)) for _, _, s in sents]
    mean_len = statistics.mean(lens)
    cv = (statistics.pstdev(lens) / mean_len) if mean_len else 1.0

    # 2. Лексическое разнообразие (TTR) на окне 400 слов.
    window = words[:400]
    ttr = len(set(window)) / len(window) if window else 0.0

    # 3. Повторяемость би- и триграмм.
    rep2 = _ngram_repetition(words, 2)
    rep3 = _ngram_repetition(words, 3)

    # 4. Плотность шаблонных фраз (на 1000 слов).
    phrase_hits = len(_AI_PHRASE_RE.findall(text))
    phrase_density = phrase_hits / n_words * 1000

    # 5. Плотность связок (на предложение).
    conn_density = len(_CONN_RE.findall(text)) / n_sent

    # 6. Разнообразие пунктуации: ИИ редко использует …, —, !, ?, ;, скобки.
    punct_kinds = sum(1 for ch in "—…!?;:()«»\"'" if ch in text)
    informal = len(re.findall(r"\.{3}|—|!!|\?!|\bну\b|\bвот\b|\bкстати\b", text, re.IGNORECASE))

    # 7. Средняя длина слова (ИИ чуть «книжнее»).
    avg_word_len = sum(len(w) for w in words) / n_words

    return {
        "cv": cv,
        "ttr": ttr,
        "rep2": rep2,
        "rep3": rep3,
        "phrase_density": phrase_density,
        "conn_density": conn_density,
        "punct_kinds": float(punct_kinds),
        "informal": float(informal),
        "avg_word_len": avg_word_len,
        "n_words": float(n_words),
    }


def _score_from_features(f: dict[str, float]) -> float:
    """Логистическая комбинация признаков → вероятность ИИ (0..1)."""
    if not f:
        return 0.0
    z = -1.8  # по умолчанию склоняемся к «человек»; ИИ нужно «доказать»

    # Шаблонные академические фразы — самый надёжный маркер ИИ.
    z += 0.6 * min(f["phrase_density"], 10)
    # Равномерно расставленные связки.
    z += 1.1 * min(f["conn_density"], 1.5)
    # Низкая вариативность длин предложений (только явно низкая).
    z += 1.8 * max(0.0, (0.42 - min(f["cv"], 0.42)) / 0.42)
    # Повторяемость триграмм.
    z += 3.0 * min(f["rep3"], 0.25)
    # Очень бедная пунктуация.
    z += 0.5 * max(0.0, (3 - f["punct_kinds"]) / 3)
    # Нет неформальных маркеров в длинном тексте.
    if f["informal"] == 0 and f["n_words"] > 200:
        z += 0.4
    # Высокое лексическое разнообразие в длинном тексте — в сторону человека.
    if f["ttr"] > 0.6 and f["n_words"] > 150:
        z -= 0.6

    return _logistic(z)


def detect_ai(text: str, language: str = "unknown") -> AiDetectorResult:
    if not text or len(text.strip()) < 100:
        return AiDetectorResult(ai_percent=0.0, model_version=_MODEL_VERSION)
    # 1. Обученная ONNX-модель, если настроена (AI_MODEL_DIR).
    try:
        from app.services.ai_model import predict_ai_percent
        ml = predict_ai_percent(text)
        if ml is not None:
            return AiDetectorResult(ai_percent=ml, model_version="distilbert-ml-onnx-v2")
    except Exception:  # noqa: BLE001
        pass
    # 2. Эвристика heuristic-v1 (fallback).
    f = _features(text)
    if not f:
        return AiDetectorResult(ai_percent=0.0, model_version=_MODEL_VERSION)
    prob = _score_from_features(f)
    return AiDetectorResult(ai_percent=round(prob * 100, 1), model_version=_MODEL_VERSION)


def _sentence_ai_score(sent: str, doc_cv: float) -> float:
    """Оценка одного предложения (0..1) — для подсветки в отчёте."""
    w = _words(sent)
    if len(w) < 6:
        return 0.0
    z = -1.1
    if _AI_PHRASE_RE.search(sent):
        z += 1.7
    if _CONN_RE.search(sent):
        z += 0.9
    z += 2.2 * min(_ngram_repetition(w, 2), 0.3)
    # лёгкий вклад общей равномерности документа
    z += 0.9 * max(0.0, (0.42 - min(doc_cv, 0.42)) / 0.42)
    return _logistic(z)


def ai_spans(text: str, language: str = "unknown") -> list[tuple[int, int]]:
    """Char-спаны предложений, похожих на ИИ-текст — для подсветки в отчёте."""
    if not text or len(text.strip()) < 100:
        return []
    sents = _sentences(text)
    if len(sents) < 2:
        return []
    lens = [len(_words(s)) for _, _, s in sents]
    mean_len = statistics.mean(lens) if lens else 1
    doc_cv = (statistics.pstdev(lens) / mean_len) if mean_len else 1.0
    spans: list[tuple[int, int]] = []
    for start, end, s in sents:
        if _sentence_ai_score(s, doc_cv) >= 0.5:
            spans.append((start, end))
    return spans
