import json
from mongoframes import *
import os
from wtforms import Form, ValidationError
from wtforms.fields import *
from wtforms.validators import *

from backends import Backend
from models.accounts import Account

__all__ = [
    'AddAccountForm',
    'ConfigAccountBackendForm',
    'DeleteAccountForm',
    'GenerateNewAccountAPIKeyForm',
    'RenameAccountForm',
    'ViewAccountForm'
    ]


# A valid name matcher
valid_name_regex = Regexp('\A[A-Za-z0-9_]+\Z')


class _FindAccountForm(Form):

    name = StringField('name', [Required(), Length(max=20)])

    def validate_name(form, field):
        """Validate that the account name exists"""
        if Account.count(Q.name == field.data) == 0:
            raise ValidationError('Account not found.')


class AddAccountForm(Form):

    name = StringField('name', [
        Required(),
        Length(min=2, max=20),
        valid_name_regex
        ])
    backend = StringField('backend', [Required()])

    def validate_backend(form, field):
        """Validate that the backend is supported"""
        if not Backend.get_backend(field.data):
            raise ValidationError('Not a supported backend.')

    def validate_name(form, field):
        """Validate that the account name isn't taken"""
        if Account.count(Q.name == field.data) > 0:
            raise ValidationError('Account name already taken.')
        return


class ConfigAccountBackendForm(_FindAccountForm):
    pass


class DeleteAccountForm(_FindAccountForm):
    pass


class GenerateNewAccountAPIKeyForm(_FindAccountForm):
    pass


class RenameAccountForm(_FindAccountForm):

    new_name = StringField('name', [
        Required(),
        Length(max=20),
        valid_name_regex
        ])

    def validate_new_name(form, field):
        """Validate that the new account name isn't taken"""
        if Account.count(Q.name == field.data) > 0:
            raise ValidationError('Account name already taken.')


class ViewAccountForm(_FindAccountForm):
    pass