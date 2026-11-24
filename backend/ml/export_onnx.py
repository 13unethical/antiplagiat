#!/usr/bin/env python3
"""
Экспорт обученной модели в ONNX для инференса в бэкенде (onnxruntime, без PyTorch).

Результат кладётся в <out>/: model.onnx + файлы токенайзера.
Затем в backend/.env укажите:  AI_MODEL_DIR=/путь/к/<out>

Пример:
  python export_onnx.py --model runs/ai-v1 --out ../app/ml_model
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="каталог обученной модели (из train.py)")
    ap.add_argument("--out", default="../app/ml_model")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # Предпочтительно через optimum (надёжный экспорт классификатора).
    try:
        from optimum.onnxruntime import ORTModelForSequenceClassification
        from transformers import AutoTokenizer

        model = ORTModelForSequenceClassification.from_pretrained(args.model, export=True)
        model.save_pretrained(out)  # кладёт model.onnx
        AutoTokenizer.from_pretrained(args.model).save_pretrained(out)
        # Нормализуем имя файла в model.onnx
        onnxs = list(out.glob("*.onnx"))
        if onnxs and onnxs[0].name != "model.onnx":
            shutil.copy(onnxs[0], out / "model.onnx")
        print("Экспортировано через optimum →", out)
        return
    except Exception as exc:
        print(f"optimum недоступен ({exc}); пробуем torch.onnx…")

    # Fallback: прямой экспорт через torch.onnx.
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification

    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForSequenceClassification.from_pretrained(args.model)
    model.eval()
    tok.save_pretrained(out)
    enc = tok("пример текста", return_tensors="pt", truncation=True, max_length=256,
              padding="max_length")
    torch.onnx.export(
        model, (enc["input_ids"], enc["attention_mask"]), str(out / "model.onnx"),
        input_names=["input_ids", "attention_mask"], output_names=["logits"],
        dynamic_axes={"input_ids": {0: "b", 1: "s"}, "attention_mask": {0: "b", 1: "s"}, "logits": {0: "b"}},
        opset_version=14,
    )
    print("Экспортировано через torch.onnx →", out)


if __name__ == "__main__":
    main()
