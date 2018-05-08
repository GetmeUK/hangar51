from datetime import datetime, timezone
import io
import imghdr
import json
import mimetypes
import re
import time

from flask import current_app, g, make_response, request
from mongoframes import *
import os
from PIL import Image
from PIL.ExifTags import TAGS
from slugify import Slugify

from api import *
from forms.assets import *
from models.assets import Asset, Variation
from utils import get_file_length, generate_uid

# Fix for missing mimetypes
mimetypes.add_type('text/csv', '.csv')
mimetypes.add_type('image/webp', '.webp')


# Routes

@api.route('/download')
@authenticated
def download():
    """Download an asset"""

    # Validate the parameters
    form = DownloadForm(request.values)
    if not form.validate():
        return fail('Invalid request', issues=form.errors)
    form_data = form.data

    # Get the asset
    asset = Asset.one(And(
        Q.account == g.account,
        Q.uid == form_data['uid']
        ))

    # Retrieve the original file
    backend = g.account.get_backend_instance()
    f = backend.retrieve(asset.store_key)

    # Build the file response to return
    response = make_response(f.read())
    response.headers['Content-Type'] = asset.content_type
    response.headers['Content-Disposition'] = \
        'attachment; filename={0}'.format(asset.store_key)

    return response

@api.route('/get')
@authenticated
def get():
    """Get the details for an asset"""

    # Validate the parameters
    form = GetForm(request.values)
    if not form.validate():
        return fail('Invalid request', issues=form.errors)
    form_data = form.data

    # Get the asset
    asset = Asset.one(And(
        Q.account == g.account,
        Q.uid == form_data['uid']
        ))

    return success(asset.to_json_type())

@api.route('/', endpoint='list')
@authenticated
def _list():
    """List assets"""

    # Validate the parameters
    form = ListForm(request.values)
    if not form.validate():
        return fail('Invalid request', issues=form.errors)
    form_data = form.data

    # Build the query
    query = [
        Q.account == g.account,
        Or(
            Exists(Q.expires, False),
            Q.expires > time.mktime(datetime.now(timezone.utc).timetuple())
        )
    ]

    # `q`
    if form_data['q'] and form_data['q'].strip():
        # Replace `*` instances with non-greedy re dot matches
        q = re.escape(form_data['q']).replace('\*', '.*?')
        q_exp = re.compile(r'^{q}$'.format(q=q), re.I)
        query.append(Q.store_key == q_exp)

    # `type`
    if form_data['type']:
        query.append(Q.type == form_data['type'])

    # `order`
    sort = {
        'created': [('created', ASC)],
        '-created': [('created', DESC)],
        'store_key': [('store_key', ASC)]
        }[form_data['order'] or 'store_key']

    # Paginate the results
    paginator = Paginator(
        Asset,
        filter=And(*query),
        projection={
            'created': True,
            'store_key': True,
            'type': True,
            'uid': True
            },
        sort=sort,
        per_page=1000
        )

    # Attempt to select the requested page
    try:
        page = paginator[form_data['page']]
    except InvalidPage:
        return fail('Invalid page')

    return success({
        'assets': [a.to_json_type() for a in page.items],
        'total_assets': paginator.item_count,
        'total_pages': paginator.page_count
        })

@api.route('/generate-variations', methods=['POST'])
@authenticated
def generate_variations():
    """Generate one or more variations for of an image asset"""

    # Validate the parameters
    form = GenerateVariationsForm(request.values)
    if not form.validate():
        return fail('Invalid request', issues=form.errors)
    form_data = form.data

    # Find the asset
    asset = Asset.one(And(Q.account == g.account, Q.uid == form_data['uid']))

    # Check the asset is an image
    if asset.type != 'image':
        return fail('Variations can only be generated for images')

    # Parse the variation data
    variations = json.loads(form_data['variations'])

    # Has the user specified how they want the results delivered?
    on_delivery = form_data['on_delivery'] or 'wait'
    if on_delivery == 'wait':
        # Caller is waiting for a response so generate the variations now

        # Retrieve the original file
        backend = g.account.get_backend_instance()
        f = backend.retrieve(asset.store_key)
        im = Image.open(f)

        # Generate the variations
        new_variations = {}
        for name, ops in variations.items():
            new_variations[name] = asset.add_variation(f, im, name, ops)
            new_variations[name] = new_variations[name].to_json_type()

        # Update the assets modified timestamp
        asset.update('modified')

        return success(new_variations)

    else:
        # Caller doesn't want to wait for a response so generate the variations
        # in the background.
        current_app.celery.send_task(
            'generate_variations',
            [g.account._id, asset.uid, variations, form_data['webhook'].strip()]
            )

        return success()

@api.route('/set-expires', methods=['POST'])
@authenticated
def set_expires():
    """Set the expiry date for an asset"""

    # Validate the parameters
    form = SetExpiresForm(request.values)
    if not form.validate():
        return fail('Invalid request', issues=form.errors)
    form_data = form.data

    # Get the asset
    asset = Asset.one(And(
        Q.account == g.account,
        Q.uid == form_data['uid']
        ))

    # Update the assets `expires` value
    if 'expires' in form_data:
        # Set `expires`
        asset.expires = form_data['expires']
        asset.update('expires', 'modified')

    else:
        # Unset `expires`
        Asset.get_collection().update(
            {'_id': asset._id},
            {'$unset': {'expires': ''}}
            )
        asset.update('modified')

    return success()

@api.route('/upload', methods=['POST'])
@authenticated
def upload():
    """Upload an asset"""

    # Check a file has been provided
    fs = request.files.get('asset')
    if not fs:
        return fail('No `asset` sent.')

    # Validate the parameters
    form = UploadForm(request.values)
    if not form.validate():
        return fail('Invalid request', issues=form.errors)

    # Prep the asset name for
    form_data = form.data

    # Name
    name = form_data['name']
    if not name:
        name = os.path.splitext(fs.filename)[0]
    name = slugify_name(name)

    # Extension
    ext = os.path.splitext(fs.filename)[1].lower()[1:]

    # If there's no extension associated with then see if we can guess it using
    # the imghdr module
    if not ext:
        fs.stream.seek(0)
        ext = imghdr.what(fs.filename,fs.stream.read()) or ''

    # If the file is a recognized image format then attempt to read it as an
    # image otherwise leave it as a file.
    asset_file = fs.stream
    asset_meta = {}
    asset_type = Asset.get_type(ext)
    if asset_type is 'image':
        try:
            asset_file, asset_meta = prep_image(asset_file)
        except IOError as e:
            return fail('File appears to be an image but it cannot be read.')

    # Add basic file information to the asset meta
    asset_meta.update({
        'filename': fs.filename,
        'length': get_file_length(asset_file)
        })

    # Create the asset
    asset = Asset(
        account=g.account._id,
        name=name,
        ext=ext,
        meta=asset_meta,
        type=asset_type,
        variations=[]
        )

    if form_data['expires']:
        asset.expires = form_data['expires']

    # Generate a unique Id for the asset
    asset.uid = generate_uid(6)
    while Asset.count(And(Q.account == g.account, Q.uid == asset.uid)) > 0:
        asset.uid = generate_uid(6)

    # Store the original file
    asset.store_key = Asset.get_store_key(asset)
    backend = g.account.get_backend_instance()
    backend.store(asset_file, asset.store_key)

    # Save the asset
    asset.insert()

    return success(asset.to_json_type())


# Utils

def prep_image(f):
    """Prepare an image as a file"""

    # Attempt to load the image
    im = Image.open(f)
    fmt = im.format

    # Orient the image
    if hasattr(im, '_getexif') and im._getexif():
        # Only JPEG images contain the _getexif tag, however if it's present we
        # can use it make sure the image is correctly orientated.

        # Convert the exif data to a dictionary with alphanumeric keys
        exif = {TAGS[k]: v for k, v in im._getexif().items() if k in TAGS}

        # Check for an orientation setting and orient the image if required
        orientation = exif.get('Orientation')
        if orientation == 2:
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
        elif orientation == 3:
            im = im.transpose(Image.ROTATE_180)
        elif orientation == 4:
            im = im.transpose(Image.FLIP_TOP_BOTTOM)
        elif orientation == 5:
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
            im = im.transpose(Image.ROTATE_90)
        elif orientation == 6:
            im = im.transpose(Image.ROTATE_270)
        elif orientation == 7:
            im = im.transpose(Image.FLIP_TOP_BOTTOM)
            im = im.transpose(Image.ROTATE_90)
        elif orientation == 8:
            im = im.transpose(Image.ROTATE_90)

        # Convert the image back to a stream
        f = io.BytesIO()
        im.save(f, format=fmt)
        f.seek(0)


    # Strip meta data from file
    im_no_exif = None
    if im.format == 'GIF':
        im_no_exif = im
    else:
        f = io.BytesIO()
        im_no_exif = Image.new(im.mode, im.size)
        im_no_exif.putdata(list(im.getdata()))
        im_no_exif.save(f, format=fmt)

    f.seek(0)

    # Extract any available meta information
    meta = {
        'image': {
            'mode': im.mode,
            'size': im.size
        }
    }

    return f, meta

def slugify_name(name):
    """Get a slugifier used to ensure asset names are safe"""

    # Create the slugifier
    slugifier = Slugify()

    # Configure the slugifier
    slugifier.to_lower = True
    slugifier.safe_chars = '-/'
    slugifier.max_length = 200

    # Names cannot start or end with forward slashes '/'
    return slugifier(name).strip('/')