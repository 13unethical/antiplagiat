<?php
defined('MOODLE_INTERNAL') || die();

$observers = [
    [
        'eventname' => '\assignsubmission_file\event\assessable_uploaded',
        'callback'  => 'plagiarism_antiplagiat_handle_submissions',
        'includefile' => '/plagiarism/antiplagiat/lib.php',
    ],
    [
        'eventname' => '\assignsubmission_onlinetext\event\assessable_uploaded',
        'callback'  => 'plagiarism_antiplagiat_handle_submissions',
        'includefile' => '/plagiarism/antiplagiat/lib.php',
    ],
    [
        'eventname' => '\mod_assign\event\assessable_submitted',
        'callback'  => 'plagiarism_antiplagiat_handle_submissions',
        'includefile' => '/plagiarism/antiplagiat/lib.php',
    ],
];
