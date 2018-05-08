"""
Initialization of the application.
"""

import argparse
from celery import Celery
from celery.bin import Option
from flask import Flask, jsonify
from mongoframes import Frame
import pymongo
from raven.contrib.flask import Sentry
from werkzeug.contrib.fixers import ProxyFix


__all__ = ['create_app']


sentry = Sentry()

def create_app(env):
    """
    We use an application factory to allow the app to be configured from the
    command line at start up.
    """

    # Create the app
    app = Flask(__name__)

    # Configure the application to the specified config
    app.config['ENV'] = env
    app.config.from_object('settings.{0}.Config'.format(env))

    # Add celery
    app.celery = create_celery_app(app)

    # Add sentry logging if the DSN is provided
    if app.config['SENTRY_DSN']:
        app.sentry = sentry.init_app(app)

    # Add mongo support
    app.mongo = pymongo.MongoClient(app.config['MONGO_URI'])
    app.db = app.mongo.get_default_database()
    Frame._client = app.mongo

    if app.config.get('MONGO_PASSWORD'):
        Frame.get_db().authenticate(
            app.config.get('MONGO_USERNAME'),
            app.config.get('MONGO_PASSWORD')
            )

    # Fix for REMOTE_ADDR value
    app.wsgi_app = ProxyFix(app.wsgi_app)

    # Import views as a blueprint
    import api
    app.register_blueprint(api.api)
    return app

def create_celery_app(app):
    """
    This function integrates celery into Flask, see ref here:
    http://flask.pocoo.org/docs/0.10/patterns/celery/
    """

    # Create a new celery object and configure it using the apps config
    celery = Celery(app.import_name, broker=app.config['CELERY_BROKER_URL'])
    app.config['CELERY_RESULT_BACKEND'] = app.config['CELERY_BROKER_URL']
    celery.conf.update(app.config)

    # Add the env option
    option = Option(
        '-e',
        '--env',
        choices=['dev', 'local', 'prod'],
        default='local',
        dest='env'
        )

    celery.user_options['beat'].add(option)
    celery.user_options['worker'].add(option)

    # Create a sub class of the celery Task class that exectures within the
    # application's context.
    TaskBase = celery.Task
    class ContextTask(TaskBase):
        abstract = True
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)
    celery.Task = ContextTask

    return celery


if __name__ == "__main__":

    # Parse the command-line arguments
    parser = argparse.ArgumentParser(description='Application server')
    parser.add_argument(
        '-e',
        '--env',
        choices=['dev', 'local', 'prod'],
        default='local',
        dest='env',
        required=False
        )
    args = parser.parse_args()

    # Create and run the application
    app = create_app(args.env)
    app.run(port=app.config.get('PORT', 5152))