<?php
defined('MOODLE_INTERNAL') || die();

/**
 * Queue / send a submission to Antiplagiat API.
 *
 * @param \core\event\base $event
 */
function plagiarism_antiplagiat_queue_event($event) {
    global $DB, $CFG;

    if (empty(get_config('plagiarism_antiplagiat', 'enabled'))) {
        return;
    }
    $apiurl = rtrim((string)get_config('plagiarism_antiplagiat', 'apiurl'), '/');
    $apikey = (string)get_config('plagiarism_antiplagiat', 'apikey');
    if ($apiurl === '' || $apikey === '') {
        return;
    }

    $data = $event->get_data();
    $cmid = (int)($data['contextinstanceid'] ?? 0);
    $userid = (int)($data['userid'] ?? 0);
    if (!$cmid || !$userid) {
        return;
    }

    $user = $DB->get_record('user', ['id' => $userid], 'id, firstname, lastname, idnumber');
    $studentname = $user ? fullname($user) : '';
    $studentid = $user && $user->idnumber ? $user->idnumber : (string)$userid;

    $files = [];
    if (!empty($data['other']['pathnamehashes']) && is_array($data['other']['pathnamehashes'])) {
        foreach ($data['other']['pathnamehashes'] as $hash) {
            $fs = get_file_storage();
            $file = $fs->get_file_by_hash($hash);
            if ($file && !$file->is_directory()) {
                $files[] = $file;
            }
        }
    }

    $callback = $CFG->wwwroot . '/plagiarism/antiplagiat/callback.php';

    if (empty($files) && !empty($data['other']['content'])) {
        plagiarism_antiplagiat_send_text(
            $apiurl, $apikey, $callback, $cmid, $userid,
            $data['other']['content'], $studentname, $studentid, 'online_' . $cmid . '_' . $userid
        );
        return;
    }

    foreach ($files as $file) {
        plagiarism_antiplagiat_send_file(
            $apiurl, $apikey, $callback, $cmid, $userid,
            $file, $studentname, $studentid
        );
    }
}

function plagiarism_antiplagiat_send_file($apiurl, $apikey, $callback, $cmid, $userid, $file, $studentname, $studentid) {
    global $DB;

    $identifier = $file->get_pathnamehash();
    $now = time();
    $record = $DB->get_record('plagiarism_antiplagiat_files', [
        'cm' => $cmid, 'userid' => $userid, 'identifier' => $identifier,
    ]);
    if (!$record) {
        $record = (object)[
            'cm' => $cmid,
            'userid' => $userid,
            'identifier' => $identifier,
            'status' => 'pending',
            'timecreated' => $now,
            'timemodified' => $now,
        ];
        $record->id = $DB->insert_record('plagiarism_antiplagiat_files', $record);
    }

    $tmp = make_request_directory() . '/' . $file->get_filename();
    $file->copy_content_to($tmp);

    $curl = new curl();
    $curl->setHeader(['X-API-Key: ' . $apikey]);
    $response = $curl->post($apiurl . '/api/v1/checks', [
        'file' => new curlfile($tmp, $file->get_mimetype(), $file->get_filename()),
        'work_title' => $file->get_filename(),
        'student_name' => $studentname,
        'student_id' => $studentid,
        'webhook_url' => $callback,
    ]);

    $decoded = json_decode($response, true);
    if (!empty($decoded['id'])) {
        $record->checkid = $decoded['id'];
        $record->status = 'processing';
        $record->timemodified = time();
        $DB->update_record('plagiarism_antiplagiat_files', $record);
    } else {
        $record->status = 'failed';
        $record->errormsg = substr((string)$response, 0, 500);
        $record->timemodified = time();
        $DB->update_record('plagiarism_antiplagiat_files', $record);
    }
}

function plagiarism_antiplagiat_send_text($apiurl, $apikey, $callback, $cmid, $userid, $text, $studentname, $studentid, $identifier) {
    global $DB;

    $now = time();
    $record = $DB->get_record('plagiarism_antiplagiat_files', [
        'cm' => $cmid, 'userid' => $userid, 'identifier' => $identifier,
    ]);
    if (!$record) {
        $record = (object)[
            'cm' => $cmid,
            'userid' => $userid,
            'identifier' => $identifier,
            'status' => 'pending',
            'timecreated' => $now,
            'timemodified' => $now,
        ];
        $record->id = $DB->insert_record('plagiarism_antiplagiat_files', $record);
    }

    $curl = new curl();
    $curl->setHeader(['X-API-Key: ' . $apikey]);
    $response = $curl->post($apiurl . '/api/v1/checks', [
        'text_content' => $text,
        'work_title' => 'Online text',
        'student_name' => $studentname,
        'student_id' => $studentid,
        'webhook_url' => $callback,
    ]);

    $decoded = json_decode($response, true);
    if (!empty($decoded['id'])) {
        $record->checkid = $decoded['id'];
        $record->status = 'processing';
        $record->timemodified = time();
        $DB->update_record('plagiarism_antiplagiat_files', $record);
    } else {
        $record->status = 'failed';
        $record->errormsg = substr((string)$response, 0, 500);
        $record->timemodified = time();
        $DB->update_record('plagiarism_antiplagiat_files', $record);
    }
}
