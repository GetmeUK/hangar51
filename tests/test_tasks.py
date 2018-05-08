from datetime import datetime, timedelta, timezone
from mongoframes import *
import time

from models.accounts import Account
from models.assets import Asset
from tests import *


def test_generate_varations(celery_app, test_images):
    asset = test_images[0]

    # Define the variation to generate
    variations = {
        'test': [
            ['fit', [200, 200]],
            ['crop', [0, 0.5, 0.5, 0]],
            ['rotate', 90],
            ['output', {'format': 'jpg', 'quality': 50}]
            ]
        }

    # Call the `generate_variation` task
    task = celery_app.tasks['generate_variations']
    task.apply([asset.account, asset.uid, variations])

    # Check the variation was generated
    asset.reload()
    assert len(asset.variations) == 1

    variation = asset.variations[0]
    assert variation['ext'] == 'jpg'
    assert variation['name'] == 'test'
    key = 'image.{uid}.test.{version}.jpg'.format(
        uid=asset.uid,
        version=variation['version']
        )
    assert variation['store_key'] == key
    assert variation['meta']['image'] == {
        'mode': 'RGB',
        'size': [200, 150]
        }

def test_purge_expired_assets(celery_app, test_images):
    # Set the expiry date for all assets to an hour ago
    expires = datetime.now(timezone.utc) - timedelta(seconds=3600)
    expires = time.mktime(expires.timetuple())
    assets = Asset.many()
    for asset in assets:
        asset.expires = expires
        asset.update('modified', 'expires')

    # Call the `purge_expired_assets` task
    task = celery_app.tasks['purge_expired_assets']
    task.apply()

    # Check all the assets where purged
    assert Asset.count() == 0
