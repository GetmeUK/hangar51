import glob
import importlib
import inspect
import os

from utils.forms import FormData

__all__ = ['Backend']


class Backend:
    """
    The `Backend` class allows different types of storage models to be used for
    asset storage.

    Different backends should inherit from the base `Backend` class and override
    its classmethods.
    """

    # Each backend must have a unique name which
    name = ''

    # Backend configurations are validated when an account is added or the
    # configuration for an account is changed. Validation is done using a
    # `WTForm.Form` instance.
    config_form = None

    def __init__(self, **config):
        raise NotImplementedError()

    def delete(self, key):
        """Delete a file from the store"""
        raise NotImplementedError()

    def retrieve(self, key):
        """Retrieve a file from the store"""
        raise NotImplementedError()

    def store(self, f, key):
        """Store a file"""
        raise NotImplementedError()

    @classmethod
    def validate_config(cls, **config):
        """Validate a set of config values"""
        if not cls.config_form:
            raise NotImplementedError()

        # Validate the configuration against the form
        form = cls.config_form(**config)
        if not form.validate():
            return False, form.errors

        return True, {}

    @classmethod
    def get_backend(self, name):
        """Return the named backend"""

        # Check if the cache exists, if not build it
        assert name in Backend.list_backends(), \
                'No backend named `{name}`'.format(name=name)

        return Backend._cache[name]

    @classmethod
    def list_backends(self):
        """Return a list of available backends"""

        # Check for a cached list of backends
        if hasattr(Backend, '_cache'):
            return sorted(Backend._cache.keys())

        # Find all python files within this (the backends) folder
        module_names = glob.glob(os.path.dirname(__file__) + '/*.py')
        module_names = [os.path.basename(n)[:-3] \
                for n in module_names if os.path.isfile(n)]

        # Build a list of the backends installed
        backends = []

        for module_name in module_names:

            # Don't import self
            if module_name == '__init__':
                continue

            # Import the module
            module = importlib.import_module('backends.' + module_name)

            # Check each member of the module to see if it's a Backend
            for member in inspect.getmembers(module):

                # Must be a class
                if not inspect.isclass(member[1]):
                    continue

                # Must be a sub-class of `Backend`
                if not issubclass(member[1], (Backend,)):
                    continue

                # Must not be the `Backend` class itself
                if member[1] == Backend:
                    continue

                backends.append(member[1])

        # Cache the result
        Backend._cache = {b.name: b for b in backends}

        return Backend.list_backends()