import builtins
import json

from blessings import Terminal
from flask import current_app
import mock
from mongoframes import *
from pytest import *

from commands.accounts import *
from models.accounts import Account
from tests import *


def mock_input(responses):
    """Return a function that will mock user input"""

    response_index = {'index': 0}

    def _input(question):
        response = responses[response_index['index']]
        response_index['index'] += 1
        return response

    return _input

def test_add_account(capsys, app):
    # Add a new account
    responses = ['tests/data/assets']
    with mock.patch.object(builtins, 'input', mock_input(responses)):
        AddAccount().run('test', 'local')

    # Check the output is as expected
    account = Account.one()
    assert 'Account added: {0}'.format(account.api_key) == \
        capsys.readouterr()[0].strip().split('\n')[-1]

    # Check the account was created correctly
    assert account.name == 'test'
    assert account.backend == json.load(open('tests/data/local.cfg'))
    assert account.api_key

def test_config_account(capsys, app, test_accounts):
    # Configure an account
    responses = [
        'AKIAIW5ILOAT5ZJ5XWJQ',
        'y80Io/ukJhZxaiHd4ngEVxIC7v96D+z+tJOFOoY2',
        'hangar51test'
        ]
    with mock.patch.object(builtins, 'input', mock_input(responses)):
        ConfigAccount().run('hangar51')

    # Check the output is as expected
    assert 'Account configured' == \
        capsys.readouterr()[0].strip().split('\n')[-1]

    # Check the account was configured correctly
    account = Account.one(Q.name == 'hangar51')
    assert account.backend['access_key'] == 'AKIAIW5ILOAT5ZJ5XWJQ'
    assert account.backend['secret_key'] == \
            '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'
    assert account.backend['bucket'] == 'hangar51test'

def test_delete_account(capsys, app, test_accounts):
    # Delete an account
    DeleteAccount().run('getme')

    # Check the output is as expected
    assert 'Account deleted' == capsys.readouterr()[0].strip()

    # Check there is no longer an account for 'getme'
    getme = Account.one(Q.name == 'getme')
    assert getme is None

def test_generate_new_api_key(capsys, app, test_accounts):
    # Find an existing account change the API key for
    old_api_key = Account.one(Q.name == 'getme').api_key

    # Generate a new API key for an account
    GenerateNewAPIKey().run('getme')

    # Check a new API key has been generated
    new_api_key = Account.one(Q.name == 'getme').api_key
    assert new_api_key
    assert new_api_key != old_api_key

    # Check the output is as expected
    assert 'New key generated: {0}'.format(new_api_key) \
            == capsys.readouterr()[0].strip()

def test_list_accounts(capsys, app, test_accounts):
    # Get a list of *all* accounts
    ListAccounts().run()

    # Check output is as expected
    expected_out = [
        'Accounts (9):',
        '- burst (using local)',
        '- deploycms (using local)',
        '- geocode (using local)',
        '- getcontenttools (using local)',
        '- getme (using local)',
        '- glitch (using s3)',
        '- hangar51 (using s3)',
        '- lupin (using s3)',
        '- mongoframes (using s3)'
        ]
    expected_out = '\n'.join(expected_out)
    out = capsys.readouterr()[0].strip()
    assert out == expected_out

    # Get a list of accounts containing the string 'ge'
    ListAccounts().run('ge')
    expected_out = [
        "Accounts matching 'ge' (3):",
        '- geocode (using local)',
        '- getcontenttools (using local)',
        '- getme (using local)'
        ]
    expected_out = '\n'.join(expected_out)
    out = capsys.readouterr()[0].strip()
    assert out == expected_out

def test_list_backends(capsys, app):
    # Get a list of supported backends
    ListBackends().run()

    # Check the output is as expected
    expected_out = [
        'Backends (2):',
        '- local',
        '- s3'
        ]
    expected_out = '\n'.join(expected_out)
    out = capsys.readouterr()[0].strip()

    assert out == expected_out

def test_rename_account(capsys, app, test_accounts):
    getme = Account.one(Q.name == 'getme').api_key

    # Generate a new API key for an account
    RenameAccount().run('getme', 'new_getme')

    # Check the account has been renamed
    new_getme = Account.one(Q.name == 'new_getme').api_key
    assert new_getme == getme

    # Check the output is as expected
    assert 'Account renamed: new_getme' == capsys.readouterr()[0].strip()

def test_view_account(capsys, app, test_accounts):
    # View the details for an account
    ViewAccount().run('getme')

    # Find the account in question as some details are generate when the account
    # is created.
    getme = Account.one(Q.name == 'getme')

    # Check output is as expected
    expected_out = [
        "About 'getme':",
        '- created------- ' + str(getme.created),
        '- modified------ ' + str(getme.modified),
        '- assets-------- 0',
        '- api_key------- ' + getme.api_key,
        '- backend------- local',
        '- > asset_root-- tests/data/assets'
        ]
    expected_out = '\n'.join(expected_out)
    out = capsys.readouterr()[0].strip()
    assert out == expected_out