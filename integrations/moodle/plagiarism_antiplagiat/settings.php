<?php
defined('MOODLE_INTERNAL') || die();

if ($ADMIN->fulltree) {
    $settings->add(new admin_setting_configcheckbox(
        'plagiarism_antiplagiat/enabled',
        get_string('enabled', 'plagiarism_antiplagiat'),
        get_string('enabled_help', 'plagiarism_antiplagiat'),
        0
    ));

    $settings->add(new admin_setting_configtext(
        'plagiarism_antiplagiat/apiurl',
        get_string('apiurl', 'plagiarism_antiplagiat'),
        get_string('apiurl_help', 'plagiarism_antiplagiat'),
        'https://api.example.com',
        PARAM_URL
    ));

    $settings->add(new admin_setting_configpasswordunmask(
        'plagiarism_antiplagiat/apikey',
        get_string('apikey', 'plagiarism_antiplagiat'),
        get_string('apikey_help', 'plagiarism_antiplagiat'),
        ''
    ));

    $settings->add(new admin_setting_configpasswordunmask(
        'plagiarism_antiplagiat/webhooksecret',
        get_string('webhooksecret', 'plagiarism_antiplagiat'),
        get_string('webhooksecret_help', 'plagiarism_antiplagiat'),
        ''
    ));

    $settings->add(new admin_setting_configtext(
        'plagiarism_antiplagiat/similaritywarn',
        get_string('similaritywarn', 'plagiarism_antiplagiat'),
        get_string('similaritywarn_help', 'plagiarism_antiplagiat'),
        '25',
        PARAM_FLOAT
    ));
}
