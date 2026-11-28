#!/usr/bin/env python3
"""
Парная генерация ИИ-сэмплов для dataset_v2.

Берёт человеческий абзац и просит LLM:
  - переписать в том же стиле и длине, ИЛИ
  - продолжить текст в том же регистре/стиле.

Это ближе к реальному «студент скормил кусок и попросил дописать»,
чем генерация с нуля по теме (v1).

Ключи (backend/ml/.env):
  OPENROUTER_API_KEY  — основной (DeepSeek / Qwen / GPT / Gemini / Llama)
  ANTHROPIC_API_KEY   — опционально (Claude Haiku)

Примеры:
  python gen_ai_v2.py --dry-run
  python gen_ai_v2.py --per-lang 50 --mode rewrite
  python gen_ai_v2.py --corpus ~/Desktop/human_corpus --out data/ai_v2
"""
from __future__ import annotations

import argparse
import json
import os
import random
import time
from pathlib import Path

random.seed(2026)
HERE = Path(__file__).resolve().parent


def _load_env() -> None:
    env = HERE / ".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


MODELS = [
    {"name": "deepseek-v3", "provider": "openrouter", "slug": "deepseek/deepseek-chat-v3.1", "weight": 1},
    {"name": "qwen3", "provider": "openrouter", "slug": "qwen/qwen3-30b-a3b-instruct-2507", "weight": 1},
    {"name": "gpt-4o-mini", "provider": "openrouter", "slug": "openai/gpt-4o-mini", "weight": 1},
    {"name": "gemini-flash", "provider": "openrouter", "slug": "google/gemini-2.5-flash-lite", "weight": 1},
    {"name": "llama-3.3", "provider": "openrouter", "slug": "meta-llama/llama-3.3-70b-instruct", "weight": 1},
    {"name": "claude-haiku", "provider": "anthropic", "slug": "claude-haiku-5-5", "weight": 1},
]

LANG_FOLDER = {"ru": "ru", "uz-Latn": "uz_latin", "uz-Cyrl": "uz_cyrillic"}
BUCKET = {"ru": "ru", "uz-Latn": "uz_latin", "uz-Cyrl": "uz_cyrillic"}


def _windows(text: str, size: int = 280, min_w: int = 80) -> list[str]:
    """Более длинные куски (~страница абзацев) — лучше для детектора на реальных работах."""
    words = text.split()
    if len(words) < min_w:
        return []
    if len(words) <= size:
        return [text.strip()]
    out = []
    for i in range(0, len(words), size):
        chunk = " ".join(words[i : i + size]).strip()
        if len(chunk.split()) >= min_w:
            out.append(chunk)
    return out


def _prompt(src: str, lang: str, mode: str) -> str:
    n = len(src.split())
    if lang == "ru":
        if mode == "continue":
            return (
                f"Продолжи следующий фрагмент студенческой работы в том же стиле и регистре. "
                f"Добавь примерно {max(40, n // 2)}–{n} слов. Не повторяй исходный текст целиком, "
                f"не пиши заголовок и комментарии — только продолжение.\n\nТекст:\n{src}"
            )
        return (
            f"Перепиши фрагмент студенческой работы своими словами, сохранив смысл, стиль и примерно "
            f"ту же длину (~{n} слов). Не улучшай «до идеала», оставь академический тон. "
            f"Без заголовка и пояснений — только текст.\n\nТекст:\n{src}"
        )
    if lang == "uz-Cyrl":
        # генерим через латиницу-промпт сложнее; просим кириллицу напрямую
        if mode == "continue":
            return (
                f"Қуйидаги талаба иши парчасини худди шу услубда давом эттиринг. "
                f"Тахминан {max(40, n // 2)}–{n} сўз қўшинг. Сарлавҳасиз, фақат давом.\n\nМатн:\n{src}"
            )
        return (
            f"Талаба иши парчасини ўз сўзларингиз билан қайта ёзинг, маъно ва услубни сақлаб, "
            f"ҳажми ~{n} сўз бўлсин. Фақат ўзбек кирилл ёзувида, шарҳсиз.\n\nМатн:\n{src}"
        )
    # uz-Latn
    if mode == "continue":
        return (
            f"Quyidagi talaba ishi parchasiini xuddi shu uslubda davom ettir. "
            f"Taxminan {max(40, n // 2)}–{n} so'z qo'sh. Sarlavhasiz, faqat davom.\n\nMatn:\n{src}"
        )
    return (
        f"Talaba ishi parchasini o'z so'zlaring bilan qayta yoz, ma'no va uslubni saqlab, "
        f"hajmi ~{n} so'z bo'lsin. Faqat o'zbek lotin yozuvida, izohsiz.\n\nMatn:\n{src}"
    )


def _call(client, model: dict, prompt: str) -> str | None:
    for attempt in range(4):
        try:
            if model["provider"] == "openrouter":
                r = client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"},
                    json={
                        "model": model["slug"],
                        "temperature": 0.85,
                        "max_tokens": 1600,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"].strip()
            else:
                r = client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                        "anthropic-version": "2023-06-01",
                    },
                    json={
                        "model": model["slug"],
                        "max_tokens": 1600,
                        "thinking": {"type": "disabled"},
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                if r.status_code == 200:
                    blocks = r.json().get("content", [])
                    return "".join(
                        b.get("text", "") for b in blocks if b.get("type") == "text"
                    ).strip() or None
            if r.status_code in (429, 500, 502, 503, 529):
                time.sleep(2 * (attempt + 1))
                continue
            print(f"      HTTP {r.status_code}: {r.text[:140]}")
            return None
        except Exception as exc:  # noqa: BLE001
            print(f"      err: {type(exc).__name__}: {exc}")
            time.sleep(2 * (attempt + 1))
    return None


def _sample_human_chunks(corpus: Path, lang: str, n: int, prefer_pre2022: bool) -> list[tuple[str, str]]:
    """Возвращает [(doc_id, chunk), ...]."""
    folder = corpus / BUCKET[lang]
    manifest: dict[str, dict] = {}
    mp = corpus / "manifest.jsonl"
    if mp.is_file():
        for line in mp.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("file"):
                manifest[row["file"]] = row

    files = sorted(folder.glob("*.txt")) if folder.is_dir() else []
    if prefer_pre2022:
        pre = []
        for p in files:
            meta = manifest.get(f"{BUCKET[lang]}/{p.name}", {})
            y = meta.get("year")
            try:
                if y is None or int(y) <= 2022:
                    pre.append(p)
            except (TypeError, ValueError):
                pre.append(p)
        if len(pre) >= max(10, n // 2):
            files = pre

    random.shuffle(files)
    out: list[tuple[str, str]] = []
    for p in files:
        if len(out) >= n:
            break
        try:
            text = p.read_text(encoding="utf-8-sig").strip()
        except Exception:
            continue
        chunks = _windows(text)
        if not chunks:
            continue
        chunk = random.choice(chunks)
        out.append((f"{BUCKET[lang]}/{p.name}", chunk))
    return out


def main() -> None:
    _load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(Path.home() / "Desktop" / "human_corpus"))
    ap.add_argument("--out", default=str(HERE / "data" / "ai_v2"))
    ap.add_argument("--per-lang", type=int, default=200, help="пар на язык (сумма по моделям)")
    ap.add_argument("--mode", choices=["rewrite", "continue", "mix"], default="mix")
    ap.add_argument("--langs", default="ru,uz-Latn")
    ap.add_argument("--only", default="", help="подмножество генераторов")
    ap.add_argument("--no-cyrl-from-latn", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    langs = [x.strip() for x in args.langs.split(",") if x.strip()]
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    models = [m for m in MODELS if not only or m["name"] in only]
    corpus = Path(args.corpus).expanduser()
    out = Path(args.out)

    if args.dry_run:
        print(f"Моделей: {len(models)} | языков: {langs} | пар/язык: {args.per_lang}")
        print(f"Режим: {args.mode}")
        print("Ключи:")
        print("  OPENROUTER_API_KEY:", "set" if os.environ.get("OPENROUTER_API_KEY") else "MISSING")
        print("  ANTHROPIC_API_KEY:", "set" if os.environ.get("ANTHROPIC_API_KEY") else "missing (optional)")
        for m in models:
            print(f"  - {m['name']}: {m['provider']} / {m['slug']}")
        return

    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("Нужен OPENROUTER_API_KEY в backend/ml/.env")
    if any(m["provider"] == "anthropic" for m in models) and not os.environ.get("ANTHROPIC_API_KEY"):
        print("  (нет ANTHROPIC_API_KEY — claude-haiku пропущу)")
        models = [m for m in models if m["provider"] != "anthropic"]

    import certifi
    import httpx

    client = httpx.Client(verify=certifi.where(), timeout=120)
    made = skipped = failed = 0

    for lang in langs:
        seeds = _sample_human_chunks(corpus, lang, args.per_lang, prefer_pre2022=True)
        if not seeds:
            print(f"[{lang}] нет human-чанков, пропуск")
            continue
        print(f"[{lang}] seeds={len(seeds)}")
        for i, (doc_id, chunk) in enumerate(seeds):
            model = models[i % len(models)]
            mode = (
                random.choice(["rewrite", "continue"])
                if args.mode == "mix"
                else args.mode
            )
            folder = out / model["name"] / LANG_FOLDER[lang]
            folder.mkdir(parents=True, exist_ok=True)
            fp = folder / f"{i:04d}.txt"
            meta_fp = folder / f"{i:04d}.meta.json"
            # короткие старые куски (<120 слов) перегенерируем под длинные окна
            existing = fp.read_text(encoding="utf-8") if fp.exists() else ""
            if existing and len(existing.split()) >= 120 and fp.stat().st_size > 150:
                skipped += 1
                text = existing
            else:
                text = None
                for _try in range(2):
                    text = _call(client, model, _prompt(chunk, lang, mode))
                    if text and len(text.split()) >= 100:
                        break
                    text = None
                if not text:
                    failed += 1
                    continue
                fp.write_text(text, encoding="utf-8")
                meta_fp.write_text(
                    json.dumps(
                        {
                            "source_doc": doc_id,
                            "mode": mode,
                            "model": model["name"],
                            "lang": lang,
                            "src_words": len(chunk.split()),
                            "out_words": len(text.split()),
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                made += 1
                if made % 10 == 0:
                    print(f"    [{model['name']}/{lang}] ...{made} готово", flush=True)
                time.sleep(0.05)  # максимальный темп; 429 → ретраи в _call

            if lang == "uz-Latn" and not args.no_cyrl_from_latn:
                from gen_ai import translit_uz

                cfp = out / model["name"] / "uz_cyrillic" / f"{i:04d}.txt"
                cfp.parent.mkdir(parents=True, exist_ok=True)
                cfp.write_text(translit_uz(text), encoding="utf-8")

    print(f"\nГотово: создано={made} пропущено={skipped} неудач={failed}")
    print("Дальше: python make_dataset_v2.py --ai-dir data/ai_v2 --out data/v2")


if __name__ == "__main__":
    main()
