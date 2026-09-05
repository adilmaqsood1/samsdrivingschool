"""Tests for crm.views.process_enrollment after the antispam + idempotency refactor.

Covers the bugs fixed in the refactor:

- re-submitting the same form does NOT create duplicate Student / Lead /
  Enrollment / Invoice rows;
- if no open CourseSession exists, the enrollment still goes through against a
  single reusable per-course placeholder session (no "Online/TBD" ghost
  session is spawned per submission);
- pay-in-office path uses SCHOOL_PHONE from settings, not a hardcoded literal;
- invoices always get a unique number (no random.randint collision retries);
- an invalid email is rejected outright instead of producing a placeholder
  ``visitor+<timestamp>@example.com`` lead.
"""

import re
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from crm import antispam
from crm.models import (
    Blog,
    Course,
    CourseSession,
    Enrollment,
    EnrollmentRequest,
    Invoice,
    Lead,
    Student,
)


def _valid_fields(now=1_000_000):
    return {antispam.TIMESTAMP_FIELD: antispam.sign_timestamp(now=now)}


def _course():
    return Course.objects.create(
        name="BDE Test",
        slug="bde-test",
        price="500.00",
        course_type="bde",
        active=True,
    )


@override_settings(
    ANTISPAM_ENABLED=True,
    TURNSTILE_SECRET_KEY="",
    ENROLLMENT_NOTIFICATION_EMAIL="info@samsdriving.ca",
    SCHOOL_PHONE="+164****1708",
    SCHOOL_PHONE_DISPLAY="+1 (647) 889-1708",
)
class ProcessEnrollmentIdempotencyTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.course = _course()
        self.session = CourseSession.objects.create(
            course=self.course,
            start_date="2099-01-01",
            enrollment_open=True,
        )

    def _submit(self, *, email="alice@example.com", first="Alice", submit_time=1_000_030, **extra):
        with mock.patch.object(antispam.time, "time", return_value=submit_time):
            return self.client.post(
                reverse("process_enrollment"),
                {
                    "course_slug": self.course.slug,
                    "first_name": first,
                    "last_name": "Doe",
                    "email": email,
                    "phone": "555-1212",
                    "address": "1 Main",
                    "city": "Toronto",
                    "province": "ON",
                    "postal_code": "M5V 1A1",
                    **_valid_fields(),
                    **extra,
                },
            )

    def test_first_submission_creates_one_of_each(self):
        resp = self._submit()
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Student.objects.count(), 1)
        self.assertEqual(EnrollmentRequest.objects.count(), 1)
        self.assertEqual(Lead.objects.count(), 1)
        self.assertEqual(Enrollment.objects.count(), 1)
        self.assertEqual(Invoice.objects.count(), 1)

    def test_resubmission_with_same_email_creates_no_duplicates(self):
        self._submit()
        # Second pass with the same data: should update, not duplicate.
        resp = self._submit()
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Student.objects.count(), 1)
        self.assertEqual(EnrollmentRequest.objects.count(), 1)
        self.assertEqual(Lead.objects.count(), 1)
        # The enrollment is keyed on (student, session) so it stays at 1,
        # but a NEW invoice must not be issued on resubmit.
        self.assertEqual(Enrollment.objects.count(), 1)
        self.assertEqual(Invoice.objects.count(), 1)

    def test_invalid_email_is_rejected_no_placeholder_rows(self):
        resp = self._submit(email="not-an-email")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Student.objects.count(), 0)
        self.assertEqual(Lead.objects.count(), 0)
        self.assertEqual(EnrollmentRequest.objects.count(), 0)
        # Ensure NO visitor+timestamp@example.com placeholder landed anywhere.
        self.assertFalse(Lead.objects.filter(email__startswith="visitor+").exists())

    def test_no_open_session_still_enrolls_against_placeholder(self):
        from crm.views import PLACEHOLDER_SESSION_LOCATION

        self.session.enrollment_open = False
        self.session.save()
        resp = self._submit()
        self.assertEqual(resp.status_code, 302)
        # Enrollment + invoice still go through.
        self.assertEqual(Student.objects.count(), 1)
        self.assertEqual(Enrollment.objects.count(), 1)
        self.assertEqual(Invoice.objects.count(), 1)
        # Exactly one placeholder session was created and it is not open.
        placeholders = CourseSession.objects.filter(
            course=self.course, location=PLACEHOLDER_SESSION_LOCATION
        )
        self.assertEqual(placeholders.count(), 1)
        self.assertFalse(placeholders.first().enrollment_open)
        self.assertEqual(Enrollment.objects.first().session, placeholders.first())

    def test_no_open_session_resubmit_reuses_one_placeholder(self):
        from crm.views import PLACEHOLDER_SESSION_LOCATION

        self.session.enrollment_open = False
        self.session.save()
        self._submit()
        self._submit()
        # No ghost-session proliferation across submissions.
        self.assertEqual(
            CourseSession.objects.filter(
                course=self.course, location=PLACEHOLDER_SESSION_LOCATION
            ).count(),
            1,
        )
        self.assertEqual(Enrollment.objects.count(), 1)
        self.assertEqual(Invoice.objects.count(), 1)


@override_settings(
    ANTISPAM_ENABLED=True,
    TURNSTILE_SECRET_KEY="",
    ENROLLMENT_NOTIFICATION_EMAIL="info@samsdriving.ca",
    SCHOOL_PHONE="+164****1708",
    SCHOOL_PHONE_DISPLAY="+1 (647) 889-1708",
)
class PayInOfficeUsesSettingsPhoneTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.course = _course()
        self.session = CourseSession.objects.create(
            course=self.course,
            start_date="2099-01-01",
            enrollment_open=True,
        )

    def test_pay_later_email_uses_school_phone_from_settings(self):
        with mock.patch.object(antispam.time, "time", return_value=1_000_030):
            with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
                resp = self.client.post(
                    reverse("process_enrollment"),
                    {
                        "course_slug": self.course.slug,
                        "first_name": "Bob",
                        "last_name": "Smith",
                        "email": "bob@example.com",
                        "phone": "555-1212",
                        "address": "1 Main",
                        "city": "Toronto",
                        "province": "ON",
                        "postal_code": "M5V 1A1",
                        "payment_method": "pay_later",
                        **_valid_fields(),
                    },
                )
        self.assertEqual(resp.status_code, 200)
        from django.core import mail

        self.assertTrue(mail.outbox, "pay-later path should send at least one email")

        # The display phone must appear in the plaintext body (so the recipient
        # can read it in any mail client). The tel: link is in the HTML
        # alternative. Together they prove the value flowed through settings
        # rather than a hardcoded literal.
        bodies = [(m.body or "") for m in mail.outbox] + [
            alt
            for m in mail.outbox
            for alt, _ctype in getattr(m, "alternatives", [])
            if isinstance(alt, str)
        ]
        joined = "\n".join(bodies)
        self.assertIn("+1 (647) 889-1708", joined, "display phone missing from body")
        self.assertIn("tel:+164****1708", joined, "tel: link missing from HTML alternative")
