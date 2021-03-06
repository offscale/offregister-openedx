# Derived from https://github.com/openfun/openedx-docker/blob/7f44edb/releases/eucalyptus/3/wb/Dockerfile
from functools import partial

from fabric.context_managers import cd, shell_env
from fabric.contrib.files import append, exists
from fabric.operations import sudo, run

from offregister_fab_utils.apt import apt_depends
import offregister_python.ubuntu as offregister_python
from offutils import ensure_quoted

VENV = "/edx/app/edxapp/venv"


def sys_install0(*args, **kwargs):
    if run('grep -Fq "LANG" /etc/environment', warn_only=True, quiet=True).succeeded:
        return False

    apt_depends(
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

    sudo("""sed -i 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen""")
    sudo("locale-gen")
    append(
        "/etc/environment",
        "LANG=en_US.UTF-8\n" "LANGUAGE=en_US:en\n" "LC_ALL=en_US.UTF-8\n",
        use_sudo=True,
    )


def nodejs_install1(*args, **kwargs):
    if exists("/usr/local/bin/node"):
        return False

    run("curl -L https://git.io/n-install | bash -s -- -y lts")
    sudo("for f in $HOME/n/bin/*; do ln -s $f /usr/local/bin/; done")


def edx_download_extract2(*args, **kwargs):
    if exists("/edx/app/edxapp/releases/eucalyptus/3/wb/requirements.txt"):
        return False

    run("mkdir -p $HOME/Downloads")
    with cd("$HOME/Downloads"):
        docker_ball = "openedx-docker.tar.gz"
        run(
            "curl -sLo {docker_ball} "
            "https://api.github.com/repos/openfun/openedx-docker/tarball".format(
                docker_ball=docker_ball
            )
        )

        edx_ball = "edxapp.tgz"
        run(
            "curl -sLo {edx_ball} "
            "https://github.com/openfun/edx-platform/archive/eucalyptus.3-wb.tar.gz".format(
                edx_ball=edx_ball
            )
        )
        run("tar xzf {edx_ball}".format(edx_ball=edx_ball))
        run("mv edx-platform* edx-platform")

        edx_app_path = "/edx/app/edxapp"
        edx_config_path = "/edx/config"
        src_path = "/usr/local/src_path"
        venv_path = "/edx/app/edxapp/venv"

        paths = edx_app_path, edx_config_path, src_path, venv_path

        ensure_quote = partial(ensure_quoted, q='"')

        sudo(
            "mkdir -p {paths} {edx_app_path}"
            " && chown -R $USER:$GROUP {paths}"
            ' && cp -r edx-platform "{edx_app_path}"'.format(
                paths=" ".join(map(ensure_quote, paths)),
                edx_app_path=ensure_quote(edx_app_path),
            ),
            shell_escape=False,
        )
        # run(
        #    "ln -s /edx/app/edxapp/edx-platform/requirements/edx/fun.txt "
        #    "/edx/app/edxapp/releases/eucalyptus/3/wb/requirements.txt"
        # )
        # Actually let's skip the FUN dependencies
        # run("ln -sf {edx_config_path}/lms /edx/app/edxapp/edx-platform/lms/envs/fun".format(
        #     edx_config_path=edx_config_path))
        run(
            "ln -sf {edx_config_path}/cms "
            "/edx/app/edxapp/edx-platform/cms/envs/fun".format(
                edx_config_path=edx_config_path
            )
        )


def python_edx_platform_install3(*args, **kwargs):
    offregister_python.install_venv0(
        python3=False, virtual_env=VENV, pip_version="9.0.3"
    )
    with cd("/edx/app/edxapp/edx-platform"), shell_env(
        VIRTUAL_ENV=VENV, PATH="{}/bin:$PATH".format(VENV)
    ):
        run("pip install -r requirements/edx/pre.txt")
        run("pip install astroid==1.6.0 django==1.8.15")
        run("pip install -r requirements/edx/base.txt")
        run("pip install -r requirements/edx/paver.txt")
        run("pip install -r requirements/edx/post.txt")
        run("pip install -r requirements/edx/local.txt")
        # run("pip install -r requirements/edx/fun.txt")


def nodejs_edx_platform_install3(*args, **kwargs):
    path_env = run("echo $PATH", quiet=True)
    with cd("/edx/app/edxapp/edx-platform"), shell_env(
        PATH="{path_env}:/edx/app/edxapp/edx-platform/node_modules/.bin".format(
            path_env=path_env
        )
    ):
        with cd("node_modules/edx-ui-toolkit"):
            run("npm i")

        with shell_env(
            NO_PREREQ_INSTALL=1, VIRTUAL_ENV=VENV, PATH="{}/bin:$PATH".format(VENV)
        ):
            run(
                " ".join(
                    (
                        "paver update_assets ",
                        "--settings=fun.docker_build_production ",
                        "--skip-collect ",
                    )
                )
            )


def static_collector(*args, **kwargs):
    collect_static_args = "--noinput - -settings = fun.docker_build_production"
    with cd("/edx/app/edxapp/edx-platform"), shell_env(
        VIRTUAL_ENV=VENV, PATH="{}/bin:$PATH".format(VENV)
    ):
        run(
            "python manage.py lms collectstatic --link {collect_static_args}".format(
                collect_static_args=collect_static_args
            )
        )
        run(
            "python manage.py cms collectstatic --link {collect_static_args}".format(
                collect_static_args=collect_static_args
            )
        )
        run("rdfind -makesymlinks true -followsymlinks true ${EDXAPP_STATIC_ROOT}")

        run(
            "python manage.py lms collectstatic {collect_static_args}".format(
                collect_static_args=collect_static_args
            )
        )
        run(
            "python manage.py cms collectstatic {collect_static_args}".format(
                collect_static_args=collect_static_args
            )
        )

        run("rdfind -makesymlinks true ${EDXAPP_STATIC_ROOT}")
