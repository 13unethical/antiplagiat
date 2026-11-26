<?php
/**
 * Webhook endpoint: Antiplagiat POSTs check.completed here.
 * Verifies X-Antiplagiat-Signature (HMAC-SHA256 of raw body).
 */
define('NO_MOODLE_COOKIES', true);

require_once(__DIR__ . '/../../config.php');

$raw = file_get_contents('php://input');
$secret = (string)get_config('plagiarism_antiplagiat', 'webhooksecret');
$sig = $_SERVER['HTTP_X_ANTIPLAGIAT_SIGNATURE'] ?? '';

if ($secret !== '') {
    $expected = hash_hmac('sha256', $raw, $secret);
    if (!hash_equals($expected, $sig)) {
        header('HTTP/1.1 401 Unauthorized');
        echo 'invalid signature';
        exit;
    }
}

$payload = json_decode($raw, true);
if (empty($payload['id'])) {
    header('HTTP/1.1 400 Bad Request');
    echo 'missing id';
    exit;
}

global $DB, $CFG;

$checkid = (string)$payload['id'];
$record = $DB->get_record('plagiarism_antiplagiat_files', ['checkid' => $checkid]);
if (!$record) {
    // Accept orphan webhooks silently to avoid retries storms.
    header('HTTP/1.1 200 OK');
    echo 'ok';
    exit;
}

$status = $payload['status'] ?? '';
$record->timemodified = time();
if ($status === 'done') {
    $record->status = 'done';
    $record->similarity = isset($payload['similarity_percent']) ? (float)$payload['similarity_percent'] : null;
    $record->aipercent = isset($payload['ai_percent']) ? (float)$payload['ai_percent'] : null;
    $api = rtrim((string)get_config('plagiarism_antiplagiat', 'apiurl'), '/');
    $record->reporturl = $api . '/api/v1/checks/' . rawurlencode($checkid) . '/verify';
    $record->errormsg = null;
} else if ($status === 'failed') {
    $record->status = 'failed';
    $record->errormsg = isset($payload['error_message']) ? substr((string)$payload['error_message'], 0, 500) : 'failed';
} else {
    $record->status = 'processing';
}

$DB->update_record('plagiarism_antiplagiat_files', $record);

header('Content-Type: application/json');
echo json_encode(['ok' => true]);
