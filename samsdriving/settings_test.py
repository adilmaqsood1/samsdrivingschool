"""Test settings: in-memory SQLite, local-memory cache, no real network/email.

Run with: DJANGO_SETTINGS_MODULE=samsdriving.settings_test
"""

import os

# Take the local-dev branches in settings.py (sqlite, no mandatory DB/secret env)
# then pin the values this suite actually needs below.
os.environ.setdefault("DJANGO_DEBUG", "true")
os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key-not-used-in-production")

from .settings import *  # noqa: E402,F401,F403

DEBUG = False

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "antispam-tests",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# The anti-spam layer logs a WARNING for every blocked submission. Tests
# deliberately trigger those paths; silence the noise unless a test opts in
# with assertLogs.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"null": {"class": "logging.NullHandler"}},
    "loggers": {"crm.antispam": {"handlers": ["null"], "level": "ERROR", "propagate": False}},
}

# Anti-spam: exercised explicitly per-test.
ANTISPAM_ENABLED = True
TURNSTILE_SITE_KEY = "1x00000000000000000000AA"
TURNSTILE_SECRET_KEY = "1x0000000000000000000000000000000AA"

# Analytics: known values; server-side MP stays disabled (no API secret) so
# no test hits the network unless it patches analytics explicitly.
GA4_MEASUREMENT_ID = "G-TEST0000"
GA4_API_SECRET = ""
GOOGLE_ADS_CONVERSION_ID = "AW-TEST123"
GOOGLE_ADS_PURCHASE_LABEL = "purchaseLabel"
GOOGLE_ADS_LEAD_LABEL = "leadLabel"
ANALYTICS_DEBUG = False
