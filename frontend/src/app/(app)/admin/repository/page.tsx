"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

interface RepoDoc {
  id: string;
  check_id: string;
  work_title: string | null;
  student_name: string | null;
  group_name: string | null;
  word_count: number | null;
  language: string | null;
  similarity_percent: number | null;
  created_at: string;
  teacher_email: string | null;
}

function simColor(pct: number) {
  if (pct >= 50) return "text-red-600 font-medium";
  if (pct >= 20) return "text-yellow-600";
  return "text-green-600";
}

export default function RepositoryPage() {
  const [docs, setDocs] = useState<RepoDoc[]>([]);
  const [loading, setLoading] = useState(true);

  async function fetchDocs() {
    try {
      const data = await apiFetch<RepoDoc[]>("/api/v1/org/repository");
      setDocs(data);
    } catch {}
    finally { setLoading(false); }
  }

  useEffect(() => {
    fetchDocs();
  }, []);

  async function handleDelete(id: string) {
    if (!confirm("Удалить работу из репозитория? Она перестанет использоваться для сравнения."))
      return;
    try {
      await apiFetch(`/api/v1/org/repository/${id}`, { method: "DELETE" });
      setDocs((prev) => prev.filter((d) => d.id !== id));
    } catch {}
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold">Репозиторий работ</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {loading
              ? "Загрузка..."
              : `${docs.length} работ сохранено с согласия студентов · используются как база для сравнения`}
          </p>
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-200 text-blue-800 text-sm px-4 py-3 rounded-xl mb-5">
        Работы сохраняются автоматически при включённой галочке «Сохранить в репозиторий» при загрузке.
        Студент и школа дали согласие. Удалить работу из репозитория можно по запросу.
      </div>

      <div className="bg-white border rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b bg-gray-50">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Работа</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Студент</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Группа</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Учитель</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Слов</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Совпадения</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Сохранено</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {!loading && docs.length === 0 ? (
              <tr>
                <td
                  colSpan={8}
                  className="px-4 py-10 text-center text-gray-400 text-sm"
                >
                  Репозиторий пуст
                </td>
              </tr>
            ) : (
              docs.map((w) => (
                <tr key={w.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900 max-w-[220px] truncate">
                    {w.work_title || "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-700">{w.student_name || "—"}</td>
                  <td className="px-4 py-3 text-gray-500">{w.group_name || "—"}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {w.teacher_email || "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {w.word_count?.toLocaleString() ?? "—"}
                  </td>
                  <td className="px-4 py-3">
                    {w.similarity_percent != null ? (
                      <span className={simColor(w.similarity_percent)}>
                        {w.similarity_percent.toFixed(1)}%
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">
                    {new Date(w.created_at).toLocaleDateString("ru")}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handleDelete(w.id)}
                      className="text-xs text-red-400 hover:text-red-600 hover:underline"
                    >
                      Удалить
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
