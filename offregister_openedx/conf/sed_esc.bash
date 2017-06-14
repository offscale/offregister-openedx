#!/usr/bin/env bash
# Bash script because Fabric stuffs up escapes, even with shell_escape=False
sed -i 's,<h1>${Text(_(u"Welcome to the Open edX{registered_trademark} platform!")).format(registered_trademark=HTML("<sup style='\''font-size: 65%'\''>&reg;</sup>"))}</h1>,_0_openedx_banner_html,' '_0_filename'
sed -i '\|<p>${_("It works! This is the default homepage for this Open edX instance.")}</p>|d' '_0_filename'

sed -i 's/It works! This is the default homepage for this Open edX instance/default_mmmmm/g' '/edx/app/edxapp/edx-platform/conf/locale/en/LC_MESSAGES/django.po'
