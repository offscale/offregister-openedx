# Based off Sep 11, 2020 (v36) version of
# https://openedx.atlassian.net/wiki/spaces/OpenOPS/pages/146440579/Native+Open+edX+platform+Ubuntu+16.04+64+bit+Installation

from os import environ

from fabric.context_managers import shell_env
from fabric.contrib.files import exists
from fabric.operations import run, sudo
from offregister_fab_utils.apt import apt_depends
from offutils import ensure_quoted

EDX_RELEASE_REF = environ.get("EDX_RELEASE_REF", "open-release/juniper.3")
CONFIGURATION_DIR = "/tmp/edx/configuration"


def system_install0(*args, **kwargs):
    apt_depends("curl", "gnupg", "git", "software-properties-common", "python-pip", "python-dev")
    sudo('pip install -U pyopenssl')


def config_yml1(*args, **kwargs):
    # if exists("config.yml"): return False

    run(
        'printf \'EDXAPP_LMS_BASE: "%s"\nEDXAPP_CMS_BASE: "%s"\' '
        "{LMS_SERVER_NAME} {CMS_SERVER_NAME} > config.yml".format(
            LMS_SERVER_NAME=ensure_quoted(kwargs["LMS_SERVER_NAME"]),
            CMS_SERVER_NAME=ensure_quoted(kwargs["CMS_SERVER_NAME"]),
        )
    )


def configuration_prepare1(*args, **kwargs):
    git_dir = "{CONFIGURATION_DIR}/.git".format(CONFIGURATION_DIR=CONFIGURATION_DIR)
    run("mkdir -p {CONFIGURATION_DIR}".format(CONFIGURATION_DIR=CONFIGURATION_DIR))
    if exists(git_dir):
        with shell_env(
            GIT_WORK_TREE=CONFIGURATION_DIR,
            GIT_DIR=git_dir,
        ):
            run(
                "git pull --ff-only origin {EDX_RELEASE_REF}".format(
                    EDX_RELEASE_REF=EDX_RELEASE_REF
                )
            )
    else:
        run(
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


def bootstrap2(*args, **kwargs):
    with shell_env(OPENEDX_RELEASE=EDX_RELEASE_REF):
        sudo(
            "bash {CONFIGURATION_DIR}/util/install/ansible-bootstrap.sh".format(
                CONFIGURATION_DIR=CONFIGURATION_DIR
            )
        )
        sudo(
            "bash {CONFIGURATION_DIR}/util/install/generate-passwords.sh".format(
                CONFIGURATION_DIR=CONFIGURATION_DIR
            )
        )


def ansible_native3(*args, **kwargs):
    system_version = run("lsb_release -rs", quiet=True)

    native_sh = ensure_quoted(
        "{CONFIGURATION_DIR}/util/install/native.sh".format(
            CONFIGURATION_DIR=CONFIGURATION_DIR
        )
    )
    run(
        "sed -i 's/16.04/{system_version}/g' {native_sh}".format(
            system_version=system_version, native_sh=native_sh
        )
    )

    with shell_env(OPENEDX_RELEASE=EDX_RELEASE_REF):
        sudo("bash {native_sh}".format(native_sh=native_sh))
