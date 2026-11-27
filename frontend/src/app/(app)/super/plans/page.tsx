"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import { Icon, Notice, PageHeader } from "../../ui";

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
    price: "150 000 сум/мес",
    features: ["До 10 учителей", "1 000 проверок в месяц", "Плагиат (шинглы)", "Защита от обхода"],
    missing: ["ИИ-детектор", "Межъязыковой поиск", "Репозиторий", "API-доступ"],
  },
  {
    id: "pro",
    name: "Pro",
    price: "350 000 сум/мес",
    features: ["До 30 учителей", "5 000 проверок в месяц", "Шинглы + семантика", "Репозиторий", "API"],
    missing: [],
  },
  {
    id: "enterprise",
    name: "Enterprise",
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
    <>
      <PageHeader title="Тарифы и лимиты" />

      {error && <Notice kind="err">{error}</Notice>}

      {/* Plan cards */}
      <div className="grid md:grid-cols-3 gap-px bg-gray-200 border-b">
        {PLANS.map((plan) => (
          <div key={plan.id} className="bg-white px-4 md:px-6 py-5">
            <h2 className="text-sm font-medium text-gray-600">{plan.name}</h2>
            <p className="mt-1 mb-4 text-xl font-semibold tracking-tight">{plan.price}</p>
            <ul className="space-y-1.5 text-sm text-gray-700">
              {plan.features.map((f) => (
                <li key={f} className="flex items-start gap-2">
                  <Icon name="check" className="text-gray-700 mt-0.5" />
                  <span>{f}</span>
                </li>
              ))}
              {plan.missing.map((f) => (
                <li key={f} className="flex items-start gap-2 text-gray-400">
                  <Icon name="close" className="mt-0.5" />
                  <span>{f}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      {/* Org plan assignments */}
      <h2 className="section-title">Тарифы школ</h2>
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th>Школа</th>
              <th>Тариф</th>
              <th>Учителей</th>
              <th>Проверок/мес</th>
              <th>Действует до</th>
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
            ) : orgs.length === 0 ? (
              <tr>
                <td colSpan={6} className="table-empty">Школ пока нет</td>
              </tr>
            ) : (
              orgs.map((org) => (
                <tr key={org.id}>
                  <td className="font-medium text-gray-900">{org.name}</td>
                  <td>
                    {editOrg === org.id && editState ? (
                      <select
                        className="field !w-auto"
                        value={editState.plan}
                        onChange={(e) => setEditState({ ...editState, plan: e.target.value })}
                      >
                        <option value="standard">standard</option>
                        <option value="pro">pro</option>
                        <option value="enterprise">enterprise</option>
                      </select>
                    ) : (
                      <span className="text-gray-700">
                        {org.plan}
                      </span>
                    )}
                  </td>
                  <td className="text-gray-700">
                    {editOrg === org.id && editState ? (
                      <input
                        type="number"
                        min={1}
                        className="field !w-20"
                        value={editState.seats_limit}
                        onChange={(e) => setEditState({ ...editState, seats_limit: +e.target.value })}
                      />
                    ) : (
                      org.seats_limit
                    )}
                  </td>
                  <td className="text-gray-700">
                    {editOrg === org.id && editState ? (
                      <input
                        type="number"
                        min={0}
                        className="field !w-24"
                        value={editState.monthly_quota}
                        onChange={(e) => setEditState({ ...editState, monthly_quota: +e.target.value })}
                      />
                    ) : (
                      org.monthly_quota.toLocaleString("ru")
                    )}
                  </td>
                  <td className="text-gray-500 text-xs">
                    {editOrg === org.id && editState ? (
                      <input
                        type="date"
                        className="field !w-auto"
                        value={editState.valid_until}
                        onChange={(e) => setEditState({ ...editState, valid_until: e.target.value })}
                      />
                    ) : org.valid_until ? (
                      new Date(org.valid_until).toLocaleDateString("ru")
                    ) : (
                      <span className="text-gray-500">Без ограничений</span>
                    )}
                  </td>
                  <td>
                    {editOrg === org.id ? (
                      <div className="flex gap-2">
                        <button
                          onClick={() => saveEdit(org.id)}
                          disabled={saving}
                          className="btn btn-primary"
                        >
                          {saving ? "..." : "Сохранить"}
                        </button>
                        <button
                          onClick={() => { setEditOrg(null); setEditState(null); }}
                          className="link-danger"
                        >
                          Отмена
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => startEdit(org)}
                        className="link"
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
    </>
  );
}
