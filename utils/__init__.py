"""
Useful functions used across more than one module.
"""

import os
import shortuuid

__all__ = [
    'get_file_length',
    'generate_uid'
    ]


def get_file_length(f):
    """Return the length of a file storage object"""
    f.seek(0, os.SEEK_END)
    length = f.tell()
    f.seek(0)
    return length

def generate_uid(length):
    """Generate a uid of a given length"""
    su = shortuuid.ShortUUID(alphabet='abcdefghijklmnopqrstuvwxyz0123456789')
    return su.uuid()[:length]