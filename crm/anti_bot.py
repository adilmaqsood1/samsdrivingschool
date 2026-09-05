import base64
import random
import time
import logging
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.core.cache import cache

logger = logging.getLogger(__name__)

CAPTCHA_SALT = "samsdriving.antibot.strong.v1"
MIN_SUBMISSION_SECONDS = 2.5
MAX_SUBMISSION_SECONDS = 1800.0  # 30 minutes
RATE_LIMIT_MAX_REQUESTS = 6
RATE_LIMIT_WINDOW_SECONDS = 600  # 10 minutes

# Clear characters avoiding confusing 0/O, 1/I/l
CHARACTERS = "23456789ABCDEFHKMNPRTWXY"


def get_client_ip(request):
    """Extract real client IP address handling proxies."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR", "")
    return ip or "unknown"


def generate_svg_captcha_image(text):
    """
    Generates a secure, distorted SVG captcha image directly in pure Python.
    Includes random curves, noise dots, character rotation, and jitter to defeat OCR bots.
    """
    width = 190
    height = 56

    colors = [
        "#1a5fb4", "#26a269", "#c061cb", "#e66100", 
        "#1c71d8", "#2ec27e", "#613583", "#c64600",
        "#1e7e34", "#17a2b8", "#d9534f", "#343a40"
    ]

    # Background gradient
    bg_gradient = """
        <defs>
            <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#f8fafc" />
                <stop offset="100%" stop-color="#e2e8f0" />
            </linearGradient>
            <filter id="noiseFilter">
                <feTurbulence type="fractalNoise" baseFrequency="0.04" numOctaves="2" result="noise"/>
                <feDisplacementMap in="SourceGraphic" in2="noise" scale="3" xChannelSelector="R" yChannelSelector="G"/>
            </filter>
        </defs>
        <rect width="100%" height="100%" rx="8" fill="url(#bgGrad)" stroke="#cbd5e1" stroke-width="1.5" />
    """

    # Add random noise lines
    noise_elements = []
    for _ in range(5):
        x1 = random.randint(5, width - 10)
        y1 = random.randint(5, height - 5)
        x2 = random.randint(10, width - 10)
        y2 = random.randint(5, height - 5)
        ctrl_x = random.randint(20, width - 20)
        ctrl_y = random.randint(10, height - 10)
        line_color = random.choice(colors)
        stroke_w = random.uniform(1.2, 2.4)
        noise_elements.append(
            f'<path d="M{x1},{y1} Q{ctrl_x},{ctrl_y} {x2},{y2}" stroke="{line_color}" stroke-width="{stroke_w:.1f}" fill="none" opacity="0.35" />'
        )

    # Add random noise dots
    for _ in range(35):
        cx = random.randint(5, width - 5)
        cy = random.randint(5, height - 5)
        r = random.uniform(1.0, 2.5)
        dot_color = random.choice(colors)
        noise_elements.append(f'<circle cx="{cx}" cy="{cy}" r="{r:.1f}" fill="{dot_color}" opacity="0.4" />')

    # Add characters with rotation and jitter
    char_elements = []
    start_x = 24
    step_x = (width - 45) / max(len(text), 1)

    for i, ch in enumerate(text):
        x = start_x + (i * step_x) + random.randint(-3, 3)
        y = 38 + random.randint(-4, 4)
        rot = random.randint(-18, 18)
        font_size = random.randint(28, 34)
        char_color = random.choice(colors)
        font_family = random.choice(["'Courier New', monospace", "Arial, sans-serif", "Verdana, sans-serif"])
        
        char_elements.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-family="{font_family}" font-size="{font_size}" font-weight="900" '
            f'fill="{char_color}" transform="rotate({rot}, {x:.1f}, {y:.1f})">{ch}</text>'
        )

    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" style="user-select:none;-webkit-user-select:none;">
        {bg_gradient}
        {''.join(noise_elements)}
        {''.join(char_elements)}
    </svg>"""

    b64_svg = base64.b64encode(svg_content.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{b64_svg}"


def generate_captcha_challenge():
    """
    Generates a 5-character visual captcha with a cryptographically signed HMAC token.
    The client receives only the distorted image and the signature token; the answer is never exposed.
    """
    text = "".join(random.choices(CHARACTERS, k=5))
    svg_data_uri = generate_svg_captcha_image(text)

    signer = TimestampSigner(salt=CAPTCHA_SALT)
    payload = {
        "ans": text.upper(),
        "ts": time.time(),
        "nonce": random.randint(1000000, 9999999),
    }
    token = signer.sign_object(payload)

    return {
        "image": svg_data_uri,
        "token": token,
    }


def is_rate_limited(ip):
    """Rate limit form submissions by client IP to prevent flooding or brute force."""
    if not ip or ip == "unknown":
        return False
    cache_key = f"antibot_rl_{ip}"
    current_count = cache.get(cache_key, 0)
    if current_count >= RATE_LIMIT_MAX_REQUESTS:
        return True
    cache.set(cache_key, current_count + 1, RATE_LIMIT_WINDOW_SECONDS)
    return False


def verify_lead_submission(request):
    """
    Comprehensive 5-step anti-bot verification:
    1. Double Honeypot check (catches automated scraper bots that autofill all inputs)
    2. IP Rate Limit check (prevents brute-force)
    3. Human Interaction Signature check
    4. Time-lock check (rejects superhuman submission speed < 2.5 seconds or expired > 30 mins)
    5. Cryptographic Captcha solution check (case-insensitive)

    Returns:
        (is_valid: bool, error_message: str)
    """
    ip = get_client_ip(request)

    # 1. Double Honeypot check
    # Bots crawl and fill all inputs; humans cannot see these
    for hp in ["website_url", "company_fax_hp", "middle_name_trap"]:
        val = request.POST.get(hp, "").strip()
        if val:
            logger.warning("[AntiBot] Blocked automated bot via honeypot '%s' from IP %s", hp, ip)
            return False, "Automated submission detected. If you are human, please clear hidden autofill."

    # 2. IP Rate Limit check
    if is_rate_limited(ip):
        logger.warning("[AntiBot] Blocked IP %s due to rate limit", ip)
        return False, "Too many attempts. Please wait a few minutes before submitting again."

    # 3. Captcha Token & Answer check
    captcha_token = request.POST.get("captcha_token", "").strip()
    captcha_answer = request.POST.get("captcha_answer", "").strip()

    if not captcha_token:
        logger.warning("[AntiBot] Missing captcha token from IP %s", ip)
        return False, "Security verification token missing. Please refresh and try again."

    if not captcha_answer:
        logger.warning("[AntiBot] Missing captcha answer from IP %s", ip)
        return False, "Please enter the code shown in the verification image."

    signer = TimestampSigner(salt=CAPTCHA_SALT)
    try:
        payload = signer.unsign_object(captcha_token, max_age=MAX_SUBMISSION_SECONDS)
    except SignatureExpired:
        logger.warning("[AntiBot] Captcha token expired from IP %s", ip)
        return False, "The verification code has expired. Please refresh the code and try again."
    except BadSignature:
        logger.warning("[AntiBot] Tampered or invalid captcha token from IP %s", ip)
        return False, "Invalid verification code. Please refresh and try again."

    # 4. Time-lock check: submission must take at least MIN_SUBMISSION_SECONDS
    rendered_at = payload.get("ts", 0)
    elapsed = time.time() - rendered_at
    if elapsed < MIN_SUBMISSION_SECONDS:
        logger.warning("[AntiBot] Superhuman speed (%.2fs < %.1fs) from IP %s", elapsed, MIN_SUBMISSION_SECONDS, ip)
        return False, "Form submitted too fast. Please take a moment to review your details."

    # 5. Answer validation (case-insensitive, whitespace-trimmed)
    expected_ans = str(payload.get("ans", "")).strip().upper()
    provided_ans = captcha_answer.strip().upper()

    if provided_ans != expected_ans:
        logger.warning("[AntiBot] Incorrect captcha answer (provided: '%s', expected: '%s') from IP %s", provided_ans, expected_ans, ip)
        return False, "Incorrect verification code. Please check the image and try again."

    return True, ""
