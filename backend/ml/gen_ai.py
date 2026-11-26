#!/usr/bin/env python3
"""
Мульти-провайдерный генератор ИИ-текстов для датасета детектора.

Имитирует модели, которыми реально пользуются студенты на бесплатных аккаунтах
(DeepSeek, ChatGPT-free, Gemini-free, Qwen, Llama, Gemma), через OpenRouter
(один ключ OPENROUTER_API_KEY) + Anthropic Haiku напрямую (ANTHROPIC_API_KEY).

Пишет .txt в data/ai/<generator>/<lang_folder>/NNN.txt, где
lang_folder ∈ {ru, uz_latin, uz_cyrillic}. uz_cyrillic получается
детерминированной транслитерацией из uz_latin (без расхода API).

Ключи читаются из backend/ml/.env (или из окружения).

Примеры:
  python gen_ai.py --dry-run                 # план + оценка стоимости
  python gen_ai.py --per-model 2             # маленький тест по всем моделям
  python gen_ai.py                           # полный прогон (веса ниже)
  python gen_ai.py --only deepseek-v3,qwen   # только эти генераторы
"""
from __future__ import annotations

import argparse
import os
import random
import time
from pathlib import Path

import httpx
import certifi

random.seed(1234)
HERE = Path(__file__).resolve().parent


def _load_env() -> None:
    env = HERE / ".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


# ── Роестр генераторов ───────────────────────────────────────────────────────
# name      — папка-генератор (data/ai/<name>/)
# provider  — openrouter | anthropic
# slug      — id модели у провайдера
# weight    — сколько эссе на язык (ru и uz_latin по отдельности)
MODELS = [
    {"name": "deepseek-v3",  "provider": "openrouter", "slug": "deepseek/deepseek-chat-v3.1",          "weight": 40},
    {"name": "deepseek-r1",  "provider": "openrouter", "slug": "deepseek/deepseek-r1-0528",            "weight": 15},
    {"name": "qwen",         "provider": "openrouter", "slug": "qwen/qwen-2.5-72b-instruct",           "weight": 35},
    {"name": "qwen3",        "provider": "openrouter", "slug": "qwen/qwen3-30b-a3b-instruct-2507",     "weight": 30},
    {"name": "gpt-4o-mini",  "provider": "openrouter", "slug": "openai/gpt-4o-mini",                   "weight": 40},
    {"name": "gpt-4o",       "provider": "openrouter", "slug": "openai/gpt-4o-2024-11-20",             "weight": 15},
    {"name": "gemini-flash", "provider": "openrouter", "slug": "google/gemini-2.5-flash-lite",         "weight": 40},
    {"name": "llama-3.3",    "provider": "openrouter", "slug": "meta-llama/llama-3.3-70b-instruct",    "weight": 30},
    {"name": "claude-haiku", "provider": "anthropic",  "slug": "claude-haiku-5-5",                     "weight": 20},
]

# прим. $/1M токенов (in, out) — только для --dry-run оценки
PRICE = {
    "deepseek/deepseek-chat-v3.1": (0.25, 0.95), "deepseek/deepseek-r1-0528": (0.571, 2.286),
    "qwen/qwen-2.5-72b-instruct": (0.36, 0.40), "qwen/qwen3-30b-a3b-instruct-2507": (0.10, 0.30),
    "openai/gpt-4o-mini": (0.15, 0.60), "openai/gpt-4o-2024-11-20": (2.50, 10.0),
    "google/gemini-2.5-flash-lite": (0.10, 0.40), "meta-llama/llama-3.3-70b-instruct": (0.71, 0.71),
    "claude-haiku-5-5": (0.80, 4.0),
}

LANG_FOLDER = {"ru": "ru", "uz-Latn": "uz_latin"}

# ── Вариативность промптов (чтобы не было одного «почерка») ───────────────────
_PERSONA_RU = [
    "Ты студент 1–2 курса университета.",
    "Ты студент, пишешь курсовую работу.",
    "Ты готовишь доклад для семинара.",
    "Ты старшекурсник, пишешь аккуратно и по делу.",
    "Ты студент колледжа, пишешь реферат.",
]
_LENGTH_RU = ["Объём 120–180 слов.", "Объём 200–300 слов.", "Объём 300–450 слов."]
_STRUCT_RU = [
    "Сделай введение, основную часть и короткий вывод.",
    "Пиши сплошным текстом, без подзаголовков.",
    "Приведи пример и аргумент.",
    "Начни с определения и раскрой тему.",
    "",
]
_PERSONA_UZ = [
    "Sen 1–2-kurs talabasisan.",
    "Sen kurs ishi yozayotgan talabasan.",
    "Sen seminar uchun ma'ruza tayyorlayapsan.",
    "Sen kollej talabasisan, referat yozyapsan.",
]
_LENGTH_UZ = ["Hajmi 120–180 so'z.", "Hajmi 200–300 so'z.", "Hajmi 300–400 so'z."]
_STRUCT_UZ = [
    "Kirish, asosiy qism va qisqa xulosa qil.",
    "Sarlavhachasiz, yaxlit matn yoz.",
    "Misol va dalil keltir.",
    "",
]


def _prompt(topic: str, lang: str) -> str:
    if lang == "ru":
        return (f"Напиши фрагмент студенческой письменной работы на тему «{topic}». "
                f"{random.choice(_PERSONA_RU)} {random.choice(_LENGTH_RU)} "
                f"{random.choice(_STRUCT_RU)} Пиши только на русском языке, "
                f"без вводных фраз вроде «конечно» и без заголовка — сразу текст.").strip()
    # uz-Latn
    return (f"«{topic}» mavzusida talabalik yozma ishidan parcha yoz. "
            f"{random.choice(_PERSONA_UZ)} {random.choice(_LENGTH_UZ)} "
            f"{random.choice(_STRUCT_UZ)} Faqat o'zbek tilida (lotin alifbosida) yoz, "
            f"sarlavhasiz va kirish iboralarsiz — darhol matnni boshla.").strip()


# ── Транслитерация uz-Latn → uz-Cyrl (детерминированная) ──────────────────────
# Все варианты апострофа (ʻ U+02BB, ʼ U+02BC, ' ' U+2018/2019, ` ´) → прямой '
_APOS = "ʻʼ‘’`´"
_UZ_MULTI = [
    ("o'", "ў"), ("O'", "Ў"),
    ("g'", "ғ"), ("G'", "Ғ"),
    ("sh", "ш"), ("Sh", "Ш"), ("SH", "Ш"),
    ("ch", "ч"), ("Ch", "Ч"), ("CH", "Ч"),
    ("ng", "нг"), ("Ng", "Нг"),
    ("yo", "ё"), ("Yo", "Ё"), ("yu", "ю"), ("Yu", "Ю"),
    ("ya", "я"), ("Ya", "Я"), ("ye", "е"), ("Ye", "Е"),
    ("ts", "ц"), ("Ts", "Ц"),
]
_UZ_SINGLE = {
    "a": "а", "b": "б", "d": "д", "e": "е", "f": "ф", "g": "г", "h": "ҳ",
    "i": "и", "j": "ж", "k": "к", "l": "л", "m": "м", "n": "н", "o": "о",
    "p": "п", "q": "қ", "r": "р", "s": "с", "t": "т", "u": "у", "v": "в",
    "x": "х", "y": "й", "z": "з",
}


def translit_uz(text: str) -> str:
    for a in _APOS:
        text = text.replace(a, "'")
    for lat, cyr in _UZ_MULTI:
        text = text.replace(lat, cyr)
    out = []
    for ch in text:
        low = ch.lower()
        if low in _UZ_SINGLE:
            cyr = _UZ_SINGLE[low]
            out.append(cyr.upper() if ch.isupper() else cyr)
        elif ch == "'":
            out.append("ъ")  # tutuq belgisi → твёрдый знак
        else:
            out.append(ch)
    return "".join(out)


# ── Вызовы API ────────────────────────────────────────────────────────────────
def _client() -> httpx.Client:
    return httpx.Client(verify=certifi.where(), timeout=120)


def _call(client: httpx.Client, model: dict, prompt: str) -> str | None:
    for attempt in range(4):
        try:
            if model["provider"] == "openrouter":
                r = client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"},
                    json={"model": model["slug"], "temperature": 0.9, "max_tokens": 900,
                          "messages": [{"role": "user", "content": prompt}]},
                )
                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"].strip()
            else:  # anthropic
                r = client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"],
                             "anthropic-version": "2023-06-01"},
                    json={"model": model["slug"], "max_tokens": 900,
                          "thinking": {"type": "disabled"},
                          "messages": [{"role": "user", "content": prompt}]},
                )
                if r.status_code == 200:
                    blocks = r.json().get("content", [])
                    return "".join(b.get("text", "") for b in blocks
                                   if b.get("type") == "text").strip() or None
            if r.status_code in (429, 500, 502, 503, 529):
                time.sleep(2 * (attempt + 1))
                continue
            print(f"      HTTP {r.status_code}: {r.text[:120]}")
            return None
        except Exception as exc:
            print(f"      err: {type(exc).__name__}: {exc}")
            time.sleep(2 * (attempt + 1))
    return None


def main() -> None:
    _load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "data"))
    ap.add_argument("--topics", default=str(HERE / "data" / "topics.txt"))
    ap.add_argument("--per-model", type=int, default=0,
                    help="фикс. число эссе на язык для каждой модели (вместо weight)")
    ap.add_argument("--only", default="", help="подмножество генераторов через запятую")
    ap.add_argument("--langs", default="ru,uz-Latn", help="какие языки генерировать через API")
    ap.add_argument("--no-cyrl", action="store_true", help="не делать uz_cyrillic транслитерацией")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    topics = [t.strip() for t in Path(args.topics).read_text(encoding="utf-8").splitlines() if t.strip()]
    langs = [l.strip() for l in args.langs.split(",") if l.strip()]
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    models = [m for m in MODELS if not only or m["name"] in only]
    out = Path(args.out)

    # план
    plan = []
    for m in models:
        n = args.per_model or m["weight"]
        for lang in langs:
            plan.append((m, lang, n))

    if args.dry_run:
        total_essays = sum(n for _, _, n in plan)
        cost = 0.0
        for m, lang, n in plan:
            pin, pout = PRICE.get(m["slug"], (0, 0))
            cost += n * (150 * pin + 550 * pout) / 1e6  # ~150 in / ~550 out токенов
        cyrl = 0 if args.no_cyrl else sum(n for m, lang, n in plan if lang == "uz-Latn")
        print(f"Моделей: {len(models)} | эссе через API: {total_essays} "
              f"(+{cyrl} uz_cyrillic транслитерацией, $0)")
        print(f"Оценка стоимости API: ~${cost:.2f}")
        for m in models:
            n = args.per_model or m["weight"]
            print(f"  {m['name']:14s} {m['slug']:40s} x{n}/язык x{len(langs)}яз")
        return

    missing = [k for k in ("OPENROUTER_API_KEY",) if not os.environ.get(k)]
    if any(m["provider"] == "anthropic" for m in models) and not os.environ.get("ANTHROPIC_API_KEY"):
        print("  (нет ANTHROPIC_API_KEY — claude-haiku пропущу)")
        models = [m for m in models if m["provider"] != "anthropic"]
    if missing:
        print(f"Нет ключей: {missing}"); return

    client = _client()
    made = skipped = failed = 0
    cyrl_made = 0
    for m in models:
        n = args.per_model or m["weight"]
        for lang in langs:
            folder = out / "ai" / m["name"] / LANG_FOLDER[lang]
            folder.mkdir(parents=True, exist_ok=True)
            print(f"[{m['name']}/{LANG_FOLDER[lang]}] цель {n}")
            for i in range(n):
                fp = folder / f"{i:03d}.txt"
                if fp.exists() and fp.stat().st_size > 200:
                    skipped += 1
                    text = fp.read_text(encoding="utf-8")
                else:
                    topic = topics[(hash(m["name"]) + i * 7) % len(topics)]
                    text = _call(client, m, _prompt(topic, lang))
                    if not text or len(text.split()) < 50:
                        failed += 1
                        continue
                    fp.write_text(text, encoding="utf-8")
                    made += 1
                    if made % 10 == 0:
                        print(f"    ...{made} готово")
                    time.sleep(0.3)
                # uz_cyrillic: всегда (пере)пишем из латиницы текущим транслитом
                if lang == "uz-Latn" and not args.no_cyrl:
                    cfp = out / "ai" / m["name"] / "uz_cyrillic" / f"{i:03d}.txt"
                    cfp.parent.mkdir(parents=True, exist_ok=True)
                    cfp.write_text(translit_uz(text), encoding="utf-8")
                    cyrl_made += 1
    print(f"\nГотово: создано={made} (+{cyrl_made} uz_cyrillic) пропущено={skipped} неудач={failed}")
    print("Дальше:  python make_dataset.py --out data")


if __name__ == "__main__":
    main()
