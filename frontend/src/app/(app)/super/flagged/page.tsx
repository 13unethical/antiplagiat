"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

interface FlaggedItem {
  id: string;
  work_title: string;
  student_name: string | null;
  org_name: string | null;
  teacher_email: string | null;
  flags: string[];
  severity: string;
  created_at: string;
}

interface Stats {
  flagged_this_month: number;
  high_severity_this_month: number;
  orgs_with_flagged: number;
}

const FLAG_LABELS: Record<string, string> = {
  homoglyph: "Подмена букв",
  invisible_char: "Невидимые символы",
  hidden_text: "Скрытый текст",
  spaced_text: "Разрядка",
  quote_abuse: "Злоупотребление кавычками",
  image_text: "Текст картинкой",
};

const SEVERITY_STYLES: Record<string, string> = {
  high: "bg-red-100 text-red-700",
  medium: "bg-yellow-100 text-yellow-700",
  low: "bg-gray-100 text-gray-500",
};

const SEVERITY_LABELS: Record<string, string> = {
  high: "Высокая",
  medium: "Средняя",
  low: "Низкая",
};

export default function FlaggedPage() {
  const [items, setItems] = useState<FlaggedItem[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiFetch<FlaggedItem[]>("/api/v1/admin/flagged?limit=200"),
      apiFetch<Stats>("/api/v1/admin/flagged/stats"),
    ])
      .then(([data, s]) => {
        setItems(data);
        setStats(s);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold">Flagged: попытки обхода</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Все проверки с обнаруженными попытками обхода по всем школам
          </p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-white border rounded-xl p-4">
          <p className="text-xs text-gray-500">Всего flagged за месяц</p>
          <p className="text-2xl font-bold mt-1 text-orange-500">
            {loading ? "—" : (stats?.flagged_this_month ?? 0)}
          </p>
        </div>
        <div className="bg-white border rounded-xl p-4">
          <p className="text-xs text-gray-500">Критичных (high)</p>
          <p className="text-2xl font-bold mt-1 text-red-600">
            {loading ? "—" : (stats?.high_severity_this_month ?? 0)}
          </p>
        </div>
        <div className="bg-white border rounded-xl p-4">
          <p className="text-xs text-gray-500">Школ с нарушениями</p>
          <p className="text-2xl font-bold mt-1">
            {loading ? "—" : (stats?.orgs_with_flagged ?? 0)}
          </p>
        </div>
      </div>

      <div className="bg-white border rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b bg-gray-50">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Работа</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Студент</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Школа</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Флаги</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Серьёзность</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Дата</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400 text-sm">
                  Загрузка...
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400 text-sm">
                  Нет проверок с флагами
                </td>
              </tr>
            ) : (
              items.map((item) => (
                <tr key={item.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900 max-w-xs truncate">
                    {item.work_title}
                  </td>
                  <td className="px-4 py-3 text-gray-700">
                    {item.student_name ?? <span className="text-gray-300">—</span>}
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {item.org_name ?? <span className="text-gray-300">—</span>}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {item.flags.map((f) => (
                        <span
                          key={f}
                          className="text-xs bg-orange-100 text-orange-700 px-1.5 py-0.5 rounded"
                        >
                          {FLAG_LABELS[f] ?? f}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        SEVERITY_STYLES[item.severity] ?? "bg-gray-100 text-gray-500"
                      }`}
                    >
                      {SEVERITY_LABELS[item.severity] ?? item.severity}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs">
                    {new Date(item.created_at).toLocaleDateString("ru")}
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      href={`/checks/${item.id}`}
                      className="text-xs text-blue-600 hover:underline"
                    >
                      Открыть
                    </Link>
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
