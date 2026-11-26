"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import { Notice, PageHeader, Status } from "../../ui";

interface ApiKeyInfo {
  id: string;
  key_prefix: string;
  is_active: boolean;
  created_at: string;
  last_used_at: string | null;
}

interface ApiKeyCreated extends ApiKeyInfo {
  raw_key: string;
}

export default function ApiKeysPage() {
  const [apiKey, setApiKey] = useState<ApiKeyInfo | null>(null);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [rotating, setRotating] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<ApiKeyInfo | null>("/api/v1/org/api-key")
      .then(setApiKey)
      .catch(() => setApiKey(null))
      .finally(() => setLoading(false));
  }, []);

  async function rotateKey() {
    if (apiKey && !confirm("Выпустить новый ключ? Старый перестанет работать немедленно.")) return;
    setRotating(true);
    setError("");
    setNewKey(null);
    try {
      const created = await apiFetch<ApiKeyCreated>("/api/v1/org/api-key/rotate", { method: "POST" });
      setApiKey(created);
      setNewKey(created.raw_key);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ошибка");
    } finally {
      setRotating(false);
    }
  }

  async function copyKey() {
    if (!newKey) return;
    await navigator.clipboard.writeText(newKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  return (
    <>
      <PageHeader title="API-ключ" />

      {error && <Notice kind="err">{error}</Notice>}

      <div className="p-4 md:p-8 max-w-3xl mx-auto space-y-5">
      {/* Key status */}
      <div className="bg-white border rounded-xl p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-gray-700 mb-2">Ключ организации</p>
            {loading ? (
              <p className="text-sm text-gray-500">Загрузка...</p>
            ) : apiKey ? (
              <>
                <code className="font-mono text-sm bg-gray-50 border rounded px-2 py-1">
                  {apiKey.key_prefix}
                </code>
                <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-gray-500">
                  <span>Выдан: {new Date(apiKey.created_at).toLocaleDateString("ru")}</span>
                  {apiKey.last_used_at && (
                    <span>Использован: {new Date(apiKey.last_used_at).toLocaleDateString("ru")}</span>
                  )}
                  <Status tone={apiKey.is_active ? "green" : "red"}>{apiKey.is_active ? "Активен" : "Отозван"}</Status>
                </div>
              </>
            ) : (
              <p className="text-sm text-gray-500">Ключ ещё не выпущен</p>
            )}
          </div>
          <button
            onClick={rotateKey}
            disabled={rotating}
            className="btn btn-primary"
          >
            {rotating ? "..." : apiKey ? "Перевыпустить" : "Выпустить ключ"}
          </button>
        </div>

        {/* Show new key once */}
        {newKey && (
          <div className="mt-4 p-3 bg-gray-50 border rounded-lg">
            <p className="text-sm font-medium text-gray-900 mb-2">
              Скопируйте ключ, он показывается только один раз
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 font-mono text-xs bg-white border rounded px-2 py-1.5 break-all">
                {newKey}
              </code>
              <button
                onClick={copyKey}
                className="btn btn-secondary"
              >
                {copied ? "Скопировано" : "Копировать"}
              </button>
            </div>
            <p className="text-xs text-gray-600 mt-1.5">
              После закрытия страницы ключ не восстановить.
            </p>
          </div>
        )}
      </div>

      {/* Code example */}
      <div className="bg-white border rounded-xl p-5">
        <h2 className="font-semibold text-base mb-3">Пример запроса</h2>
        <pre className="bg-gray-50 border rounded-lg p-3 text-xs font-mono overflow-x-auto whitespace-pre">
{`curl -X POST ${apiBase}/api/v1/checks \\
  -H "X-API-Key: ${apiKey?.key_prefix ?? "sk-antipla..."}..." \\
  -F "file=@document.docx" \\
  -F "work_title=Курсовая работа" \\
  -F "student_name=Иванов Иван" \\
  -F "webhook_url=https://your-server.com/webhook"`}
        </pre>
      </div>

      {/* Endpoints */}
      <div className="bg-white border rounded-xl p-5">
        <h2 className="font-semibold text-base mb-3">Эндпоинты</h2>
        <div className="space-y-2">
          {[
            ["POST", "/api/v1/checks", "Загрузить файл и запустить проверку"],
            ["GET", "/api/v1/checks/{id}", "Статус и результат проверки"],
            ["GET", "/api/v1/checks/{id}/report?format=json", "Скачать отчёт (json / text / html)"],
            ["POST", "/api/v1/checks/{id}/dispute", "Оспорить результат"],
          ].map(([method, path, desc]) => (
            <div key={path} className="flex flex-wrap items-start gap-x-3 gap-y-0.5 text-sm">
              <span className="font-mono text-xs text-gray-500 w-10 shrink-0 mt-0.5">
                {method}
              </span>
              <code className="font-mono text-xs text-gray-800 mt-0.5 break-all">{path}</code>
              <span className="text-xs text-gray-500 mt-0.5">{desc}</span>
            </div>
          ))}
        </div>
      </div>
      </div>
    </>
  );
}
