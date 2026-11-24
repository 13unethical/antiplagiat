"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";

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
    <div className="p-8 max-w-2xl space-y-5">
      <h1 className="text-xl font-semibold">API-ключ</h1>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-xl">
          {error}
        </div>
      )}

      {/* Key status */}
      <div className="bg-white border rounded-xl p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-gray-700 mb-2">Ключ организации</p>
            {loading ? (
              <p className="text-sm text-gray-400">Загрузка...</p>
            ) : apiKey ? (
              <>
                <code className="font-mono text-sm bg-gray-50 border rounded px-2 py-1">
                  {apiKey.key_prefix}
                </code>
                <div className="flex gap-3 mt-2 text-xs text-gray-500">
                  <span>Выдан: {new Date(apiKey.created_at).toLocaleDateString("ru")}</span>
                  {apiKey.last_used_at && (
                    <span>Использован: {new Date(apiKey.last_used_at).toLocaleDateString("ru")}</span>
                  )}
                  <span className={apiKey.is_active ? "text-green-600" : "text-red-500"}>
                    {apiKey.is_active ? "● Активен" : "● Отозван"}
                  </span>
                </div>
              </>
            ) : (
              <p className="text-sm text-gray-400">Ключ ещё не выпущен</p>
            )}
          </div>
          <button
            onClick={rotateKey}
            disabled={rotating}
            className="flex-shrink-0 bg-blue-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-40 transition-colors"
          >
            {rotating ? "..." : apiKey ? "Перевыпустить" : "Выпустить ключ"}
          </button>
        </div>

        {/* Show new key once */}
        {newKey && (
          <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded-lg">
            <p className="text-xs font-semibold text-green-700 mb-2">
              ⚠ Скопируйте ключ — он показывается только один раз:
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 font-mono text-xs bg-white border rounded px-2 py-1.5 break-all">
                {newKey}
              </code>
              <button
                onClick={copyKey}
                className="flex-shrink-0 text-xs bg-green-600 text-white px-3 py-1.5 rounded hover:bg-green-700"
              >
                {copied ? "✓" : "Копировать"}
              </button>
            </div>
            <p className="text-xs text-green-600 mt-1.5">
              После закрытия страницы ключ не восстановить.
            </p>
          </div>
        )}
      </div>

      {/* Code example */}
      <div className="bg-white border rounded-xl p-5">
        <h2 className="font-semibold text-sm mb-3">Пример запроса</h2>
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
        <h2 className="font-semibold text-sm mb-3">Эндпоинты</h2>
        <div className="space-y-2">
          {[
            ["POST", "/api/v1/checks", "Загрузить файл и запустить проверку"],
            ["GET", "/api/v1/checks/{id}", "Статус и результат проверки"],
            ["GET", "/api/v1/checks/{id}/report?format=json", "Скачать отчёт (json / text / html)"],
            ["POST", "/api/v1/checks/{id}/dispute", "Оспорить результат"],
          ].map(([method, path, desc]) => (
            <div key={path} className="flex items-start gap-3 text-sm">
              <span className={`font-mono text-xs font-bold px-1.5 py-0.5 rounded flex-shrink-0 mt-0.5 ${
                method === "POST" ? "bg-blue-100 text-blue-700" : "bg-green-100 text-green-700"
              }`}>
                {method}
              </span>
              <code className="font-mono text-xs text-gray-700 mt-0.5 flex-shrink-0">{path}</code>
              <span className="text-xs text-gray-400 mt-0.5">{desc}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
