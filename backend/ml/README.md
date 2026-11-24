# Обучение ИИ-детектора (XLM-RoBERTa → ONNX)

Каркас для дообучения настоящего детектора ИИ-текста вместо эвристики.
Обучение запускается на **GPU** (Google Colab / Kaggle / арендованный сервер),
инференс в бэкенде идёт через **ONNX Runtime** без PyTorch.

## Пайплайн

```
данные (data/human, data/ai)  ->  make_dataset.py  ->  train.py  ->  eval.py  ->  export_onnx.py  ->  backend
```

## 1. Данные

Это главный и самый трудоёмкий шаг. Нужны две группы текстов на uz/ru:

- `data/human/**/*.txt` — **человеческие** тексты. Лучше всего студенческие
  работы **до 2022 года** (до массового ChatGPT). Один файл — один текст.
- `data/ai/<generator>/**/*.txt` — **ИИ-тексты**, разложенные по папкам-генераторам
  (`data/ai/gpt-4o/…`, `data/ai/claude/…`, `data/ai/gemini/…`). Разнообразие
  генераторов критично для обобщения.

Быстрый старт без реальных данных (бутстрап):

```bash
python make_dataset.py --out data --synth 400
```

Автогенерация ИИ-текстов по темам (нужен ключ в окружении):

```bash
ANTHROPIC_API_KEY=... python make_dataset.py --out data --gen-llm data/topics.txt
# или OPENAI_API_KEY=...
```

`make_dataset.py` режет длинные тексты на окна ~120 слов и делает
стратифицированный train/val. Результат: `data/train.jsonl`, `data/val.jsonl`.

## 2. Обучение (GPU)

```bash
pip install -r requirements.txt
python train.py --data data --model xlm-roberta-base --epochs 3 --out runs/ai-v1
```

Модель сохраняется в `runs/ai-v1`.

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
