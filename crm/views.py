from datetime import timedelta
import secrets
from urllib.parse import urlencode
import requests
import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import get_template
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .forms import LeadForm, StudentRegistrationForm, LoginForm, EnrollmentRequestForm, LessonRequestForm
from .models import (
    Lead,
    LeadNote,
    Student,
    Invoice,
    Payment,
    CalendarFeed,
    CalendarAccount,
    Lesson,
    EnrollmentRequest,
    LessonRequest,
    ScheduledEmail,
    Notification,
    NotificationReceipt,
    Blog,
    BlogCategory,
    BlogTag,
    BlogComment,
    Testimonial,
)


def template_page(request, template_name):
    if ".." in template_name or template_name.startswith("/"):
        raise Http404()
    if not template_name.endswith(".html"):
        template_name = f"{template_name}.html"
    try:
        get_template(template_name)
    except Exception as exc:
        raise Http404() from exc
    return render(request, template_name)


def index_page(request):
    home_blogs = Blog.objects.filter(is_published=True).order_by("-published_at")[:6]
    testimonials = Testimonial.objects.filter(is_published=True).order_by("display_order", "-updated_at")[:12]
    return render(request, "index.html", {"home_blogs": home_blogs, "testimonials": testimonials})


def about_page(request):
    testimonials = Testimonial.objects.filter(is_published=True).order_by("display_order", "-updated_at")[:12]
    return render(request, "about.html", {"testimonials": testimonials})


def team_page(request):
    return render(request, "team.html")


def team_details_page(request):
    return render(request, "team-details.html")


def gallery_page(request):
    return render(request, "gallery.html")


def faq_page(request):
    return render(request, "faq.html")


def login_page(request):
    return render(request, "login.html")


def not_found_page(request):
    return render(request, "404.html")


def course_page(request):
    return render(request, "course.html")


def course_details_page(request):
    return render(request, "course-details.html")


def blog_grid_right_page(request):
    blogs = Blog.objects.filter(is_published=True).order_by("-published_at")
    latest_blogs = blogs[:3]
    categories = BlogCategory.objects.order_by("name")
    tags = BlogTag.objects.order_by("name")
    comments = (
        BlogComment.objects.filter(is_approved=True, blog__is_published=True)
        .select_related("blog")
        .order_by("-created_at")[:4]
    )
    return render(
        request,
        "blogs.html",
        {"blogs": blogs, "latest_blogs": latest_blogs, "categories": categories, "tags": tags, "comments": comments},
    )


def blog_details_right_page(request, slug):
    blog = get_object_or_404(Blog, slug=slug, is_published=True)
    latest_blogs = (
        Blog.objects.filter(is_published=True).exclude(pk=blog.pk).order_by("-published_at")[:3]
    )
    return render(request, "blog-details.html", {"blog": blog, "latest_blogs": latest_blogs})


def contact_page(request):
    return render(request, "contact.html")


def lead_capture(request):
    if request.method != "POST":
        return HttpResponseRedirect(reverse("contact_page"))
    form = LeadForm(request.POST)
    if not form.is_valid():
        return HttpResponseRedirect(request.META.get("HTTP_REFERER") or reverse("contact_page"))
    name = form.cleaned_data.get("name", "").strip()
    email = form.cleaned_data.get("email", "")
    phone = form.cleaned_data.get("phone", "")
    subject = form.cleaned_data.get("subject", "").strip()
    message = form.cleaned_data.get("message", "")
    parts = name.split()
    first_name = parts[0] if parts else ""
    last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
    lead = Lead.objects.create(
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        status="new",
        source="Website Contact Form",
        interest=subject,
        notes=message,
    )
    if message:
        LeadNote.objects.create(lead=lead, note=message)
    notification_email = getattr(settings, "ENROLLMENT_NOTIFICATION_EMAIL", "")
    if notification_email:
        body_lines = [
            "New website lead received.",
            f"Name: {name}",
            f"Email: {email}",
            f"Phone: {phone}",
            f"Subject: {subject}",
            "",
            "Message:",
            message,
        ]
        body = "\n".join(body_lines).strip()
        ScheduledEmail.objects.create(
            recipient_email=notification_email,
            subject="New Website Lead",
            body=body,
            scheduled_for=timezone.now(),
            channel="email",
        )
        send_mail("New Website Lead", body, None, [notification_email], fail_silently=True)
    return HttpResponseRedirect(request.META.get("HTTP_REFERER") or reverse("contact_page"))


def register(request):
    if request.method != "POST":
        return HttpResponseRedirect(reverse("login_page"))
    form = StudentRegistrationForm(request.POST)
    if not form.is_valid():
        return HttpResponseRedirect(reverse("login_page"))
    email = form.cleaned_data["email"]
    password = form.cleaned_data["password"]
    User = get_user_model()
    if User.objects.filter(username=email).exists():
        return HttpResponseRedirect(reverse("login_page"))
    user = User.objects.create_user(username=email, email=email, password=password)
    first_name = email.split("@")[0]
    Student.objects.create(user=user, first_name=first_name, email=email)
    return HttpResponseRedirect(reverse("login_page"))


def login_view(request):
    if request.method != "POST":
        return HttpResponseRedirect(reverse("login_page"))
    form = LoginForm(request.POST)
    if not form.is_valid():
        return HttpResponseRedirect(reverse("login_page"))
    email = form.cleaned_data["email"]
    password = form.cleaned_data["password"]
    user = authenticate(request, username=email, password=password)
    if user:
        login(request, user)
    return HttpResponseRedirect(reverse("login_page"))


def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("login_page"))


def enroll_request(request):
    if request.method != "POST":
        return HttpResponseRedirect(reverse("course_page"))
    data = {
        "name": request.POST.get("name", "").strip(),
        "email": request.POST.get("email", "").strip(),
        "phone": request.POST.get("phone", "").strip(),
        "package": request.POST.get("package", "").strip(),
        "preferred_location": request.POST.get("preferred_location", "").strip(),
        "preferred_schedule": request.POST.get("preferred_schedule", "").strip(),
        "notes": request.POST.get("notes", "").strip(),
    }
    if (not data["name"] or not data["email"]) and request.user.is_authenticated:
        student = Student.objects.filter(user=request.user).first()
        if student:
            data["name"] = data["name"] or f"{student.first_name} {student.last_name}".strip()
            data["email"] = data["email"] or student.email
            data["phone"] = data["phone"] or student.phone
    if not data["name"]:
        data["name"] = "Website Visitor"
    if not data["email"]:
        data["email"] = f"visitor+{timezone.now().strftime('%Y%m%d%H%M%S')}@example.com"
    if not data["notes"]:
        data["notes"] = "Auto-captured from pricing Apply Now."
    EnrollmentRequest.objects.create(
        name=data["name"],
        email=data["email"],
        phone=data.get("phone", ""),
        package=data.get("package", ""),
        preferred_location=data.get("preferred_location", ""),
        preferred_schedule=data.get("preferred_schedule", ""),
        notes=data.get("notes", ""),
    )
    Lead.objects.create(
        first_name=data["name"].split()[0],
        last_name=" ".join(data["name"].split()[1:]),
        email=data["email"],
        phone=data.get("phone", ""),
        status="new",
        interest=data.get("package", ""),
        notes=data.get("notes", ""),
    )
    if settings.ENROLLMENT_NOTIFICATION_EMAIL:
        ScheduledEmail.objects.create(
            recipient_email=settings.ENROLLMENT_NOTIFICATION_EMAIL,
            subject="New Enrollment Request",
            body=f"{data['name']} requested {data.get('package','')} {data.get('preferred_location','')}",
            scheduled_for=timezone.now(),
            channel="email",
        )
    return HttpResponseRedirect(reverse("course_details_page"))


def lesson_request(request):
    if request.method != "POST":
        return HttpResponseRedirect(reverse("course_details_page"))
    form = LessonRequestForm(request.POST)
    if not form.is_valid():
        return HttpResponseRedirect(reverse("course_details_page"))
    data = form.cleaned_data
    LessonRequest.objects.create(
        name=data["name"],
        email=data["email"],
        phone=data.get("phone", ""),
        preferred_date=data.get("preferred_date"),
        preferred_time=data.get("preferred_time", ""),
        notes=data.get("notes", ""),
    )
    Lead.objects.create(
        first_name=data["name"].split()[0],
        last_name=" ".join(data["name"].split()[1:]),
        email=data["email"],
        phone=data.get("phone", ""),
        status="new",
        notes=data.get("notes", ""),
    )
    if settings.ENROLLMENT_NOTIFICATION_EMAIL:
        ScheduledEmail.objects.create(
            recipient_email=settings.ENROLLMENT_NOTIFICATION_EMAIL,
            subject="New Lesson Request",
            body=f"{data['name']} requested a lesson on {data.get('preferred_date','')} {data.get('preferred_time','')}",
            scheduled_for=timezone.now(),
            channel="email",
        )
    return HttpResponseRedirect(reverse("course_details_page"))


@login_required
def google_oauth_start(request):
    if not getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", ""):
        messages.error(request, "Google OAuth is not configured (missing client_id).")
        return HttpResponseRedirect("/admin/crm/calendaraccount/")
    if not getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", ""):
        messages.error(request, "Google OAuth is not configured (missing client_secret).")
        return HttpResponseRedirect("/admin/crm/calendaraccount/")
    state = secrets.token_urlsafe(16)
    request.session["google_oauth_state"] = state
    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(settings.GOOGLE_OAUTH_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return HttpResponseRedirect(f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}")


@login_required
def google_oauth_callback(request):
    state = request.GET.get("state")
    code = request.GET.get("code")
    if not code or state != request.session.get("google_oauth_state"):
        return HttpResponseRedirect("/admin/crm/calendaraccount/")
    token_response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    token_data = token_response.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token", "")
    expires_in = token_data.get("expires_in", 0)
    if not access_token:
        return HttpResponseRedirect("/admin/crm/calendaraccount/")
    userinfo = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    ).json()
    email = userinfo.get("email", "")
    CalendarAccount.objects.update_or_create(
        owner=request.user,
        provider="google",
        defaults={
            "email": email,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_expires_at": timezone.now() + timedelta(seconds=expires_in or 0),
            "active": True,
        },
    )
    return HttpResponseRedirect("/admin/crm/calendaraccount/")


@login_required
def outlook_oauth_start(request):
    state = secrets.token_urlsafe(16)
    request.session["outlook_oauth_state"] = state
    params = {
        "client_id": settings.OUTLOOK_OAUTH_CLIENT_ID,
        "redirect_uri": settings.OUTLOOK_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "response_mode": "query",
        "scope": " ".join(settings.OUTLOOK_OAUTH_SCOPES),
        "state": state,
    }
    return HttpResponseRedirect(
        f"https://login.microsoftonline.com/{settings.OUTLOOK_OAUTH_TENANT_ID}/oauth2/v2.0/authorize?{urlencode(params)}"
    )


@login_required
def outlook_oauth_callback(request):
    state = request.GET.get("state")
    code = request.GET.get("code")
    if not code or state != request.session.get("outlook_oauth_state"):
        return HttpResponseRedirect("/admin/crm/calendaraccount/")
    token_response = requests.post(
        f"https://login.microsoftonline.com/{settings.OUTLOOK_OAUTH_TENANT_ID}/oauth2/v2.0/token",
        data={
            "client_id": settings.OUTLOOK_OAUTH_CLIENT_ID,
            "client_secret": settings.OUTLOOK_OAUTH_CLIENT_SECRET,
            "redirect_uri": settings.OUTLOOK_OAUTH_REDIRECT_URI,
            "grant_type": "authorization_code",
            "code": code,
            "scope": " ".join(settings.OUTLOOK_OAUTH_SCOPES),
        },
        timeout=30,
    )
    token_data = token_response.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token", "")
    expires_in = token_data.get("expires_in", 0)
    if not access_token:
        return HttpResponseRedirect("/admin/crm/calendaraccount/")
    profile = requests.get(
        "https://graph.microsoft.com/v1.0/me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    ).json()
    email = profile.get("mail") or profile.get("userPrincipalName") or ""
    CalendarAccount.objects.update_or_create(
        owner=request.user,
        provider="outlook",
        defaults={
            "email": email,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_expires_at": timezone.now() + timedelta(seconds=expires_in or 0),
            "active": True,
        },
    )
    return HttpResponseRedirect("/admin/crm/calendaraccount/")


def calendar_feed(request, token):
    feed = CalendarFeed.objects.filter(token=token, active=True).select_related("student", "instructor").first()
    if not feed:
        raise Http404()
    lessons = Lesson.objects.all()
    if feed.feed_type == "student" and feed.student:
        lessons = lessons.filter(student=feed.student)
    if feed.feed_type == "instructor" and feed.instructor:
        lessons = lessons.filter(instructor=feed.instructor)
    if not feed.include_past:
        lessons = lessons.filter(end_time__gte=timezone.now())
    lessons = lessons.order_by("start_time")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Sams Driving//CRM//EN",
        "CALSCALE:GREGORIAN",
    ]
    for lesson in lessons:
        start = lesson.start_time.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        end = lesson.end_time.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        summary = f"{lesson.lesson_type.title()} Lesson"
        uid = f"lesson-{lesson.id}@samsdriving"
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{timezone.now().astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
                f"DTSTART:{start}",
                f"DTEND:{end}",
                f"SUMMARY:{summary}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    return HttpResponse("\r\n".join(lines), content_type="text/calendar; charset=utf-8")


def stripe_checkout(request, invoice_id):
    invoice = Invoice.objects.select_related("enrollment__student").filter(id=invoice_id).first()
    if not invoice:
        raise Http404()
    stripe.api_key = settings.STRIPE_SECRET_KEY
    customer_email = ""
    if invoice.enrollment and invoice.enrollment.student:
        customer_email = invoice.enrollment.student.email or ""
    session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        customer_email=customer_email or None,
        line_items=[
            {
                "price_data": {
                    "currency": "cad",
                    "product_data": {"name": f"Invoice {invoice.number}"},
                    "unit_amount": int(invoice.total_amount * 100),
                },
                "quantity": 1,
            }
        ],
        success_url=f"{settings.SITE_URL}/crm/stripe/success/{invoice.id}/",
        cancel_url=f"{settings.SITE_URL}/crm/stripe/cancel/{invoice.id}/",
        metadata={"invoice_id": str(invoice.id)},
    )
    invoice.stripe_checkout_session_id = session.id
    invoice.save(update_fields=["stripe_checkout_session_id"])
    return HttpResponseRedirect(session.url)


def stripe_success(request, invoice_id):
    return HttpResponseRedirect(reverse("course_page"))


def stripe_cancel(request, invoice_id):
    return HttpResponseRedirect(reverse("course_page"))


@csrf_exempt
def stripe_webhook(request):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except Exception:
        return JsonResponse({"status": "invalid"}, status=400)
    event_type = event.get("type")
    data_object = event.get("data", {}).get("object", {})
    if event_type == "checkout.session.completed":
        invoice_id = data_object.get("metadata", {}).get("invoice_id")
        payment_intent_id = data_object.get("payment_intent")
        session_id = data_object.get("id")
        _mark_invoice_paid(invoice_id, payment_intent_id, session_id)
    if event_type == "payment_intent.succeeded":
        invoice_id = data_object.get("metadata", {}).get("invoice_id")
        payment_intent_id = data_object.get("id")
        _mark_invoice_paid(invoice_id, payment_intent_id, "")
    return JsonResponse({"status": "ok"})


def _mark_invoice_paid(invoice_id, payment_intent_id, session_id):
    if not invoice_id:
        return
    invoice = Invoice.objects.filter(id=invoice_id).first()
    if not invoice:
        return
    invoice.status = "paid"
    if payment_intent_id:
        invoice.stripe_payment_intent_id = payment_intent_id
    if session_id:
        invoice.stripe_checkout_session_id = session_id
    invoice.save(update_fields=["status", "stripe_payment_intent_id", "stripe_checkout_session_id"])
    if payment_intent_id:
        existing = Payment.objects.filter(stripe_payment_intent_id=payment_intent_id).first()
        if not existing:
            Payment.objects.create(
                invoice=invoice,
                amount=invoice.total_amount,
                paid_at=timezone.now(),
                method="stripe",
                stripe_payment_intent_id=payment_intent_id,
                status="completed",
            )


@login_required
def notifications_unread_count(request):
    if not (request.user.is_active and request.user.is_staff):
        return JsonResponse({"detail": "forbidden"}, status=403)
    unread_count = NotificationReceipt.objects.filter(
        user=request.user, notification__active=True, read_at__isnull=True
    ).count()
    return JsonResponse({"unread_count": unread_count})


@login_required
def notifications_list(request):
    if not (request.user.is_active and request.user.is_staff):
        return JsonResponse({"detail": "forbidden"}, status=403)
    try:
        limit = int(request.GET.get("limit") or 10)
    except ValueError:
        limit = 10
    limit = max(1, min(limit, 50))
    receipts = (
        NotificationReceipt.objects.filter(user=request.user, notification__active=True)
        .select_related("notification")
        .order_by("-notification__created_at", "-id")[:limit]
    )
    items = []
    for receipt in receipts:
        notification = receipt.notification
        items.append(
            {
                "receipt_id": receipt.id,
                "title": notification.title,
                "body": notification.body,
                "level": notification.level,
                "link_url": notification.link_url,
                "created_at": notification.created_at.isoformat() if notification.created_at else None,
                "read_at": receipt.read_at.isoformat() if receipt.read_at else None,
            }
        )
    return JsonResponse({"items": items})


@login_required
def notifications_mark_read(request, receipt_id):
    if not (request.user.is_active and request.user.is_staff):
        return JsonResponse({"detail": "forbidden"}, status=403)
    if request.method != "POST":
        return JsonResponse({"detail": "method_not_allowed"}, status=405)
    receipt = get_object_or_404(NotificationReceipt, id=receipt_id, user=request.user)
    if not receipt.read_at:
        receipt.read_at = timezone.now()
        receipt.save(update_fields=["read_at"])
    return JsonResponse({"ok": True, "read_at": receipt.read_at.isoformat() if receipt.read_at else None})


@login_required
def notifications_mark_all_read(request):
    if not (request.user.is_active and request.user.is_staff):
        return JsonResponse({"detail": "forbidden"}, status=403)
    if request.method != "POST":
        return JsonResponse({"detail": "method_not_allowed"}, status=405)
    now = timezone.now()
    updated = (
        NotificationReceipt.objects.filter(user=request.user, notification__active=True, read_at__isnull=True).update(
            read_at=now
        )
    )
    return JsonResponse({"ok": True, "updated": updated})
