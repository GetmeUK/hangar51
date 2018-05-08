"""
A set of pytest fixtures to help create test suites for Flask applications.
"""

from flask import appcontext_tearing_down, \
    current_app, \
    message_flashed, \
    template_rendered, \
    url_for, \
    _app_ctx_stack

import io
import json
from mongoframes import *
import os
import pytest

from app import create_app
from commands import Drop, Init, AddAccount
from models.accounts import Account
from models.assets import Asset, Variation
from tasks import setup_tasks

__all__ = [
    'app',
    'celery_app',
    'client',
    'flashed',
    'template',

    # Data generators
    'test_accounts',
    'test_backends',
    'test_images',
    'test_local_account',
    'test_local_assets'
    ]


class TemplateInfo:
    """
    A class that retains information about a `render_template` call.
    """

    def __init__(self):
        self.path = None
        self.args = None


@pytest.yield_fixture(scope="session")
def app():
    """Return a test application"""
    app = create_app('test')

    # Make sure the app is initialized
    Init().run()

    def teardown(sender, **kwargs):
        # HACK: Check that the teardown is for the last item in the app context
        # stack, otherwise don't drop the app yet.
        #
        # I don't know enough about the internal workings of flask or werkzeug
        # Context Locals to be sure this is a safe solution. Any additional
        # input/advice on the matter would be welcome.
        #
        # Anthony Blackshaw <ant@getme.co.uk>
        if len(getattr(_app_ctx_stack._local, 'stack', [])) > 1:
            return

        # Drop the application
        Drop().run()

    with appcontext_tearing_down.connected_to(teardown, app):
        yield app

@pytest.yield_fixture
def celery_app(app):
    """Return a test celery application"""
    setup_tasks(app.celery)

    yield app.celery

@pytest.yield_fixture
def client(app):
    """Return a test client for the app"""
    with app.test_client() as client:
        yield client

@pytest.yield_fixture
def flashed(app):
    """Return information about messages flashed"""
    with app.test_client() as client:

        flashes = []

        def on_message_flashed(sender, category, message):
            flashes.append((message, category))

        message_flashed.connect(on_message_flashed)

        yield flashes

@pytest.yield_fixture
def template(app):
    """Return information about templates rendered"""

    with app.test_client() as client:

        template_info = TemplateInfo()

        def on_template_rendered(sender, template, **kwargs):
            template_info.path = template.name
            template_info.args = kwargs['context']

        template_rendered.connect(on_template_rendered)

        yield template_info


# Data generators

@pytest.yield_fixture
def test_accounts(app):
    """Load test accounts"""

    # Load the test account information
    with open('tests/data/accounts.json') as f:
        data = json.load(f)

    # Add the test accounts
    accounts = []
    for account_data in data:

        with open('tests/data/' + account_data['config_filepath']) as f:
            config = json.load(f)

        account = Account(
            name=account_data['name'],
            backend=config
            )
        account.insert()
        accounts.append(account)

    yield accounts

    # Purge the accounts
    for account in accounts:
        account.purge()

@pytest.yield_fixture
def test_backends(app):
    """Create accounts to support each backend"""

    # Add the test accounts for each backend
    accounts = []
    for backend in ['local', 's3']:

        with open('tests/data/{backend}.cfg'.format(backend=backend)) as f:
            config = json.load(f)

        account = Account(name=backend, backend=config)
        account.insert()
        accounts.append(account)

    yield accounts

    # Purge the accounts
    for account in accounts:
        account.purge()

@pytest.yield_fixture
def test_images(app, client, test_backends):
    """Create a test image asset for all backends"""
    for account in test_backends:

        # Load the file to upload
        with open('tests/data/assets/uploads/image.jpg', 'rb') as f:
            file_stream = io.BytesIO(f.read())

        # Upload the file
        response = client.post(
            url_for('api.upload'),
            data=dict(
                api_key=account.api_key,
                asset=(file_stream, 'image.jpg')
                )
            )

    assets = Asset.many()
    yield assets

    # Purge the assets
    for asset in assets:

        # Reload the asset to make sure it still exists before we attempt to
        # purge it.
        asset = asset.by_id(asset._id)
        if asset:
            asset.purge()

@pytest.yield_fixture
def test_local_account(app):
    """Create a local account"""

    # Add the local account
    with open('tests/data/local.cfg') as f:
        config = json.load(f)

    account = Account(name='local', backend=config)
    account.insert()

    yield account

    # Purge the account
    account.purge()

@pytest.yield_fixture
def test_local_assets(client, test_local_account):
    """Create a set of test assets"""
    account = test_local_account

    # Upload all test assets
    filepath = 'tests/data/assets/uploads'
    for filename in os.listdir(filepath):

        # Load the file to upload
        with open(os.path.join(filepath, filename), 'rb') as f:
            file_stream = io.BytesIO(f.read())

        # Upload the file
        response = client.post(
            url_for('api.upload'),
            data=dict(
                api_key=account.api_key,
                asset=(file_stream, filename),
                )
            )

        # Generate a variation for the `image.jpg` asset
        if filename == 'image.jpg':
            variations = {
                'test': [
                    ['fit', [100, 100]],
                    ['output', {'format': 'webp', 'quality': 50}]
                    ]
                }

            client.post(
                url_for('api.generate_variations'),
                data=dict(
                    api_key=account.api_key,
                    uid=response.json['payload']['uid'],
                    variations=json.dumps(variations)
                    )
                )

    assets = Asset.many()
    yield assets

    # Purge the assets
    for asset in assets:

        # Reload the asset to make sure it still exists before we attempt to
        # purge it.
        asset = asset.by_id(asset._id)
        if asset:
            asset.purge()