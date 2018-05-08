from datetime import datetime, timezone
from flask import current_app
import io
import mimetypes
from mongoframes import *
import numpy
from PIL import Image
import time

# Fix for missing mimetypes
mimetypes.add_type('text/csv', '.csv')
mimetypes.add_type('image/webp', '.webp')


from utils import get_file_length, generate_uid

__all__ = [
    'Asset',
    'Variation'
    ]


class Variation(SubFrame):
    """
    A variation of an asset transformed by one or more operations.
    """

    _fields = {
        'name',
        'version',
        'ext',
        'meta',
        'store_key'
        }

    def __str__(self):
        return self.store_key

    @staticmethod
    def find_face(im, bias=None, padding=0, min_padding=0):
        """
        Find a face in an image and return it's coordinates. If no face can be
        found then None is returned.
        """

        # Import optional libraries required for face detection
        import dlib
        from skimage import io as skimage_io
        skimage_io.use_plugin('pil')

        # Check we have already aquired a face detector and if not do so now
        if not hasattr(Variation, '_face_detector'):
            Variation._face_detector = dlib.get_frontal_face_detector()

        # Convert the image to an array that can be read by skimage
        w, h = im.size
        skimage_im = numpy.array(im.getdata(), numpy.uint8).reshape(h, w, 3)

        d = dlib.get_frontal_face_detector()
        faces = d(skimage_im, 1)

        # Detect faces
        faces = Variation._face_detector(skimage_im, 1)

        # If no faces were detected there's nothing more to do, we return `None`
        if len(faces) == 0:
            return

        # If a face was found apply any bias and padding to it
        face = faces[0]
        rect = [face.left(), face.top(), face.right(), face.bottom()]

        # Apply bias
        if bias:
            # Shift the center of the face
            bias_x = int(face.width() * bias[0])
            bias_y = int(face.width() * bias[1])
            rect[0] += bias_x
            rect[1] += bias_y
            rect[2] += bias_x
            rect[3] += bias_y

        # Apply padding
        if padding > 0:

            # Determine the maximum amount of padding that can be applied in any
            # direction.
            max_padding = rect[0]
            max_padding = min(rect[1], max_padding)
            max_padding = min(rect[2], max_padding)
            max_padding = min(rect[3], max_padding)

            # Calculate the padding to apply
            pad = [
                int(face.width() * padding),
                int(face.height() * padding)
                ]

            # Ensure that the minimum padding is observed
            if min_padding > 0:
                pad = [
                    min(pad[0], max(max_padding, int(pad[0] * min_padding))),
                    min(pad[1], max(max_padding, int(pad[1] * min_padding)))
                    ]

            # Apply the padding to the face rectangle
            rect[0] = max(rect[0] - pad[0], 0)
            rect[1] = max(rect[1] - pad[1], 0)
            rect[2] = min(rect[2] + pad[0], im.size[0])
            rect[3] = min(rect[3] + pad[1], im.size[1])

        return rect

    @staticmethod
    def get_store_key(asset, variation):
        """Return the store key for an asset variation"""
        return '.'.join([
            asset.name,
            asset.uid,
            variation.name,
            variation.version,
            variation.ext
            ])

    @staticmethod
    def optimize_ops(ops):
        """
        Optimize/reduce a list of image operations to the fewest possible
        operations to achieve the same image transform.

        Due to the limited set of image operations that are possible we can
        always reduce the operations list to a limited ordered set, e.g:

        - crop
        - rotate
        - face (if supported)
        - fit
        - output

        """

        def rotate_crop_cw(crop):
            # Rotate a crop region 90 degrees clockwise
            crop = [c - 0.5 for c in crop]
            crop[1] *= -1
            crop[3] *= -1
            crop = [c + 0.5 for c in crop]
            crop.append(crop.pop(0))
            return crop

        # Initial transform settings
        angle = 0
        crop = [0, 1, 1, 0]
        fit = None
        fmt = None
        face = None

        # Optimize the ops
        for op in ops:
            if op[0] == 'crop':
                # Apply the crop as a crop of the last crop
                sub_crop = list(op[1])

                # Rotate the crop to be aligned with the current angle
                for i in range(0, int(angle / 90)):
                    sub_crop = rotate_crop_cw(sub_crop)

                # Crop the existing crop
                w = crop[1] - crop[3]
                h = crop[2] - crop[0]

                crop = [
                    crop[0] + (h * sub_crop[0]),        # Top
                    crop[1] - (w * (1 - sub_crop[1])),  # Right
                    crop[2] - (h * (1 - sub_crop[2])),  # Bottom
                    crop[3] + (w * sub_crop[3])         # Left
                ]

            elif op[0] == 'face':
                face = op[1]

            elif op[0] == 'fit':
                # Set the fit dimensions allowing for the current orientation of
                # the image.
                if angle in [0, 180]:
                    fit = [op[1][0], op[1][1]]
                else:
                    fit = [op[1][1], op[1][0]]

            elif op[0] == 'output':
                fmt = op[1]

            elif op[0] == 'rotate':
                # Set the rotation of the image clamping it to (0, 90, 180, 270)
                angle = (angle + op[1]) % 360

        # Build the optimized list of ops
        less_ops = []

        # Crop
        if crop != [0, 1, 1, 0]:
            less_ops.append(['crop', crop])

        # Rotate
        if angle != 0:
            less_ops.append(['rotate', angle])

        # Face
        if face is not None:
            less_ops.append(['face', face])

        # Fit
        if fit is not None:
            less_ops.append(['fit', fit])

        # Output
        if fmt is not None:
            less_ops.append(['output', fmt])

        return less_ops

    @staticmethod
    def transform_image(im, ops):
        """
        Perform a list of operations against an image and return the resulting
        image.
        """

        # Optimize the list of operations
        #
        # IMPORTANT! The optimized operations method doesn't work correctly in
        # a number of cases and therefore has been removed for the moment until
        # those issues can be resolved (hint I think the stack of operations
        # needs to be optimized in reverse).
        #
        # ~ Anthony Blackshaw <ant@getme.co.uk>, 31 August 2017
        #
        # ops = Variation.optimize_ops(ops)

        # Perform the operations
        fmt = {'format': 'jpeg', 'ext': 'jpg'}
        for op in ops:

            # Crop
            if op[0] == 'crop':
                im = im.crop([
                    int(op[1][3] * im.size[0]), # Left
                    int(op[1][0] * im.size[1]), # Top
                    int(op[1][1] * im.size[0]), # Right
                    int(op[1][2] * im.size[1])  # Bottom
                    ])

            # Face
            elif op[0] == 'face':
                # If face detection isn't supported ignore the operation
                if not current_app.config['SUPPORT_FACE_DETECTION']:
                    continue

                # Ensure the image we use to find a face with is RGB format
                face_im = im.convert('RGB')

                # Due to performance constraints we don't attempt face
                # recognition on images over 2000x2000 pixels, instead we scale
                # the images within these bounds ahead of the action.
                ratio = 1.0
                if im.size[0] > 2000 or im.size[1] > 2000:
                    face_im.thumbnail((2000, 2000), Image.ANTIALIAS)
                    ratio = float(im.size[0]) / float(face_im.size[0])

                # Attempt to find the face
                face_rect = Variation.find_face(face_im, **op[1])

                # If no face is detected there's nothing more to do
                if face_rect is None:
                    continue

                # Scale the rectangle by the reduced ratio
                if ratio:
                    face_rect = [int(d * ratio) for d in face_rect]

                # If a face was found crop it from the image
                im = im.crop(face_rect)

            # Fit
            elif op[0] == 'fit':
                im.thumbnail(op[1], Image.ANTIALIAS)

            # Rotate
            elif op[0] == 'rotate':
                if op[1] == 90:
                    im = im.transpose(Image.ROTATE_270)

                elif op[1] == 180:
                    im = im.transpose(Image.ROTATE_180)

                elif op[1] == 270:
                    im = im.transpose(Image.ROTATE_90)

            # Output
            elif op[0] == 'output':
                fmt = op[1]

                # Set the extension for the output and the format required by
                # Pillow.
                fmt['ext'] = fmt['format']
                if fmt['format'] == 'jpg':
                    fmt['format'] = 'jpeg'

                # Add the optimize flag for JPEGs and PNGs
                if fmt['format'] in ['jpeg', 'png']:
                    fmt['optimize'] = True

                # Allow gifs to store multiple frames
                if fmt['format'] in ['gif', 'webp']:
                    fmt['save_all'] = True
                    fmt['optimize'] = True

        # Variations are output in web safe colour modes, if the
        # original image isn't using a web safe colour mode supported by
        # the output format it will be converted to one.
        if fmt['format'] == 'gif' and im.mode != 'P':
            im = im.convert('P')

        elif fmt['format'] == 'jpeg' and im.mode != 'RGB':
            im = im.convert('RGB')

        elif fmt['format'] == 'png' \
                and im.mode not in ['P', 'RGB', 'RGBA']:
            im = im.convert('RGB')

        elif fmt['format'] == 'webp' and im.mode != 'RGBA':
            im = im.convert('RGBA')

        return im, fmt


class Asset(Frame):
    """
    An asset stored in Hangar51.
    """

    _fields = {
        'created',
        'modified',
        'account',
        'name',
        'uid',
        'ext',
        'type',
        'expires',
        'meta',
        'store_key',
        'variations'
        }
    _indexes = [
        IndexModel([('account', ASC), ('uid', ASC)], unique=True)
    ]

    _private_fields = ['_id', 'account']

    _default_projection = {'variations': {'$sub': Variation}}

    # A list of support image extensions
    SUPPORTED_IMAGE_EXT = {
        'in': [
            'bmp',
            'gif',
            'jpg', 'jpeg',
            'png',
            'tif', 'tiff',
            'webp'
            ],
        'out': ['jpg', 'gif', 'png', 'webp']
        }

    def __str__(self):
        return self.store_key

    @property
    def content_type(self):
        """Return a content type for the asset based on the extension"""
        return self.guess_content_type(self.store_key)

    @property
    def expired(self):
        if self.expires is None:
            return False
        now = time.mktime(datetime.now(timezone.utc).timetuple())
        return self.expires < now

    def add_variation(self, f, im, name, ops):
        """Add a variation to the asset"""
        from models.accounts import Account

        # Make sure we have access to the associated account frame
        if not isinstance(self.account, Account):
            self.account = Account.one(Q._id == self.account)

        # Transform the original image to generate the variation
        vim = None
        if im.format.lower() == 'gif' and im.is_animated:
            # By-pass transforms for animated gifs
            fmt = {'ext': 'gif', 'fmt': 'gif'}

        else:
            # Transform the image based on the variation
            vim = im.copy()
            vim, fmt = Variation.transform_image(vim, ops)

            # Prepare the variation file for storage
            f = io.BytesIO()
            vim.save(f, **fmt)
            f.seek(0)

        # Add the variation to the asset
        variation = Variation(
            name=name,
            ext=fmt['ext'],
            meta={
                'length': get_file_length(f),
                'image': {
                    'mode': (vim or im).mode,
                    'size': (vim or im).size
                    }
                }
            )

        # Set a version
        variation.version = generate_uid(3)
        while self.get_variation(name, variation.version):
            variation.version = generate_uid(3)

        # Store the variation
        variation.store_key = Variation.get_store_key(self, variation)
        backend = self.account.get_backend_instance()
        backend.store(f, variation.store_key)

        # We use the $push operator to store the variation to prevent race
        # conditions if multiple processes attempt to update the assets
        # variations at the same time.
        self.get_collection().update(
            {'_id': self._id},
            {'$push': {'variations': variation._document}}
        )

        return variation

    def get_variation(self, name, version):
        """Return a variation with the given name and version"""
        if not self.variations:
            return

        # Attempt to find the variation
        for variation in self.variations:
            if variation.name == name and variation.version == version:
                return variation

    def purge(self):
        """Deletes the asset along with all related files."""
        from models.accounts import Account

        # Make sure we have access to the associated account frame
        if not isinstance(self.account, Account):
            self.account = Account.one(Q._id == self.account)

        # Get the backend required to delete the asset
        backend = self.account.get_backend_instance()

        # Delete the original file
        backend.delete(self.store_key)

        # Delete all variation files
        for variation in self.variations:
            backend.delete(variation.store_key)

        self.delete()

    @staticmethod
    def get_store_key(asset):
        """Return the store key for an asset"""
        return '.'.join([asset.name, asset.uid, asset.ext])

    @staticmethod
    def get_type(ext):
        """Return the type of asset for the given filename extension"""
        if ext.lower() in Asset.SUPPORTED_IMAGE_EXT['in']:
            return 'image'
        return 'file'

    @staticmethod
    def guess_content_type(filename):
        """Guess the content type for a given filename"""
        return mimetypes.guess_type(filename)[0]


Asset.listen('insert', Asset.timestamp_insert)
Asset.listen('update', Asset.timestamp_update)