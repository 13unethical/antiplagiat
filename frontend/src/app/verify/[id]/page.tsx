"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

interface VerifyResult {
  id: string;
  id_short: string;
  is_authentic: boolean;
  status: string;
  work_title: string;
  similarity_percent: number | null;
  ai_percent: number | null;
  word_count: number | null;
  language: string | null;
  completed_at: string | null;
}

const LANG_LABELS: Record<string, string> = {
  "uz-Latn": "узбекский (латиница)",
  "uz-Cyrl": "узбекский (кириллица)",
  ru: "русский",
  mixed: "смешанный",
};

export default function VerifyPage() {
  const { id } = useParams<{ id: string }>();
  const [result, setResult] = useState<VerifyResult | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    fetch(`${apiBase}/api/v1/checks/${id}/verify`)
      .then((r) => {
        if (!r.ok) throw new Error("Отчёт не найден");
        return r.json();
      })
      .then(setResult)
      .catch((e) => setError(e.message));
  }, [id]);

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
      <div className="bg-white border rounded-2xl shadow-sm p-8 max-w-md w-full space-y-5">
        <div className="text-center">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-blue-50 mb-3">
            <span className="text-2xl">🔍</span>
          </div>
          <h1 className="text-lg font-semibold">Верификация отчёта</h1>
          <p className="text-sm text-gray-500 mt-1">Проверка подлинности антиплагиата</p>
        </div>

        {error ? (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3 text-center">
            {error}
          </div>
        ) : !result ? (
          <p className="text-center text-sm text-gray-400">Загрузка...</p>
        ) : (
          <>
            <div className="bg-green-50 border border-green-200 rounded-xl px-4 py-3 flex items-center gap-3">
              <span className="text-green-600 text-xl">✓</span>
              <div>
                <p className="font-medium text-green-800 text-sm">Отчёт подлинный</p>
                <p className="text-xs text-green-600 mt-0.5">ID: {result.id_short}</p>
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Работа</span>
                <span className="font-medium text-gray-900 text-right max-w-[220px] truncate">
                  {result.work_title}
                </span>
              </div>
              {result.language && (
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Язык</span>
                  <span className="text-gray-700">{LANG_LABELS[result.language] ?? result.language}</span>
                </div>
              )}
              {result.word_count != null && (
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Слов</span>
                  <span className="text-gray-700">{result.word_count.toLocaleString()}</span>
                </div>
              )}
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Совпадения</span>
                <span className={`font-semibold ${
                  (result.similarity_percent ?? 0) >= 50 ? "text-red-600"
                  : (result.similarity_percent ?? 0) >= 20 ? "text-yellow-600"
                  : "text-green-600"
                }`}>
                  {result.similarity_percent?.toFixed(1) ?? "—"}%
                </span>
              </div>
              {result.ai_percent != null && (
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">ИИ-вероятность</span>
                  <span className="font-semibold text-gray-800">{result.ai_percent.toFixed(0)}%</span>
                </div>
              )}
              {result.completed_at && (
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Дата</span>
                  <span className="text-gray-700">
                    {new Date(result.completed_at).toLocaleDateString("ru", {
                      day: "2-digit", month: "2-digit", year: "numeric",
                    })}
                  </span>
                </div>
              )}
            </div>

            <p className="text-xs text-gray-400 text-center pt-2 border-t">
              antiplagiat.uz — Антиплагиат для узбекских школ и вузов
            </p>
          </>
        )}
      </div>
    </div>
  );
}
