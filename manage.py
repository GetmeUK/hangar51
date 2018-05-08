"""
Command line tools for managing the application.
"""

from flask.ext.script import Manager

from app import create_app
import commands


# Set up the manager
manager = Manager(create_app)
manager.add_option(
    '-e',
    '--env',
    choices=['dev', 'local', 'prod'],
    default='local',
    dest='env',
    required=False
    )

# Add commands
manager.add_command('drop', commands.Drop)
manager.add_command('init', commands.Init)

# Accounts
manager.add_command('add-account', commands.AddAccount)
manager.add_command('config-account', commands.ConfigAccount)
manager.add_command('delete-account', commands.DeleteAccount)
manager.add_command('generate-new-api-key', commands.GenerateNewAPIKey)
manager.add_command('list-accounts', commands.ListAccounts)
manager.add_command('list-backends', commands.ListBackends)
manager.add_command('rename-account', commands.RenameAccount)
manager.add_command('view-account', commands.ViewAccount)


if __name__ == "__main__":
    manager.run()