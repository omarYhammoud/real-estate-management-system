"""
Local development settings.
Every developer runs this by default (see manage.py). SQLite needs zero
setup, so a fresh clone works immediately with `python manage.py runserver`.
"""
from .base import *  # noqa

DEBUG = True
ALLOWED_HOSTS = ['*']

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Django Debug Toolbar (optional, uncomment once installed):
# INSTALLED_APPS += ['debug_toolbar']
# MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
# INTERNAL_IPS = ['127.0.0.1']