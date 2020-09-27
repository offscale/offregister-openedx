# Derived from https://github.com/openfun/openedx-docker/blob/a395143/releases/eucalyptus/3/bare/Dockerfile
from functools import partial
from os import path
from sys import modules

import offregister_python.ubuntu as offregister_python
import offregister_service.ubuntu as offregister_service
import offregister_nginx.ubuntu as offregister_nginx

from fabric.context_managers import cd, shell_env
from fabric.contrib.files import append, exists, upload_template
from fabric.operations import sudo, run
from offregister_fab_utils import Package
from offregister_fab_utils.apt import apt_depends
from offregister_fab_utils.misc import remote_newer_than
from offregister_fab_utils.ubuntu.misc import user_group_tuple
from offutils import ensure_quoted
from pkg_resources import resource_filename

EDX_RELEASE_REF = "open-release/eucalyptus.3"

APP_PATH = "/edx/app/edxapp"
VENV = "{APP_PATH}/venv".format(APP_PATH=APP_PATH)
PLATFORM = "{APP_PATH}/edx-platform".format(APP_PATH=APP_PATH)
STATIC_ROOT = "{APP_PATH}/staticfiles".format(APP_PATH=APP_PATH)


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
        "libjpeg8",
        "libjpeg8-dev",
        "libmysqlclient20",
        "libmysqlclient-dev",
        "libpng12-0" "libpng12-dev",
        "libxml2",
        "libxml2-dev",
        "libxmlsec1-dev",
        "rdfind",
        "libsqlite3-dev",
        "mongodb",
        "lynx",
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
    if exists("$HOME/Downloads/edx-platform"):
        return False

    edx_config_path = "/edx/config"
    src_path = "/usr/local/src_path"
    upload_path = "{APP_PATH}/uploads".format(APP_PATH=APP_PATH)
    log_path = "{APP_PATH}/log".format(APP_PATH=APP_PATH)
    paths = APP_PATH, edx_config_path, src_path, VENV, upload_path, log_path

    ensure_quote = partial(ensure_quoted, q='"')

    user, group = user_group_tuple()
    sudo(
        'mkdir -p "$HOME/Downloads" {paths} '
        "&& chown -R {user}:{group} {paths}".format(
            paths=" ".join(map(ensure_quote, paths)),
            user=user,
            group=group,
        ),
        shell_escape=False,
    )
    run("touch '{APP_PATH}/log/edx.log'".format(APP_PATH=APP_PATH))

    with cd("$HOME/Downloads"):
        """
        openedx_docker_archive = "openedx-docker.tar.gz"
        run(
            "curl -L https://api.github.com/repos/openfun/openedx-docker/tarball -o {openedx_docker_archive}".format(
                openedx_docker_archive=openedx_docker_archive
            )
        )
        run(
            "tar xf {openedx_docker_archive}".format(
                openedx_docker_archive=openedx_docker_archive
            )
        )
        run("mv openfun-openedx-docker* openfun-openedx-docker")
        """

        edx_ball = "edxapp.tgz"
        run(
            "curl -sLo {edx_ball} "
            "https://github.com/edx/edx-platform/archive/{edx_release_ref}.tar.gz".format(
                edx_ball=edx_ball, edx_release_ref=EDX_RELEASE_REF
            )
        )
        run(
            " && ".join(
                (
                    "tar xzf {edx_ball}".format(edx_ball=edx_ball),
                    "mv edx-platform* edx-platform",
                    'cp -r "edx-platform" {edx_app_path}'.format(
                        edx_app_path=ensure_quote(APP_PATH)
                    ),
                )
            ),
            shell_escape=False,
        )


def python_edx_platform_install3(*args, **kwargs):
    if exists("{venv}/lib/python2.7/site-packages/twisted".format(venv=VENV)):
        return False

    offregister_python.install_venv0(
        python3=False,
        virtual_env=VENV,
        pip_version="9.0.3",
        use_sudo=False,
        packages=(
            Package("astroid", "1.6.0"),
            Package("django", "1.8.15"),
            Package("markdown", "2.2.1"),
            Package("Twisted", "20.3.0"),
            Package("redis", "3.3.7"),
            Package("gunicorn", "19.9.0"),
        ),
    )

    user, group = user_group_tuple()
    sudo("chown -R {user}:{group} {VENV}".format(user=user, group=group, VENV=VENV))
    with cd(PLATFORM), shell_env(VIRTUAL_ENV=VENV, PATH="{}/bin:$PATH".format(VENV)):
        run(
            """sed -i 's/pip/# pip/g; s/setuptools/# setuptools/g' requirements/edx/pre.txt"""
        )
        run("pip install -r requirements/edx/pre.txt")
        run("pip install --src /usr/local/src_path -r requirements/edx/github.txt")
        run("pip install -r requirements/edx/base.txt")
        run("pip install -r requirements/edx/paver.txt")
        run("pip install -r requirements/edx/post.txt")
        run("pip install -r requirements/edx/local.txt")
        run("pip install -r requirements/edx/development.txt")


def nodejs_edx_platform_install4(*args, **kwargs):
    if remote_newer_than(
        "{platform}/lms/static/css/lms-footer.css".format(platform=PLATFORM),
        # 2020-09-26; `touch` the file to make this process rerun
        1601107060,
    ):
        return False

    with cd(PLATFORM), shell_env(
        PATH="$HOME/n/bin:{PLATFORM}/node_modules/.bin:$PATH".format(PLATFORM=PLATFORM)
    ):
        if not exists("node_modules"):
            run("npm i")

        # with cd("node_modules/edx-ui-toolkit"):
        # run("npm i -S node-sass==3.12.5")
        # run("npm i")

        with shell_env(
            NO_PREREQ_INSTALL="1", VIRTUAL_ENV=VENV, PATH="{}/bin:$PATH".format(VENV)
        ):
            run(
                " ".join(
                    (
                        "paver",
                        "update_assets",
                        # "--settings=fun.docker_build_production",
                        "--skip-collect",
                    )
                )
            )


def static_collector5(*args, **kwargs):
    if remote_newer_than(
        "{platform}/cms/static/css/edx-icons.css".format(platform=PLATFORM),
        # 2020-09-26; `touch` the file to make this process rerun
        1601107060,
    ):
        return False

    collect_static_args = "--noinput"
    edxapp_static_root = ensure_quoted(STATIC_ROOT)

    with cd(PLATFORM), shell_env(VIRTUAL_ENV=VENV, PATH="{}/bin:$PATH".format(VENV)):
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

        # Replace duplicated file by a symlink
        run(
            "rdfind -makesymlinks true -followsymlinks true {edxapp_static_root}".format(
                edxapp_static_root=edxapp_static_root
            ),
            quiet=True,
        )

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

        run(
            "rdfind -makesymlinks true {edxapp_static_root}".format(
                edxapp_static_root=edxapp_static_root
            ),
            quiet=True,
        )


def python_server6(lms_port=9053, cms_port=9054, *args, **kwargs):
    user, group = user_group_tuple()
    host = kwargs.get("gunicorn_host", "localhost")

    def _service(name, port):
        return offregister_service.install_service0(
            "{name}.gunicorn".format(name=name),
            **{
                "ExecStart": "{VENV}/bin/gunicorn {arg}".format(
                    VENV=VENV,
                    arg=" \\\n\t\t\t\t\t    ".join(
                        (
                            "--name={name}".format(name=name),
                            "--bind={host}:{port}".format(host=host, port=port),
                            "--max-requests=1000",
                            "--timeout=300",
                            "--workers=3",
                            "--threads=6",
                            "{name}.wsgi:application".format(name=name),
                        )
                    ),
                ),
                "Environments": "Environment=VIRTUAL_ENV={VENV}\n"
                "Environment=PYTHONPATH={VENV}".format(VENV=VENV),
                "WorkingDirectory": PLATFORM,
                "User": user,
                "Group": group,
            }
        )

    return tuple(
        map(
            lambda both: _service(both[0], both[1]),
            (("lms", lms_port), ("cms", cms_port)),
        )
    )


def nginx_server6(lms_port=9053, cms_port=9054, *args, **kwargs):
    offregister_nginx.install_nginx0()
    offregister_nginx.setup_nginx_init1()

    configs_dir = partial(
        path.join,
        path.join(
            path.dirname(
                path.dirname(
                    resource_filename(modules[__name__].__package__, "__init__.py")
                )
            )
        ),
        "config",
        "openedx-docker",
    )

    upload_template(
        configs_dir("cms.conf"),
        "/etc/nginx/sites-enabled/{server_name}.conf".format(
            server_name=kwargs["CMS_SERVER_NAME"]
        ),
        context={
            "CMS_HOST": "localhost",
            "CMS_PORT": cms_port,
            "CMS_SERVER_NAME": kwargs["CMS_SERVER_NAME"],
            "CMS_LISTEN": int(kwargs.get("CMS_LISTEN", "80")),
            "STATIC_ROOT": STATIC_ROOT,
        },
        use_sudo=True,
        backup=False,
    )

    upload_template(
        configs_dir("lms.conf"),
        "/etc/nginx/sites-enabled/{server_name}.conf".format(
            server_name=kwargs["LMS_SERVER_NAME"]
        ),
        context={
            "LMS_HOST": "localhost",
            "LMS_PORT": lms_port,
            "LMS_SERVER_NAME": kwargs["LMS_SERVER_NAME"],
            "LMS_LISTEN": int(kwargs.get("LMS_LISTEN", "80")),
            "STATIC_ROOT": STATIC_ROOT,
        },
        use_sudo=True,
        backup=False,
    )
    return sudo("systemctl start nginx", warn_only=True)
