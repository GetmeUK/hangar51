"""
Command line tools for managing the application.
"""

from flask import current_app
from mongoframes import *

from commands import AppCommand
from models.accounts import Account
from models.assets import Asset, Variation


class Drop(AppCommand):
    """
    Drop the application.
    """

    def run(self):

        # Confirm the drop
        if not self.confirm('Enter the following string to confirm drop', \
                    'hangar51'):
            return

        # Delete all accounts, assets and files
        accounts = Account.many()
        for account in accounts:
            account.purge()

        # Drop the collections
        Asset.get_collection().drop()
        Account.get_collection().drop()


class Init(AppCommand):
    """
    Initialize the application.
    """

    models = [
        Account,
        Asset
        ]

    def run(self):

        # Initialzie the application database
        for model in self.models:

            # (Re)create indexes for collections that specify them
            if hasattr(model, '_indexes'):
                model.get_collection().drop_indexes()
                model.get_collection().create_indexes(model._indexes)