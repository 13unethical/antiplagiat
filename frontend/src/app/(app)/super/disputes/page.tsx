"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import { PageHeader, Status, Tabs } from "../../ui";

interface Dispute {
  id: string;
  check_id: string;
  submitted_by: string;
  comment: string;
  status: string;
  verdict: string | null;
  created_at: string;
  resolved_at: string | null;
}

const VERDICT_LABELS: Record<string, string> = {
  human_written: "Написано человеком",
  keep_ai: "ИИ-вердикт подтверждён",
  added_to_dataset: "Добавлен в датасет",
};

export default function DisputesPage() {
  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "pending" | "reviewed">("all");

  useEffect(() => {
    const params = filter === "all" ? "" : `?status=${filter}`;
    apiFetch<Dispute[]>(`/api/v1/admin/disputes${params}`)
      .then(setDisputes)
      .catch(() => setDisputes([]))
      .finally(() => setLoading(false));
  }, [filter]);

  async function resolve(id: string, verdict: string) {
    try {
      const updated = await apiFetch<Dispute>(`/api/v1/admin/disputes/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ verdict }),
      });
      setDisputes((prev) => prev.map((d) => (d.id === id ? updated : d)));
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Ошибка");
    }
  }

  const pending = disputes.filter((d) => d.status === "pending").length;

  return (
    <>
      <PageHeader title="Спорные результаты">
        {pending > 0 && <Status tone="amber">На рассмотрении: {pending}</Status>}
      </PageHeader>
      <Tabs
        value={filter}
        onChange={setFilter}
        options={[["all", "Все"], ["pending", "На рассмотрении"], ["reviewed", "Рассмотренные"]]}
      />

      {loading ? (
        <p className="px-4 md:px-6 py-4 text-gray-500">Загрузка...</p>
      ) : disputes.length === 0 ? (
        <div className="table-empty">
          {filter === "pending" ? "Нет споров на рассмотрении" : "Споров нет"}
        </div>
      ) : (
        <div className="divide-y">
          {disputes.map((d) => (
            <div key={d.id} className="px-4 md:px-6 py-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="font-mono text-xs text-gray-500">
                    Проверка {d.check_id.slice(0, 8).toUpperCase()}
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {new Date(d.created_at).toLocaleString("ru", {
                      day: "2-digit", month: "2-digit", year: "numeric",
                      hour: "2-digit", minute: "2-digit",
                    })}
                  </p>
                </div>
                <Status tone={d.status === "pending" ? "amber" : "gray"}>
                  {d.status === "pending" ? "На рассмотрении" : d.verdict ? VERDICT_LABELS[d.verdict] ?? d.verdict : "Рассмотрен"}
                </Status>
              </div>

              <div className="mt-3 max-w-2xl text-gray-900">
                «{d.comment}»
              </div>

              {d.status === "pending" && (
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    onClick={() => resolve(d.id, "human_written")}
                    className="btn btn-secondary"
                  >
                    Написано человеком
                  </button>
                  <button
                    onClick={() => resolve(d.id, "keep_ai")}
                    className="btn btn-secondary"
                  >
                    Оставить ИИ-вердикт
                  </button>
                  <button
                    onClick={() => resolve(d.id, "added_to_dataset")}
                    className="btn btn-secondary"
                  >
                    Добавить в датасет
                  </button>
                </div>
              )}
              {d.status === "reviewed" && d.resolved_at && (
                <p className="mt-2 text-xs text-gray-500">
                  Решено: {new Date(d.resolved_at).toLocaleDateString("ru")}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </>
  );
}
