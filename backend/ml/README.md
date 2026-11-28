# Обучение ИИ-детектора (XLM-RoBERTa → ONNX)

Каркас для дообучения настоящего детектора ИИ-текста вместо эвристики.
Обучение запускается на **GPU** (Google Colab / Kaggle / арендованный сервер),
инференс в бэкенде идёт через **ONNX Runtime** без PyTorch.

Операционный чеклист (Brave + EN DocMaxxing + цикл RU/UZ): см. корневой
[`OPS_AI_DETECTOR.md`](../../OPS_AI_DETECTOR.md).

## Пайплайн

```
human_corpus -> ingest_human_corpus.py -> data/human
data/ai_v2   + data/human -> make_dataset_v3.py -> data/v3
data/v3 -> train.py (xlm-roberta-base) -> eval.py -> export_onnx.py -> AI_MODEL_DIR
```

EN в проде идёт через DocMaxxing (`DOCMAXXING_AI_*`), не через этот ONNX.

## 1. Данные

```bash
# Симлинки на Desktop/human_corpus
python ingest_human_corpus.py --src ~/Desktop/human_corpus --out data/human

# JSONL v3 под XLM-R
python make_dataset_v3.py --human data/human --ai data/ai_v2 --out data/v3 --per-lang 2500

# Leave-one-model-out
python make_dataset_v3.py --human data/human --ai data/ai_v2 --out data/v3-lomo \
  --exclude-generator gpt-4o-mini
```

Быстрый бутстрап без корпуса:

```bash
python make_dataset.py --out data --synth 400
```

Автогенерация ИИ-текстов: `gen_ai_v2.py` / `make_dataset.py --gen-llm` (нужен API-ключ).

## 2. Обучение (GPU)

```bash
pip install -r requirements.txt
python train.py --data data/v3 --model xlm-roberta-base --epochs 3 --out runs/ai-v3
```

Модель сохраняется в `runs/ai-v3`.

## 3. Честная оценка (leave-one-model-out)

Чтобы проверить, что детектор обобщается на **невиданный** генератор, а не
запоминает «почерк» одного, уберите генератор из обучения и оцените на нём:

```bash
python make_dataset.py --out data --exclude-generator gpt-4o   # gpt-4o -> holdout.jsonl
python train.py --data data --out runs/ai-lomo
python eval.py --model runs/ai-lomo --data data/holdout.jsonl
```

Смотрите на accuracy / f1 / auc на holdout — это реалистичная оценка.

## 4. Экспорт в ONNX и подключение к бэкенду

```bash
python export_onnx.py --model runs/ai-v1 --out ../app/ml_model
```

Это кладёт `model.onnx` + токенайзер в `backend/app/ml_model/`. Затем в
`backend/.env`:

```
AI_MODEL_DIR=./app/ml_model
```

и в проде поставить токенайзер/рантайм:

```
pip install onnxruntime transformers
```

После рестарта бэкенда `detect_ai` автоматически использует модель
(`model_version = "xlmr-onnx"`); если модели нет — откат на `heuristic-v1`.
Остальной пайплайн (отчёты, подсветка, проценты) уже готов и не меняется.

## Colab

Готовый ноутбук: `colab_train.ipynb` — загрузка данных, обучение, оценка,
экспорт и скачивание `model.onnx` одним проходом.

## Заметки

- `xlm-roberta-base` (~270M) обучается на T4 за десятки минут при нескольких
  тысячах примеров. Для более высокой точности — `microsoft/mdeberta-v3-base`.
- Аугментации против обхода (перевод, «гуманайзеры») добавляйте как отдельные
  папки-генераторы в `data/ai/` — детектор научится их узнавать.
- Датасет и веса (`data/*.jsonl`, `runs/`, `app/ml_model/`) не коммитятся
  (см. `.gitignore`).
