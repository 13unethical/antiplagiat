"use client";

import { useEffect, useState, useCallback } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import { Icon, Notice, PageHeader } from "../../ui";

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
    <>
      <PageHeader title="Корпус антиплагиата">
        <button onClick={() => setShowAdd(!showAdd)} className="btn btn-primary">
          <Icon name="plus" />
          Добавить документ
        </button>
      </PageHeader>
      <p className="px-4 md:px-6 py-3 border-b text-gray-600">
        Документов: {docs.length}. По ним проверяются все работы
      </p>

      {/* Add form */}
      {showAdd && (
        <form onSubmit={addDoc} className="form-block">
          <h2 className="font-semibold text-base">Новый документ</h2>
          <div>
            <label className="field-label">Название *</label>
            <input
              required
              className="field"
              placeholder="Статья / книга / работа"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
          </div>
          <div>
            <label className="field-label">URL источника</label>
            <input
              type="url"
              className="field"
              placeholder="https://..."
              value={form.url}
              onChange={(e) => setForm({ ...form, url: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="field-label">Язык</label>
              <select
                className="field"
                value={form.language}
                onChange={(e) => setForm({ ...form, language: e.target.value })}
              >
                <option value="ru">Русский</option>
                <option value="uz-Latn">Узбекский (лат.)</option>
                <option value="uz-Cyrl">Узбекский (кир.)</option>
              </select>
            </div>
            <div>
              <label className="field-label">Тип источника</label>
              <select
                className="field"
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
            <label className="field-label">
              Текст документа *{" "}
              <span className="font-normal text-gray-500">
                ({form.content.split(/\s+/).filter(Boolean).length} слов)
              </span>
            </label>
            <textarea
              required
              rows={8}
              className="field font-mono resize-y"
              placeholder="Вставьте текст документа..."
              value={form.content}
              onChange={(e) => setForm({ ...form, content: e.target.value })}
            />
          </div>
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={adding}
              className="btn btn-primary"
            >
              {adding ? "Индексирование..." : "Добавить и проиндексировать"}
            </button>
            <button
              type="button"
              onClick={() => setShowAdd(false)}
              className="btn btn-secondary"
            >
              Отмена
            </button>
          </div>
        </form>
      )}

      {/* Message */}
      {msg && <Notice kind={msg.kind} onClose={() => setMsg(null)}>{msg.text}</Notice>}

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th>Название</th>
              <th>URL</th>
              <th>Язык</th>
              <th>Тип</th>
              <th>Слов</th>
              <th>Добавлен</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="table-empty">Загрузка...</td>
              </tr>
            ) : docs.length === 0 ? (
              <tr>
                <td colSpan={7} className="table-empty">
                  Корпус пуст. Добавьте первый документ — по нему будут проверяться работы.
                </td>
              </tr>
            ) : (
              docs.map((doc) => (
                <tr key={doc.id}>
                  <td className="font-medium text-gray-900 max-w-[260px] truncate">
                    {doc.title}
                  </td>
                  <td className="text-xs text-gray-500 max-w-[180px] truncate">
                    {doc.url ? (
                      <span title={doc.url}>{doc.url}</span>
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>
                  <td className="text-gray-600">{LANG_LABEL[doc.language] ?? doc.language}</td>
                  <td>
                    <span className="text-gray-700">
                      {SOURCE_LABEL[doc.source_type] ?? doc.source_type}
                    </span>
                  </td>
                  <td className="text-gray-600">{doc.word_count.toLocaleString("ru")}</td>
                  <td className="text-gray-500 text-xs whitespace-nowrap">
                    {new Date(doc.created_at).toLocaleDateString("ru")}
                  </td>
                  <td>
                    <button
                      onClick={() => deleteDoc(doc.id)}
                      disabled={deleting === doc.id}
                      className="link-danger"
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
    </>
  );
}
