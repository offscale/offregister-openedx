#!/usr/bin/env bash

sudo -u www-data /edx/app/edxapp/venvs/edxapp/bin/python /edx/app/edxapp/edx-platform/manage.py lms --settings aws dbshell

update auth_user set is_active=true, is_staff=true, is_superuser=true where email like '%au';
update auth_user set is_active=true, is_staff=true, is_superuser=true where email like '%gmail%';
