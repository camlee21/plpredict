"""
Django settings for backend project.
"""

import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-%ucczf6ckmkq*8@1ocr%4z2w3_do*r5o$k*0zwzxf3_f1l5^i^",
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# Needed for admin logins to work once this sits behind Render's proxy on
# its own https:// domain - e.g. "https://plpredict-api.onrender.com".
CSRF_TRUSTED_ORIGINS = [
    origin for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if origin
]


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "backend.accounts",
    "backend.leagues",
    "backend.fixtures",
    "backend.predictions",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

CORS_ALLOWED_ORIGINS = os.environ.get(
    "CORS_ALLOWED_ORIGINS", "http://localhost:3000"
).split(",")

ROOT_URLCONF = "backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "backend.wsgi.application"


# Database
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases

# DATABASE_URL (e.g. postgres://user:pass@host:port/dbname) points this at a
# real Postgres instance in production - Neon, Render, etc. Falls back to a
# local sqlite file when unset, for local dev.
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}


AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    "backend.accounts.backends.EmailOrUsernameBackend",
    "django.contrib.auth.backends.ModelBackend",
]


# Password validation
# https://docs.djangoproject.com/en/6.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=6),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# Google OAuth (Sign in with Google) - client ID from Google Cloud Console.
# The frontend uses this same ID to render the Google Sign-In button; the
# backend uses it to verify the audience of the ID token it receives.
GOOGLE_OAUTH_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")

# Fantasy Premier League's public API - free, no key required. Used to pull
# real Premier League teams/players/fixtures/results for the current season.
FPL_BASE_URL = os.environ.get("FPL_BASE_URL", "https://fantasy.premierleague.com/api")

# How long before a gameweek's first kickoff predictions lock.
PREDICTION_LOCK_BEFORE_KICKOFF = timedelta(hours=1)
# How long after a gameweek's last kickoff we consider it safe to finalise
# scores (approximates full-time + the 30 minute buffer from the spec).
GAMEWEEK_FINALIZE_AFTER_LAST_KICKOFF = timedelta(hours=2, minutes=30)

# Seconds between automatic background pulls of fixtures/results from the FPL
# API while the dev server is running (see backend/fixtures/apps.py). 0 disables it.
AUTO_SYNC_INTERVAL_SECONDS = int(os.environ.get("AUTO_SYNC_INTERVAL_SECONDS", "300"))


# Internationalization
# https://docs.djangoproject.com/en/6.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.1/howto/static-files/
# Only the Django admin's own CSS/JS - the React app is a separate static
# site (deployed on Vercel), not served from here. Whitenoise serves these
# directly from the app process, so no separate static-file host is needed.

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Render (and most PaaS hosts) terminate HTTPS at a proxy and forward plain
# HTTP to the app, so Django needs to be told which header to trust to know
# a request was actually made over HTTPS (affects request.is_secure(),
# CSRF, and secure-cookie checks below).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True


# Email
# https://docs.djangoproject.com/en/6.1/topics/email/#topic-email-configuration

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
