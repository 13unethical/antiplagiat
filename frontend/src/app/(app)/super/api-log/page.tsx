"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { PageHeader, Stats, Status, type Tone } from "../../ui";

interface ApiLogEntry {
  id: string;
  org_name: string | null;
  key_prefix: string | null;
  method: string;
  path: string;
  status_code: number;
  response_ms: number | null;
  created_at: string;
}

interface ApiLogStats {
  requests_today: number;
  errors_today: number;
  limit_hits_today: number;
  avg_response_ms: number;
}

function statusTone(code: number): Tone {
  if (code < 300) return "green";
  if (code < 400) return "blue";
  if (code < 500) return "amber";
  return "red";
}

export default function ApiLogPage() {
  const [logs, setLogs] = useState<ApiLogEntry[]>([]);
  const [stats, setStats] = useState<ApiLogStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiFetch<ApiLogEntry[]>("/api/v1/admin/api-log?limit=100").catch(() => [] as ApiLogEntry[]),
      apiFetch<ApiLogStats>("/api/v1/admin/api-log/stats").catch(() => null),
    ])
      .then(([logsData, statsData]) => {
        setLogs(logsData);
        setStats(statsData);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <PageHeader title="API и журнал запросов" />
      <Stats
        items={[
          { label: "Запросы", value: stats?.requests_today ?? "—", note: "сегодня, по ключам школ" },
          { label: "Ошибки 4xx и 5xx", value: stats?.errors_today ?? "—", note: "сегодня" },
          { label: "Превышен лимит (429)", value: stats?.limit_hits_today ?? "—", note: "сегодня" },
          { label: "Среднее время ответа", value: stats ? `${stats.avg_response_ms} мс` : "—", note: "сегодня" },
        ]}
      />

      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th>Время</th>
              <th>Школа</th>
              <th>Ключ</th>
              <th>Запрос</th>
              <th>Статус</th>
              <th>Длительность</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} className="table-empty">
                  Загрузка...
                </td>
              </tr>
            ) : logs.length === 0 ? (
              <tr>
                <td colSpan={6} className="table-empty">
                  Нет API-запросов
                </td>
              </tr>
            ) : (
              logs.map((r) => (
                <tr key={r.id}>
                  <td className="text-gray-500 text-xs whitespace-nowrap">
                    {new Date(r.created_at).toLocaleString("ru")}
                  </td>
                  <td className="text-gray-700 text-xs">
                    {r.org_name ?? "—"}
                  </td>
                  <td className="text-gray-500 text-xs font-mono">{r.key_prefix ?? "—"}</td>
                  <td className="text-gray-800 text-xs font-mono">
                    {r.method} {r.path}
                  </td>
                  <td>
                    <Status tone={statusTone(r.status_code)}>{r.status_code}</Status>
                  </td>
                  <td className="text-gray-500 text-xs">
                    {r.response_ms != null ? `${r.response_ms} мс` : "—"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        {logs.length > 0 && (
          <div className="px-4 md:px-6 py-3 text-xs text-gray-500">
            Показано запросов: {logs.length}
          </div>
        )}
      </div>
    </>
  );
}
