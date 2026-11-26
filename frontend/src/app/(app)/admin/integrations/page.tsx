"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch, ApiError } from "@/lib/api";
import { Notice, PageHeader, Status } from "../../ui";

type Tab = "moodle" | "canvas" | "api";

interface LtiPlatform {
  id: string;
  name: string;
  platform_type: string;
  issuer: string;
  client_id: string;
  deployment_ids: string[];
  jwks_url: string | null;
  auth_login_url: string | null;
  auth_token_url: string | null;
  api_base_url: string | null;
  is_active: boolean;
  created_at: string;
}

interface LtiSubmission {
  id: string;
  platform_id: string;
  check_id: string | null;
  external_assignment_id: string;
  external_submission_id: string;
  student_name: string | null;
  report_status: string;
  error_message: string | null;
  created_at: string;
}

interface IntegrationsOverview {
  api_public_url: string;
  frontend_url: string;
  jwks_url: string;
  oidc_login_url: string;
  launch_url: string;
  canvas_config_url: string;
  webhook_secret_set: boolean;
  has_api_key: boolean;
  platforms: LtiPlatform[];
  recent_submissions: LtiSubmission[];
}

const emptyForm = {
  name: "Canvas",
  platform_type: "canvas",
  issuer: "https://canvas.instructure.com",
  client_id: "",
  deployment_ids: "",
  jwks_url: "",
  auth_login_url: "",
  auth_token_url: "",
  api_base_url: "",
};

export default function IntegrationsPage() {
  const [tab, setTab] = useState<Tab>("moodle");
  const [data, setData] = useState<IntegrationsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [newSecret, setNewSecret] = useState<string | null>(null);
  const [rotating, setRotating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState(emptyForm);

  const load = useCallback(async () => {
    try {
      const overview = await apiFetch<IntegrationsOverview>("/api/v1/org/integrations");
      setData(overview);
      setError("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось загрузить");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function rotateSecret() {
    if (data?.webhook_secret_set && !confirm("Выпустить новый секрет? Старый перестанет проверяться.")) return;
    setRotating(true);
    setError("");
    try {
      const res = await apiFetch<{ webhook_secret: string }>(
        "/api/v1/org/integrations/webhook-secret/rotate",
        { method: "POST" },
      );
      setNewSecret(res.webhook_secret);
      setNotice("Секрет вебхука выпущен — скопируйте его сейчас");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ошибка");
    } finally {
      setRotating(false);
    }
  }

  async function createPlatform(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await apiFetch("/api/v1/org/integrations/platforms", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: form.name.trim() || "Canvas",
          platform_type: form.platform_type,
          issuer: form.issuer.trim(),
          client_id: form.client_id.trim(),
          deployment_ids: form.deployment_ids
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
          jwks_url: form.jwks_url.trim() || null,
          auth_login_url: form.auth_login_url.trim() || null,
          auth_token_url: form.auth_token_url.trim() || null,
          api_base_url: form.api_base_url.trim() || null,
        }),
      });
      setForm(emptyForm);
      setNotice("Платформа добавлена");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ошибка сохранения");
    } finally {
      setSaving(false);
    }
  }

  async function removePlatform(id: string) {
    if (!confirm("Удалить платформу?")) return;
    try {
      await apiFetch(`/api/v1/org/integrations/platforms/${id}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ошибка удаления");
    }
  }

  async function downloadCanvasJson() {
    if (!data) return;
    try {
      const cfg = await apiFetch<Record<string, unknown>>("/api/v1/lti/config/canvas.json");
      const blob = new Blob([JSON.stringify(cfg, null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "antiplagiat-canvas-lti.json";
      a.click();
      URL.revokeObjectURL(a.href);
    } catch {
      window.open(data.canvas_config_url, "_blank");
    }
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: "moodle", label: "Moodle" },
    { id: "canvas", label: "Canvas" },
    { id: "api", label: "Свой сайт (API)" },
  ];

  return (
    <>
      <PageHeader title="Интеграции LMS" />

      <div className="p-4 md:p-8 max-w-3xl mx-auto space-y-5">
        {error && <Notice kind="err">{error}</Notice>}
        {notice && <Notice kind="ok">{notice}</Notice>}

        <div className="flex flex-wrap gap-2 border-b pb-3">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={`px-3 py-1.5 text-sm rounded-lg ${
                tab === t.id ? "bg-gray-900 text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {loading || !data ? (
          <p className="text-sm text-gray-500">Загрузка...</p>
        ) : (
          <>
            {/* Shared secrets strip */}
            <div className="bg-white border rounded-xl p-5 space-y-3">
              <h2 className="font-semibold text-base">Доступ для LMS</h2>
              <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-gray-600">
                <span>
                  API-ключ:{" "}
                  {data.has_api_key ? (
                    <Status tone="green">есть</Status>
                  ) : (
                    <Status tone="amber">нет</Status>
                  )}{" "}
                  <Link href="/admin/api-keys" className="text-blue-600 underline ml-1">
                    управлять
                  </Link>
                </span>
                <span>
                  Webhook secret:{" "}
                  {data.webhook_secret_set ? (
                    <Status tone="green">задан</Status>
                  ) : (
                    <Status tone="amber">не задан</Status>
                  )}
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <button type="button" onClick={rotateSecret} disabled={rotating} className="btn btn-secondary">
                  {rotating ? "..." : data.webhook_secret_set ? "Перевыпустить секрет" : "Выпустить секрет вебхука"}
                </button>
                <code className="text-xs text-gray-500 break-all">{data.api_public_url}</code>
              </div>
              {newSecret && (
                <div className="p-3 bg-gray-50 border rounded-lg">
                  <p className="text-sm font-medium mb-2">Скопируйте секрет — показывается один раз</p>
                  <code className="block font-mono text-xs break-all bg-white border rounded px-2 py-1.5">
                    {newSecret}
                  </code>
                </div>
              )}
            </div>

            {tab === "moodle" && (
              <div className="bg-white border rounded-xl p-5 space-y-4 text-sm">
                <h2 className="font-semibold text-base">Moodle 4.x — плагин plagiarism_antiplagiat</h2>
                <ol className="list-decimal pl-5 space-y-2 text-gray-700">
                  <li>
                    Выпустите API-ключ и webhook secret выше (секрет вставьте в настройки плагина).
                  </li>
                  <li>
                    Установите плагин: скопируйте каталог{" "}
                    <code className="text-xs bg-gray-50 px-1 rounded">plagiarism_antiplagiat</code> в{" "}
                    <code className="text-xs bg-gray-50 px-1 rounded">moodle/plagiarism/antiplagiat</code>{" "}
                    или поставьте ZIP из репозитория{" "}
                    <code className="text-xs bg-gray-50 px-1 rounded">integrations/moodle/</code>.
                  </li>
                  <li>
                    Moodle → Плагины → Плагиатизм → Антиплагиат: API URL ={" "}
                    <code className="text-xs bg-gray-50 px-1 rounded break-all">{data.api_public_url}</code>,
                    ключ и секрет.
                  </li>
                  <li>Включите проверку на плагиат в задании Assign.</li>
                </ol>
                <p className="text-gray-600">
                  Callback (формируется Moodle сам):{" "}
                  <code className="text-xs bg-gray-50 px-1 rounded">
                    https://&lt;moodle&gt;/plagiarism/antiplagiat/callback.php
                  </code>
                </p>
                <p className="text-xs text-gray-500">
                  Подпись вебхука: заголовок <code>X-Antiplagiat-Signature</code> (HMAC-SHA256 тела).
                </p>
              </div>
            )}

            {tab === "canvas" && (
              <div className="space-y-5">
                <div className="bg-white border rounded-xl p-5 space-y-4 text-sm">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <h2 className="font-semibold text-base">Canvas LTI 1.3</h2>
                    <button type="button" onClick={downloadCanvasJson} className="btn btn-secondary">
                      Скачать JSON Developer Key
                    </button>
                  </div>
                  <ol className="list-decimal pl-5 space-y-2 text-gray-700">
                    <li>Admin → Developer Keys → + LTI Key → вставьте JSON конфиг.</li>
                    <li>Включите ключ, скопируйте Client ID → Apps → By Client ID.</li>
                    <li>Зарегистрируйте платформу формой ниже.</li>
                    <li>В Assignment включите Plagiarism Review → Antiplagiat.</li>
                  </ol>
                  <dl className="grid gap-2 text-xs font-mono text-gray-600">
                    <div>
                      <dt className="text-gray-400">JWKS</dt>
                      <dd className="break-all">{data.jwks_url}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-400">OIDC login</dt>
                      <dd className="break-all">{data.oidc_login_url}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-400">Launch</dt>
                      <dd className="break-all">{data.launch_url}</dd>
                    </div>
                  </dl>
                </div>

                <form onSubmit={createPlatform} className="bg-white border rounded-xl p-5 space-y-3">
                  <h3 className="font-semibold text-sm">Зарегистрировать платформу</h3>
                  <div className="grid sm:grid-cols-2 gap-3">
                    {(
                      [
                        ["name", "Название"],
                        ["issuer", "Issuer"],
                        ["client_id", "Client ID"],
                        ["deployment_ids", "Deployment ID(s), через запятую"],
                        ["jwks_url", "JWKS URL"],
                        ["auth_login_url", "OIDC Auth URL"],
                        ["auth_token_url", "Token URL"],
                        ["api_base_url", "Canvas API base"],
                      ] as const
                    ).map(([key, label]) => (
                      <label key={key} className="block text-xs text-gray-600 sm:col-span-1">
                        {label}
                        <input
                          className="mt-1 w-full border rounded-lg px-2 py-1.5 text-sm"
                          value={form[key]}
                          onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                          required={key === "issuer" || key === "client_id"}
                        />
                      </label>
                    ))}
                  </div>
                  <button type="submit" disabled={saving} className="btn btn-primary">
                    {saving ? "..." : "Добавить"}
                  </button>
                </form>

                {data.platforms.length > 0 && (
                  <div className="bg-white border rounded-xl p-5 space-y-3">
                    <h3 className="font-semibold text-sm">Платформы</h3>
                    <ul className="space-y-2 text-sm">
                      {data.platforms.map((p) => (
                        <li
                          key={p.id}
                          className="flex flex-wrap items-center justify-between gap-2 border rounded-lg px-3 py-2"
                        >
                          <div>
                            <div className="font-medium">
                              {p.name}{" "}
                              <span className="text-xs text-gray-500">({p.platform_type})</span>
                            </div>
                            <div className="text-xs text-gray-500 break-all">
                              {p.issuer} · {p.client_id}
                            </div>
                          </div>
                          <button
                            type="button"
                            className="btn btn-secondary text-xs"
                            onClick={() => removePlatform(p.id)}
                          >
                            Удалить
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {data.recent_submissions.length > 0 && (
                  <div className="bg-white border rounded-xl p-5 space-y-3">
                    <h3 className="font-semibold text-sm">Последние LMS-проверки</h3>
                    <ul className="space-y-2 text-xs text-gray-700">
                      {data.recent_submissions.map((s) => (
                        <li key={s.id} className="flex flex-wrap gap-x-3 gap-y-1 border-b pb-2">
                          <Status
                            tone={
                              s.report_status === "reported"
                                ? "green"
                                : s.report_status === "failed"
                                  ? "red"
                                  : "amber"
                            }
                          >
                            {s.report_status}
                          </Status>
                          <span>{s.student_name || "—"}</span>
                          <span className="text-gray-400">
                            asg {s.external_assignment_id} / sub {s.external_submission_id}
                          </span>
                          {s.check_id && (
                            <Link href={`/checks/${s.check_id}`} className="text-blue-600 underline">
                              отчёт
                            </Link>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {tab === "api" && (
              <div className="bg-white border rounded-xl p-5 space-y-4 text-sm">
                <h2 className="font-semibold text-base">Свой сайт / портал вуза</h2>
                <p className="text-gray-700">
                  Server-to-server: отправляете файл на API с ключом организации и{" "}
                  <code className="text-xs bg-gray-50 px-1 rounded">webhook_url</code>.
                </p>
                <pre className="bg-gray-50 border rounded-lg p-3 text-xs font-mono overflow-x-auto whitespace-pre">{`curl -X POST ${data.api_public_url}/api/v1/checks \\
  -H "X-API-Key: sk-..." \\
  -F "file=@work.docx" \\
  -F "student_id=lms-0152" \\
  -F "webhook_url=https://portal.univ.uz/hooks/antiplagiat"`}</pre>
                <p className="text-gray-600 text-xs">
                  В callback проверьте{" "}
                  <code>X-Antiplagiat-Signature = HMAC-SHA256(body, webhook_secret)</code>. Документация:{" "}
                  <code>API_INTEGRATION.md</code>.
                </p>
                <Link href="/admin/api-keys" className="text-blue-600 underline text-sm">
                  Перейти к API-ключу →
                </Link>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}
