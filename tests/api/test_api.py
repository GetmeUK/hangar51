from datetime import datetime, timedelta, timezone
from flask import current_app, g, url_for
import io
import json
from mongoframes import *
import time

from models.accounts import Account
from models.assets import Asset
from tests import *


def test_list(client, test_local_account, test_local_assets):
    account = test_local_account

    # Get all assets
    response = client.get(
        url_for('api.list'),
        data=dict(
            api_key=account.api_key
            )
        )
    assert response.json['status'] == 'success'

    # Check the response is correct
    payload = response.json['payload']
    assert payload['total_assets'] == 9
    assert payload['total_pages'] == 1
    assert payload['assets'][0]['store_key'].startswith('cdrs')
    assert payload['assets'][1]['store_key'].startswith('dribbbleshot')
    assert payload['assets'][2]['store_key'].startswith('file')
    assert payload['assets'][3]['store_key'].startswith('frameless')
    assert payload['assets'][4]['store_key'].startswith('gloop')
    assert payload['assets'][5]['store_key'].startswith('image-no-ext')
    assert payload['assets'][6]['store_key'].startswith('image')
    assert payload['assets'][7]['store_key'].startswith('navicons')
    assert payload['assets'][8]['store_key'].startswith('navigation-ui')

    # Get all file assets
    response = client.get(
        url_for('api.list'),
        data=dict(
            api_key=account.api_key,
            type='file'
            )
        )
    assert response.json['status'] == 'success'

    # Check the response is correct
    payload = response.json['payload']
    assert payload['total_assets'] == 2
    assert payload['total_pages'] == 1
    assert payload['assets'][0]['store_key'].startswith('file')
    assert payload['assets'][1]['store_key'].startswith('frameless')

    # Get all image assets
    response = client.get(
        url_for('api.list'),
        data=dict(
            api_key=account.api_key,
            type='image'
            )
        )
    assert response.json['status'] == 'success'

    # Check the response is correct
    payload = response.json['payload']
    assert payload['total_assets'] == 7
    assert payload['total_pages'] == 1
    assert payload['assets'][0]['store_key'].startswith('cdrs')
    assert payload['assets'][1]['store_key'].startswith('dribbbleshot')
    assert payload['assets'][2]['store_key'].startswith('gloop')
    assert payload['assets'][3]['store_key'].startswith('image-no-ext')
    assert payload['assets'][4]['store_key'].startswith('image')
    assert payload['assets'][5]['store_key'].startswith('navicons')
    assert payload['assets'][6]['store_key'].startswith('navigation-ui')

    # Get all jpg assets
    response = client.get(
        url_for('api.list'),
        data=dict(
            api_key=account.api_key,
            type='image',
            q='*.jpg'
            )
        )
    assert response.json['status'] == 'success'

    # Check the response is correct
    payload = response.json['payload']
    assert payload['total_assets'] == 3
    assert payload['total_pages'] == 1
    assert payload['assets'][0]['store_key'].startswith('gloop')
    assert payload['assets'][1]['store_key'].startswith('image')
    assert payload['assets'][2]['store_key'].startswith('navigation-ui')

    # Get all assets starting with 'f'
    response = client.get(
        url_for('api.list'),
        data=dict(
            api_key=account.api_key,
            q='f*'
            )
        )
    assert response.json['status'] == 'success'

    # Check the response is correct
    payload = response.json['payload']
    assert payload['total_assets'] == 2
    assert payload['total_pages'] == 1
    assert payload['assets'][0]['store_key'].startswith('file')
    assert payload['assets'][1]['store_key'].startswith('frameless')

def test_generate_variations(client, test_backends, test_images):
    # Define a set of variations for the image
    variations = {
        'test1': [
            ['fit', [200, 200]],
            ['crop', [0, 0.5, 0.5, 0]],
            ['rotate', 90],
            ['output', {'format': 'jpg', 'quality': 50}]
            ],
        'test2': [
            ['fit', [100, 100]],
            ['rotate', 90],
            ['crop', [0, 0.5, 0.5, 0]],
            ['rotate', 180],
            ['output', {'format': 'webp', 'quality': 50}]
            ]
        }

    # Test each backend
    for account in test_backends:
        asset = Asset.one(And(Q.account == account, Q.name == 'image'))
        response = client.post(
            url_for('api.generate_variations'),
            data=dict(
                api_key=account.api_key,
                uid=asset.uid,
                variations=json.dumps(variations),
                on_delivery='wait'
                )
            )
        assert response.json['status'] == 'success'

        # Check the response is correct
        payload = response.json['payload']
        assert len(payload.keys()) == 2

        # Test variation 1
        assert 'test1' in payload
        assert payload['test1']['ext'] == 'jpg'
        assert payload['test1']['name'] == 'test1'
        key = 'image.{uid}.test1.{version}.jpg'.format(
            uid=asset.uid,
            version=payload['test1']['version']
            )
        assert payload['test1']['store_key'] == key
        assert payload['test1']['meta']['image'] == {
            'mode': 'RGB',
            'size': [200, 150]
            }

        # Test variation 2
        assert 'test2' in payload
        assert payload['test2']['ext'] == 'webp'
        assert payload['test2']['name'] == 'test2'
        key = 'image.{uid}.test2.{version}.webp'.format(
            uid=asset.uid,
            version=payload['test2']['version']
            )
        assert payload['test2']['store_key'] == key
        assert payload['test2']['meta']['image'] == {
            'mode': 'RGBA',
            'size': [100, 75]
            }

def test_get(client, test_local_account, test_local_assets):
    account = test_local_account

    # Find a file and image asset to get
    file_asset = Asset.one(Q.name == 'file')
    image_asset = Asset.one(Q.name =='image')

    # Get the details for a file
    response = client.get(
        url_for('api.get'),
        data=dict(
            api_key=account.api_key,
            uid=file_asset.uid
            )
        )
    assert response.json['status'] == 'success'

    # Check that the asset information returned is correct
    payload = response.json['payload']
    assert payload.get('created') is not None
    assert payload['ext'] == 'zip'
    assert payload['meta']['filename'] == 'file.zip'
    assert payload.get('modified') is not None
    assert payload['name'] == 'file'
    assert payload['type'] == 'file'
    assert payload.get('uid') is not None
    assert payload['store_key'] == 'file.' + payload['uid'] + '.zip'

    # Get the details for an image
    response = client.get(
        url_for('api.get'),
        data=dict(
            api_key=account.api_key,
            uid=image_asset.uid
            )
        )
    assert response.json['status'] == 'success'

    # Check that the asset information returned is correct
    payload = response.json['payload']

    assert payload.get('created') is not None
    assert payload['ext'] == 'jpg'
    assert payload['meta']['filename'] == 'image.jpg'
    assert payload['meta']['image'] == {
        'size': [720, 960],
        'mode': 'RGB'
        }
    assert payload.get('modified') is not None
    assert payload['name'] == 'image'
    assert payload['type'] == 'image'
    assert payload.get('uid') is not None
    assert payload['store_key'] == 'image.' + payload['uid'] + '.jpg'
    assert len(payload['variations']) == 1

    variation = payload['variations'][0]
    assert variation['name'] == 'test'
    assert variation['ext'] == 'webp'
    key = 'image.{uid}.test.{version}.webp'.format(
            uid=payload['uid'],
            version=variation['version']
            )
    assert variation['store_key'] == key
    assert variation.get('version') is not None
    assert variation['meta']['image'] == {
        'size': [75, 100],
        'mode': 'RGBA'
        }

def test_download(client, test_local_account, test_local_assets):
    account = test_local_account

    # Find an asset to download
    file_asset = Asset.one(Q.name == 'file')

    # Download the file
    response = client.get(
        url_for('api.download'),
        data=dict(
            api_key=account.api_key,
            uid=file_asset.uid
            )
        )
    assert response.content_type == 'application/zip'
    content_disposition = 'attachment; filename=' + file_asset.store_key
    assert response.headers['Content-Disposition'] == content_disposition
    assert len(response.data) == file_asset.meta['length']

def test_set_expires(client, test_local_account):
    account = test_local_account

    # Load a file to upload
    with open('tests/data/assets/uploads/file.zip', 'rb') as f:
        file_stream = io.BytesIO(f.read())

    # Create an asset
    response = client.post(
        url_for('api.upload'),
        data=dict(
            api_key=account.api_key,
            asset=(file_stream, 'file.zip'),
            name='files/test'
            )
        )

    # Get the asset we uploaded
    asset = Asset.one(And(
        Q.account == account,
        Q.uid == response.json['payload']['uid']
        ))

    # Set an expiry date 1 hour from now
    expires = datetime.now(timezone.utc) + timedelta(seconds=3600)
    expires = time.mktime(expires.timetuple())

    response = client.post(
        url_for('api.set_expires'),
        data=dict(
            api_key=account.api_key,
            uid=asset.uid,
            expires=str(expires)
            )
        )
    assert response.json['status'] == 'success'

    # Reload the asset and check the expires has been correctly set
    asset.reload()
    assert asset.expires == expires

    # Unset the expiry date
    response = client.post(
        url_for('api.set_expires'),
        data=dict(
            api_key=account.api_key,
            uid=asset.uid
            )
        )
    assert response.json['status'] == 'success'

    # Reload the asset and check the expires has been correctly set
    asset.reload()
    assert asset.expires == None

def test_upload_file(client, test_backends):

    # Test each backend
    for account in test_backends:

        # Load a file to upload
        with open('tests/data/assets/uploads/file.zip', 'rb') as f:
            file_stream = io.BytesIO(f.read())

        # Set an expiry date 1 hour from now
        expires = datetime.now(timezone.utc) + timedelta(seconds=3600)
        expires = time.mktime(expires.timetuple())

        # Upload a file (non-image) asset
        response = client.post(
            url_for('api.upload'),
            data=dict(
                api_key=account.api_key,
                asset=(file_stream, 'file.zip'),
                name='files/test',
                expires=str(expires)
                )
            )
        assert response.json['status'] == 'success'

        # Validate the payload
        payload = response.json['payload']
        assert payload.get('created') is not None
        assert payload['expires'] == expires
        assert payload['ext'] == 'zip'
        assert payload['meta']['filename'] == 'file.zip'
        assert payload.get('modified') is not None
        assert payload['name'] == 'files/test'
        assert payload['type'] == 'file'
        assert payload.get('uid') is not None
        assert payload['store_key'] == 'files/test.' + payload['uid'] + '.zip'

def test_upload_image(client, test_backends):

    # Test each backend
    for account in test_backends:

        # Load an image to upload
        with open('tests/data/assets/uploads/image.jpg', 'rb') as f:
            image_stream = io.BytesIO(f.read())

        # Set an expiry date 1 hour from now
        expires = datetime.now(timezone.utc) + timedelta(seconds=3600)
        expires = time.mktime(expires.timetuple())

        # Upload an image asset
        response = client.post(
            url_for('api.upload'),
            data=dict(
                api_key=account.api_key,
                asset=(image_stream, 'image.jpg'),
                name='images/test',
                expires=str(expires)
                )
            )
        assert response.json['status'] == 'success'

        # Validate the payload
        payload = response.json['payload']
        assert payload.get('created') is not None
        assert payload['expires'] == expires
        assert payload['ext'] == 'jpg'
        assert payload['meta']['filename'] == 'image.jpg'
        assert payload['meta']['image'] == {
            'size': [720, 960],
            'mode': 'RGB'
            }
        assert payload.get('modified') is not None
        assert payload['name'] == 'images/test'
        assert payload['type'] == 'image'
        assert payload.get('uid') is not None
        assert payload['store_key'] == 'images/test.' + payload['uid'] + '.jpg'

def test_upload_image_without_ext(client, test_local_account):

    account = test_local_account

    # Load an image to upload
    with open('tests/data/assets/uploads/image_no_ext', 'rb') as f:
        image_stream = io.BytesIO(f.read())

    # Set an expiry date 1 hour from now
    expires = datetime.now(timezone.utc) + timedelta(seconds=3600)
    expires = time.mktime(expires.timetuple())

    # Upload an image asset without an extension
    response = client.post(
        url_for('api.upload'),
        data=dict(
            api_key=account.api_key,
            asset=(image_stream, 'image_no_ext'),
            name='images/test',
            expires=str(expires)
            )
        )
    assert response.json['status'] == 'success'

    # Validate the payload
    payload = response.json['payload']
    assert payload.get('created') is not None
    assert payload['expires'] == expires
    assert payload['ext'] == 'png'
    assert payload['meta']['filename'] == 'image_no_ext'
    assert payload['meta']['image'] == {
        'size': [800, 600],
        'mode': 'RGB'
        }
    assert payload.get('modified') is not None
    assert payload['name'] == 'images/test'
    assert payload['type'] == 'image'
    assert payload.get('uid') is not None
    assert payload['store_key'] == 'images/test.' + payload['uid'] + '.png'
