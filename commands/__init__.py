"""
Command line tools for managing the application.
"""

from blessings import Terminal
from flask import current_app
from flask.ext.script import Command, Option
from pymongo import IndexModel, ASCENDING, DESCENDING
from random import choice
from string import ascii_lowercase

from models.accounts import Account
from models.assets import Asset

__all__ = [
    'AppCommand'
    ]


class AppCommand(Command):
    """
    A base command class for the application.
    """

    def __init__(self, *args, **kwargs):
        super(AppCommand, self).__init__(*args, **kwargs)

        # Create a terminal instance we can use for formatting command line
        # output.
        self.t = Terminal()

    def confirm(self, question, s):
        """Ask the you user to confirm an action before performing it"""

        # In test mode we confirms are automatic
        if current_app.config['ENV'] is 'test':
            return True

        # Ask the user to confirm the action by request they repeat a randomly
        # generated string.
        answer = input(
            '{t.blue}{question}: {t.bold}{s}{t.normal}\n'.format(
                question=question,
                s=s,
                t=self.t
                )
            )

        # Check the answer
        if answer != s:
            print(self.t.bold_red("Strings didn't match"))
            return False

        return True

    def err(self, *errors, **error_dict):
        """
        Output a list of errors to the command line, for example:

            self.err(
                'Unable to find account: foobar',
                ...
                )

        Optional if a dictionary of errors is sent as keywords (this is typical
        used to output error information from a form) then that will be
        automatically converted to a list of error messages.
        """

        # Convert error dict to additional messages
        if error_dict:
            errors += tuple((f, ''.join(e)) for f, e in error_dict.items())

        # Build the error output
        output = [('Failed', 'underline_bold_red')]
        for error in errors:
            if isinstance(error, tuple):
                field, error = error
                output.append(('- {0} - {1}'.format(field, error), 'red'))

            else:
                output.append((error, 'red'))

        self.out(*output)

    def out(self, *strings):
        """
        Output one or more strings (optionally with formats) to the commandline,
        for example:

            self.out(
                'hi',
                ('I am red', 'red'),
                ...
                )

        """

        # We add an additional blank line to the head and tail of the output
        # accept when testing where we remove these to make it easier to compare
        # output.
        if current_app.config['ENV'] != 'test':
            print()

        for s in strings:
            if isinstance(s, tuple):
                # Formatted string
                s, fmt = s

                # When testing we ignore formatting to make it easier to compare
                # output.
                if current_app.config['ENV'] == 'test':
                    # Unformatted string
                    print(s)

                else:
                    # Formatted string
                    fmt = getattr(self.t, fmt)
                    print(fmt(s))

            else:
                # Unformatted string
                print(s)

        if current_app.config['ENV'] != 'test':
            print()

# Prevent cross import clashes by importing other commands here
from commands.accounts import *
from commands.app import *