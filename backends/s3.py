import boto3
from botocore.client import ClientError
import io
import os
import tempfile
import uuid
from wtforms import Form, ValidationError
from wtforms.fields import *
from wtforms.validators import *

from backends import Backend
from models.assets import Asset

__all__ = ['S3Backend']


class ConfigForm(Form):

    access_key = StringField(
        'Please specify your AWS `access_key`',
        [Required()]
        )
    secret_key = StringField(
        'Please specify your AWS `secret_key`',
        [Required()]
        )
    bucket = StringField(
        'Please specify the S3 `bucket` that will store the assets',
        [Required()]
        )

    def validate_access_key(form, field):
        access_key = field.data
        secret_key = form.secret_key.data
        bucket = form.bucket.data

        # To validate we can make a connection we need all values to have been
        # specified.
        if not (access_key and secret_key and bucket):
            return

        s3 = boto3.resource(
            's3',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )

        try:
            s3.meta.client.head_bucket(Bucket=bucket)
        except ClientError as e:
            raise ValidationError(str(e))


class S3Backend(Backend):
    """
    Backend to support storing files on the local file system.
    """

    name = 's3'
    config_form = ConfigForm

    def __init__(self, **config):
        self.s3 =  boto3.resource(
            's3',
            aws_access_key_id=config['access_key'],
            aws_secret_access_key=config['secret_key']
        )
        self.bucket = self.s3.Bucket(config['bucket'])

    def delete(self, key):
        """Delete a file from the store"""
        self.bucket.delete_objects(Delete={'Objects': [{'Key': key}]})

    def retrieve(self, key):
        """Retrieve a file from the store"""

        # Create a temporary directory to download the file to
        with tempfile.TemporaryDirectory() as dirname:

            # Create a temporary filepath to store and retrieve the file from
            filepath = os.path.join(dirname, uuid.uuid4().hex)

            # Download the file
            self.bucket.download_file(key, filepath)

            # Convert the file to a stream
            with open(filepath, 'rb') as f:
                stream = io.BytesIO(f.read())

            # Remove the temporary file
            os.remove(filepath)

            return stream

    def store(self, f, key):
        """Store a file"""

        # Guess the content type
        content_type = Asset.guess_content_type(key)

        # Set the file to be cached to a year from now
        cache_control = 'max-age=%d, public' % (365 * 24 * 60 * 60)

        # Store the object
        obj = self.s3.Object(self.bucket.name, key)
        if content_type:
            obj.put(
                Body=f,
                ContentType=content_type,
                CacheControl=cache_control
                )
        else:
            obj.put(Body=f, CacheControl=cache_control)