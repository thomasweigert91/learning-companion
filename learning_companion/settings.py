"""Django-Settings fuer das Projekt learning_companion."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Lokale .env in die Umgebung laden, bevor irgendeine Einstellung gelesen wird.
# override=False (Default): bereits gesetzte Variablen gewinnen -- im Container
# und in der CI kommen die Werte aus der echten Umgebung, eine .env gibt es
# dort nicht. Fehlt die Datei, passiert schlicht nichts.
load_dotenv(BASE_DIR / ".env")


# --- Sicherheit -------------------------------------------------------------
# Produktiv werden SECRET_KEY, DEBUG und ALLOWED_HOSTS ueber Umgebungsvariablen
# gesetzt (siehe .env.example); der Fallback dient nur der lokalen Entwicklung.

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-nur-fuer-die-lokale-entwicklung-bitte-ersetzen",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]


# --- Anwendungen ------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Direkt nach der SecurityMiddleware -- die von WhiteNoise dokumentierte
    # Position. Liefert die statischen Dateien aus, wenn DEBUG=False ist und
    # kein Webserver davor steht (Container-Betrieb mit gunicorn).
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "learning_companion.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Templates liegen in core/templates/, deshalb reicht APP_DIRS.
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "learning_companion.wsgi.application"


# --- Datenbank --------------------------------------------------------------
# SQLite fuer die lokale Entwicklung; die Konfiguration bleibt austauschbar.
# Der Pfad ist ueber DJANGO_DB_PATH umlenkbar: im Container laeuft die Anwendung
# unprivilegiert und kann nicht nach BASE_DIR schreiben -- SQLite braucht
# Schreibrechte auf das Verzeichnis, nicht nur auf die Datei (Journal-Datei).

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DJANGO_DB_PATH") or BASE_DIR / "db.sqlite3",
    }
}


# --- Authentifizierung ------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/profile/"
LOGOUT_REDIRECT_URL = "/"


# --- Internationalisierung --------------------------------------------------

LANGUAGE_CODE = "de-de"
TIME_ZONE = "Europe/Berlin"
USE_I18N = True
USE_TZ = True


# --- Statische Dateien ------------------------------------------------------

STATIC_URL = "static/"

# Ziel von collectstatic. Ohne STATIC_ROOT bricht der Befehl mit
# ImproperlyConfigured ab -- im Container laeuft er im Entrypoint.
STATIC_ROOT = os.environ.get("DJANGO_STATIC_ROOT") or BASE_DIR / "staticfiles"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Testlaeufe erzwingen den KI-Mock -- auch wenn die .env einen echten Schluessel
# enthaelt. Siehe core/test_runner.py.
TEST_RUNNER = "core.test_runner.OfflineTestRunner"


# --- OpenAI -----------------------------------------------------------------
# Der Schluessel kommt ausschliesslich aus der Umgebung -- kein Default, kein
# Fallback-Literal. Fehlt er, schaltet der Service selbsttaetig in den
# Mock-Modus, statt beim Start zu scheitern.

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TIMEOUT_SECONDS = float(os.environ.get("OPENAI_TIMEOUT_SECONDS", "20"))
AI_MOCK_MODE = os.environ.get("AI_MOCK_MODE", "") == "True"
