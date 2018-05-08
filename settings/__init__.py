from datetime import timedelta

class DefaultConfig:

    # Database
    MONGO_URI = 'mongodb://localhost:27017/hangar51'
    MONGO_USERNAME = 'hangar51'
    MONGO_PASSWORD = ''

    # Debugging
    DEBUG = False
    SENTRY_DSN = ''

    # Networking
    PREFERRED_URL_SCHEME = 'http'
    SERVER_NAME = ''

    # Tasks (background)
    CELERY_BROKER_URL = ''
    CELERYBEAT_SCHEDULE = {
        'purge_expired_assets': {
            'task': 'purge_expired_assets',
            'schedule': timedelta(seconds=3600)
        }
    }

    # Additional variation support
    SUPPORT_FACE_DETECTION = False