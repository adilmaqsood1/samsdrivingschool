import re
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from crm import antispam
from crm.models import Blog, EnrollmentRequest, Lead, LessonRequest


def _valid_fields(now=1_000_000):
    return {
        antispam.TIMESTAMP_FIELD: antispam.sign_timestamp(now=now),
    }


@override_settings(
    ANTISPAM_ENABLED=True,
    TURNSTILE_SECRET_KEY="",  # Turnstile check skipped; local layers still active
    ENROLLMENT_NOTIFICATION_EMAIL="info@samsdriving.ca",
)
class LeadCaptureAntiSpamTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()

    def _submit(self, data, submit_time=1_000_030):
        with mock.patch.object(antispam.time, "time", return_value=submit_time):
            return self.client.post(reverse("lead_capture"), data)

    def test_clean_submission_creates_lead_and_sends_mail(self):
        resp = self._submit({
            "name": "Real Person",
            "email": "real@example.com",
            "message": "I want lessons",
            **_valid_fields(),
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Lead.objects.count(), 1)
        self.assertTrue(mail.outbox)

    def test_honeypot_submission_is_silently_dropped(self):
        resp = self._submit({
            "name": "Spam Bot",
            "email": "spam@example.com",
            "message": "buy cheap stuff",
            "website": "http://spam.example",
            **_valid_fields(),
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Lead.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_submission_faster_than_three_seconds_is_dropped(self):
        resp = self._submit(
            {"name": "Fast Bot", "email": "b@example.com", **_valid_fields()},
            submit_time=1_000_001,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Lead.objects.count(), 0)

    def test_missing_timestamp_is_dropped(self):
        resp = self._submit({"name": "No TS Bot", "email": "b@example.com"})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Lead.objects.count(), 0)

    def test_fourth_submission_from_same_ip_is_rate_limited(self):
        for i in range(antispam.RATE_LIMIT_SHORT):
            self._submit({
                "name": f"Person {i}",
                "email": f"p{i}@example.com",
                **_valid_fields(),
            })
        self.assertEqual(Lead.objects.count(), antispam.RATE_LIMIT_SHORT)
        self._submit({"name": "Extra", "email": "extra@example.com", **_valid_fields()})
        self.assertEqual(Lead.objects.count(), antispam.RATE_LIMIT_SHORT)


@override_settings(ANTISPAM_ENABLED=True, TURNSTILE_SECRET_KEY="",
                   ENROLLMENT_NOTIFICATION_EMAIL="info@samsdriving.ca")
class EnrollAndLessonAntiSpamTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()

    def test_enroll_request_blocks_honeypot(self):
        with mock.patch.object(antispam.time, "time", return_value=1_000_030):
            resp = self.client.post(reverse("enroll_request"), {
                "name": "Bot", "email": "bot@example.com", "website": "x",
                **_valid_fields(),
            })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(EnrollmentRequest.objects.count(), 0)
        self.assertEqual(Lead.objects.count(), 0)

    def test_enroll_request_allows_clean(self):
        with mock.patch.object(antispam.time, "time", return_value=1_000_030):
            resp = self.client.post(reverse("enroll_request"), {
                "name": "Real Student", "email": "s@example.com", "package": "G2",
                **_valid_fields(),
            })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(EnrollmentRequest.objects.count(), 1)

    def test_lesson_request_blocks_fast_submit(self):
        with mock.patch.object(antispam.time, "time", return_value=1_000_001):
            resp = self.client.post(reverse("lesson_request"), {
                "name": "Bot", "email": "bot@example.com", **_valid_fields(),
            })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(LessonRequest.objects.count(), 0)


@override_settings(ANTISPAM_ENABLED=True, TURNSTILE_SECRET_KEY="")
class ProcessEnrollmentAntiSpamTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()

    def test_honeypot_enrollment_is_dropped_before_any_records(self):
        from crm.models import Student

        with mock.patch.object(antispam.time, "time", return_value=1_000_030):
            resp = self.client.post(reverse("process_enrollment"), {
                "course_slug": "g2", "first_name": "Bot", "email": "b@example.com",
                "website": "x", **_valid_fields(),
            })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Student.objects.count(), 0)
        self.assertEqual(Lead.objects.count(), 0)


@override_settings(ANTISPAM_ENABLED=True, TURNSTILE_SECRET_KEY="")
class RenderRoundTripTests(TestCase):
    """The timestamp planted in the rendered page must be accepted on submit."""

    def setUp(self):
        from django.core.cache import cache

        cache.clear()

    def test_token_from_contact_page_is_accepted_on_post(self):
        page = self.client.get(reverse("contact_page")).content.decode()
        match = re.search(
            rf'name="{antispam.TIMESTAMP_FIELD}" value="([^"]+)"', page
        )
        self.assertIsNotNone(match, "antispam timestamp field missing from contact page")
        planted = int(antispam._timestamp_signer.unsign(match.group(1)))
        with mock.patch.object(antispam.time, "time", return_value=planted + 30):
            resp = self.client.post(reverse("lead_capture"), {
                "name": "Real Person", "email": "real@example.com",
                antispam.TIMESTAMP_FIELD: match.group(1),
            })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Lead.objects.count(), 1)


@override_settings(ANTISPAM_ENABLED=True, TURNSTILE_SECRET_KEY="")
class BlogCommentAntiSpamTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.blog = Blog.objects.create(title="Post", slug="post", is_published=True)

    def test_honeypot_comment_is_dropped(self):
        from crm.models import BlogComment

        with mock.patch.object(antispam.time, "time", return_value=1_000_030):
            self.client.post(reverse("blog_comment_create", args=[self.blog.slug]), {
                "name": "Bot", "body": "spam link", "website": "x", **_valid_fields(),
            })
        self.assertEqual(BlogComment.objects.count(), 0)
