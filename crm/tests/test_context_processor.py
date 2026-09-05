from django.test import RequestFactory, TestCase, override_settings

from crm import antispam
from crm.context_processors import analytics_context, antispam_context


class AntiSpamContextProcessorTests(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/contact/")

    @override_settings(ANTISPAM_ENABLED=True, TURNSTILE_SITE_KEY="site-abc")
    def test_exposes_site_key_and_a_verifiable_timestamp(self):
        ctx = antispam_context(self.request)
        self.assertEqual(ctx["turnstile_site_key"], "site-abc")
        self.assertTrue(ctx["antispam_enabled"])
        # the planted timestamp must survive a round-trip through the checker
        post = {antispam.TIMESTAMP_FIELD: ctx["antispam_timestamp"]}
        self.assertTrue(antispam.check_timing(post, now=_ts(ctx) + 30).ok)

    @override_settings(ANTISPAM_ENABLED=False, TURNSTILE_SITE_KEY="site-abc")
    def test_reports_disabled_state(self):
        ctx = antispam_context(self.request)
        self.assertFalse(ctx["antispam_enabled"])


class AnalyticsContextProcessorTests(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/")

    @override_settings(
        GA4_MEASUREMENT_ID="G-ABC123",
        GOOGLE_ADS_CONVERSION_ID="AW-999",
        GOOGLE_ADS_PURCHASE_LABEL="buy",
        GOOGLE_ADS_LEAD_LABEL="lead",
        ANALYTICS_CURRENCY="CAD",
    )
    def test_exposes_configured_ids(self):
        ctx = analytics_context(self.request)
        self.assertEqual(ctx["ga4_measurement_id"], "G-ABC123")
        self.assertEqual(ctx["google_ads_conversion_id"], "AW-999")
        self.assertEqual(ctx["google_ads_purchase_label"], "buy")
        self.assertEqual(ctx["google_ads_lead_label"], "lead")
        self.assertEqual(ctx["analytics_currency"], "CAD")

    @override_settings(GA4_MEASUREMENT_ID="", GOOGLE_ADS_CONVERSION_ID="")
    def test_blank_when_unconfigured(self):
        ctx = analytics_context(self.request)
        self.assertEqual(ctx["ga4_measurement_id"], "")
        self.assertEqual(ctx["google_ads_conversion_id"], "")


def _ts(ctx):
    return int(antispam._timestamp_signer.unsign(ctx["antispam_timestamp"]))
