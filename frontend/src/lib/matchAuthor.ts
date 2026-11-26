export type RosterStudent = { name: string; group: string };

export type AuthorMatch = {
  level: "exact" | "guess" | "none";
  name: string;
  group?: string;
};

const NOT_NAMES = new Set(
  (
    "курсовая дипломная контрольная лабораторная практическая самостоятельная работа работы реферат эссе " +
    "доклад отчет проект диплом курсач финал финальная итог итоговая версия копия новый новая документ скан " +
    "глава тема вариант группа класс " +
    "essay report coursework project final draft version copy scan document doc file paper thesis work homework " +
    "kurs ishi mustaqil referat"
  ).split(" ")
);

const norm = (s: string) => s.normalize("NFC").toLowerCase().replace(/ё/g, "е").replace(/[ʻʼ’‘`']/g, "'");

function tokens(s: string): string[] {
  return s
    .normalize("NFC")
    .replace(/(\p{Ll})(\p{Lu})/gu, "$1 $2")
    .split(/[^\p{L}ʻʼ’‘`']+/u)
    .filter(Boolean);
}

export function matchAuthor(filename: string, roster: RosterStudent[]): AuthorMatch {
  const raw = tokens(filename.replace(/\.[^.]+$/, ""));
  const words = new Set(raw.map(norm));

  const full = roster.filter((s) => {
    const parts = tokens(s.name).map(norm);
    return parts.length > 1 && parts.every((p) => words.has(p));
  });
  if (full.length === 1) return { level: "exact", name: full[0].name, group: full[0].group };

  const partial = roster.filter((s) => tokens(s.name).map(norm).some((p) => p.length >= 4 && words.has(p)));
  if (full.length === 0 && partial.length === 1) {
    return { level: "guess", name: partial[0].name, group: partial[0].group };
  }
  if (full.length > 1 || partial.length > 1) return { level: "none", name: "" };

  // Списка групп может не быть: два подряд слова с заглавной похожи на имя
  for (let i = 0; i + 1 < raw.length; i++) {
    const pair = [raw[i], raw[i + 1]];
    if (pair.every((w) => /^\p{Lu}\p{Ll}{2,}$/u.test(w) && !NOT_NAMES.has(norm(w)))) {
      return { level: "guess", name: pair.join(" ") };
    }
  }
  return { level: "none", name: "" };
}
