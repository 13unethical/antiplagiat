"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { PageHeader, Similarity } from "../../ui";

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
    <>
      <PageHeader title="Репозиторий работ" />
      <p className="px-4 md:px-6 py-3 border-b text-gray-600">
        {!loading && `Сохранено работ: ${docs.length}. `}
        Сюда попадают работы, отмеченные «Сохранить в репозиторий», с согласия студента и школы. По запросу работу можно удалить.
      </p>

      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th>Работа</th>
              <th>Студент</th>
              <th>Группа</th>
              <th>Учитель</th>
              <th>Слов</th>
              <th>Совпадения</th>
              <th>Сохранено</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {docs.length === 0 ? (
              <tr>
                <td
                  colSpan={8}
                  className="table-empty"
                >
                  {loading ? "Загрузка..." : "Репозиторий пуст"}
                </td>
              </tr>
            ) : (
              docs.map((w) => (
                <tr key={w.id}>
                  <td className="font-medium text-gray-900 max-w-[220px] truncate">
                    {w.work_title || "—"}
                  </td>
                  <td className="text-gray-700">{w.student_name || "—"}</td>
                  <td className="text-gray-500">{w.group_name || "—"}</td>
                  <td className="text-gray-500 text-xs">
                    {w.teacher_email || "—"}
                  </td>
                  <td className="text-gray-500">
                    {w.word_count?.toLocaleString("ru") ?? "—"}
                  </td>
                  <td>
                    <Similarity value={w.similarity_percent} />
                  </td>
                  <td className="text-gray-500 text-xs whitespace-nowrap">
                    {new Date(w.created_at).toLocaleDateString("ru")}
                  </td>
                  <td>
                    <button
                      onClick={() => handleDelete(w.id)}
                      className="link-danger"
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
    </>
  );
}
