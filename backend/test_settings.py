"""Test settings: isolate tests from Postgres/pgbouncer/Redis.

Run:  python manage.py test --settings=backend.test_settings
"""
import tempfile

from .settings import *  # noqa: F401,F403

# Keep uploaded test files out of the real media dir.
MEDIA_ROOT = tempfile.mkdtemp(prefix='test-media-')

# Fast, dependency-free test database.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# In-memory channel layer so notification code runs without Redis.
CHANNEL_LAYERS = {
    'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'},
}

# Local-memory cache so WS-ticket tests don't need Redis.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    },
}

PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# Capture emails in mail.outbox instead of printing them.
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
