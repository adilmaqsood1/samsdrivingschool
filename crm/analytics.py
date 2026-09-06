"""Server-side analytics: GA4 Measurement Protocol.

The website loads gtag.js client-side for pageviews and for events that
happen in the browser (lead form submits, tel/mailto clicks, the
``purchase`` event on the payment-success page). Client-side alone
under-counts purchases: ad blockers drop 10-30% of hits and a buyer who
closes the Square tab without returning never fires the browser event.

``report_purchase()`` closes that gap. It runs from the Square webhook
handler -- the one code path that always executes when a payment
completes -- and posts a ``purchase`` event straight to GA4 over the
Measurement Protocol, keyed on the invoice number so GA4 de-duplicates
it against any client-side ``purchase`` for the same transaction.

Everything degrades to a no-op when the measurement id or API secret is
missing, and network failures are logged, never raised, so analytics can
never break checkout.
"""

import json
import logging
import urllib.request
import uuid
from decimal import Decimal

from django.conf import settings

logger = logging.getLogger(__name__)

COLLECT_URL = "https://www.google-analytics.com/mp/collect"
DEBUG_COLLECT_URL = "https://www.google-analytics.com/debug/mp/collect"
REQUEST_TIMEOUT = 5


def _measurement_id() -> str:
    return getattr(settings, "GA4_MEASUREMENT_ID", "") or ""


def _api_secret() -> str:
    return getattr(settings, "GA4_API_SECRET", "") or ""


def _currency() -> str:
    return getattr(settings, "ANALYTICS_CURRENCY", "CAD") or "CAD"


def server_side_enabled() -> bool:
    """True when both credentials the Measurement Protocol needs are set."""
    return bool(_measurement_id() and _api_secret())


def new_client_id() -> str:
    """A synthetic GA client id for events with no browser-supplied one.

    GA4 wants ``<random>.<timestamp>``. A purchase reported with a fresh
    id still counts; it just starts its own (attribution-less) session.
    """
    return f"{uuid.uuid4().int % (10**10)}.{uuid.uuid4().int % (10**10)}"


def client_id_from_request(request) -> str:
    """Pull the GA4 client id out of the ``_ga`` cookie, if present.

    The cookie value is ``GA1.1.<client-id>`` where the client id is itself
    ``<random>.<timestamp>``. Returns "" when the cookie is missing or
    malformed (a fresh id is synthesised later).
    """
    raw = request.COOKIES.get("_ga", "") or ""
    parts = raw.split(".")
    if len(parts) >= 4 and parts[0].startswith("GA"):
        return f"{parts[2]}.{parts[3]}"
    return ""


def ga4_collect(client_id: str, events: list[dict], *, user_properties: dict | None = None) -> bool:
    """POST one batch of events to GA4. Returns True on a 2xx response.

    Never raises: a misconfigured or unreachable endpoint returns False.
    """
    if not server_side_enabled():
        return False

    payload = {"client_id": client_id or new_client_id(), "events": events}
    if user_properties:
        payload["user_properties"] = user_properties

    debug = bool(getattr(settings, "ANALYTICS_DEBUG", False))
    base = DEBUG_COLLECT_URL if debug else COLLECT_URL
    url = f"{base}?measurement_id={_measurement_id()}&api_secret={_api_secret()}"

    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            raw = response.read().decode("utf-8", "replace")
            status = response.getcode()
    except Exception:  # noqa: BLE001 - analytics must never break the caller
        logger.warning("GA4 Measurement Protocol request failed", exc_info=True)
        return False

    if debug:
        logger.info("GA4 debug validation response: %s", raw)
    return 200 <= status < 300


def build_purchase_event(invoice) -> dict:
    """A GA4 ``purchase`` event for a paid invoice.

    ``transaction_id`` is the invoice number so this event de-duplicates
    against a client-side ``purchase`` for the same sale.
    """
    enrollment = getattr(invoice, "enrollment", None)
    session = getattr(enrollment, "session", None)
    course = getattr(session, "course", None)
    course_name = getattr(course, "name", "") or "Driving Course"
    course_id = getattr(course, "slug", "") or (str(course.pk) if course else "course")

    value = invoice.total_amount or Decimal("0")
    return {
        "name": "purchase",
        "params": {
            "transaction_id": invoice.number,
            "value": float(value),
            "currency": _currency(),
            "items": [
                {
                    "item_id": course_id,
                    "item_name": course_name,
                    "item_category": "Driving Course",
                    "price": float(value),
                    "quantity": 1,
                }
            ],
        },
    }


def report_purchase(invoice) -> bool:
    """Send the server-side ``purchase`` event for ``invoice`` exactly once.

    No-ops when server-side tracking is unconfigured or when this invoice
    has already been reported (``invoice.ga_purchase_reported``). Called
    from the Square webhook's paid-invoice path.
    """
    if getattr(invoice, "ga_purchase_reported", False):
        return False
    if not server_side_enabled():
        return False

    client_id = getattr(invoice, "ga_client_id", "") or new_client_id()
    ok = ga4_collect(client_id, [build_purchase_event(invoice)])
    if ok:
        invoice.ga_purchase_reported = True
        invoice.save(update_fields=["ga_purchase_reported"])
        logger.info("Reported server-side GA4 purchase for invoice %s", invoice.number)
    return ok
