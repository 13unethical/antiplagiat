"use client";

import { useEffect, useState } from "react";

interface ServiceStatus {
  name: string;
  status: "ok" | "warn" | "error";
  latency?: string;
  detail?: string;
}

const STATUS_DOT: Record<string, string> = {
  ok: "bg-green-400",
  warn: "bg-yellow-400",
  error: "bg-red-400",
};

const STATUS_LABEL: Record<string, string> = {
  ok: "Работает",
  warn: "Внимание",
  error: "Ошибка",
};

const STATUS_TEXT: Record<string, string> = {
  ok: "text-green-700",
  warn: "text-yellow-700",
  error: "text-red-700",
};

export default function StatusPage() {
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const [loading, setLoading] = useState(true);

  async function fetchStatus() {
    const token = localStorage.getItem("access_token");
    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    try {
      const res = await fetch(`${apiBase}/api/v1/admin/status`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setServices(data.services);
        setLastChecked(new Date(data.checked_at));
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchStatus();
    const t = setInterval(fetchStatus, 30_000);
    return () => clearInterval(t);
  }, []);

  const ok = services.filter((s) => s.status === "ok").length;
  const warn = services.filter((s) => s.status === "warn").length;
  const error = services.filter((s) => s.status === "error").length;

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold">Состояние системы</h1>
          <p className="text-xs text-gray-400 mt-1">
            {lastChecked
              ? `Обновлено: ${lastChecked.toLocaleTimeString("ru")}`
              : "Загрузка..."}
          </p>
        </div>
        <button
          onClick={fetchStatus}
          className="text-xs text-gray-500 border rounded-lg px-3 py-1.5 hover:bg-gray-50 transition-colors"
        >
          Обновить
        </button>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-white border rounded-xl p-4 flex items-center gap-3">
          <div className="w-3 h-3 rounded-full bg-green-400" />
          <div>
            <p className="text-xl font-bold text-green-700">{ok}</p>
            <p className="text-xs text-gray-500">Работает нормально</p>
          </div>
        </div>
        <div className="bg-white border rounded-xl p-4 flex items-center gap-3">
          <div className="w-3 h-3 rounded-full bg-yellow-400" />
          <div>
            <p className="text-xl font-bold text-yellow-700">{warn}</p>
            <p className="text-xs text-gray-500">Требуют внимания</p>
          </div>
        </div>
        <div className="bg-white border rounded-xl p-4 flex items-center gap-3">
          <div className="w-3 h-3 rounded-full bg-red-400" />
          <div>
            <p className="text-xl font-bold text-red-700">{error}</p>
            <p className="text-xs text-gray-500">С ошибками</p>
          </div>
        </div>
      </div>

      {/* Services */}
      {loading ? (
        <p className="text-sm text-gray-400">Загрузка...</p>
      ) : (
        <div className="space-y-2">
          {services.map((s) => (
            <div
              key={s.name}
              className="bg-white border rounded-xl px-5 py-3.5 flex items-center gap-4"
            >
              <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${STATUS_DOT[s.status]}`} />
              <div className="flex-1 min-w-0">
                <p className="font-medium text-sm text-gray-900">{s.name}</p>
                {s.detail && (
                  <p className="text-xs text-gray-400 mt-0.5">{s.detail}</p>
                )}
              </div>
              <div className="flex items-center gap-4 shrink-0">
                {s.latency && (
                  <span className="text-xs text-gray-400">{s.latency}</span>
                )}
                <span className={`text-xs font-medium ${STATUS_TEXT[s.status]}`}>
                  {STATUS_LABEL[s.status]}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
