from operator import methodcaller
from sys import version

from offutils.util import iteritems

if version[0] == "2":
    from cStringIO import StringIO
else:
    from io import StringIO

from copy import deepcopy
from functools import partial

from json import load, dumps
from os import path

from fabric.context_managers import cd, shell_env, prefix
from fabric.contrib.files import upload_template, sed, exists, append
from fabric.operations import sudo, run, put
from fabric.state import env
from offregister_fab_utils.apt import apt_depends
from offregister_fab_utils.git import clone_or_update
from offregister_fab_utils.misc import timeout, get_load_remote_file
from offregister_fab_utils.ubuntu.systemd import (
    restart_systemd,
    install_upgrade_service,
)
from offutils import gen_random_str, pp, it_consumes
from pkg_resources import resource_filename

from offregister_openedx.utils import OTemplate, is_email

g_openedx_release = "open-release/ironwood.2"


def ansible_bootstrap0(*args, **kwargs):
    """Reimplemented in Fabric:
    https://github.com/edx/configuration/blob/c47d85a/util/install/ansible-bootstrap.sh"""

    sudo("add-apt-repository -y universe")
    sudo("add-apt-repository -y main")
    sudo("add-apt-repository -y ppa:ubuntu-toolchain-r/test")

    apt_depends(
        "python2.7",
        "python2.7-dev",
        "python-pip",
        "python-apt",
        "python-yaml",
        "python-jinja2",
        "build-essential",
        "git-core",
        "libmysqlclient-dev",
        "libffi-dev",
        "libssl-dev",
        "libatlas-base-dev",
        "liblapack-dev",
        "libblas-dev",
    )

    virtual_env_version = "16.6.0"
    pip_version = "19.3.1"
    setuptools_version = "39.0.1"
    virtual_env = "/tmp/bootstrap"
    configuration_dir = "/tmp/configuration"
    """ # These don't seem to be used:
    python_bin = '{virtual_env}/bin'.format(virtual_env=virtual_env)
    ansible_dir = '/tmp/ansible'
    edx_ppa = 'deb http://ppa.edx.org precise main'
    edx_ppa_key_server = 'hkp://pgp.mit.edu:80'
    edx_ppa_key_id = 'b41e5e3969464050'
    """

    sudo(
        'apt-key adv --keyserver "keyserver.ubuntu.com" --recv-keys "B41E5E3969464050"'
    )
    sudo("add-apt-repository -y ppa:git-core/ppa")

    dist = run("lsb_release -cs")
    append(
        "/etc/apt/sources.list.d/openedx.list",
        "deb http://ppa.edx.org {dist} main".format(dist=dist),
        use_sudo=True,
    )
    sudo("apt-get update -q")
    apt_depends(
        "gnupg",
        "software-properties-common",
        "python-software-properties",
        "python2.7",
        "python2.7-dev",
        "python-pip",
        "python-apt",
        "python-jinja2",
        "build-essential",
        "sudo",
        "git-core",
        "libmysqlclient-dev",
        "libffi-dev",
        "libssl-dev",
    )

    openedx_release = kwargs.get("OPENEDX_RELEASE", g_openedx_release)

    sudo("pip install --upgrade pip=={}".format(pip_version))
    sudo("pip install setuptools=={}".format(setuptools_version))
    sudo("pip install virtualenv=={}".format(virtual_env_version))

    if not path.isdir(virtual_env):
        run("virtualenv '{}'".format(virtual_env))
    clone_or_update(
        team="edx",
        repo="configuration",
        branch=openedx_release,
        to_dir=configuration_dir,
        skip_reset=True,
    )

    # TODO: Run this as a separate offregister task, using new ansible support
    with cd(configuration_dir), shell_env(
        VIRTUAL_ENV=virtual_env, PATH="{}/bin:$PATH".format(virtual_env)
    ):
        run("make requirements")
        with cd("playbooks/edx-east"):
            run("env")
            run(
                "ansible-playbook "
                "-c local ./edx_ansible.yml "
                '-i "127.0.0.1," '
                "-c local"
                "-e \"configuration_version='{}'\"".format(openedx_release),
                warn_only=True,
            )

    return "openedx::step0", configuration_dir


def sandbox1(*args, **kwargs):
    """Reimplemented in Fabric:
    https://github.com/edx/configuration/blob/d87bf6a/util/install/native.sh"""

    apt_depends("software-properties-common")
    sudo("add-apt-repository -y ppa:ubuntu-toolchain-r/test")
    apt_depends(
        "build-essential",
        "software-properties-common",
        "curl",
        "git-core",
        "libxml2-dev",
        "libxslt1-dev",
        "python-pip",
        "libmysqlclient-dev",
        "python-apt",
        "python-dev",
        "libxmlsec1-dev",
        "libfreetype6-dev",
        "swig",
        "gcc",
        "g++",
    )
    sudo("apt-get remove -y python-yaml")
    sudo("pip install --upgrade pip==19.3.1")
    sudo("pip install --upgrade setuptools==39.0.1")
    sp = deepcopy(env["sudo_prefix"])
    env["sudo_prefix"] += "-H "
    sudo("pip install --upgrade virtualenv==15.2.0")

    openedx_release = kwargs.get("OPENEDX_RELEASE", g_openedx_release)

    config_vars = (
        "edx_platform_version",
        "certs_version",
        "forum_version",
        "XQUEUE_VERSION",
        "configuration_version",
        "demo_version",
        "NOTIFIER_VERSION",
        "INSIGHTS_VERSION",
        "ANALYTICS_API_VERSION",
        "ECOMMERCE_VERSION",
        "ECOMMERCE_WORKER_VERSION",
        "DISCOVERY_VERSION",
        "THEMES_VERSION",
    )

    extra_vars_d = {
        k: (lambda v: "{v}".format(v=v) if v[0] in ("'", '"') else "'{v}'".format(v=v))(
            kwargs.get(k, openedx_release)
        )
        for k in config_vars
    }
    extra_vars_d["SANDBOX_ENABLE_ECOMMERCE"] = "True"
    extra_vars = "-e " + " -e ".join(
        "{k}={v}".format(k=k, v=v) for k, v in iteritems(extra_vars_d)
    )

    wd = "/var/tmp/configuration"
    clone_or_update(
        team="edx",
        repo="configuration",
        branch=openedx_release,
        to_dir=wd,
        skip_reset=True,
    )
    home = run("echo $HOME")
    sudo(
        'HOME="{home}" pip install -r "{wd}/requirements.txt"'.format(home=home, wd=wd)
    )
    env["sudo_prefix"] = deepcopy(sp)

    env["sudo_prefix"] = "-E " + env["sudo_prefix"]

    # TODO: Run this as a separate offregister task, using new ansible support
    with cd("{wd}/playbooks".format(wd=wd)), shell_env(**extra_vars_d):
        run(
            'ansible-playbook ansible-playbook -c local ./openedx_native.yml -i "localhost," {extra_vars}'.format(
                extra_vars=extra_vars
            ),
            warn_only=True,
        )
        run("env")

    env["sudo_prefix"] = sp

    return "installed: {}".format(openedx_release)


def update_lms_cms_env2(**kwargs):
    if not kwargs.get("NO_OPENEDX_RESTART"):
        run_paver = True
        restart_openedx666(run_paver=run_paver, paver_cms=True, paver_lms=run_paver)
    return "openedx::step3"


def update_conf3(*args, **kwargs):
    lms_path, lms_config = get_env("lms.env.json")
    cms_path, cms_config = get_env("cms.env.json")
    if "ALL_EMAILS_TO" in kwargs:
        lms_config = {
            k: (kwargs["ALL_EMAILS_TO"] if isinstance(v, str) and is_email(v) else v)
            for k, v in iteritems(lms_config)
        }
        cms_config = {
            k: (kwargs["ALL_EMAILS_TO"] if isinstance(v, str) and is_email(v) else v)
            for k, v in iteritems(cms_config)
        }
        for k in (
            "FEEDBACK_SUBMISSION_EMAIL",
            "CONTACT_MAILING_ADDRESS",
            "PARTNER_SUPPORT_EMAIL",
        ):
            lms_config[k] = kwargs["ALL_EMAILS_TO"]

    """if 'treat_local_different' in kwargs and kwargs['treat_local_different']:
        lms_config = {k: (kwargs['ALL_EMAILS_TO'] if isinstance(v, basestring) and is_email(v) else v)
                      for k, v in lms_config.iteritems()}
        cms_config = {k: (kwargs['ALL_EMAILS_TO'] if isinstance(v, basestring) and is_email(v) else v)
                      for k, v in cms_config.iteritems()}
        # TODO^"""
    for env_conf in ("lms.env", "cms.env"):
        if env_conf in kwargs:
            for k, v in iteritems(kwargs[env_conf]):
                if "." not in k:
                    (lms_config if env_conf == "lms.env" else cms_config)[k] = v
                else:
                    raise NotImplementedError("nested configuration edits")

    put(
        local_path=StringIO(dumps(lms_config, indent=4, sort_keys=True)),
        remote_path=lms_path,
        use_sudo=True,
    )
    put(
        local_path=StringIO(dumps(cms_config, indent=4, sort_keys=True)),
        remote_path=cms_path,
        use_sudo=True,
    )

    run_paver = kwargs.get("run_paver", False)
    if "openedx_honor_html" in kwargs:
        with open(
            resource_filename("offregister_openedx", path.join("conf", "honor.html")),
            "rt",
        ) as f:
            honor = f.read().format(openedx_honor_html=kwargs["openedx_honor_html"])

        honor_path = "/edx/var/edxapp/staticfiles/templates/static_templates/honor.html"
        crc_chk = lambda: sudo("crc32 '{honor_path}'".format(honor_path=honor_path))
        pre_crc = crc_chk()
        put(local_path=StringIO(honor), remote_path=honor_path, use_sudo=True)

        if pre_crc != crc_chk():
            run_paver = True
            """sudo(
                'for f in /edx/var/edxapp/staticfiles/templates/static_templates/honor*; do cp \'{honor_path}\' $f; done'.format(
                    honor_path=honor_path),
                shell_escape=False)"""
            it_consumes(
                [
                    sudo(
                        "cp {honor_path} {dest}".format(
                            honor_path=honor_path, dest=dest
                        )
                    )
                    for dest in (
                        d
                        for d in sudo(
                            "ls /edx/var/edxapp/staticfiles/templates/static_templates/honor*"
                        ).splitlines()
                        + [
                            "/edx/app/edxapp/edx-platform/lms/templates/static_templates/honor.html"
                        ]
                        if d != honor_path
                    )
                ]
            )

    if "openedx_banner_html" in kwargs:
        p = "/edx/var/edxapp/staticfiles/templates/index.html"

        def replace(_p):
            with open(
                resource_filename(
                    "offregister_openedx", path.join("conf", "sed_esc.bash")
                ),
                "rt",
            ) as f:
                put(
                    StringIO(
                        OTemplate(f.read()).substitute(
                            openedx_banner_html=kwargs["openedx_banner_html"],
                            filename=_p,
                        )
                    ),
                    remote_path="/tmp/a.bash",
                    mode=0o755,
                )
            return sudo("/tmp/a.bash")

        crc_chk = lambda: sudo("crc32 '{path}'".format(path=p))
        pre_crc = crc_chk()
        replace(p)
        if True or pre_crc != crc_chk():
            run_paver = True
            it_consumes(
                [
                    sudo(replace(dest))
                    for dest in sudo(
                        "ls /edx/app/edxapp/edx-platform/lms/templates/index**"
                    ).splitlines()
                    + [
                        "/edx/var/edxapp/staticfiles/templates/index.html",
                        "/edx/app/edxapp/edx-platform/lms/static/templates/index.html",
                    ]
                ]
            )
    # sed('', '"city", "country", "goals",', '"city", "country", "goals", "student_id",', limit=1, use_sudo=True)

    if not kwargs.get("NO_OPENEDX_RESTART"):
        restart_openedx666(run_paver=run_paver, paver_cms=True, paver_lms=run_paver)
    return "openedx::step3"


def nginx_domain_and_https_setup4(*args, **kwargs):
    pp(kwargs)
    g = partial(
        get_load_remote_file,
        directory="/edx/app/nginx/sites-available",
        load_f=lambda fd: fd.read(),
    )
    lms = g(filename="lms")
    cms = g(filename="cms")

    sudo(
        'cp "{filename}" "{filename}.$(date +%s%3N).bak"'.format(
            filename=lms.remote_path
        )
    )
    sudo(
        'cp "{filename}" "{filename}.$(date +%s%3N).bak"'.format(
            filename=cms.remote_path
        )
    )

    hosts_append = partial(append, filename="/etc/hosts", use_sudo=True)

    hosts_append(
        text="127.0.0.1\t{site_name}".format(site_name=kwargs["lms.env"]["LMS_BASE"])
    )
    lms_content = (
        lms.content.replace(
            "server {",
            "server {\n"
            + "    server_name {site_name};".format(
                site_name=kwargs["lms.env"]["LMS_BASE"]
            ),
        )
        if "server_name" not in lms.content
        else lms.content
    )

    hosts_append(
        text="127.0.0.1\t{site_name}".format(site_name=kwargs["cms.env"]["CMS_BASE"])
    )
    cms_content = cms.content.replace(
        "server_name ~^((stage|prod)-)?studio.*;",
        "server_name {site_name};".format(site_name=kwargs["cms.env"]["CMS_BASE"]),
    ).replace(" listen 18010 ;", "#listen 18010 ;")
    put(local_path=StringIO(cms_content), remote_path=cms.remote_path, use_sudo=True)
    put(local_path=StringIO(lms_content), remote_path=lms.remote_path, use_sudo=True)

    return restart_systemd("nginx")


def edx_platform_fork5(*args, **kwargs):
    # TODO: Finish
    run_paver = True

    to_dir = "/edx/app/edxapp/edx-platform"
    if exists(to_dir) and not exists(to_dir + ".orig"):
        sudo("mv {to_dir} {to_dir}.orig".format(to_dir=to_dir))
    clone_or_update(
        team="offscale",
        repo="edx-platform",
        branch="open-release/ficus.master",
        use_sudo=True,
        to_dir=to_dir,
    )
    sudo("chown -R edxapp:edxapp {}".format(to_dir))

    virtual_env = "/edx/app/edxapp/venvs/edxapp"
    edxapp = partial(sudo, user="edxapp", warn_only=True)
    with cd(to_dir), shell_env(
        VIRTUAL_ENV=virtual_env, PATH="{}/bin:$PATH".format(virtual_env)
    ):
        edxapp(
            "pip install -q --disable-pip-version-check --exists-action w -r requirements/edx/local.txt"
        )

    # if not kwargs.get('NO_OPENEDX_RESTART'):
    restart_openedx666(run_paver=run_paver, paver_cms=True, paver_lms=run_paver)
    return "openedx::step5"


def _install_stanford_theme3(*args, **kwargs):
    theme_dir = "/edx/app/edxapp/edx-platform/themes/edx-stanford-theme"
    clone_or_update(
        team="Stanford-Online",
        repo="edx-theme",
        branch="master",
        to_dir=theme_dir,
        use_sudo=True,
    )
    sudo("chown -R edxapp:edxapp '{}'".format(theme_dir))
    lms_path, lms_config = get_env("lms.env.json")
    lms_config["USE_CUSTOM_THEME"] = True
    lms_config["THEME_NAME"] = "stanford-style"
    put(
        local_path=StringIO(dumps(lms_config, indent=4, sort_keys=True)),
        remote_path=lms_path,
        use_sudo=True,
    )

    edxapp = partial(sudo, user="edxapp", warn_only=True)
    with cd("/edx/app/edxapp/edx-platform"):
        with prefix("source /edx/app/edxapp/edxapp_env"):
            edxapp(timeout("120s", "paver update_assets cms --settings=aws"))
            edxapp(timeout("120s", "paver update_assets lms --settings=aws"))
    if not kwargs.get("NO_OPENEDX_RESTART"):
        restart_openedx666()
    return 'installed "{!s}" theme'.format(lms_config["THEME_NAME"])


def _uninstall_stanford_theme4(*args, **kwargs):
    theme_dir = "/edx/app/edxapp/edx-platform/themes/edx-stanford-theme"
    if exists(theme_dir):
        sudo("rm -rf '{}'".format(theme_dir))
    lms_path, lms_config = get_env("lms.env.json")
    lms_config["USE_CUSTOM_THEME"] = False
    lms_config["THEME_NAME"] = "stanford-style"
    put(
        local_path=StringIO(dumps(lms_config, indent=4, sort_keys=True)),
        remote_path=lms_path,
        use_sudo=True,
    )

    edxapp = partial(sudo, user="edxapp", warn_only=True)
    with cd("/edx/app/edxapp/edx-platform"):
        with prefix("source /edx/app/edxapp/edxapp_env"):
            edxapp(timeout("120s", "paver update_assets cms --settings=aws"))
            edxapp(timeout("120s", "paver update_assets lms --settings=aws"))
    if not kwargs.get("NO_OPENEDX_RESTART"):
        restart_openedx666()
    return 'installed "{!s}" theme'.format(lms_config["THEME_NAME"])


def install_analytics_dashboard6(*args, **kwargs):
    apt_depends("python-virtualenv")

    edxapp = partial(sudo, user="edxapp", warn_only=True)

    root = "/edx/extra_repos"
    repo = "edx-analytics-dashboard"
    repo_dir = "{root}/{repo}".format(root=root, repo=repo)
    venvs_dir = "{root}/venvs".format(root=root, repo=repo)
    venv = "{venvs_dir}/{repo}-env".format(venvs_dir=venvs_dir, repo=repo)
    home_dir = run("echo $HOME", quiet=True)

    sudo(
        "mkdir -p '{repo_dir}' '{venvs_dir}/.cache'".format(
            repo_dir=repo_dir, venvs_dir=venvs_dir
        )
    )
    sudo(
        "chown -R edxapp:edxapp '{repo_dir}' '{venvs_dir}'".format(
            repo_dir=repo_dir, venvs_dir=venvs_dir
        )
    )
    sudo("setfacl -m g:edxapp:r /var/tmp")
    with shell_env(
        NODE_PATH="{home_dir}/n/lib/node_modules".format(home_dir=home_dir),
        PATH="{home_dir}/n/bin:$PATH".format(venv=venv, home_dir=home_dir),
    ):
        run("npm i -g webpack-dev-server")

    clone_or_update(
        repo=repo, team="edx", branch="master", to_dir=repo_dir, cmd_runner=edxapp
    )

    if not exists("$HOME/n"):
        raise NotImplementedError("TODO: Add `n-install` code from app-push repo")
    elif not exists(venv):
        edxapp("virtualenv '{venv}'".format(venv=venv))
        edxapp(
            "printf '%s\n%s' '[global]' 'cache-dir={venvs_dir}/.cache' > {venv}/pip.conf".format(
                venvs_dir=venvs_dir, venv=venv
            )
        )

    with shell_env(
        VIRTUAL_ENV=venv,
        PYTHONPATH=venv,
        NODE_PATH="{home_dir}/n/lib/node_modules".format(home_dir=home_dir),
        npm_config_cache="{venvs_dir}/.node_cache".format(venvs_dir=venvs_dir),
        PATH="{venv}/bin:{home_dir}/n/bin:$PATH".format(venv=venv, home_dir=home_dir),
    ), cd(repo_dir):
        edxapp("make develop")
        edxapp("make migrate")

    frontend_service_name = "{repo}-frontend".format(repo=repo)
    install_upgrade_service(
        frontend_service_name,
        context={
            "WorkingDirectory": repo_dir,
            "Environments": "Environment="
            "NODE_PATH={home_dir}/n/lib/node_modules"
            "Environment="
            "PATH={home_dir}/n/bin"
            "".format(home_dir=home_dir),
            "ExecStart": "{home_dir}/n/bin/npm start" "".format(home_dir=home_dir),
            "User": "edxapp",
            "Group": "edxapp",
            "service_name": frontend_service_name,
        },
    )

    backend_service_name = "{repo}-backend".format(repo=repo)
    install_upgrade_service(
        backend_service_name,
        context={
            "WorkingDirectory": repo_dir,
            "Environments": "Environment=VIRTUAL_ENV={venv}\n"
            "Environment=PYTHONPATH={venv}".format(venv=venv),
            "ExecStart": "{venv}/bin/python manage.py runserver 0.0.0.0:8110".format(
                venv=venv
            ),
            "User": "edxapp",
            "Group": "edxapp",
            "service_name": backend_service_name,
        },
    )

    return restart_systemd(frontend_service_name), restart_systemd(backend_service_name)


def restart_openedx666(
    run_paver=False, paver_cms=True, paver_lms=True, debug_no_paver=False, **kwargs
):
    sudo("/edx/bin/supervisorctl stop edxapp:")
    sudo("/edx/bin/supervisorctl stop edxapp_worker:")
    if run_paver:
        edxapp = partial(sudo, user="edxapp", warn_only=True)
        with cd("/edx/app/edxapp/edx-platform"):
            with prefix("source /edx/app/edxapp/edxapp_env"):
                if paver_cms:
                    # if debug_no_paver:
                    edxapp(
                        "python manage.py cms --settings=aws collectstatic --noinput"
                    )
                    # else:
                    #     edxapp(timeout('5m', 'paver update_assets cms --settings=aws'))
                if paver_lms:
                    if debug_no_paver:
                        edxapp(
                            "python manage.py lms --settings=aws collectstatic --noinput"
                        )
                    else:
                        edxapp(timeout("5m", "paver update_assets lms --settings=aws"))
    sudo("/edx/bin/supervisorctl start edxapp:")
    sudo("/edx/bin/supervisorctl start edxapp_worker:")


get_env = lambda filename: get_load_remote_file(
    "/edx/app/edxapp", filename, load_f=load
)


def _step3(*args, **kwargs):
    clone_or_update(
        team="edx", repo="configuration", branch=g_openedx_release, skip_reset=True
    )
    sudo("pip install -r configuration/requirements.txt")
    with cd("configuration/playbooks"):
        sudo('ansible-playbook -c local ./edx_sandbox.yml -i "localhost,"')
    """
    with cd('configuration'):
        sudo('util/install/ansible-bootstrap.sh')
        sudo('util/install/sandbox.sh')
    """
    return "openedx::step1"


def _step4(*args, **kwargs):
    upload_template(
        resource_filename("offregister_openedx", path.join("conf", "server-vars.yml")),
        "/edx/app/edx_ansible/server-vars.yml",
        use_sudo=False,
        context={
            "EMAIL_HOST_USER": gen_random_str(10),
            "EMAIL_HOST_PASSWORD": gen_random_str(10),
        },
    )


def _install_theme5(*args, **kwargs):
    clone_or_update(
        team="dadasoz",
        repo="edx-bootstrap-theme",
        branch="master",
        to_dir="/edx/app/edxapp/edx-platform/themes/edx-bootstrap-theme",
    )

    s = '"COMPREHENSIVE_THEME_DIR": "{}"'
    sed(
        "/edx/app/edxapp/lms.env.json",
        s.format("/edx/app/edxapp/edx-platform/themes/edx-bootstrap-theme"),
        s.format(""),
        backup="",
        use_sudo=True,
        shell=True,
    )
    return "openedx::step3"


def _set_theme6(*args, **kwargs):
    virtual_env = "/edx/app/edxapp/venvs/edxapp"
    with cd("/edx/app/edxapp/edx-platform"), shell_env(
        VIRTUAL_ENV=virtual_env, PATH="{}/bin:$PATH".format(virtual_env)
    ):
        run("paver update_assets lms")
        run("paver lms")
    return "openedx::step4"
