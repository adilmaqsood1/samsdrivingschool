from django.test import RequestFactory, TestCase, override_settings

from crm import antispam
from crm.context_processors import antispam_context


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


def _ts(ctx):
    return int(antispam._timestamp_signer.unsign(ctx["antispam_timestamp"]))
