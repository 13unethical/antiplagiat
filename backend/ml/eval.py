#!/usr/bin/env python3
"""
Оценка обученного ИИ-детектора на любом JSONL (val.jsonl или holdout.jsonl).

Пример (честная проверка на невиданном генераторе, LOMO):
  python make_dataset.py --out data --exclude-generator gpt-4o
  python train.py --data data --out runs/ai-v1
  python eval.py --model runs/ai-v1 --data data/holdout.jsonl
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="каталог обученной модели")
    ap.add_argument("--data", required=True, help="JSONL для оценки")
    ap.add_argument("--max-len", type=int, default=256)
    ap.add_argument("--batch", type=int, default=32)
    args = ap.parse_args()

    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    from sklearn.metrics import accuracy_score, precision_recall_fscore_support, roc_auc_score, confusion_matrix

    rows = [json.loads(l) for l in Path(args.data).read_text(encoding="utf-8").splitlines() if l.strip()]
    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForSequenceClassification.from_pretrained(args.model)
    model.eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)

    preds, probs, labels = [], [], []
    for i in range(0, len(rows), args.batch):
        batch = rows[i : i + args.batch]
        enc = tok([r["text"] for r in batch], truncation=True, max_length=args.max_len,
                  padding=True, return_tensors="pt").to(device)
        with torch.no_grad():
            logits = model(**enc).logits
        p = torch.softmax(logits, dim=1).cpu().numpy()
        preds += list(np.argmax(p, axis=1))
        probs += list(p[:, 1])
        labels += [int(r["label"]) for r in batch]

    pr, rc, f1, _ = precision_recall_fscore_support(labels, preds, average="binary", zero_division=0)
    try:
        auc = roc_auc_score(labels, probs)
    except Exception:
        auc = float("nan")
    print(f"accuracy={accuracy_score(labels, preds):.3f} precision={pr:.3f} recall={rc:.3f} f1={f1:.3f} auc={auc:.3f}")
    print("confusion matrix [[TN FP],[FN TP]]:\n", confusion_matrix(labels, preds))


if __name__ == "__main__":
    main()
