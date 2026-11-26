"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, ApiError } from "@/lib/api";
import { getUser } from "@/lib/auth";
import { Icon, PageHeader, Ring } from "../ui";

interface Check {
  id: string;
  filename: string;
  file_size: number;
  status: "pending" | "processing" | "done" | "failed";
  work_title: string | null;
  student_name: string | null;
  group_name: string | null;
  word_count: number | null;
  language: string | null;
  similarity_percent: number | null;
  ai_percent: number | null;
  flag_count: number;
  created_at: string;
}

const STATUS_LABEL: Record<string, string> = {
  done: "Готово",
  processing: "Обработка...",
  pending: "В очереди",
  failed: "Ошибка",
};

const STATUS_COLOR: Record<string, string> = {
  done: "bg-green-600",
  processing: "bg-blue-600",
  pending: "bg-gray-300",
  failed: "bg-red-600",
};

function simColor(pct: number) {
  if (pct >= 50) return "text-red-600 font-medium";
  if (pct >= 20) return "text-yellow-700";
  return "text-green-700";
}

interface MyStats {
  checks_this_month: number;
  quota_limit: number | null;
  personal_quota: number | null;
}

export default function ChecksHistoryPage() {
  const router = useRouter();
  const [checks, setChecks] = useState<Check[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [myStats, setMyStats] = useState<MyStats | null>(null);
  const user = getUser();

  useEffect(() => {
    if (user?.role === "teacher") {
      apiFetch<MyStats>("/api/v1/auth/me/stats")
        .then(setMyStats)
        .catch(() => {});
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    apiFetch<Check[]>("/api/v1/checks")
      .then(setChecks)
      .catch(() => {})
      .finally(() => setLoading(false));

    // poll while any check is processing
    const interval = setInterval(async () => {
      try {
        const data = await apiFetch<Check[]>("/api/v1/checks");
        setChecks(data);
      } catch {}
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  const filtered = checks.filter((c) => {
    const q = search.toLowerCase();
    const matchSearch =
      !search ||
      c.filename.toLowerCase().includes(q) ||
      (c.work_title ?? "").toLowerCase().includes(q) ||
      (c.student_name ?? "").toLowerCase().includes(q);
    const matchStatus = !statusFilter || c.status === statusFilter;
    return matchSearch && matchStatus;
  });

  const done = checks.filter((c) => c.status === "done");
  const attention = done.filter((c) => c.flag_count > 0 || (c.similarity_percent ?? 0) >= 20);
  const withSim = done.filter((c) => c.similarity_percent != null);
  const stats = [
    ...(myStats
      ? [
          {
            label: "Проверок в этом месяце",
            value: myStats.checks_this_month.toLocaleString("ru"),
            note:
              myStats.quota_limit != null
                ? `осталось ${Math.max(0, myStats.quota_limit - myStats.checks_this_month).toLocaleString("ru")}`
                : "без лимита",
          },
        ]
      : []),
    { label: "Требуют внимания", value: String(attention.length), note: "совпадения от 20% или попытки обхода" },
    {
      label: "Средние совпадения",
      value: withSim.length
        ? `${Math.round(withSim.reduce((a, c) => a + (c.similarity_percent ?? 0), 0) / withSim.length)}%`
        : "0%",
      note: "по готовым работам",
    },
    { label: "Всего работ", value: String(checks.length), note: `готово ${done.length}` },
  ];

  async function handleDelete(id: string) {
    if (!confirm("Удалить проверку? Это действие необратимо.")) return;
    try {
      await apiFetch(`/api/v1/checks/${id}`, { method: "DELETE" });
      setChecks((prev) => prev.filter((c) => c.id !== id));
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Ошибка удаления");
    }
  }

  async function downloadCSV() {
    const token = localStorage.getItem("access_token");
    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    try {
      const res = await fetch(`${base}/api/v1/checks/export`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "checks.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch {}
  }

  async function downloadReport(
    checkId: string,
    kind: "plagiarism" | "ai" | "flagged",
  ) {
    if (process.env.NEXT_PUBLIC_DEMO === "1") {
      alert("Демо-режим: скачивание отчётов доступно после подключения бэкенда.");
      return;
    }
    const token = localStorage.getItem("access_token");
    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    try {
      const res = await fetch(
        `${apiBase}/api/v1/checks/${checkId}/report?format=pdf&kind=${kind}`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? "Ошибка генерации PDF");
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const kindLabel =
        kind === "ai" ? "ИИ" : kind === "flagged" ? "обход" : "совпадения";
      a.href = url;
      a.download = `Антиплагиат-${kindLabel}-${checkId.slice(0, 8).toUpperCase()}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Ошибка");
    }
  }

  return (
    <>
      <PageHeader title="История проверок">
        <button onClick={downloadCSV} className="btn btn-secondary">
          <Icon name="download" className="text-gray-500" />
          Экспорт CSV
        </button>
        <button onClick={() => router.push("/checks/new")} className="btn btn-primary">
          <Icon name="plus" />
          Новая проверка
        </button>
      </PageHeader>

      <dl className="grid grid-cols-2 lg:grid-cols-4 gap-px bg-gray-200 border-b tabular">
        {stats.map((st) => (
          <div key={st.label} className="bg-white px-4 md:px-6 py-4">
            <dt className="text-xs text-gray-500">{st.label}</dt>
            <dd className="mt-1.5 text-2xl font-semibold tracking-tight">{st.value}</dd>
            <dd className="mt-0.5 text-xs text-gray-500">{st.note}</dd>
          </div>
        ))}
      </dl>

      <div className="flex flex-wrap gap-2 px-4 md:px-6 py-3 border-b">
        <div className="relative flex-1 max-w-xs">
          <Icon name="search" className="absolute left-2.5 top-[7px] text-gray-500" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Работа или студент"
            aria-label="Поиск"
            className="w-full h-8 border rounded-lg pl-8 pr-3 text-sm focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          aria-label="Статус"
          className="h-8 border rounded-lg px-2 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-blue-200"
        >
          <option value="">Все статусы</option>
          <option value="done">Готово</option>
          <option value="processing">Обработка</option>
          <option value="pending">В очереди</option>
          <option value="failed">Ошибка</option>
        </select>
      </div>

      {loading ? (
        <p className="px-6 py-4 text-gray-500 text-sm">Загрузка...</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b">
              <tr>
                <th className="text-left px-3 first:pl-4 md:first:pl-6 h-9 text-xs font-medium text-gray-500 whitespace-nowrap">Работа</th>
                <th className="hidden sm:table-cell text-left px-3 first:pl-4 md:first:pl-6 h-9 text-xs font-medium text-gray-500 whitespace-nowrap">Студент</th>
                <th className="hidden sm:table-cell text-left px-3 first:pl-4 md:first:pl-6 h-9 text-xs font-medium text-gray-500 whitespace-nowrap">Группа</th>
                <th className="hidden sm:table-cell text-left px-3 first:pl-4 md:first:pl-6 h-9 text-xs font-medium text-gray-500 whitespace-nowrap">Дата</th>
                <th className="text-left px-3 first:pl-4 md:first:pl-6 h-9 text-xs font-medium text-gray-500 whitespace-nowrap">Совпадения</th>
                <th className="text-left px-3 first:pl-4 md:first:pl-6 h-9 text-xs font-medium text-gray-500 whitespace-nowrap">ИИ</th>
                <th className="text-left px-3 first:pl-4 md:first:pl-6 h-9 text-xs font-medium text-gray-500 whitespace-nowrap">Обход</th>
                <th className="text-left px-3 first:pl-4 md:first:pl-6 h-9 text-xs font-medium text-gray-500 whitespace-nowrap">Статус</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-10 text-center text-gray-400 text-sm">
                    {search || statusFilter
                      ? "Ничего не найдено"
                      : "Проверок пока нет. Загрузите первый файл."}
                  </td>
                </tr>
              ) : (
                filtered.map((c) => {
                  const flagCount = c.flag_count ?? 0;
                  return (
                    <tr key={c.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-3 first:pl-4 md:first:pl-6 py-2.5 max-w-[150px] sm:max-w-[220px]">
                        <p className="font-medium truncate text-gray-900">
                          {c.work_title || c.filename}
                        </p>
                        {c.student_name && <p className="sm:hidden text-xs text-gray-700 truncate">{c.student_name}</p>}
                        {c.word_count != null && (
                          <p className="text-xs text-gray-400 mt-0.5">{c.word_count} слов</p>
                        )}
                      </td>
                      <td className="hidden sm:table-cell px-3 first:pl-4 md:first:pl-6 py-2.5 text-gray-700 text-xs">
                        {c.student_name || <span className="text-gray-300">—</span>}
                      </td>
                      <td className="hidden sm:table-cell px-3 first:pl-4 md:first:pl-6 py-2.5 text-gray-700 text-xs">
                        {c.group_name || <span className="text-gray-300">—</span>}
                      </td>
                      <td className="hidden sm:table-cell px-3 first:pl-4 md:first:pl-6 py-2.5 text-gray-500 whitespace-nowrap text-xs">
                        {new Date(c.created_at).toLocaleDateString("ru", {
                          day: "2-digit",
                          month: "2-digit",
                          year: "numeric",
                        })}
                      </td>
                      <td className="px-3 first:pl-4 md:first:pl-6 py-2.5">
                        {c.status === "done" && c.similarity_percent != null ? (
                          <div className="flex flex-col items-start gap-0.5">
                            <span className={`inline-flex items-center gap-2 ${simColor(c.similarity_percent)}`}>
                              <Ring value={c.similarity_percent} />
                              {c.similarity_percent.toFixed(1)}%
                            </span>
                            <button
                              type="button"
                              onClick={() => downloadReport(c.id, "plagiarism")}
                              className="p-0.5 rounded text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
                              aria-label="Скачать отчёт совпадений"
                              title="Скачать PDF"
                            >
                              <Icon name="download" className="!w-3.5 !h-3.5" />
                            </button>
                          </div>
                        ) : c.similarity_percent != null ? (
                          <span className={`inline-flex items-center gap-2 ${simColor(c.similarity_percent)}`}>
                            <Ring value={c.similarity_percent} />
                            {c.similarity_percent.toFixed(1)}%
                          </span>
                        ) : (
                          <span className="text-gray-300">—</span>
                        )}
                      </td>
                      <td className="px-3 first:pl-4 md:first:pl-6 py-2.5">
                        {c.status === "done" && c.ai_percent != null ? (
                          <div className="flex flex-col items-start gap-0.5">
                            <span className={c.ai_percent >= 50 ? "text-gray-900" : "text-gray-500"}>
                              {c.ai_percent.toFixed(0)}%
                            </span>
                            <button
                              type="button"
                              onClick={() => downloadReport(c.id, "ai")}
                              className="p-0.5 rounded text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
                              aria-label="Скачать отчёт ИИ"
                              title="Скачать PDF"
                            >
                              <Icon name="download" className="!w-3.5 !h-3.5" />
                            </button>
                          </div>
                        ) : c.ai_percent != null ? (
                          <span className={c.ai_percent >= 50 ? "text-gray-900" : "text-gray-500"}>
                            {c.ai_percent.toFixed(0)}%
                          </span>
                        ) : (
                          <span className="text-gray-300">—</span>
                        )}
                      </td>
                      <td className="px-3 first:pl-4 md:first:pl-6 py-2.5">
                        {c.status === "done" ? (
                          <div className="flex flex-col items-start gap-0.5">
                            {flagCount > 0 ? (
                              <span className="inline-flex items-center gap-1.5 text-orange-700 font-medium">
                                <Icon name="flag" />
                                {flagCount}
                              </span>
                            ) : (
                              <span className="text-gray-300">—</span>
                            )}
                            <button
                              type="button"
                              onClick={() => downloadReport(c.id, "flagged")}
                              className="p-0.5 rounded text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
                              aria-label="Скачать отчёт по обходу"
                              title="Скачать PDF"
                            >
                              <Icon name="download" className="!w-3.5 !h-3.5" />
                            </button>
                          </div>
                        ) : flagCount > 0 ? (
                          <span className="inline-flex items-center gap-1.5 text-orange-700 font-medium">
                            <Icon name="flag" />
                            {flagCount}
                          </span>
                        ) : (
                          <span className="text-gray-300">—</span>
                        )}
                      </td>
                      <td className="px-3 first:pl-4 md:first:pl-6 py-2.5">
                        <span
                          className="inline-flex items-center gap-2 text-xs text-gray-700 whitespace-nowrap"
                        >
                          <span className={`w-2 h-2 rounded-full ${STATUS_COLOR[c.status] ?? "bg-gray-300"}`} />
                          {STATUS_LABEL[c.status] ?? c.status}
                        </span>
                      </td>
                      <td className="px-3 first:pl-4 md:first:pl-6 py-2.5">
                        <div className="flex items-center gap-3">
                          <button
                            onClick={() => c.status === "done" && router.push(`/checks/${c.id}`)}
                            disabled={c.status !== "done"}
                            className="text-blue-700 text-sm font-medium hover:underline disabled:text-gray-300 disabled:cursor-default"
                          >
                            Открыть
                          </button>
                          <button
                            onClick={() => handleDelete(c.id)}
                            className="p-1.5 rounded-md text-gray-400 hover:text-red-700 hover:bg-red-50 transition-colors"
                           aria-label="Удалить" title="Удалить"><Icon name="trash" /></button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
          {filtered.length > 0 && (
            <div className="px-4 md:px-6 py-3 border-t text-xs text-gray-500">
              Показано {filtered.length} из {checks.length}
            </div>
          )}
        </div>
      )}
    </>
  );
}
