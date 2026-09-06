"""Test settings: in-memory SQLite, fast hasher, local-memory cache.

Run with:  python manage.py test --settings=samsdriving.settings_test
"""

import os

# Take the local-dev branches in settings.py (sqlite, no mandatory secret/DB
# env) then pin the values this suite needs below.
os.environ.setdefault("DJANGO_DEBUG", "true")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-used-in-production")

from .settings import *  # noqa: E402,F401,F403

DEBUG = False

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Known analytics values; server-side Measurement Protocol stays disabled
# (no API secret) so no test touches the network unless it patches
# crm.analytics explicitly.
GA4_MEASUREMENT_ID = "G-TEST0000"
GA4_API_SECRET = ""
GOOGLE_ADS_CONVERSION_ID = "AW-TEST123"
GOOGLE_ADS_PURCHASE_LABEL = "purchaseLabel"
GOOGLE_ADS_LEAD_LABEL = "leadLabel"
ANALYTICS_DEBUG = False
