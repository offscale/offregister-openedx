from fabric.context_managers import cd, shell_env
from fabric.contrib.files import exists
from fabric.operations import run, sudo

import offregister_python.ubuntu as offregister_python
from offregister_fab_utils.apt import apt_depends
from offregister_fab_utils.ubuntu.misc import user_group_tuple

EDX_RELEASE_REF = "open-release/juniper.3"
VENV = "/tmp/ansible_bootstrap"


def system_install0(*args, **kwargs):
    apt_depends(
        "gnupg",
        "python2.7",
        "python2.7-dev",
        "python3-dev",
        "python3-venv",
        "python-pip",
        "python-apt",
        "python-jinja2",
        "build-essential",
        "sudo",
        "git-core",
        "libmysqlclient-dev",
        "libffi-dev",
        "libssl-dev",
        "python-virtualenv",
    )


def python_install1(*args, **kwargs):
    if exists("{VENV}/lib/python2.7/site-packages/ansible".format(VENV=VENV)) or exists(
        "{VENV}/lib/python3.5/site-packages/ansible_collections".format(VENV=VENV)
    ):
        return False

    offregister_python.install_venv0(
        python3=True,
        virtual_env=VENV,
        pip_version="20.0.2",
        use_sudo=False,
        packages=("ansible",),
    )

    user, group = user_group_tuple()
    sudo("chown -R {user}:{group} {VENV}".format(user=user, group=group, VENV=VENV))
    with shell_env(VIRTUAL_ENV=VENV, PATH="{VENV}/bin:$PATH".format(VENV=VENV)):
        for fname in "pre-requirements.txt", "requirements.txt":
            run(
                "pip install -qr "
                "https://raw.githubusercontent.com/edx/configuration/{EDX_RELEASE_REF}/{fname} "
                "--exists-action w".format(EDX_RELEASE_REF=EDX_RELEASE_REF, fname=fname)
            )


def ansible_run2(*args, **kwargs):
    home = run("printf '%s' \"$HOME\"", quiet=True)
    configuration_dir = "{home}/repos/edx/configuration".format(home=home)
    git_dir = "{configuration_dir}/.git".format(configuration_dir=configuration_dir)
    run("mkdir -p {configuration_dir}".format(configuration_dir=configuration_dir))
    if exists(git_dir):
        with shell_env(
            GIT_WORK_TREE=configuration_dir,
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
                    "--branch {EDX_RELEASE_REF} {configuration_dir}".format(
                        EDX_RELEASE_REF=EDX_RELEASE_REF,
                        configuration_dir=configuration_dir,
                    ),
                )
            )
        )
    with cd(
        "{configuration_dir}/playbooks".format(configuration_dir=configuration_dir)
    ), shell_env(VIRTUAL_ENV=VENV, PATH="{VENV}/bin:$PATH".format(VENV=VENV)):
        run(
            " ".join(
                (
                    "ansible-playbook",
                    "edx_ansible.yml",
                    "-i '127.0.0.1,'",
                    "-c local",
                    "-e 'configuration_version={EDX_RELEASE_REF}'".format(
                        EDX_RELEASE_REF=EDX_RELEASE_REF
                    ),
                )
            )
        )
