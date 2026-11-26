"use client";

import { useEffect, useState, useCallback } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import { Icon, PageHeader, Stats, Status } from "../../ui";

interface ModelVersion {
  id: string;
  model_type: string;
  version: string;
  description: string | null;
  is_active: boolean;
  metrics: Record<string, number | string>;
  created_at: string;
}

interface DatasetStats {
  human_written?: number;
  ai_generated?: number;
  machine_translated?: number;
  [key: string]: number | undefined;
}

export default function ModelsPage() {
  const [versions, setVersions] = useState<ModelVersion[]>([]);
  const [datasetStats, setDatasetStats] = useState<DatasetStats>({});
  const [loading, setLoading] = useState(true);
  const [activating, setActivating] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    model_type: "ai_detector",
    version: "",
    description: "",
    fpr: "",
    tpr_at_1: "",
    auroc: "",
    f1: "",
    dataset_size: "",
    languages: "",
  });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");

  const fetchData = useCallback(async () => {
    try {
      const [v, ds] = await Promise.all([
        apiFetch<ModelVersion[]>("/api/v1/admin/model-versions"),
        apiFetch<DatasetStats>("/api/v1/admin/dataset/stats"),
      ]);
      setVersions(v);
      setDatasetStats(ds);
    } catch {}
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  async function activate(id: string) {
    setActivating(id);
    try {
      await apiFetch(`/api/v1/admin/model-versions/${id}/activate`, { method: "PATCH" });
      await fetchData();
    } catch (e) {
      alert(e instanceof ApiError ? e.message : "Ошибка активации");
    } finally {
      setActivating(null);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!form.version.trim()) { setFormError("Укажите версию"); return; }
    setSaving(true);
    setFormError("");
    try {
      const metrics: Record<string, unknown> = {};
      if (form.fpr) metrics.fpr = parseFloat(form.fpr);
      if (form.tpr_at_1) metrics.tpr_at_1pct = parseFloat(form.tpr_at_1);
      if (form.auroc) metrics.auroc = parseFloat(form.auroc);
      if (form.f1) metrics.f1 = parseFloat(form.f1);
      if (form.dataset_size) metrics.dataset_size = parseInt(form.dataset_size);
      if (form.languages) metrics.languages = form.languages;

      await apiFetch("/api/v1/admin/model-versions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model_type: form.model_type,
          version: form.version.trim(),
          description: form.description.trim() || null,
          metrics,
        }),
      });
      setShowForm(false);
      setForm({ model_type: "ai_detector", version: "", description: "", fpr: "", tpr_at_1: "", auroc: "", f1: "", dataset_size: "", languages: "" });
      await fetchData();
    } catch (e) {
      setFormError(e instanceof ApiError ? e.message : "Ошибка");
    } finally {
      setSaving(false);
    }
  }

  const activeAi = versions.find((v) => v.model_type === "ai_detector" && v.is_active);
  const activeMt = versions.find((v) => v.model_type === "mt_detector" && v.is_active);
  const totalDataset = Object.values(datasetStats).reduce<number>((s, v) => s + (v ?? 0), 0);

  return (
    <>
      <PageHeader title="Модели детектора">
        <button onClick={() => setShowForm(!showForm)} className="btn btn-primary">
          <Icon name="plus" />
          Добавить версию
        </button>
      </PageHeader>

      <div className="grid md:grid-cols-2 gap-px bg-gray-200 border-b">
        <div className="bg-white px-4 md:px-6 py-4">
          <p className="text-xs text-gray-500">ИИ-детектор</p>
          <p className="mt-1.5 text-base font-semibold">{activeAi?.version ?? "Нет активной версии"}</p>
          {activeAi && (
            <p className="mt-0.5 text-xs text-gray-500">
              {[
                activeAi.description,
                activeAi.metrics.fpr !== undefined && `FPR ${((activeAi.metrics.fpr as number) * 100).toFixed(1)}%`,
                activeAi.metrics.tpr_at_1pct !== undefined && `TPR@1% ${((activeAi.metrics.tpr_at_1pct as number) * 100).toFixed(0)}%`,
              ].filter(Boolean).join(", ")}
            </p>
          )}
        </div>
        <div className="bg-white px-4 md:px-6 py-4">
          <p className="text-xs text-gray-500">Детектор машинного перевода</p>
          <p className="mt-1.5 text-base font-semibold">{activeMt?.version ?? "Нет активной версии"}</p>
          <p className="mt-0.5 text-xs text-gray-500">{activeMt ? activeMt.description : "используется heuristic-v0"}</p>
        </div>
      </div>

      {/* Add version form */}
      {showForm && (
        <div className="form-block">
          <h2 className="font-semibold text-base">Добавить версию модели</h2>
          <form onSubmit={handleCreate} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="field-label">Тип модели</label>
                <select
                  value={form.model_type}
                  onChange={(e) => setForm((f) => ({ ...f, model_type: e.target.value }))}
                  className="field"
                >
                  <option value="ai_detector">ИИ-детектор</option>
                  <option value="mt_detector">MT-детектор</option>
                </select>
              </div>
              <div>
                <label className="field-label">Версия</label>
                <input
                  value={form.version}
                  onChange={(e) => setForm((f) => ({ ...f, version: e.target.value }))}
                  placeholder="v0.4-xlmr-large"
                  className="field"
                />
              </div>
            </div>
            <div>
              <label className="field-label">Описание</label>
              <input
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                placeholder="XLM-RoBERTa large, аугментации NLLB"
                className="field"
              />
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {[
                { key: "fpr", label: "FPR (доля)" },
                { key: "tpr_at_1", label: "TPR при FPR=1%" },
                { key: "auroc", label: "AUROC" },
                { key: "f1", label: "F1" },
                { key: "dataset_size", label: "Размер датасета" },
                { key: "languages", label: "Языки" },
              ].map(({ key, label }) => (
                <div key={key}>
                  <label className="field-label">{label}</label>
                  <input
                    value={(form as Record<string, string>)[key]}
                    onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                    placeholder={key === "languages" ? "ru, uz" : "0.012"}
                    className="field"
                  />
                </div>
              ))}
            </div>
            {formError && <p className="text-xs text-red-600">{formError}</p>}
            <div className="flex gap-2 pt-1">
              <button
                type="submit"
                disabled={saving}
                className="btn btn-primary"
              >
                {saving ? "Сохранение..." : "Добавить"}
              </button>
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="btn btn-secondary"
              >
                Отмена
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="section-title">
        <h2>Датасет для дообучения</h2>
        <span className="text-xs font-normal text-gray-500">всего записей: {totalDataset}</span>
      </div>
      <Stats
        items={[
          { label: "Написано человеком", value: loading ? "—" : datasetStats.human_written ?? 0 },
          { label: "Написано ИИ", value: loading ? "—" : datasetStats.ai_generated ?? 0 },
          { label: "Машинный перевод", value: loading ? "—" : datasetStats.machine_translated ?? 0 },
        ]}
      />
      <p className="px-4 md:px-6 py-3 border-b text-xs text-gray-500">
        Записи добавляются вердиктом «Добавить в датасет» в разделе споров
      </p>

      <h2 className="section-title">Все версии</h2>
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th>Версия</th>
              <th>Тип</th>
              <th>FPR</th>
              <th>TPR@1%</th>
              <th>F1</th>
              <th>Датасет</th>
              <th>Добавлена</th>
              <th>Статус</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {loading || versions.length === 0 ? (
              <tr>
                <td colSpan={9} className="table-empty">
                  {loading ? "Загрузка..." : "Нет зарегистрированных версий. Сейчас работает эвристика"}
                </td>
              </tr>
            ) : (
              versions.map((v) => (
                <tr key={v.id}>
                  <td>
                    <p className="font-medium text-gray-900">{v.version}</p>
                    {v.description && <p className="text-xs text-gray-500">{v.description}</p>}
                  </td>
                  <td className="text-gray-700 whitespace-nowrap">{v.model_type === "ai_detector" ? "ИИ-детектор" : "Машинный перевод"}</td>
                  <td>{v.metrics.fpr !== undefined ? `${((v.metrics.fpr as number) * 100).toFixed(1)}%` : "—"}</td>
                  <td>{v.metrics.tpr_at_1pct !== undefined ? `${((v.metrics.tpr_at_1pct as number) * 100).toFixed(0)}%` : "—"}</td>
                  <td>{v.metrics.f1 !== undefined ? `${((v.metrics.f1 as number) * 100).toFixed(0)}%` : "—"}</td>
                  <td>{v.metrics.dataset_size !== undefined ? (v.metrics.dataset_size as number).toLocaleString("ru") : "—"}</td>
                  <td className="text-gray-500 text-xs whitespace-nowrap">{new Date(v.created_at).toLocaleDateString("ru")}</td>
                  <td>
                    <Status tone={v.is_active ? "green" : "gray"}>{v.is_active ? "Активна" : "Не активна"}</Status>
                  </td>
                  <td>
                    {!v.is_active && (
                      <button onClick={() => activate(v.id)} disabled={activating === v.id} className="link">
                        {activating === v.id ? "Запуск..." : "Развернуть"}
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
