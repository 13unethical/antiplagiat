# Максимальный раскач ИИ-детектора RU / UZ

## Что нужно по данным

### Human (класс 0) — без этого модель врёт

| Язык | Сейчас | Цель «хорошо» | Откуда брать |
|---|---|---|---|
| ru | ~30k файлов | 10–20k **окон** в train (уже почти есть) | CyberLeninka, старые курсовые ≤2022, вики |
| uz-Latn | ~4.6k | ≥8–10k текстов | ziyonet, блоги, школьные архивы, Wikipedia uz |
| uz-Cyrl | — | **отключено** | не собираем, не учим |

Правило: темы human и AI должны совпадать (параграф студента → LLM переписывает).

### AI (класс 1) — сейчас догоняем API

Цель на этот прогон: **~2000 окон/язык** × несколько генераторов.

Генераторы (уже в `gen_ai_v2.py`):
- OpenRouter: DeepSeek, Qwen, GPT-4o-mini, Gemini Flash, Llama 3.3
- Anthropic: Claude Haiku

Дополнительно усилит (следующий круг):
- атаки: Google/Yandex/NLLB перевод RU↔UZ, парафраз, «humanizer»
- смешанные документы (часть абзацев AI)

### API-ключи (есть в `backend/ml/.env`)

- `OPENROUTER_API_KEY` — основной объём
- `ANTHROPIC_API_KEY` — Claude

Опционально добавить в `.env` для ещё большей ширины:
- `OPENAI_API_KEY` напрямую
- Google AI Studio / Gemini key

Бюджет API на «максимум» (оценка): **$20–80** за 5–10k генераций (дешёвые модели), Claude дороже.

## Железо

- Mac M1: DistilBERT multilingual, batch 8, 3 эпохи (~1–2 ч)
- XLM-R / mDeBERTa: Colab Pro / облачный GPU ($10–30 за прогон)

## Критерий «хорошо для школы» (SPEC)

- FPR на human ≤ **1%**
- F1 / AUC смотреть **по языкам отдельно**
- leave-one-model-out (убрать один генератор из train)

## Сейчас запущено (ускоренный прогон)

1. **12 detached** `gen_ai_v2` (ru×6 + uz-Latn×6), `--per-lang 2000`, окна ~280 слов, `max_tokens=1600`
2. Короткие старые сэмплы (<120 слов) перегенерируются
3. `logs/auto_train_v31.py` — при ≥1200 long ru и ≥600 long uz: `make_dataset_v3` → DistilBERT 3 эпохи → ONNX `runs/ai-v31` → `app/ml_model`
4. Прогресс: `logs/watch_progress.log`, воркеры: `logs/gen_fast_*.log`
5. uz-Cyrl отключён; VPS corpus → только `uz_latin`
