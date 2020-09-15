offregister_openedx
===================
[![No Maintenance Intended](http://unmaintained.tech/badge.svg)](http://unmaintained.tech)
![Python version range](https://img.shields.io/badge/python-2.7%20|%203.4%20|%203.5%20|%203.6%20|%203.7%20|%203.8-blue.svg)
[![License](https://img.shields.io/badge/license-Apache--2.0%20OR%20MIT-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

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

## License

Licensed under either of

- Apache License, Version 2.0 ([LICENSE-APACHE](LICENSE-APACHE) or <https://www.apache.org/licenses/LICENSE-2.0>)
- MIT license ([LICENSE-MIT](LICENSE-MIT) or <https://opensource.org/licenses/MIT>)

at your option.

### Contribution

Unless you explicitly state otherwise, any contribution intentionally submitted
for inclusion in the work by you, as defined in the Apache-2.0 license, shall be
dual licensed as above, without any additional terms or conditions.
