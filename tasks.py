import argparse
from celery import Celery
from datetime import datetime, timezone
import json
from mongoframes import *
from PIL import Image
import requests
import time

from app import create_app
from models.accounts import Account
from models.assets import Asset, Variation

__all__ = ['setup_tasks']


# Define the tasks for the application
def setup_tasks(celery):

    @celery.task(name='generate_variations')
    def generate_variations(account_id, asset_uid, variations, webhook=''):
        """Generate a set of variations for an image asset"""

        # Find the account
        account = Account.by_id(account_id)
        if not account:
            return

        # Find the asset
        asset = Asset.one(And(Q.account == account, Q.uid == asset_uid))
        if not asset:
            return

        # Check the asset hasn't expired
        if asset.expired:
            return

        # Retrieve the original file
        backend = account.get_backend_instance()
        f = backend.retrieve(asset.store_key)
        im = Image.open(f)

        # Generate the variations
        new_variations = {}
        for name, ops in variations.items():
            variation = asset.add_variation(im, name, ops)
            new_variations[name] = variation.to_json_type()

        # Update the assets modified timestamp
        asset.update('modified')

        # If a webhook has been provide call it with details of the new
        # variations.
        if webhook:
            requests.get(
                webhook,
                data={
                    'account': account.name,
                    'asset': asset.uid,
                    'variations': json.dumps(variations)
                    }
                )

    @celery.task(name='purge_expired_assets')
    def purge_expired_assets():
        """Purge assets which have expired"""

        # Get any asset that has expired
        now = time.mktime(datetime.now(timezone.utc).timetuple())
        assets = Asset.many(And(
            Exists(Q.expires, True),
            Q.expires <= now
            ))

        # Purge each asset
        for asset in assets:
            asset.purge()