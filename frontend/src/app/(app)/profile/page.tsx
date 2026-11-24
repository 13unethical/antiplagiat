"use client";

import { useState, useEffect } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import { getUser, setAuth } from "@/lib/auth";

interface UserOut {
  id: string;
  email: string;
  full_name: string;
  role: string;
  org_id: string | null;
  status: string;
  personal_quota: number | null;
}

export default function ProfilePage() {
  const [fullName, setFullName] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [nameSaved, setNameSaved] = useState(false);
  const [pwSaved, setPwSaved] = useState(false);
  const [nameError, setNameError] = useState("");
  const [pwError, setPwError] = useState("");
  const [savingName, setSavingName] = useState(false);
  const [savingPw, setSavingPw] = useState(false);

  const user = getUser();

  useEffect(() => {
    if (user) setFullName(user.full_name);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function saveName(e: React.FormEvent) {
    e.preventDefault();
    if (!fullName.trim()) return;
    setSavingName(true);
    setNameError("");
    try {
      const updated = await apiFetch<UserOut>("/api/v1/auth/me", {
        method: "PATCH",
        body: JSON.stringify({ full_name: fullName.trim() }),
      });
      // Update localStorage user object
      const stored = localStorage.getItem("access_token");
      const refresh = localStorage.getItem("refresh_token");
      if (stored && refresh && user) {
        setAuth(stored, refresh, {
          id: updated.id,
          email: updated.email,
          full_name: updated.full_name,
          role: updated.role as "superadmin" | "school_admin" | "teacher",
          org_id: updated.org_id,
          status: updated.status,
        });
      }
      setNameSaved(true);
      setTimeout(() => setNameSaved(false), 2500);
    } catch (err) {
      setNameError(err instanceof ApiError ? err.message : "Ошибка сохранения");
    } finally {
      setSavingName(false);
    }
  }

  async function savePassword(e: React.FormEvent) {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setPwError("Пароли не совпадают");
      return;
    }
    if (newPassword.length < 8) {
      setPwError("Пароль должен быть не менее 8 символов");
      return;
    }
    setSavingPw(true);
    setPwError("");
    try {
      await apiFetch("/api/v1/auth/me", {
        method: "PATCH",
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPwSaved(true);
      setTimeout(() => setPwSaved(false), 2500);
    } catch (err) {
      setPwError(err instanceof ApiError ? err.message : "Ошибка сохранения");
    } finally {
      setSavingPw(false);
    }
  }

  return (
    <div className="p-8 max-w-lg">
      <h1 className="text-xl font-semibold mb-6">Профиль</h1>

      {/* Account info */}
      <div className="bg-white border rounded-xl p-5 mb-5 space-y-1">
        <p className="text-xs text-gray-400">Email</p>
        <p className="text-sm font-medium text-gray-800">{user?.email}</p>
        <p className="text-xs text-gray-400 mt-2">Роль</p>
        <p className="text-sm text-gray-700">
          {(({ teacher: "Учитель", school_admin: "Администратор", superadmin: "Суперадмин" } as Record<string, string>)[user?.role ?? ""]) ?? user?.role}
        </p>
      </div>

      {/* Change name */}
      <form onSubmit={saveName} className="bg-white border rounded-xl p-5 mb-5 space-y-3">
        <h2 className="font-medium text-sm">Имя</h2>
        <input
          className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          placeholder="Полное имя"
          required
        />
        {nameError && (
          <p className="text-sm text-red-600">{nameError}</p>
        )}
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={savingName || !fullName.trim()}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-40 font-medium"
          >
            {savingName ? "Сохранение..." : "Сохранить имя"}
          </button>
          {nameSaved && <span className="text-sm text-green-600">✓ Сохранено</span>}
        </div>
      </form>

      {/* Change password */}
      <form onSubmit={savePassword} className="bg-white border rounded-xl p-5 space-y-3">
        <h2 className="font-medium text-sm">Изменить пароль</h2>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Текущий пароль</label>
          <input
            type="password"
            className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            required
            autoComplete="current-password"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Новый пароль</label>
          <input
            type="password"
            className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Повторите пароль</label>
          <input
            type="password"
            className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            autoComplete="new-password"
          />
        </div>
        {pwError && <p className="text-sm text-red-600">{pwError}</p>}
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={savingPw}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-40 font-medium"
          >
            {savingPw ? "Сохранение..." : "Сменить пароль"}
          </button>
          {pwSaved && <span className="text-sm text-green-600">✓ Пароль изменён</span>}
        </div>
      </form>
    </div>
  );
}
