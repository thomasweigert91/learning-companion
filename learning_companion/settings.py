"""Django-Settings fuer das Projekt learning_companion."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


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

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
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

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
