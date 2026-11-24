"use client";

import { useEffect, useState, useCallback } from "react";
import { apiFetch, ApiError } from "@/lib/api";

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
    <div className="p-8 max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Модели детектора</h1>
          <p className="text-sm text-gray-500 mt-0.5">Версии ИИ-детектора и детектора машинного перевода</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="text-sm bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
        >
          + Добавить версию
        </button>
      </div>

      {/* Active versions summary */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
          <p className="text-xs text-blue-500 font-medium uppercase tracking-wide">ИИ-детектор</p>
          {activeAi ? (
            <>
              <p className="font-semibold text-blue-900 mt-1">{activeAi.version}</p>
              <p className="text-xs text-blue-600 mt-0.5">{activeAi.description || "—"}</p>
              {activeAi.metrics.fpr !== undefined && (
                <p className="text-xs text-blue-500 mt-1">
                  FPR: {((activeAi.metrics.fpr as number) * 100).toFixed(1)}%
                  {activeAi.metrics.tpr_at_1pct !== undefined && ` · TPR@1%: ${((activeAi.metrics.tpr_at_1pct as number) * 100).toFixed(0)}%`}
                </p>
              )}
            </>
          ) : (
            <p className="text-sm text-blue-400 mt-1">Нет активной версии</p>
          )}
        </div>
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
          <p className="text-xs text-amber-500 font-medium uppercase tracking-wide">MT-детектор</p>
          {activeMt ? (
            <>
              <p className="font-semibold text-amber-900 mt-1">{activeMt.version}</p>
              <p className="text-xs text-amber-600 mt-0.5">{activeMt.description || "—"}</p>
            </>
          ) : (
            <p className="text-sm text-amber-400 mt-1">Нет активной версии · используется heuristic-v0</p>
          )}
        </div>
      </div>

      {/* Dataset stats */}
      <div className="bg-white border rounded-xl p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-medium text-sm">Датасет для дообучения</h2>
          <span className="text-xs text-gray-400">{totalDataset} записей всего</span>
        </div>
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: "human_written", display: "Человек", color: "text-green-700 bg-green-50" },
            { label: "ai_generated", display: "ИИ", color: "text-orange-700 bg-orange-50" },
            { label: "machine_translated", display: "Маш. перевод", color: "text-amber-700 bg-amber-50" },
          ].map(({ label, display, color }) => (
            <div key={label} className={`rounded-lg p-3 text-center ${color}`}>
              <p className="text-2xl font-bold">{loading ? "—" : (datasetStats[label] ?? 0)}</p>
              <p className="text-xs mt-0.5">{display}</p>
            </div>
          ))}
        </div>
        <p className="text-xs text-gray-400 mt-3">
          Записи добавляются автоматически при вердикте «added_to_dataset» в разделе споров.
        </p>
      </div>

      {/* Add version form */}
      {showForm && (
        <div className="bg-white border rounded-xl p-5">
          <h2 className="font-medium mb-4">Добавить версию модели</h2>
          <form onSubmit={handleCreate} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Тип модели</label>
                <select
                  value={form.model_type}
                  onChange={(e) => setForm((f) => ({ ...f, model_type: e.target.value }))}
                  className="w-full border rounded-lg px-3 py-2 text-sm"
                >
                  <option value="ai_detector">ИИ-детектор</option>
                  <option value="mt_detector">MT-детектор</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Версия</label>
                <input
                  value={form.version}
                  onChange={(e) => setForm((f) => ({ ...f, version: e.target.value }))}
                  placeholder="v0.4-xlmr-large"
                  className="w-full border rounded-lg px-3 py-2 text-sm"
                />
              </div>
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Описание</label>
              <input
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                placeholder="XLM-RoBERTa large, аугментации NLLB"
                className="w-full border rounded-lg px-3 py-2 text-sm"
              />
            </div>
            <div className="grid grid-cols-3 gap-3">
              {[
                { key: "fpr", label: "FPR (доля)" },
                { key: "tpr_at_1", label: "TPR при FPR=1%" },
                { key: "auroc", label: "AUROC" },
                { key: "f1", label: "F1" },
                { key: "dataset_size", label: "Размер датасета" },
                { key: "languages", label: "Языки" },
              ].map(({ key, label }) => (
                <div key={key}>
                  <label className="text-xs text-gray-500 mb-1 block">{label}</label>
                  <input
                    value={(form as Record<string, string>)[key]}
                    onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                    placeholder={key === "languages" ? "ru, uz" : "0.012"}
                    className="w-full border rounded-lg px-3 py-2 text-sm"
                  />
                </div>
              ))}
            </div>
            {formError && <p className="text-xs text-red-600">{formError}</p>}
            <div className="flex gap-2 pt-1">
              <button
                type="submit"
                disabled={saving}
                className="text-sm bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-40"
              >
                {saving ? "Сохранение..." : "Добавить"}
              </button>
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="text-sm text-gray-500 hover:underline px-4 py-2"
              >
                Отмена
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Versions list */}
      <div>
        <h2 className="font-medium text-sm mb-3">Все версии</h2>
        {loading ? (
          <p className="text-sm text-gray-400">Загрузка...</p>
        ) : versions.length === 0 ? (
          <div className="bg-white border rounded-xl p-6 text-center">
            <p className="text-sm text-gray-400">Нет зарегистрированных версий. Текущая модель — stub heuristic.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {versions.map((v) => (
              <div
                key={v.id}
                className={`bg-white border rounded-xl p-5 ${v.is_active ? "border-blue-300" : ""}`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-semibold text-gray-900">{v.version}</h3>
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        v.model_type === "ai_detector"
                          ? "bg-blue-100 text-blue-700"
                          : "bg-amber-100 text-amber-700"
                      }`}>
                        {v.model_type === "ai_detector" ? "ИИ-детектор" : "MT-детектор"}
                      </span>
                      {v.is_active && (
                        <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
                          Активна
                        </span>
                      )}
                    </div>
                    {v.description && (
                      <p className="text-xs text-gray-500 mt-0.5">{v.description}</p>
                    )}
                    <p className="text-xs text-gray-400 mt-0.5">
                      {new Date(v.created_at).toLocaleDateString("ru", { day: "2-digit", month: "2-digit", year: "numeric" })}
                    </p>
                  </div>
                  {!v.is_active && (
                    <button
                      onClick={() => activate(v.id)}
                      disabled={activating === v.id}
                      className="text-xs border px-3 py-1.5 rounded-lg text-gray-600 hover:bg-gray-50 shrink-0 disabled:opacity-40"
                    >
                      {activating === v.id ? "..." : "Развернуть"}
                    </button>
                  )}
                </div>

                {Object.keys(v.metrics).length > 0 && (
                  <div className="grid grid-cols-4 gap-2 mt-4">
                    {v.metrics.fpr !== undefined && (
                      <div className="bg-gray-50 rounded-lg p-2.5 text-center">
                        <p className={`text-base font-bold ${(v.metrics.fpr as number) < 0.02 ? "text-green-600" : "text-yellow-600"}`}>
                          {((v.metrics.fpr as number) * 100).toFixed(1)}%
                        </p>
                        <p className="text-xs text-gray-500">FPR</p>
                      </div>
                    )}
                    {v.metrics.tpr_at_1pct !== undefined && (
                      <div className="bg-gray-50 rounded-lg p-2.5 text-center">
                        <p className="text-base font-bold text-gray-800">
                          {((v.metrics.tpr_at_1pct as number) * 100).toFixed(0)}%
                        </p>
                        <p className="text-xs text-gray-500">TPR@1%</p>
                      </div>
                    )}
                    {v.metrics.f1 !== undefined && (
                      <div className="bg-gray-50 rounded-lg p-2.5 text-center">
                        <p className="text-base font-bold text-gray-800">
                          {((v.metrics.f1 as number) * 100).toFixed(0)}%
                        </p>
                        <p className="text-xs text-gray-500">F1</p>
                      </div>
                    )}
                    {v.metrics.dataset_size !== undefined && (
                      <div className="bg-gray-50 rounded-lg p-2.5 text-center">
                        <p className="text-base font-bold text-gray-800">
                          {(v.metrics.dataset_size as number).toLocaleString()}
                        </p>
                        <p className="text-xs text-gray-500">Датасет</p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
