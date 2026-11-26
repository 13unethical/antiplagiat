"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { Icon, PageHeader, Similarity, Status, type Tone } from "../../ui";

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

const STATUS_TONE: Record<string, Tone> = { done: "green", processing: "blue", pending: "gray", failed: "red" };

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
    <>
      <PageHeader title="Все проверки школы" />

      <div className="flex flex-wrap gap-2 px-4 md:px-6 py-3 border-b">
        <div className="relative flex-1 max-w-xs">
          <Icon name="search" className="absolute left-2.5 top-[7px] text-gray-500" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Работа, студент, учитель"
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
        <p className="px-4 md:px-6 py-4 text-gray-500">Загрузка...</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Работа</th>
                <th>Студент</th>
                <th>Группа</th>
                <th>Учитель</th>
                <th>Дата</th>
                <th>Совпадения</th>
                <th>Статус</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={8} className="table-empty">
                    {search || statusFilter ? "Ничего не найдено" : "Проверок в организации нет."}
                  </td>
                </tr>
              ) : (
                filtered.map((c) => (
                  <tr key={c.id}>
                    <td className="max-w-[200px]">
                      <p className="font-medium truncate text-gray-900">
                        {c.work_title || c.filename}
                      </p>
                      {c.word_count != null && (
                        <p className="text-xs text-gray-500 mt-0.5">{c.word_count} слов</p>
                      )}
                    </td>
                    <td className="text-gray-700 text-xs">
                      {c.student_name || <span className="text-gray-300">—</span>}
                    </td>
                    <td className="text-gray-700 text-xs">
                      {c.group_name || <span className="text-gray-300">—</span>}
                    </td>
                    <td className="text-gray-500 text-xs">
                      {c.teacher_email || <span className="text-gray-300">—</span>}
                    </td>
                    <td className="text-gray-500 whitespace-nowrap text-xs">
                      {new Date(c.created_at).toLocaleDateString("ru", {
                        day: "2-digit", month: "2-digit", year: "numeric",
                      })}
                    </td>
                    <td>
                      <Similarity value={c.similarity_percent} />
                    </td>
                    <td>
                      <Status tone={STATUS_TONE[c.status]}>{STATUS_LABEL[c.status] ?? c.status}</Status>
                    </td>
                    <td>
                      <button
                        onClick={() => c.status === "done" && router.push(`/checks/${c.id}`)}
                        disabled={c.status !== "done"}
                        className="link"
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
            <div className="px-4 md:px-6 py-3 text-xs text-gray-500">
              Показано {filtered.length} из {checks.length}
            </div>
          )}
        </div>
      )}
    </>
  );
}
