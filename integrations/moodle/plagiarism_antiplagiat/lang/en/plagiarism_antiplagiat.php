<?php
defined('MOODLE_INTERNAL') || die();

$string['pluginname'] = 'Antiplagiat';
$string['antiplagiat'] = 'Antiplagiat';
$string['enabled'] = 'Enable Antiplagiat';
$string['enabled_help'] = 'Send student submissions to Antiplagiat for plagiarism and AI detection.';
$string['apiurl'] = 'API base URL';
$string['apiurl_help'] = 'Example: https://api.your-domain.com (without trailing slash)';
$string['apikey'] = 'API key';
$string['apikey_help'] = 'Organization API key from Antiplagiat admin → Integrations / API keys';
$string['webhooksecret'] = 'Webhook secret';
$string['webhooksecret_help'] = 'HMAC secret from Antiplagiat admin → Integrations (whsec_…)';
$string['similaritywarn'] = 'Similarity warning threshold (%)';
$string['similaritywarn_help'] = 'Highlight results at or above this plagiarism percent.';
$string['status_pending'] = 'Queued';
$string['status_processing'] = 'Checking…';
$string['status_done'] = 'Similarity: {$a->similarity}% · AI: {$a->ai}%';
$string['status_failed'] = 'Check failed';
$string['viewreport'] = 'Open report';
$string['privacy:metadata'] = 'Student submissions are sent to the Antiplagiat service for analysis.';
$string['antiplagiat:enable'] = 'Enable Antiplagiat in a course';
$string['antiplagiat:viewreport'] = 'View Antiplagiat report links';
