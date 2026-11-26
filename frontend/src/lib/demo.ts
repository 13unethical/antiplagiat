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

// Демо-группы со студентами (как ждёт страница «Группы и классы»)
const demoGroups = [
  {
    id: "g1", name: "ФК-21", created_at: new Date().toISOString(),
    students: [
      { id: "s1", name: "Иван Петров", checks_count: 3 },
      { id: "s2", name: "Мадина Каримова", checks_count: 2 },
      { id: "s3", name: "Алишер Усмонов", checks_count: 1 },
    ],
  },
  {
    id: "g2", name: "ФК-22", created_at: new Date().toISOString(),
    students: [
      { id: "s4", name: "Дильноза Рахимова", checks_count: 4 },
      { id: "s5", name: "Тимур Саидов", checks_count: 0 },
    ],
  },
  {
    id: "g3", name: "Информатика 10-А", created_at: new Date().toISOString(),
    students: [
      { id: "s6", name: "Азиза Юлдашева", checks_count: 2 },
      { id: "s7", name: "Руслан Ким", checks_count: 1 },
      { id: "s8", name: "Нигора Абдуллаева", checks_count: 3 },
    ],
  },
];

const ago = (h: number) => new Date(Date.now() - h * 3600_000).toISOString();

const demoTeachers = [
  { id: "t1", email: "n.karimova@school.uz", full_name: "Нодира Каримова", status: "active", personal_quota: 200, role: "teacher", org_id: "o1" },
  { id: "t2", email: "o.saidov@school.uz", full_name: "Отабек Саидов", status: "active", personal_quota: null, role: "teacher", org_id: "o1" },
  { id: "t3", email: "e.li@school.uz", full_name: "Елена Ли", status: "inactive", personal_quota: null, role: "teacher", org_id: "o1" },
  { id: "t4", email: "b.yusupov@school.uz", full_name: "", status: "pending", personal_quota: null, role: "teacher", org_id: "o1" },
];

const demoOrgs = [
  { id: "o1", name: "Школа № 14, Ташкент", plan: "standard", seats_limit: 10, monthly_quota: 1000, valid_until: "2027-06-30" },
  { id: "o2", name: "Самаркандский лицей", plan: "pro", seats_limit: 30, monthly_quota: 5000, valid_until: null },
];

const demoSeats = { active: 2, pending_invitations: 1, used: 3, seats_limit: 10, available: 7 };

const demoKey = { id: "k1", key_prefix: "sk-demo", is_active: true, created_at: ago(900), last_used_at: ago(5) };

const demoDisputes = [
  { id: "d1", check_id: "a41c09f2-demo", submitted_by: "t1", comment: "Студент писал работу на уроке, черновики сохранились", status: "pending", verdict: null, created_at: ago(20), resolved_at: null },
  { id: "d2", check_id: "77be10d4-demo", submitted_by: "t2", comment: "Текст переведён самим студентом с узбекского", status: "reviewed", verdict: "human_written", created_at: ago(120), resolved_at: ago(90) },
];

const demoAudit = [
  { id: "a1", user_id: "u1", action: "update_organization", resource_type: "organization", resource_id: "o1a2b3c4d5", details: { monthly_quota: 1000 }, created_at: ago(4) },
  { id: "a2", user_id: "u1", action: "create_organization", resource_type: "organization", resource_id: "o2a2b3c4d5", details: { name: "Самаркандский лицей" }, created_at: ago(70) },
];

const demoAdmin: Record<string, unknown> = {
  "/api/v1/org/stats": { ...demoSeats, monthly_quota: 1000, checks_this_month: 12, flagged_this_month: 2 },
  "/api/v1/org/teachers": demoTeachers,
  "/api/v1/org/teachers/stats": demoSeats,
  "/api/v1/org/teachers/checks-stats": { t1: 8, t2: 4 },
  "/api/v1/org/repository/stats": { total: 2 },
  "/api/v1/org/repository": [
    { id: "r1", check_id: "demo-1", work_title: "МСФО для малого бизнеса", student_name: "Иван Петров", group_name: "ФК-21", word_count: 3735, language: "ru", similarity_percent: 14, created_at: ago(30), teacher_email: "n.karimova@school.uz" },
    { id: "r2", check_id: "demo-3", work_title: "Курсовая работа", student_name: "Алишер Усмонов", group_name: "ФК-22", word_count: 5120, language: "ru", similarity_percent: 31, created_at: ago(50), teacher_email: "o.saidov@school.uz" },
  ],
  "/api/v1/org/api-key": demoKey,
  "/api/v1/admin/stats": { orgs_total: 2, teachers_total: 4, admins_total: 1, checks_this_month: 12, flagged_this_month: 2, web_queries_this_month: 86, web_urls_fetched_this_month: 240, web_matches_this_month: 31 },
  "/api/v1/admin/organizations": demoOrgs,
  "/api/v1/admin/users": [...demoTeachers, { id: "u2", email: "director@school.uz", full_name: "Дилшод Рахимов", role: "school_admin", org_id: "o1", status: "active" }],
  "/api/v1/admin/flagged/stats": { flagged_this_month: 2, high_severity_this_month: 1, orgs_with_flagged: 1 },
  "/api/v1/admin/flagged": [
    { id: "demo-1", work_title: "МСФО для малого бизнеса", student_name: "Иван Петров", org_name: "Школа № 14, Ташкент", teacher_email: "n.karimova@school.uz", flags: ["homoglyph", "invisible_char"], severity: "high", created_at: ago(30) },
    { id: "demo-2", work_title: "ИИ в образовании", student_name: "Мадина Каримова", org_name: "Школа № 14, Ташкент", teacher_email: "n.karimova@school.uz", flags: ["spaced_text"], severity: "medium", created_at: ago(40) },
  ],
  "/api/v1/admin/model-versions": [
    { id: "m1", model_type: "ai_detector", version: "stub-v0", description: "Эвристика", is_active: true, metrics: {}, created_at: ago(2000) },
    { id: "m2", model_type: "ai_detector", version: "v0.4-xlmr-large", description: "XLM-RoBERTa large", is_active: false, metrics: { fpr: 0.012, tpr_at_1pct: 0.83, f1: 0.88, dataset_size: 42000 }, created_at: ago(200) },
  ],
  "/api/v1/admin/dataset/stats": { human_written: 18, ai_generated: 12, machine_translated: 4 },
  "/api/v1/admin/api-log/stats": { requests_today: 3, errors_today: 2, limit_hits_today: 1, avg_response_ms: 184 },
  "/api/v1/admin/api-log": [
    { id: "l1", org_name: "Самаркандский лицей", key_prefix: "sk-demo", method: "POST", path: "/api/v1/checks", status_code: 201, response_ms: 412, created_at: ago(1) },
    { id: "l2", org_name: "Самаркандский лицей", key_prefix: "sk-demo", method: "GET", path: "/api/v1/checks/demo-1", status_code: 404, response_ms: 38, created_at: ago(2) },
    { id: "l3", org_name: "Школа № 14, Ташкент", key_prefix: "sk-demo", method: "POST", path: "/api/v1/checks", status_code: 429, response_ms: 102, created_at: ago(3) },
  ],
  "/api/v1/admin/status": {
    checked_at: new Date().toISOString(),
    services: [
      { name: "PostgreSQL", status: "ok", latency: "4 мс" },
      { name: "OpenSearch", status: "ok", latency: "21 мс" },
      { name: "Brave Search", status: "warn", detail: "Ключ не задан, веб-поиск отключён" },
    ],
  },
  "/api/v1/corpus": [
    { id: "c1", title: "Международные стандарты финансовой отчётности", url: "https://example.org/ifrs", language: "ru", source_type: "academic", word_count: 48200, created_at: ago(600) },
    { id: "c2", title: "Oʻzbekiston tarixi", url: null, language: "uz-Latn", source_type: "book", word_count: 91400, created_at: ago(800) },
  ],
};

const rndId = (p: string) => p + Math.random().toString(36).slice(2, 8);

// Возвращает примерные данные по пути API. method — GET/POST/...; body — тело запроса (JSON-строка)
export function demoData(path: string, method = "GET", body?: string): unknown {
  const p = path.split("?")[0];
  let payload: Record<string, unknown> = {};
  try { payload = body ? (JSON.parse(body) as Record<string, unknown>) : {}; } catch { /* ignore */ }

  if (p === "/api/v1/auth/login") return { access_token: "demo-token", refresh_token: "demo-refresh" };
  if (p === "/api/v1/auth/refresh") return { access_token: "demo-token", refresh_token: "demo-refresh" };
  if (p === "/api/v1/auth/me") return demoUser;
  if (p === "/api/v1/auth/me/stats")
    return { checks_this_month: 12, quota_limit: 1000, personal_quota: null, total_checks: 48 };
  if (p === "/api/v1/org/settings") return orgSettings;
  if (p in demoAdmin && method === "GET") return demoAdmin[p];
  if (/^\/api\/v1\/admin\/organizations\/[^/]+$/.test(p) && method === "PATCH")
    return { ...demoOrgs.find((o) => p.endsWith(`/${o.id}`)), ...payload };
  if (/^\/api\/v1\/admin\/disputes\/[^/]+$/.test(p) && method === "PATCH")
    return { ...demoDisputes.find((d) => p.endsWith(`/${d.id}`)), status: "reviewed", verdict: payload.verdict, resolved_at: new Date().toISOString() };
  if (p === "/api/v1/admin/disputes") {
    const status = new URLSearchParams(path.split("?")[1]).get("status");
    return demoDisputes.filter((d) => !status || d.status === status);
  }
  if (p === "/api/v1/admin/audit-log") {
    const action = new URLSearchParams(path.split("?")[1]).get("action");
    return demoAudit.filter((a) => !action || a.action === action);
  }
  if (p === "/api/v1/org/checks") return sampleChecks.map((c) => ({ ...c, teacher_email: "n.karimova@school.uz" }));
  if (p === "/api/v1/org/api-key/rotate")
    return { ...demoKey, created_at: new Date().toISOString(), raw_key: "demo-key-not-real" };
  if (/\/invitations$/.test(p) && method === "POST") return { token: "demo-invite" };
  if (p === "/api/v1/groups") {
    if (method === "POST")
      return { id: rndId("g-"), name: (payload.name as string) || "Новая группа", created_at: new Date().toISOString(), students: [] };
    return demoGroups;
  }
  // добавить/удалить студента в группе (демо)
  if (/^\/api\/v1\/groups\/[^/]+\/students$/.test(p) && method === "POST")
    return { id: rndId("s-"), name: (payload.name as string) || "Новый студент", checks_count: 0 };
  if (/^\/api\/v1\/groups\/[^/]+\/students\/[^/]+$/.test(p) && method === "DELETE") return {};
  if (/^\/api\/v1\/groups\/[^/]+$/.test(p) && method === "DELETE") return {};
  if (p === "/api/v1/checks" && method === "POST") {
    const n = sampleChecks.length;
    const created = {
      ...sampleChecks[sampleChecks.length - 1 - (n % 3)], id: `demo-${n + 1}`,
      work_title: (payload.work_title as string) || "Без названия",
      student_name: (payload.student_name as string) || "", student_id: (payload.student_id as string) || "",
      group_name: (payload.group_name as string) || "", status: "processing",
      created_at: new Date().toISOString(),
    };
    sampleChecks.unshift(created);
    setTimeout(() => {
      created.status = "done";
      created.completed_at = new Date().toISOString();
    }, 2500);
    return { id: created.id, status: created.status, filename: created.filename };
  }
  if (p === "/api/v1/checks" && method === "GET") return sampleChecks.map((c) => ({ ...c }));
  if (p.startsWith("/api/v1/checks/") && method === "GET") {
    const id = p.split("/").pop() || "demo-1";
    return { ...sampleReport, ...(id === "demo-1" ? {} : sampleChecks.find((c) => c.id === id)), id };
  }

  // Безопасные значения по умолчанию, чтобы страницы не падали
  if (method === "GET") return [];
  return {};
}
