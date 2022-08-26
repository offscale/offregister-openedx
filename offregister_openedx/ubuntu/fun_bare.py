# Derived from https://github.com/openfun/openedx-docker/blob/a395143/releases/eucalyptus/3/bare/Dockerfile
from functools import partial
from os import path
from sys import modules

import offregister_nginx.ubuntu as offregister_nginx
import offregister_python.ubuntu as offregister_python
import offregister_service.ubuntu as offregister_service
from fabric.context_managers import shell_env
from fabric.contrib.files import append, exists
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

    c.sudo("""sed -i 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen""")
    c.sudo("locale-gen")
    append(
        "/etc/environment",
        "LANG=en_US.UTF-8\n" "LANGUAGE=en_US:en\n" "LC_ALL=en_US.UTF-8\n",
        use_sudo=True,
    )


def nodejs_install1(*args, **kwargs):
    if exists(c, runner=c.run, path="/usr/local/bin/node"):
        return False

    c.run("curl -L https://git.io/n-install | bash -s -- -y lts")
    c.sudo("for f in $HOME/n/bin/*; do ln -s $f /usr/local/bin/; done")


def edx_download_extract2(*args, **kwargs):
    if exists(c, runner=c.run, path="$HOME/Downloads/edx-platform"):
        return False

    edx_config_path = "/edx/config"
    src_path = "/usr/local/src_path"
    upload_path = "{APP_PATH}/uploads".format(APP_PATH=APP_PATH)
    log_path = "{APP_PATH}/log".format(APP_PATH=APP_PATH)
    paths = APP_PATH, edx_config_path, src_path, VENV, upload_path, log_path

    ensure_quote = partial(ensure_quoted, q='"')

    user, group = user_group_tuple(c)
    c.sudo(
        'mkdir -p "$HOME/Downloads" {paths} '
        "&& chown -R {user}:{group} {paths}".format(
            paths=" ".join(map(ensure_quote, paths)),
            user=user,
            group=group,
        )
    )
    c.run("touch '{APP_PATH}/log/edx.log'".format(APP_PATH=APP_PATH))

    with c.cd("$HOME/Downloads"):
        """
        openedx_docker_archive = "openedx-docker.tar.gz"
        c.run(
            "curl -L https://api.github.com/repos/openfun/openedx-docker/tarball -o {openedx_docker_archive}".format(
                openedx_docker_archive=openedx_docker_archive
            )
        )
        c.run(
            "tar xf {openedx_docker_archive}".format(
                openedx_docker_archive=openedx_docker_archive
            )
        )
        c.run("mv openfun-openedx-docker* openfun-openedx-docker")
        """

        edx_ball = "edxapp.tgz"
        c.run(
            "curl -sLo {edx_ball} "
            "https://github.com/edx/edx-platform/archive/{edx_release_ref}.tar.gz".format(
                edx_ball=edx_ball, edx_release_ref=EDX_RELEASE_REF
            )
        )
        c.run(
            " && ".join(
                (
                    "tar xzf {edx_ball}".format(edx_ball=edx_ball),
                    "mv edx-platform* edx-platform",
                    'cp -r "edx-platform" {edx_app_path}'.format(
                        edx_app_path=ensure_quote(APP_PATH)
                    ),
                )
            )
        )


def python_edx_platform_install3(*args, **kwargs):
    if exists(
        c,
        runner=c.run,
        path="{venv}/lib/python2.7/site-packages/twisted".format(venv=VENV),
    ):
        return False

    offregister_python.install_venv0(
        c,
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

    user, group = user_group_tuple(c)
    c.sudo("chown -R {user}:{group} {VENV}".format(user=user, group=group, VENV=VENV))
    with c.cd(PLATFORM), shell_env(VIRTUAL_ENV=VENV, PATH="{}/bin:$PATH".format(VENV)):
        c.run(
            """sed -i 's/pip/# pip/g; s/setuptools/# setuptools/g' requirements/edx/pre.txt"""
        )
        c.run("python -m pip install -r requirements/edx/pre.txt")
        c.run(
            "python -m pip install --src /usr/local/src_path -r requirements/edx/github.txt"
        )
        c.run("python -m pip install -r requirements/edx/base.txt")
        c.run("python -m pip install -r requirements/edx/paver.txt")
        c.run("python -m pip install -r requirements/edx/post.txt")
        c.run("python -m pip install -r requirements/edx/local.txt")
        c.run("python -m pip install -r requirements/edx/development.txt")


def nodejs_edx_platform_install4(*args, **kwargs):
    if remote_newer_than(
        "{platform}/lms/static/css/lms-footer.css".format(platform=PLATFORM),
        # 2020-09-26; `touch` the file to make this process rerun
        1601107060,
    ):
        return False

    with c.cd(PLATFORM), shell_env(
        PATH="$HOME/n/bin:{PLATFORM}/node_modules/.bin:$PATH".format(PLATFORM=PLATFORM)
    ):
        if not exists(c, runner=c.run, path="node_modules"):
            c.run("npm i")

        # with c.cd("node_modules/edx-ui-toolkit"):
        # c.run("npm i -S node-sass==3.12.5")
        # c.run("npm i")

        env = dict(
            NO_PREREQ_INSTALL="1", VIRTUAL_ENV=VENV, PATH="{}/bin:$PATH".format(VENV)
        )
        c.run(
            " ".join(
                (
                    "paver",
                    "update_assets",
                    # "--settings=fun.docker_build_production",
                    "--skip-collect",
                )
            ),
            env=env,
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

    with c.cd(PLATFORM), shell_env(VIRTUAL_ENV=VENV, PATH="{}/bin:$PATH".format(VENV)):
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

        # Replace duplicated file by a symlink
        c.run(
            "rdfind -makesymlinks true -followsymlinks true {edxapp_static_root}".format(
                edxapp_static_root=edxapp_static_root
            ),
            hide=True,
        )

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

        c.run(
            "rdfind -makesymlinks true {edxapp_static_root}".format(
                edxapp_static_root=edxapp_static_root
            ),
            hide=True,
        )


def python_server6(c, lms_port=9053, cms_port=9054, *args, **kwargs):
    user, group = user_group_tuple(c)
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

    upload_template_fmt(
        c,
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

    upload_template_fmt(
        c,
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
    return c.sudo("systemctl start nginx", warn=True)
