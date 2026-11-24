"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, ApiError } from "@/lib/api";

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
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">Школы и админы</h1>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 transition-colors"
        >
          + Создать школу
        </button>
      </div>

      {/* Create form */}
      {showCreate && (
        <form onSubmit={createOrg} className="bg-white border rounded-xl p-5 mb-5 space-y-4">
          <h2 className="font-medium text-sm">Новая школа</h2>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Название</label>
            <input
              required
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Школа №1"
              value={newOrg.name}
              onChange={(e) => setNewOrg({ ...newOrg, name: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Лимит учителей</label>
              <input
                type="number" min={1}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={newOrg.seats_limit}
                onChange={(e) => setNewOrg({ ...newOrg, seats_limit: +e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Проверок в месяц</label>
              <input
                type="number" min={1}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={newOrg.monthly_quota}
                onChange={(e) => setNewOrg({ ...newOrg, monthly_quota: +e.target.value })}
              />
            </div>
          </div>
          <div className="flex gap-2">
            <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700">Создать</button>
            <button type="button" onClick={() => setShowCreate(false)} className="border px-4 py-2 rounded-lg text-sm text-gray-600 hover:bg-gray-50">Отмена</button>
          </div>
        </form>
      )}

      {/* Edit limits modal */}
      {editForm && (
        <form onSubmit={saveOrgLimits} className="bg-white border rounded-xl p-5 mb-5 space-y-4">
          <h2 className="font-medium text-sm">Лимиты: {editForm.name}</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Лимит учителей</label>
              <input
                type="number" min={1}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={editForm.seats_limit}
                onChange={(e) => setEditForm({ ...editForm, seats_limit: +e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Проверок в месяц</label>
              <input
                type="number" min={1}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={editForm.monthly_quota}
                onChange={(e) => setEditForm({ ...editForm, monthly_quota: +e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Тариф</label>
              <select
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={editForm.plan}
                onChange={(e) => setEditForm({ ...editForm, plan: e.target.value })}
              >
                <option value="standard">standard</option>
                <option value="pro">pro</option>
                <option value="enterprise">enterprise</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Действует до</label>
              <input
                type="date"
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={editForm.valid_until?.slice(0, 10) ?? ""}
                onChange={(e) => setEditForm({ ...editForm, valid_until: e.target.value || null })}
              />
            </div>
          </div>
          <div className="flex gap-2">
            <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700">Сохранить</button>
            <button type="button" onClick={() => setEditForm(null)} className="border px-4 py-2 rounded-lg text-sm text-gray-600 hover:bg-gray-50">Отмена</button>
          </div>
        </form>
      )}

      {/* Invite admin form */}
      {inviteForm && (
        <form onSubmit={sendInvite} className="bg-white border rounded-xl p-5 mb-5 space-y-3">
          <h2 className="font-medium text-sm">Пригласить администратора школы</h2>
          <input
            type="email" required
            value={inviteForm.email}
            onChange={(e) => setInviteForm({ ...inviteForm, email: e.target.value })}
            placeholder="admin@school.uz"
            className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <div className="flex gap-2">
            <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700">Отправить</button>
            <button type="button" onClick={() => setInviteForm(null)} className="border px-4 py-2 rounded-lg text-sm text-gray-600 hover:bg-gray-50">Отмена</button>
          </div>
        </form>
      )}

      {/* Message */}
      {msg && (
        <div className={`mb-5 px-4 py-3 rounded-xl text-sm break-all border ${
          msg.kind === "ok" ? "bg-blue-50 border-blue-200 text-blue-800" : "bg-red-50 border-red-200 text-red-700"
        }`}>
          {msg.text}
          <button onClick={() => setMsg(null)} className="ml-3 opacity-50 hover:opacity-100">×</button>
        </div>
      )}

      {/* Table */}
      <div className="bg-white border rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b bg-gray-50">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Школа</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Админ</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Учителя</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Лимит проверок</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Тариф</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Действует до</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400 text-sm">Загрузка...</td>
              </tr>
            ) : orgs.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400 text-sm">Нет школ. Нажмите «Создать школу».</td>
              </tr>
            ) : (
              orgs.map((org) => {
                const admin = users.find((u) => u.org_id === org.id && u.role === "school_admin");
                const teachers = users.filter((u) => u.org_id === org.id && u.role === "teacher");
                const isExpanded = expandedOrg === org.id;
                return (
                  <>
                    <tr key={org.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium text-gray-900">{org.name}</td>
                      <td className="px-4 py-3 text-xs text-gray-500">
                        {admin ? (
                          <div className="flex items-center gap-2">
                            <span>{admin.email}</span>
                            <button
                              onClick={() => handleImpersonate(admin)}
                              className="text-purple-600 hover:underline text-xs"
                            >
                              войти
                            </button>
                          </div>
                        ) : (
                          <span className="text-gray-300">не назначен</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-gray-700">
                        <button
                          onClick={() => setExpandedOrg(isExpanded ? null : org.id)}
                          className="flex items-center gap-1 hover:text-blue-600 transition-colors"
                        >
                          <span>{teachers.length} / {org.seats_limit}</span>
                          <span className="text-gray-400 text-xs">{isExpanded ? "▲" : "▼"}</span>
                        </button>
                      </td>
                      <td className="px-4 py-3 text-gray-500">{org.monthly_quota.toLocaleString()} / мес</td>
                      <td className="px-4 py-3">
                        <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{org.plan}</span>
                      </td>
                      <td className="px-4 py-3 text-gray-500 text-xs">
                        {org.valid_until
                          ? new Date(org.valid_until).toLocaleDateString("ru")
                          : <span className="text-gray-300">—</span>}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-3">
                          <button
                            onClick={() => setEditForm({ ...org })}
                            className="text-xs text-blue-600 hover:underline"
                          >
                            Лимиты
                          </button>
                          <button
                            onClick={() => setInviteForm({ orgId: org.id, email: "" })}
                            className="text-xs text-blue-600 hover:underline"
                          >
                            {admin ? "Сменить админа" : "Пригласить админа"}
                          </button>
                        </div>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr key={`${org.id}-teachers`} className="bg-purple-50">
                        <td colSpan={7} className="px-6 py-3">
                          {teachers.length === 0 ? (
                            <p className="text-xs text-gray-400">Нет учителей в этой школе</p>
                          ) : (
                            <div className="space-y-1">
                              <p className="text-xs font-medium text-gray-500 mb-2">Учителя школы:</p>
                              {teachers.map((t) => (
                                <div key={t.id} className="flex items-center gap-3 text-xs">
                                  <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${t.status === "active" ? "bg-green-400" : "bg-gray-300"}`} />
                                  <span className="text-gray-700 w-48 truncate">{t.email}</span>
                                  <span className="text-gray-400">{t.full_name || "—"}</span>
                                  <span className={`text-xs px-1.5 py-0.5 rounded ${t.status === "active" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                                    {t.status === "active" ? "активен" : "отключён"}
                                  </span>
                                  {t.status === "active" && (
                                    <button
                                      onClick={() => handleImpersonate(t)}
                                      className="text-purple-600 hover:underline font-medium"
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
                  </>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
