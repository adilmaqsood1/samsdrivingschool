"""Layered spam defense for the public website forms.

Four independent checks, cheapest first:

1. honeypot  - a form field real users never see; bots fill it in
2. timing    - a signed timestamp planted when the page renders; reject
               submissions that arrive implausibly fast or stale
3. rate limit - per-IP submission ceiling, backed by the Django cache
4. Turnstile - Cloudflare's privacy-friendly CAPTCHA, verified server-side

``evaluate()`` runs them in order and returns the first failure. Every
check degrades to "allow" when its dependency is not configured so the
forms keep working before the Turnstile keys are deployed.
"""

import json
import logging
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass

from django.conf import settings
from django.core import signing
from django.core.cache import cache

logger = logging.getLogger(__name__)

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
SITEVERIFY_TIMEOUT = 5
TURNSTILE_FIELD = "cf-turnstile-response"


@dataclass
class SpamCheck:
    ok: bool
    reason: str = ""


HONEYPOT_FIELD = "website"
TIMESTAMP_FIELD = "form_loaded_at"

MIN_FILL_SECONDS = 3
MAX_FORM_AGE_SECONDS = 2 * 60 * 60

RATE_LIMIT_SHORT = 3
RATE_LIMIT_SHORT_WINDOW = 10 * 60
RATE_LIMIT_LONG = 10
RATE_LIMIT_LONG_WINDOW = 60 * 60

_timestamp_signer = signing.Signer(salt="crm.antispam.timestamp")


def sign_timestamp(now: float | None = None) -> str:
    """Value planted in a hidden field when the form page is rendered."""
    epoch = int(now if now is not None else time.time())
    return _timestamp_signer.sign(str(epoch))


def check_timing(
    post,
    *,
    now: float | None = None,
    min_seconds: int = MIN_FILL_SECONDS,
    max_seconds: int = MAX_FORM_AGE_SECONDS,
) -> SpamCheck:
    raw = post.get(TIMESTAMP_FIELD) or ""
    try:
        planted = int(_timestamp_signer.unsign(raw))
    except (signing.BadSignature, ValueError):
        return SpamCheck(False, "bad_timestamp")
    age = int(now if now is not None else time.time()) - planted
    if age < min_seconds:
        return SpamCheck(False, "too_fast")
    if age > max_seconds:
        return SpamCheck(False, "stale")
    return SpamCheck(True)


def _bump(key: str, window: int) -> int:
    """Increment a per-window counter, seeding it on first use. Returns the new count."""
    cache.add(key, 0, window)
    try:
        return cache.incr(key)
    except ValueError:
        # Entry expired between add and incr; treat as first hit in a new window.
        cache.set(key, 1, window)
        return 1


def check_rate_limit(ip: str) -> SpamCheck:
    if not ip:
        return SpamCheck(True)
    short = _bump(f"antispam:rl:short:{ip}", RATE_LIMIT_SHORT_WINDOW)
    long = _bump(f"antispam:rl:long:{ip}", RATE_LIMIT_LONG_WINDOW)
    if short > RATE_LIMIT_SHORT or long > RATE_LIMIT_LONG:
        return SpamCheck(False, "rate_limited")
    return SpamCheck(True)


def _siteverify(secret: str, token: str, remote_ip: str) -> dict:
    payload = urllib.parse.urlencode(
        {"secret": secret, "response": token, "remoteip": remote_ip or ""}
    ).encode()
    request = urllib.request.Request(SITEVERIFY_URL, data=payload)
    with urllib.request.urlopen(request, timeout=SITEVERIFY_TIMEOUT) as response:
        return json.loads(response.read().decode())


def verify_turnstile(token: str, remote_ip: str = "") -> SpamCheck:
    secret = getattr(settings, "TURNSTILE_SECRET_KEY", "") or ""
    if not getattr(settings, "ANTISPAM_ENABLED", True) or not secret:
        return SpamCheck(True)
    if not (token or "").strip():
        return SpamCheck(False, "turnstile_missing")
    try:
        data = _siteverify(secret, token, remote_ip)
    except Exception:  # noqa: BLE001 - network/parse failure must not lock out real users
        logger.warning("Turnstile siteverify unreachable; allowing submission", exc_info=True)
        return SpamCheck(True, "turnstile_unreachable")
    if data.get("success"):
        return SpamCheck(True)
    logger.info("Turnstile rejected a submission: %s", data.get("error-codes"))
    return SpamCheck(False, "turnstile_failed")


def client_ip(request) -> str:
    if getattr(settings, "ANTISPAM_TRUST_XFF", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or ""


def evaluate(request) -> SpamCheck:
    """Run every check against an inbound form POST; return the first failure.

    Ordering is cheapest-first: the honeypot and timing checks are pure local
    computation, the rate limit is a cache round-trip, and Turnstile is an
    outbound HTTP call made only when everything else has passed.
    """
    post = request.POST
    ip = client_ip(request)

    for check in (
        lambda: check_honeypot(post),
        lambda: check_timing(post),
        lambda: check_rate_limit(ip),
        lambda: verify_turnstile(post.get(TURNSTILE_FIELD, ""), ip),
    ):
        result = check()
        if not result.ok:
            logger.warning("Blocked form submission from %s: %s", ip or "?", result.reason)
            return result
    return SpamCheck(True)


def check_honeypot(post) -> SpamCheck:
    if (post.get(HONEYPOT_FIELD) or "").strip():
        return SpamCheck(False, "honeypot")
    return SpamCheck(True)
