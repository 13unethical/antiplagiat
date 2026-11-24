"use client";

import { useEffect, useState, useCallback } from "react";
import { apiFetch } from "@/lib/api";

interface AuditEntry {
  id: string;
  user_id: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  details: Record<string, unknown>;
  created_at: string;
}

const ACTION_LABELS: Record<string, string> = {
  create_organization: "Создал организацию",
  update_organization: "Обновил организацию",
  resolve_dispute: "Вынес вердикт по спору",
  activate_model_version: "Активировал версию модели",
  create_model_version: "Добавил версию модели",
};

const ACTION_COLORS: Record<string, string> = {
  create_organization: "bg-blue-100 text-blue-700",
  update_organization: "bg-yellow-100 text-yellow-700",
  resolve_dispute: "bg-green-100 text-green-700",
  activate_model_version: "bg-purple-100 text-purple-700",
  create_model_version: "bg-gray-100 text-gray-700",
};

export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState("");

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = actionFilter ? `?action=${actionFilter}` : "";
      const data = await apiFetch<AuditEntry[]>(`/api/v1/admin/audit-log${params}`);
      setEntries(data);
    } catch {}
    finally { setLoading(false); }
  }, [actionFilter]);

  useEffect(() => { fetchData(); }, [fetchData]);

  return (
    <div className="p-8 max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Аудит действий</h1>
          <p className="text-sm text-gray-500 mt-0.5">Журнал всех действий суперадмина</p>
        </div>
      </div>

      {/* Filter */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setActionFilter("")}
          className={`text-xs px-3 py-1.5 rounded-lg border ${!actionFilter ? "bg-gray-900 text-white border-gray-900" : "text-gray-600 border-gray-200 hover:bg-gray-50"}`}
        >
          Все
        </button>
        {Object.entries(ACTION_LABELS).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setActionFilter(key === actionFilter ? "" : key)}
            className={`text-xs px-3 py-1.5 rounded-lg border ${actionFilter === key ? "bg-gray-900 text-white border-gray-900" : "text-gray-600 border-gray-200 hover:bg-gray-50"}`}
          >
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-sm text-gray-400">Загрузка...</p>
      ) : entries.length === 0 ? (
        <div className="bg-white border rounded-xl p-10 text-center text-gray-400 text-sm">
          Нет записей в журнале
        </div>
      ) : (
        <div className="bg-white border rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b bg-gray-50">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Время</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Действие</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Ресурс</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Детали</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {entries.map((e) => (
                <tr key={e.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                    {new Date(e.created_at).toLocaleString("ru", {
                      day: "2-digit", month: "2-digit", year: "numeric",
                      hour: "2-digit", minute: "2-digit",
                    })}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${ACTION_COLORS[e.action] ?? "bg-gray-100 text-gray-600"}`}>
                      {ACTION_LABELS[e.action] ?? e.action}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    <span className="font-mono">{e.resource_type}</span>
                    {e.resource_id && (
                      <span className="text-gray-400 ml-1">
                        {e.resource_id.slice(0, 8).toUpperCase()}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500 max-w-xs truncate">
                    {Object.entries(e.details)
                      .map(([k, v]) => `${k}: ${v}`)
                      .join(" · ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
