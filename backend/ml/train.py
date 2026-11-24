#!/usr/bin/env python3
"""
Дообучение ИИ-детектора: XLM-RoBERTa (мультиязычный) как бинарный классификатор
человек(0) / ИИ(1). Запускать на GPU (Colab/Kaggle T4 и т.п.).

Пример:
  python train.py --data data --model xlm-roberta-base --epochs 3 --out runs/ai-v1
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def load_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--model", default="xlm-roberta-base")
    ap.add_argument("--epochs", type=float, default=3)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--max-len", type=int, default=256)
    ap.add_argument("--out", default="runs/ai-detector")
    args = ap.parse_args()

    from datasets import Dataset
    from transformers import (
        AutoTokenizer, AutoModelForSequenceClassification,
        TrainingArguments, Trainer, DataCollatorWithPadding,
    )
    from sklearn.metrics import accuracy_score, precision_recall_fscore_support, roc_auc_score

    data = Path(args.data)
    train_rows = load_jsonl(data / "train.jsonl")
    val_rows = load_jsonl(data / "val.jsonl")
    print(f"train={len(train_rows)} val={len(val_rows)}")

    tok = AutoTokenizer.from_pretrained(args.model)

    def to_ds(rows):
        ds = Dataset.from_list([{"text": r["text"], "label": int(r["label"])} for r in rows])
        return ds.map(lambda b: tok(b["text"], truncation=True, max_length=args.max_len), batched=True)

    train_ds, val_ds = to_ds(train_rows), to_ds(val_rows)

    model = AutoModelForSequenceClassification.from_pretrained(args.model, num_labels=2)

    def metrics(eval_pred):
        logits, labels = eval_pred
        preds = np.argmax(logits, axis=1)
        p, r, f1, _ = precision_recall_fscore_support(labels, preds, average="binary", zero_division=0)
        try:
            probs = np.exp(logits) / np.exp(logits).sum(axis=1, keepdims=True)
            auc = roc_auc_score(labels, probs[:, 1])
        except Exception:
            auc = float("nan")
        return {"accuracy": accuracy_score(labels, preds), "precision": p, "recall": r, "f1": f1, "auc": auc}

    targs = TrainingArguments(
        output_dir=args.out, num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch, per_device_eval_batch_size=args.batch,
        learning_rate=args.lr, eval_strategy="epoch", save_strategy="epoch",
        load_best_model_at_end=True, metric_for_best_model="f1",
        logging_steps=50, report_to=[],
    )
    trainer = Trainer(
        model=model, args=targs, train_dataset=train_ds, eval_dataset=val_ds,
        tokenizer=tok, data_collator=DataCollatorWithPadding(tok), compute_metrics=metrics,
    )
    trainer.train()
    print("VAL:", trainer.evaluate())
    trainer.save_model(args.out)
    tok.save_pretrained(args.out)
    print("Модель сохранена в", args.out)


if __name__ == "__main__":
    main()
