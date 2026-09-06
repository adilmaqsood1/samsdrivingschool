"""Tests for crm.analytics (server-side GA4 Measurement Protocol) and the
GA client-id capture wired into the checkout + webhook paths."""

from decimal import Decimal
from unittest import mock

from django.test import Client, RequestFactory, TestCase, override_settings

from crm import analytics
from crm.models import Course, CourseSession, Enrollment, Invoice, Student


def _invoice(number="INV-TEST-1", amount="500.00"):
    course = Course.objects.create(name="BDE Test", slug="bde-test", price=amount, active=True)
    session = CourseSession.objects.create(
        course=course, start_date="2099-01-01", enrollment_open=True
    )
    student = Student.objects.create(first_name="Alice", last_name="Doe", email="a@example.com")
    enrollment = Enrollment.objects.create(student=student, session=session, status="pending")
    return Invoice.objects.create(
        enrollment=enrollment,
        number=number,
        issue_date="2099-01-01",
        total_amount=Decimal(amount),
        status="paid",
    )


class ClientIdFromRequestTests(TestCase):
    def _req(self, ga_cookie=None):
        req = RequestFactory().get("/")
        if ga_cookie is not None:
            req.COOKIES["_ga"] = ga_cookie
        return req

    def test_parses_standard_ga_cookie(self):
        self.assertEqual(
            analytics.client_id_from_request(self._req("GA1.1.1234567890.1700000000")),
            "1234567890.1700000000",
        )

    def test_missing_cookie_returns_empty(self):
        self.assertEqual(analytics.client_id_from_request(self._req()), "")

    def test_malformed_cookie_returns_empty(self):
        self.assertEqual(analytics.client_id_from_request(self._req("garbage")), "")


class ServerSideEnabledTests(TestCase):
    @override_settings(GA4_MEASUREMENT_ID="G-X", GA4_API_SECRET="")
    def test_disabled_without_api_secret(self):
        self.assertFalse(analytics.server_side_enabled())

    @override_settings(GA4_MEASUREMENT_ID="", GA4_API_SECRET="secret")
    def test_disabled_without_measurement_id(self):
        self.assertFalse(analytics.server_side_enabled())

    @override_settings(GA4_MEASUREMENT_ID="G-X", GA4_API_SECRET="secret")
    def test_enabled_with_both(self):
        self.assertTrue(analytics.server_side_enabled())

    @override_settings(GA4_MEASUREMENT_ID="G-X", GA4_API_SECRET="")
    def test_ga4_collect_is_noop_when_disabled(self):
        # No network patching: a network call here would raise / hang.
        self.assertFalse(analytics.ga4_collect("cid", [{"name": "purchase"}]))


@override_settings(ANALYTICS_CURRENCY="CAD")
class BuildPurchaseEventTests(TestCase):
    def test_event_shape(self):
        invoice = _invoice(number="INV-9", amount="450.00")
        event = analytics.build_purchase_event(invoice)
        self.assertEqual(event["name"], "purchase")
        params = event["params"]
        self.assertEqual(params["transaction_id"], "INV-9")
        self.assertEqual(params["value"], 450.0)
        self.assertEqual(params["currency"], "CAD")
        self.assertEqual(len(params["items"]), 1)
        self.assertEqual(params["items"][0]["item_id"], "bde-test")
        self.assertEqual(params["items"][0]["item_name"], "BDE Test")


class ReportPurchaseTests(TestCase):
    @override_settings(GA4_MEASUREMENT_ID="G-X", GA4_API_SECRET="")
    def test_noop_when_server_side_disabled(self):
        invoice = _invoice()
        with mock.patch.object(analytics, "ga4_collect") as collect:
            self.assertFalse(analytics.report_purchase(invoice))
            collect.assert_not_called()
        invoice.refresh_from_db()
        self.assertFalse(invoice.ga_purchase_reported)

    @override_settings(GA4_MEASUREMENT_ID="G-X", GA4_API_SECRET="secret")
    def test_reports_once_and_sets_flag(self):
        invoice = _invoice()
        with mock.patch.object(analytics, "ga4_collect", return_value=True) as collect:
            self.assertTrue(analytics.report_purchase(invoice))
            self.assertEqual(collect.call_count, 1)
            _cid, events = collect.call_args[0]
            self.assertEqual(events[0]["params"]["transaction_id"], invoice.number)
        invoice.refresh_from_db()
        self.assertTrue(invoice.ga_purchase_reported)

        # Second call is a no-op (flag already set).
        with mock.patch.object(analytics, "ga4_collect", return_value=True) as collect:
            self.assertFalse(analytics.report_purchase(invoice))
            collect.assert_not_called()

    @override_settings(GA4_MEASUREMENT_ID="G-X", GA4_API_SECRET="secret")
    def test_flag_not_set_when_collect_fails(self):
        invoice = _invoice()
        with mock.patch.object(analytics, "ga4_collect", return_value=False):
            self.assertFalse(analytics.report_purchase(invoice))
        invoice.refresh_from_db()
        self.assertFalse(invoice.ga_purchase_reported)

    @override_settings(GA4_MEASUREMENT_ID="G-X", GA4_API_SECRET="secret")
    def test_uses_stored_client_id(self):
        invoice = _invoice()
        invoice.ga_client_id = "111.222"
        invoice.save(update_fields=["ga_client_id"])
        with mock.patch.object(analytics, "ga4_collect", return_value=True) as collect:
            analytics.report_purchase(invoice)
            self.assertEqual(collect.call_args[0][0], "111.222")


class CheckoutCapturesGaClientIdTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(
            name="BDE Test", slug="bde-test", price="500.00", course_type="bde", active=True
        )
        CourseSession.objects.create(
            course=self.course, start_date="2099-01-01", enrollment_open=True
        )

    def test_invoice_records_ga_client_id_from_cookie(self):
        self.client.cookies["_ga"] = "GA1.1.555000555.1699999999"
        resp = self.client.post(
            "/crm/enroll/process/",
            {
                "course_slug": "bde-test",
                "first_name": "Alice",
                "last_name": "Doe",
                "email": "alice@example.com",
                "phone": "555-1212",
                "payment_method": "square",
            },
        )
        self.assertEqual(resp.status_code, 302)
        invoice = Invoice.objects.get()
        self.assertEqual(invoice.ga_client_id, "555000555.1699999999")


class MarkInvoicePaidReportsPurchaseTests(TestCase):
    def test_webhook_paid_path_calls_report_purchase(self):
        from crm.views import _mark_invoice_paid_square

        invoice = _invoice(number="INV-WH-1")
        invoice.status = "issued"
        invoice.save(update_fields=["status"])
        with mock.patch("crm.views.analytics.report_purchase") as report:
            _mark_invoice_paid_square(invoice.id, payment_id="pay_1", order_id="ord_1")
            report.assert_called_once()
            self.assertEqual(report.call_args[0][0].id, invoice.id)


@override_settings(GA4_MEASUREMENT_ID="G-TEST0000", GOOGLE_ADS_CONVERSION_ID="AW-TEST123")
class BaseTemplateTagRenderTests(TestCase):
    def test_public_pages_carry_gtag_and_lead_tracking(self):
        client = Client()
        for url in ("/", "/contact/"):
            body = client.get(url).content.decode("utf-8", "replace")
            self.assertIn("gtag/js?id=G-TEST0000", body)
            self.assertIn("AW-TEST123", body)
            self.assertIn("generate_lead", body)
            self.assertIn("lead_sent", body)

    @override_settings(GA4_MEASUREMENT_ID="", GOOGLE_ADS_CONVERSION_ID="")
    def test_no_gtag_when_unconfigured(self):
        body = Client().get("/").content.decode("utf-8", "replace")
        self.assertNotIn("googletagmanager.com/gtag", body)
