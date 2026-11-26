"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { Icon, PageHeader, Stats } from "../ui";

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
    <>
      <PageHeader title="Обзор платформы">
        <button onClick={() => router.push("/super/schools")} className="btn btn-primary">
          <Icon name="plus" />
          Создать школу
        </button>
      </PageHeader>
      <Stats
        items={[
          { label: "Школы", value: loading ? "—" : platformStats?.orgs_total ?? 0, note: "на платформе" },
          {
            label: "Учителя",
            value: loading ? "—" : platformStats?.teachers_total ?? 0,
            note: `администраторов: ${platformStats?.admins_total ?? 0}`,
          },
          { label: "Проверки", value: loading ? "—" : platformStats?.checks_this_month ?? 0, note: "за этот месяц" },
          { label: "Попытки обхода", value: loading ? "—" : platformStats?.flagged_this_month ?? 0, note: "работ за этот месяц" },
        ]}
      />
      <div className="px-4 md:px-6 py-3 border-b flex flex-wrap gap-x-6 gap-y-1 text-gray-600 tabular">
        <span className="font-medium text-gray-900">Веб-поиск за месяц</span>
        <span>запросов к Brave: {loading ? "—" : platformStats?.web_queries_this_month ?? 0}</span>
        <span>страниц скачано: {loading ? "—" : platformStats?.web_urls_fetched_this_month ?? 0}</span>
        <span>совпадений: {loading ? "—" : platformStats?.web_matches_this_month ?? 0}</span>
      </div>

      <div className="section-title">
        <h2>Школы</h2>
        <button onClick={() => router.push("/super/schools")} className="link">
          Все школы
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th>Школа</th>
              <th>Админ</th>
              <th>Учителя</th>
              <th>Лимит проверок</th>
              <th>Тариф</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} className="table-empty">Загрузка...</td>
              </tr>
            ) : orgs.length === 0 ? (
              <tr>
                <td colSpan={6} className="table-empty">
                  Нет школ. Нажмите «Создать школу».
                </td>
              </tr>
            ) : (
              orgs.map((org) => {
                const admin = users.find((u) => u.org_id === org.id && u.role === "school_admin");
                const teacherCount = users.filter((u) => u.org_id === org.id && u.role === "teacher").length;
                return (
                  <tr key={org.id}>
                    <td className="font-medium text-gray-900">{org.name}</td>
                    <td className="text-gray-500 text-xs">
                      {admin?.email ?? <span className="text-gray-500">Не назначен</span>}
                    </td>
                    <td className="text-gray-700">
                      {teacherCount} / {org.seats_limit}
                    </td>
                    <td className="text-gray-500">
                      {org.monthly_quota.toLocaleString("ru")} / мес
                    </td>
                    <td>
                      <span className="text-gray-700">
                        {org.plan}
                      </span>
                    </td>
                    <td>
                      <button
                        onClick={() => router.push("/super/schools")}
                        className="link"
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
    </>
  );
}
