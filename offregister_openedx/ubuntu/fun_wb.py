# -*- coding: utf-8 -*-
# Derived from https://github.com/openfun/openedx-docker/blob/7f44edb/releases/eucalyptus/3/wb/Dockerfile
from functools import partial

import offregister_python.ubuntu as offregister_python
from fabric.context_managers import shell_env
from offregister_fab_utils.apt import apt_depends
from offutils import ensure_quoted
from patchwork.files import append, exists

VENV = "/edx/app/edxapp/venv"


def sys_install0(c, *args, **kwargs):
    if c.run('grep -Fq "LANG" /etc/environment', warn=True, hide=True).exited == 0:
        return False

    apt_depends(
        c,
        "gettext",
        "libreadline6",
        "locales",
        "tzdata",
        "curl",
        "apt-transport-https",
        "python-dev",
        "python-virtualenv",
        "python-pip",
        "build-essential",
        "gettext",
        "git",
        "graphviz-dev",
        "libgeos-dev",
        "libjpeg8-dev",
        "libmysqlclient-dev",
        "libpng12-dev",
        "libxml2-dev",
        "libxmlsec1-dev",
        "rdfind",
        "libsqlite3-dev",
        "mongodb",
    )

    c.sudo("""sed -i 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen""")
    c.sudo("locale-gen")
    append(
        c,
        c.sudo,
        "/etc/environment",
        "LANG=en_US.UTF-8\n" "LANGUAGE=en_US:en\n" "LC_ALL=en_US.UTF-8\n",
    )


def nodejs_install1(c, *args, **kwargs):
    if exists(c, runner=c.run, path="/usr/local/bin/node"):
        return False

    c.run("curl -L https://git.io/n-install | bash -s -- -y lts")
    c.sudo("for f in $HOME/n/bin/*; do ln -s $f /usr/local/bin/; done")


def edx_download_extract2(c, *args, **kwargs):
    if exists(
        c,
        runner=c.run,
        path="/edx/app/edxapp/releases/eucalyptus/3/wb/requirements.txt",
    ):
        return False

    c.run("mkdir -p $HOME/Downloads")
    with c.cd("$HOME/Downloads"):
        docker_ball = "openedx-docker.tar.gz"
        c.run(
            "curl -sLo {docker_ball} "
            "https://api.github.com/repos/openfun/openedx-docker/tarball".format(
                docker_ball=docker_ball
            )
        )

        edx_ball = "edxapp.tgz"
        c.run(
            "curl -sLo {edx_ball} "
            "https://github.com/openfun/edx-platform/archive/eucalyptus.3-wb.tar.gz".format(
                edx_ball=edx_ball
            )
        )
        c.run("tar xzf {edx_ball}".format(edx_ball=edx_ball))
        c.run("mv edx-platform* edx-platform")

        edx_app_path = "/edx/app/edxapp"
        edx_config_path = "/edx/config"
        src_path = "/usr/local/src_path"
        venv_path = "/edx/app/edxapp/venv"

        paths = edx_app_path, edx_config_path, src_path, venv_path

        ensure_quote = partial(ensure_quoted, q='"')

        c.sudo(
            "mkdir -p {paths} {edx_app_path}"
            " && chown -R $USER:$GROUP {paths}"
            ' && cp -r edx-platform "{edx_app_path}"'.format(
                paths=" ".join(map(ensure_quote, paths)),
                edx_app_path=ensure_quote(edx_app_path),
            )
        )
        # c.run(
        #    "ln -s /edx/app/edxapp/edx-platform/requirements/edx/fun.txt "
        #    "/edx/app/edxapp/releases/eucalyptus/3/wb/requirements.txt"
        # )
        # Actually let's skip the FUN dependencies
        # c.run("ln -sf {edx_config_path}/lms /edx/app/edxapp/edx-platform/lms/envs/fun".format(
        #     edx_config_path=edx_config_path))
        c.run(
            "ln -sf {edx_config_path}/cms "
            "/edx/app/edxapp/edx-platform/cms/envs/fun".format(
                edx_config_path=edx_config_path
            )
        )


def python_edx_platform_install3(c, *args, **kwargs):
    offregister_python.install_venv0(
        python3=False, virtual_env=VENV, pip_version="9.0.3"
    )
    with c.cd("/edx/app/edxapp/edx-platform"), shell_env(
        VIRTUAL_ENV=VENV, PATH="{}/bin:$PATH".format(VENV)
    ):
        c.run("python -m pip install -r requirements/edx/pre.txt")
        c.run("python -m pip install astroid==1.6.0 django==1.8.15")
        c.run("python -m pip install -r requirements/edx/base.txt")
        c.run("python -m pip install -r requirements/edx/paver.txt")
        c.run("python -m pip install -r requirements/edx/post.txt")
        c.run("python -m pip install -r requirements/edx/local.txt")
        # c.run("python -m pip install -r requirements/edx/fun.txt")


def nodejs_edx_platform_install3(c, *args, **kwargs):
    path_env = c.run("echo $PATH", hide=True).stdout.rstrip()
    with c.cd("/edx/app/edxapp/edx-platform"), shell_env(
        PATH="{path_env}:/edx/app/edxapp/edx-platform/node_modules/.bin".format(
            path_env=path_env
        )
    ):
        with c.cd("node_modules/edx-ui-toolkit"):
            c.run("npm i")

        env = dict(
            NO_PREREQ_INSTALL=1, VIRTUAL_ENV=VENV, PATH="{}/bin:$PATH".format(VENV)
        )
        c.run(
            " ".join(
                (
                    "paver update_assets ",
                    "--settings=fun.docker_build_production ",
                    "--skip-collect ",
                )
            ),
            env=env,
        )


def static_collector(c, *args, **kwargs):
    collect_static_args = "--noinput - -settings = fun.docker_build_production"
    with c.cd("/edx/app/edxapp/edx-platform"), shell_env(
        VIRTUAL_ENV=VENV, PATH="{}/bin:$PATH".format(VENV)
    ):
        c.run(
            "python manage.py lms collectstatic --link {collect_static_args}".format(
                collect_static_args=collect_static_args
            )
        )
        c.run(
            "python manage.py cms collectstatic --link {collect_static_args}".format(
                collect_static_args=collect_static_args
            )
        )
        c.run("rdfind -makesymlinks true -followsymlinks true ${EDXAPP_STATIC_ROOT}")

        c.run(
            "python manage.py lms collectstatic {collect_static_args}".format(
                collect_static_args=collect_static_args
            )
        )
        c.run(
            "python manage.py cms collectstatic {collect_static_args}".format(
                collect_static_args=collect_static_args
            )
        )

        c.run("rdfind -makesymlinks true ${EDXAPP_STATIC_ROOT}")
