"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

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

function statusColor(code: number) {
  if (code < 300) return "text-green-600";
  if (code < 400) return "text-blue-600";
  if (code < 500) return "text-yellow-600";
  return "text-red-600";
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
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold">API и журнал запросов</h1>
          <p className="text-sm text-gray-500 mt-0.5">Все запросы через API-ключи школ</p>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-white border rounded-xl p-4">
          <p className="text-xs text-gray-500">Запросов сегодня</p>
          <p className="text-2xl font-bold mt-1">{stats?.requests_today ?? "—"}</p>
        </div>
        <div className="bg-white border rounded-xl p-4">
          <p className="text-xs text-gray-500">Ошибок 4xx/5xx</p>
          <p className="text-2xl font-bold mt-1 text-yellow-600">{stats?.errors_today ?? "—"}</p>
        </div>
        <div className="bg-white border rounded-xl p-4">
          <p className="text-xs text-gray-500">Лимит (429)</p>
          <p className="text-2xl font-bold mt-1 text-red-500">{stats?.limit_hits_today ?? "—"}</p>
        </div>
        <div className="bg-white border rounded-xl p-4">
          <p className="text-xs text-gray-500">Среднее время ответа</p>
          <p className="text-2xl font-bold mt-1">
            {stats ? `${stats.avg_response_ms}мс` : "—"}
          </p>
        </div>
      </div>

      <div className="bg-white border rounded-xl overflow-hidden">
        <table className="w-full text-sm font-mono">
          <thead className="border-b bg-gray-50 font-sans">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Время</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Школа</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Ключ</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Запрос</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Статус</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Время</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400 text-sm font-sans">
                  Загрузка...
                </td>
              </tr>
            ) : logs.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400 text-sm font-sans">
                  Нет API-запросов
                </td>
              </tr>
            ) : (
              logs.map((r) => (
                <tr key={r.id} className="hover:bg-gray-50">
                  <td className="px-4 py-2.5 text-gray-400 text-xs whitespace-nowrap">
                    {new Date(r.created_at).toLocaleString("ru")}
                  </td>
                  <td className="px-4 py-2.5 text-gray-700 font-sans text-xs">
                    {r.org_name ?? "—"}
                  </td>
                  <td className="px-4 py-2.5 text-gray-400 text-xs">{r.key_prefix ?? "—"}</td>
                  <td className="px-4 py-2.5 text-gray-800 text-xs">
                    {r.method} {r.path}
                  </td>
                  <td className={`px-4 py-2.5 font-bold text-xs ${statusColor(r.status_code)}`}>
                    {r.status_code}
                  </td>
                  <td className="px-4 py-2.5 text-gray-500 text-xs">
                    {r.response_ms != null ? `${r.response_ms}мс` : "—"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        {logs.length > 0 && (
          <div className="px-4 py-3 border-t text-xs text-gray-400">
            Последние {logs.length} запросов
          </div>
        )}
      </div>
    </div>
  );
}
