# PROJECT STATUS — Антиплагиат

Полное описание проекта: что сделано, как устроено, что осталось.

---

## Что это за проект

**B2B SaaS-сервис** для школ и вузов Узбекистана.
Преподаватель загружает студенческую работу — система проверяет её на плагиат и ИИ-генерацию, выдаёт отчёт с процентами совпадений, подсветкой фрагментов и флагами подозрительных приёмов.

**Поддерживаемые языки:** узбекский (латиница uz-Latn + кириллица uz-Cyrl) и русский.

---

## Роли пользователей

| Роль | Кто | Что может |
|---|---|---|
| `superadmin` | владелец платформы | Создаёт школы, приглашает их админов, задаёт тарифы и лимиты, видит всё, может «войти как» любой пользователь |
| `school_admin` | директор/методист школы | Управляет учителями (до 10 мест), настраивает школу, видит все проверки школы, управляет репозиторием работ |
| `teacher` | учитель | Загружает работы, видит свои отчёты, скачивает PDF/DOCX |

---

## Стек технологий

| Слой | Что используется |
|---|---|
| **Backend** | Python 3.11, FastAPI, SQLAlchemy 2 async, asyncpg, Alembic |
| **Frontend** | Next.js 14 App Router, TypeScript, Tailwind CSS |
| **База данных** | PostgreSQL 16 |
| **Авторизация** | JWT access token (30 мин) + refresh token (7 дней), bcrypt |
| **Поиск плагиата (точный)** | OpenSearch 2 — шинглы (N-граммы слов), BM25 |
| **Поиск плагиата (семантический)** | Qdrant (векторная БД) + fastembed (модель BGE-M3, мультиязычная, 1.1 ГБ) |
| **Веб-поиск плагиата** | Brave Search API + trafilatura (парсинг страниц) + httpx |
| **ИИ-детектор** | эвристика (пока заглушка, готово к дообучению XLM-RoBERTa) |
| **Парсинг файлов** | python-docx (DOCX), pypdf (PDF), pytesseract + Pillow (OCR сканов) |
| **Email** | smtplib через asyncio.to_thread (fallback: print в консоль) |
| **Инфра** | Docker Compose (PostgreSQL + OpenSearch + Qdrant + опционально backend/frontend) |

---

## Архитектура backend

```
backend/app/
├── main.py          — FastAPI app, CORS, middleware логирования API
├── config.py        — все env-переменные (pydantic-settings)
├── database.py      — async engine, сессия, get_db dep
│
├── models/          — SQLAlchemy модели (13 таблиц + миграции)
├── schemas/         — Pydantic v2 схемы запросов/ответов
│
├── api/v1/
│   ├── auth.py        — /auth/*
│   ├── checks.py      — /checks/*
│   ├── org.py         — /org/* (school_admin + teacher)
│   ├── admin.py       — /admin/* (superadmin only)
│   ├── invitations.py — /invitations/*
│   ├── corpus.py      — /corpus/*
│   └── groups.py      — /groups/*
│
├── core/
│   └── security.py    — create_token, verify_token, bcrypt, FastAPI deps:
│                        any_authenticated / school_admin_only / superadmin_only
│
└── services/
    ├── processor.py      — ГЛАВНЫЙ ПАЙПЛАЙН: координирует все этапы проверки
    ├── parser.py         — DOCX / PDF / OCR → текст + карта позиций
    ├── flagged.py        — детектор манипуляций (подмена букв, невидимые символы)
    ├── normalizer.py     — NFC, апострофы, удаление невидимых символов
    ├── language.py       — определение языка (uz-Latn / uz-Cyrl / ru)
    ├── shingles.py       — разбиение на N-граммы для OpenSearch
    ├── plagiarism.py     — антиплагиат через OpenSearch (шинглы + BM25)
    ├── embedder.py       — fastembed + Qdrant (graceful degradation)
    ├── semantic_search.py— семантический и межъязыковой поиск
    ├── web_search.py     — Brave API → страницы → rapidfuzz + кэш
    ├── ai_detector.py    — ИИ-детектор (heuristic stub)
    ├── mt_detector.py    — детектор машинного перевода (heuristic)
    ├── stylometry.py     — стилометрия (длина предложений, словарное богатство)
    ├── corpus.py         — работа с OpenSearch корпусом
    ├── repository.py     — репозиторий работ школы
    └── email.py          — SMTP email с fallback в консоль
```

---

## База данных (13 миграций, 20+ таблиц)

| Таблица | Назначение |
|---|---|
| `organizations` | Школы: лимиты мест, квота проверок, тариф, срок действия |
| `users` | Пользователи: роль, статус (active/inactive), personal_quota |
| `invitations` | Токены приглашений (secrets.token_urlsafe, 7 дней) |
| `checks` | Проверки: статус, результаты, ai_percent, similarity_percent |
| `check_documents` | Текст и метаданные загруженного файла |
| `check_flags` | Флаги подозрительных приёмов (тип, severity, позиции) |
| `check_matches` | Совпадения с источниками (start/end позиции, процент) |
| `disputes` | Оспаривание результата проверки |
| `api_keys` | API-ключи школ (хранится только хэш) |
| `audit_log` | Журнал действий суперадмина (особенно impersonate) |
| `corpus_documents` | Корпус для поиска плагиата (OpenSearch) |
| `repository_documents` | Репозиторий работ школы (с согласия) |
| `web_search_logs` | Кэш результатов веб-поиска (TTL 7 дней) |
| `model_versions` | Версии ИИ-детектора |
| `dataset_entries` | Датасет для обучения ИИ-детектора |
| `mt_segments` | Сегменты машинного перевода |
| `api_request_log` | Лог всех API-запросов (для аналитики) |
| `org_settings` | Настройки по умолчанию для проверок в школе |
| `groups` | Группы/классы студентов |
| `students` | Студенты (имя, группа) |

---

## API эндпоинты

### Auth `/api/v1/auth/`
| Метод | URL | Кто | Что делает |
|---|---|---|---|
| POST | `/login` | все | Вход, возвращает access + refresh токены |
| POST | `/refresh` | все | Обновить access token |
| GET | `/me` | авторизован | Данные текущего пользователя |
| PATCH | `/me` | авторизован | Изменить имя или пароль |
| GET | `/me/stats` | авторизован | Статистика: проверок в этом месяце, квота |

### Checks `/api/v1/checks/`
| Метод | URL | Кто | Что делает |
|---|---|---|---|
| POST | `` | авторизован | Создать проверку (файл или текст) |
| GET | `` | авторизован | Список своих проверок |
| GET | `/export` | авторизован | Скачать CSV с историей проверок |
| GET | `/{id}` | авторизован | Детали проверки + результаты |
| GET | `/{id}/report` | авторизован | Скачать отчёт (PDF/DOCX/JSON/text) |
| DELETE | `/{id}` | авторизован | Удалить проверку |
| POST | `/{id}/exclude-source` | авторизован | Исключить источник из результата |
| GET | `/{id}/verify` | публично | Проверить подлинность отчёта по QR-коду |
| POST | `/{id}/dispute` | авторизован | Оспорить результат |

### Org `/api/v1/org/` (school_admin + teacher)
| Метод | URL | Кто | Что делает |
|---|---|---|---|
| GET | `/checks` | school_admin | Все проверки школы с email учителя |
| GET | `/stats` | school_admin | Статистика: учителя, проверки, квота |
| GET | `/teachers` | school_admin | Список учителей |
| POST | `/invitations` | school_admin | Пригласить учителя (email) |
| PATCH | `/teachers/{id}/status` | school_admin | Активировать / деактивировать учителя |
| PATCH | `/teachers/{id}/quota` | school_admin | Задать личный лимит проверок |
| GET/POST | `/api-key` | school_admin | Просмотр/создание API-ключа |
| POST | `/api-key/rotate` | school_admin | Перевыпустить API-ключ |
| GET | `/repository` | school_admin | Репозиторий работ школы |
| DELETE | `/repository/{id}` | school_admin | Удалить работу из репозитория |
| GET/PATCH | `/settings` | school_admin | Настройки проверок по умолчанию |

### Admin `/api/v1/admin/` (superadmin only)
| Метод | URL | Что делает |
|---|---|---|
| GET | `/stats` | Общая статистика платформы |
| POST | `/organizations` | Создать школу |
| GET | `/organizations` | Список всех школ |
| GET/PATCH | `/organizations/{id}` | Просмотр/изменение школы |
| POST | `/invitations` | Пригласить school_admin |
| GET | `/users` | Все пользователи |
| GET/PATCH | `/disputes/{id}` | Управление оспариваниями |
| GET/POST | `/model-versions` | Версии ИИ-детектора |
| PATCH | `/model-versions/{id}/activate` | Активировать версию модели |
| GET | `/dataset` | Датасет для обучения |
| GET | `/repository` | Общий репозиторий |
| GET | `/audit-log` | Журнал действий |
| GET | `/api-log` | Лог API-запросов |
| GET | `/api-log/stats` | Статистика API |
| POST | `/impersonate/{user_id}` | Войти как пользователь |

---

## Страницы фронтенда

### Публичные (без авторизации)
| URL | Страница |
|---|---|
| `/login` | Вход в систему |
| `/invite/[token]` | Принятие приглашения (создание пароля) |
| `/verify/[id]` | Публичная проверка подлинности отчёта по QR-коду |

### Для учителя
| URL | Страница |
|---|---|
| `/checks` | История проверок: список, поиск, сортировка, **CSV экспорт**, удаление, quota bar |
| `/checks/new` | Новая проверка: загрузка файла или ввод текста, опции (студент, группа), **quota bar** |
| `/checks/[id]` | Отчёт: similarity %, AI %, флаги, список совпадений, скачать PDF/DOCX/JSON |
| `/settings` | Настройки по умолчанию (read-only для учителя, только school_admin может менять) |
| `/groups` | Список групп и студентов |
| `/profile` | Смена отображаемого имени и пароля |

### Для school_admin (+ все страницы учителя)
| URL | Страница |
|---|---|
| `/admin` | Дашборд: статистика школы (учителя, проверки, квота) |
| `/admin/teachers` | Управление учителями: пригласить, отключить, задать личный лимит |
| `/admin/checks` | Все проверки школы с именем/email учителя |
| `/admin/repository` | Репозиторий работ: список, удаление |
| `/admin/settings` | Настройки школы по умолчанию (require_student, require_group и др.) |
| `/admin/api-keys` | API-ключ школы: просмотр, перевыпуск |

### Для superadmin
| URL | Страница |
|---|---|
| `/super` | Дашборд суперадмина: общая статистика |
| `/super/schools` | Список школ: создать, редактировать лимиты и тариф |
| `/super/plans` | Управление тарифами (quota, seats, valid_until) |
| `/super/status` | Status-page: состояние PostgreSQL, OpenSearch, Qdrant, диск |
| `/super/api-log` | Лог всех API-запросов + статистика |
| `/super/audit` | Журнал действий суперадмина |
| `/super/flagged` | Все проверки с флагами подозрительных приёмов |
| `/super/disputes` | Оспаривания результатов |
| `/super/models` | Версии ИИ-детектора |
| `/super/corpus` | Корпус документов для поиска |

---

## Пайплайн проверки (что происходит при загрузке работы)

```
1. Загрузка файла (DOCX / PDF / текст)
        ↓
2. Парсинг → текст + карта позиций (для подсветки)
   - DOCX: python-docx + разбор XML (видит скрытый текст, стили)
   - PDF: pypdf
   - Сканы: pytesseract (tesseract-ocr, языки rus + uzb + uzb_cyrl)
        ↓
3. Flagged-проверки (на сыром тексте, до нормализации)
   - Подмена букв (кириллица/латиница внутри слова)
   - Невидимые символы (U+200B, U+FEFF и др.)
   - Скрытый текст (белый цвет, font-size ≤ 2pt, w:vanish в DOCX)
   - Разрядка (буквы через пробел)
        ↓
4. Нормализация
   - Unicode NFC
   - Единые апострофы узбекского (ʻ / ʼ / ' / ` → ʻ)
   - Удаление невидимых символов
   - Приведение подменённых букв к письменности документа
        ↓
5. Определение языка (uz-Latn / uz-Cyrl / ru / mixed)
        ↓
6. Поиск плагиата — три уровня параллельно:
   а) Шинглы + OpenSearch (точные и близкие совпадения)
   б) Векторный поиск: Qdrant + BGE-M3 (парафраз, межъязыковой)
   в) Веб-поиск: Brave API → скачать страницы → rapidfuzz (кэш 7 дней)
        ↓
7. ИИ-детектор (эвристика → в будущем XLM-RoBERTa)
   + Детектор машинного перевода (heuristic)
   + Стилометрия (длина предложений, TTR, пунктуация)
        ↓
8. Сборка отчёта
   - similarity_percent, ai_percent, флаги, совпадения по источникам
   - Форматы: JSON (API), текст, DOCX, PDF с QR-кодом
```

---

## Безопасность

- **JWT**: access token 30 мин + refresh token 7 дней (хранятся в localStorage)
- **Авто-refresh**: `apiFetch` при 401 автоматически обновляет токен и повторяет запрос
- **Bcrypt**: пароли не хранятся в открытом виде
- **API-ключи школ**: в БД хранится только SHA-256 хэш, сам ключ показывается один раз
- **Квоты**: превышение → HTTP 429 (на уровне org + personal)
- **Impersonation**: записывается в audit_log с временной меткой и IP
- **CORS**: настроен только для FRONTEND_URL

---

## Деплой

### Разработка (локально)
```bash
docker compose up -d postgres opensearch qdrant

cd backend && source .venv/bin/activate
alembic upgrade head && python seed.py
uvicorn app.main:app --reload --port 8000

cd frontend && npm run dev
```
Или: `./start.sh`

### Production (всё в Docker)
```bash
cp backend/.env.example backend/.env  # заполнить переменные
docker compose --profile prod up --build -d
```

---

## Переменные окружения (backend/.env)

| Переменная | По умолчанию | Описание |
|---|---|---|
| `DATABASE_URL` | localhost/antiplagiat | Строка PostgreSQL |
| `SECRET_KEY` | dev-key | **Менять в проде!** `openssl rand -hex 32` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 30 | Время жизни access token |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 7 | Время жизни refresh token |
| `FRONTEND_URL` | http://localhost:3000 | Для ссылок в письмах |
| `UPLOAD_DIR` | ./uploads | Папка с загруженными файлами |
| `QDRANT_URL` | http://localhost:6333 | URL Qdrant |
| `EMBED_MODEL` | BAAI/bge-m3 | Модель эмбеддингов (bge-small-en для dev) |
| `BRAVE_API_KEY` | (пусто) | Brave Search API — без него веб-поиск отключён |
| `WEB_SEARCH_ENABLED` | true | Включить/выключить веб-поиск |
| `WEB_SEARCH_MAX_QUERIES` | 20 | Макс. запросов к Brave на проверку |
| `WEB_SEARCH_MAX_URLS` | 10 | Макс. страниц для анализа |
| `WEB_SEARCH_MATCH_THRESHOLD` | 70 | Мин. score совпадения (0–100) |
| `SMTP_HOST` | (пусто) | SMTP сервер. Пусто → письма в консоль |
| `SMTP_PORT` | 587 | Порт SMTP |
| `SMTP_USER` | (пусто) | Логин SMTP |
| `SMTP_PASSWORD` | (пусто) | Пароль SMTP |
| `SMTP_FROM` | noreply@antiplagiat.uz | Адрес отправителя |
| `SMTP_TLS` | true | STARTTLS (587) или plain (25) |

---

## Что НЕ сделано / что делать дальше

### Критично для запуска в прод

| Задача | Почему важно |
|---|---|
| **Redis + Celery или Arq** | Сейчас пайплайн проверки блокирует HTTP-запрос на несколько секунд. При реальной нагрузке нужна фоновая очередь. |
| **Настоящий ИИ-детектор** | Сейчас эвристика (длина предложений, частота слов). Нужно дообучить XLM-RoBERTa/mDeBERTa-v3 на реальных данных (см. SPEC.md разделы 3–4). |
| **S3 / MinIO** | Загруженные файлы лежат в `./uploads/` на диске. Для прода нужно объектное хранилище. |
| **Nginx** | Reverse proxy перед backend и frontend. TLS/HTTPS. |
| **Rate limiting** | Защита API от злоупотреблений (библиотека `slowapi`). |
| **Tesseract для узбекского** | В Dockerfile добавлен только `tesseract-ocr-rus`. Нужно `tesseract-ocr-uzb` и `tesseract-ocr-uzb-cyrl`. |

### Функциональность (есть в SPEC, не реализовано в UI)

| Задача | Статус |
|---|---|
| **Удаление организации** суперадмином | Эндпоинт не написан, UI нет |
| **Переиздание API-ключа** | Эндпоинт `/org/api-key/rotate` есть, UI страница `/admin/api-keys` есть, но кнопка Rotate не доделана |
| **Оспаривание** результата (`POST /checks/{id}/dispute`) | Эндпоинт есть, модель есть, кнопка в UI не добавлена |
| **Сравнение бок о бок** с источником в отчёте | Экран отчёта показывает список совпадений, но не side-by-side view |
| **Вебхуки** при готовности проверки | `webhook_url` принимается в опциях, но отправка не реализована |
| **Email учителю** при готовности отчёта | Инфраструктура email есть, уведомление не добавлено |
| **PDF-отчёт с подсветкой** | Сейчас DOCX + JSON + текст. PDF без подсветки (только базовый) |
| **Корпус (наполнение)** | Таблица есть, OpenSearch работает, но реальный корпус не загружен |
| **Межъязыковой поиск в отчёте** | Семантический поиск находит cross-lingual совпадения, но в UI они не выделяются отдельным цветом |

### Технический долг

| Задача | Описание |
|---|---|
| **Тесты** | Нет ни одного автоматического теста. Нужны pytest + httpx AsyncClient хотя бы для auth и checks. |
| **Сбор датасета** | Для обучения ИИ-детектора нужны человеческие тексты (студенческие работы до 2022) + ИИ-тексты на uz/ru. Подробности в SPEC.md раздел 3. |
| **Настоящий определитель языка** | Сейчас простая эвристика. Нужен fastText LID или GlotLID. |
| **OpenSearch корпус** | Шинглы реализованы, но без реального корпуса поиск плагиата работает только через веб. |
| **Мониторинг** | Нет логирования ошибок (Sentry или аналог), нет метрик (Prometheus). |

---

## Дефолтный аккаунт

После `python seed.py`:

**Email:** `admin@antiplagiat.uz`
**Пароль:** `changeme123`
**Роль:** `superadmin`

Первый шаг после входа: создать организацию (школу) → пригласить `school_admin` → тот приглашает учителей.
