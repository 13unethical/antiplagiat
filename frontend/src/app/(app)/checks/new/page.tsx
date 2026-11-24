"use client";

import { useRef, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

export default function NewCheckPage() {
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);
  const [inputMode, setInputMode] = useState<"file" | "text">("file");
  const [file, setFile] = useState<File | null>(null);
  const [textContent, setTextContent] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  // form fields
  const [title, setTitle] = useState("");
  const [student, setStudent] = useState("");
  const [studentId, setStudentId] = useState("");
  const [group, setGroup] = useState("");
  const [excludeQuotes, setExcludeQuotes] = useState(true);
  const [excludeBiblio, setExcludeBiblio] = useState(true);
  const [saveToRepo, setSaveToRepo] = useState(false);
  const [requireStudent, setRequireStudent] = useState(false);
  const [requireGroup, setRequireGroup] = useState(false);

  // Load quota info
  useEffect(() => {
    apiFetch<{ checks_this_month: number; quota_limit: number | null; personal_quota: number | null }>(
      "/api/v1/auth/me/stats"
    )
      .then((s) => setQuotaInfo({ checks_this_month: s.checks_this_month, quota_limit: s.quota_limit }))
      .catch(() => {});
  }, []);

  // Load org defaults
  useEffect(() => {
    apiFetch<{
      default_exclude_quotes: boolean;
      default_exclude_bibliography: boolean;
      default_save_to_repository: boolean;
      require_student_name: boolean;
      require_group: boolean;
    }>("/api/v1/org/settings")
      .then((s) => {
        setExcludeQuotes(s.default_exclude_quotes);
        setExcludeBiblio(s.default_exclude_bibliography);
        setSaveToRepo(s.default_save_to_repository);
        setRequireStudent(s.require_student_name);
        setRequireGroup(s.require_group);
      })
      .catch(() => {});
  }, []);
  const [quotaInfo, setQuotaInfo] = useState<{
    checks_this_month: number;
    quota_limit: number | null;
  } | null>(null);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);

  // ── Групповая (пакетная) проверка ────────────────────────────────────────
  type GroupRow = { key: string; name: string; studentId: string; file: File | null };
  type BatchResult = {
    key: string;
    name: string;
    checkId?: string;
    status: "pending" | "running" | "done" | "error";
    error?: string;
  };
  const [checkMode, setCheckMode] = useState<"single" | "group">("single");
  const [rows, setRows] = useState<GroupRow[]>([
    { key: crypto.randomUUID(), name: "", studentId: "", file: null },
    { key: crypto.randomUUID(), name: "", studentId: "", file: null },
  ]);
  const [batchRunning, setBatchRunning] = useState(false);
  const [batchResults, setBatchResults] = useState<BatchResult[]>([]);

  function addRow() {
    setRows((r) => [...r, { key: crypto.randomUUID(), name: "", studentId: "", file: null }]);
  }
  function removeRow(key: string) {
    setRows((r) => (r.length <= 1 ? r : r.filter((x) => x.key !== key)));
  }
  function updateRow(key: string, patch: Partial<GroupRow>) {
    setRows((r) => r.map((x) => (x.key === key ? { ...x, ...patch } : x)));
  }

  async function runBatch() {
    const ready = rows.filter((r) => r.file && r.name.trim());
    if (ready.length === 0) {
      setError("Добавьте хотя бы одного студента с именем и файлом");
      return;
    }
    setError("");
    setBatchRunning(true);
    setBatchResults(ready.map((r) => ({ key: r.key, name: r.name.trim(), status: "pending" })));
    const token = localStorage.getItem("access_token");
    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

    for (const r of ready) {
      setBatchResults((prev) =>
        prev.map((b) => (b.key === r.key ? { ...b, status: "running" } : b))
      );
      try {
        const form = new FormData();
        form.append("file", r.file!);
        form.append("work_title", r.name.trim());
        form.append("student_name", r.name.trim());
        if (r.studentId.trim()) form.append("student_id", r.studentId.trim());
        if (group) form.append("group_name", group);
        form.append("save_to_repository", String(saveToRepo));
        form.append("exclude_quotes", String(excludeQuotes));
        form.append("exclude_bibliography", String(excludeBiblio));
        const res = await fetch(`${apiBase}/api/v1/checks`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: form,
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail ?? "Ошибка загрузки");
        }
        const check = await res.json();
        setBatchResults((prev) =>
          prev.map((b) => (b.key === r.key ? { ...b, status: "done", checkId: check.id } : b))
        );
      } catch (err) {
        setBatchResults((prev) =>
          prev.map((b) =>
            b.key === r.key
              ? { ...b, status: "error", error: err instanceof Error ? err.message : "Ошибка" }
              : b
          )
        );
      }
    }
    setBatchRunning(false);
  }

  function selectFile(f: File) {
    if (!f.name.match(/\.(docx|pdf)$/i)) {
      setError("Только .docx и .pdf файлы");
      return;
    }
    setFile(f);
    setError("");
    if (!title) setTitle(f.name.replace(/\.(docx|pdf)$/i, ""));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (inputMode === "file" && !file) { setError("Выберите файл"); return; }
    if (inputMode === "text" && textContent.trim().length < 50) { setError("Текст слишком короткий (минимум 50 символов)"); return; }
    if (requireStudent && !student.trim()) { setError("ФИО студента обязательно для заполнения"); return; }
    if (requireGroup && !group.trim()) { setError("Группа/класс обязательны для заполнения"); return; }
    setUploading(true);
    setError("");
    try {
      const form = new FormData();
      if (inputMode === "file") {
        form.append("file", file!);
      } else {
        form.append("text_content", textContent.trim());
      }
      if (title) form.append("work_title", title);
      if (student) form.append("student_name", student);
      if (studentId) form.append("student_id", studentId);
      if (group) form.append("group_name", group);
      if (webhookUrl) form.append("webhook_url", webhookUrl);
      form.append("save_to_repository", String(saveToRepo));
      form.append("exclude_quotes", String(excludeQuotes));
      form.append("exclude_bibliography", String(excludeBiblio));
      const token = localStorage.getItem("access_token");
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/checks`,
        { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: form }
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? "Ошибка загрузки");
      }
      const check = await res.json();
      router.push(`/checks/${check.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки");
      setUploading(false);
    }
  }

  if (uploading) {
    return (
      <div className="p-8 max-w-lg">
        <h1 className="text-xl font-semibold mb-6">Новая проверка</h1>
        <div className="bg-white border rounded-xl p-6">
          <p className="font-medium text-sm mb-4 flex items-center gap-2">
            <span className="inline-block w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
            Идёт проверка · {file?.name}
          </p>
          <div className="space-y-2.5 text-sm">
            <div className="flex items-center gap-2 text-green-600">
              <span>✓</span><span>Извлекаем текст и нормализуем</span>
            </div>
            <div className="flex items-center gap-2 text-green-600">
              <span>✓</span><span>Flagged: ищем подмену символов</span>
            </div>
            <div className="flex items-center gap-2 text-blue-600">
              <span className="animate-spin inline-block">◌</span>
              <span>Ищем совпадения в базе</span>
            </div>
          </div>
          <p className="text-xs text-gray-400 mt-5">
            Обычно 30–90 секунд. Можно закрыть страницу — отчёт появится в истории.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-2xl">
      <h1 className="text-xl font-semibold mb-6">Новая проверка</h1>

      {/* Режим: одиночная / групповая */}
      <div className="flex gap-1 bg-gray-100 rounded-xl p-1 w-fit mb-5">
        <button
          type="button"
          onClick={() => setCheckMode("single")}
          className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            checkMode === "single" ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
          }`}
        >
          Одиночная
        </button>
        <button
          type="button"
          onClick={() => setCheckMode("group")}
          className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            checkMode === "group" ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
          }`}
        >
          Групповая
        </button>
      </div>

      {checkMode === "single" && (
      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Input mode tabs */}
        <div className="flex gap-1 bg-gray-100 rounded-xl p-1 w-fit">
          <button
            type="button"
            onClick={() => setInputMode("file")}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              inputMode === "file" ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
            }`}
          >
            Файл
          </button>
          <button
            type="button"
            onClick={() => setInputMode("text")}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              inputMode === "text" ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
            }`}
          >
            Вставить текст
          </button>
        </div>

        {/* File upload */}
        {inputMode === "file" && <div
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            const f = e.dataTransfer.files[0];
            if (f) selectFile(f);
          }}
          className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
            dragOver
              ? "border-blue-400 bg-blue-50"
              : file
              ? "border-green-400 bg-green-50"
              : "border-gray-200 hover:border-gray-300 bg-white"
          }`}
        >
          <input
            ref={fileRef}
            type="file"
            accept=".docx,.pdf"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) selectFile(f);
              e.target.value = "";
            }}
          />
          {file ? (
            <>
              <div className="text-3xl mb-2">📄</div>
              <p className="font-medium text-sm text-green-700">{file.name}</p>
              <p className="text-xs text-gray-400 mt-1">
                {(file.size / 1024).toFixed(0)} KB · нажмите чтобы изменить
              </p>
            </>
          ) : (
            <>
              <div className="text-3xl mb-2 text-gray-300">↑</div>
              <p className="font-medium text-sm text-gray-700">
                Перетащите файл или выберите на компьютере
              </p>
              <p className="text-xs text-gray-400 mt-1">DOCX, PDF · сканы распознаются (OCR)</p>
            </>
          )}
        </div>}

        {/* Text input */}
        {inputMode === "text" && (
          <div className="bg-white border rounded-xl overflow-hidden">
            <textarea
              rows={12}
              className="w-full px-4 py-3 text-sm focus:outline-none resize-none font-mono"
              placeholder="Вставьте текст работы сюда... (минимум 50 символов)"
              value={textContent}
              onChange={(e) => setTextContent(e.target.value)}
            />
            <div className="px-4 py-2 border-t bg-gray-50 flex justify-between text-xs text-gray-400">
              <span>{textContent.length} символов</span>
              <span>{textContent.trim().split(/\s+/).filter(Boolean).length} слов</span>
            </div>
          </div>
        )}

        {/* Meta */}
        <div className="bg-white border rounded-xl p-4 space-y-3">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">
              Название работы
            </label>
            <input
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Курсовая работа..."
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">
                Студент{requireStudent && <span className="text-red-500 ml-0.5">*</span>}
              </label>
              <input
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={student}
                onChange={(e) => setStudent(e.target.value)}
                placeholder="ФИО"
                required={requireStudent}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">
                ID студента
              </label>
              <input
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={studentId}
                onChange={(e) => setStudentId(e.target.value)}
                placeholder="например, 2024-0152"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-xs font-medium text-gray-500 mb-1">
                Группа / класс{requireGroup && <span className="text-red-500 ml-0.5">*</span>}
              </label>
              <input
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={group}
                onChange={(e) => setGroup(e.target.value)}
                placeholder="Группа А"
                required={requireGroup}
              />
            </div>
          </div>
        </div>

        {/* Exclusions */}
        <div className="bg-white border rounded-xl p-4 space-y-2.5">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">
            Исключения
          </p>
          <label className="flex items-center gap-2.5 cursor-pointer">
            <input
              type="checkbox"
              checked={excludeQuotes}
              onChange={(e) => setExcludeQuotes(e.target.checked)}
              className="accent-blue-600"
            />
            <span className="text-sm text-gray-700">Исключить цитаты в кавычках «» и ""</span>
          </label>
          <label className="flex items-center gap-2.5 cursor-pointer">
            <input
              type="checkbox"
              checked={excludeBiblio}
              onChange={(e) => setExcludeBiblio(e.target.checked)}
              className="accent-blue-600"
            />
            <span className="text-sm text-gray-700">Исключить список литературы</span>
          </label>
          <label className="flex items-center gap-2.5 cursor-pointer">
            <input
              type="checkbox"
              checked={saveToRepo}
              onChange={(e) => setSaveToRepo(e.target.checked)}
              className="accent-blue-600"
            />
            <span className="text-sm text-gray-700">
              Сохранить работу в репозиторий школы для будущих сравнений
            </span>
          </label>
        </div>

        {/* Advanced: webhook */}
        <div className="bg-white border rounded-xl overflow-hidden">
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="w-full flex items-center justify-between px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider hover:bg-gray-50 transition-colors"
          >
            <span>Дополнительно</span>
            <span>{showAdvanced ? "▲" : "▼"}</span>
          </button>
          {showAdvanced && (
            <div className="px-4 pb-4 border-t">
              <label className="block text-xs font-medium text-gray-500 mt-3 mb-1">
                Webhook URL{" "}
                <span className="font-normal text-gray-400">— POST уведомление после завершения</span>
              </label>
              <input
                type="url"
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={webhookUrl}
                onChange={(e) => setWebhookUrl(e.target.value)}
                placeholder="https://your-server.com/webhook"
              />
              <p className="text-xs text-gray-400 mt-1.5">
                Получите JSON с результатом на ваш сервер. Поле X-Antiplagiat-Event: check.completed.
              </p>
            </div>
          )}
        </div>

        {quotaInfo && quotaInfo.quota_limit !== null && (
          <div className={`text-sm px-3 py-2 rounded-lg border ${
            quotaInfo.checks_this_month >= quotaInfo.quota_limit
              ? "bg-red-50 border-red-200 text-red-700"
              : quotaInfo.checks_this_month >= quotaInfo.quota_limit * 0.9
              ? "bg-yellow-50 border-yellow-200 text-yellow-700"
              : "bg-gray-50 border-gray-200 text-gray-500"
          }`}>
            Проверок в этом месяце: {quotaInfo.checks_this_month} / {quotaInfo.quota_limit.toLocaleString()}
            {quotaInfo.checks_this_month >= quotaInfo.quota_limit && (
              <span className="font-medium"> — лимит исчерпан</span>
            )}
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2 rounded-lg">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={
            (inputMode === "file" ? !file : textContent.trim().length < 50) ||
            (quotaInfo !== null &&
              quotaInfo.quota_limit !== null &&
              quotaInfo.checks_this_month >= quotaInfo.quota_limit)
          }
          className="w-full bg-blue-600 text-white py-2.5 rounded-xl font-medium text-sm hover:bg-blue-700 disabled:opacity-40 transition-colors"
        >
          Запустить проверку
        </button>
      </form>
      )}

      {checkMode === "group" && (
        <div className="space-y-5">
          <p className="text-sm text-gray-500">
            Добавьте студентов, укажите имя и ID, прикрепите файл каждому — проверки запустятся разом.
          </p>

          {/* Общая группа / класс */}
          <div className="bg-white border rounded-xl p-4">
            <label className="block text-xs font-medium text-gray-500 mb-1">
              Группа / класс (для всех)
            </label>
            <input
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={group}
              onChange={(e) => setGroup(e.target.value)}
              placeholder="Группа А"
            />
          </div>

          {/* Список студентов */}
          <div className="bg-white border rounded-xl divide-y">
            {rows.map((r, idx) => (
              <div key={r.key} className="p-3 flex items-center gap-2 flex-wrap">
                <span className="text-xs text-gray-400 w-5 shrink-0">{idx + 1}</span>
                <input
                  className="flex-1 min-w-[140px] border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={r.name}
                  onChange={(e) => updateRow(r.key, { name: e.target.value })}
                  placeholder="ФИО студента"
                />
                <input
                  className="w-32 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={r.studentId}
                  onChange={(e) => updateRow(r.key, { studentId: e.target.value })}
                  placeholder="ID студента"
                />
                <label
                  className={`text-xs px-3 py-2 rounded-lg border cursor-pointer whitespace-nowrap ${
                    r.file ? "border-green-400 bg-green-50 text-green-700" : "border-gray-200 text-gray-500 hover:bg-gray-50"
                  }`}
                >
                  {r.file ? `📄 ${r.file.name.slice(0, 22)}` : "Прикрепить файл"}
                  <input
                    type="file"
                    accept=".docx,.pdf"
                    className="hidden"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f && !f.name.match(/\.(docx|pdf)$/i)) {
                        setError("Только .docx и .pdf файлы");
                        return;
                      }
                      if (f) {
                        updateRow(r.key, { file: f, name: r.name || f.name.replace(/\.(docx|pdf)$/i, "") });
                        setError("");
                      }
                      e.target.value = "";
                    }}
                  />
                </label>
                <button
                  type="button"
                  onClick={() => removeRow(r.key)}
                  className="text-gray-300 hover:text-red-500 px-1 text-lg shrink-0"
                  title="Удалить строку"
                >
                  ×
                </button>
              </div>
            ))}
            <div className="p-3">
              <button
                type="button"
                onClick={addRow}
                className="text-sm text-blue-600 hover:text-blue-800 font-medium"
              >
                + Добавить студента
              </button>
            </div>
          </div>

          {/* Исключения (общие) */}
          <div className="bg-white border rounded-xl p-4 space-y-2.5">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">
              Исключения (для всех)
            </p>
            <label className="flex items-center gap-2.5 cursor-pointer">
              <input type="checkbox" checked={excludeQuotes} onChange={(e) => setExcludeQuotes(e.target.checked)} className="accent-blue-600" />
              <span className="text-sm text-gray-700">Исключить цитаты в кавычках «» и ""</span>
            </label>
            <label className="flex items-center gap-2.5 cursor-pointer">
              <input type="checkbox" checked={excludeBiblio} onChange={(e) => setExcludeBiblio(e.target.checked)} className="accent-blue-600" />
              <span className="text-sm text-gray-700">Исключить список литературы</span>
            </label>
            <label className="flex items-center gap-2.5 cursor-pointer">
              <input type="checkbox" checked={saveToRepo} onChange={(e) => setSaveToRepo(e.target.checked)} className="accent-blue-600" />
              <span className="text-sm text-gray-700">Сохранить работы в репозиторий школы</span>
            </label>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2 rounded-lg">
              {error}
            </div>
          )}

          {/* Результаты пакета */}
          {batchResults.length > 0 && (
            <div className="bg-white border rounded-xl divide-y">
              {batchResults.map((b) => (
                <div key={b.key} className="p-3 flex items-center justify-between gap-2 text-sm">
                  <span className="truncate">{b.name}</span>
                  {b.status === "pending" && <span className="text-xs text-gray-400">в очереди…</span>}
                  {b.status === "running" && <span className="text-xs text-blue-500">отправка…</span>}
                  {b.status === "error" && <span className="text-xs text-red-500">{b.error}</span>}
                  {b.status === "done" && b.checkId && (
                    <a href={`/checks/${b.checkId}`} className="text-xs text-blue-600 hover:text-blue-800 font-medium shrink-0">
                      Открыть отчёт →
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}

          <button
            type="button"
            onClick={runBatch}
            disabled={batchRunning || rows.filter((r) => r.file && r.name.trim()).length === 0}
            className="w-full bg-blue-600 text-white py-2.5 rounded-xl font-medium text-sm hover:bg-blue-700 disabled:opacity-40 transition-colors"
          >
            {batchRunning
              ? "Запуск проверок…"
              : `Запустить проверки (${rows.filter((r) => r.file && r.name.trim()).length})`}
          </button>
        </div>
      )}
    </div>
  );
}
