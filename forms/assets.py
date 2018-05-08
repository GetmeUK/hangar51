from flask import g
import json
from mongoframes import *
from numbers import Number
import re
from wtforms import Form, ValidationError
from wtforms.fields import *
from wtforms.validators import *

from models.assets import Asset

__all__ = [
    'DownloadForm',
    'GenerateVariationsForm',
    'GetForm',
    'ListForm',
    'SetExpiresForm',
    'UploadForm'
    ]


class _FindAssetForm(Form):

    uid = StringField('uid')

    def validate_uid(form, field):
        """Validate that the asset exists"""
        asset = Asset.one(And(Q.account == g.account, Q.uid == field.data))
        if not asset or asset.expired:
            raise ValidationError('Asset not found.')


class DownloadForm(_FindAssetForm):

    pass


class GenerateVariationsForm(_FindAssetForm):

    variations = StringField('variations', [Required()])
    on_delivery = StringField(
        'on_delivery',
        [Optional(), AnyOf(['forget', 'wait'])]
        )
    webhook = StringField('webhook', [Optional(), URL()])

    def validate_variations(form, field):
        # A valid name matcher
        valid_name_regex = re.compile('\A[A-Za-z0-9\-]+\Z')

        # Check a valid JSON string has been provided
        try:
            variations = json.loads(field.data)
        except ValueError:
            raise ValidationError('Invalid JSON string')

        # Validate the structure of the JSON data (must be a dictionary with at
        # least one item).
        if not isinstance(variations, dict) or len(variations) == 0:
            raise ValidationError(
                'Must be a dictionary containing at least one item')

        # Validate each item in the dictionary contains a valid set of image
        # operations.
        supported_formats = Asset.SUPPORTED_IMAGE_EXT['out']
        for name, ops in variations.items():

            # Check the variation name is allowed
            if not valid_name_regex.match(name):
                raise ValidationError(
                    'Invalid variations name (a-Z, 0-9, -)')

            # Check a list of ops has been specified for the variation
            if len(ops) == 0:
                raise ValidationError('Empty ops list'.format(name=name))

            for op in ops:
                # Validate op is a list with 2 values
                if not isinstance(op, list) and len(op) != 2:
                    raise ValidationError('Invalid op [name, value]')

                # Crop
                if op[0] == 'crop':
                    # Crop region must be a 4 item list
                    if not isinstance(op[1], list) and len(op[1]) != 4:
                         raise ValidationError(
                            'Invalid crop region [t, r, b, l] (0.0-1.0)')

                    # Check each value is a number
                    if False in [isinstance(v, Number) for v in op[1]]:
                         raise ValidationError(
                            'Invalid crop region [t, r, b, r] (0.0-1.0)')

                    # All values must be between 0 and 1
                    if False in [v >= 0 and v <= 1 for v in op[1]]:
                         raise ValidationError(
                            'Invalid crop region [t, r, b, l] (0.0-1.0)')

                    # Width and height must both be great than 0
                    if (op[1][2] - op[1][0]) <= 0 or (op[1][1] - op[1][3]) <= 0:
                         raise ValidationError(
                            'Invalid crop region, width and height must be ' +
                            'greater than 0'
                            )

                # Face
                elif op[0] == 'face':

                    # Face options must be a dictionary
                    if not isinstance(op[1], dict):
                        raise ValidationError(
                            "Invalid ouput format {'bias': [0.0, -0.2], ...}")

                    # Bias
                    if 'bias' in op[1]:
                        bias = op[1]['bias']

                        # Bias must have 2 values
                        if not isinstance(bias, list) and len(bias) != 2:
                            raise ValidationError(
                                'Invalid face bias [horz, vert] as decimals')

                        # Bias values must be numbers
                        if not (isinstance(bias[0], Number) \
                                and isinstance(bias[1], Number)):
                            raise ValidationError(
                                'Invalid face bias [horz, vert] as decimals')

                    # Padding
                    if 'padding' in op[1]:
                        padding = op[1]['padding']

                        # Padding must be a number
                        if not isinstance(padding, Number):
                            raise ValidationError(
                                'Invalid face padding must be a number')

                    # Min padding must be a number
                    if 'min_padding' in op[1]:
                        padding = op[1]['min_padding']

                        # Min padding must be a number
                        if not isinstance(padding, Number):
                            raise ValidationError(
                                'Invalid face min padding must be a number')

                # Fit
                elif op[0] == 'fit':
                    # Dimensions must be a 2 item list
                    if not isinstance(op[1], list) and len(op[1]) != 2:
                        raise ValidationError(
                            'Invalid fit dimensions [width, height] in pixels')

                    # Dimensions must be integers
                    if not (isinstance(op[1][0], int) \
                            and isinstance(op[1][1], int)):
                        raise ValidationError(
                            'Invalid fit dimensions [width, height] in pixels')

                    # Dimensions must both be greater than 0
                    if not (op[1][0] > 0 and op[1][1] > 0):
                        raise ValidationError(
                            'Fit dimensions must be greater than 0')

                # Ouput
                elif op[0] == 'output':
                    # Format options must be a dictionary
                    if not isinstance(op[1], dict):
                        raise ValidationError(
                            "Invalid ouput format {'format': 'jpg', ...}")

                    # Format must be supported
                    if op[1].get('format') not in supported_formats:
                        raise ValidationError(
                            'Output format not supported ({formats})'.format(
                                formats='|'.join(supported_formats)
                                )
                            )

                    # If quality is specified
                    fmt = op[1].get('format')
                    if 'quality' in op[1]:
                        # Must be a format that supports quality
                        if fmt not in ['jpg', 'webp']:
                            raise ValidationError(
                                'Output quality only allowed for jpg and webp')

                        # Quality must be an integer between 1 and 100
                        quality = op[1].get('quality')
                        if not isinstance(quality, int) \
                                or quality < 0 or quality > 100:
                            raise ValidationError(
                                'Invalid output quality (0-100)')

                # Rotate
                elif op[0] == 'rotate':
                    if op[1] not in [0, 90, 180, 270]:
                        raise ValidationError(
                            'Rotate angle must be 0, 90, 180 or 270')

                # Unknown ops
                else:
                    raise ValidationError('Unknown op {op}'.format(op=op[0]))


class GetForm(_FindAssetForm):

    pass


class ListForm(Form):

    q = StringField('q')
    type = StringField('type', [Optional(), AnyOf(['file', 'image'])])
    page = IntegerField('Page', default=1)
    order = StringField(
        'order',
        [Optional(), AnyOf(['created', '-created', 'store_key'])]
        )


class SetExpiresForm(_FindAssetForm):

    expires = FloatField('expires', [Optional(), NumberRange(min=1)])


class UploadForm(Form):

    name = StringField('name')
    expires = FloatField('expires', [Optional(), NumberRange(min=1)])