# Moodle: плагин `plagiarism_antiplagiat`

Плагин подсистемы **Plagiarism plugins** для Moodle 4.x. При сдаче задания файл/текст уходит в Antiplagiat API; по вебхуку проценты и ссылка на отчёт появляются рядом с работой в журнале оценок.

## Установка

1. В кабинете Antiplagiat (роль school_admin) откройте **Интеграции**:
   - выпустите **API-ключ** (раздел API-ключи);
   - выпустите **Webhook secret** (кнопка «Секрет вебхука»).
2. Скачайте ZIP: `plagiarism_antiplagiat.zip` (собирается из этой папки) **или** скопируйте каталог:
   ```bash
   cp -R plagiarism_antiplagiat /path/to/moodle/plagiarism/antiplagiat
   ```
3. В Moodle: **Администрирование → Уведомления** — завершите установку плагина.
4. **Администрирование → Плагины → Плагиатизм → Антиплагиат**:
   - Включить: да
   - API base URL: `https://<ваш-api>` (без `/` в конце)
   - API key: ключ организации
   - Webhook secret: `whsec_…`
5. Включите проверку на плагиат в настройках задания (Assign).

Callback URL (формируется автоматически):

```
https://<ваш-moodle>/plagiarism/antiplagiat/callback.php
```

## Сборка ZIP

```bash
cd integrations/moodle
zip -r plagiarism_antiplagiat.zip plagiarism_antiplagiat \
  -x '*.DS_Store' -x '*/.git/*'
```

## Поток

1. Студент сдаёт файл → событие `assessable_uploaded` / `assessable_submitted`.
2. Плагин: `POST {api}/api/v1/checks` с `X-API-Key` и `webhook_url=…/callback.php`.
3. Antiplagiat шлёт `POST callback` с заголовком `X-Antiplagiat-Signature`.
4. Плагин пишет similarity / AI % в `plagiarism_antiplagiat_files` и показывает их через `get_links()`.
