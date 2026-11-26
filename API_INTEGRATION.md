# Интеграция по API (Canvas, Moodle и любые LMS)

Публичный REST API для встраивания проверки на плагиат и ИИ в сторонние системы —
LMS (Canvas, Moodle, Google Classroom), приёмные порталы, собственные сервисы вуза.
Интеграция **server-to-server**: платформа шлёт работу студента на наш API, получает
отчёт синхронно (поллинг) или по вебхуку (callback).

Базовый URL: `https://<ваш-домен>/api/v1`
Интерактивная документация (Swagger): `https://<ваш-домен>/docs`

---

## 1. Аутентификация — API-ключ

Все запросы к API авторизуются заголовком `X-API-Key`. Ключ выдаётся **на организацию**
(вуз/школу) её администратором в кабинете: раздел **API-ключ** → кнопка выпуска/ротации.

```
X-API-Key: ak_live_8f2c...a91
```

- Один ключ = одна организация. Все проверки идут на её квоту и в её репозиторий.
- Ключ хранится у нас только в виде SHA-256-хэша — восстановить нельзя, можно только перевыпустить.
- Перевыпуск: `POST /api/v1/org/api-key/rotate` (старый ключ сразу отключается).
- Каждый запрос с ключом пишется в журнал API (кто, когда, какой эндпоинт, статус) — для аудита.

> JWT (логин/пароль преподавателя) — для веб-кабинета. Для машинной интеграции используйте API-ключ.

---

## 2. Эндпоинты

| Метод | Путь | Назначение |
|---|---|---|
| `POST` | `/api/v1/checks` | Создать проверку (файл .docx/.pdf **или** текст) |
| `GET` | `/api/v1/checks/{id}` | Получить полный отчёт |
| `GET` | `/api/v1/checks` | Список проверок организации |
| `GET` | `/api/v1/checks/{id}/report?format=pdf\|docx\|json` | Скачать отчёт файлом |
| `GET` | `/api/v1/checks/{id}/verify` | **Публичная** проверка подлинности отчёта (без ключа, для QR) |

---

## 3. Полный поток интеграции

```
LMS                         Antiplagiat API
 │  POST /checks (файл + webhook_url)   │
 │ ───────────────────────────────────▶ │  201 { id, status: "pending" }
 │                                       │  … пайплайн: parse→plagiarism→AI→MT→стилометрия
 │        webhook: check.completed       │
 │ ◀─────────────────────────────────── │  POST webhook_url { id, similarity_percent, ai_percent, … }
 │  GET /checks/{id}  (за полным отчётом)│
 │ ───────────────────────────────────▶ │  200 { matches[], flags[], ai_percent, … }
```

Поддерживаются **оба** способа узнать о готовности:
- **Вебхук** (рекомендуется): передайте `webhook_url` при создании — мы сами дёрнем его, когда готово.
- **Поллинг**: периодически запрашивайте `GET /checks/{id}`, пока `status != "pending"`.

### 3.1. Создать проверку

`POST /api/v1/checks` — `multipart/form-data`.

| Поле | Тип | Описание |
|---|---|---|
| `file` | файл | `.docx` или `.pdf`, до 50 МБ (**или** `text_content`) |
| `text_content` | строка | Текст напрямую, 50–500 000 символов (**или** `file`) |
| `work_title` | строка | Название работы |
| `student_name` | строка | ФИО студента (для отчёта) |
| `student_id` | строка | Внешний ID студента в LMS |
| `group_name` | строка | Группа/курс |
| `webhook_url` | строка | URL для callback по готовности |
| `exclude_quotes` | bool | Не считать цитаты (по умолч. `false`) |
| `exclude_bibliography` | bool | Не считать список литературы (по умолч. `true`) |
| `save_to_repository` | bool | Сохранить работу в репозиторий вуза (по умолч. `false`) |
| `min_match_words` | int | Мин. длина совпадения в словах (по умолч. `8`) |

```bash
curl -X POST https://<домен>/api/v1/checks \
  -H "X-API-Key: $ANTIPLAGIAT_KEY" \
  -F "file=@coursework.docx" \
  -F "work_title=Курсовая по МСФО" \
  -F "student_name=Иван Петров" \
  -F "student_id=lms-2024-0152" \
  -F "group_name=ФК-21" \
  -F "webhook_url=https://lms.univ.uz/hooks/antiplagiat"
```

Ответ `201`:
```json
{ "id": "7c9e...", "status": "pending", "filename": "coursework.docx" }
```

### 3.2. Получить отчёт

`GET /api/v1/checks/{id}` → `200`:
```json
{
  "id": "7c9e...",
  "status": "done",
  "language": "ru",
  "word_count": 3735,
  "similarity_percent": 14.0,
  "similarity_sources_count": 3,
  "ai_percent": 78.0,
  "ai_model_version": "distilbert-ml-onnx-v1",
  "mt_flag": true,
  "mt_percent": 11.0,
  "stylometry_score": 0.41,
  "matches": [
    { "start_char": 0, "end_char": 58, "matched_text": "…",
      "source_title": "kwpublications.com", "source_url": "https://…",
      "source_lang": "ru", "match_kind": "exact", "score": 0.62 }
  ],
  "flags": [
    { "type": "homoglyph", "severity": "high", "count": 4 }
  ]
}
```

### 3.3. Проверка подлинности (anti-fraud)

Каждый отчёт имеет публичную ссылку/QR: `GET /api/v1/checks/{id}/verify` — работает **без ключа**.
Любой (деканат, комиссия) может убедиться, что отчёт настоящий, а не подрисован в фоторедакторе.

---

## 4. Вебхук (callback)

Когда проверка завершена, мы делаем `POST` на ваш `webhook_url`:

```
POST <webhook_url>
Content-Type: application/json
X-Antiplagiat-Event: check.completed
X-Antiplagiat-Signature: <hmac-sha256-hex>
```

Подпись: `HMAC-SHA256(raw_body, org.webhook_secret)` в hex. Секрет выпускается в кабинете
**Интеграции LMS** (`POST /api/v1/org/integrations/webhook-secret/rotate`). Доставка — до 3 попыток
с backoff. Ответьте `2xx`.

```json
{
  "id": "7c9e...",
  "status": "done",
  "filename": "coursework.docx",
  "work_title": "Курсовая по МСФО",
  "student_name": "Иван Петров",
  "student_id": "lms-2024-0152",
  "group_name": "ФК-21",
  "similarity_percent": 14.0,
  "similarity_sources_count": 3,
  "ai_percent": 78.0,
  "ai_model_version": "distilbert-ml-onnx-v1",
  "mt_flag": true,
  "mt_percent": 11.0,
  "word_count": 3735,
  "language": "ru",
  "error_message": null,
  "completed_at": "2026-11-26T00:42:11+00:00"
}
```

---

## 5. Moodle и Canvas — готовые поставки

Кабинет school_admin → **Интеграции LMS** (`/admin/integrations`): вкладки Moodle / Canvas / API,
выпуск webhook secret, регистрация LTI-платформ, JSON Developer Key.

### Moodle (плагин)

Каталог: [`integrations/moodle/plagiarism_antiplagiat/`](integrations/moodle/plagiarism_antiplagiat/)  
Инструкция: [`integrations/moodle/README.md`](integrations/moodle/README.md)

1. Установить в `moodle/plagiarism/antiplagiat` (или ZIP).
2. В настройках плагина: API URL, API-ключ организации, webhook secret.
3. При сдаче Assign плагин шлёт файл на `POST /checks` с `webhook_url=…/callback.php`.
4. Callback проверяет `X-Antiplagiat-Signature` и показывает % плагиата / ИИ в UI задания.

### Canvas (LTI 1.3 Plagiarism Detection)

Инструкция: [`integrations/canvas/README.md`](integrations/canvas/README.md)

Публичные URL tool:

| Назначение | Путь |
|---|---|
| JWKS | `GET /.well-known/jwks.json` |
| OIDC login | `GET|POST /api/v1/lti/oidc/login` |
| Launch | `POST /api/v1/lti/launch` |
| Developer Key JSON | `GET /api/v1/lti/config/canvas.json` |
| Ingest submission | `POST /api/v1/lti/canvas/submissions` |

После проверки бэкенд пушит originality report в Canvas (score = `similarity_percent`, launch =
публичный `/verify/{id}`).

Env: `API_PUBLIC_URL`, `LTI_PRIVATE_KEY_PATH` (см. `backend/.env.example`).

---

## 6. Пример коннектора (Python)

```python
import time, requests

API = "https://<домен>/api/v1"
KEY = "ak_live_..."
H = {"X-API-Key": KEY}

# 1. Отправить работу
with open("coursework.docx", "rb") as f:
    r = requests.post(f"{API}/checks", headers=H,
        files={"file": f},
        data={"work_title": "Курсовая", "student_id": "lms-0152",
              "student_name": "Иван Петров", "group_name": "ФК-21"})
check_id = r.json()["id"]

# 2. Дождаться (поллинг; в проде лучше webhook_url)
while True:
    rep = requests.get(f"{API}/checks/{check_id}", headers=H).json()
    if rep["status"] != "pending":
        break
    time.sleep(3)

print("Плагиат:", rep["similarity_percent"], "% | ИИ:", rep["ai_percent"], "%")
# → проставить в LMS и дать ссылку на отчёт /checks/{id}/verify
```

---

## 7. Лимиты и ошибки

- Квоты: месячный лимит на организацию (`monthly_quota`) и опционально персональный. Превышение → `429`.
- Форматы файлов: `.docx`, `.pdf` (PDF со сканами проходит OCR). Размер ≤ 50 МБ. Текст ≤ 500 000 символов.
- Коды: `401` неверный ключ · `403` нет прав/нет активного админа у организации · `400` плохой ввод ·
  `429` превышена квота.

---

## 8. Безопасность: доступ только для преподавателей

Студент **не может** абузить систему, потому что у него нет доступа:
- Аккаунты и API-ключи есть только у ролей `superadmin` / `school_admin` / `teacher`.
- Проверки создаёт преподаватель (или LMS от имени вуза по ключу организации) — студент не видит
  ни API, ни порога срабатывания, ни внутренней логики.
- Нельзя «подобрать» текст под детектор: подсчёт идёт на сервере, веса модели и корпус недоступны.
- Каждый отчёт подписан и проверяем через публичный `/verify` — подделать нельзя.
