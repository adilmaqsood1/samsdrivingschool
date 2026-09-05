"""Shared template context: anti-spam form fields and analytics config.

``antispam_context`` adds a freshly signed timestamp and the Turnstile
site key so any public form can drop in ``partials/antispam_fields.html``.

``analytics_context`` exposes the GA4 / Google Ads identifiers the base
template needs to load gtag.js and fire conversions.
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


def analytics_context(request):
    return {
        "ga4_measurement_id": getattr(settings, "GA4_MEASUREMENT_ID", "") or "",
        "google_ads_conversion_id": getattr(settings, "GOOGLE_ADS_CONVERSION_ID", "") or "",
        "google_ads_purchase_label": getattr(settings, "GOOGLE_ADS_PURCHASE_LABEL", "") or "",
        "google_ads_lead_label": getattr(settings, "GOOGLE_ADS_LEAD_LABEL", "") or "",
        "analytics_currency": getattr(settings, "ANALYTICS_CURRENCY", "CAD") or "CAD",
    }
