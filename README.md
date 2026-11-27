# Markly

B2B SaaS для проверки студенческих работ на плагиат и ИИ-генерацию.
Целевые языки: **узбекский** (латиница / кириллица) и **русский**.

---

## Быстрый старт (разработка)

### Требования
- Python 3.11+
- Node.js 20+
- Docker Desktop

### 1. Инфраструктура

```bash
docker compose up -d postgres opensearch qdrant
```

### 2. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # заполните SECRET_KEY и другие переменные
alembic upgrade head
python seed.py                # создаёт admin@antiplagiat.uz / changeme123
uvicorn app.main:app --reload --port 8000
```

API-документация: http://localhost:8000/docs

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Открыть: http://localhost:3000

### Скрипт-обёртка

```bash
chmod +x start.sh stop.sh
./start.sh       # запускает всё сразу
./stop.sh        # останавливает
```

---

## Production (Docker Compose)

```bash
cp backend/.env.example backend/.env
# Отредактируйте backend/.env:
#   SECRET_KEY, BRAVE_API_KEY, SMTP_*, FRONTEND_URL

docker compose --profile prod up --build -d
```

| Сервис     | Порт  |
|------------|-------|
| Frontend   | 3000  |
| Backend    | 8000  |
| PostgreSQL | 5432  |
| OpenSearch | 9200  |
| Qdrant     | 6333  |

Остановить: `./stop.sh prod`

---

## Переменные окружения

Все переменные описаны в `backend/.env.example`.

| Переменная | Описание |
|---|---|
| `DATABASE_URL` | Строка подключения PostgreSQL |
| `SECRET_KEY` | Секрет для JWT (`openssl rand -hex 32`) |
| `FRONTEND_URL` | Базовый URL фронтенда (для ссылок в письмах) |
| `EMBED_MODEL` | `BAAI/bge-m3` (прод) или `BAAI/bge-small-en-v1.5` (dev) |
| `BRAVE_API_KEY` | Ключ Brave Search API (веб-поиск плагиата) |
| `SMTP_HOST` | SMTP-сервер. Пусто — письма печатаются в консоль |

---

## Роли

| Роль | Возможности |
|---|---|
| `superadmin` | Создаёт организации, приглашает `school_admin`, управляет тарифами, имперсонирует |
| `school_admin` | Управляет учителями в своей школе (лимит 10 мест), настройки, репозиторий |
| `teacher` | Загружает работы, просматривает свои проверки |

---

## Структура проекта

```
antiplagiat/
├── backend/
│   ├── app/
│   │   ├── api/v1/       # Роутеры FastAPI
│   │   ├── models/       # SQLAlchemy модели
│   │   ├── schemas/      # Pydantic схемы
│   │   ├── services/     # Бизнес-логика (парсер, детектор, поиск)
│   │   └── core/         # Security (JWT, bcrypt)
│   ├── alembic/          # Миграции (001–013)
│   ├── seed.py           # Начальные данные
│   └── requirements.txt
├── frontend/
│   └── src/app/          # Next.js 14 App Router
│       ├── (app)/        # Защищённые страницы
│       ├── login/
│       ├── invite/[token]/
│       └── verify/[id]/  # Публичная проверка подлинности отчёта
├── docker-compose.yml
├── start.sh
└── stop.sh
```

---

## Технологии

**Backend:** FastAPI · SQLAlchemy 2 async · asyncpg · Alembic · python-jose · bcrypt
**AI/ML:** fastembed (BGE-M3) · Qdrant · trafilatura · rapidfuzz
**Поиск:** OpenSearch 2 (шинглы) · Qdrant (векторный) · Brave Search API (веб)
**Frontend:** Next.js 14 · TypeScript · Tailwind CSS
**Инфра:** PostgreSQL 16 · Docker Compose
