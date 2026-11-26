#!/usr/bin/env python3
"""
Сборка датасета для обучения ИИ-детектора.

Формат выхода — JSONL, по строке на пример:
  {"text": "...", "label": 0, "lang": "ru", "generator": "human"}
  label: 0 = человек, 1 = ИИ.

Источники:
  data/human/**/*.txt              -> label 0, generator "human"
  data/ai/<generator>/**/*.txt     -> label 1, generator = имя подпапки
  --synth N                        -> добавить N синтетических примеров (бутстрап)
  --gen-llm topics.txt             -> сгенерировать ИИ-тексты через LLM-API
                                      (нужен ANTHROPIC_API_KEY или OPENAI_API_KEY)

Длинные тексты режутся на окна ~120 слов. Делёж train/val стратифицированный.
LOMO (leave-one-model-out): --exclude-generator <name> уберёт этот генератор
из train (используйте его как holdout для честной оценки).

Пример:
  python make_dataset.py --out data --synth 400
  python make_dataset.py --out data --exclude-generator gpt-4o
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
from pathlib import Path

random.seed(42)

WINDOW_WORDS = 120


def _guess_lang(text: str) -> str:
    cyr = len(re.findall(r"[а-яёА-ЯЁ]", text))
    lat_uz = len(re.findall(r"[o'g'shchngʻʼ]", text.lower()))
    if cyr > 20:
        return "ru"
    if lat_uz > 3:
        return "uz-Latn"
    return "ru"


def _windows(text: str) -> list[str]:
    words = text.split()
    if len(words) <= WINDOW_WORDS:
        return [text.strip()] if len(words) >= 40 else []
    out = []
    for i in range(0, len(words), WINDOW_WORDS):
        chunk = " ".join(words[i : i + WINDOW_WORDS])
        if len(chunk.split()) >= 40:
            out.append(chunk)
    return out


# Имя папки -> язык (узбекскую кириллицу эвристикой от русской не отличить, берём из папки)
_FOLDER_LANG = {
    "ru": "ru", "russian": "ru",
    "uz_latin": "uz-Latn", "uz-latn": "uz-Latn", "uz_latn": "uz-Latn", "uzlatin": "uz-Latn",
    "uz_cyrillic": "uz-Cyrl", "uz-cyrl": "uz-Cyrl", "uz_cyrl": "uz-Cyrl", "uzcyrillic": "uz-Cyrl",
}


def _read_folder(base: Path, label: int, default_gen: str, per_file_cap: int = 0) -> list[dict]:
    rows = []
    if not base.is_dir():
        return rows
    for p in base.glob("**/*.txt"):
        try:
            text = p.read_text(encoding="utf-8").strip()
        except Exception:
            continue
        rel = p.relative_to(base).parts
        generator = default_gen
        if label == 1 and len(rel) > 1:
            # data/ai/<generator>/[lang/]file.txt -> generator = первая подпапка
            generator = rel[0]
        # язык: из любой папки пути, иначе эвристика
        lang = None
        for part in rel[:-1]:
            if part.lower() in _FOLDER_LANG:
                lang = _FOLDER_LANG[part.lower()]
                break
        if lang is None:
            lang = _guess_lang(text)
        ws = _windows(text)
        if per_file_cap and len(ws) > per_file_cap:
            ws = ws[:per_file_cap]  # окна с начала — максимум источников при балансе
        for w in ws:
            rows.append({"text": w, "label": label, "lang": lang, "generator": generator})
    return rows


# ── Синтетический бутстрап (для первого запуска без реальных данных) ──────────
_HUMAN_BITS = [
    "Честно, я возился с этим до ночи.", "Мой научрук сказал переписать — и был прав.",
    "В Ташкенте я сам опросил нескольких владельцев кафе.", "Не всё получилось гладко, таблицы поехали.",
    "Кажется, вышло норм, хотя я не уверен.", "Пример про пекарню в Фергане мне понравился больше всего.",
    "Короче, тема сложная, но интересная.", "Я переделывал введение раза три.",
]
_AI_BITS = [
    "Следует отметить, что данный процесс играет важную роль в современной экономике.",
    "Таким образом, необходимо подчеркнуть значимость проводимых реформ.",
    "Кроме того, важно отметить, что стандарты обеспечивают прозрачность отчётности.",
    "Более того, их внедрение способствует повышению доверия со стороны инвесторов.",
    "В заключение можно сказать, что переход является актуальной задачей.",
    "Данная работа посвящена всестороннему анализу рассматриваемой проблематики.",
    "Актуальность темы обусловлена возрастающей ролью цифровых технологий.",
    "В рамках настоящего исследования были рассмотрены ключевые аспекты вопроса.",
]


def _synth(n: int) -> list[dict]:
    rows = []
    for _ in range(n // 2):
        human = " ".join(random.choices(_HUMAN_BITS, k=random.randint(5, 9)))
        ai = " ".join(random.choices(_AI_BITS, k=random.randint(5, 9)))
        rows.append({"text": human, "label": 0, "lang": "ru", "generator": "human"})
        rows.append({"text": ai, "label": 1, "lang": "ru", "generator": "synthetic"})
    return rows


def _gen_llm(topics_path: str) -> list[dict]:
    """Генерация ИИ-текстов по темам через доступный LLM-API (опционально)."""
    topics = [t.strip() for t in Path(topics_path).read_text(encoding="utf-8").splitlines() if t.strip()]
    rows: list[dict] = []
    prompt_tmpl = "Напиши абзац из студенческой работы на тему: {t}. 120-160 слов, академический стиль."

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    try:
        if anthropic_key:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_key)
            for t in topics:
                msg = client.messages.create(
                    model="claude-3-5-haiku-latest", max_tokens=400,
                    messages=[{"role": "user", "content": prompt_tmpl.format(t=t)}],
                )
                rows.append({"text": msg.content[0].text.strip(), "label": 1, "lang": "ru", "generator": "claude"})
        elif openai_key:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            for t in topics:
                r = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt_tmpl.format(t=t)}],
                )
                rows.append({"text": r.choices[0].message.content.strip(), "label": 1, "lang": "ru", "generator": "gpt-4o-mini"})
        else:
            print("  (LLM-генерация пропущена: нет ANTHROPIC_API_KEY/OPENAI_API_KEY)")
    except Exception as exc:
        print(f"  LLM-генерация прервана: {exc}")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data", help="каталог с data/ai и для train/val.jsonl")
    ap.add_argument("--human-dir", default="", help="папка человеческих текстов (ru/uz_latin/uz_cyrillic); по умолчанию <out>/human")
    ap.add_argument("--human-per-file", type=int, default=0, help="макс. окон с одного человеческого файла (0=все)")
    ap.add_argument("--balance", type=float, default=0.0, help="отношение human/AI на язык (2 = вдвое больше человека; 0=выкл)")
    ap.add_argument("--exclude-lang", default="", help="исключить языки через запятую, напр. uz-Cyrl")
    ap.add_argument("--synth", type=int, default=0, help="сколько синтетических примеров добавить")
    ap.add_argument("--gen-llm", default="", help="файл со списком тем для генерации через LLM")
    ap.add_argument("--exclude-generator", default="", help="убрать генератор из train (holdout для LOMO)")
    ap.add_argument("--val-frac", type=float, default=0.15)
    args = ap.parse_args()

    out = Path(args.out)
    human_base = Path(os.path.expanduser(args.human_dir)) if args.human_dir else (out / "human")
    rows: list[dict] = []
    rows += _read_folder(human_base, 0, "human", per_file_cap=args.human_per_file)
    rows += _read_folder(out / "ai", 1, "ai")
    if args.synth:
        rows += _synth(args.synth)
    if args.gen_llm:
        rows += _gen_llm(args.gen_llm)

    if not rows:
        print("Нет данных. Положите .txt в human-dir и data/ai/<generator>/ или добавьте --synth N.")
        return

    if args.exclude_lang:
        ex = {x.strip() for x in args.exclude_lang.split(",") if x.strip()}
        rows = [r for r in rows if r["lang"] not in ex]

    holdout = []
    if args.exclude_generator:
        keep = [r for r in rows if r["generator"] != args.exclude_generator]
        holdout = [r for r in rows if r["generator"] == args.exclude_generator]
        rows = keep
        Path(out / "holdout.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in holdout), encoding="utf-8")

    # балансировка классов по языку: human ограничиваем до balance × (кол-во ИИ)
    if args.balance > 0:
        from collections import defaultdict
        by: dict = defaultdict(lambda: {0: [], 1: []})
        for r in rows:
            by[r["lang"]][r["label"]].append(r)
        rows = []
        for lang, grp in by.items():
            ai, hu = grp[1], grp[0]
            target = int(len(ai) * args.balance)
            if target and len(hu) > target:
                hu = random.sample(hu, target)
            rows += ai + hu

    # сводка по языкам
    from collections import Counter
    per_lang: dict = {}
    for r in rows:
        d = per_lang.setdefault(r["lang"], [0, 0])
        d[r["label"]] += 1
    print("Баланс по языкам (человек / ИИ):")
    for lang, (h, a) in sorted(per_lang.items()):
        print(f"  {lang:8s} человек={h:6d}  ИИ={a:6d}")

    random.shuffle(rows)
    n_val = int(len(rows) * args.val_frac)
    val, train = rows[:n_val], rows[n_val:]

    (out / "train.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in train), encoding="utf-8")
    (out / "val.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in val), encoding="utf-8")

    n_ai = sum(r["label"] for r in rows)
    gens = Counter(r["generator"] for r in rows if r["label"] == 1)
    print(f"Готово: train={len(train)} val={len(val)} holdout={len(holdout)} | ИИ={n_ai} человек={len(rows)-n_ai}")
    print("ИИ по генераторам:", dict(gens))


if __name__ == "__main__":
    main()
