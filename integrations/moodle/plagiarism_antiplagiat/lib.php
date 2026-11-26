<?php
defined('MOODLE_INTERNAL') || die();

require_once($CFG->dirroot . '/plagiarism/lib.php');

class plagiarism_plugin_antiplagiat extends plagiarism_plugin {

    public function get_links($linkarray) {
        global $DB, $OUTPUT;

        if (empty(get_config('plagiarism_antiplagiat', 'enabled'))) {
            return '';
        }
        if (empty($linkarray['cmid']) || empty($linkarray['userid'])) {
            return '';
        }

        $cm = (int)$linkarray['cmid'];
        $userid = (int)$linkarray['userid'];
        $identifier = !empty($linkarray['file'])
            ? $linkarray['file']->get_pathnamehash()
            : ('online_' . $cm . '_' . $userid);

        $record = $DB->get_record('plagiarism_antiplagiat_files', [
            'cm' => $cm,
            'userid' => $userid,
            'identifier' => $identifier,
        ]);
        if (!$record) {
            return '';
        }

        $out = html_writer::start_span('plagiarism_antiplagiat');
        if ($record->status === 'done') {
            $a = (object)[
                'similarity' => format_float((float)$record->similarity, 1),
                'ai' => format_float((float)$record->aipercent, 1),
            ];
            $warn = (float)get_config('plagiarism_antiplagiat', 'similaritywarn');
            $class = ((float)$record->similarity >= $warn) ? 'text-danger' : 'text-success';
            $out .= html_writer::span(get_string('status_done', 'plagiarism_antiplagiat', $a), $class);
            if (!empty($record->reporturl)) {
                $out .= ' ' . html_writer::link(
                    $record->reporturl,
                    get_string('viewreport', 'plagiarism_antiplagiat'),
                    ['target' => '_blank', 'rel' => 'noopener']
                );
            }
        } else if ($record->status === 'failed') {
            $out .= html_writer::span(get_string('status_failed', 'plagiarism_antiplagiat'), 'text-danger');
        } else if ($record->status === 'processing') {
            $out .= get_string('status_processing', 'plagiarism_antiplagiat');
        } else {
            $out .= get_string('status_pending', 'plagiarism_antiplagiat');
        }
        $out .= html_writer::end_span();
        return $out;
    }

    public function event_handler($eventdata) {
        if (empty(get_config('plagiarism_antiplagiat', 'enabled'))) {
            return true;
        }
        // Handled via assessable_submitted observer / cron queue in locallib.
        return true;
    }
}

/**
 * Hook called when a file is submitted for plagiarism checking.
 */
function plagiarism_antiplagiat_handle_submissions($event) {
    require_once(__DIR__ . '/locallib.php');
    plagiarism_antiplagiat_queue_event($event);
}

function plagiarism_antiplagiat_coursemodule_standard_elements($formwrapper, $mform) {
    // Optional per-activity enable checkbox can be added later.
}

function plagiarism_antiplagiat_coursemodule_edit_post_actions($data, $course) {
    return $data;
}
