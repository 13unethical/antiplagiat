// Демо-режим: включается переменной окружения NEXT_PUBLIC_DEMO=1.
// Фронтенд работает без бэкенда — вход пропускается, API отдаёт примерные данные.
import type { AuthUser } from "./auth";

export const DEMO = process.env.NEXT_PUBLIC_DEMO === "1";

export const demoUser: AuthUser = {
  id: "demo-teacher",
  email: "demo@antiplagiat.uz",
  full_name: "Демо Учитель",
  role: "teacher",
  org_id: "demo-org",
  status: "active",
};

const fullText = `Малый и средний бизнес — основа экономики большинства стран. Чтобы оставаться на плаву, компаниям нужны не только деньги, но и точная информация о своём финансовом состоянии.

Данная работа посвящена анализу внедрения МСФО для малых и средних предприятий в Узбекистане. Следует отметить, что система финансовой отчётности, которая применяется в стране, находится в стадии реформирования.

Таким образом, переход на международные стандарты требует подготовки кадров, времени и ресурсов. В рамках настоящего исследования рассматриваются институциональные барьеры, которые мешают внедрению стандарта на практике.

«Стандарт упрощает учёт для небольших компаний и снижает издержки на подготовку отчётности», — отмечают исследователи. Это подтверждается опытом ряда развивающихся стран.`;

function at(sub: string): [number, number] {
  const i = fullText.indexOf(sub);
  return i < 0 ? [0, 0] : [i, i + sub.length];
}

const [m1s, m1e] = at("Малый и средний бизнес — основа экономики большинства стран.");
const [m2s, m2e] = at("переход на международные стандарты требует подготовки кадров");
const [m3s, m3e] = at("Стандарт упрощает учёт для небольших компаний");

const sampleReport = {
  id: "demo-1",
  filename: "IFRS_for_SMEs_Uzbekistan.docx",
  work_title: "МСФО для малого бизнеса в Узбекистане",
  student_name: "Иван Петров",
  student_id: "2024-0152",
  group_name: "ФК-21",
  file_size: 25190,
  status: "done",
  word_count: 3735,
  language: "ru",
  similarity_percent: 14,
  similarity_sources_count: 3,
  ai_percent: 78,
  ai_model_version: "stub-v0",
  mt_flag: true,
  mt_percent: 11,
  stylometry_score: 0.41,
  excluded_sources: [] as string[],
  created_at: new Date(Date.now() - 3600_000).toISOString(),
  completed_at: new Date(Date.now() - 3540_000).toISOString(),
  text_preview: fullText.slice(0, 200),
  full_text: fullText,
  ocr_used: false,
  flags: [
    {
      id: "f1",
      type: "homoglyph",
      severity: "high",
      count: 4,
      details: { word_count: 4, examples: [{ word: "инфoрмация", position: 180 }, { word: "кoмпания", position: 420 }] },
    },
    {
      id: "f2",
      type: "quote_abuse",
      severity: "medium",
      count: 1,
      details: { quoted_percent: 28.0 },
    },
  ],
  matches: [
    {
      id: "m1", start_char: m1s, end_char: m1e, matched_text: fullText.slice(m1s, m1e),
      source_title: "kwpublications.com", source_url: "https://kwpublications.com/ifrs-smes",
      source_lang: "ru", match_kind: "exact", score: 0.62,
    },
    {
      id: "m2", start_char: m2s, end_char: m2e, matched_text: fullText.slice(m2s, m2e),
      source_title: "Cross-country determinants of IFRS for SMEs adoption", source_url: null,
      source_lang: "ru", match_kind: "paraphrase", score: 0.33,
    },
    {
      id: "m3", start_char: m3s, end_char: m3e, matched_text: fullText.slice(m3s, m3e),
      source_title: "viewpoint.pwc.com", source_url: "https://viewpoint.pwc.com/ifrs-sme",
      source_lang: "ru", match_kind: "exact", score: 0.21,
    },
  ],
  mt_segments: [
    { id: "s1", start_char: m2s, end_char: m2e, probability: 0.74, mt_kind: "machine" },
  ],
};

const sampleChecks = [
  {
    id: "demo-1", filename: "IFRS_for_SMEs_Uzbekistan.docx", work_title: "МСФО для малого бизнеса",
    student_name: "Иван Петров", student_id: "2024-0152", group_name: "ФК-21", status: "done",
    word_count: 3735, language: "ru", similarity_percent: 14, similarity_sources_count: 3,
    ai_percent: 78, flag_count: 2, file_size: 25190,
    created_at: new Date(Date.now() - 3600_000).toISOString(), completed_at: new Date(Date.now() - 3540_000).toISOString(),
  },
  {
    id: "demo-2", filename: "essay_ai_education.docx", work_title: "ИИ в образовании",
    student_name: "Мадина Каримова", student_id: "2024-0153", group_name: "ФК-21", status: "done",
    word_count: 1920, language: "uz-Latn", similarity_percent: 6, similarity_sources_count: 1,
    ai_percent: 91, flag_count: 1, file_size: 14200,
    created_at: new Date(Date.now() - 86400_000).toISOString(), completed_at: new Date(Date.now() - 86300_000).toISOString(),
  },
  {
    id: "demo-3", filename: "coursework_final.pdf", work_title: "Курсовая работа",
    student_name: "Алишер Усмонов", student_id: "2024-0160", group_name: "ФК-22", status: "done",
    word_count: 5120, language: "ru", similarity_percent: 31, similarity_sources_count: 7,
    ai_percent: 22, flag_count: 0, file_size: 48900,
    created_at: new Date(Date.now() - 2 * 86400_000).toISOString(), completed_at: new Date(Date.now() - 2 * 86400_000 + 60000).toISOString(),
  },
];

const orgSettings = {
  default_exclude_quotes: true,
  default_exclude_bibliography: true,
  default_save_to_repository: false,
  require_student_name: false,
  require_group: false,
  default_min_match_words: 8,
  report_footer: "",
  name: "Демо-школа",
  seats_limit: 10,
  monthly_quota: 1000,
  plan: "standard",
};

// Возвращает примерные данные по пути API. method — GET/POST/...
export function demoData(path: string, method = "GET"): unknown {
  const p = path.split("?")[0];

  if (p === "/api/v1/auth/login") return { access_token: "demo-token", refresh_token: "demo-refresh" };
  if (p === "/api/v1/auth/refresh") return { access_token: "demo-token", refresh_token: "demo-refresh" };
  if (p === "/api/v1/auth/me") return demoUser;
  if (p === "/api/v1/auth/me/stats")
    return { checks_this_month: 12, quota_limit: 1000, personal_quota: null, total_checks: 48 };
  if (p === "/api/v1/org/settings") return orgSettings;
  if (p === "/api/v1/org/stats") return { teachers: 4, checks_this_month: 12, monthly_quota: 1000, seats_limit: 10 };
  if (p === "/api/v1/groups") {
    if (method === "POST") return { id: "g-new", name: "Новая группа", student_count: 0 };
    return [
      { id: "g1", name: "ФК-21", student_count: 2, created_at: new Date().toISOString() },
      { id: "g2", name: "ФК-22", student_count: 1, created_at: new Date().toISOString() },
    ];
  }
  if (p === "/api/v1/checks" && method === "POST") return { id: "demo-1", status: "done", filename: "demo.docx" };
  if (p === "/api/v1/checks" && method === "GET") return sampleChecks;
  if (p.startsWith("/api/v1/checks/") && method === "GET") {
    return { ...sampleReport, id: p.split("/").pop() || "demo-1" };
  }

  // Безопасные значения по умолчанию, чтобы страницы не падали
  if (method === "GET") return [];
  return {};
}
