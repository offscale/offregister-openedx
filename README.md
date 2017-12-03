offregister_openedx
===============

## Install dependencies

    pip install -r requirements.txt

## Install package

    pip install .

## Example config

    {
        "module": "offregister-openedx",
        "type": "fabric",
        "kwargs": {
          "PLATFORM_NAME": "edu by complicated.io",
          "LMS_ROOT_URL": "http://edu2.complicated.io",
          "CMS_ROOT_URL": "http://studio2.complicated.io",
          "LMS_SITE_NAME": "edu2.complicated.io",
          "CMS_SITE_NAME": "studio2.complicated.io",
          "PREVIEW_LMS_BASE": "preview.edu2.complicated.io",
          "MYSQL_PASSWORD": {
            "$ref": "env:MYSQL_PASSWORD"
          },
          "staff_user": "samuel",
          "staff_email": "samuel@offscale.io",
          "staff_pass": "3333333333",
          "LMS_LISTEN": 80,
          "CMS_LISTEN": 80,
          "LMS_EXTRA_BLOCK": "",
          "CMS_EXTRA_BLOCK": "",
          "reboot_storage_services": true,
          "db_migration": false,
          "cms_paver": false,
          "lms_paver": true
        }
    }
