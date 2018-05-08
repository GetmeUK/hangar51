from flask import Blueprint, g, jsonify, request
from functools import wraps
from mongoframes import *

from models.accounts import Account

api = Blueprint('api', __name__)

__all__ = [
    # Blueprint
    'api',

    # Decorators
    'authenticated',

    # Responses
    'fail',
    'success'
    ]


# Decorators

def authenticated(func):
    """
    Wrap this decorator around any view that requires a valid account key.
    """

    # Wrap the function with the decorator
    @wraps(func)
    def wrapper(*args, **kwargs):

        api_key = request.values.get('api_key')
        if not api_key:
            return fail('`api_key` not specified.')

        # Find the account
        account = Account.one(Q.api_key == api_key.strip())
        if not account:
            return fail('Not a valid `api_key`.')

        # Set the account against the global context
        g.account = account

        return func(*args, **kwargs)

    return wrapper


# Responses

def fail(reason, issues=None):
    """Return a fail response"""
    response = {'status': 'fail', 'payload': {'reason': reason}}
    if issues:
        response['payload']['issues'] = issues
    return jsonify(response)

def success(payload=None):
    """Return a success response"""
    response = {'status': 'success'}
    if payload:
        response['payload'] = payload
    return jsonify(response)


# Place imports here to prevent cross import clashes

from api import assets