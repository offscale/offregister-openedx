from functools import partial
from json import load, dumps, dump
from sys import modules

from cStringIO import StringIO

from offutils import update_d, gen_random_str
from pkg_resources import resource_filename
from os import path

from fabric.context_managers import cd, shell_env
from fabric.contrib.files import append, exists, upload_template
from fabric.operations import sudo, put

from offregister_fab_utils.apt import apt_depends, is_installed
from offregister_fab_utils.git import clone_or_update
from offregister_fab_utils.ubuntu.systemd import restart_systemd

# Global variables
g_openedx_release = 'open-release/ginkgo.master'
g_context = {
    'EDXROOT': '/opt/openedx',
    'VENV': '/opt/openedx/venv'
}
g_platform_dir = '{root}/edx-platform'.format(root=g_context['EDXROOT'])
g_user = 'edxapp'
g_edxapp = partial(sudo, user=g_user, group=g_user, warn_only=True)

# Get file from config dir of this python package
g_file = lambda *paths: resource_filename(modules[__name__].__name__, path.join('config', *paths))


def install0(*args, **kwargs):
    openedx_release = kwargs.get('OPENEDX_RELEASE', g_openedx_release)

    # Services
    apt_depends('memcached', 'mysql-server', 'mysql-client', 'rabbitmq-server', 'mongodb-server', 'openjdk-8-jdk')
    sudo('wget -O - http://packages.elasticsearch.org/GPG-KEY-elasticsearch | apt-key add -')

    # Elasticsearch (optional)
    append('/etc/apt/sources.list.d/elasticsearch.list',
           'deb http://packages.elasticsearch.org/elasticsearch/0.90/debian stable main',
           use_sudo=True)
    sudo('apt update')
    if not is_installed('elasticsearch'):
        sudo('apt-get install -y elasticsearch=0.90.13')

    # LMS/CMS install prep
    apt_depends('gettext', 'gfortran', 'graphviz', 'graphviz-dev', 'libffi-dev', 'libfreetype6-dev', 'libgeos-dev',
                'libjpeg8-dev', 'liblapack-dev', 'libpng12-dev', 'libxml2-dev', 'libxmlsec1-dev', 'libxslt1-dev',
                'nodejs', 'npm', 'ntp', 'pkg-config')

    # Production
    apt_depends('supervisor', 'nginx')

    # LMS/CMS install
    # TODO: Create `edxapp` user
    sudo('mkdir -p {root} {root}/staticfiles {root}/uploads'.format(root=g_context['EDXROOT']))
    sudo('chown -R {user}:{user} {root}'.format(user=g_user, root=g_context['EDXROOT']))

    clone_or_update(team='edx', repo='edx-platform', branch=openedx_release, skip_reset=True, cmd_runner=g_edxapp,
                    to_dir=g_platform_dir)

    if not exists(g_context['VENV']):
        g_edxapp('virtualenv {}'.format(g_context['VENV']))
    with cd(g_platform_dir), shell_env(PATH='{}/bin:$PATH'.format(g_context['VENV']), VIRTUAL_ENV=g_context['VENV']):
        g_edxapp('pip install pip==8.1.2')
        g_edxapp('pip install setuptools==24.0.3')
        g_edxapp('pip install -r requirements/edx/pre.txt')
        g_edxapp('pip install -r requirements/edx/github.txt')  # go grab a coffee, this is going to take some time
        g_edxapp('pip install -r requirements/edx/local.txt')
        g_edxapp('pip install -r requirements/edx/base.txt')
        g_edxapp('pip install -r requirements/edx/post.txt')
        g_edxapp('pip install -r requirements/edx/paver.txt')
        g_edxapp('nodeenv -p')  # Install node environment in same virtualenv
        g_edxapp('paver install_prereqs')


def configure1(staff_user, staff_email, staff_pass, settings='production', https=False, *args, **kwargs):
    # Configuration files
    env = {'LOG_DIR': '{root}/logs'.format(root=g_context['EDXROOT']),
           'PLATFORM_NAME': kwargs['PLATFORM_NAME'],
           'FEATURES': {'PREVIEW_LMS_BASE': kwargs['PREVIEW_LMS_BASE']},
           'LMS_ROOT_URL': '{protocol}://{lms_site_name}'.format(protocol='https' if https else 'http',
                                                                 lms_site_name=kwargs['LMS_SITE_NAME']),
           'CMS_ROOT_URL': '{protocol}://{cms_site_name}'.format(protocol='https' if https else 'http',
                                                                 cms_site_name=kwargs['CMS_SITE_NAME']),
           'CMS_BASE': kwargs['CMS_SITE_NAME'],
           'LMS_BASE': kwargs['LMS_SITE_NAME'],
           'CELERY_BROKER_HOSTNAME': 'localhost',
           'MEDIA_ROOT': '{root}/uploads/'.format(root=g_context['EDXROOT'])}
    auth = {
        'SECRET_KEY': gen_random_str(32),
        'AWS_ACCESS_KEY_ID': kwargs.get('AWS_ACCESS_KEY_ID', ''),
        'AWS_SECRET_ACCESS_KEY': kwargs.get('AWS_SECRET_ACCESS_KEY', ''),
        'DATABASES': {
            'default': {
                'ENGINE': 'django.db.backends.mysql',
                'NAME': 'edxapp',
                'USER': 'edxapp',
                'PASSWORD': '--- database password ---',
                'HOST': 'localhost',
                'PORT': 3306,
                'ATOMIC_REQUESTS': True
            }
        }
    }
    deploy(system='cms', settings=settings, auth_config=auth,
           env_config=update_d(env, SITE_NAME=kwargs['CMS_SITE_NAME']))
    deploy(system='lms', settings=settings, auth_config=auth,
           env_config=update_d(env, SITE_NAME=kwargs['LMS_SITE_NAME']))

    # Configure database users
    with cd(g_platform_dir), shell_env(PATH='{}/bin:$PATH'.format(g_context['VENV']), VIRTUAL_ENV=g_context['VENV']):
        cmd = './manage.py lms --settings={settings}'.format(settings=settings)
        g_edxapp('{cmd} manage_user --superuser --staff {staff_user} {staff_email}'.format(cmd=cmd,
                                                                                           staff_user=staff_user,
                                                                                           staff_email=staff_email))
        sudo("{cmd} changepassword '{staff_pass}'".format(cmd=cmd, staff_pass=staff_pass),
             user=g_user, group=g_user, shell_escape=False)

    return restart_systemd('nginx')


#####################
# Utility functions #
#####################

def regen(system, paver=True, supervisor=True, settings='production'):
    with cd(g_platform_dir), shell_env(PATH='{}/bin:$PATH'.format(g_context['VENV']), VIRTUAL_ENV=g_context['VENV']):
        if paver:
            g_edxapp('paver update_assets {system} --settings={settings}'.format(system=system, settings=settings))
        if supervisor:
            sudo('supervisorctl restart {system}:'.format(system=system))


def update_and_put(d, merge_d, put_location, use_sudo=False):
    d.update(merge_d)
    sio = StringIO()
    dump(d, sio)
    return put(sio, put_location, use_sudo=use_sudo)


def deploy(system, settings, auth_config, env_config):
    with open(g_file(system, '{system}.auth.json'.format(system=system))) as f:
        auth = load(f)
    update_and_put(auth, auth_config, '{root}/{system}.auth.json'.format(root=g_context['EDXROOT'], system=system),
                   use_sudo=True)

    with open(g_file(system, '{system}.env.json'.format(system=system))) as f:
        env = load(f)
    update_and_put(env, env_config, '{root}/{system}.env.json'.format(root=g_context['EDXROOT'], system=system),
                   use_sudo=True)

    upload_template(g_file(system, '{settings}.py'.format(settings=settings)),
                    '{platform_dir}/{system}/envs/{settings}.py'.format(platform_dir=g_platform_dir, system=system,
                                                                        settings=settings),
                    use_sudo=False, context=g_context)

    if settings == 'production':
        upload_template(g_file(system, 'nginx', 'sites-enabled', '{system}.conf'.format(system=system)),
                        '/etc/nginx/sites-enabled/{system}.conf'.format(system=system), context=g_context)
