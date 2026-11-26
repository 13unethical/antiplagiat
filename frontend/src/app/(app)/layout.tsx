"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { getUser, clearAuth } from "@/lib/auth";
import { DEMO } from "@/lib/demo";
import type { AuthUser } from "@/lib/auth";
import { Icon, Logo, type IconName } from "./ui";

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
  // Плашку убрали по просьбе: возврат к суперадмину — в переключателе ролей сайдбара.
  return null;
}

interface PickerUser { id: string; email: string; full_name: string; role: string; status: string; }

const ROLES: { key: AuthUser["role"]; label: string; icon: IconName; home: string }[] = [
  { key: "superadmin", label: "Суперадмин", icon: "shield", home: "/super" },
  { key: "school_admin", label: "Администратор", icon: "grid", home: "/admin" },
  { key: "teacher", label: "Учитель", icon: "user", home: "/checks/new" },
];

function AccountMenu({ user }: { user: AuthUser }) {
  const router = useRouter();
  const pathname = usePathname();
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [pickerRole, setPickerRole] = useState<AuthUser["role"] | null>(null);
  const [pickerUsers, setPickerUsers] = useState<PickerUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [isImpersonating, setIsImpersonating] = useState(false);

  useEffect(() => setOpen(false), [pathname]);

  useEffect(() => {
    if (!open) {
      setPickerRole(null);
      return;
    }
    setIsImpersonating(!!localStorage.getItem("impersonation_original_token"));
    function onPointer(e: PointerEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key !== "Escape") return;
      setOpen(false);
      triggerRef.current?.focus();
    }
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const canSwitch = DEMO || user.role === "superadmin";

  async function switchRole(role: AuthUser["role"]) {
    if (role === user.role) return;

    if (DEMO) {
      localStorage.setItem("user", JSON.stringify({ ...user, role }));
      window.location.href = ROLES.find((r) => r.key === role)!.home;
      return;
    }

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
    } catch {
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

  const row = "w-full flex items-center gap-2.5 min-h-9 px-2.5 rounded-[10px] text-sm text-left text-gray-800 hover:bg-gray-100 transition-colors";

  return (
    <div ref={rootRef} className="relative p-2">
      {open && (
        <div className="absolute inset-x-2 bottom-full max-h-[70dvh] overflow-y-auto p-1.5 bg-white rounded-2xl shadow-[0_0_0_1px_rgba(24,24,27,0.05),0_2px_4px_rgba(24,24,27,0.03),0_8px_16px_rgba(24,24,27,0.04),0_24px_48px_rgba(24,24,27,0.08)]">
          <Link href="/settings" onClick={() => setOpen(false)} className={row}>
            <Icon name="settings" className="text-gray-500" />
            Настройки
          </Link>

          {isImpersonating && (
            <button type="button" onClick={stopImpersonation} className={row}>
              <Icon name="shield" className="text-gray-500" />
              Вернуться к суперадмину
            </button>
          )}

          {canSwitch && !isImpersonating && (
            <div className="my-1 py-1 border-y">
              <p className="px-2.5 py-1 text-xs text-gray-500">Войти как</p>
              {ROLES.map((r) => (
                <div key={r.key}>
                  <button
                    type="button"
                    onClick={() => switchRole(r.key)}
                    aria-current={r.key === user.role ? "true" : undefined}
                    aria-expanded={!DEMO && r.key !== user.role ? pickerRole === r.key : undefined}
                    className={`${row} ${r.key === user.role ? "font-medium" : ""}`}
                  >
                    <Icon name={r.icon} className="text-gray-500" />
                    <span className="flex-1">{r.label}</span>
                    {r.key === user.role && <Icon name="check" className="text-green-600" />}
                    {!DEMO && r.key !== user.role && (
                      <Icon name="chevron" className={`text-gray-400 ${pickerRole === r.key ? "rotate-180" : ""}`} />
                    )}
                  </button>
                  {pickerRole === r.key && (
                    <div className="max-h-48 overflow-y-auto pl-6">
                      {loading ? (
                        <p className="text-xs text-gray-500 px-2.5 py-2">Загрузка...</p>
                      ) : pickerUsers.length === 0 ? (
                        <p className="text-xs text-gray-500 px-2.5 py-2">Нет активных пользователей</p>
                      ) : (
                        pickerUsers.map((u) => (
                          <button
                            key={u.id}
                            type="button"
                            onClick={() => impersonate(u)}
                            className="w-full text-left px-2.5 py-1.5 rounded-lg hover:bg-gray-100 text-xs transition-colors"
                          >
                            <p className="text-gray-800 font-medium truncate">{u.full_name || u.email}</p>
                            <p className="text-gray-500 truncate">{u.email}</p>
                          </button>
                        ))
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          <button
            type="button"
            onClick={() => { clearAuth(); router.replace("/login"); }}
            className={`${row} !text-red-700`}
          >
            <Icon name="logout" />
            Выйти
          </button>
        </div>
      )}

      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className={`w-full flex items-center gap-2.5 p-2 mt-1 rounded-xl text-left transition-colors ${open ? "bg-[#e7e7ea]" : "hover:bg-[#ededf0]"}`}
      >
        <span className="w-8 h-8 rounded-full bg-blue-100 text-blue-800 text-xs font-semibold flex items-center justify-center shrink-0">
          {(user.full_name || user.email).slice(0, 1).toUpperCase()}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium truncate">{user.full_name || user.email}</span>
          <span className="block text-xs text-gray-500">{ROLE_LABELS[user.role]}</span>
        </span>
        <Icon name="updown" className="text-gray-500" />
      </button>
    </div>
  );
}

type NavItem = { href: string; label: string; icon: IconName; soon?: boolean };

const NAV: Record<AuthUser["role"], NavItem[]> = {
  teacher: [
    { href: "/checks/new", label: "Новая проверка", icon: "plus" },
    { href: "/checks", label: "История проверок", icon: "clock" },
    { href: "/groups", label: "Группы и классы", icon: "users" },
    { href: "/settings", label: "Настройки", icon: "settings" },
  ],
  school_admin: [
    { href: "/admin", label: "Обзор школы", icon: "grid" },
    { href: "/admin/teachers", label: "Учителя", icon: "users" },
    { href: "/admin/checks", label: "Все проверки школы", icon: "clock" },
    { href: "/admin/repository", label: "Репозиторий работ", icon: "library" },
    { href: "/admin/api-keys", label: "API-ключи", icon: "key" },
    { href: "/admin/integrations", label: "Интеграции LMS", icon: "server" },
    { href: "/settings", label: "Настройки", icon: "settings" },
  ],
  superadmin: [
    { href: "/super", label: "Обзор", icon: "grid" },
    { href: "/super/schools", label: "Школы и админы", icon: "school" },
    { href: "/super/corpus", label: "Корпус антиплагиата", icon: "library" },
    { href: "/super/plans", label: "Тарифы и лимиты", icon: "plans" },
    { href: "/super/flagged", label: "Попытки обхода", icon: "flag" },
    { href: "/super/disputes", label: "Спорные результаты", icon: "question" },
    { href: "/super/models", label: "Модели детектора", icon: "cpu" },
    { href: "/super/audit", label: "Аудит действий", icon: "audit" },
    { href: "/super/api-log", label: "API и журнал запросов", icon: "server" },
    { href: "/super/status", label: "Состояние системы", icon: "activity" },
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
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => setMenuOpen(false), [pathname]);

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
    <div className="min-h-screen bg-canvas">
      <ImpersonationBanner />
      <header className="md:hidden fixed top-0 inset-x-0 h-14 z-20 bg-canvas border-b flex items-center justify-between px-4">
        <Logo />
        <button
          type="button"
          onClick={() => setMenuOpen(!menuOpen)}
          aria-expanded={menuOpen}
          aria-label={menuOpen ? "Закрыть меню" : "Меню"}
          className="p-3 -mr-3 text-gray-700"
        >
          <Icon name={menuOpen ? "close" : "menu"} />
        </button>
      </header>
      {menuOpen && <div className="md:hidden fixed inset-0 z-[9] bg-black/30" onClick={() => setMenuOpen(false)} />}

      <aside
        className={`w-60 bg-canvas flex-col fixed top-0 left-0 h-dvh z-10 pt-14 md:pt-0 md:flex border-r md:border-r-0 ${
          menuOpen ? "flex" : "hidden"
        }`}
      >
        <div className="hidden md:flex items-center gap-2 h-14 px-4">
          <Logo />
        </div>

        <nav className="flex-1 px-2 py-2 md:pt-0 space-y-0.5 overflow-y-auto">
          {nav.map((item) =>
            item.soon ? (
              <span
                key={item.href}
                className="flex items-center gap-2.5 h-8 px-2 text-sm text-gray-400 cursor-not-allowed select-none"
              >
                <Icon name={item.icon} />
                {item.label}
              </span>
            ) : (
              <Link
                key={item.href}
                href={item.href}
                aria-current={isActive(item.href) ? "page" : undefined}
                className={`flex items-center gap-2.5 h-8 px-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive(item.href)
                    ? "bg-[#e7e7ea] text-gray-900"
                    : "text-gray-600 hover:bg-[#ededf0] hover:text-gray-900"
                }`}
              >
                <Icon name={item.icon} className={isActive(item.href) ? "text-gray-800" : "text-gray-500"} />
                {item.label}
              </Link>
            )
          )}
        </nav>

        <AccountMenu user={user} />
      </aside>

      <div className="md:ml-60 pt-14 md:pt-6 min-h-screen flex">
        <main className="flex-1 min-w-0 bg-white md:rounded-tl-[16px]">{children}</main>
      </div>
    </div>
  );
}
