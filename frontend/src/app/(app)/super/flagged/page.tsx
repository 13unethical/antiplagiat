"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { PageHeader, Stats, Status, type Tone } from "../../ui";

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

const SEVERITY_LABELS: Record<string, string> = {
  high: "Высокая",
  medium: "Средняя",
  low: "Низкая",
};

const SEVERITY_TONE: Record<string, Tone> = { high: "red", medium: "amber", low: "gray" };

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
    <>
      <PageHeader title="Попытки обхода" />
      <Stats
        items={[
          { label: "Работ с обходом", value: loading ? "—" : stats?.flagged_this_month ?? 0, note: "за этот месяц, все школы" },
          { label: "Критичных", value: loading ? "—" : stats?.high_severity_this_month ?? 0, note: "высокая серьёзность" },
          { label: "Школ с нарушениями", value: loading ? "—" : stats?.orgs_with_flagged ?? 0, note: "за этот месяц" },
        ]}
      />

      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th>Работа</th>
              <th>Студент</th>
              <th>Школа</th>
              <th>Что найдено</th>
              <th>Серьёзность</th>
              <th>Дата</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="table-empty">
                  Загрузка...
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={7} className="table-empty">
                  Попыток обхода не найдено
                </td>
              </tr>
            ) : (
              items.map((item) => (
                <tr key={item.id}>
                  <td className="font-medium text-gray-900 max-w-xs truncate">
                    {item.work_title}
                  </td>
                  <td className="text-gray-700">
                    {item.student_name ?? <span className="text-gray-300">—</span>}
                  </td>
                  <td className="text-gray-500 text-xs">
                    {item.org_name ?? <span className="text-gray-300">—</span>}
                  </td>
                  <td>
                    <span className="text-gray-700">{item.flags.map((f) => FLAG_LABELS[f] ?? f).join(", ").toLowerCase()}</span>
                  </td>
                  <td>
                    <Status tone={SEVERITY_TONE[item.severity]}>{SEVERITY_LABELS[item.severity] ?? item.severity}</Status>
                  </td>
                  <td className="text-gray-500 text-xs">
                    {new Date(item.created_at).toLocaleDateString("ru")}
                  </td>
                  <td>
                    <Link
                      href={`/checks/${item.id}`}
                      className="link"
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
    </>
  );
}
