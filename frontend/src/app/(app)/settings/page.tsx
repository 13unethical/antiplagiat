"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import { getUser, setAuth } from "@/lib/auth";
import { PageHeader } from "../ui";

interface UserOut {
  id: string;
  email: string;
  full_name: string;
  role: string;
  org_id: string | null;
  status: string;
}

interface OrgSettings {
  default_exclude_quotes: boolean;
  default_exclude_bibliography: boolean;
  default_save_to_repository: boolean;
  default_min_match_words: number;
  require_student_name: boolean;
  require_group: boolean;
  report_footer: string;
}

const ROLE_LABELS: Record<string, string> = {
  teacher: "Учитель",
  school_admin: "Администратор",
  superadmin: "Суперадмин",
};

const inputCls =
  "w-full h-9 border border-gray-300 rounded-lg px-3 text-sm bg-white transition-colors hover:border-gray-400/60 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200 disabled:bg-gray-50 disabled:text-gray-600";
const labelCls = "block text-xs font-medium text-gray-600 mb-1.5";
const cardCls = "bg-white border rounded-xl";
const checkCls = "flex items-start gap-2.5 cursor-pointer text-sm text-gray-800 [&>input]:mt-0.5";

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="text-base font-semibold">{title}</h2>
      {hint && <p className="text-sm text-gray-500 mt-1">{hint}</p>}
      <div className="mt-3 space-y-3">{children}</div>
    </section>
  );
}

function Saved({ show, text = "Сохранено" }: { show: boolean; text?: string }) {
  return show ? <span className="text-sm text-green-700" role="status">{text}</span> : null;
}

export default function SettingsPage() {
  const user = getUser();
  const role = user?.role;
  const isTeacher = role === "teacher";

  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [savedName, setSavedName] = useState(user?.full_name ?? "");
  const [nameState, setNameState] = useState<"idle" | "saving" | "saved">("idle");
  const [nameError, setNameError] = useState("");

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [pwState, setPwState] = useState<"idle" | "saving" | "saved">("idle");
  const [pwError, setPwError] = useState("");

  const [settings, setSettings] = useState<OrgSettings | null>(null);
  const [settingsError, setSettingsError] = useState("");
  const [settingsState, setSettingsState] = useState<"idle" | "saving" | "saved">("idle");

  useEffect(() => {
    if (role === "superadmin") return;
    apiFetch<OrgSettings>("/api/v1/org/settings")
      .then(setSettings)
      .catch(() => setSettingsError("Не удалось загрузить настройки"));
  }, [role]);

  function flash(set: (s: "idle" | "saved") => void) {
    set("saved");
    setTimeout(() => set("idle"), 2500);
  }

  async function saveName(e: React.FormEvent) {
    e.preventDefault();
    const name = fullName.trim();
    if (!name || name === savedName) return;
    setNameState("saving");
    setNameError("");
    try {
      const updated = await apiFetch<UserOut>("/api/v1/auth/me", {
        method: "PATCH",
        body: JSON.stringify({ full_name: name }),
      });
      const access = localStorage.getItem("access_token");
      const refresh = localStorage.getItem("refresh_token");
      if (access && refresh) {
        setAuth(access, refresh, {
          id: updated.id,
          email: updated.email,
          full_name: updated.full_name,
          role: updated.role as "superadmin" | "school_admin" | "teacher",
          org_id: updated.org_id,
          status: updated.status,
        });
      }
      setSavedName(updated.full_name);
      setFullName(updated.full_name);
      flash(setNameState);
    } catch (err) {
      setNameError(err instanceof ApiError ? err.message : "Не удалось сохранить");
      setNameState("idle");
    }
  }

  async function savePassword(e: React.FormEvent) {
    e.preventDefault();
    if (newPassword.length < 8) return setPwError("Пароль должен быть не короче 8 символов");
    if (newPassword !== confirmPassword) return setPwError("Пароли не совпадают");
    setPwState("saving");
    setPwError("");
    try {
      await apiFetch("/api/v1/auth/me", {
        method: "PATCH",
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      flash(setPwState);
    } catch (err) {
      setPwError(err instanceof ApiError ? err.message : "Не удалось сменить пароль");
      setPwState("idle");
    }
  }

  async function saveSettings(e: React.FormEvent) {
    e.preventDefault();
    if (!settings || isTeacher) return;
    setSettingsState("saving");
    setSettingsError("");
    try {
      const updated = await apiFetch<OrgSettings>("/api/v1/org/settings", {
        method: "PATCH",
        body: JSON.stringify(settings),
      });
      setSettings(updated);
      flash(setSettingsState);
    } catch (err) {
      setSettingsError(err instanceof ApiError ? err.message : "Не удалось сохранить");
      setSettingsState("idle");
    }
  }

  const patch = (p: Partial<OrgSettings>) => setSettings((s) => (s ? { ...s, ...p } : s));

  return (
    <>
      <PageHeader title="Настройки" />
      <div className="p-4 md:p-8 max-w-2xl mx-auto space-y-10">
        <Section title="Профиль">
          <form onSubmit={saveName} className={`${cardCls} divide-y`}>
            <div className="px-5 py-3 flex items-center justify-between gap-4 text-sm">
              <span className="text-gray-600">Email</span>
              <span className="text-gray-900 truncate">{user?.email}</span>
            </div>
            <div className="px-5 py-3 flex items-center justify-between gap-4 text-sm">
              <span className="text-gray-600">Роль</span>
              <span className="text-gray-900">{ROLE_LABELS[role ?? ""] ?? role}</span>
            </div>
            <div className="px-5 py-4">
              <label htmlFor="full-name" className={labelCls}>Имя</label>
              <div className="flex gap-2">
                <input
                  id="full-name"
                  className={inputCls}
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Полное имя"
                  autoComplete="name"
                  required
                />
                <button
                  type="submit"
                  disabled={nameState === "saving" || !fullName.trim() || fullName.trim() === savedName}
                  className="btn btn-secondary h-9"
                >
                  {nameState === "saving" ? "Сохранение..." : "Сохранить"}
                </button>
              </div>
              {nameError && <p className="mt-2 text-sm text-red-700">{nameError}</p>}
              <div className="mt-2 empty:hidden"><Saved show={nameState === "saved"} /></div>
            </div>
          </form>

          <form onSubmit={savePassword} className={`${cardCls} p-5`}>
            <p className="text-sm font-medium">Пароль</p>
            <div className="mt-3 grid sm:grid-cols-3 gap-3">
              <div>
                <label htmlFor="pw-current" className={labelCls}>Текущий</label>
                <input
                  id="pw-current"
                  type="password"
                  className={inputCls}
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  autoComplete="current-password"
                  required
                />
              </div>
              <div>
                <label htmlFor="pw-new" className={labelCls}>Новый</label>
                <input
                  id="pw-new"
                  type="password"
                  className={inputCls}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  autoComplete="new-password"
                  required
                />
              </div>
              <div>
                <label htmlFor="pw-confirm" className={labelCls}>Ещё раз</label>
                <input
                  id="pw-confirm"
                  type="password"
                  className={inputCls}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  autoComplete="new-password"
                  required
                />
              </div>
            </div>
            <p className="mt-2 text-xs text-gray-500">Не короче 8 символов</p>
            {pwError && <p className="mt-2 text-sm text-red-700">{pwError}</p>}
            <div className="mt-4 flex items-center gap-3">
              <button
                type="submit"
                disabled={pwState === "saving" || !currentPassword || !newPassword || !confirmPassword}
                className="btn btn-secondary"
              >
                {pwState === "saving" ? "Сохранение..." : "Сменить пароль"}
              </button>
              <Saved show={pwState === "saved"} text="Пароль изменён" />
            </div>
          </form>
        </Section>

        {role !== "superadmin" && (
          <Section
            title="Проверка работ"
            hint={
              isTeacher
                ? "Значения по умолчанию задаёт администратор школы. В каждой проверке их можно поменять."
                : "Значения по умолчанию для всех учителей школы. В каждой проверке их можно поменять."
            }
          >
            {!settings ? (
              <p className={`text-sm ${settingsError ? "text-red-700" : "text-gray-500"}`}>
                {settingsError || "Загрузка..."}
              </p>
            ) : (
              <form onSubmit={saveSettings}>
                <fieldset disabled={isTeacher} className={`${cardCls} divide-y`}>
                  <div className="p-5 space-y-3">
                    <p className="text-sm font-medium">Исключения</p>
                    <label className={checkCls}>
                      <input
                        type="checkbox"
                        checked={settings.default_exclude_quotes}
                        onChange={(e) => patch({ default_exclude_quotes: e.target.checked })}
                      />
                      {'Исключать цитаты в кавычках «» и ""'}
                    </label>
                    <label className={checkCls}>
                      <input
                        type="checkbox"
                        checked={settings.default_exclude_bibliography}
                        onChange={(e) => patch({ default_exclude_bibliography: e.target.checked })}
                      />
                      Исключать список литературы
                    </label>
                    <label className={checkCls}>
                      <input
                        type="checkbox"
                        checked={settings.default_save_to_repository}
                        onChange={(e) => patch({ default_save_to_repository: e.target.checked })}
                      />
                      Сохранять работы в репозиторий школы
                    </label>
                    <div className="pt-1">
                      <label htmlFor="min-words" className={labelCls}>Учитывать совпадения от, слов</label>
                      <input
                        id="min-words"
                        type="number"
                        min={3}
                        max={30}
                        className={`${inputCls} !w-24`}
                        value={settings.default_min_match_words}
                        onChange={(e) => patch({ default_min_match_words: +e.target.value })}
                      />
                    </div>
                  </div>

                  <div className="p-5 space-y-3">
                    <p className="text-sm font-medium">Обязательные поля</p>
                    <label className={checkCls}>
                      <input
                        type="checkbox"
                        checked={settings.require_student_name}
                        onChange={(e) => patch({ require_student_name: e.target.checked })}
                      />
                      ФИО студента
                    </label>
                    <label className={checkCls}>
                      <input
                        type="checkbox"
                        checked={settings.require_group}
                        onChange={(e) => patch({ require_group: e.target.checked })}
                      />
                      Группа / класс
                    </label>
                  </div>

                  <div className="p-5">
                    <label htmlFor="footer" className="block text-sm font-medium mb-3">Подпись в отчёте</label>
                    <textarea
                      id="footer"
                      rows={2}
                      className={`${inputCls} h-auto py-2 resize-none`}
                      placeholder="Школа №1, г. Ташкент"
                      value={settings.report_footer}
                      onChange={(e) => patch({ report_footer: e.target.value })}
                    />
                    <p className="mt-1.5 text-xs text-gray-500">Внизу PDF-отчёта</p>
                  </div>
                </fieldset>

                {settingsError && <p className="mt-3 text-sm text-red-700">{settingsError}</p>}
                {!isTeacher && (
                  <div className="mt-4 flex items-center gap-3">
                    <button type="submit" disabled={settingsState === "saving"} className="btn btn-primary">
                      {settingsState === "saving" ? "Сохранение..." : "Сохранить"}
                    </button>
                    <Saved show={settingsState === "saved"} />
                  </div>
                )}
              </form>
            )}
          </Section>
        )}
      </div>
    </>
  );
}
