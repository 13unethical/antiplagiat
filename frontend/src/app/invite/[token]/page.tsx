"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiFetch, ApiError } from "@/lib/api";

interface InvitationInfo {
  id: string;
  email: string;
  role: string;
  status: string;
  expires_at: string;
}

const roleLabel: Record<string, string> = {
  school_admin: "Администратор школы",
  teacher: "Учитель",
};

export default function InvitePage() {
  const { token } = useParams<{ token: string }>();
  const router = useRouter();

  const [invitation, setInvitation] = useState<InvitationInfo | null>(null);
  const [fetchError, setFetchError] = useState("");

  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [submitError, setSubmitError] = useState("");
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token) return;
    apiFetch<InvitationInfo>(`/api/v1/invitations/${token}`)
      .then(setInvitation)
      .catch((err) => setFetchError(err instanceof ApiError ? err.message : "Ошибка"));
  }, [token]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== password2) {
      setSubmitError("Пароли не совпадают");
      return;
    }
    if (password.length < 8) {
      setSubmitError("Пароль должен быть минимум 8 символов");
      return;
    }
    setSubmitError("");
    setLoading(true);
    try {
      await apiFetch(`/api/v1/invitations/${token}/accept`, {
        method: "POST",
        body: JSON.stringify({ full_name: fullName, password }),
      });
      setSuccess(true);
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Ошибка");
    } finally {
      setLoading(false);
    }
  }

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="bg-white p-8 rounded-2xl shadow-sm border w-full max-w-sm text-center">
          <div className="text-4xl mb-3">✓</div>
          <h2 className="text-xl font-bold mb-2">Аккаунт создан!</h2>
          <p className="text-gray-500 text-sm mb-6">Теперь вы можете войти в систему.</p>
          <button
            onClick={() => router.push("/login")}
            className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 font-medium text-sm"
          >
            Войти
          </button>
        </div>
      </div>
    );
  }

  if (fetchError) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="bg-white p-8 rounded-2xl shadow-sm border w-full max-w-sm text-center">
          <div className="text-4xl mb-3">✗</div>
          <h2 className="text-xl font-bold mb-2 text-red-600">Ссылка недействительна</h2>
          <p className="text-gray-500 text-sm">{fetchError}</p>
        </div>
      </div>
    );
  }

  if (!invitation) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-400">Загрузка...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="bg-white p-8 rounded-2xl shadow-sm border w-full max-w-sm">
        <h1 className="text-2xl font-bold mb-1">Принять приглашение</h1>
        <p className="text-sm text-gray-500 mb-1">
          Роль: <span className="font-medium text-gray-700">{roleLabel[invitation.role] ?? invitation.role}</span>
        </p>
        <p className="text-sm text-gray-500 mb-6">
          Email: <span className="font-medium text-gray-700">{invitation.email}</span>
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Ваше имя</label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Иванов Иван Иванович"
              required
              autoFocus
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Пароль</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Минимум 8 символов"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Повторите пароль</label>
            <input
              type="password"
              value={password2}
              onChange={(e) => setPassword2(e.target.value)}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            />
          </div>

          {submitError && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2 rounded-lg">
              {submitError}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium text-sm transition-colors"
          >
            {loading ? "Создание аккаунта..." : "Создать аккаунт"}
          </button>
        </form>
      </div>
    </div>
  );
}
