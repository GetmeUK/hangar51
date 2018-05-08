from flask import current_app
from wtforms import Form, ValidationError
from wtforms.fields import *
import io
import os
import shutil
from wtforms.validators import *

from backends import Backend

__all__ = ['LocalBackend']


class ConfigForm(Form):

    asset_root = StringField(
        'Please specify the `asset_root` directory path where assets will be \
stored',
        [Required()]
        )

    def validate_asset_root(form, field):
        """Validate the asset root directory exists"""

        # Check the asset root directory exists
        if not os.path.exists(field.data):
            raise ValidationError('Asset root directory does not exist.')


class LocalBackend(Backend):
    """
    Backend to support storing files on the local file system.
    """

    name = 'local'
    config_form = ConfigForm

    def __init__(self, **config):
        self.asset_root = config['asset_root']

    def delete(self, key):
        """Delete a file from the store"""

        # Remove the file if it exists
        abs_path =  os.path.join(self.asset_root, key)
        if os.path.exists(abs_path):
            os.remove(abs_path)

    def retrieve(self, key):
        """Retrieve a file from the store"""

        # Return the file as a byte stream
        abs_path =  os.path.join(self.asset_root, key)
        with open(abs_path, 'rb') as f:
            stream = io.BytesIO(f.read())

        return stream

    def store(self, f, key):
        """Store a file"""

        # Determine the storage location
        filepath, filename = os.path.split(key)
        abs_path = os.path.join(self.asset_root, filepath)

        # Ensure the location exists
        os.makedirs(abs_path, exist_ok=True)

        # Save the file
        with open(os.path.join(abs_path, filename), 'wb') as store:
            store.write(f.read())