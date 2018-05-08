from flask import current_app

from commands import Drop
from tests import *


def test_init(app):
    # The application is initialized as part of the test set up

    # Check the correct list of collections has been initialized
    expected_collection = {
        'Account',
        'Asset'
        }
    assert set(current_app.db.collection_names(False)) == expected_collection


def test_drop(app):

    # Drop the application
    Drop().run()

    # Check all collections have been dropped
    assert set(current_app.db.collection_names(False)) == set()