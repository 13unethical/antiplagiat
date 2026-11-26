"""
Инференс обученного ИИ-детектора через ONNX Runtime (без PyTorch в проде).

Активируется, если в .env задан AI_MODEL_DIR и в нём лежат:
  model.onnx                 — экспортированная модель-классификатор (2 класса)
  токенайзер (tokenizer.json / sentencepiece) — формат HuggingFace

Если каталог не задан или библиотеки/файлы отсутствуют — возвращает None,
и вызывающий код откатывается на эвристику (ai_detector.heuristic).
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_session = None
_tokenizer = None
_temperature = 1.0
_loaded = False
_available = False


def _load() -> bool:
    global _session, _tokenizer, _temperature, _loaded, _available
    if _loaded:
        return _available
    _loaded = True

    from app.config import settings
    model_dir = settings.AI_MODEL_DIR
    if not model_dir or not os.path.isdir(model_dir):
        return False
    onnx_path = os.path.join(model_dir, "model.onnx")
    if not os.path.isfile(onnx_path):
        logger.warning("AI_MODEL_DIR задан, но model.onnx не найден")
        return False
    try:
        import json
        import onnxruntime as ort
        from transformers import AutoTokenizer

        _tokenizer = AutoTokenizer.from_pretrained(model_dir)
        _session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
        calib_path = os.path.join(model_dir, "calibration.json")
        _temperature = 1.0
        if os.path.isfile(calib_path):
            try:
                calib = json.loads(open(calib_path, encoding="utf-8").read())
                _temperature = float(calib.get("temperature", 1.0)) or 1.0
            except Exception:  # noqa: BLE001
                _temperature = 1.0
        _available = True
        logger.info(
            "Loaded ONNX AI-detector from %s (T=%.3f)", model_dir, _temperature
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cannot load ONNX AI-detector: %s", exc)
        _available = False
    return _available


def _softmax(x):
    import numpy as np
    e = np.exp(x - np.max(x))
    return e / e.sum()


def predict_ai_percent(text: str, max_len: int = 512) -> float | None:
    """Вероятность ИИ (0..100) по обученной модели, или None если модель недоступна."""
    if not _load():
        return None
    try:
        import numpy as np

        enc = _tokenizer(
            text, truncation=True, max_length=max_len,
            padding="max_length", return_tensors="np",
        )
        feeds = {k: v for k, v in enc.items() if k in {i.name for i in _session.get_inputs()}}
        logits = _session.run(None, feeds)[0][0]
        logits = np.asarray(logits, dtype=np.float64) / max(_temperature, 1e-3)
        prob_ai = float(_softmax(logits)[1])  # класс 1 = ИИ
        return round(prob_ai * 100, 1)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ONNX AI-detector inference failed: %s", exc)
        return None
