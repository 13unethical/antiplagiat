"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

interface PlatformStats {
  orgs_total: number;
  teachers_total: number;
  admins_total: number;
  checks_this_month: number;
  flagged_this_month: number;
  web_queries_this_month: number;
  web_urls_fetched_this_month: number;
  web_matches_this_month: number;
}

interface Organization {
  id: string;
  name: string;
  seats_limit: number;
  monthly_quota: number;
  plan: string;
  valid_until: string | null;
}

interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  org_id: string | null;
  status: string;
}

export default function SuperOverviewPage() {
  const router = useRouter();
  const [platformStats, setPlatformStats] = useState<PlatformStats | null>(null);
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const [stats, o, u] = await Promise.all([
        apiFetch<PlatformStats>("/api/v1/admin/stats"),
        apiFetch<Organization[]>("/api/v1/admin/organizations"),
        apiFetch<User[]>("/api/v1/admin/users"),
      ]);
      setPlatformStats(stats);
      setOrgs(o);
      setUsers(u);
    } catch {}
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">Обзор платформы</h1>
        <button
          onClick={() => router.push("/super/schools")}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 transition-colors"
        >
          + Создать школу
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-white border rounded-xl p-4">
          <p className="text-xs text-gray-500">Школ</p>
          <p className="text-2xl font-bold mt-1">
            {loading ? "—" : platformStats?.orgs_total ?? 0}
          </p>
        </div>
        <div className="bg-white border rounded-xl p-4">
          <p className="text-xs text-gray-500">Учителей</p>
          <p className="text-2xl font-bold mt-1">
            {loading ? "—" : platformStats?.teachers_total ?? 0}
          </p>
          {platformStats && platformStats.admins_total > 0 && (
            <p className="text-xs text-gray-400 mt-1">{platformStats.admins_total} администраторов</p>
          )}
        </div>
        <div className="bg-white border rounded-xl p-4">
          <p className="text-xs text-gray-500">Проверок за месяц</p>
          <p className="text-2xl font-bold mt-1">
            {loading ? "—" : platformStats?.checks_this_month ?? 0}
          </p>
        </div>
        <div className="bg-white border rounded-xl p-4">
          <p className="text-xs text-gray-500">Flagged за месяц</p>
          <p className={`text-2xl font-bold mt-1 ${platformStats && platformStats.flagged_this_month > 0 ? "text-orange-500" : ""}`}>
            {loading ? "—" : platformStats?.flagged_this_month ?? 0}
          </p>
        </div>
      </div>

      {/* Web search stats */}
      <div className="bg-white border rounded-xl p-4 mb-8">
        <p className="text-xs font-medium text-gray-500 mb-3">🌐 Веб-поиск за месяц</p>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <p className="text-xl font-bold">{loading ? "—" : platformStats?.web_queries_this_month ?? 0}</p>
            <p className="text-xs text-gray-400 mt-0.5">Запросов к Brave API</p>
          </div>
          <div>
            <p className="text-xl font-bold">{loading ? "—" : platformStats?.web_urls_fetched_this_month ?? 0}</p>
            <p className="text-xs text-gray-400 mt-0.5">Страниц скачано</p>
          </div>
          <div>
            <p className="text-xl font-bold text-orange-600">{loading ? "—" : platformStats?.web_matches_this_month ?? 0}</p>
            <p className="text-xs text-gray-400 mt-0.5">Совпадений найдено</p>
          </div>
        </div>
      </div>

      {/* Schools */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold">Школы</h2>
        <button
          onClick={() => router.push("/super/schools")}
          className="text-sm text-blue-600 hover:underline"
        >
          Все школы →
        </button>
      </div>

      <div className="bg-white border rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b bg-gray-50">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Школа</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Админ</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Учителя</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Лимит проверок</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Тариф</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400 text-sm">Загрузка...</td>
              </tr>
            ) : orgs.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400 text-sm">
                  Нет школ. Нажмите «Создать школу».
                </td>
              </tr>
            ) : (
              orgs.map((org) => {
                const admin = users.find((u) => u.org_id === org.id && u.role === "school_admin");
                const teacherCount = users.filter((u) => u.org_id === org.id && u.role === "teacher").length;
                return (
                  <tr key={org.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-900">{org.name}</td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {admin?.email ?? <span className="text-gray-300">не назначен</span>}
                    </td>
                    <td className="px-4 py-3 text-gray-700">
                      {teacherCount} / {org.seats_limit}
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {org.monthly_quota.toLocaleString()} / мес
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                        {org.plan}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => router.push("/super/schools")}
                        className="text-xs text-blue-600 hover:underline"
                      >
                        Лимиты
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
