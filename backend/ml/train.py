#!/usr/bin/env python3
"""
Дообучение ИИ-детектора: XLM-RoBERTa / mDeBERTa как бинарный классификатор
человек(0) / ИИ(1).

v2:
  - метрики отдельно по ru / uz-Latn / uz-Cyrl;
  - temperature scaling на val → calibration.json;
  - поддержка test.jsonl.

Пример:
  python train.py --data data/v2 --model xlm-roberta-base --epochs 3 --out runs/ai-v2
  python train.py --data data/v2 --model microsoft/mdeberta-v3-base --out runs/ai-v2-mdeberta
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np


LANGS = ("ru", "uz-Latn", "uz-Cyrl")


def load_jsonl(p: Path) -> list[dict]:
    if not p.is_file():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def _softmax_rows(logits: np.ndarray) -> np.ndarray:
    x = logits - logits.max(axis=1, keepdims=True)
    e = np.exp(x)
    return e / e.sum(axis=1, keepdims=True)


def _fit_temperature(logits: np.ndarray, labels: np.ndarray) -> float:
    """Минимизирует NLL по температуре T > 0 (1D grid + Nelder-Mead-like refine)."""
    y = labels.astype(np.int64)

    def nll(t: float) -> float:
        t = max(t, 1e-3)
        probs = _softmax_rows(logits / t)
        p = np.clip(probs[np.arange(len(y)), y], 1e-8, 1.0)
        return float(-np.mean(np.log(p)))

    grid = np.concatenate([np.linspace(0.5, 5.0, 46), np.array([1.0])])
    best_t = 1.0
    best = nll(best_t)
    for t in grid:
        v = nll(float(t))
        if v < best:
            best, best_t = v, float(t)
    # локальное уточнение
    step = 0.05
    for _ in range(40):
        improved = False
        for cand in (best_t - step, best_t + step):
            if cand <= 0.05:
                continue
            v = nll(cand)
            if v < best:
                best, best_t, improved = v, cand, True
        if not improved:
            step *= 0.5
            if step < 1e-3:
                break
    return float(best_t)


def _metrics_from_logits(logits: np.ndarray, labels: np.ndarray, temperature: float = 1.0) -> dict:
    from sklearn.metrics import accuracy_score, precision_recall_fscore_support, roc_auc_score

    probs = _softmax_rows(logits / max(temperature, 1e-3))
    preds = probs.argmax(axis=1)
    p, r, f1, _ = precision_recall_fscore_support(labels, preds, average="binary", zero_division=0)
    try:
        auc = roc_auc_score(labels, probs[:, 1])
    except Exception:
        auc = float("nan")
    return {
        "accuracy": float(accuracy_score(labels, preds)),
        "precision": float(p),
        "recall": float(r),
        "f1": float(f1),
        "auc": float(auc),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/v2")
    ap.add_argument("--model", default="xlm-roberta-base",
                    help="xlm-roberta-base | microsoft/mdeberta-v3-base | …")
    ap.add_argument("--epochs", type=float, default=3)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--max-len", type=int, default=256)
    ap.add_argument("--out", default="runs/ai-v2")
    ap.add_argument("--no-calibrate", action="store_true")
    args = ap.parse_args()

    from datasets import Dataset
    from transformers import (
        AutoTokenizer,
        AutoModelForSequenceClassification,
        TrainingArguments,
        Trainer,
        DataCollatorWithPadding,
    )

    data = Path(args.data)
    train_rows = load_jsonl(data / "train.jsonl")
    val_rows = load_jsonl(data / "val.jsonl")
    test_rows = load_jsonl(data / "test.jsonl")
    if not train_rows or not val_rows:
        raise SystemExit(f"Нет train/val в {data}")
    print(f"train={len(train_rows)} val={len(val_rows)} test={len(test_rows)}")

    tok = AutoTokenizer.from_pretrained(args.model)

    def to_ds(rows: list[dict]) -> Dataset:
        ds = Dataset.from_list(
            [{"text": r["text"], "label": int(r["label"]), "lang": r.get("lang", "ru")} for r in rows]
        )
        return ds.map(
            lambda b: tok(b["text"], truncation=True, max_length=args.max_len),
            batched=True,
        )

    train_ds, val_ds = to_ds(train_rows), to_ds(val_rows)

    model = AutoModelForSequenceClassification.from_pretrained(args.model, num_labels=2)

    def metrics(eval_pred):
        logits, labels = eval_pred
        return _metrics_from_logits(np.asarray(logits), np.asarray(labels))

    targs = TrainingArguments(
        output_dir=args.out,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch,
        per_device_eval_batch_size=args.batch,
        learning_rate=args.lr,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        logging_steps=50,
        report_to=[],
    )
    trainer = Trainer(
        model=model,
        args=targs,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        tokenizer=tok,
        data_collator=DataCollatorWithPadding(tok),
        compute_metrics=metrics,
    )
    trainer.train()
    overall = trainer.evaluate()
    print("VAL overall:", overall)

    # logits на val для калибровки и per-lang метрик
    pred = trainer.predict(val_ds)
    val_logits = np.asarray(pred.predictions)
    val_labels = np.asarray(pred.label_ids)

    temperature = 1.0
    if not args.no_calibrate:
        temperature = _fit_temperature(val_logits, val_labels)
        print(f"Temperature scaling: T={temperature:.4f}")

    per_lang = {}
    langs = [r.get("lang", "ru") for r in val_rows]
    for lang in LANGS:
        idx = [i for i, L in enumerate(langs) if L == lang]
        if len(idx) < 5:
            continue
        per_lang[lang] = _metrics_from_logits(val_logits[idx], val_labels[idx], temperature)
        print(f"VAL {lang}:", per_lang[lang])

    calibrated_overall = _metrics_from_logits(val_logits, val_labels, temperature)
    print("VAL calibrated:", calibrated_overall)

    test_metrics = {}
    if test_rows:
        test_ds = to_ds(test_rows)
        tpred = trainer.predict(test_ds)
        t_logits = np.asarray(tpred.predictions)
        t_labels = np.asarray(tpred.label_ids)
        test_metrics["overall"] = _metrics_from_logits(t_logits, t_labels, temperature)
        t_langs = [r.get("lang", "ru") for r in test_rows]
        for lang in LANGS:
            idx = [i for i, L in enumerate(t_langs) if L == lang]
            if len(idx) < 5:
                continue
            test_metrics[lang] = _metrics_from_logits(t_logits[idx], t_labels[idx], temperature)
        print("TEST:", json.dumps(test_metrics, ensure_ascii=False, indent=2))

    out = Path(args.out)
    trainer.save_model(out)
    tok.save_pretrained(out)
    calib = {
        "temperature": temperature,
        "backbone": args.model,
        "val_overall": calibrated_overall,
        "val_per_lang": per_lang,
        "test": test_metrics,
    }
    (out / "calibration.json").write_text(
        json.dumps(calib, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Модель сохранена в", out)
    print("calibration.json записан (temperature + per-lang metrics)")


if __name__ == "__main__":
    main()
