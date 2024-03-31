# -*- coding: utf-8 -*-
# Based off Sep 11, 2020 (v36) version of
# https://openedx.atlassian.net/wiki/spaces/OpenOPS/pages/146440579/Native+Open+edX+platform+Ubuntu+16.04+64+bit+Installation

from os import environ

from fabric.contrib.files import exists
from offregister_fab_utils.apt import apt_depends
from offutils import ensure_quoted

EDX_RELEASE_REF = environ.get("EDX_RELEASE_REF", "open-release/juniper.3")
CONFIGURATION_DIR = "/tmp/edx/configuration"


def system_install0(c, *args, **kwargs):
    apt_depends(
        c,
        "curl",
        "gnupg",
        "git",
        "software-properties-common",
        "python-pip",
        "python-dev",
    )
    c.sudo("python -m pip install -U pyopenssl")


def config_yml1(c, *args, **kwargs):
    # if exists(c, runner=c.run, path="config.yml"): return False

    c.run(
        'printf \'EDXAPP_LMS_BASE: "%s"\nEDXAPP_CMS_BASE: "%s"\' '
        "{LMS_SERVER_NAME} {CMS_SERVER_NAME} > config.yml".format(
            LMS_SERVER_NAME=ensure_quoted(kwargs["LMS_SERVER_NAME"]),
            CMS_SERVER_NAME=ensure_quoted(kwargs["CMS_SERVER_NAME"]),
        )
    )


def configuration_prepare1(c, *args, **kwargs):
    git_dir = "{CONFIGURATION_DIR}/.git".format(CONFIGURATION_DIR=CONFIGURATION_DIR)
    c.run("mkdir -p {CONFIGURATION_DIR}".format(CONFIGURATION_DIR=CONFIGURATION_DIR))
    if exists(c, runner=c.run, path=git_dir):
        env = dict(
            GIT_WORK_TREE=CONFIGURATION_DIR,
            GIT_DIR=git_dir,
        )
        c.run(
            "git pull --ff-only origin {EDX_RELEASE_REF}".format(
                EDX_RELEASE_REF=EDX_RELEASE_REF
            ),
            env=env,
        )
    else:
        c.run(
            " ".join(
                (
                    "git clone https://github.com/edx/configuration",
                    "--depth=1",
                    "--branch {EDX_RELEASE_REF} {CONFIGURATION_DIR}".format(
                        EDX_RELEASE_REF=EDX_RELEASE_REF,
                        CONFIGURATION_DIR=CONFIGURATION_DIR,
                    ),
                )
            )
        )


def bootstrap2(c, *args, **kwargs):
    env = dict(OPENEDX_RELEASE=EDX_RELEASE_REF)
    c.sudo(
        "bash {CONFIGURATION_DIR}/util/install/ansible-bootstrap.sh".format(
            CONFIGURATION_DIR=CONFIGURATION_DIR
        ),
        env=env,
    )
    c.sudo(
        "bash {CONFIGURATION_DIR}/util/install/generate-passwords.sh".format(
            CONFIGURATION_DIR=CONFIGURATION_DIR
        ),
        env=env,
    )


def ansible_native3(c, *args, **kwargs):
    system_version = c.run("lsb_release -rs", hide=True)

    native_sh = ensure_quoted(
        "{CONFIGURATION_DIR}/util/install/native.sh".format(
            CONFIGURATION_DIR=CONFIGURATION_DIR
        )
    )
    c.run(
        "sed -i 's/16.04/{system_version}/g' {native_sh}".format(
            system_version=system_version, native_sh=native_sh
        )
    )

    env = dict(OPENEDX_RELEASE=EDX_RELEASE_REF)
    c.sudo("bash {native_sh}".format(native_sh=native_sh), env=env)
