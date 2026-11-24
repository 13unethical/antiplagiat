"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { getUser, clearAuth } from "@/lib/auth";
import type { AuthUser } from "@/lib/auth";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function stopImpersonation() {
  const originalToken = localStorage.getItem("impersonation_original_token");
  const originalUser = localStorage.getItem("impersonation_original_user");
  if (originalToken) localStorage.setItem("access_token", originalToken);
  if (originalUser) localStorage.setItem("user", originalUser);
  localStorage.removeItem("impersonation_original_token");
  localStorage.removeItem("impersonation_original_user");
  localStorage.removeItem("impersonation_target_name");
  localStorage.removeItem("impersonation_target_email");
  window.location.href = "/super/schools";
}

function ImpersonationBanner() {
  const [name, setName] = useState<string | null>(null);

  useEffect(() => {
    setName(localStorage.getItem("impersonation_target_name"));
  }, []);

  if (!name) return null;

  return (
    <div className="fixed top-0 left-0 right-0 z-50 bg-purple-600 text-white text-xs px-4 py-2 flex items-center justify-between">
      <span>Вы вошли от имени: <strong>{name}</strong></span>
      <button onClick={stopImpersonation} className="underline hover:no-underline ml-4">
        Вернуться к суперадмину
      </button>
    </div>
  );
}

interface PickerUser { id: string; email: string; full_name: string; role: string; status: string; }

function RoleSwitcher({ currentRole }: { currentRole: AuthUser["role"] }) {
  const [pickerRole, setPickerRole] = useState<"school_admin" | "teacher" | null>(null);
  const [pickerUsers, setPickerUsers] = useState<PickerUser[]>([]);
  const [loading, setLoading] = useState(false);
  const isImpersonating = typeof window !== "undefined" &&
    !!localStorage.getItem("impersonation_original_token");

  const roles: { key: AuthUser["role"]; label: string }[] = [
    { key: "superadmin", label: "Супер" },
    { key: "school_admin", label: "Админ" },
    { key: "teacher", label: "Учитель" },
  ];

  async function handleClick(role: AuthUser["role"]) {
    if (role === currentRole) return;

    // Go back to superadmin
    if (role === "superadmin") {
      if (isImpersonating) stopImpersonation();
      return;
    }

    // Switch from impersonated role to another — not allowed
    if (currentRole !== "superadmin") return;

    // Superadmin → open picker for selected role
    if (pickerRole === role) { setPickerRole(null); return; }

    setPickerRole(role);
    setLoading(true);
    setPickerUsers([]);
    try {
      const token = localStorage.getItem("access_token");
      const res = await fetch(`${BASE_URL}/api/v1/admin/users`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const all: PickerUser[] = await res.json();
        setPickerUsers(all.filter((u) => u.role === role && u.status === "active"));
      }
    } finally {
      setLoading(false);
    }
  }

  async function impersonate(target: PickerUser) {
    try {
      const token = localStorage.getItem("access_token");
      const res = await fetch(`${BASE_URL}/api/v1/admin/impersonate/${target.id}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return;
      const data = await res.json();

      const currentToken = localStorage.getItem("access_token");
      const currentUser = localStorage.getItem("user");
      if (currentToken) localStorage.setItem("impersonation_original_token", currentToken);
      if (currentUser) localStorage.setItem("impersonation_original_user", currentUser);
      localStorage.setItem("impersonation_target_name", data.target_name);
      localStorage.setItem("impersonation_target_email", data.target_email);
      localStorage.setItem("access_token", data.access_token);

      const meRes = await fetch(`${BASE_URL}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${data.access_token}` },
      });
      if (meRes.ok) localStorage.setItem("user", JSON.stringify(await meRes.json()));

      window.location.href = target.role === "teacher" ? "/checks" : "/admin";
    } catch {}
  }

  return (
    <div className="mb-3">
      <p className="text-xs text-gray-400 mb-1.5">Переключить роль</p>
      <div className="flex gap-1">
        {roles.map(({ key, label }) => {
          const isActive = key === currentRole;
          const disabled = !isActive && currentRole !== "superadmin" && key !== "superadmin";
          return (
            <button
              key={key}
              onClick={() => !disabled && handleClick(key)}
              disabled={disabled}
              className={`text-xs px-2 py-1 rounded flex-1 transition-colors ${
                isActive
                  ? "bg-blue-600 text-white font-medium"
                  : disabled
                  ? "bg-gray-50 text-gray-300 cursor-not-allowed"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200 cursor-pointer"
              }`}
            >
              {label}
            </button>
          );
        })}
      </div>

      {pickerRole && (
        <div className="mt-2 bg-gray-50 border border-gray-200 rounded-lg overflow-hidden">
          {loading ? (
            <p className="text-xs text-gray-400 px-3 py-2">Загрузка...</p>
          ) : pickerUsers.length === 0 ? (
            <p className="text-xs text-gray-400 px-3 py-2">Нет активных пользователей</p>
          ) : (
            pickerUsers.map((u) => (
              <button
                key={u.id}
                onClick={() => impersonate(u)}
                className="w-full text-left px-3 py-2 hover:bg-white text-xs border-b border-gray-100 last:border-0 transition-colors"
              >
                <p className="text-gray-800 font-medium truncate">{u.full_name || u.email}</p>
                <p className="text-gray-400 truncate">{u.email}</p>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}

type NavItem = { href: string; label: string; soon?: boolean };

const NAV: Record<AuthUser["role"], NavItem[]> = {
  teacher: [
    { href: "/checks/new", label: "Новая проверка" },
    { href: "/checks", label: "История проверок" },
    { href: "/groups", label: "Группы и классы" },
    { href: "/settings", label: "Настройки" },
    { href: "/profile", label: "Профиль" },
  ],
  school_admin: [
    { href: "/admin", label: "Обзор школы" },
    { href: "/admin/teachers", label: "Учителя" },
    { href: "/admin/checks", label: "Все проверки школы" },
    { href: "/admin/repository", label: "Репозиторий работ" },
    { href: "/admin/api-keys", label: "API-ключи" },
    { href: "/admin/settings", label: "Настройки по умолчанию" },
    { href: "/profile", label: "Профиль" },
  ],
  superadmin: [
    { href: "/super", label: "Обзор" },
    { href: "/super/schools", label: "Школы и админы" },
    { href: "/super/corpus", label: "Корпус антиплагиата" },
    { href: "/super/plans", label: "Тарифы и лимиты" },
    { href: "/super/flagged", label: "Flagged: попытки обхода" },
    { href: "/super/disputes", label: "Спорные результаты" },
    { href: "/super/models", label: "Модели детектора" },
    { href: "/super/audit", label: "Аудит действий" },
    { href: "/super/api-log", label: "API и журнал запросов" },
    { href: "/super/status", label: "Состояние системы" },
  ],
};

const ROLE_LABELS: Record<string, string> = {
  superadmin: "Суперадмин",
  school_admin: "Администратор",
  teacher: "Учитель",
};

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    const u = getUser();
    if (!u) {
      router.replace("/login");
      return;
    }
    setUser(u);
  }, [router]);

  if (!user) return null;

  const nav = NAV[user.role] ?? [];

  function isActive(href: string) {
    if (href === "/checks") return pathname === "/checks";
    if (href === "/admin") return pathname === "/admin";
    if (href === "/super") return pathname === "/super";
    return pathname.startsWith(href);
  }

  return (
    <div className="flex min-h-screen bg-gray-50">
      <ImpersonationBanner />
      {/* Sidebar */}
      <aside className="w-56 shrink-0 bg-white border-r border-gray-200 flex flex-col fixed top-0 left-0 h-screen z-10">
        {/* Logo */}
        <div className="px-5 py-4 border-b border-gray-100">
          <span className="font-bold text-gray-900 text-sm">Антиплагиат</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-2 overflow-y-auto">
          {nav.map((item) =>
            item.soon ? (
              <span
                key={item.href}
                className="flex items-center px-5 py-2.5 text-sm text-gray-300 cursor-not-allowed select-none"
              >
                {item.label}
              </span>
            ) : (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center px-5 py-2.5 text-sm transition-colors ${
                  isActive(item.href)
                    ? "bg-blue-50 text-blue-700 font-medium border-r-2 border-blue-600"
                    : "text-gray-700 hover:bg-gray-50"
                }`}
              >
                {item.label}
              </Link>
            )
          )}
        </nav>

        {/* User */}
        <div className="border-t border-gray-100 px-5 py-4">
          <p className="text-xs font-medium text-gray-700">{ROLE_LABELS[user.role]}</p>
          <p className="text-xs text-gray-400 mt-0.5 truncate mb-3">{user.full_name}</p>
          <RoleSwitcher currentRole={user.role} />
          <button
            onClick={() => { clearAuth(); router.replace("/login"); }}
            className="text-xs text-gray-400 hover:text-gray-700 transition-colors"
          >
            Выйти
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 ml-56 min-h-screen">
        {children}
      </div>
    </div>
  );
}
