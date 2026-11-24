"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, ApiError } from "@/lib/api";
import { getUser } from "@/lib/auth";

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
  done: "bg-green-100 text-green-700",
  processing: "bg-blue-100 text-blue-700",
  pending: "bg-gray-100 text-gray-500",
  failed: "bg-red-100 text-red-600",
};

function simColor(pct: number) {
  if (pct >= 50) return "text-red-600 font-medium";
  if (pct >= 20) return "text-yellow-600";
  return "text-green-600";
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

  const quotaPct = myStats && myStats.quota_limit
    ? Math.min(100, (myStats.checks_this_month / myStats.quota_limit) * 100)
    : 0;

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

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">История проверок</h1>
        <div className="flex gap-2">
          <button
            onClick={downloadCSV}
            className="border px-4 py-2 rounded-lg text-sm text-gray-600 hover:bg-gray-50 transition-colors"
          >
            Экспорт CSV
          </button>
          <button
            onClick={() => router.push("/checks/new")}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 transition-colors"
          >
            + Новая проверка
          </button>
        </div>
      </div>

      {myStats && (
        <div className="bg-white border rounded-xl p-4 mb-5 flex items-center gap-6">
          <div className="flex-1">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs text-gray-500">Проверок в этом месяце</span>
              <span className="text-xs font-medium text-gray-700">
                {myStats.checks_this_month}
                {myStats.quota_limit != null && (
                  <span className="text-gray-400"> / {myStats.quota_limit.toLocaleString()}</span>
                )}
              </span>
            </div>
            {myStats.quota_limit != null && (
              <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    quotaPct >= 90 ? "bg-red-400" : quotaPct >= 70 ? "bg-yellow-400" : "bg-blue-500"
                  }`}
                  style={{ width: `${quotaPct}%` }}
                />
              </div>
            )}
          </div>
          {myStats.quota_limit != null && (
            <p className="text-xs text-gray-400 shrink-0">
              осталось {(myStats.quota_limit - myStats.checks_this_month).toLocaleString()}
            </p>
          )}
          {myStats.quota_limit == null && (
            <p className="text-xs text-gray-400 shrink-0">без лимита</p>
          )}
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 mb-5">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Поиск по названию..."
          className="border rounded-lg px-3 py-1.5 text-sm max-w-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="border rounded-lg px-3 py-1.5 text-sm text-gray-700"
        >
          <option value="">Все статусы</option>
          <option value="done">Готово</option>
          <option value="processing">Обработка</option>
          <option value="pending">В очереди</option>
          <option value="failed">Ошибка</option>
        </select>
      </div>

      {loading ? (
        <p className="text-gray-400 text-sm">Загрузка...</p>
      ) : (
        <div className="bg-white border rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b bg-gray-50">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Работа</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Студент</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Группа</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Дата</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Совпадения</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">ИИ</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Flagged</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Статус</th>
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
                      <td className="px-4 py-3 max-w-[220px]">
                        <p className="font-medium truncate text-gray-900">
                          {c.work_title || c.filename}
                        </p>
                        {c.word_count != null && (
                          <p className="text-xs text-gray-400 mt-0.5">{c.word_count} слов</p>
                        )}
                      </td>
                      <td className="px-4 py-3 text-gray-700 text-xs">
                        {c.student_name || <span className="text-gray-300">—</span>}
                      </td>
                      <td className="px-4 py-3 text-gray-700 text-xs">
                        {c.group_name || <span className="text-gray-300">—</span>}
                      </td>
                      <td className="px-4 py-3 text-gray-500 whitespace-nowrap text-xs">
                        {new Date(c.created_at).toLocaleDateString("ru", {
                          day: "2-digit",
                          month: "2-digit",
                          year: "numeric",
                        })}
                      </td>
                      <td className="px-4 py-3">
                        {c.similarity_percent != null ? (
                          <span className={simColor(c.similarity_percent)}>
                            {c.similarity_percent.toFixed(1)}%
                          </span>
                        ) : (
                          <span className="text-gray-300">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {c.ai_percent != null ? (
                          <span className={c.ai_percent >= 50 ? "text-orange-600 font-medium" : "text-gray-500"}>
                            {c.ai_percent.toFixed(0)}%
                          </span>
                        ) : (
                          <span className="text-gray-300">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {flagCount > 0 ? (
                          <span className="text-orange-500 font-medium">⚑ {flagCount}</span>
                        ) : (
                          <span className="text-gray-300">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                            STATUS_COLOR[c.status] ?? "bg-gray-100 text-gray-500"
                          }`}
                        >
                          {STATUS_LABEL[c.status] ?? c.status}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <button
                            onClick={() => c.status === "done" && router.push(`/checks/${c.id}`)}
                            disabled={c.status !== "done"}
                            className="text-blue-600 text-xs hover:underline disabled:text-gray-300 disabled:cursor-default"
                          >
                            Открыть
                          </button>
                          <button
                            onClick={() => handleDelete(c.id)}
                            className="text-xs text-gray-300 hover:text-red-500 transition-colors"
                          >
                            Удалить
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
          {filtered.length > 0 && (
            <div className="px-4 py-3 border-t text-xs text-gray-400">
              Показано {filtered.length} из {checks.length}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
