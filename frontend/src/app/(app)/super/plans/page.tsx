"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";

interface OrgPlan {
  id: string;
  name: string;
  plan: string;
  seats_limit: number;
  monthly_quota: number;
  valid_until: string | null;
}

interface EditState {
  plan: string;
  seats_limit: number;
  monthly_quota: number;
  valid_until: string;
}

const PLANS = [
  {
    id: "standard",
    name: "Standard",
    color: "border-gray-200",
    badge: "bg-gray-100 text-gray-600",
    price: "150 000 сум/мес",
    features: ["До 10 учителей", "1 000 проверок в месяц", "Антиплагиат (шинглы)", "Flagged-защита"],
    missing: ["ИИ-детектор", "Межъязыковой поиск", "Репозиторий", "API-доступ"],
  },
  {
    id: "pro",
    name: "Pro",
    color: "border-blue-400",
    badge: "bg-blue-100 text-blue-700",
    price: "350 000 сум/мес",
    features: ["До 30 учителей", "5 000 проверок в месяц", "Шинглы + семантика", "Репозиторий", "API"],
    missing: [],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    color: "border-purple-400",
    badge: "bg-purple-100 text-purple-700",
    price: "По договору",
    features: ["Без ограничений", "Все функции Pro", "On-premise", "SLA 99.9%"],
    missing: [],
  },
];

export default function PlansPage() {
  const [orgs, setOrgs] = useState<OrgPlan[]>([]);
  const [editOrg, setEditOrg] = useState<string | null>(null);
  const [editState, setEditState] = useState<EditState | null>(null);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<OrgPlan[]>("/api/v1/admin/organizations")
      .then(setOrgs)
      .catch(() => setOrgs([]))
      .finally(() => setLoading(false));
  }, []);

  function startEdit(org: OrgPlan) {
    setEditOrg(org.id);
    setEditState({
      plan: org.plan,
      seats_limit: org.seats_limit,
      monthly_quota: org.monthly_quota,
      valid_until: org.valid_until ?? "",
    });
  }

  async function saveEdit(orgId: string) {
    if (!editState) return;
    setSaving(true);
    setError("");
    try {
      const payload: Record<string, unknown> = {
        plan: editState.plan,
        seats_limit: editState.seats_limit,
        monthly_quota: editState.monthly_quota,
        valid_until: editState.valid_until || null,
      };
      const updated = await apiFetch<OrgPlan>(`/api/v1/admin/organizations/${orgId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      setOrgs((prev) => prev.map((o) => (o.id === orgId ? { ...o, ...updated } : o)));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ошибка");
    } finally {
      setSaving(false);
      setEditOrg(null);
      setEditState(null);
    }
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">Тарифы и лимиты</h1>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-xl mb-5">
          {error}
        </div>
      )}

      {/* Plan cards */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        {PLANS.map((plan) => (
          <div key={plan.id} className={`bg-white border-2 rounded-xl p-5 ${plan.color}`}>
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold">{plan.name}</h2>
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${plan.badge}`}>
                {plan.id}
              </span>
            </div>
            <p className="text-lg font-bold text-gray-800 mb-4">{plan.price}</p>
            <ul className="space-y-1.5 text-sm text-gray-700">
              {plan.features.map((f) => (
                <li key={f} className="flex items-start gap-1.5">
                  <span className="text-green-500 mt-0.5 shrink-0">✓</span>
                  <span>{f}</span>
                </li>
              ))}
              {plan.missing.map((f) => (
                <li key={f} className="flex items-start gap-1.5 opacity-30">
                  <span className="mt-0.5 shrink-0">—</span>
                  <span>{f}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      {/* Org plan assignments */}
      <h2 className="font-semibold mb-4">Тарифы школ</h2>
      <div className="bg-white border rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b bg-gray-50">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Школа</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Тариф</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Учителей</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Проверок/мес</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Действует до</th>
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
            ) : (
              orgs.map((org) => (
                <tr key={org.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900">{org.name}</td>
                  <td className="px-4 py-3">
                    {editOrg === org.id && editState ? (
                      <select
                        className="border rounded px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        value={editState.plan}
                        onChange={(e) => setEditState({ ...editState, plan: e.target.value })}
                      >
                        <option value="standard">standard</option>
                        <option value="pro">pro</option>
                        <option value="enterprise">enterprise</option>
                      </select>
                    ) : (
                      <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                        {org.plan}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-700">
                    {editOrg === org.id && editState ? (
                      <input
                        type="number"
                        min={1}
                        className="w-20 border rounded px-2 py-1 text-sm focus:outline-none"
                        value={editState.seats_limit}
                        onChange={(e) => setEditState({ ...editState, seats_limit: +e.target.value })}
                      />
                    ) : (
                      org.seats_limit
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-700">
                    {editOrg === org.id && editState ? (
                      <input
                        type="number"
                        min={0}
                        className="w-24 border rounded px-2 py-1 text-sm focus:outline-none"
                        value={editState.monthly_quota}
                        onChange={(e) => setEditState({ ...editState, monthly_quota: +e.target.value })}
                      />
                    ) : (
                      org.monthly_quota.toLocaleString()
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {editOrg === org.id && editState ? (
                      <input
                        type="date"
                        className="border rounded px-2 py-1 text-sm focus:outline-none"
                        value={editState.valid_until}
                        onChange={(e) => setEditState({ ...editState, valid_until: e.target.value })}
                      />
                    ) : org.valid_until ? (
                      new Date(org.valid_until).toLocaleDateString("ru")
                    ) : (
                      <span className="text-gray-300">без ограничений</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {editOrg === org.id ? (
                      <div className="flex gap-2">
                        <button
                          onClick={() => saveEdit(org.id)}
                          disabled={saving}
                          className="text-xs bg-blue-600 text-white px-2 py-1 rounded hover:bg-blue-700 disabled:opacity-40"
                        >
                          {saving ? "..." : "Сохранить"}
                        </button>
                        <button
                          onClick={() => { setEditOrg(null); setEditState(null); }}
                          className="text-xs text-gray-500 hover:underline"
                        >
                          Отмена
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => startEdit(org)}
                        className="text-xs text-blue-600 hover:underline"
                      >
                        Изменить
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
