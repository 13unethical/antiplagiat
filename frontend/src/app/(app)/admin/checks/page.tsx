"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

interface OrgCheck {
  id: string;
  filename: string;
  work_title: string | null;
  student_name: string | null;
  group_name: string | null;
  status: "pending" | "processing" | "done" | "failed";
  word_count: number | null;
  similarity_percent: number | null;
  created_at: string;
  teacher_email: string | null;
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

export default function AdminChecksPage() {
  const router = useRouter();
  const [checks, setChecks] = useState<OrgCheck[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  useEffect(() => {
    apiFetch<OrgCheck[]>("/api/v1/org/checks")
      .then(setChecks)
      .catch(() => {})
      .finally(() => setLoading(false));

    const interval = setInterval(async () => {
      try {
        const data = await apiFetch<OrgCheck[]>("/api/v1/org/checks");
        setChecks(data);
      } catch {}
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const filtered = checks.filter((c) => {
    const q = search.toLowerCase();
    const matchSearch =
      !search ||
      c.filename.toLowerCase().includes(q) ||
      (c.work_title ?? "").toLowerCase().includes(q) ||
      (c.student_name ?? "").toLowerCase().includes(q) ||
      (c.teacher_email ?? "").toLowerCase().includes(q);
    const matchStatus = !statusFilter || c.status === statusFilter;
    return matchSearch && matchStatus;
  });

  return (
    <div className="p-8">
      <h1 className="text-xl font-semibold mb-6">Все проверки школы</h1>

      <div className="flex gap-3 mb-5">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Поиск по работе, студенту, учителю..."
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
                <th className="text-left px-4 py-3 font-medium text-gray-500">Учитель</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Дата</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Совпадения</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Статус</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-gray-400 text-sm">
                    {search || statusFilter ? "Ничего не найдено" : "Проверок в организации нет."}
                  </td>
                </tr>
              ) : (
                filtered.map((c) => (
                  <tr key={c.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 max-w-[200px]">
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
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {c.teacher_email || <span className="text-gray-300">—</span>}
                    </td>
                    <td className="px-4 py-3 text-gray-500 whitespace-nowrap text-xs">
                      {new Date(c.created_at).toLocaleDateString("ru", {
                        day: "2-digit", month: "2-digit", year: "numeric",
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
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLOR[c.status] ?? "bg-gray-100 text-gray-500"}`}>
                        {STATUS_LABEL[c.status] ?? c.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => c.status === "done" && router.push(`/checks/${c.id}`)}
                        disabled={c.status !== "done"}
                        className="text-blue-600 text-xs hover:underline disabled:text-gray-300 disabled:cursor-default"
                      >
                        Открыть
                      </button>
                    </td>
                  </tr>
                ))
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
