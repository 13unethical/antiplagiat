# OPS: Brave + ИИ-детектор (EN / RU / UZ)

Рабочий цикл Markly. Спека: `SPEC.md` §3–5.

## Кто что делает

| Слой | Когда | Где |
|---|---|---|
| Brave Search | любой язык, плагиат по сайтам | `BRAVE_API_KEY` → `web_search.py` |
| DocMaxxing DeBERTa | язык `en` | `DOCMAXXING_AI_URL` → `en_ai_detector.py` |
| Markly ONNX | `ru` / `uz-Latn` / `uz-Cyrl` | `AI_MODEL_DIR` → `ai_model.py` |
| Эвристика | fallback | `ai_detector.py` heuristic-v1 |

```
проверка → language
         ├─ en        → DocMaxxing /score (окна 5–8 предл.)
         └─ ru/uz/*   → ONNX (или heuristic)
         + шинглы + семантика + Brave → отчёт
```

---

## A. Brave (один раз + проверка)

1. Ключ: https://brave.com/search/api/
2. В `backend/.env` (local и prod):

```
BRAVE_API_KEY=<ключ>
WEB_SEARCH_ENABLED=true
WEB_SEARCH_MAX_QUERIES=20
WEB_SEARCH_MAX_URLS=10
```

3. Рестарт backend.
4. Superadmin → **Состояние системы**: строка «Brave Search» = ok (ключ задан).
5. Smoke API: `cd backend && python scripts/smoke_brave.py`
6. Smoke UI: загрузить текст с цитатой с Wikipedia / kun.uz → web-matches + `web_search_logs`.

Без ключа слой тихо отключается (graceful degradation).

---

## B. EN-детектор DocMaxxing

Инференс DocMaxxing на GCP L4 (`docmaxxing-detector`, порт **8081**) — не ZeroGPT.

### Актуальный прод (синхрон с DocMaxxing)

| Поле | Значение |
|---|---|
| URL | `http://34.71.144.75:8081` |
| Веса | `/models/detector/prod` (`VERSION` + `THRESHOLD` рядом) |
| Модель | `auto_20261117_all-202611170747` (DeBERTa-v3-large) |
| Threshold | **0.35** (сервер отдаёт в `/score` и `/healthz`) |
| Tokenizer max_len | **384** |
| Окна | 6 предл. (clamp 5–8), stride 1 — как `services/ai_detector.py` |
| Auth | `Authorization: Bearer <AI_DETECTOR_API_KEY>` |

### Контракт `/score`

```http
POST /score
Authorization: Bearer <key>
Content-Type: application/json

{"texts": ["window one…", "window two…"]}
```

Ответ:

```json
{"probs": [0.02, 0.91], "model": "auto_20261117_all-202611170747", "threshold": 0.35}
```

`GET /healthz` → `{"ok":true,"device":"cuda","model":"…","threshold":0.35,"zg_loaded":true}`  
(`zg_loaded` = dual ZeroGPT-proxy на том же сервисе; Markly EN использует только `probs` / `threshold`.)

### Markly `.env`

```
DOCMAXXING_AI_ENABLED=true
DOCMAXXING_AI_URL=http://34.71.144.75:8081
DOCMAXXING_AI_KEY=<тот же AI_DETECTOR_API_KEY что у DocMaxxing VPS>
DOCMAXXING_AI_THRESHOLD=0
```

`DOCMAXXING_AI_THRESHOLD=0` → брать `threshold` из ответа сервера (сейчас 0.35).  
Явно `0.35` можно задать, если нужен офлайн-фолбэк без первого `/score`.

Клиент: `backend/app/services/en_ai_detector.py` (порт DocMaxxing windowing → word-% AI).

Проверка: статус «DocMaxxing AI (EN)» = ok (модель + thr); английское эссе → `model_version` вида `docmaxxing-auto_20261117_…`.

---

## C. Обучение RU/UZ (повторяемый цикл)

### C1. Данные

```bash
cd backend/ml
# симлинки human из Desktop/human_corpus
python ingest_human_corpus.py --src ~/Desktop/human_corpus --out data/human

# ИИ уже в data/ai_v2/ (или gen_ai_v2 / make_dataset --gen-llm)
# Собрать v3 jsonl
python make_dataset_v3.py --human data/human --ai data/ai_v2 --out data/v3
```

Цели по human (ориентир SPEC):

| Язык | Сейчас (human_corpus) | Цель |
|---|---|---|
| ru | ~30k | держать ≥ ИИ |
| uz-Latn | ~4.6k | ≥ 5k |
| uz-Cyrl | ~16 | **≥ 1–2k** (критический пробел) |

uz-Cyrl: партнёрские архивы / ziyonet / временный Latn→Cyrl с меткой `attack=translit` (не считать «чистым» human в eval).

### C2. Train → eval → ONNX

```bash
# GPU / Colab: XLM-R
python train.py --data data/v3 --model xlm-roberta-base --epochs 3 --out runs/ai-v3

# Mac M1 (MPS): XLM-R часто OOM → DistilBERT multilingual
python train.py --data data/v3 --model distilbert-base-multilingual-cased \
  --epochs 3 --batch 8 --max-len 128 --out runs/ai-v3

# Leave-one-model-out
python make_dataset_v3.py ... --exclude-generator gpt-4o-mini
python train.py --data data/v3 --out runs/ai-v3-lomo
python eval.py --model runs/ai-v3-lomo --data data/v3/holdout.jsonl

# Порог: FPR на human ≤ 1% (SPEC §3.3)
python export_onnx.py --model runs/ai-v3 --out ../app/ml_model
```

В `.env`: `AI_MODEL_DIR=./app/ml_model` → рестарт.

### C3. Регистрация версии

Superadmin → модели: `POST /api/v1/admin/model-versions`  
`model_type=ai_detector`, метрики FPR/TPR/AUROC по языкам, активировать новую, старую оставить для отката.

### C4. Обратная связь

Учитель dispute → суперадмин размечает → текст в `data/human` или `data/ai/<gen>/` → следующий цикл train.

---

## Чеклист релиза модели

- [ ] Ingest human + AI сбалансированы по lang
- [ ] train.jsonl / val / test без утечки документов
- [ ] Eval по языкам + LOMO на ≥1 невиданный генератор
- [ ] FPR human ≤ 1% при выбранном пороге (calibration.json)
- [ ] export_onnx + локальный smoke на 5 human / 5 AI
- [ ] Запись в model_versions
- [ ] Prod `.env` AI_MODEL_DIR + рестарт
- [ ] Status page: AI model ok

## Чеклист инфраструктуры

- [ ] Brave key local + prod
- [ ] DocMaxxing URL/key (EN)
- [ ] Status: Brave + DocMaxxing + AI ONNX зелёные
