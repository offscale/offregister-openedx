from functools import partial
from json import load, dump
from sys import modules, version

if version[0] == "2":
    from cStringIO import StringIO

else:
    from io import StringIO

from offregister_fab_utils.fs import cmd_avail
from offutils import update_d
from pkg_resources import resource_filename
from os import path

from fabric.context_managers import cd, shell_env, settings
from fabric.contrib.files import append, exists, upload_template
from fabric.operations import sudo, put

from offregister_fab_utils.apt import apt_depends
from offregister_fab_utils.git import clone_or_update
from offregister_fab_utils.ubuntu.systemd import restart_systemd

# Global variables
g_openedx_release = "open-release/ginkgo.master"
g_context = {"EDXROOT": "/opt/openedx", "VENV": "/opt/openedx/venv"}
g_platform_dir = "{root}/edx-platform".format(root=g_context["EDXROOT"])
g_user = "edxapp"
g_edxapp = partial(sudo, user=g_user, group=g_user)

# Get file from config dir of this python package
g_file = lambda *paths: resource_filename(
    modules[__name__].__name__.partition(".")[0], path.join("config", *paths)
)


def install0(*args, **kwargs):
    openedx_release = kwargs.get("OPENEDX_RELEASE", g_openedx_release)

    # Services
    apt_depends("openjdk-8-jdk", "memcached", "rabbitmq-server")

    if sudo("dpkg -s mysql-server", quiet=True, warn_only=True).failed:
        with shell_env(DEBIAN_FRONTEND="noninteractive"):
            # TODO: Better password handling; I think this can get leaked, even with `quiet=True`?
            sudo(
                """
            debconf-set-selections <<< 'mysql-server mysql-server/root_password password {password}';
            debconf-set-selections <<< 'mysql-server mysql-server/root_password_again password {password}';
            """.format(
                    password=kwargs["MYSQL_PASSWORD"]
                ),
                quiet=True,
            )
            apt_depends("mysql-server", "mysql-client", "libmysqlclient-dev")
            sudo("systemctl unmask mysql")
            restart_systemd("mysql")

    if sudo("dpkg -s mongodb-org", quiet=True, warn_only=True).failed:
        sudo(
            "apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 0C49F3730359A14518585931BC711F9BA15703C6"
        )
        sudo(
            'echo "deb [ arch=amd64,arm64 ] http://repo.mongodb.org/apt/ubuntu xenial/mongodb-org/3.4 multiverse"'
            " | sudo tee /etc/apt/sources.list.d/mongodb-org-3.4.list"
        )
        apt_depends("mongodb-org")
        restart_systemd("mongod")

    if sudo("dpkg -s elasticsearch", quiet=True, warn_only=True).failed:
        sudo(
            "wget -O - http://packages.elasticsearch.org/GPG-KEY-elasticsearch | apt-key add -"
        )

        # Elasticsearch (optional)
        append(
            "/etc/apt/sources.list.d/elasticsearch.list",
            "deb http://packages.elasticsearch.org/elasticsearch/0.90/debian stable main",
            use_sudo=True,
        )
        sudo("apt update")
        sudo("apt-get install -y elasticsearch=0.90.13")
        sudo("apt-mark hold elasticsearch")

    # LMS/CMS install prep
    apt_depends(
        "gettext",
        "gfortran",
        "graphviz",
        "graphviz-dev",
        "libffi-dev",
        "libfreetype6-dev",
        "libgeos-dev",
        "libjpeg8-dev",
        "liblapack-dev",
        "libpng12-dev",
        "libxml2-dev",
        "libxmlsec1-dev",
        "libxslt1-dev",
        "nodejs",
        "npm",
        "ntp",
        "pkg-config",
        "python-pip",
        "virtualenv",
        "libsqlite3-dev",
        "python-pysqlite2",
        "python-pysqlite2-dbg",
    )

    # Production
    apt_depends("supervisor", "nginx")

    # LMS/CMS install
    if sudo("id -u {user}".format(user=g_user), warn_only=True, quiet=True).failed:
        sudo("useradd -UM {user}".format(user=g_user))
    sudo(
        "mkdir -p {root} {root}/staticfiles {root}/uploads $HOME/.npm $HOME/.config".format(
            root=g_context["EDXROOT"]
        )
    )
    sudo(
        "touch {root}/lms.env.json {root}/cms.env.json".format(
            root=g_context["EDXROOT"]
        )
    )
    sudo(
        "chown -R {user}:{user} {root} $HOME/.cache $HOME/.npm $HOME/.config".format(
            user=g_user, root=g_context["EDXROOT"]
        )
    )

    if kwargs.get("destroy_edx_platform", False):
        g_edxapp("rm -rf {}".format(g_platform_dir))

    clone_or_update(
        team=kwargs.get("git_team", "edx"),
        repo=kwargs.get("git_project", "edx-platform"),
        branch=kwargs.get("git_branch", openedx_release),
        skip_reset=kwargs.get("git_skip_reset", True),
        skip_checkout=kwargs.get("git_skip_checkout", True),
        cmd_runner=g_edxapp,
        to_dir=g_platform_dir,
    )

    if kwargs.get("destroy_virtualenv", False):
        g_edxapp("rm -rf {}".format(g_context["VENV"]))

    if not exists(g_context["VENV"]):
        g_edxapp(
            "virtualenv --system-site-packages {}".format(g_context["VENV"])
        )  # pysqlite wasn't building
        cache_dir = "{}/{}".format(g_context["VENV"], ".cache")
        sudo("mkdir -p {cache_dir}".format(cache_dir=cache_dir))
        sudo(
            "chown -R {user}:{user} {cache_dir}".format(
                user=g_user, cache_dir=cache_dir
            )
        )

        with cd(g_platform_dir), shell_env(
            PATH="{}/bin:$PATH".format(g_context["VENV"]),
            VIRTUAL_ENV=g_context["VENV"],
            PIP_DOWNLOAD_CACHE=cache_dir,
        ):
            for f in ("pre", "github", "local", "base", "paver", "post"):
                g_edxapp(
                    "pip install --no-cache-dir -r requirements/edx/{f}.txt".format(f=f)
                )
            g_edxapp("nodeenv -p")  # Install node environment in same virtualenv
            g_edxapp("paver install_prereqs")
    if not cmd_avail("rtlcss"):
        sudo("npm i -g rtlcss")
    g_edxapp(
        "mkdir -p {platform_dir}/lms/envs {platform_dir}/cms/envs".format(
            platform_dir=g_platform_dir
        )
    )


def configure1(
    staff_user,
    staff_email,
    staff_pass,
    deployment="production",
    https=False,
    db_migration=True,
    *args,
    **kwargs
):
    mysql_password = "{}".format(kwargs["MYSQL_PASSWORD"])

    # Configure database
    existent = sudo(
        "mysql -h localhost -u'{user}' -p'{password}' -Bse 'use {user}'".format(
            user=g_user, password=mysql_password
        ),
        warn_only=True,
        quiet=True,
    )
    if existent.failed:
        ftmp = g_edxapp("mktemp --suffix .sql")
        sio = StringIO()
        sio.write(
            """CREATE DATABASE {user};
                     CREATE USER '{user}'@'localhost' IDENTIFIED BY '{password}';
                     GRANT ALL ON {user}.* TO '{user}'@'localhost';""".format(
                user=g_user, password=mysql_password
            )
        )
        put(sio, ftmp, use_sudo=True)
        sudo(
            "mysql -h localhost -u root -p'{password}' < {ftmp}".format(
                password=mysql_password, ftmp=ftmp
            ),
            shell_escape=False,  # quiet=True
            warn_only=True,
        )
        if exists(ftmp):
            sudo("rm {ftmp}".format(ftmp=ftmp))

    # Configuration files
    env = {
        "LOG_DIR": "{root}/logs".format(root=g_context["EDXROOT"]),
        "PLATFORM_NAME": kwargs["PLATFORM_NAME"],
        "FEATURES": {"PREVIEW_LMS_BASE": kwargs["PREVIEW_LMS_BASE"]},
        "LMS_ROOT_URL": "{protocol}://{lms_site_name}".format(
            protocol="https" if https else "http", lms_site_name=kwargs["LMS_SITE_NAME"]
        ),
        "CMS_ROOT_URL": "{protocol}://{cms_site_name}".format(
            protocol="https" if https else "http", cms_site_name=kwargs["CMS_SITE_NAME"]
        ),
        "CMS_BASE": kwargs["CMS_SITE_NAME"],
        "LMS_BASE": kwargs["LMS_SITE_NAME"],
        "CELERY_BROKER_HOSTNAME": "localhost",
        "MEDIA_ROOT": "{root}/uploads/".format(root=g_context["EDXROOT"]),
    }
    auth = {
        "SECRET_KEY": mysql_password,
        "AWS_ACCESS_KEY_ID": kwargs.get("AWS_ACCESS_KEY_ID", ""),
        "AWS_SECRET_ACCESS_KEY": kwargs.get("AWS_SECRET_ACCESS_KEY", ""),
        "DATABASES": {
            "default": {
                "ENGINE": "django.db.backends.mysql",
                "NAME": g_user,
                "USER": g_user,
                "PASSWORD": mysql_password,
                "HOST": "localhost",
                "PORT": 3306,
                "ATOMIC_REQUESTS": True,
            }
        },
    }

    for system in ("CMS", "LMS"):
        k = kwargs["{system}_SITE_NAME".format(system=system)]
        if k not in ("127.0.0.1", "localhost"):
            append("/etc/hosts", "127.0.0.1\t{k}".format(k=k), use_sudo=True)

    get_nginx_conf = lambda system: update_d(
        dict(
            (lambda key: (key, kwargs[key]))("_".join((system.upper(), k)))
            for k in ("LISTEN", "SITE_NAME", "EXTRA_BLOCK")
        ),
        EDXROOT=g_context["EDXROOT"],
    )

    deploy(
        system="cms",
        deployment=deployment,
        auth_config=auth,
        env_config=update_d({"SITE_NAME": kwargs["CMS_SITE_NAME"]}, env),
        nginx_config=get_nginx_conf("cms"),
    )
    deploy(
        system="lms",
        deployment=deployment,
        auth_config=auth,
        env_config=update_d({"SITE_NAME": kwargs["LMS_SITE_NAME"]}, env),
        nginx_config=get_nginx_conf("lms"),
    )

    def fin():
        return restart_systemd("nginx")

    if not db_migration:
        return fin()

    # Configure database users
    with cd(g_platform_dir), shell_env(
        PATH="{}/bin:$PATH".format(g_context["VENV"]), VIRTUAL_ENV=g_context["VENV"]
    ):
        lms_cmd = "./manage.py lms --settings={deployment}".format(
            deployment=deployment
        )
        cms_cmd = "./manage.py cms --settings={deployment}".format(
            deployment=deployment
        )

        g_edxapp("{lms_cmd} migrate".format(lms_cmd=lms_cmd))
        g_edxapp("{cms_cmd} migrate".format(cms_cmd=cms_cmd))

        g_edxapp(
            "{lms_cmd} manage_user --superuser --staff {staff_user} {staff_email}".format(
                lms_cmd=lms_cmd, staff_user=staff_user, staff_email=staff_email
            )
        )
        with settings(
            prompts={"Password: ": staff_pass, "Password (again): ": staff_pass}
        ):
            g_edxapp(
                "{lms_cmd} changepassword '{staff_user}'".format(
                    lms_cmd=lms_cmd, staff_user=staff_user
                )
            )

    return fin()


def restart_services3(*args, **kwargs):
    if kwargs.get("reboot_storage_services"):
        for service in (
            "memcached",
            "mysql",
            "mongod",
            "rabbitmq-server",
            "elasticsearch",
        ):
            if not kwargs.get("reboot_{service}".format(service=service)):
                restart_systemd(service)

    regen("lms", paver=kwargs.get("lms_paver", True))
    regen("cms", paver=kwargs.get("cms_paver", True))

    return restart_systemd("nginx")


#####################
# Utility functions #
#####################


def regen(system, paver=True, supervisor=True, deployment="production"):
    with cd(g_platform_dir), shell_env(
        PATH="{}/bin:$PATH".format(g_context["VENV"]), VIRTUAL_ENV=g_context["VENV"]
    ):
        if paver:
            g_edxapp(
                "paver update_assets {system} --settings={deployment}".format(
                    system=system, deployment=deployment
                )
            )
        if supervisor:
            sudo("supervisorctl restart {system}:".format(system=system))


def update_and_put(d, merge_d, put_location, use_sudo=False):
    d.update(merge_d)
    sio = StringIO()
    dump(d, sio)
    return put(sio, put_location, use_sudo=use_sudo)


def deploy(system, deployment, auth_config, env_config, nginx_config):
    with open(g_file(system, "{system}.auth.json".format(system=system))) as f:
        auth = load(f)

    g_edxapp("mkdir -p {root}".format(root=g_context["EDXROOT"]))
    update_and_put(
        auth,
        auth_config,
        "{root}/{system}.auth.json".format(root=g_context["EDXROOT"], system=system),
        use_sudo=True,
    )

    with open(g_file(system, "{system}.env.json".format(system=system))) as f:
        env = load(f)
    update_and_put(
        env,
        env_config,
        "{root}/{system}.env.json".format(root=g_context["EDXROOT"], system=system),
        use_sudo=True,
    )

    upload_template(
        g_file(system, "{deployment}.py".format(deployment=deployment)),
        "{platform_dir}/{system}/envs/{deployment}.py".format(
            platform_dir=g_platform_dir, system=system, deployment=deployment
        ),
        use_sudo=True,
        context=g_context,
    )

    sudo(
        "chown -R {user}:{user} {root} {platform_dir}".format(
            user=g_user, root=g_context["EDXROOT"], platform_dir=g_platform_dir
        )
    )

    if deployment == "production":
        sudo(
            "rm /etc/nginx/sites-enabled/{system}.conf*".format(system=system),
            warn_only=True,
        )
        upload_template(
            g_file("nginx", "sites-enabled", "{system}.conf".format(system=system)),
            "/etc/nginx/sites-enabled/{system}.conf".format(system=system),
            context=nginx_config,
            use_sudo=True,
            backup=False,
        )
        for _system in (system, "workers"):
            sio = StringIO()
            with open(
                g_file("supervisor", "conf.d", "{system}.conf".format(system=_system))
            ) as f:
                s = f.read()
            sio.write(s.format(**g_context))
            put(
                sio,
                "/etc/supervisor/conf.d/{system}.conf".format(system=_system),
                use_sudo=True,
            )
        sudo("supervisorctl update")
