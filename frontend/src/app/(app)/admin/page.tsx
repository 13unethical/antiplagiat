"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { PageHeader, Stats, Status, type Tone } from "../ui";

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

const STATUS_TONE: Record<string, Tone> = { active: "green", inactive: "gray", pending: "amber" };

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

  return (
    <>
      <PageHeader title="Обзор школы" />
      <Stats
        items={[
          {
            label: "Места учителей",
            value: stats ? <>{stats.used} <span className="text-base font-normal text-gray-500">из {stats.seats_limit}</span></> : "—",
            note: stats && `активны: ${stats.active}, ожидают: ${stats.pending_invitations}, свободно: ${stats.available}`,
          },
          {
            label: "Проверок в этом месяце",
            value: stats ? <>{stats.checks_this_month} <span className="text-base font-normal text-gray-500">из {stats.monthly_quota.toLocaleString("ru")}</span></> : "—",
            note: stats && `осталось ${(stats.monthly_quota - stats.checks_this_month).toLocaleString("ru")}`,
          },
          { label: "Работ в репозитории", value: repoTotal ?? "—", note: "база для сравнения" },
          { label: "Попытки обхода", value: stats ? stats.flagged_this_month : "—", note: "работ за месяц" },
        ]}
      />

      {/* Teachers table */}
      <div className="section-title">
        <h2>Учителя</h2>
        <button onClick={() => router.push("/admin/teachers")} className="link">
          Управлять
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th>Имя</th>
              <th>Email</th>
              <th>Статус</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={4} className="table-empty">Загрузка...</td>
              </tr>
            ) : teachers.length === 0 ? (
              <tr>
                <td colSpan={4} className="table-empty">
                  Нет учителей. Перейдите в «Учителя» чтобы пригласить первого.
                </td>
              </tr>
            ) : (
              teachers.map((t) => (
                <tr key={t.id}>
                  <td className="font-medium text-gray-900">{t.full_name || "—"}</td>
                  <td className="text-gray-500">{t.email}</td>
                  <td>
                    <Status tone={STATUS_TONE[t.status]}>{STATUS_LABEL[t.status] ?? t.status}</Status>
                  </td>
                  <td>
                    <button
                      onClick={() => router.push("/admin/teachers")}
                      className="link"
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
    </>
  );
}
