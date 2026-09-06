"""Shared template context for analytics configuration.

``analytics_context`` exposes the GA4 / Google Ads identifiers the base
template needs to load gtag.js and fire conversions. Every value degrades
to an empty string (or a sane default) when the corresponding setting is
unset, so the base template simply renders nothing.
"""

from django.conf import settings


def analytics_context(request):
    return {
        "ga4_measurement_id": getattr(settings, "GA4_MEASUREMENT_ID", "") or "",
        "google_ads_conversion_id": getattr(settings, "GOOGLE_ADS_CONVERSION_ID", "") or "",
        "google_ads_purchase_label": getattr(settings, "GOOGLE_ADS_PURCHASE_LABEL", "") or "",
        "google_ads_lead_label": getattr(settings, "GOOGLE_ADS_LEAD_LABEL", "") or "",
        "analytics_currency": getattr(settings, "ANALYTICS_CURRENCY", "CAD") or "CAD",
    }
