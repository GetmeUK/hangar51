import argparse
from celery import Celery

from app import create_app
from tasks import setup_tasks


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
args, unknown = parser.parse_known_args()

# Create and run the application
celery = create_app(args.env).celery

setup_tasks(celery)