"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";

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

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-700",
  reviewed: "bg-gray-100 text-gray-600",
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
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold">Спорные результаты</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Учителя оспаривают ИИ-оценку — вынесите вердикт и добавьте пример в датасет
          </p>
        </div>
        {pending > 0 && (
          <span className="bg-yellow-100 text-yellow-700 text-xs font-medium px-2.5 py-1 rounded-full">
            {pending} на рассмотрении
          </span>
        )}
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2 mb-5">
        {(["all", "pending", "reviewed"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
              filter === f
                ? "bg-gray-900 text-white border-gray-900"
                : "text-gray-600 border-gray-200 hover:bg-gray-50"
            }`}
          >
            {f === "all" ? "Все" : f === "pending" ? "На рассмотрении" : "Рассмотренные"}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-sm text-gray-400">Загрузка...</p>
      ) : disputes.length === 0 ? (
        <div className="bg-white border rounded-xl p-10 text-center text-gray-400 text-sm">
          {filter === "pending" ? "Нет споров на рассмотрении" : "Споров нет"}
        </div>
      ) : (
        <div className="space-y-4">
          {disputes.map((d) => (
            <div key={d.id} className="bg-white border rounded-xl p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="font-mono text-xs text-gray-400">
                    Проверка {d.check_id.slice(0, 8).toUpperCase()}
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {new Date(d.created_at).toLocaleString("ru", {
                      day: "2-digit", month: "2-digit", year: "numeric",
                      hour: "2-digit", minute: "2-digit",
                    })}
                  </p>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_STYLES[d.status] ?? "bg-gray-100 text-gray-600"}`}>
                  {d.status === "pending" ? "На рассмотрении" : d.verdict ? VERDICT_LABELS[d.verdict] ?? d.verdict : "Рассмотрен"}
                </span>
              </div>

              <div className="mt-3 bg-gray-50 rounded-lg px-3 py-2 text-sm text-gray-700 italic">
                «{d.comment}»
              </div>

              {d.status === "pending" && (
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    onClick={() => resolve(d.id, "human_written")}
                    className="text-xs bg-green-600 text-white px-3 py-1.5 rounded-lg hover:bg-green-700"
                  >
                    Написано человеком
                  </button>
                  <button
                    onClick={() => resolve(d.id, "keep_ai")}
                    className="text-xs bg-red-600 text-white px-3 py-1.5 rounded-lg hover:bg-red-700"
                  >
                    Оставить ИИ-вердикт
                  </button>
                  <button
                    onClick={() => resolve(d.id, "added_to_dataset")}
                    className="text-xs border px-3 py-1.5 rounded-lg text-gray-600 hover:bg-gray-50"
                  >
                    Добавить в датасет
                  </button>
                </div>
              )}
              {d.status === "reviewed" && d.resolved_at && (
                <p className="mt-2 text-xs text-gray-400">
                  Решено: {new Date(d.resolved_at).toLocaleDateString("ru")}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
