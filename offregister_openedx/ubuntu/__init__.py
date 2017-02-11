from os import path

from offutils import gen_random_str
from pkg_resources import resource_filename

from fabric.context_managers import cd, shell_env
from fabric.operations import sudo, run
from fabric.contrib.files import upload_template, sed

from offregister_fab_utils.apt import apt_depends
from offregister_fab_utils.git import clone_or_update


def ansible_bootstrap0(*args, **kwargs):
    """ Reimplemented in Fabric:
        github.com/edx/configuration/blob/e2d3ad7f8f3fbcd9047843e03b62b489ef39540e/util/install/ansible-bootstrap.sh """
    exit(1)

    apt_depends('python2.7', 'python2.7-dev', 'python-pip', 'python-apt', 'python-yaml', 'python-jinja2',
                'build-essential', 'sudo', 'git-core', 'libmysqlclient-dev', 'libffi-dev', 'libssl-dev',
                'python-software-properties')

    virtual_env_version = '15.0.2'
    pip_version = '8.1.2'
    setuptools_version = '24.0.3'
    virtual_env = '/tmp/bootstrap'
    configuration_dir = '/tmp/configuration'
    ''' # These don't seem to be used:
    python_bin = '{virtual_env}/bin'.format(virtual_env=virtual_env)
    ansible_dir = '/tmp/ansible'
    edx_ppa = 'deb http://ppa.edx.org precise main'
    edx_ppa_key_server = 'hkp://pgp.mit.edu:80'
    edx_ppa_key_id = 'b41e5e3969464050'
    '''

    openedx_release = kwargs.get('OPENEDX_RELEASE', 'open-release/ficus.1rc3')

    sudo('pip install setuptools=={}'.format(setuptools_version))
    sudo('pip install pip=={}'.format(pip_version))
    sudo('pip install virtualenv=={}'.format(virtual_env_version))
    if not path.isdir(virtual_env):
        run('virtualenv \'{}\''.format(virtual_env))
    clone_or_update(team='edx', repo='configuration',
                    branch=openedx_release,
                    to_dir=configuration_dir,
                    skip_reset=True)

    # TODO: Run this as a separate offregister task, using new ansible support
    with cd(configuration_dir), shell_env(VIRTUAL_ENV=virtual_env,
                                          PATH="{}/bin:$PATH".format(virtual_env)):
        run('make requirements')
        with cd('playbooks/edx-east'):
            run("ansible-playbook edx_ansible.yml -i '127.0.0.1,' -c local -e \"openedx_release='{}'\"".format(
                openedx_release))

    return 'openedx::step0', configuration_dir


def ansible_sandbox1(*args, **kwargs):
    """ Reimplemented in Fabric:
        github.com/edx/configuration/blob/98c6fb5dcc5e329c2b7fab5629e141568a081ba5/util/install/sandbox.sh """

    apt_depends('software-properties-common')
    sudo('add-apt-repository -y ppa:ubuntu-toolchain-r/test')
    apt_depends('build-essential', 'curl', 'git-core', 'libxml2-dev', 'libxslt1-dev',
                'python-pip', 'libmysqlclient-dev', 'python-apt', 'python-dev', 'libxmlsec1-dev', 'libfreetype6-dev',
                'swig', 'gcc', 'g++')

    openedx_release = kwargs.get('OPENEDX_RELEASE', 'open-release/ficus.1rc3')

    config_vars = ('edx_platform_version',
                   'certs_version',
                   'forum_version',
                   'xqueue_version',
                   'configuration_version',
                   'demo_version',
                   'NOTIFIER_VERSION',
                   'INSIGHTS_VERSION',
                   'ANALYTICS_API_VERSION',
                   'ECOMMERCE_VERSION',
                   'ECOMMERCE_WORKER_VERSION',
                   'PROGRAMS_VERSION')

    extra_vars_d = {k: "'{v}'".format(v=kwargs.get(k, openedx_release)) for k in config_vars}
    extra_vars_d['SANDBOX_ENABLE_ECOMMERCE'] = 'True'
    extra_vars = '-e ' + ' -e '.join('{k}={v}'.format(k=k, v=v) for k, v in extra_vars_d.iteritems())

    wd = '/var/tmp/configuration'
    clone_or_update(team='edx', repo='configuration',
                    branch=openedx_release,
                    to_dir=wd, skip_reset=True)
    home = run('echo $HOME')
    sudo('HOME="{home}" pip install -r "{wd}/requirements.txt"'.format(home=home, wd=wd))

    # TODO: Run this as a separate offregister task, using new ansible support
    with cd('{wd}/playbooks'.format(wd=wd)), shell_env(**extra_vars_d):
        sudo('ansible-playbook -c local ./edx_sandbox.yml -i "localhost," {extra_vars}'.format(extra_vars=extra_vars))

    return 'installed: {}'.format(openedx_release)


def step2(*args, **kwargs):
    run('echo hello world && ip addr')
    return 'openedx::step2'


def _step3(*args, **kwargs):
    clone_or_update(team='edx', repo='configuration', branch='open-release/ficus.1rc3', skip_reset=True)
    sudo('pip install -r configuration/requirements.txt')
    with cd('configuration/playbooks'):
        sudo('ansible-playbook -c local ./edx_sandbox.yml -i "localhost,"')
    '''
    with cd('configuration'):
        sudo('util/install/ansible-bootstrap.sh')
        sudo('util/install/sandbox.sh')
    '''
    return 'openedx::step1'


def _step4(*args, **kwargs):
    upload_template(resource_filename('offregister_openedx', path.join('conf', 'server-vars.yml')),
                    '/edx/app/edx_ansible/server-vars.yml', use_sudo=False,
                    context={'EMAIL_HOST_USER': gen_random_str(10),
                             'EMAIL_HOST_PASSWORD': gen_random_str(10)})


def _install_theme5(*args, **kwargs):
    clone_or_update(team='dadasoz', repo='edx-bootstrap-theme', branch='master',
                    to_dir='/edx/app/edxapp/edx-platform/themes/edx-bootstrap-theme')

    s = '"COMPREHENSIVE_THEME_DIR": "{}"'
    sed('/edx/app/edxapp/lms.env.json',
        s.format('/edx/app/edxapp/edx-platform/themes/edx-bootstrap-theme'),
        s.format(''),
        backup='', use_sudo=True, shell=True)
    return 'openedx::step3'


def _set_theme6(*args, **kwargs):
    virtual_env = '/edx/app/edxapp/venvs/edxapp'
    with cd('/edx/app/edxapp/edx-platform'), \
         shell_env(VIRTUAL_ENV=virtual_env, PATH="{}/bin:$PATH".format(virtual_env)):
        run('paver update_assets lms')
        run('paver lms')
    return 'openedx::step4'
