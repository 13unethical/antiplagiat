"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiFetch, ApiError } from "@/lib/api";
import { Icon, PageHeader, Ring } from "../../ui";

interface Flag {
  id: string;
  type: string;
  severity: string;
  count: number;
  details: Record<string, unknown>;
}

interface Match {
  id: string;
  start_char: number;
  end_char: number;
  matched_text: string;
  source_title: string;
  source_url: string | null;
  source_lang: string;
  match_kind: string;
  score: number;
}

interface MTSegment {
  id: string;
  start_char: number;
  end_char: number;
  probability: number;
  mt_kind: string;
}

interface CheckDetail {
  id: string;
  filename: string;
  work_title: string | null;
  student_name: string | null;
  group_name: string | null;
  file_size: number;
  status: string;
  word_count: number | null;
  language: string | null;
  similarity_percent: number | null;
  similarity_sources_count: number | null;
  ai_percent: number | null;
  ai_model_version: string | null;
  mt_flag: boolean | null;
  mt_percent: number | null;
  stylometry_score: number | null;
  excluded_sources: string[];
  created_at: string;
  completed_at: string | null;
  flags: Flag[];
  matches: Match[];
  mt_segments: MTSegment[];
  text_preview: string | null;
  full_text: string | null;
  error_message?: string | null;
  ocr_used?: boolean;
}

const FLAG_LABELS: Record<string, string> = {
  homoglyph: "Подмена букв (гомоглифы)",
  invisible_char: "Невидимые символы",
  hidden_text: "Скрытый текст",
  spaced_text: "Разрядка (р а з р я д к а)",
  quote_abuse: "Злоупотребление кавычками",
};

const FLAG_HOW: Record<string, string> = {
  homoglyph:
    "Буквы заменены на похожие из другого алфавита (кириллица ↔ латиница): слово выглядит прежним, но не совпадает при поиске.",
  invisible_char:
    "В текст вставлены невидимые символы нулевой ширины — они разбивают слова, чтобы обойти поиск совпадений.",
  hidden_text:
    "В документе есть скрытый текст (белый цвет, крошечный кегль): не виден при чтении, но влияет на объём.",
  spaced_text:
    "Буквы в словах разделены пробелами («р а з р я д к а»), чтобы слово не распознавалось целиком.",
  quote_abuse:
    "Слишком большая доля текста заключена в кавычки, чтобы исключить её из проверки как цитаты.",
};

const SEVERITY_STYLES: Record<string, string> = {
  high: "bg-red-50 border-red-200 text-red-700",
  medium: "bg-yellow-50 border-yellow-200 text-yellow-700",
  low: "bg-gray-50 border-gray-200 text-gray-600",
};

const SEVERITY_LABELS: Record<string, string> = {
  high: "Высокая",
  medium: "Средняя",
  low: "Низкая",
};

const LANG_LABELS: Record<string, string> = {
  "uz-Latn": "узбекский (латиница)",
  "uz-Cyrl": "узбекский (кириллица)",
  ru: "русский",
  en: "английский",
  mixed: "смешанный",
  other: "другой",
};

function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function simColor(pct: number) {
  if (pct >= 50) return "text-red-600";
  if (pct >= 20) return "text-yellow-700";
  return "text-green-700";
}

function buildTextReport(check: CheckDetail): string {
  const date = new Date(check.created_at).toLocaleDateString("ru");
  const lines = [
    `Проверка ${check.id.slice(0, 8).toUpperCase()} · ${date}`,
    `Работа: ${check.work_title || check.filename}${check.language ? ` · ${LANG_LABELS[check.language] ?? check.language}` : ""}${check.word_count ? ` · ${check.word_count} слов` : ""}`,
    check.student_name ? `Студент: ${check.student_name}${check.group_name ? ` · ${check.group_name}` : ""}` : "",
    `Совпадения: ${check.similarity_percent?.toFixed(1) ?? "—"}%${check.similarity_sources_count ? ` (${check.similarity_sources_count} источников)` : ""}`,
    `Flagged: ${check.flags.length}${check.flags.length > 0 ? " — " + check.flags.map((f) => FLAG_LABELS[f.type] ?? f.type).join(", ") : ""}`,
    ``,
    `ИИ-оценка — вероятность, а не доказательство.`,
  ].filter(Boolean);
  return lines.join("\n");
}

// ─── Highlighted text ───────────────────────────────────────────────────────

interface Segment {
  text: string;
  matchIdx: number | null; // null = plain text
}

function buildSegments(text: string, matches: Match[]): Segment[] {
  // Sort ranges by start position; skip if out of bounds
  const ranges = matches
    .map((m, i) => ({
      start: m.start_char,
      end: Math.min(m.end_char, text.length),
      idx: i,
    }))
    .filter((r) => r.start < text.length && r.end > r.start)
    .sort((a, b) => a.start - b.start);

  const segs: Segment[] = [];
  let pos = 0;

  for (const range of ranges) {
    if (range.start < pos) continue; // overlapping — skip
    if (range.start > pos) {
      segs.push({ text: text.slice(pos, range.start), matchIdx: null });
    }
    segs.push({ text: text.slice(range.start, range.end), matchIdx: range.idx });
    pos = range.end;
  }
  if (pos < text.length) {
    segs.push({ text: text.slice(pos), matchIdx: null });
  }
  return segs;
}

function HighlightedText({
  text,
  matches,
  activeIdx,
  onMatchClick,
}: {
  text: string;
  matches: Match[];
  activeIdx: number | null;
  onMatchClick: (idx: number) => void;
}) {
  const segments = buildSegments(text, matches);

  return (
    <div className="text-sm leading-relaxed text-gray-800 whitespace-pre-wrap font-sans">
      {segments.map((seg, i) => {
        if (seg.matchIdx === null) {
          return <span key={i}>{seg.text}</span>;
        }
        const m = matches[seg.matchIdx];
        const isActive = seg.matchIdx === activeIdx;
        const kind = m.match_kind; // exact | paraphrase | cross_lingual
        const activeClass =
          kind === "exact" ? "bg-red-400 text-white"
          : kind === "cross_lingual" ? "bg-purple-400 text-white"
          : kind === "web" ? "bg-orange-400 text-white"
          : "bg-yellow-400 text-gray-900";
        const idleClass =
          kind === "exact" ? "bg-red-100 text-red-900 hover:bg-red-200"
          : kind === "cross_lingual" ? "bg-purple-100 text-purple-900 hover:bg-purple-200"
          : kind === "web" ? "bg-orange-100 text-orange-900 hover:bg-orange-200"
          : "bg-yellow-100 text-yellow-900 hover:bg-yellow-200";
        return (
          <mark
            key={i}
            onClick={() => onMatchClick(seg.matchIdx!)}
            title={`${m.source_title} · ${(m.score * 100).toFixed(0)}%`}
            className={`cursor-pointer rounded px-0.5 transition-colors ${isActive ? activeClass : idleClass}`}
          >
            {seg.text}
          </mark>
        );
      })}
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────

export default function CheckDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [check, setCheck] = useState<CheckDetail | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [activeMatch, setActiveMatch] = useState<number | null>(null);
  const [showDispute, setShowDispute] = useState(false);
  const [disputeText, setDisputeText] = useState("");
  const [disputeSent, setDisputeSent] = useState(false);
  const [excludedSources, setExcludedSources] = useState<string[]>([]);
  const [recalcSim, setRecalcSim] = useState<number | null>(null);
  const matchRefs = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    if (!id) return;
    apiFetch<CheckDetail>(`/api/v1/checks/${id}`)
      .then((c) => {
        setCheck(c);
        setExcludedSources(c.excluded_sources ?? []);
      })
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Ошибка загрузки")
      );
  }, [id]);

  function handleMatchClick(idx: number) {
    setActiveMatch(idx === activeMatch ? null : idx);
    matchRefs.current[idx]?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function downloadJSON() {
    if (!check) return;
    const blob = new Blob([JSON.stringify(check, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `report-${check.id.slice(0, 8)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function copyTextReport() {
    if (!check) return;
    await navigator.clipboard.writeText(buildTextReport(check));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  async function downloadHtmlReport() {
    if (!check) return;
    setPdfLoading(true);
    try {
      const token = localStorage.getItem("access_token");
      const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const res = await fetch(`${apiBase}/api/v1/checks/${check.id}/report?format=html`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Ошибка генерации отчёта");
      const html = await res.blob();
      const url = URL.createObjectURL(html);
      const win = window.open(url, "_blank");
      // revoke after window loads
      setTimeout(() => URL.revokeObjectURL(url), 10_000);
      if (!win) {
        // fallback: download as file
        const a = document.createElement("a");
        a.href = url;
        a.download = `report-${check.id.slice(0, 8)}.html`;
        a.click();
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : "Ошибка");
    } finally {
      setPdfLoading(false);
    }
  }

  async function downloadReport(kind: "plagiarism" | "ai" | "flagged") {
    if (!check) return;
    if (process.env.NEXT_PUBLIC_DEMO === "1") {
      alert("Демо-режим: скачивание отчётов доступно после подключения бэкенда.");
      return;
    }
    const token = localStorage.getItem("access_token");
    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    try {
      const res = await fetch(
        `${apiBase}/api/v1/checks/${check.id}/report?format=pdf&kind=${kind}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? "Ошибка генерации PDF");
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const kindLabel =
        kind === "ai" ? "ИИ" : kind === "flagged" ? "обход" : "совпадения";
      a.href = url;
      a.download = `Markly-${kindLabel}-${check.id.slice(0, 8).toUpperCase()}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Ошибка");
    }
  }

  if (error) {
    return (
      <div className="p-8">
        <button
          onClick={() => router.push("/checks")}
          className="text-sm text-gray-500 hover:text-gray-800 mb-6 inline-block"
        >
          ← Назад
        </button>
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm">
          {error}
        </div>
      </div>
    );
  }

  if (!check) {
    return (
      <div className="p-8">
        <p className="text-gray-400 text-sm">Загрузка...</p>
      </div>
    );
  }

  const flagsHigh = check.flags.filter((f) => f.severity === "high");
  const simPct = check.similarity_percent ?? 0;
  const hasHighlight = check.full_text && check.matches.length > 0;

  const aiPct = check.status === "done" ? check.ai_percent : null;
  const isAiStub = check.ai_model_version?.startsWith("stub") ?? true;

  return (
    <>
      <PageHeader
        title={
          <span className="flex items-center gap-2 min-w-0 text-sm tracking-normal">
            <button
              onClick={() => router.push("/checks")}
              className="font-normal text-gray-500 hover:text-gray-900 transition-colors shrink-0"
            >
              История проверок
            </button>
            <span className="text-gray-300">/</span>
            <span className="truncate">{check.work_title || check.filename}</span>
          </span>
        }
      />
    <div className="p-4 md:p-8 max-w-4xl mx-auto space-y-6">
      <div>
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h2 className="font-semibold text-2xl tracking-tight">
              {check.work_title || check.filename}
            </h2>
            <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1.5 text-xs text-gray-500">
              {check.student_name && (
                <span>
                  {check.student_name}
                  {check.group_name && ` · ${check.group_name}`}
                </span>
              )}
              {check.language && (
                <span>{LANG_LABELS[check.language] ?? check.language}</span>
              )}
              {check.word_count != null && <span>{check.word_count} слов</span>}
              <span>{formatSize(check.file_size)}</span>
              {check.completed_at && (
                <span>
                  {new Date(check.completed_at).toLocaleString("ru", {
                    day: "2-digit",
                    month: "2-digit",
                    year: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              )}
              {check.ocr_used && (
                <span className="bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded">
                  OCR
                </span>
              )}
            </div>
          </div>
          <span
            className={`flex-shrink-0 text-xs font-medium px-2.5 py-1 rounded-full ${
              check.status === "done"
                ? "bg-green-100 text-green-700"
                : check.status === "failed"
                ? "bg-red-100 text-red-600"
                : "bg-blue-100 text-blue-700"
            }`}
          >
            {check.status === "done"
              ? "Готово"
              : check.status === "failed"
              ? "Ошибка"
              : "Обработка..."}
          </span>
        </div>

        {check.status === "failed" && check.error_message && (
          <div className="mt-3 bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2 rounded-lg">
            {check.error_message}
          </div>
        )}

        {/* Экспорт — PDF в стиле Markly */}
        {check.status === "done" && (
          <div className="mt-4 pt-4 border-t border-gray-100 flex flex-col sm:flex-row gap-3">
            <div className="flex-1 flex flex-wrap items-center justify-between gap-2 border rounded-xl pl-4 pr-2 py-2">
              <p className="text-sm font-medium">Отчёт антиплагиата</p>
              <button
                onClick={() => downloadReport("plagiarism")}
                className="btn btn-secondary"
              >
                <Icon name="download" className="text-gray-500" />
                PDF
              </button>
            </div>
            <div className="flex-1 flex flex-wrap items-center justify-between gap-2 border rounded-xl pl-4 pr-2 py-2">
              <p className="text-sm font-medium">Отчёт ИИ-детектора</p>
              <button
                onClick={() => downloadReport("ai")}
                className="btn btn-secondary"
              >
                <Icon name="download" className="text-gray-500" />
                PDF
              </button>
            </div>
            <div className="flex-1 flex flex-wrap items-center justify-between gap-2 border rounded-xl pl-4 pr-2 py-2">
              <p className="text-sm font-medium">Отчёт по обходу</p>
              <button
                onClick={() => downloadReport("flagged")}
                className="btn btn-secondary"
              >
                <Icon name="download" className="text-gray-500" />
                PDF
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Summary cards */}
      {check.status === "done" && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 border rounded-xl divide-y sm:divide-y-0 sm:divide-x tabular">
            <div className="px-5 py-4">
              <p className={`text-2xl font-semibold tracking-tight flex items-center gap-2.5 ${simColor(simPct)}`}>
                <Ring value={simPct} />
                {simPct.toFixed(1)}%
              </p>
              <p className="text-xs text-gray-500 mt-1">Совпадения</p>
              {check.similarity_sources_count != null &&
                check.similarity_sources_count > 0 && (
                  <p className="text-xs text-gray-400 mt-0.5">
                    {check.similarity_sources_count} источн.
                  </p>
                )}
            </div>
            <div className="px-5 py-4">
              {aiPct !== null && aiPct !== undefined ? (
                <>
                  <p className={`text-2xl font-semibold tracking-tight ${
                    "text-gray-900"
                  }`}>
                    {aiPct.toFixed(0)}%
                  </p>
                  <p className="text-xs text-gray-500 mt-1">Вероятный ИИ-текст</p>
                  {isAiStub && (
                    <p className="text-xs text-gray-500 mt-0.5">модель в разработке</p>
                  )}
                </>
              ) : (
                <>
                  <p className="text-2xl font-semibold tracking-tight text-gray-200">—</p>
                  <p className="text-xs text-gray-500 mt-1">Вероятный ИИ-текст</p>
                </>
              )}
            </div>
            <div className="px-5 py-4">
              <p
                className={`text-2xl font-semibold tracking-tight ${
                  check.flags.length > 0 ? "text-orange-700" : "text-gray-400"
                }`}
              >
                {check.flags.length}
              </p>
              <p className="text-xs text-gray-500 mt-1">Попытки обхода</p>
              {flagsHigh.length > 0 && (
                <p className="text-xs text-red-700 mt-0.5">
                  критичных: {flagsHigh.length}
                </p>
              )}
            </div>
          </div>

          {/* Disclaimer */}
          <p className="text-xs text-gray-600 bg-gray-50 rounded-xl px-4 py-3">
            ИИ-оценка — вероятность, а не доказательство. Перед выводами
            откройте подсвеченные фрагменты и поговорите со студентом.
          </p>

          {/* MT flag */}
          {check.mt_flag && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-800">
              <span className="font-medium">Вероятно машинный перевод</span>
              {" — "}
              фрагментов: {check.mt_segments.length} ({check.mt_percent?.toFixed(0)}% текста).
              Текст мог быть переведён с другого языка.
            </div>
          )}

          {/* Stylometry alert */}
          {check.stylometry_score !== null && check.stylometry_score < 0.45 && (
            <div className="bg-orange-50 border border-orange-200 rounded-xl px-4 py-3 text-sm text-orange-800">
              <span className="font-medium">Стиль отличается от предыдущих работ</span>
              {" — "}
              коэффициент похожести {((check.stylometry_score) * 100).toFixed(0)}%.
              Возможно, текст написан другим автором.
            </div>
          )}
        </>
      )}

      {/* Excluded sources banner */}
      {excludedSources.length > 0 && (
        <div className="bg-green-50 border border-green-200 rounded-xl px-4 py-3 text-sm text-green-800">
          <span className="font-medium">{excludedSources.length} источников исключено.</span>
          {recalcSim !== null && ` Пересчитанный процент совпадений: ${recalcSim.toFixed(1)}%.`}
        </div>
      )}

      {/* ── Matches list ──────────────────────────────────────────────── */}
      {check.matches.length > 0 && (
        <div>
          <h2 className="text-base font-semibold mb-4">
            Источники совпадений ({check.matches.length})
          </h2>
          <div className="space-y-2">
            {check.matches.map((m, i) => {
              const isActive = activeMatch === i;
              return (
                <div
                  key={m.id}
                  ref={(el) => { matchRefs.current[i] = el; }}
                  onClick={() => setActiveMatch(isActive ? null : i)}
                  className={`border rounded-lg p-3 cursor-pointer transition-colors ${
                    isActive
                      ? m.match_kind === "exact"
                        ? "bg-red-50 border-red-300"
                        : m.match_kind === "cross_lingual"
                        ? "bg-purple-50 border-purple-300"
                        : m.match_kind === "web"
                        ? "bg-orange-50 border-orange-300"
                        : "bg-yellow-50 border-yellow-300"
                      : "hover:bg-gray-50 border-gray-100"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-medium text-sm text-gray-900 flex items-center gap-1.5">
                        <span className="text-xs text-gray-400 font-normal shrink-0">
                          {i + 1}
                        </span>
                        <span className="truncate">{m.source_title}</span>
                      </p>
                      {m.source_url && (
                        <p className="text-xs text-gray-400 truncate mt-0.5">
                          {m.source_url}
                        </p>
                      )}
                    </div>
                    <div className="flex-shrink-0 flex gap-1.5 items-center">
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full ${
                          m.match_kind === "exact"
                            ? "bg-red-100 text-red-700"
                            : m.match_kind === "cross_lingual"
                            ? "bg-purple-100 text-purple-700"
                            : m.match_kind === "web"
                            ? "bg-orange-100 text-orange-700"
                            : "bg-yellow-100 text-yellow-700"
                        }`}
                      >
                        {m.match_kind === "exact" ? "Точное"
                          : m.match_kind === "cross_lingual" ? "Межъязыковое"
                          : m.match_kind === "web" ? "Веб"
                          : "Перефраз"}
                      </span>
                      <span className="text-xs font-medium text-gray-600">
                        {(m.score * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                  <p className="mt-2 text-xs text-gray-600 bg-white rounded px-2 py-1.5 border border-gray-100 line-clamp-2">
                    «{m.matched_text}»
                  </p>
                  {!excludedSources.includes(m.source_title) ? (
                    <button
                      onClick={async (e) => {
                        e.stopPropagation();
                        try {
                          const res = await apiFetch<{ similarity_percent: number; excluded_sources: string[] }>(
                            `/api/v1/checks/${check.id}/exclude-source`,
                            {
                              method: "POST",
                              headers: { "Content-Type": "application/json" },
                              body: JSON.stringify({ source_title: m.source_title }),
                            }
                          );
                          setExcludedSources(res.excluded_sources);
                          setRecalcSim(res.similarity_percent);
                        } catch {}
                      }}
                      className="mt-2 text-xs text-gray-400 hover:text-red-600 hover:underline"
                    >
                      Исключить источник
                    </button>
                  ) : (
                    <span className="mt-2 text-xs text-green-600">Источник исключён</span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {check.status === "done" && check.matches.length === 0 && (
        <div className="bg-white border rounded-xl p-6 text-center">
          <Icon name="check" className="mx-auto mb-2 text-green-700" />
          <p className="font-medium text-green-700">Совпадений с корпусом не найдено</p>
          <p className="text-sm text-gray-400 mt-1">
            Корпус пока небольшой — результат улучшится по мере его роста
          </p>
        </div>
      )}

      {/* Flags */}
      {check.flags.length > 0 && (
        <div>
          <h2 className="text-base font-semibold mb-4">
            Попытки обхода ({check.flags.length})
          </h2>
          <div className="space-y-3">
            {check.flags.map((flag) => (
              <div
                key={flag.id}
                className={`border rounded-lg p-3 ${
                  SEVERITY_STYLES[flag.severity] ?? "bg-gray-50 border-gray-200"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="font-medium text-sm">
                    {FLAG_LABELS[flag.type] ?? flag.type}
                  </p>
                  <span className="text-xs opacity-70 shrink-0">
                    {SEVERITY_LABELS[flag.severity] ?? flag.severity} · {flag.count} шт.
                  </span>
                </div>
                <div className="mt-1.5">
                  <span className="text-xs font-medium opacity-80">
                    Где найдено
                  </span>
                  <FlagDetails type={flag.type} details={flag.details} />
                </div>
                {FLAG_HOW[flag.type] && (
                  <p className="mt-2 text-xs opacity-90">
                    <span className="font-semibold">Как обходит систему: </span>
                    {FLAG_HOW[flag.type]}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
    </>
  );
}

function FlagDetails({
  type,
  details,
}: {
  type: string;
  details: Record<string, unknown>;
}) {
  if (type === "homoglyph" && details.examples) {
    const examples = details.examples as Array<{ word: string; position: number }>;
    return (
      <div className="mt-1 text-xs">
        <div className="flex flex-wrap gap-1">
          {examples.slice(0, 8).map((ex, i) => (
            <code
              key={i}
              title={`позиция ${ex.position}`}
              className="bg-white bg-opacity-60 px-1.5 py-0.5 rounded border border-current border-opacity-20"
            >
              {ex.word} <span className="opacity-50">· поз. {ex.position}</span>
            </code>
          ))}
        </div>
      </div>
    );
  }
  if (type === "invisible_char" && details.by_type) {
    const byType = details.by_type as Record<string, number>;
    return (
      <div className="mt-2 text-xs opacity-90 space-y-0.5">
        {Object.entries(byType).map(([name, count]) => (
          <p key={name}>
            {name}: {count}×
          </p>
        ))}
      </div>
    );
  }
  if (type === "hidden_text" && details.examples) {
    const examples = details.examples as string[];
    return (
      <div className="mt-2 text-xs opacity-90">
        {examples.slice(0, 2).map((ex, i) => (
          <p key={i} className="truncate">
            {ex}
          </p>
        ))}
      </div>
    );
  }
  if (type === "quote_abuse" && details.quoted_percent) {
    return (
      <p className="mt-2 text-xs opacity-90">
        В кавычках: {details.quoted_percent as number}% текста (порог 25%)
      </p>
    );
  }
  if (type === "spaced_text" && details.examples) {
    const examples = details.examples as string[];
    return (
      <div className="mt-2 text-xs opacity-90">
        {examples.slice(0, 3).map((ex, i) => (
          <p key={i}>«{ex}»</p>
        ))}
      </div>
    );
  }
  return null;
}
