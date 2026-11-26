"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { PageHeader, Stats, Status } from "../../ui";

interface ServiceStatus {
  name: string;
  status: "ok" | "warn" | "error";
  latency?: string;
  detail?: string;
}

const STATUS_TONE = { ok: "green", warn: "amber", error: "red" } as const;

const STATUS_LABEL: Record<string, string> = {
  ok: "Работает",
  warn: "Внимание",
  error: "Ошибка",
};

export default function StatusPage() {
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);

  async function fetchStatus() {
    try {
      const data = await apiFetch<{ services: ServiceStatus[]; checked_at: string }>("/api/v1/admin/status");
      setServices(data.services);
      setLastChecked(new Date(data.checked_at));
      setFailed(false);
    } catch {
      setFailed(true);
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
    <>
      <PageHeader title="Состояние системы">
        {lastChecked && (
          <span className="hidden sm:block text-xs text-gray-500">Обновлено в {lastChecked.toLocaleTimeString("ru")}</span>
        )}
        <button onClick={fetchStatus} className="btn btn-secondary">Обновить</button>
      </PageHeader>
      <Stats
        items={[
          { label: "Работает", value: ok },
          { label: "Требуют внимания", value: warn },
          { label: "С ошибками", value: error },
        ]}
      />
      {failed && <p role="alert" className="px-4 md:px-6 py-3 border-b text-red-700">Не удалось получить состояние сервисов</p>}
      {loading && <p className="px-4 md:px-6 py-4 text-gray-500">Загрузка...</p>}
      <ul className="divide-y divide-gray-100">
        {services.map((s) => (
          <li key={s.name} className="px-4 md:px-6 py-3 flex items-center gap-4">
            <div className="flex-1 min-w-0">
              <p className="font-medium text-gray-900">{s.name}</p>
              {s.detail && <p className="text-xs text-gray-500">{s.detail}</p>}
            </div>
            {s.latency && <span className="text-xs text-gray-500 tabular">{s.latency}</span>}
            <Status tone={STATUS_TONE[s.status]}>{STATUS_LABEL[s.status]}</Status>
          </li>
        ))}
      </ul>
    </>
  );
}
