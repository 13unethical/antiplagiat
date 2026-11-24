"use client";

import { useEffect, useState, useCallback } from "react";
import { apiFetch, ApiError } from "@/lib/api";

interface Teacher {
  id: string;
  email: string;
  full_name: string;
  status: string;
  personal_quota: number | null;
}

interface TeacherStats {
  active: number;
  pending_invitations: number;
  used: number;
  seats_limit: number;
  available: number;
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

export default function TeachersPage() {
  const [teachers, setTeachers] = useState<Teacher[]>([]);
  const [stats, setStats] = useState<TeacherStats | null>(null);
  const [checksStats, setChecksStats] = useState<Record<string, number>>({});
  const [showInvite, setShowInvite] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [editQuotaId, setEditQuotaId] = useState<string | null>(null);
  const [quotaInput, setQuotaInput] = useState("");
  const [msg, setMsg] = useState<{ text: string; kind: "ok" | "err" } | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const [t, s, cs] = await Promise.all([
        apiFetch<Teacher[]>("/api/v1/org/teachers"),
        apiFetch<TeacherStats>("/api/v1/org/teachers/stats"),
        apiFetch<Record<string, number>>("/api/v1/org/teachers/checks-stats"),
      ]);
      setTeachers(t);
      setStats(s);
      setChecksStats(cs);
    } catch {}
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  async function invite(e: React.FormEvent) {
    e.preventDefault();
    try {
      const inv = await apiFetch<{ token: string }>("/api/v1/org/invitations", {
        method: "POST",
        body: JSON.stringify({ email: inviteEmail, role: "teacher" }),
      });
      setMsg({
        text: `Приглашение создано. Токен: ${inv.token}`,
        kind: "ok",
      });
      setInviteEmail("");
      setShowInvite(false);
      fetchData();
    } catch (err) {
      setMsg({
        text: err instanceof ApiError ? err.message : "Ошибка",
        kind: "err",
      });
    }
  }

  async function saveQuota(teacher: Teacher) {
    const val = quotaInput.trim() === "" ? null : parseInt(quotaInput);
    if (quotaInput.trim() !== "" && (isNaN(val!) || val! < 0)) {
      setMsg({ text: "Лимит должен быть целым числом ≥ 0", kind: "err" });
      return;
    }
    try {
      await apiFetch(`/api/v1/org/teachers/${teacher.id}/quota?personal_quota=${val ?? ""}`, {
        method: "PATCH",
      });
      setEditQuotaId(null);
      fetchData();
    } catch (err) {
      setMsg({ text: err instanceof ApiError ? err.message : "Ошибка", kind: "err" });
    }
  }

  async function toggleStatus(t: Teacher) {
    const newStatus = t.status === "active" ? "inactive" : "active";
    try {
      await apiFetch(`/api/v1/org/teachers/${t.id}/status?status=${newStatus}`, {
        method: "PATCH",
      });
      fetchData();
    } catch (err) {
      setMsg({
        text: err instanceof ApiError ? err.message : "Ошибка",
        kind: "err",
      });
    }
  }

  const canInvite = stats ? stats.available > 0 : false;

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold">Учителя</h1>
          {stats && (
            <p className="text-sm text-gray-500 mt-0.5">
              {stats.used} из {stats.seats_limit} мест занято · можно добавить ещё {stats.available}
            </p>
          )}
        </div>
        <button
          onClick={() => setShowInvite(!showInvite)}
          disabled={!canInvite}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-40 transition-colors"
        >
          + Пригласить учителя
        </button>
      </div>

      {/* Invite form */}
      {showInvite && (
        <form
          onSubmit={invite}
          className="bg-white border rounded-xl p-4 mb-5 flex gap-3 items-end"
        >
          <div className="flex-1">
            <label className="block text-xs font-medium text-gray-500 mb-1">
              Email учителя
            </label>
            <input
              type="email"
              required
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="teacher@school.uz"
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div className="flex gap-2">
            <button
              type="submit"
              className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700"
            >
              Отправить
            </button>
            <button
              type="button"
              onClick={() => setShowInvite(false)}
              className="border px-4 py-2 rounded-lg text-sm text-gray-600 hover:bg-gray-50"
            >
              Отмена
            </button>
          </div>
        </form>
      )}

      {/* Message */}
      {msg && (
        <div
          className={`mb-5 px-4 py-3 rounded-xl text-sm break-all border ${
            msg.kind === "ok"
              ? "bg-blue-50 border-blue-200 text-blue-800"
              : "bg-red-50 border-red-200 text-red-700"
          }`}
        >
          {msg.text}
          <button
            onClick={() => setMsg(null)}
            className="ml-3 opacity-50 hover:opacity-100"
          >
            ×
          </button>
        </div>
      )}

      {/* Teachers table */}
      <div className="bg-white border rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b bg-gray-50">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Имя</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Email</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">
                Проверок за месяц
              </th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">
                Личный лимит
              </th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Статус</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400 text-sm">
                  Загрузка...
                </td>
              </tr>
            ) : teachers.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400 text-sm">
                  Нет учителей. Нажмите «Пригласить учителя».
                </td>
              </tr>
            ) : (
              teachers.map((t) => (
                <tr key={t.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900">{t.full_name}</td>
                  <td className="px-4 py-3 text-gray-500">{t.email}</td>
                  <td className="px-4 py-3 text-gray-700 text-sm">
                    {checksStats[t.id] ?? 0}
                  </td>
                  <td className="px-4 py-3">
                    {editQuotaId === t.id ? (
                      <div className="flex items-center gap-1">
                        <input
                          type="number"
                          min={0}
                          className="w-20 border rounded px-2 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                          placeholder="∞"
                          value={quotaInput}
                          onChange={(e) => setQuotaInput(e.target.value)}
                          autoFocus
                        />
                        <button onClick={() => saveQuota(t)} className="text-xs text-green-600 hover:underline">✓</button>
                        <button onClick={() => setEditQuotaId(null)} className="text-xs text-gray-400 hover:underline">✕</button>
                      </div>
                    ) : (
                      <button
                        onClick={() => { setEditQuotaId(t.id); setQuotaInput(t.personal_quota?.toString() ?? ""); }}
                        className="text-xs text-gray-500 hover:text-blue-600"
                      >
                        {t.personal_quota != null ? `${t.personal_quota}/мес` : "∞ без лимита"}
                      </button>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        STATUS_COLOR[t.status] ?? "bg-gray-100 text-gray-500"
                      }`}
                    >
                      {STATUS_LABEL[t.status] ?? t.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {t.status !== "pending" && (
                      <button
                        onClick={() => toggleStatus(t)}
                        className={`text-xs hover:underline ${
                          t.status === "active"
                            ? "text-red-500"
                            : "text-green-600"
                        }`}
                      >
                        {t.status === "active" ? "Отключить" : "Включить"}
                      </button>
                    )}
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
