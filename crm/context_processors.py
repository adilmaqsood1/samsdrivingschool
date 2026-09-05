"""Template context for the anti-spam form fields.

Adds a freshly signed timestamp and the Turnstile site key to every
template render so any public form can drop in ``partials/antispam_fields.html``.
"""

from django.conf import settings

from . import antispam


def antispam_context(request):
    return {
        "antispam_enabled": bool(getattr(settings, "ANTISPAM_ENABLED", True)),
        "antispam_timestamp_field": antispam.TIMESTAMP_FIELD,
        "antispam_honeypot_field": antispam.HONEYPOT_FIELD,
        "antispam_timestamp": antispam.sign_timestamp(),
        "turnstile_site_key": getattr(settings, "TURNSTILE_SITE_KEY", "") or "",
    }
