"use client";

import { useEffect, useState, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import { PageHeader } from "../../ui";

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
    <>
      <PageHeader title="Аудит действий" />
      <div className="px-4 md:px-6 py-3 border-b">
        <select
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          aria-label="Действие"
          className="h-8 border rounded-lg px-2 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-blue-200"
        >
          <option value="">Все действия</option>
          {Object.entries(ACTION_LABELS).map(([key, label]) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>
      </div>

      {loading ? (
        <p className="px-4 md:px-6 py-4 text-gray-500">Загрузка...</p>
      ) : entries.length === 0 ? (
        <div className="table-empty">
          Нет записей в журнале
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Время</th>
                <th>Действие</th>
                <th>Ресурс</th>
                <th>Детали</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.id}>
                  <td className="text-xs text-gray-500 whitespace-nowrap">
                    {new Date(e.created_at).toLocaleString("ru", {
                      day: "2-digit", month: "2-digit", year: "numeric",
                      hour: "2-digit", minute: "2-digit",
                    })}
                  </td>
                  <td>
                    <span className="font-medium text-gray-900 whitespace-nowrap">{ACTION_LABELS[e.action] ?? e.action}</span>
                  </td>
                  <td className="text-xs text-gray-500">
                    <span className="font-mono">{e.resource_type}</span>
                    {e.resource_id && (
                      <span className="text-gray-500 ml-1">
                        {e.resource_id.slice(0, 8).toUpperCase()}
                      </span>
                    )}
                  </td>
                  <td className="text-xs text-gray-500 max-w-xs truncate">
                    {Object.entries(e.details)
                      .map(([k, v]) => `${k}: ${v}`)
                      .join(", ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
