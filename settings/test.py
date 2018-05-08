from . import DefaultConfig

class Config(DefaultConfig):

    # Database
    MONGO_URI = 'mongodb://localhost:27017/hangar51_test'
    MONGO_PASSWORD = 'password'

    # Debugging
    DEBUG = True

    # Networking
    SERVER_NAME = '127.0.0.1'