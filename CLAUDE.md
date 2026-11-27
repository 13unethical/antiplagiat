# CLAUDE.md — инструкции для Claude Code

## Проект

B2B SaaS **Markly** (антиплагиат + ИИ-детектор) для школ и вузов Узбекистана.
Преподаватель загружает студенческую работу → система проверяет её на плагиат
и ИИ-генерацию, выдаёт отчёт с процентами совпадений, подсветкой фрагментов
и флагами подозрительных приёмов обхода.

Целевые языки: **узбекский** (uz-Latn / uz-Cyrl) и **русский**.
Два режима работы: веб-кабинет и публичный API.

- `SPEC.md` — полное ТЗ. Читать перед любой новой задачей.
- `PROJECT_STATUS.md` — подробное текущее состояние (таблицы, пайплайн, список эндпоинтов). Самый детальный документ.
- `README.md` — быстрый старт для разработчика.

---

## Правила работы

- **Никогда не запускай установку пакетов в фоне** (`brew install`, `pip install`, `npm install`) — пиши команду, пользователь выполняет сам.
- Не создавай файлы без необходимости. Редактируй существующие.
- Не добавляй комментарии, типизацию и docstring туда, где не трогал код.
- Не делай обратную совместимость и заглушки — просто меняй код.
- Новый этап начинай с короткого описания и ссылки на нужный раздел `SPEC.md`.

---

## Стек

| Слой | Технология |
|---|---|
| Backend | FastAPI + SQLAlchemy 2.x async + asyncpg + Alembic (Python 3.11+) |
| Frontend | Next.js 14 App Router + TypeScript + Tailwind CSS |
| База данных | PostgreSQL 16 |
| Auth | JWT (python-jose): access 30 мин + refresh 7 дней, bcrypt (passlib) |
| Поиск точный | OpenSearch 2 — шинглы (N-граммы слов), BM25 |
| Поиск семантический | Qdrant + fastembed (BGE-M3, мультиязычный) |
| Веб-поиск | Brave Search API + trafilatura + httpx + rapidfuzz |
| Парсинг | python-docx, pypdf, pytesseract + Pillow (OCR сканов) |
| ИИ-детектор | эвристика (v0, готово к дообучению XLM-RoBERTa) |
| Email | smtplib через asyncio.to_thread (fallback: print в консоль) |
| Инфра | Docker Compose |

Деградация без внешних сервисов: если OpenSearch / Qdrant / Brave недоступны,
соответствующий слой поиска просто отключается (graceful degradation), пайплайн не падает.

---

## Структура проекта

```
antiplagiat/
├── SPEC.md                 # Полное ТЗ
├── PROJECT_STATUS.md       # Детальное текущее состояние
├── CLAUDE.md               # Этот файл
├── README.md               # Быстрый старт
├── docker-compose.yml      # postgres + opensearch + qdrant + backend/frontend (--profile prod)
├── start.sh / stop.sh      # ./start.sh [prod]
│
├── backend/
│   ├── app/
│   │   ├── main.py         # FastAPI app, CORS, middleware API-лога
│   │   ├── config.py       # Settings (pydantic-settings, .env)
│   │   ├── database.py     # async engine + get_db dependency
│   │   ├── models/         # SQLAlchemy: organization, user, invitation, check, match,
│   │   │                   #   dispute, api_key, api_request_log, audit_log, corpus,
│   │   │                   #   repository_document, web_search_log, model_version,
│   │   │                   #   dataset_entry, mt_segment, group
│   │   ├── schemas/        # Pydantic v2: auth, check, corpus, invitation, match, organization
│   │   ├── api/v1/         # auth, checks, org, admin, invitations, corpus, groups
│   │   ├── core/
│   │   │   └── security.py # JWT deps: any_authenticated / school_admin_only / superadmin_only
│   │   └── services/
│   │       ├── parser.py        # docx/pdf/OCR → текст + карта позиций
│   │       ├── flagged.py       # подмена букв, невидимые символы, скрытый текст, разрядка
│   │       ├── normalizer.py    # NFC, апострофы uz, удаление невидимых символов
│   │       ├── language.py      # определение языка uz-Latn / uz-Cyrl / ru / mixed
│   │       ├── shingles.py      # шинглы для OpenSearch
│   │       ├── plagiarism.py    # антиплагиат по шинглам (OpenSearch)
│   │       ├── embedder.py      # fastembed + Qdrant (graceful degradation)
│   │       ├── semantic_search.py  # семантический + межъязыковой поиск
│   │       ├── web_search.py    # Brave API + trafilatura + кэш (graceful degradation)
│   │       ├── ai_detector.py   # ИИ-детектор (эвристика → XLM-R)
│   │       ├── mt_detector.py   # детектор машинного перевода
│   │       ├── stylometry.py    # стилометрия
│   │       ├── corpus.py        # корпус (OpenSearch)
│   │       ├── repository.py    # репозиторий работ школы
│   │       ├── processor.py     # ГЛАВНЫЙ пайплайн проверки
│   │       └── email.py         # SMTP
│   ├── alembic/versions/   # миграции 001–013
│   ├── seed.py             # admin@antiplagiat.uz / changeme123 (superadmin)
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
│
└── frontend/src/
    ├── lib/
    │   ├── api.ts          # apiFetch<T>() — все запросы, авто-refresh JWT при 401
    │   └── auth.ts         # getUser / getToken / setAuth / clearAuth
    └── app/
        ├── login/              # вход
        ├── invite/[token]/     # принятие приглашения
        ├── verify/[id]/        # ПУБЛИЧНАЯ проверка подлинности отчёта (без auth)
        └── (app)/              # защищённые страницы (layout с navbar по роли)
            ├── dashboard/
            ├── checks/         # история + new + [id] отчёт
            ├── profile/        # имя + пароль
            ├── settings/       # настройки проверок (read-only для teacher)
            ├── groups/         # группы и студенты
            ├── admin/          # school_admin: teachers, api-keys, checks, repository, settings
            └── super/          # superadmin: schools, plans, api-log, audit,
                                #   corpus, disputes, flagged, models, status
```

---

## Ключевые файлы

| Файл | Зачем |
|---|---|
| `backend/app/services/processor.py` | Пайплайн: parse → flagged → normalize → language → plagiarism (3 уровня) → AI/MT/стилометрия → отчёт |
| `backend/app/core/security.py` | JWT-зависимости и проверка ролей |
| `frontend/src/lib/api.ts` | Единая точка запросов к API + авто-refresh токена |

---

## Роли и права

| Роль | Эндпоинты | Возможности |
|---|---|---|
| `superadmin` | `/api/v1/admin/*` | Создаёт школы, приглашает их админов, тарифы и лимиты, видит всё, impersonation |
| `school_admin` | `/api/v1/org/*` | До 10 учителей, настройки школы, репозиторий, API-ключ, все проверки школы |
| `teacher` | — | Создаёт проверки, видит свои отчёты, скачивает |

Проверки `/api/v1/checks/*` доступны всем авторизованным (dep `any_authenticated`).

**Лимиты:** `seats_limit=10` на организацию (приглашённый занимает место, отключённый — нет);
`monthly_quota` на организацию + опциональный `personal_quota` на учителя. Превышение → HTTP 429.

---

## Запуск

### Dev (локально)

```bash
# 1. Инфраструктура
docker compose up -d postgres opensearch qdrant

# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # заполнить SECRET_KEY
alembic upgrade head
python seed.py                  # admin@antiplagiat.uz / changeme123
uvicorn app.main:app --reload --port 8000     # docs: http://localhost:8000/docs

# 3. Frontend
cd frontend && npm install && npm run dev      # http://localhost:3000
```

Или одним скриптом: `./start.sh` (остановить `./stop.sh`).

### Production (Docker)

```bash
cp backend/.env.example backend/.env    # заполнить все переменные
docker compose --profile prod up --build -d
./stop.sh prod
```

Порты: frontend 3000, backend 8000, postgres 5432, opensearch 9200, qdrant 6333.

---

## Переменные окружения (backend/.env)

Все описаны в `backend/.env.example`. Обязательно заменить в production:

- `SECRET_KEY` — `openssl rand -hex 32`
- `DATABASE_URL` — строка подключения PostgreSQL
- `BRAVE_API_KEY` — ключ Brave Search API (без него веб-поиск отключён)
- `SMTP_HOST` — SMTP-сервер (пусто → письма печатаются в консоль)
- `FRONTEND_URL` — базовый URL для ссылок в письмах
- `EMBED_MODEL` — `BAAI/bge-m3` (прод) или `BAAI/bge-small-en-v1.5` (dev)

---

## Что сделано

Пройдено **20 итераций разработки** — от скелета до полного Docker-стека, все закрыты.
Ниже они сгруппированы по 10 этапам раздела 9 `SPEC.md`.

| # | Этап | Статус |
|---|---|---|
| 1 | Скелет: FastAPI + Postgres + Next.js, auth, роли, организации, лимит 10, приглашения | ✅ |
| 2 | Загрузка и парсинг (docx/pdf/OCR), карта позиций, нормализация, Flagged-модуль | ✅ |
| 3 | Антиплагиат v1: шинглы + OpenSearch, корпус, исключения, подсчёт процента | ✅ |
| 4 | Отчёт: экран, DOCX/JSON/текст/PDF, QR-проверка подлинности | ✅ |
| 5 | Панели: admin школы (учителя, API-ключ, настройки) и superadmin (школы, лимиты, flagged) | ✅ |
| 6 | Публичный API + вебхуки (приём `webhook_url`) + документация `/docs` | ✅ |
| 7 | ИИ-детектор v0: эвристика, миграции под dataset/model_versions | ⚠️ v0 (нужен XLM-R) |
| 8 | Семантический и межъязыковой поиск: BGE-M3 + Qdrant | ✅ |
| 9 | Живой веб-поиск (Brave) + пополнение корпуса | ✅ |
| 10 | MT-детектор (heuristic), стилометрия, модель disputes | ✅ |

Поверх ТЗ также сделано: группы/студенты, профиль, CSV-экспорт и удаление проверок,
quota-bar, audit log, API-лог (middleware), тарифы, impersonation, status-page, Docker-стек.

---

## Что делать дальше

### Критично для прода
- **Фоновая очередь** (Redis + Celery/Arq): пайплайн сейчас блокирует HTTP-запрос.
- **Настоящий ИИ-детектор**: дообучить XLM-RoBERTa / mDeBERTa-v3 (SPEC.md разделы 3–4).
- **S3 / MinIO**: вынести файлы из локальной `./uploads/`.
- **Nginx** (reverse proxy + TLS) и **rate limiting** (`slowapi`).
- **Tesseract uz**: добавить `tesseract-ocr-uzb` и `tesseract-ocr-uzb-cyrl` в Dockerfile (сейчас только `rus`).

### Функциональность (в SPEC есть, в UI нет)
- Удаление организации суперадмином (эндпоинта нет).
- Кнопка Rotate API-ключа (эндпоинт `/org/api-key/rotate` есть, UI не доделан).
- Оспаривание результата (`POST /checks/{id}/dispute` есть, кнопки в UI нет).
- Side-by-side сравнение с источником в отчёте.
- Отправка вебхуков и email-уведомление учителю при готовности.
- PDF-отчёт с подсветкой; выделение межъязыковых совпадений отдельным цветом.
- Наполнение реального корпуса в OpenSearch.

### Технический долг
- Тесты (pytest + httpx AsyncClient) — хотя бы auth и checks.
- Сбор датасета для ИИ-детектора (человеческие тексты + ИИ-тексты uz/ru, SPEC.md раздел 3).
- Настоящий определитель языка (fastText LID / GlotLID вместо эвристики).
- Мониторинг: логирование ошибок (Sentry) и метрики (Prometheus).

---

## Дефолтный аккаунт (после `python seed.py`)

`admin@antiplagiat.uz` / `changeme123` — superadmin.
Первый шаг: создать школу → пригласить `school_admin` → тот приглашает учителей.
