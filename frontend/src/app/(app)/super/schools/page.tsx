"use client";

import { Fragment, useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, ApiError } from "@/lib/api";
import { Icon, Notice, PageHeader, Status } from "../../ui";

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

type MsgState = { text: string; kind: "ok" | "err" } | null;

export default function SchoolsPage() {
  const router = useRouter();
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [inviteForm, setInviteForm] = useState<{ orgId: string; email: string } | null>(null);
  const [editForm, setEditForm] = useState<Organization | null>(null);
  const [newOrg, setNewOrg] = useState({ name: "", seats_limit: 10, monthly_quota: 1000 });
  const [msg, setMsg] = useState<MsgState>(null);
  const [loading, setLoading] = useState(true);
  const [expandedOrg, setExpandedOrg] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [o, u] = await Promise.all([
        apiFetch<Organization[]>("/api/v1/admin/organizations"),
        apiFetch<User[]>("/api/v1/admin/users"),
      ]);
      setOrgs(o);
      setUsers(u);
    } catch {}
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  async function createOrg(e: React.FormEvent) {
    e.preventDefault();
    try {
      await apiFetch("/api/v1/admin/organizations", {
        method: "POST",
        body: JSON.stringify(newOrg),
      });
      setShowCreate(false);
      setNewOrg({ name: "", seats_limit: 10, monthly_quota: 1000 });
      setMsg({ text: "Школа создана", kind: "ok" });
      fetchData();
    } catch (err) {
      setMsg({ text: err instanceof ApiError ? err.message : "Ошибка", kind: "err" });
    }
  }

  async function saveOrgLimits(e: React.FormEvent) {
    e.preventDefault();
    if (!editForm) return;
    try {
      await apiFetch(`/api/v1/admin/organizations/${editForm.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          seats_limit: editForm.seats_limit,
          monthly_quota: editForm.monthly_quota,
          plan: editForm.plan,
          valid_until: editForm.valid_until || null,
        }),
      });
      setEditForm(null);
      setMsg({ text: "Лимиты обновлены", kind: "ok" });
      fetchData();
    } catch (err) {
      setMsg({ text: err instanceof ApiError ? err.message : "Ошибка", kind: "err" });
    }
  }

  async function handleImpersonate(targetUser: User) {
    try {
      const data = await apiFetch<{ access_token: string; target_email: string; target_name: string }>(
        `/api/v1/admin/impersonate/${targetUser.id}`,
        { method: "POST" }
      );
      // Save originals so we can restore later
      const currentToken = localStorage.getItem("access_token");
      const currentUser = localStorage.getItem("user");
      if (currentToken) localStorage.setItem("impersonation_original_token", currentToken);
      if (currentUser) localStorage.setItem("impersonation_original_user", currentUser);
      localStorage.setItem("impersonation_target_name", data.target_name);
      localStorage.setItem("impersonation_target_email", data.target_email);
      // Switch token
      localStorage.setItem("access_token", data.access_token);
      // Fetch impersonated user's profile and store it
      const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const meRes = await fetch(`${base}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${data.access_token}` },
      });
      if (meRes.ok) {
        const me = await meRes.json();
        localStorage.setItem("user", JSON.stringify(me));
      }
      window.location.href = targetUser.role === "teacher" ? "/checks" : "/admin";
    } catch (err) {
      setMsg({ text: err instanceof ApiError ? err.message : "Ошибка имперсонации", kind: "err" });
    }
  }

  async function sendInvite(e: React.FormEvent) {
    e.preventDefault();
    if (!inviteForm) return;
    try {
      const inv = await apiFetch<{ token: string }>("/api/v1/admin/invitations", {
        method: "POST",
        body: JSON.stringify({
          email: inviteForm.email,
          role: "school_admin",
          org_id: inviteForm.orgId,
        }),
      });
      setMsg({ text: `Приглашение создано. Токен: ${inv.token}`, kind: "ok" });
      setInviteForm(null);
      fetchData();
    } catch (err) {
      setMsg({ text: err instanceof ApiError ? err.message : "Ошибка", kind: "err" });
    }
  }

  return (
    <>
      <PageHeader title="Школы и админы">
        <button onClick={() => setShowCreate(!showCreate)} className="btn btn-primary">
          <Icon name="plus" />
          Создать школу
        </button>
      </PageHeader>

      {/* Create form */}
      {showCreate && (
        <form onSubmit={createOrg} className="form-block">
          <h2 className="font-semibold text-base">Новая школа</h2>
          <div>
            <label className="field-label">Название</label>
            <input
              required
              className="field"
              placeholder="Школа №1"
              value={newOrg.name}
              onChange={(e) => setNewOrg({ ...newOrg, name: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="field-label">Лимит учителей</label>
              <input
                type="number" min={1}
                className="field"
                value={newOrg.seats_limit}
                onChange={(e) => setNewOrg({ ...newOrg, seats_limit: +e.target.value })}
              />
            </div>
            <div>
              <label className="field-label">Проверок в месяц</label>
              <input
                type="number" min={1}
                className="field"
                value={newOrg.monthly_quota}
                onChange={(e) => setNewOrg({ ...newOrg, monthly_quota: +e.target.value })}
              />
            </div>
          </div>
          <div className="flex gap-2">
            <button type="submit" className="btn btn-primary">Создать</button>
            <button type="button" onClick={() => setShowCreate(false)} className="btn btn-secondary">Отмена</button>
          </div>
        </form>
      )}

      {/* Edit limits modal */}
      {editForm && (
        <form onSubmit={saveOrgLimits} className="form-block">
          <h2 className="font-semibold text-base">Лимиты: {editForm.name}</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="field-label">Лимит учителей</label>
              <input
                type="number" min={1}
                className="field"
                value={editForm.seats_limit}
                onChange={(e) => setEditForm({ ...editForm, seats_limit: +e.target.value })}
              />
            </div>
            <div>
              <label className="field-label">Проверок в месяц</label>
              <input
                type="number" min={1}
                className="field"
                value={editForm.monthly_quota}
                onChange={(e) => setEditForm({ ...editForm, monthly_quota: +e.target.value })}
              />
            </div>
            <div>
              <label className="field-label">Тариф</label>
              <select
                className="field"
                value={editForm.plan}
                onChange={(e) => setEditForm({ ...editForm, plan: e.target.value })}
              >
                <option value="standard">standard</option>
                <option value="pro">pro</option>
                <option value="enterprise">enterprise</option>
              </select>
            </div>
            <div>
              <label className="field-label">Действует до</label>
              <input
                type="date"
                className="field"
                value={editForm.valid_until?.slice(0, 10) ?? ""}
                onChange={(e) => setEditForm({ ...editForm, valid_until: e.target.value || null })}
              />
            </div>
          </div>
          <div className="flex gap-2">
            <button type="submit" className="btn btn-primary">Сохранить</button>
            <button type="button" onClick={() => setEditForm(null)} className="btn btn-secondary">Отмена</button>
          </div>
        </form>
      )}

      {/* Invite admin form */}
      {inviteForm && (
        <form onSubmit={sendInvite} className="form-block">
          <h2 className="font-semibold text-base">Пригласить администратора школы</h2>
          <input
            type="email" required
            value={inviteForm.email}
            onChange={(e) => setInviteForm({ ...inviteForm, email: e.target.value })}
            placeholder="admin@school.uz"
            className="field"
          />
          <div className="flex gap-2">
            <button type="submit" className="btn btn-primary">Отправить</button>
            <button type="button" onClick={() => setInviteForm(null)} className="btn btn-secondary">Отмена</button>
          </div>
        </form>
      )}

      {/* Message */}
      {msg && <Notice kind={msg.kind} onClose={() => setMsg(null)}>{msg.text}</Notice>}

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th>Школа</th>
              <th>Админ</th>
              <th>Учителя</th>
              <th>Лимит проверок</th>
              <th>Тариф</th>
              <th>Действует до</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="table-empty">Загрузка...</td>
              </tr>
            ) : orgs.length === 0 ? (
              <tr>
                <td colSpan={7} className="table-empty">Нет школ. Нажмите «Создать школу».</td>
              </tr>
            ) : (
              orgs.map((org) => {
                const admin = users.find((u) => u.org_id === org.id && u.role === "school_admin");
                const teachers = users.filter((u) => u.org_id === org.id && u.role === "teacher");
                const isExpanded = expandedOrg === org.id;
                return (
                  <Fragment key={org.id}>
                    <tr>
                      <td className="font-medium text-gray-900">{org.name}</td>
                      <td className="text-xs text-gray-500">
                        {admin ? (
                          <div className="flex items-center gap-2">
                            <span>{admin.email}</span>
                            <button
                              onClick={() => handleImpersonate(admin)}
                              className="link"
                            >
                              Войти
                            </button>
                          </div>
                        ) : (
                          <span className="text-gray-500">Не назначен</span>
                        )}
                      </td>
                      <td className="text-gray-700">
                        <button
                          onClick={() => setExpandedOrg(isExpanded ? null : org.id)}
                          aria-expanded={isExpanded}
                          aria-label={`Учителя школы ${org.name}`}
                          className="flex items-center gap-1 whitespace-nowrap hover:text-blue-700 transition-colors"
                        >
                          <span>{teachers.length} / {org.seats_limit}</span>
                          <Icon name="chevron" className={`text-gray-500 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
                        </button>
                      </td>
                      <td className="text-gray-500">{org.monthly_quota.toLocaleString("ru")} / мес</td>
                      <td>
                        <span className="text-gray-700">{org.plan}</span>
                      </td>
                      <td className="text-gray-500 text-xs">
                        {org.valid_until
                          ? new Date(org.valid_until).toLocaleDateString("ru")
                          : <span className="text-gray-300">—</span>}
                      </td>
                      <td>
                        <div className="flex gap-3">
                          <button
                            onClick={() => setEditForm({ ...org })}
                            className="link"
                          >
                            Лимиты
                          </button>
                          <button
                            onClick={() => setInviteForm({ orgId: org.id, email: "" })}
                            className="link"
                          >
                            {admin ? "Сменить админа" : "Пригласить админа"}
                          </button>
                        </div>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr className="bg-gray-50">
                        <td colSpan={7} className="px-6 py-3">
                          {teachers.length === 0 ? (
                            <p className="text-xs text-gray-500">Нет учителей в этой школе</p>
                          ) : (
                            <div className="space-y-1">
                              <p className="text-xs font-medium text-gray-500 mb-2">Учителя школы</p>
                              {teachers.map((t) => (
                                <div key={t.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
                                  <span className="text-gray-700 w-48 truncate">{t.email}</span>
                                  <span className="text-gray-500">{t.full_name || "—"}</span>
                                  <Status tone={t.status === "active" ? "green" : t.status === "pending" ? "amber" : "gray"}>
                                    {t.status === "active" ? "Активен" : t.status === "pending" ? "Приглашён" : "Отключён"}
                                  </Status>
                                  {t.status === "active" && (
                                    <button
                                      onClick={() => handleImpersonate(t)}
                                      className="link"
                                    >
                                      Войти как учитель
                                    </button>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
