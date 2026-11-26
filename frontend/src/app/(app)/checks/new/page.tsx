"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { DEMO } from "@/lib/demo";
import { Icon, PageHeader, Ring } from "../../ui";
import { matchAuthor, type RosterStudent } from "@/lib/matchAuthor";

const MAX_FILE_SIZE = 50 * 1024 * 1024;
const MIN_TEXT = 50;
const MAX_TEXT = 500_000;
const COLLAPSE_AFTER = 5;

type Item = {
  key: string;
  file: File | null;
  text: string;
  title: string;
  author: string | null; // null — автор ещё не подтверждён и не исправлен вручную
  studentId: string;
  coauthors: { key: string; name: string; id: string }[];
};

type Job = {
  key: string;
  label: string;
  item: Item;
  author: string;
  state: "waiting" | "uploading" | "processing" | "done" | "failed";
  checkId?: string;
  similarity?: number | null;
  flags?: number;
  error?: string;
};

type Group = { id: string; name: string; students: { id: string; name: string }[] };

type CheckRow = {
  id: string;
  status: string;
  similarity_percent: number | null;
  flag_count: number;
};

const EMPTY_DRAFT: Item = { key: "draft", file: null, text: "", title: "", author: null, studentId: "", coauthors: [] };

const labelCls = "block text-xs font-medium text-gray-600 mb-1.5";

const inputCls =
  "w-full h-9 border border-gray-300 rounded-lg px-3 text-sm bg-white transition-colors hover:border-gray-400/60 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200";

function plural(n: number, one: string, few: string, many: string) {
  const a = n % 10;
  const b = n % 100;
  if (a === 1 && b !== 11) return one;
  if (a >= 2 && a <= 4 && (b < 12 || b > 14)) return few;
  return many;
}

const works = (n: number) => `${n} ${plural(n, "работу", "работы", "работ")}`;

export default function NewCheckPage() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [rejected, setRejected] = useState<string[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [textMode, setTextMode] = useState(false);
  // Вставленный текст и поля, заполненные до загрузки файла
  const [draft, setDraft] = useState<Item>(EMPTY_DRAFT);

  const [group, setGroup] = useState<string | null>(null); // null — подставляем сами
  const [groups, setGroups] = useState<Group[]>([]);
  const [showReady, setShowReady] = useState(false);

  const [excludeQuotes, setExcludeQuotes] = useState(true);
  const [excludeBiblio, setExcludeBiblio] = useState(true);
  const [minWords, setMinWords] = useState(8);
  const [saveToRepo, setSaveToRepo] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [requireStudent, setRequireStudent] = useState(false);
  const [requireGroup, setRequireGroup] = useState(false);
  const [quota, setQuota] = useState<{ used: number; limit: number } | null>(null);
  const remaining = quota ? Math.max(0, quota.limit - quota.used) : null;

  const [jobs, setJobs] = useState<Job[]>([]);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    apiFetch<Group[]>("/api/v1/groups").then(setGroups).catch(() => {});
    apiFetch<{ checks_this_month: number; quota_limit: number | null }>("/api/v1/auth/me/stats")
      .then((s) => {
        if (s.quota_limit !== null) setQuota({ used: s.checks_this_month, limit: s.quota_limit });
      })
      .catch(() => {});
    apiFetch<{
      default_exclude_quotes: boolean;
      default_exclude_bibliography: boolean;
      default_save_to_repository: boolean;
      default_min_match_words: number;
      require_student_name: boolean;
      require_group: boolean;
    }>("/api/v1/org/settings")
      .then((s) => {
        setExcludeQuotes(s.default_exclude_quotes);
        setExcludeBiblio(s.default_exclude_bibliography);
        setSaveToRepo(s.default_save_to_repository);
        setMinWords(s.default_min_match_words);
        setRequireStudent(s.require_student_name);
        setRequireGroup(s.require_group);
      })
      .catch(() => {});
  }, []);

  const draftLength = draft.text.trim().length;
  const draftReady = draftLength >= MIN_TEXT && draftLength <= MAX_TEXT;
  const all = draftReady ? [...items, draft] : items;

  const allStudents = useMemo<RosterStudent[]>(
    () => groups.flatMap((g) => g.students.map((s) => ({ name: s.name, group: g.name }))),
    [groups]
  );

  // Если все точно узнанные студенты из одной группы, подставляем её
  const suggestedGroup = useMemo(() => {
    const found = items
      .flatMap((i) => {
        if (i.author !== null) {
          const same = allStudents.filter((s) => s.name === i.author!.trim());
          return same.length === 1 ? [same[0].group] : [];
        }
        const m = matchAuthor(i.file?.name ?? "", allStudents);
        return m.level === "exact" && m.group ? [m.group] : [];
      });
    return found.length > 0 && new Set(found).size === 1 ? found[0] : "";
  }, [items, allStudents]);

  const groupName = (group ?? suggestedGroup).trim();
  const roster = useMemo(() => {
    const own = allStudents.filter((s) => s.group === groupName);
    return own.length > 0 ? own : allStudents;
  }, [allStudents, groupName]);

  const rows = all.map((item) => {
    const match = matchAuthor(item.file?.name ?? "", roster);
    const author = (item.author ?? match.name).trim();
    const unconfirmed = item.author === null && match.level === "guess";
    const missing = requireStudent && !author;
    return {
      item,
      match,
      author,
      unconfirmed,
      missing,
      // раздел строки зависит только от автоподбора, чтобы она не прыгала во время правки
      review: match.level === "guess" || (match.level === "none" && (requireStudent || all.length > 1)),
      problem: unconfirmed || missing,
    };
  });
  const review = rows.filter((r) => r.review);
  const ready = rows.filter((r) => !r.review);
  const problems = rows.filter((r) => r.problem).length;
  const unconfirmed = rows.filter((r) => r.unconfirmed).length;

  const single = all.length > 1 ? null : all[0] ?? draft;
  const singleRow = all.length === 1 ? rows[0] : null;

  const blocker =
    draftLength > 0 && !draftReady
      ? draftLength < MIN_TEXT
        ? `Вставленный текст слишком короткий: нужно ещё ${MIN_TEXT - draftLength} симв.`
        : "Вставленный текст длиннее 500 000 символов"
      : all.length === 0
      ? "Добавьте хотя бы одну работу"
      : requireGroup && !groupName
      ? "Укажите группу: этого требуют настройки школы"
      : rows.some((r) => r.missing)
      ? "Укажите автора каждой работы: этого требуют настройки школы"
      : unconfirmed > 0
      ? `Подтвердите авторов: ${unconfirmed}`
      : remaining !== null && all.length > remaining
      ? `Не хватает лимита: доступно ${remaining}, выбрано ${all.length}`
      : "";

  function addFiles(list: FileList | File[]) {
    const bad: string[] = [];
    const next: Item[] = [];
    const seen = new Set(items.filter((i) => i.file).map((i) => `${i.file!.name}:${i.file!.size}`));
    for (const f of Array.from(list)) {
      const id = `${f.name}:${f.size}`;
      if (!/\.(docx|pdf)$/i.test(f.name)) bad.push(`${f.name}: подходят только DOCX и PDF`);
      else if (f.size === 0) bad.push(`${f.name}: файл пустой`);
      else if (f.size > MAX_FILE_SIZE) bad.push(`${f.name}: больше 50 МБ`);
      else if (seen.has(id)) bad.push(`${f.name}: уже добавлен`);
      else {
        seen.add(id);
        next.push({
          key: crypto.randomUUID(),
          file: f,
          text: "",
          title: f.name.replace(/\.(docx|pdf)$/i, ""),
          author: null,
          studentId: "",
          coauthors: [],
        });
      }
    }
    if (items.length === 0 && next.length > 0 && draftLength === 0) {
      if (next.length === 1) {
        next[0].title = draft.title.trim() || next[0].title;
        next[0].author = draft.author?.trim() ? draft.author : null;
        next[0].studentId = draft.studentId;
        next[0].coauthors = draft.coauthors;
      }
      setDraft(EMPTY_DRAFT);
    }
    setItems((prev) => [...prev, ...next]);
    setRejected(bad);
  }

  function addText() {
    setItems((prev) => [...prev, { ...draft, key: crypto.randomUUID() }]);
    setDraft(EMPTY_DRAFT);
  }

  function removeItem(key: string) {
    if (key === draft.key) setDraft(EMPTY_DRAFT);
    else setItems((prev) => prev.filter((i) => i.key !== key));
  }

  function patchItem(key: string, patch: Partial<Item>) {
    if (key === draft.key) setDraft((d) => ({ ...d, ...patch }));
    else setItems((prev) => prev.map((i) => (i.key === key ? { ...i, ...patch } : i)));
  }

  function confirmAll() {
    const names = new Map(rows.filter((r) => r.unconfirmed).map((r) => [r.item.key, r.author]));
    setItems((prev) => prev.map((i) => (names.has(i.key) ? { ...i, author: names.get(i.key)! } : i)));
  }

  function patchJob(key: string, patch: Partial<Job>) {
    setJobs((prev) => prev.map((j) => (j.key === key ? { ...j, ...patch } : j)));
  }

  async function upload(list: Job[]) {
    setUploading(true);
    for (const job of list) {
      patchJob(job.key, { state: "uploading", error: undefined });
      const form = new FormData();
      if (job.item.file) form.append("file", job.item.file);
      else form.append("text_content", job.item.text);
      form.append("work_title", job.label);
      if (job.author) form.append("student_name", job.author);
      const ids = [job.item.studentId, ...job.item.coauthors.map((c) => c.id)]
        .map((id) => id.trim())
        .filter(Boolean)
        .join(", ");
      if (ids) form.append("student_id", ids);
      if (groupName) form.append("group_name", groupName);
      if (webhookUrl.trim()) form.append("webhook_url", webhookUrl.trim());
      form.append("save_to_repository", String(saveToRepo));
      form.append("exclude_quotes", String(excludeQuotes));
      form.append("exclude_bibliography", String(excludeBiblio));
      form.append("min_match_words", String(minWords));
      try {
        const res = await apiFetch<{ id: string }>("/api/v1/checks", { method: "POST", body: form });
        patchJob(job.key, { state: "processing", checkId: res.id });
        setQuota((q) => (q ? { ...q, used: q.used + 1 } : q));
      } catch (err) {
        patchJob(job.key, {
          state: "failed",
          error: err instanceof Error ? err.message : "Не удалось загрузить",
        });
      }
    }
    setUploading(false);
  }

  function start() {
    if (blocker) return;
    const list: Job[] = rows.map((r) => ({
      key: r.item.key,
      label: r.item.title.trim() || r.item.file?.name || "Вставленный текст",
      item: r.item,
      author: [r.author, ...r.item.coauthors.map((c) => c.name.trim())].filter(Boolean).join(", "),
      state: "waiting",
    }));
    setJobs(list);
    upload(list);
  }

  function reset() {
    setJobs([]);
    setItems([]);
    setDraft(EMPTY_DRAFT);
    setRejected([]);
    setGroup(null);
    setShowReady(false);
  }

  const processing = jobs.some((j) => j.state === "processing");
  const router = useRouter();

  // Одна работа → после завершения сразу открываем её отчёт.
  // Две и более → остаёмся на списке, отчёт открывается по кнопке «Отчёт».
  useEffect(() => {
    if (jobs.length !== 1) return;
    const j = jobs[0];
    if (j.state === "done" && j.checkId) router.replace(`/checks/${j.checkId}`);
  }, [jobs, router]);

  useEffect(() => {
    if (!processing) return;
    const timer = setInterval(async () => {
      try {
        const list = await apiFetch<CheckRow[]>("/api/v1/checks");
        const byId = new Map(list.map((c) => [c.id, c]));
        setJobs((prev) =>
          prev.map((j) => {
            const c = j.checkId ? byId.get(j.checkId) : undefined;
            if (j.state !== "processing" || !c) return j;
            if (c.status === "done")
              return { ...j, state: "done", similarity: c.similarity_percent, flags: c.flag_count };
            if (c.status === "failed") return { ...j, state: "failed", error: "Не удалось обработать файл" };
            return j;
          })
        );
      } catch {
        // следующая попытка через интервал
      }
    }, 3000);
    return () => clearInterval(timer);
  }, [processing]);

  useEffect(() => {
    if (!uploading) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [uploading]);

  // ── Очередь ────────────────────────────────────────────────────────────────
  if (jobs.length > 0) {
    const done = jobs.filter((j) => j.state === "done");
    const failed = jobs.filter((j) => j.state === "failed");
    const finished = done.length + failed.length;
    const rank = (j: Job) =>
      j.state === "failed" ? 1e6 : j.state === "done" ? (j.flags ?? 0) * 1000 + (j.similarity ?? 0) : -1;
    const sorted = [...jobs].sort((a, b) => rank(b) - rank(a));
    const retry = failed.filter((j) => !j.checkId);

    return (
      <>
      <PageHeader title={finished === jobs.length ? "Проверка завершена" : "Идёт проверка"} />
      <div className="p-4 md:p-8 max-w-4xl mx-auto">
        <p className="text-sm text-gray-600 mt-1" role="status">
          {uploading
            ? "Файлы загружаются. Не закрывайте вкладку до конца загрузки."
            : processing
            ? "Все файлы загружены. Можно уйти: отчёты появятся в истории."
            : `Готово: ${done.length}. С ошибкой: ${failed.length}.`}
        </p>
        {DEMO && <p className="text-sm text-gray-600 mt-1">Демо-режим: файлы не отправляются, результаты примерные.</p>}

        <div className="mt-5 h-1.5 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-600 transition-all"
            style={{ width: `${(finished / jobs.length) * 100}%` }}
          />
        </div>
        <p className="text-xs text-gray-500 mt-1.5">
          {finished} из {jobs.length}
        </p>

        <ul className="mt-4 bg-white border rounded-xl divide-y">
          {sorted.map((j) => (
            <li key={j.key} className="px-4 py-3 flex items-center gap-4">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium truncate">{j.author || "Автор не указан"}</p>
                <p className="text-xs text-gray-500 truncate">{j.label}</p>
                {j.error && <p className="text-xs text-red-700 mt-0.5">{j.error}</p>}
              </div>
              {j.state === "waiting" && <span className="text-xs text-gray-500">В очереди</span>}
              {j.state === "uploading" && <span className="text-xs text-blue-700">Загружается</span>}
              {j.state === "processing" && <span className="text-xs text-blue-700">Проверяется</span>}
              {j.state === "failed" && <span className="text-xs text-red-700">Ошибка</span>}
              {j.state === "done" && (
                <>
                  {j.similarity != null && <Ring value={j.similarity} />}
                  <span className="text-xs text-gray-600 tabular">
                    Совпадения {j.similarity != null ? `${Math.round(j.similarity)}%` : "нет данных"}
                    {(j.flags ?? 0) > 0 && (
                      <span className="block text-orange-700">Попытки обхода: {j.flags}</span>
                    )}
                  </span>
                  <Link
                    href={`/checks/${j.checkId}`}
                    className="text-sm text-blue-700 font-medium hover:underline shrink-0"
                  >
                    Отчёт
                  </Link>
                </>
              )}
            </li>
          ))}
        </ul>

        <div className="mt-5 flex flex-wrap gap-3">
          {!uploading && retry.length > 0 && (
            <button
              type="button"
              onClick={() => upload(retry)}
              className="btn btn-primary"
            >
              Повторить загрузку ({retry.length})
            </button>
          )}
          {!uploading && (
            <button
              type="button"
              onClick={reset}
              className="btn btn-secondary"
            >
              Проверить другие работы
            </button>
          )}
          <Link href="/checks" className="btn text-gray-700 hover:bg-gray-100">
            История проверок
          </Link>
        </div>
      </div>
      </>
    );
  }

  // ── Подготовка ─────────────────────────────────────────────────────────────
  const visibleReady = showReady || ready.length <= COLLAPSE_AFTER ? ready : [];

  const renderRow = (r: (typeof rows)[number]) => (
    <li key={r.item.key} className="px-4 py-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="min-w-0 flex-1 basis-48">
          <p className="text-sm font-medium truncate" title={r.item.file?.name}>
            {r.item.file?.name ?? (r.item.title.trim() || "Вставленный текст")}
          </p>
          <p className={`text-xs mt-0.5 ${r.problem ? "text-orange-700" : "text-gray-500"}`}>
            {r.missing
              ? "Укажите автора"
              : r.unconfirmed
              ? "Автор определён по имени файла, проверьте"
              : r.author
              ? r.item.author === null
                ? "Студент найден в группе"
                : "Автор указан"
              : "Без автора: сравнить стиль с прошлыми работами не получится"}
          </p>
        </div>
        <input
          className={`${inputCls} flex-1 basis-44 ${r.problem ? "!border-orange-400" : ""}`}
          value={r.item.author ?? r.match.name}
          onChange={(e) => patchItem(r.item.key, { author: e.target.value })}
          placeholder="ФИО автора"
          aria-label={`Автор: ${r.item.title}`}
          list="students"
        />
        {r.unconfirmed && (
          <button
            type="button"
            onClick={() => patchItem(r.item.key, { author: r.author })}
            className="text-sm text-blue-700 font-medium hover:underline"
          >
            Верно
          </button>
        )}
        <button
          type="button"
          onClick={() => removeItem(r.item.key)}
          className="text-sm text-gray-500 hover:text-red-700"
          aria-label={`Убрать: ${r.item.title}`}
        >
          Убрать
        </button>
      </div>
      <details className="mt-1.5">
        <summary className="text-xs text-gray-500 cursor-pointer w-fit hover:text-gray-800">
          Название и ID студента
        </summary>
        <div className="grid sm:grid-cols-2 gap-3 mt-2">
          <input
            className={inputCls}
            value={r.item.title}
            onChange={(e) => patchItem(r.item.key, { title: e.target.value })}
            placeholder="Название работы"
            aria-label="Название работы"
          />
          <input
            className={inputCls}
            value={r.item.studentId}
            onChange={(e) => patchItem(r.item.key, { studentId: e.target.value })}
            placeholder="ID студента, если есть"
            aria-label="ID студента"
          />
        </div>
      </details>
    </li>
  );

  return (
    <>
      <PageHeader title="Новая проверка" />
      <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_320px] lg:min-h-[calc(100vh-136px)]">
      <div className="p-4 md:p-8">
      <div className="max-w-3xl mx-auto">
      <div className="flex gap-0.5 bg-gray-100 rounded-lg p-0.5 w-fit">
        {[
          { label: "Файл", value: false },
          { label: "Вставить текст", value: true },
        ].map((tab) => (
          <button
            key={tab.label}
            type="button"
            aria-pressed={textMode === tab.value}
            onClick={() => setTextMode(tab.value)}
            className={`px-3 h-7 rounded-md text-sm font-medium transition-colors ${
              textMode === tab.value ? "bg-white text-gray-900 shadow-sm" : "text-gray-600 hover:text-gray-900"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <input
        ref={fileRef}
        type="file"
        accept=".docx,.pdf"
        multiple
        className="hidden"
        onChange={(e) => {
          if (e.target.files) addFiles(e.target.files);
          e.target.value = "";
        }}
      />
      {!textMode && (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            addFiles(e.dataTransfer.files);
          }}
          className={`mt-4 border border-dashed rounded-xl text-center transition-colors ${
            items.length > 0 ? "p-4" : "p-10"
          } ${dragOver ? "border-blue-500 bg-blue-50" : "border-gray-300 bg-gray-50"}`}
        >
          {items.length === 0 && (
            <p className="font-medium text-sm text-gray-800 mb-3 flex flex-col items-center gap-3">
              <span className="w-9 h-9 rounded-lg bg-white border shadow-sm flex items-center justify-center text-gray-600">
                <Icon name="upload" />
              </span>
              Перетащите сюда файлы работ
            </p>
          )}
          {singleRow?.item.file && (
            <p className="text-sm mb-3 flex flex-wrap justify-center gap-x-3">
              <span className="font-medium break-all">{singleRow.item.file.name}</span>
              <button
                type="button"
                onClick={() => removeItem(singleRow.item.key)}
                className="text-gray-600 hover:text-red-700"
              >
                Убрать
              </button>
            </p>
          )}
          <div className="flex flex-wrap justify-center items-center gap-x-4 gap-y-2">
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              className={`btn ${items.length > 0 ? "btn-secondary" : "btn-primary"}`}
            >
              {items.length > 0 ? "Добавить ещё файлы" : "Выбрать файлы"}
            </button>
          </div>
          {items.length === 0 && (
            <p className="text-xs text-gray-500 mt-3">
              DOCX или PDF до 50 МБ. Сканы распознаются.
            </p>
          )}
        </div>
      )}

      {textMode && (
        <div className="mt-4 bg-white border rounded-xl overflow-hidden">
          <textarea
            rows={10}
            className="w-full px-4 py-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500 rounded-t-xl"
            value={draft.text}
            onChange={(e) => setDraft((d) => ({ ...d, text: e.target.value }))}
            placeholder="Вставьте текст работы (минимум 50 символов)"
            aria-label="Текст работы"
          />
          <div className="px-4 py-2 border-t bg-gray-50 flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-xs text-gray-600">
            <span>
              {draftLength.toLocaleString("ru")} символов, {draft.text.trim().split(/\s+/).filter(Boolean).length} слов
            </span>
            {draftReady && (
              <button type="button" onClick={addText} className="text-blue-700 font-medium hover:underline">
                Добавить ещё один текст
              </button>
            )}
          </div>
        </div>
      )}

      {rejected.length > 0 && (
        <div role="alert" className="mt-3 bg-red-50 border border-red-200 text-red-800 text-sm px-4 py-3 rounded-lg">
          <p className="font-medium">Не добавлено: {rejected.length}</p>
          <ul className="mt-1">
            {rejected.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      <datalist id="students">
        {roster.map((s, i) => (
          <option key={i} value={s.name} />
        ))}
      </datalist>
      <datalist id="groups">
        {groups.map((g) => (
          <option key={g.id} value={g.name} />
        ))}
      </datalist>

      <div className="mt-6 bg-white border rounded-xl">
        <div className={`p-4 grid gap-3 ${single ? "sm:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]" : ""}`}>
          {single && (
            <div>
              <label htmlFor="title" className={labelCls}>Название работы</label>
              <input
                id="title"
                className={inputCls}
                value={single.title}
                onChange={(e) => patchItem(single.key, { title: e.target.value })}
                placeholder="Курсовая работа..."
              />
            </div>
          )}
          <div>
            <label htmlFor="group" className={labelCls}>
              {single ? "Группа / класс" : "Группа / класс (для всех работ)"}
              {requireGroup && <span className="text-red-600"> *</span>}
            </label>
            <input
              id="group"
              className={inputCls}
              value={group ?? suggestedGroup}
              onChange={(e) => setGroup(e.target.value)}
              placeholder="Группа А"
              list="groups"
            />
          </div>
        </div>
        {single && (
          <div className="p-4 border-t">
            <div className="grid grid-cols-[minmax(0,1fr)_112px_32px] sm:grid-cols-[minmax(0,1fr)_144px_32px] gap-x-3">
              <label htmlFor="student" className={labelCls}>
                {single.coauthors.length > 0 ? "Студенты" : "Студент"}
                {requireStudent && <span className="text-red-600"> *</span>}
              </label>
              <label htmlFor="student-id" className={`${labelCls} col-span-2`}>ID студента</label>
            </div>
            <div className="space-y-2">
              <div className="grid grid-cols-[minmax(0,1fr)_112px_32px] sm:grid-cols-[minmax(0,1fr)_144px_32px] gap-x-3 items-center">
                <input
                  id="student"
                  className={`${inputCls} ${singleRow?.problem ? "!border-orange-400" : ""}`}
                  value={single.author ?? singleRow?.match.name ?? ""}
                  onChange={(e) => patchItem(single.key, { author: e.target.value })}
                  placeholder="ФИО"
                  list="students"
                />
                <input
                  id="student-id"
                  className={inputCls}
                  value={single.studentId}
                  onChange={(e) => patchItem(single.key, { studentId: e.target.value })}
                  placeholder="2024-0152"
                />
              </div>
              {singleRow?.unconfirmed && (
                <p className="text-xs text-orange-700">
                  Определён по имени файла, проверьте.{" "}
                  <button
                    type="button"
                    onClick={() => patchItem(single.key, { author: singleRow.author })}
                    className="text-blue-700 font-medium hover:underline"
                  >
                    Верно
                  </button>
                </p>
              )}
              {single.coauthors.map((c, i) => (
                <div
                  key={c.key}
                  className="grid grid-cols-[minmax(0,1fr)_112px_32px] sm:grid-cols-[minmax(0,1fr)_144px_32px] gap-x-3 items-center"
                >
                  <input
                    className={inputCls}
                    value={c.name}
                    onChange={(e) =>
                      patchItem(single.key, {
                        coauthors: single.coauthors.map((x) => (x.key === c.key ? { ...x, name: e.target.value } : x)),
                      })
                    }
                    placeholder="ФИО"
                    aria-label={`Студент ${i + 2}`}
                    list="students"
                    autoFocus={!c.name && !c.id}
                  />
                  <input
                    className={inputCls}
                    value={c.id}
                    onChange={(e) =>
                      patchItem(single.key, {
                        coauthors: single.coauthors.map((x) => (x.key === c.key ? { ...x, id: e.target.value } : x)),
                      })
                    }
                    placeholder={i === 0 ? "2024-0153" : ""}
                    aria-label={`ID студента ${i + 2}`}
                  />
                  <button
                    type="button"
                    onClick={() =>
                      patchItem(single.key, { coauthors: single.coauthors.filter((x) => x.key !== c.key) })
                    }
                    className="w-8 h-8 rounded-lg flex items-center justify-center text-gray-400 hover:text-red-700 hover:bg-gray-100 transition-colors"
                    aria-label={`Убрать студента ${i + 2}`}
                  >
                    <Icon name="close" />
                  </button>
                </div>
              ))}
            </div>
            <button
              type="button"
              onClick={() =>
                patchItem(single.key, {
                  coauthors: [...single.coauthors, { key: crypto.randomUUID(), name: "", id: "" }],
                })
              }
              className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-blue-700 hover:text-blue-800"
            >
              <Icon name="plus" />
              Добавить студента
            </button>
          </div>
        )}
      </div>

      {!single && review.length > 0 && (
        <section className="mt-6">
          <div className="flex items-baseline justify-between gap-3 mb-2">
            <h2 className="text-base font-semibold">
              {problems > 0
                ? `Проверьте авторов: ${problems}`
                : review.some((r) => !r.author)
                ? `Без автора: ${review.filter((r) => !r.author).length}`
                : `Авторы проверены: ${review.length}`}
            </h2>
            {unconfirmed > 1 && (
              <button
                type="button"
                onClick={confirmAll}
                className="text-sm text-blue-700 font-medium hover:underline"
              >
                Все верно
              </button>
            )}
          </div>
          <ul className="bg-white border rounded-xl divide-y">{review.map(renderRow)}</ul>
        </section>
      )}

      {!single && ready.length > 0 && (
        <section className="mt-6">
          <div className="flex items-baseline justify-between gap-3 mb-2">
            <h2 className="text-base font-semibold">Готовы к проверке: {ready.length}</h2>
            {ready.length > COLLAPSE_AFTER && (
              <button
                type="button"
                onClick={() => setShowReady(!showReady)}
                className="text-sm text-blue-700 font-medium hover:underline"
              >
                {showReady ? "Свернуть" : "Показать"}
              </button>
            )}
          </div>
          {visibleReady.length > 0 && (
            <ul className="bg-white border rounded-xl divide-y">{visibleReady.map(renderRow)}</ul>
          )}
        </section>
      )}

      </div>
      </div>
      <aside className="p-4 md:px-8 lg:p-6 border-t lg:border-t-0 lg:border-l space-y-6">
      <div className="space-y-3">
        <p className="text-xs font-medium text-gray-500">
          {single ? "Исключения" : "Исключения (для всех)"}
        </p>
        <label className="flex items-start gap-2.5 cursor-pointer text-sm text-gray-800 [&>input]:mt-0.5">
          <input type="checkbox" checked={excludeQuotes} onChange={(e) => setExcludeQuotes(e.target.checked)} />
          {'Исключить цитаты в кавычках «» и\u00a0""'}
        </label>
        <label className="flex items-start gap-2.5 cursor-pointer text-sm text-gray-800 [&>input]:mt-0.5">
          <input type="checkbox" checked={excludeBiblio} onChange={(e) => setExcludeBiblio(e.target.checked)} />
          Исключить список литературы
        </label>
        <label className="flex items-start gap-2.5 cursor-pointer text-sm text-gray-800 [&>input]:mt-0.5">
          <input type="checkbox" checked={saveToRepo} onChange={(e) => setSaveToRepo(e.target.checked)} />
          {single ? "Сохранить работу" : "Сохранить работы"} в репозиторий школы для будущих сравнений
        </label>
      </div>

      <div className="border-t pt-4">
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          aria-expanded={showAdvanced}
          className="-mx-2 px-2 py-2 w-[calc(100%+16px)] text-left rounded-lg hover:bg-gray-50 transition-colors"
        >
          <span className="flex items-center justify-between text-xs font-medium text-gray-500">
            Дополнительно
            <Icon name="chevron" className={`transition-transform ${showAdvanced ? "rotate-180" : ""}`} />
          </span>
          {!showAdvanced && (
            <span className="mt-2 block space-y-2 text-sm">
              <span className="flex justify-between gap-4">
                <span className="text-gray-600">Учитывать совпадения</span>
                <span className="text-gray-900 whitespace-nowrap">
                  от {minWords} {minWords % 10 === 1 && minWords !== 11 ? "слова" : "слов"}
                </span>
              </span>
              <span className="flex justify-between gap-4">
                <span className="text-gray-600">Webhook</span>
                <span className={`min-w-0 truncate ${webhookUrl.trim() ? "text-gray-900" : "text-gray-500"}`}>
                  {webhookUrl.trim().replace(/^https?:\/\//, "") || "Не задан"}
                </span>
              </span>
            </span>
          )}
        </button>
        {showAdvanced && (
          <div className="pt-2 space-y-4">
            <div>
              <label htmlFor="min-words" className={labelCls}>Минимальная длина совпадения (слов)</label>
              <input
                id="min-words"
                type="number"
                min={1}
                max={50}
                value={minWords}
                onChange={(e) => setMinWords(Math.max(1, Math.min(50, Number(e.target.value) || 1)))}
                className={`${inputCls} !w-24`}
              />
            </div>
            <div>
              <label htmlFor="webhook" className={labelCls}>Webhook URL: POST-уведомление после завершения</label>
              <input
                id="webhook"
                type="url"
                className={inputCls}
                value={webhookUrl}
                onChange={(e) => setWebhookUrl(e.target.value)}
                placeholder="https://your-server.com/webhook"
              />
              <p className="text-xs text-gray-500 mt-1.5">
                Получите JSON с результатом на ваш сервер. Поле X-Antiplagiat-Event: check.completed.
              </p>
            </div>
          </div>
        )}
      </div>

      {quota && (
        <div className="border-t pt-5">
          <div className="flex items-baseline justify-between text-sm tabular">
            <span className="text-gray-600">Проверок в этом месяце</span>
            <span className="font-medium">
              {quota.used.toLocaleString("ru")} <span className="text-gray-500 font-normal">/ {quota.limit.toLocaleString("ru")}</span>
            </span>
          </div>
          <div className="mt-2 h-1 rounded-full bg-gray-200 overflow-hidden">
            <div
              className={`h-full rounded-full ${
                remaining === 0 ? "bg-red-600" : quota.used >= quota.limit * 0.9 ? "bg-yellow-500" : "bg-blue-600"
              }`}
              style={{ width: `${Math.min(100, (quota.used / quota.limit) * 100)}%` }}
            />
          </div>
          {remaining === 0 && <p className="mt-2 text-xs text-red-700">Лимит исчерпан</p>}
        </div>
      )}
      </aside>
      </div>

      <div className="sticky bottom-0 px-4 md:px-6 py-3 md:py-[15px] bg-white border-t flex flex-wrap items-center justify-between gap-3">
        <p className={`text-sm ${blocker && all.length > 0 ? "text-orange-700" : "text-gray-600"}`} role="status">
          {blocker ||
            (remaining !== null
              ? `После проверки останется ${(remaining - all.length).toLocaleString("ru")} в этом месяце`
              : "Всё готово")}
        </p>
        <button
          type="button"
          onClick={start}
          disabled={!!blocker}
          className="btn btn-primary"
        >
          {all.length === 0 ? "Проверить" : `Проверить ${works(all.length)}`}
        </button>
      </div>
    </>
  );
}
