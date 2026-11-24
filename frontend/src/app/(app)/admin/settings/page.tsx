"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";

interface OrgSettings {
  default_exclude_quotes: boolean;
  default_exclude_bibliography: boolean;
  default_save_to_repository: boolean;
  default_min_match_words: number;
  require_student_name: boolean;
  require_group: boolean;
  report_footer: string;
}

export default function AdminSettingsPage() {
  const [form, setForm] = useState<OrgSettings>({
    default_exclude_quotes: true,
    default_exclude_bibliography: true,
    default_save_to_repository: false,
    default_min_match_words: 8,
    require_student_name: false,
    require_group: false,
    report_footer: "",
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<OrgSettings>("/api/v1/org/settings")
      .then((data) => setForm(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await apiFetch("/api/v1/org/settings", {
        method: "PATCH",
        body: JSON.stringify(form),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ошибка сохранения");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="p-8 text-sm text-gray-400">Загрузка...</div>;

  return (
    <div className="p-8 max-w-xl">
      <h1 className="text-xl font-semibold mb-6">Настройки по умолчанию</h1>

      <form onSubmit={save} className="space-y-5">
        <div className="bg-white border rounded-xl p-5 space-y-4">
          <h2 className="font-medium text-sm">Настройки проверки по умолчанию для учителей</h2>
          <p className="text-xs text-gray-400">Учитель может изменить эти значения при каждой проверке.</p>

          <div className="space-y-2.5">
            <label className="flex items-center gap-2.5 cursor-pointer">
              <input
                type="checkbox"
                checked={form.default_exclude_quotes}
                onChange={(e) => setForm({ ...form, default_exclude_quotes: e.target.checked })}
                className="accent-blue-600"
              />
              <span className="text-sm text-gray-700">Исключать цитаты по умолчанию</span>
            </label>
            <label className="flex items-center gap-2.5 cursor-pointer">
              <input
                type="checkbox"
                checked={form.default_exclude_bibliography}
                onChange={(e) => setForm({ ...form, default_exclude_bibliography: e.target.checked })}
                className="accent-blue-600"
              />
              <span className="text-sm text-gray-700">Исключать список литературы по умолчанию</span>
            </label>
            <label className="flex items-center gap-2.5 cursor-pointer">
              <input
                type="checkbox"
                checked={form.default_save_to_repository}
                onChange={(e) => setForm({ ...form, default_save_to_repository: e.target.checked })}
                className="accent-blue-600"
              />
              <span className="text-sm text-gray-700">Сохранять в репозиторий по умолчанию</span>
            </label>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">
              Минимальная длина совпадения (слов)
            </label>
            <input
              type="number"
              min={3}
              max={30}
              className="w-32 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={form.default_min_match_words}
              onChange={(e) => setForm({ ...form, default_min_match_words: +e.target.value })}
            />
          </div>
        </div>

        <div className="bg-white border rounded-xl p-5 space-y-4">
          <h2 className="font-medium text-sm">Обязательные поля</h2>
          <div className="space-y-2">
            <label className="flex items-center gap-2.5 cursor-pointer">
              <input
                type="checkbox"
                checked={form.require_student_name}
                onChange={(e) => setForm({ ...form, require_student_name: e.target.checked })}
                className="accent-blue-600"
              />
              <span className="text-sm text-gray-700">Требовать ФИО студента</span>
            </label>
            <label className="flex items-center gap-2.5 cursor-pointer">
              <input
                type="checkbox"
                checked={form.require_group}
                onChange={(e) => setForm({ ...form, require_group: e.target.checked })}
                className="accent-blue-600"
              />
              <span className="text-sm text-gray-700">Требовать группу/класс</span>
            </label>
          </div>
        </div>

        <div className="bg-white border rounded-xl p-5 space-y-3">
          <h2 className="font-medium text-sm">Нижний колонтитул отчёта</h2>
          <input
            className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Школа №1 г. Ташкент"
            value={form.report_footer}
            onChange={(e) => setForm({ ...form, report_footer: e.target.value })}
          />
          <p className="text-xs text-gray-400">Отображается в PDF-отчётах.</p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2 rounded-lg">
            {error}
          </div>
        )}

        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={saving}
            className="bg-blue-600 text-white px-5 py-2 rounded-lg text-sm hover:bg-blue-700 font-medium disabled:opacity-40"
          >
            {saving ? "Сохранение..." : "Сохранить"}
          </button>
          {saved && <span className="text-sm text-green-600">✓ Сохранено</span>}
        </div>
      </form>
    </div>
  );
}
