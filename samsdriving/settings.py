import os
from pathlib import Path
import dj_database_url


BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = False

SECRET_KEY = "django-insecure-REDACTED"

ALLOWED_HOSTS = ["*"]


INSTALLED_APPS = [
    "jet",
    "jet.dashboard",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "crm",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "samsdriving.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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

WSGI_APPLICATION = "samsdriving.wsgi.application"

if os.environ.get("DATABASE_URL"):
    DATABASES = {
        "default": dj_database_url.config(
            conn_max_age=600,
            ssl_require=not DEBUG,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"

TIME_ZONE = "America/Toronto"

USE_I18N = True

USE_TZ = True

STATIC_URL = "/assets/"
STATIC_ROOT = BASE_DIR / "staticfiles_build" / "assets"
STATICFILES_DIRS = [BASE_DIR / "templates" / "assets"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

JET_INDEX_DASHBOARD = "crm.dashboard.CustomIndexDashboard"
JET_THEMES = [
    {"theme": "default", "color": "#1c2b36", "title": "Default"},
    {"theme": "drivschol", "color": "#6fbe44", "title": "Drivschol"},
]
JET_DEFAULT_THEME = "drivschol"

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.example.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-reply@samsdriving.ca")
ENROLLMENT_NOTIFICATION_EMAIL = os.environ.get("ENROLLMENT_NOTIFICATION_EMAIL", "")

SMS_WEBHOOK_URL = os.environ.get("SMS_WEBHOOK_URL", "")
SMS_WEBHOOK_TOKEN = os.environ.get("SMS_WEBHOOK_TOKEN", "")

CSRF_TRUSTED_ORIGINS = ["*"]


SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

SECURE_HSTS_SECONDS = 0 if DEBUG else 3600
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG

STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

GOOGLE_OAUTH_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_OAUTH_REDIRECT_URI = os.environ.get(
    "GOOGLE_OAUTH_REDIRECT_URI", "/crm/oauth/google/callback/"
)
GOOGLE_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/calendar",
]
GOOGLE_CALENDAR_EMBED_URL = os.environ.get("GOOGLE_CALENDAR_EMBED_URL", "")

OUTLOOK_OAUTH_CLIENT_ID = os.environ.get("OUTLOOK_OAUTH_CLIENT_ID", "")
OUTLOOK_OAUTH_CLIENT_SECRET = os.environ.get("OUTLOOK_OAUTH_CLIENT_SECRET", "")
OUTLOOK_OAUTH_TENANT_ID = os.environ.get("OUTLOOK_OAUTH_TENANT_ID", "common")
OUTLOOK_OAUTH_REDIRECT_URI = os.environ.get(
    "OUTLOOK_OAUTH_REDIRECT_URI", "/crm/oauth/outlook/callback/"
)
OUTLOOK_OAUTH_SCOPES = [
    "offline_access",
    "https://graph.microsoft.com/User.Read",
    "https://graph.microsoft.com/Calendars.ReadWrite",
]
