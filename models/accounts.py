from mongoframes import *
from uuid import uuid4

from backends import Backend

__all__ = ['Account']


class Account(Frame):
    """
    Accounts provide access control and backend configuration.
    """

    _fields = {
        'created',
        'modified',
        'name',
        'api_key',
        'backend'
        }
    _indexes = [
        IndexModel([('name', ASC)], unique=True),
        IndexModel([('api_key', ASC)], unique=True)
    ]

    def __str__(self):
        return self.name

    def get_backend_instance(self):
        """Return a configured instance of the backend for the account"""
        backendCls = Backend.get_backend(self.backend['backend'])
        return backendCls(**self.backend)

    def purge(self):
        """Deletes the account along with all related assets and files."""
        from models.assets import Asset

        # Purge all assets
        for asset in Asset.many(Q.account == self):
            asset.account = self
            asset.purge()

        # Delete self
        self.delete()

    @staticmethod
    def generate_api_key():
        return str(uuid4())

    @staticmethod
    def on_insert(sender, frames):
        # Set an API key for newely created accounts
        for frame in frames:
            frame.api_key = sender.generate_api_key()

Account.listen('insert', Account.timestamp_insert)
Account.listen('insert', Account.on_insert)
Account.listen('update', Account.timestamp_update)