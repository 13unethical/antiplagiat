"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import { getUser } from "@/lib/auth";

interface OrgSettings {
  default_exclude_quotes: boolean;
  default_exclude_bibliography: boolean;
  default_save_to_repository: boolean;
  default_min_match_words: number;
  require_student_name: boolean;
  require_group: boolean;
  report_footer: string;
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<OrgSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const isTeacher = getUser()?.role === "teacher";

  useEffect(() => {
    apiFetch<OrgSettings>("/api/v1/org/settings")
      .then(setSettings)
      .catch(() => setError("Не удалось загрузить настройки"))
      .finally(() => setLoading(false));
  }, []);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!settings) return;
    setSaving(true);
    setError("");
    try {
      const updated = await apiFetch<OrgSettings>("/api/v1/org/settings", {
        method: "PATCH",
        body: JSON.stringify({
          default_exclude_quotes: settings.default_exclude_quotes,
          default_exclude_bibliography: settings.default_exclude_bibliography,
          default_save_to_repository: settings.default_save_to_repository,
          default_min_match_words: settings.default_min_match_words,
          require_student_name: settings.require_student_name,
          require_group: settings.require_group,
          report_footer: settings.report_footer,
        }),
      });
      setSettings(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ошибка сохранения");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="p-8 max-w-xl">
        <h1 className="text-xl font-semibold mb-6">Настройки</h1>
        <p className="text-sm text-gray-400">Загрузка...</p>
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="p-8 max-w-xl">
        <h1 className="text-xl font-semibold mb-6">Настройки</h1>
        <p className="text-sm text-red-500">{error || "Не удалось загрузить настройки"}</p>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-xl">
      <h1 className="text-xl font-semibold mb-6">Настройки</h1>

      {isTeacher && (
        <div className="bg-blue-50 border border-blue-200 text-blue-700 text-sm px-4 py-3 rounded-xl mb-5">
          Настройки по умолчанию задаются администратором школы. Вы можете изменить параметры при каждой проверке отдельно.
        </div>
      )}

      <form onSubmit={isTeacher ? (e) => e.preventDefault() : save} className="space-y-5">
        <fieldset disabled={isTeacher} className="contents">
        {/* Настройки проверки */}
        <div className="bg-white border rounded-xl p-5 space-y-4">
          <h2 className="font-medium text-sm">Настройки проверки по умолчанию</h2>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1.5">
              Минимальная длина совпадения (слов)
            </label>
            <input
              type="number"
              min={3}
              max={30}
              className="w-32 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={settings.default_min_match_words}
              onChange={(e) =>
                setSettings({ ...settings, default_min_match_words: +e.target.value })
              }
            />
            <p className="text-xs text-gray-400 mt-1">
              Совпадения короче не учитываются. По умолчанию: 8 слов.
            </p>
          </div>

          <div className="space-y-2.5">
            <label className="flex items-center gap-2.5 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.default_exclude_quotes}
                onChange={(e) =>
                  setSettings({ ...settings, default_exclude_quotes: e.target.checked })
                }
                className="accent-blue-600"
              />
              <span className="text-sm text-gray-700">Исключать цитаты в кавычках «» и ""</span>
            </label>
            <label className="flex items-center gap-2.5 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.default_exclude_bibliography}
                onChange={(e) =>
                  setSettings({ ...settings, default_exclude_bibliography: e.target.checked })
                }
                className="accent-blue-600"
              />
              <span className="text-sm text-gray-700">Исключать список литературы</span>
            </label>
            <label className="flex items-center gap-2.5 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.default_save_to_repository}
                onChange={(e) =>
                  setSettings({ ...settings, default_save_to_repository: e.target.checked })
                }
                className="accent-blue-600"
              />
              <span className="text-sm text-gray-700">
                Сохранять работы в репозиторий школы по умолчанию
              </span>
            </label>
          </div>
        </div>

        {/* Обязательные поля */}
        <div className="bg-white border rounded-xl p-5 space-y-3">
          <h2 className="font-medium text-sm">Обязательные поля при проверке</h2>
          <label className="flex items-center gap-2.5 cursor-pointer">
            <input
              type="checkbox"
              checked={settings.require_student_name}
              onChange={(e) =>
                setSettings({ ...settings, require_student_name: e.target.checked })
              }
              className="accent-blue-600"
            />
            <span className="text-sm text-gray-700">Требовать ФИО студента</span>
          </label>
          <label className="flex items-center gap-2.5 cursor-pointer">
            <input
              type="checkbox"
              checked={settings.require_group}
              onChange={(e) =>
                setSettings({ ...settings, require_group: e.target.checked })
              }
              className="accent-blue-600"
            />
            <span className="text-sm text-gray-700">Требовать указание группы / класса</span>
          </label>
        </div>

        {/* Footer отчёта */}
        <div className="bg-white border rounded-xl p-5">
          <h2 className="font-medium text-sm mb-3">Подпись в отчёте</h2>
          <textarea
            rows={3}
            className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            placeholder="Текст в подвале PDF/DOCX отчёта..."
            value={settings.report_footer}
            onChange={(e) => setSettings({ ...settings, report_footer: e.target.value })}
          />
        </div>

        {/* Уведомления (UI-only) */}
        <div className="bg-white border rounded-xl p-5 space-y-3 opacity-60">
          <h2 className="font-medium text-sm">Уведомления</h2>
          <p className="text-xs text-gray-400">Email-уведомления · скоро</p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2 rounded-lg">
            {error}
          </div>
        )}

        {!isTeacher && (
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
        )}
        </fieldset>
      </form>
    </div>
  );
}
