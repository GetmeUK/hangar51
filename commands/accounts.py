"""
Command line tools for managing accounts.
"""

from blessings import Terminal
from flask import current_app
from flask.ext.script import Command, Option
import json
from mongoframes import *
import re

from backends import Backend
from commands import AppCommand
from forms.accounts import *
from models.accounts import Account
from models.assets import Asset

__all__ = [
    'AddAccount',
    'ConfigAccount',
    'DeleteAccount',
    'GenerateNewAPIKey',
    'ListAccounts',
    'ListBackends',
    'RenameAccount',
    'ViewAccount'
    ]


class AddAccount(AppCommand):
    """
    Add an account.

    `python manage.py add-account {name} {backend}`
    """

    def get_options(self):
        return [
            Option(dest='name'),
            Option(dest='backend')
            ]

    def run(self, name, backend):

        # Validate the parameters
        form = AddAccountForm(name=name, backend=backend)
        if not form.validate():
            self.err(**form.errors)
            return

        # Ask the user for the backend configuration options
        backend = Backend.get_backend(backend)
        config = {'backend': form.data['backend']}
        for field in backend.config_form():
            self.out((field.label.text, 'blue'))
            value = input('> ').strip()
            if value:
                config[field.name] = value

        # Validate the users configuration
        result = backend.validate_config(**config)
        if not result[0]:
            self.err('Invalid backend config:', **result[1])
            return

        # Create the new account
        account = Account(
            name=form.data['name'],
            backend=config
            )
        account.insert()

        self.out(('Account added: {0}'.format(account.api_key), 'bold_green'))


class ConfigAccount(AppCommand):
    """
    Configure an account storage backend.

    `python manage.py config-account {name} {congig-file.json}`
    """

    def get_options(self):
        return [Option(dest='name')]

    def run(self, name):

        # Validate the parameters
        form = ConfigAccountBackendForm(name=name)
        if not form.validate():
            self.err(**form.errors)
            return

        # Find the account to be configured
        account = Account.one(Q.name == form.data['name'])

        # Let the user know to use dash to clear existing values
        self.out((
            '* Enter dash (-) to clear the existing value',
            'underline_bold_blue'
            ))

        # Ask the user for the backend configuration options
        backend = Backend.get_backend(account.backend['backend'])
        config = {'backend': account.backend['backend']}
        for field in backend.config_form():

            # Request the value
            self.out((field.label.text, 'blue'))
            value = input('({0}) > '.format(
                account.backend.get(field.name, '')))
            value = value.strip()

            # Check if the value should be set to the original, cleared or used
            # as provided.
            if value:
                if value == '-':
                    continue
                else:
                    config[field.name] = value
            else:
                if account.backend.get(field.name):
                    config[field.name] = account.backend.get(field.name)

        # Validate the users configuration
        result = backend.validate_config(**config)
        if not result[0]:
            self.err('Invalid backend config:', **result[1])
            return

        # Update the accounts backend
        account.backend = config
        account.update('modified', 'backend')

        self.out(('Account configured', 'bold_green'))


class DeleteAccount(AppCommand):
    """
    Delete an account.

    `python manage.py delete-account {name}`
    """

    def get_options(self):
        return [Option(dest='name')]

    def run(self, name):

        # Validate the parameters
        form = DeleteAccountForm(name=name)
        if not form.validate():
            self.err(**form.errors)
            return

        # Find the account to be deleted
        account = Account.one(Q.name == form.data['name'])

        # Confirm the account deletion
        if not self.confirm('Enter the following string to confirm you want to \
delete this account deletion', account.name):
            return

        # Delete the account
        account.delete()

        self.out(('Account deleted', 'bold_green'))


class GenerateNewAPIKey(AppCommand):
    """
    Generate a new API key for an account.

    `python manage.py generate-new-api-key {name}`
    """

    def get_options(self):
        return [Option(dest='name')]

    def run(self, name):

        # Validate the parameters
        form = GenerateNewAccountAPIKeyForm(name=name)
        if not form.validate():
            self.err(**form.errors)
            return

        # Find the account to generate a new API key for
        account = Account.one(Q.name == form.data['name'])

        # Confirm the account deletion
        if not self.confirm('Enter the following string to confirm you want to \
generate a new API key for this account', account.name):
            return

        # Generate a new API key for the account
        account.api_key = account.generate_api_key()
        account.update('modified', 'api_key')

        self.out(('New key generated: ' + account.api_key, 'bold_green'))


class ListAccounts(AppCommand):
    """
    List all accounts.

    `python manage.py list-accounts -q`
    """

    def get_options(self):
        return [Option(
            '-q',
            dest='q',
            default='',
            help='filter the list by the specified value'
            )]

    def run(self, q=''):

        # If `q` is specified we filter the list of accounts to only accounts
        # with names that contain the value of `q`.
        filter = {}
        if q:
            filter = Q.name == re.compile(re.escape(q), re.I)

        # Get the list of accounts
        accounts = Account.many(filter, sort=[('name', ASC)])

        # Print a list of accounts
        output = []

        if q:
            output.append((
                "Accounts matching '{0}' ({1}):".format(q, len(accounts)),
                'underline_bold_blue'
                ))
        else:
            output.append((
                'Accounts ({0}):'.format(len(accounts)),
                'underline_bold_blue'
                ))

        for account in accounts:
            output.append((
                '- {name} (using {backend})'.format(
                    name=account.name,
                    backend=account.backend.get('backend', 'unknown')
                    ),
                'blue'
                ))

        self.out(*output)


class ListBackends(AppCommand):
    """
    List the available storage backends.

    `python manage.py list-backends`
    """

    def run(self):

        # Print a list of available backends
        output = [(
            'Backends ({0}):'.format(len(Backend.list_backends())),
            'underline_bold_blue'
            )]
        for backend in Backend.list_backends():
            output.append(('- ' + backend, 'blue'))

        self.out(*output)


class RenameAccount(AppCommand):
    """
    Rename an existing account.

    `python manage.py rename-account {name} {new_name}`
    """

    def get_options(self):
        return [
            Option(dest='name'),
            Option(dest='new_name')
            ]

    def run(self, name, new_name):

        # Validate the parameters
        form = RenameAccountForm(name=name, new_name=new_name)

        if not form.validate():
            self.err(**form.errors)
            return

        # Find the account to rename
        account = Account.one(Q.name == form.data['name'])

        # Set the accounts new name
        account.name = form.data['new_name']
        account.update('modified', 'name')

        self.out(('Account renamed: ' + account.name, 'bold_green'))


class ViewAccount(AppCommand):
    """
    View the details for an account.

    `python manage.py view-account {name}`
    """

    def get_options(self):
        return [Option(dest='name')]

    def run(self, name):

        # Validate the parameters
        form = ViewAccountForm(name=name)
        if not form.validate():
            self.err(**form.errors)
            return

        # Find the account to view
        account = Account.one(Q.name == form.data['name'])

        # Output details of the account
        output = [("About '{0}':".format(account.name), 'underline_bold_blue')]

        pairs = [
            ('created', account.created),
            ('modified', account.modified),
            ('assets', Asset.count(Q.account == account)),
            ('api_key', account.api_key),
            ('backend', account.backend.get('backend', 'unknown'))
            ]

        for key in sorted(account.backend.keys()):
            if key == 'backend':
                continue
            pairs.append(('> ' + key, account.backend[key]))

        # Find the longest key so we pad/align values
        width = sorted([len(p[0]) for p in pairs])[-1] + 2

        for pair in pairs:
            pair_str = '- {key:-<{width}} {value}'.format(
                    key=pair[0].ljust(width, '-'),
                    value=pair[1],
                    width=width
                    )
            output.append((pair_str, 'blue'))

        self.out(*output)