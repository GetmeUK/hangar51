"""
Fabric is used to deploy changes and run tasks across multiple environments.
"""

import os, sys, shutil, time, datetime

from fabric.api import *
from fabric.colors import red, blue, green, yellow
from fabric.contrib.console import confirm
from fabric.contrib.files import exists
from fabric.operations import local


# Setup up the environments
env.branch = 'master'
env.env = 'local'
env.home = ''
env.hosts = ['localhost']
env.project_repo = ''
env.runner = local

@task
def prod():
    env.home = '/sites/hangar51'
    env.env = 'prod'
    env.hosts = ['']
    env.runner = run
    env.user = 'hangar51'


# Tasks

@task
def deploy():
    """Push changes to the server"""
    with cd(env.home):
        # Checkout to the relevant branch
        env.runner('git checkout ' + env.branch)

        # Pull down the changes from the repo
        env.runner('git pull')

@task(alias='m')
def manage(manage_task):
    """Run a manage task"""
    if env.env == 'local':
        env.runner('python manage.py {task}'.format(task=manage_task))
    else:
        env.runner(
            'bin/python manage.py --env {env} {task}'.format(
                env=env.env,
                task=manage_task
                )
            )


@task(alias='pip')
def install_pip_requirements():
    """Install all pip requirements"""

    with cd(env.home):
        if env.env == 'local':
            # For local environments assume the virtual environment is activated
            # and attempt the pip install.
            local('pip install -r requirements.txt')
        else:
            env.runner('bin/pip install -r requirements.txt')

@task(alias='up')
def start_app():
    """Start the application"""
    if env.env == 'local':
        local('python app.py')
    else:
        sudo('/usr/bin/supervisorctl start hangar51_server', shell=False)

@task(alias='down')
def stop_app():
    """Stop the application"""
    if env.env == 'local':
        # When the app is run locally it doesn't deamonize
        pass

    else:
        sudo('/usr/bin/supervisorctl stop hangar51_server', shell=False)

@task(alias='cycle')
def cycle_app():
    """Cycle the application"""
    stop_app()
    start_app()

@task(alias='tasks_up')
def start_background_tasks():
    """Start the celery task queue"""
    if env.env == 'local':
        # When run locally we only fire up the worker (not beats)
        local('celery -A run_tasks worker')

    else:
        # Start the tasks worker
        sudo('/usr/bin/supervisorctl start hangar51_worker', shell=False)

        # Start the beat
        if env.host_string == env.hosts[0]:
            sudo('/usr/bin/supervisorctl start hangar51_beat', shell=False)

@task(alias='tasks_down')
def stop_background_tasks():
    """Stop the celery task queue"""
    if env.env == 'local':
        # When the tasks are run locally celery doesn't deamonize
        pass

    else:
        # Stop the tasks worker
        sudo('/usr/bin/supervisorctl stop hangar51_beat', shell=False)

        # Stop the beat
        if env.host_string == env.hosts[0]:
            sudo('/usr/bin/supervisorctl stop hangar51_worker', shell=False)