# Canvas: LTI 1.3 + Plagiarism Detection

Антиплагиат подключается к Canvas как внешний LTI 1.3 tool с placement **similarity_detection**. После сдачи работы Canvas (или коннектор) передаёт submission на API; по завершении проверки originality score и ссылка на отчёт уходят обратно в SpeedGrader.

## 1. Подготовка API

В `.env` бэкенда:

```
API_PUBLIC_URL=https://api.ваш-домен.uz
FRONTEND_URL=https://app.ваш-домен.uz
LTI_PRIVATE_KEY_PATH=./lti_private.pem
```

Ключ `lti_private.pem` создаётся автоматически при первом запросе JWKS.

Публичные URL:

| Назначение | URL |
|---|---|
| JWKS | `{API}/.well-known/jwks.json` |
| OIDC login | `{API}/api/v1/lti/oidc/login` |
| Launch | `{API}/api/v1/lti/launch` |
| Developer Key JSON | `{API}/api/v1/lti/config/canvas.json` |

## 2. Developer Key в Canvas

1. **Admin → Developer Keys → + LTI Key → Enter JSON**  
   Вставьте содержимое `GET /api/v1/lti/config/canvas.json` (или кнопка «Скачать JSON» в кабинете → Интеграции → Canvas).
2. Включите ключ, скопируйте **Client ID**.
3. **Admin → Settings → Apps → + App → By Client ID** — вставьте Client ID, подтвердите Deployment.

## 3. Регистрация платформы в Антиплагиат

В кабинете school_admin → **Интеграции → Canvas** заполните:

- Issuer — обычно `https://canvas.instructure.com` или URL инстанса
- Client ID — из Developer Key
- Deployment ID(s)
- JWKS URL — `https://<canvas>/api/lti/security/jwks`
- Auth login URL — `https://<canvas>/api/lti/authorize_redirect`
- Auth token URL — `https://<canvas>/login/oauth2/token`
- API base URL — `https://<canvas>`

## 4. Assignment

В задании Canvas: **Plagiarism Review → Antiplagiat**. Студенты сдают файлы как обычно; процент появляется в SpeedGrader.

Коннектор / сервис plagiarism платформы может также вызывать:

```
POST /api/v1/lti/canvas/submissions
Authorization: Bearer <JWT> или X-API-Key
{
  "platform_id": "<uuid>",
  "assignment_id": "123",
  "submission_id": "456",
  "user_id": "789",
  "user_name": "Иванов",
  "file_url": "https://...",
  "originality_report_url": "https://canvas.../originality_report"
}
```

После `check.completed` бэкенд делает `PUT` originality report (score = similarity_percent, launch = `/verify/{id}`).
