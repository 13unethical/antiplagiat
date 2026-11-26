#!/usr/bin/env python3
"""
Экспорт обученной модели в ONNX для инференса в бэкенде (onnxruntime, без PyTorch).

Копирует также calibration.json (temperature scaling из train.py), если есть.

Пример:
  python export_onnx.py --model runs/ai-v2 --out ../app/ml_model
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="каталог обученной модели (из train.py)")
    ap.add_argument("--out", default="../app/ml_model")
    ap.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="переопределить T (иначе берётся из calibration.json или 1.0)",
    )
    args = ap.parse_args()

    src = Path(args.model)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # temperature
    temperature = 1.0
    calib_src = src / "calibration.json"
    calib: dict = {}
    if calib_src.is_file():
        calib = json.loads(calib_src.read_text(encoding="utf-8"))
        temperature = float(calib.get("temperature", 1.0))
    if args.temperature is not None:
        temperature = float(args.temperature)
        calib["temperature"] = temperature

    # Предпочтительно через optimum
    try:
        from optimum.onnxruntime import ORTModelForSequenceClassification
        from transformers import AutoTokenizer

        model = ORTModelForSequenceClassification.from_pretrained(args.model, export=True)
        model.save_pretrained(out)
        AutoTokenizer.from_pretrained(args.model).save_pretrained(out)
        onnxs = list(out.glob("*.onnx"))
        if onnxs and onnxs[0].name != "model.onnx":
            shutil.copy(onnxs[0], out / "model.onnx")
        print("Экспортировано через optimum →", out)
    except Exception as exc:
        print(f"optimum недоступен ({exc}); пробуем torch.onnx…")
        import torch
        from transformers import AutoTokenizer, AutoModelForSequenceClassification

        tok = AutoTokenizer.from_pretrained(args.model)
        model = AutoModelForSequenceClassification.from_pretrained(args.model)
        model.eval()
        tok.save_pretrained(out)
        enc = tok(
            "пример текста",
            return_tensors="pt",
            truncation=True,
            max_length=256,
            padding="max_length",
        )
        torch.onnx.export(
            model,
            (enc["input_ids"], enc["attention_mask"]),
            str(out / "model.onnx"),
            input_names=["input_ids", "attention_mask"],
            output_names=["logits"],
            dynamic_axes={
                "input_ids": {0: "b", 1: "s"},
                "attention_mask": {0: "b", 1: "s"},
                "logits": {0: "b"},
            },
            opset_version=14,
            dynamo=False,
        )
        print("Экспортировано через torch.onnx →", out)

    # калибровка рядом с onnx (бэкенд делит logits на T)
    calib_out = {
        "temperature": temperature,
        "backbone": calib.get("backbone"),
        "val_overall": calib.get("val_overall"),
        "val_per_lang": calib.get("val_per_lang"),
        "note": "At inference: softmax(logits / temperature)",
    }
    (out / "calibration.json").write_text(
        json.dumps(calib_out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if calib_src.is_file() and args.temperature is None:
        # сохраняем полный оригинал тоже
        shutil.copy(calib_src, out / "calibration.full.json")
    print(f"calibration.json: temperature={temperature:.4f}")


if __name__ == "__main__":
    main()
