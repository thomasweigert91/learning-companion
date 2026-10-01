"""WSGI-Einstiegspunkt des Projekts."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "learning_companion.settings")

application = get_wsgi_application()
