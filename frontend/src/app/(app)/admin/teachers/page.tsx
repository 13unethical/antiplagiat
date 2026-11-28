"use client";

import { useEffect, useState, useCallback } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import { Icon, Notice, PageHeader, Status, type Tone } from "../../ui";

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

const STATUS_TONE: Record<string, Tone> = { active: "green", inactive: "gray", pending: "amber" };

export default function TeachersPage() {
  const [teachers, setTeachers] = useState<Teacher[]>([]);
  const [stats, setStats] = useState<TeacherStats | null>(null);
  const [checksStats, setChecksStats] = useState<Record<string, number>>({});
  const [showInvite, setShowInvite] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteName, setInviteName] = useState("");
  const [creds, setCreds] = useState<{ email: string; password: string } | null>(null);
  const [copied, setCopied] = useState(false);
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
      const created = await apiFetch<{ email: string; password: string }>("/api/v1/org/teachers", {
        method: "POST",
        body: JSON.stringify({
          email: inviteEmail.trim(),
          full_name: inviteName.trim() || undefined,
        }),
      });
      setCreds({ email: created.email, password: created.password });
      setMsg({ text: "Учитель создан. Скопируйте логин и пароль — пароль больше не покажется.", kind: "ok" });
      setInviteEmail("");
      setInviteName("");
      setShowInvite(false);
      fetchData();
    } catch (err) {
      setMsg({
        text: err instanceof ApiError ? err.message : "Ошибка",
        kind: "err",
      });
    }
  }

  async function resetPassword(t: Teacher) {
    if (!confirm(`Выпустить новый пароль для ${t.email}? Старый перестанет работать.`)) return;
    try {
      const created = await apiFetch<{ email: string; password: string }>(
        `/api/v1/org/teachers/${t.id}/reset-password`,
        { method: "POST" },
      );
      setCreds({ email: created.email, password: created.password });
      setMsg({ text: "Новый пароль выпущен. Скопируйте его сейчас.", kind: "ok" });
    } catch (err) {
      setMsg({ text: err instanceof ApiError ? err.message : "Ошибка", kind: "err" });
    }
  }

  async function copyCreds() {
    if (!creds) return;
    await navigator.clipboard.writeText(`Логин: ${creds.email}\nПароль: ${creds.password}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
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
    <>
      <PageHeader title="Учителя">
        {stats && (
          <span className="hidden sm:block text-xs text-gray-500 mr-2">
            Занято {stats.used} из {stats.seats_limit} мест
          </span>
        )}
        <button onClick={() => setShowInvite(!showInvite)} disabled={!canInvite} className="btn btn-primary">
          <Icon name="plus" />
          Добавить учителя
        </button>
      </PageHeader>

      {showInvite && (
        <form
          onSubmit={invite}
          className="px-4 md:px-6 py-4 border-b bg-gray-50 flex flex-wrap gap-3 items-end"
        >
          <div className="flex-1 min-w-[180px] max-w-xs">
            <label className="field-label">Имя</label>
            <input
              value={inviteName}
              onChange={(e) => setInviteName(e.target.value)}
              placeholder="Иван Иванов"
              className="field"
            />
          </div>
          <div className="flex-1 min-w-[220px] max-w-sm">
            <label className="field-label">Email (логин)</label>
            <input
              type="email"
              required
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="teacher@school.uz"
              className="field"
            />
          </div>
          <div className="flex gap-2">
            <button type="submit" className="btn btn-primary">Создать</button>
            <button type="button" onClick={() => setShowInvite(false)} className="btn btn-secondary">Отмена</button>
          </div>
        </form>
      )}

      {msg && <Notice kind={msg.kind} onClose={() => setMsg(null)}>{msg.text}</Notice>}

      {creds && (
        <div className="mx-4 md:mx-6 my-4 p-4 border rounded-xl bg-gray-50 space-y-2">
          <p className="text-sm font-medium text-gray-900">Данные для входа (скопируйте сейчас)</p>
          <div className="text-sm font-mono break-all">
            <div>Логин: {creds.email}</div>
            <div>Пароль: {creds.password}</div>
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={copyCreds} className="btn btn-secondary">
              {copied ? "Скопировано" : "Копировать"}
            </button>
            <button type="button" onClick={() => setCreds(null)} className="btn btn-secondary">Закрыть</button>
          </div>
        </div>
      )}

      {/* Teachers table */}
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th>Имя</th>
              <th>Email</th>
              <th>
                Проверок за месяц
              </th>
              <th>
                Личный лимит
              </th>
              <th>Статус</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} className="table-empty">
                  Загрузка...
                </td>
              </tr>
            ) : teachers.length === 0 ? (
              <tr>
                <td colSpan={6} className="table-empty">
                  Нет учителей. Нажмите «Добавить учителя».
                </td>
              </tr>
            ) : (
              teachers.map((t) => (
                <tr key={t.id}>
                  <td className="font-medium text-gray-900">{t.full_name || "—"}</td>
                  <td className="text-gray-500">{t.email}</td>
                  <td className="text-gray-700">
                    {checksStats[t.id] ?? 0}
                  </td>
                  <td>
                    {editQuotaId === t.id ? (
                      <div className="flex items-center gap-1">
                        <input
                          type="number"
                          min={0}
                          className="field !w-28 !min-h-8"
                          placeholder="Без лимита"
                          aria-label="Личный лимит"
                          value={quotaInput}
                          onChange={(e) => setQuotaInput(e.target.value)}
                          autoFocus
                        />
                        <button onClick={() => saveQuota(t)} className="link ml-2">Сохранить</button>
                        <button onClick={() => setEditQuotaId(null)} className="link-danger ml-2">Отмена</button>
                      </div>
                    ) : (
                      <button
                        onClick={() => { setEditQuotaId(t.id); setQuotaInput(t.personal_quota?.toString() ?? ""); }}
                        className="text-sm text-gray-700 hover:text-blue-700 hover:underline"
                      >
                        {t.personal_quota != null ? `${t.personal_quota} в месяц` : "Без лимита"}
                      </button>
                    )}
                  </td>
                  <td>
                    <Status tone={STATUS_TONE[t.status]}>{STATUS_LABEL[t.status] ?? t.status}</Status>
                  </td>
                  <td className="space-x-3 whitespace-nowrap">
                    {t.status !== "pending" && (
                      <button
                        onClick={() => toggleStatus(t)}
                        className={t.status === "active" ? "link-danger" : "link"}
                      >
                        {t.status === "active" ? "Отключить" : "Включить"}
                      </button>
                    )}
                    {t.status === "active" && (
                      <button onClick={() => resetPassword(t)} className="link">
                        Новый пароль
                      </button>
                    )}
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
