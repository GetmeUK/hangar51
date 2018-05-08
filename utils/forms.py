"""
Utils for common form operations.
"""

__all__ = ['FormData']


class FormData:
    """
    A wrapper class that converts a dictionary into a request like object that
    can be used as the `formdata` argument when initializing a `WTForm`
    instance, for example:

    ```
    form = MyWTForm(FormData({...}))
    ```
    """

    def __init__(self, data):
        self._data = {}
        for key, value in data.items():

            # Fields named `session_token` are not allowed in form data
            if key == 'session_token':
                continue

            if key not in self._data:
                self._data[key] = []

            if isinstance(value, list):
                self._data[key] += value
            else:
                self._data[key].append(value)

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __contains__(self, name):
        return (name in self._data)

    # Methods

    def get(self, key, default=None):
        if key in self._data:
            return self._data[key][0]
        return default

    def getlist(self, key):
        return self._data.get(key, [])