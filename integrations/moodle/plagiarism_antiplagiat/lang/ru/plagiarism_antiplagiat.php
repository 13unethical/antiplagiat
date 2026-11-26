<?php
defined('MOODLE_INTERNAL') || die();

$string['pluginname'] = 'Антиплагиат';
$string['antiplagiat'] = 'Антиплагиат';
$string['enabled'] = 'Включить Антиплагиат';
$string['enabled_help'] = 'Отправлять работы студентов в Антиплагиат на проверку плагиата и ИИ.';
$string['apiurl'] = 'Базовый URL API';
$string['apiurl_help'] = 'Пример: https://api.your-domain.com (без слэша в конце)';
$string['apikey'] = 'API-ключ';
$string['apikey_help'] = 'Ключ организации из кабинета Антиплагиат → Интеграции / API-ключи';
$string['webhooksecret'] = 'Секрет вебхука';
$string['webhooksecret_help'] = 'HMAC-секрет из кабинета → Интеграции (whsec_…)';
$string['similaritywarn'] = 'Порог предупреждения по совпадениям (%)';
$string['similaritywarn_help'] = 'Подсвечивать результат при проценте плагиата не ниже этого значения.';
$string['status_pending'] = 'В очереди';
$string['status_processing'] = 'Проверка…';
$string['status_done'] = 'Совпадения: {$a->similarity}% · ИИ: {$a->ai}%';
$string['status_failed'] = 'Ошибка проверки';
$string['viewreport'] = 'Открыть отчёт';
$string['privacy:metadata'] = 'Работы студентов отправляются в сервис Антиплагиат для анализа.';
$string['antiplagiat:enable'] = 'Включать Антиплагиат в курсе';
$string['antiplagiat:viewreport'] = 'Видеть ссылки на отчёты Антиплагиат';
