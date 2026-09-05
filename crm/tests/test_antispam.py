from unittest import mock

from django.test import TestCase, override_settings

from crm import antispam


@override_settings(
    ANTISPAM_ENABLED=True,
    TURNSTILE_SECRET_KEY="secret-xyz",
    TURNSTILE_SITE_KEY="site-xyz",
)
class TurnstileTests(TestCase):
    def test_valid_token_passes(self):
        with mock.patch.object(antispam, "_siteverify", return_value={"success": True}) as sv:
            result = antispam.verify_turnstile("good-token", "203.0.113.7")
        self.assertTrue(result.ok)
        sv.assert_called_once_with("secret-xyz", "good-token", "203.0.113.7")

    def test_rejected_token_is_spam(self):
        with mock.patch.object(antispam, "_siteverify", return_value={"success": False}):
            result = antispam.verify_turnstile("bad-token", "203.0.113.7")
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "turnstile_failed")

    def test_missing_token_is_spam(self):
        with mock.patch.object(antispam, "_siteverify") as sv:
            result = antispam.verify_turnstile("", "203.0.113.7")
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "turnstile_missing")
        sv.assert_not_called()

    def test_network_error_fails_open(self):
        with mock.patch.object(antispam, "_siteverify", side_effect=OSError("boom")):
            with self.assertLogs("crm.antispam", level="WARNING"):
                result = antispam.verify_turnstile("good-token", "203.0.113.7")
        self.assertTrue(result.ok)
        self.assertEqual(result.reason, "turnstile_unreachable")

    @override_settings(TURNSTILE_SECRET_KEY="")
    def test_skipped_when_no_secret_configured(self):
        with mock.patch.object(antispam, "_siteverify") as sv:
            result = antispam.verify_turnstile("", "203.0.113.7")
        self.assertTrue(result.ok)
        sv.assert_not_called()

    @override_settings(ANTISPAM_ENABLED=False)
    def test_skipped_when_disabled(self):
        with mock.patch.object(antispam, "_siteverify") as sv:
            result = antispam.verify_turnstile("", "203.0.113.7")
        self.assertTrue(result.ok)
        sv.assert_not_called()


@override_settings(ANTISPAM_ENABLED=True, TURNSTILE_SECRET_KEY="secret-xyz", TURNSTILE_SITE_KEY="site-xyz")
class EvaluateTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        from django.test import RequestFactory

        cache.clear()
        self.rf = RequestFactory()

    def _post(self, **overrides):
        data = {
            "name": "Real Person",
            antispam.TIMESTAMP_FIELD: antispam.sign_timestamp(now=1_000_000),
            antispam.TURNSTILE_FIELD: "good-token",
        }
        data.update(overrides)
        request = self.rf.post("/lead/", data, REMOTE_ADDR="203.0.113.50")
        return request

    def test_clean_submission_passes(self):
        with mock.patch.object(antispam, "_siteverify", return_value={"success": True}):
            with mock.patch.object(antispam.time, "time", return_value=1_000_030):
                result = antispam.evaluate(self._post())
        self.assertTrue(result.ok, result.reason)

    def test_honeypot_beats_every_later_check(self):
        with mock.patch.object(antispam, "_siteverify") as sv:
            with self.assertLogs("crm.antispam", level="WARNING"):
                result = antispam.evaluate(self._post(website="http://spam.example"))
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "honeypot")
        sv.assert_not_called()

    def test_fast_bot_with_clean_honeypot_is_caught_on_timing(self):
        with mock.patch.object(antispam, "_siteverify") as sv:
            with mock.patch.object(antispam.time, "time", return_value=1_000_001):
                with self.assertLogs("crm.antispam", level="WARNING"):
                    result = antispam.evaluate(self._post())
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "too_fast")
        sv.assert_not_called()


class RateLimitTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()

    def test_allows_up_to_the_short_window_limit(self):
        for _ in range(antispam.RATE_LIMIT_SHORT):
            self.assertTrue(antispam.check_rate_limit("203.0.113.7").ok)

    def test_blocks_once_the_short_window_limit_is_exceeded(self):
        for _ in range(antispam.RATE_LIMIT_SHORT):
            antispam.check_rate_limit("203.0.113.7")
        result = antispam.check_rate_limit("203.0.113.7")
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "rate_limited")

    def test_limits_are_per_ip(self):
        for _ in range(antispam.RATE_LIMIT_SHORT + 2):
            antispam.check_rate_limit("203.0.113.7")
        self.assertTrue(antispam.check_rate_limit("198.51.100.9").ok)


class TimingTests(TestCase):
    def test_normal_delay_passes(self):
        planted = antispam.sign_timestamp(now=1_000_000)
        result = antispam.check_timing({antispam.TIMESTAMP_FIELD: planted}, now=1_000_030)
        self.assertTrue(result.ok, result.reason)

    def test_submitted_too_fast_is_rejected(self):
        planted = antispam.sign_timestamp(now=1_000_000)
        result = antispam.check_timing({antispam.TIMESTAMP_FIELD: planted}, now=1_000_001)
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "too_fast")

    def test_stale_form_is_rejected(self):
        planted = antispam.sign_timestamp(now=1_000_000)
        result = antispam.check_timing({antispam.TIMESTAMP_FIELD: planted}, now=1_000_000 + 8000)
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "stale")

    def test_tampered_timestamp_is_rejected(self):
        result = antispam.check_timing({antispam.TIMESTAMP_FIELD: "1000000:forged"}, now=1_000_030)
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "bad_timestamp")

    def test_missing_timestamp_is_rejected(self):
        result = antispam.check_timing({}, now=1_000_030)
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "bad_timestamp")


class HoneypotTests(TestCase):
    def test_empty_honeypot_passes(self):
        result = antispam.check_honeypot({"name": "Real Person"})
        self.assertTrue(result.ok)

    def test_filled_honeypot_is_rejected(self):
        result = antispam.check_honeypot({"website": "http://spam.example"})
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "honeypot")
