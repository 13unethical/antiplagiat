"use client";

import { useEffect, useState, useCallback } from "react";
import { apiFetch, ApiError } from "@/lib/api";

interface CorpusDoc {
  id: string;
  title: string;
  url: string | null;
  language: string;
  source_type: string;
  word_count: number;
  created_at: string;
}

const LANG_LABEL: Record<string, string> = {
  ru: "Русский",
  "uz-Latn": "Узб. (лат.)",
  "uz-Cyrl": "Узб. (кир.)",
  mixed: "Смешанный",
};

const SOURCE_LABEL: Record<string, string> = {
  web: "Интернет",
  academic: "Академический",
  school: "Школьный",
  book: "Книга",
};

export default function CorpusPage() {
  const [docs, setDocs] = useState<CorpusDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<{ text: string; kind: "ok" | "err" } | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);

  const [form, setForm] = useState({
    title: "",
    content: "",
    url: "",
    language: "ru",
    source_type: "web",
  });
  const [adding, setAdding] = useState(false);

  const fetchDocs = useCallback(async () => {
    try {
      const data = await apiFetch<CorpusDoc[]>("/api/v1/corpus");
      setDocs(data);
    } catch {}
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchDocs(); }, [fetchDocs]);

  async function addDoc(e: React.FormEvent) {
    e.preventDefault();
    setAdding(true);
    try {
      await apiFetch("/api/v1/corpus", {
        method: "POST",
        body: JSON.stringify({
          title: form.title,
          content: form.content,
          url: form.url || undefined,
          language: form.language,
          source_type: form.source_type,
        }),
      });
      setMsg({ text: "Документ добавлен и проиндексирован", kind: "ok" });
      setShowAdd(false);
      setForm({ title: "", content: "", url: "", language: "ru", source_type: "web" });
      fetchDocs();
    } catch (err) {
      setMsg({ text: err instanceof ApiError ? err.message : "Ошибка", kind: "err" });
    } finally {
      setAdding(false);
    }
  }

  async function deleteDoc(id: string) {
    setDeleting(id);
    try {
      await apiFetch(`/api/v1/corpus/${id}`, { method: "DELETE" });
      setDocs((prev) => prev.filter((d) => d.id !== id));
    } catch (err) {
      setMsg({ text: err instanceof ApiError ? err.message : "Ошибка удаления", kind: "err" });
    } finally {
      setDeleting(null);
    }
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold">Корпус антиплагиата</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {docs.length} документов · по ним проверяются все работы
          </p>
        </div>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 transition-colors"
        >
          + Добавить документ
        </button>
      </div>

      {/* Add form */}
      {showAdd && (
        <form onSubmit={addDoc} className="bg-white border rounded-xl p-5 mb-5 space-y-4">
          <h2 className="font-medium text-sm">Новый документ</h2>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Название *</label>
            <input
              required
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Статья / книга / работа"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">URL источника</label>
            <input
              type="url"
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="https://..."
              value={form.url}
              onChange={(e) => setForm({ ...form, url: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Язык</label>
              <select
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={form.language}
                onChange={(e) => setForm({ ...form, language: e.target.value })}
              >
                <option value="ru">Русский</option>
                <option value="uz-Latn">Узбекский (лат.)</option>
                <option value="uz-Cyrl">Узбекский (кир.)</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Тип источника</label>
              <select
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={form.source_type}
                onChange={(e) => setForm({ ...form, source_type: e.target.value })}
              >
                <option value="web">Интернет</option>
                <option value="academic">Академический</option>
                <option value="school">Школьный</option>
                <option value="book">Книга</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">
              Текст документа *{" "}
              <span className="font-normal text-gray-400">
                ({form.content.split(/\s+/).filter(Boolean).length} слов)
              </span>
            </label>
            <textarea
              required
              rows={8}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono resize-y"
              placeholder="Вставьте текст документа..."
              value={form.content}
              onChange={(e) => setForm({ ...form, content: e.target.value })}
            />
          </div>
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={adding}
              className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
            >
              {adding ? "Индексирование..." : "Добавить и проиндексировать"}
            </button>
            <button
              type="button"
              onClick={() => setShowAdd(false)}
              className="border px-4 py-2 rounded-lg text-sm text-gray-600 hover:bg-gray-50"
            >
              Отмена
            </button>
          </div>
        </form>
      )}

      {/* Message */}
      {msg && (
        <div className={`mb-5 px-4 py-3 rounded-xl text-sm border ${
          msg.kind === "ok" ? "bg-blue-50 border-blue-200 text-blue-800" : "bg-red-50 border-red-200 text-red-700"
        }`}>
          {msg.text}
          <button onClick={() => setMsg(null)} className="ml-3 opacity-50 hover:opacity-100">×</button>
        </div>
      )}

      {/* Table */}
      <div className="bg-white border rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b bg-gray-50">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Название</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">URL</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Язык</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Тип</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Слов</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Добавлен</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400 text-sm">Загрузка...</td>
              </tr>
            ) : docs.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-10 text-center text-gray-400 text-sm">
                  Корпус пуст. Добавьте первый документ — по нему будут проверяться работы.
                </td>
              </tr>
            ) : (
              docs.map((doc) => (
                <tr key={doc.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900 max-w-[260px] truncate">
                    {doc.title}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-400 max-w-[180px] truncate">
                    {doc.url ? (
                      <span title={doc.url}>{doc.url}</span>
                    ) : (
                      <span className="text-gray-200">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-600">{LANG_LABEL[doc.language] ?? doc.language}</td>
                  <td className="px-4 py-3">
                    <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                      {SOURCE_LABEL[doc.source_type] ?? doc.source_type}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{doc.word_count.toLocaleString()}</td>
                  <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">
                    {new Date(doc.created_at).toLocaleDateString("ru")}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => deleteDoc(doc.id)}
                      disabled={deleting === doc.id}
                      className="text-xs text-red-500 hover:underline disabled:opacity-40"
                    >
                      {deleting === doc.id ? "..." : "Удалить"}
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
