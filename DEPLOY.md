# Деплой

Архитектура не укладывается в один Vercel: **Vercel хостит только фронтенд**
(Next.js). Бэкенд (FastAPI + PostgreSQL + ML + фоновая обработка) ставится на
контейнерный хостинг. Ниже — связка **Vercel (фронт) + Render (бэкенд + Postgres)**.

Весь деплой выполняется под **твоими** аккаунтами (GitHub, Vercel, Render) —
вход и подтверждения делаешь ты.

---

## 0. Залить код на GitHub

Vercel и Render деплоят из git-репозитория.

```bash
cd ~/Desktop/antiplagiat
git init && git add -A && git commit -m "Initial"
# создать пустой репозиторий на github.com, затем:
git remote add origin https://github.com/<user>/antiplagiat.git
git branch -M main && git push -u origin main
```

`uploads/`, `.venv/`, `node_modules/` стоит добавить в `.gitignore`.

---

## 1. Бэкенд → Render (Docker + Postgres)

В репозитории есть `render.yaml` (Blueprint) — он сразу создаёт веб-сервис и БД.

1. Render Dashboard → **New → Blueprint** → выбрать репозиторий.
2. Render прочитает `render.yaml`: поднимет `antiplagiat-backend` (из
   `backend/Dockerfile`) и бесплатную базу `antiplagiat-db`.
3. `SECRET_KEY` сгенерируется, `DATABASE_URL` подставится из базы автоматически.
   Миграции (`alembic upgrade head`) запускаются при старте контейнера.
4. Дождаться деплоя → скопировать URL вида `https://antiplagiat-backend.onrender.com`.
5. (Опционально) создать супер-админа: Render → сервис → **Shell** →
   `python seed.py` (аккаунт `admin@antiplagiat.uz` / `changeme123`).

Замечания:
- Free-план Render — 512 МБ RAM; ML-модель может не влезть. Для демо хватает
  (ИИ-детектор работает без внешних сервисов; поиск плагиата деградирует мягко).
  Для продакшена — план starter+ и отдельные OpenSearch/Qdrant.
- Загруженные файлы лежат на диске контейнера и исчезают при редеплое — для
  продакшена нужен S3/MinIO (см. `PROJECT_STATUS.md`).

---

## 2. Фронтенд → Vercel

```bash
cd ~/Desktop/antiplagiat/frontend
npm i -g vercel        # если нет CLI
vercel login           # твой аккаунт
vercel                 # Root Directory оставить = текущая папка (frontend)
```

Или через сайт: Vercel → **Add New → Project** → импортировать репозиторий →
**Root Directory = `frontend`** (важно, иначе Vercel не найдёт Next.js).

Переменная окружения в настройках проекта Vercel:

```
NEXT_PUBLIC_API_URL = https://antiplagiat-backend.onrender.com
```

Затем **Deploy**. Прод-билд проверен локально и проходит.

---

## 3. Связать домены

1. Скопировать итоговый адрес Vercel (например `https://antiplagiat.vercel.app`).
2. В Render у `antiplagiat-backend` задать `FRONTEND_URL` = этот адрес →
   **Save** (сервис перезапустится). Это нужно для CORS и ссылок в письмах.
   Превью-домены `*.vercel.app` уже разрешены в CORS по маске.

Готово: фронт на Vercel ходит в API на Render.

---

## Что работает в облаке без доп. сервисов

| Возможность | Статус |
|---|---|
| Авторизация, роли, организации, приглашения | ✅ |
| Загрузка, парсинг, Flagged, отчёты DOCX/PDF с полным текстом | ✅ |
| ИИ-детектор (эвристика) | ✅ |
| Антиплагиат по корпусу (OpenSearch) | ⚠️ нужен отдельный OpenSearch |
| Семантический/межъязыковой (Qdrant + BGE-M3) | ⚠️ нужен Qdrant + RAM |
| Живой веб-поиск (Brave) | ⚠️ нужен `BRAVE_API_KEY` |

Без OpenSearch/Qdrant антиплагиат находит 0 совпадений и подсвечивает только
цитаты — ИИ-отчёт при этом полноценный.
