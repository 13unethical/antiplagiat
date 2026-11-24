"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

interface OrgStats {
  active: number;
  pending_invitations: number;
  used: number;
  seats_limit: number;
  available: number;
  monthly_quota: number;
  checks_this_month: number;
  flagged_this_month: number;
}

interface Teacher {
  id: string;
  email: string;
  full_name: string;
  status: string;
}

const STATUS_LABEL: Record<string, string> = {
  active: "Активен",
  inactive: "Отключён",
  pending: "Приглашён",
};

const STATUS_COLOR: Record<string, string> = {
  active: "bg-green-100 text-green-700",
  inactive: "bg-gray-100 text-gray-500",
  pending: "bg-yellow-100 text-yellow-600",
};

export default function AdminOverviewPage() {
  const router = useRouter();
  const [stats, setStats] = useState<OrgStats | null>(null);
  const [teachers, setTeachers] = useState<Teacher[]>([]);
  const [repoTotal, setRepoTotal] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const [s, t, repo] = await Promise.all([
        apiFetch<OrgStats>("/api/v1/org/stats"),
        apiFetch<Teacher[]>("/api/v1/org/teachers"),
        apiFetch<{ total: number }>("/api/v1/org/repository/stats"),
      ]);
      setStats(s);
      setTeachers(t);
      setRepoTotal(repo.total);
    } catch {}
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const checksPct = stats
    ? Math.min(100, (stats.checks_this_month / stats.monthly_quota) * 100)
    : 0;

  return (
    <div className="p-8">
      <h1 className="text-xl font-semibold mb-6">Обзор школы</h1>

      <div className="grid grid-cols-4 gap-4 mb-8">
        {/* Учителя */}
        <div className="bg-white border rounded-xl p-4">
          <p className="text-xs text-gray-500">Учительские аккаунты</p>
          <p className="text-2xl font-bold mt-1">
            {stats ? (
              <span>
                {stats.used}{" "}
                <span className="text-base font-normal text-gray-400">
                  из {stats.seats_limit}
                </span>
              </span>
            ) : "—"}
          </p>
          {stats && (
            <>
              <div className="mt-2 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 rounded-full"
                  style={{ width: `${Math.min(100, (stats.used / stats.seats_limit) * 100)}%` }}
                />
              </div>
              <p className="text-xs text-gray-400 mt-1">
                {stats.active} активных · {stats.pending_invitations} ожидают · {stats.available} свободно
              </p>
            </>
          )}
        </div>

        {/* Проверки */}
        <div className="bg-white border rounded-xl p-4">
          <p className="text-xs text-gray-500">Проверок в этом месяце</p>
          <p className="text-2xl font-bold mt-1">
            {stats ? (
              <span>
                {stats.checks_this_month}{" "}
                <span className="text-base font-normal text-gray-400">
                  из {stats.monthly_quota.toLocaleString()}
                </span>
              </span>
            ) : "—"}
          </p>
          {stats && (
            <>
              <div className="mt-2 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${
                    checksPct >= 90 ? "bg-red-400" : checksPct >= 70 ? "bg-yellow-400" : "bg-green-400"
                  }`}
                  style={{ width: `${checksPct}%` }}
                />
              </div>
              <p className="text-xs text-gray-400 mt-1">
                осталось {(stats.monthly_quota - stats.checks_this_month).toLocaleString()}
              </p>
            </>
          )}
        </div>

        {/* Репозиторий */}
        <div className="bg-white border rounded-xl p-4">
          <p className="text-xs text-gray-500">Работ в репозитории</p>
          <p className="text-2xl font-bold mt-1">
            {repoTotal ?? "—"}
          </p>
        </div>

        {/* Flagged */}
        <div className="bg-white border rounded-xl p-4">
          <p className="text-xs text-gray-500">Flagged за месяц</p>
          <p className={`text-2xl font-bold mt-1 ${stats && stats.flagged_this_month > 0 ? "text-orange-500" : "text-gray-800"}`}>
            {stats ? stats.flagged_this_month : "—"}
          </p>
          {stats && stats.flagged_this_month > 0 && (
            <p className="text-xs text-orange-400 mt-1">проверок с обходом</p>
          )}
        </div>
      </div>

      {/* Teachers table */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold">Учителя</h2>
        <button
          onClick={() => router.push("/admin/teachers")}
          className="text-sm text-blue-600 hover:underline"
        >
          Управлять →
        </button>
      </div>

      <div className="bg-white border rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b bg-gray-50">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Имя</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Email</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Статус</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-gray-400 text-sm">Загрузка...</td>
              </tr>
            ) : teachers.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-gray-400 text-sm">
                  Нет учителей. Перейдите в «Учителя» чтобы пригласить первого.
                </td>
              </tr>
            ) : (
              teachers.map((t) => (
                <tr key={t.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900">{t.full_name}</td>
                  <td className="px-4 py-3 text-gray-500">{t.email}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLOR[t.status] ?? "bg-gray-100 text-gray-500"}`}>
                      {STATUS_LABEL[t.status] ?? t.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => router.push("/admin/teachers")}
                      className="text-xs text-blue-600 hover:underline"
                    >
                      Изменить
                    </button>
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
