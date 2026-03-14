import stripe
import json
import uuid
import logging
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from urllib.parse import urlencode
from urllib import request as urlrequest
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db.models import Q
from django.db import transaction, IntegrityError
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import get_template
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .forms import (
    LeadForm,
    StudentRegistrationForm,
    LoginForm,
    EnrollmentRequestForm,
    LessonRequestForm,
    BlogCommentForm,
)
from .models import (
    Lead,
    LeadNote,
    Student,
    Invoice,
    Payment,
    CalendarFeed,
    Lesson,
    EnrollmentRequest,
    LessonRequest,
    ScheduledEmail,
    Notification,
    NotificationReceipt,
    Blog,
    BlogComment,
    Testimonial,
    Course,
    CourseSession,
    Enrollment,
    CalendarAccount,
    HomeHeroSlide,
)


logger = logging.getLogger(__name__)

def _course_total_with_hst(course):
    def _parse_decimal(value):
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        if isinstance(value, str):
            cleaned = value.strip().replace("$", "").replace(",", "")
            for token in ("+HST", "HST"):
                cleaned = cleaned.replace(token, "")
            cleaned = cleaned.strip()
            if not cleaned:
                return None
            return Decimal(cleaned)
        return None

    try:
        fees_total = None
        if hasattr(course, "fees_calc"):
            fees_total = _parse_decimal((course.fees_calc or {}).get("total"))
        if fees_total is not None:
            return fees_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        pass

    base = Decimal(getattr(course, "price", 0) or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    hst_amount = (base * Decimal("0.13")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return (base + hst_amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _queue_and_send_email(*, recipient_email, subject, body, to_lead=None, to_student=None):
    if not recipient_email:
        return 0
    scheduled = ScheduledEmail.objects.create(
        recipient_email=recipient_email,
        subject=subject,
        body=body,
        scheduled_for=timezone.now(),
        channel="email",
        to_lead=to_lead,
        to_student=to_student,
        status="scheduled",
    )
    try:
        html_message = body if body.strip().startswith("<") else None
        send_mail(
            subject,
            body if not html_message else "",
            getattr(settings, "DEFAULT_FROM_EMAIL", None),
            [recipient_email],
            fail_silently=False,
            html_message=html_message,
        )
    except Exception as exc:
        scheduled.last_error = str(exc)
        scheduled.save(update_fields=["last_error"])
        logger.exception("Email send failed (queued for retry): %s", subject)
        return 0
    scheduled.status = "sent"
    scheduled.sent_at = timezone.now()
    scheduled.last_error = ""
    scheduled.save(update_fields=["status", "sent_at", "last_error"])
    return 1


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
    courses = Course.objects.filter(active=True).exclude(slug="").order_by("display_order", "name")
    try:
        hero_slides = HomeHeroSlide.objects.filter(is_active=True).order_by("display_order", "-updated_at")[:10]
    except Exception:
        hero_slides = []
    return render(
        request,
        "index.html",
        {"home_blogs": home_blogs, "testimonials": testimonials, "courses": courses, "hero_slides": hero_slides},
    )


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
    courses = Course.objects.filter(active=True).exclude(slug="").order_by("display_order", "name")
    return render(request, "course.html", {"courses": courses})


def course_details_page(request, course_slug=None):
    if not course_slug:
        course = Course.objects.filter(active=True).exclude(slug="").order_by("display_order", "name").first()
        if not course:
            raise Http404()
    else:
        course = get_object_or_404(Course, slug=course_slug, active=True)

    other_courses = Course.objects.filter(active=True).exclude(pk=course.pk).order_by("display_order", "name")[:6]
    return render(
        request,
        "course-details.html",
        {"course": course, "course_slug": course.slug, "other_courses": other_courses},
    )


def enroll_page(request, course_slug):
    course = get_object_or_404(Course, slug=course_slug, active=True)
    return render(request, "enroll.html", {"course": course, "course_slug": course.slug})


def process_enrollment(request):
    if request.method != "POST":
        return HttpResponseRedirect(reverse("course_page"))
    
    course_slug = request.POST.get("course_slug")
    if not course_slug:
        raise Http404()
    course = get_object_or_404(Course, slug=course_slug, active=True)
        
    first_name = request.POST.get("first_name", "").strip()
    last_name = request.POST.get("last_name", "").strip()
    email = request.POST.get("email", "").strip()
    phone = request.POST.get("phone", "").strip()
    address = request.POST.get("address", "").strip()
    city = request.POST.get("city", "").strip()
    province = request.POST.get("province", "").strip()
    postal_code = request.POST.get("postal_code", "").strip()
    notes = request.POST.get("notes", "").strip()
    
    # Create or update student
    student = None
    if request.user.is_authenticated:
        student = Student.objects.filter(user=request.user).first()
        
    if not student:
        # Check by email
        student = Student.objects.filter(email=email).first()
        
    if not student:
        # Create new student (without user account for now)
        student = Student.objects.create(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            address_line1=address,
            city=city,
            province=province,
            postal_code=postal_code,
        )
    
    # Create Enrollment Request (for admin tracking)
    EnrollmentRequest.objects.create(
        name=f"{first_name} {last_name}",
        email=email,
        phone=phone,
        package=course.enroll_package or course.title,
        preferred_location=f"{city}, {province}",
        notes=notes,
    )
    
    # Create Lead
    Lead.objects.create(
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        status="new",
        interest=course.title,
        notes=notes,
    )
    
    # Create Enrollment record (pending)
    # We need a CourseSession, but for now we might not have one selected.
    # Let's check if we can create an Enrollment without a session or pick a default/dummy one.
    # The Enrollment model requires a session.
    # For simplicity, we'll try to find an open session for this course type or create a placeholder.
    # Or, given the constraints, we might skip Enrollment creation and go straight to Invoice 
    # if Invoice doesn't strictly require Enrollment (let's check Invoice model).
    # Invoice requires Enrollment.
    
    # So we need a Course and CourseSession in DB matching the catalog.
    # This might be a bit complex if DB is empty.
    # Let's try to find or create a placeholder Course and Session.
    
    db_session = CourseSession.objects.filter(course=course, enrollment_open=True).first()
    if not db_session:
        db_session = CourseSession.objects.create(
            course=course,
            start_date=timezone.now().date(),
            location="Online/TBD",
            delivery_mode="online" if "online" in (course.session or "").lower() else "in_class"
        )
        
    enrollment = Enrollment.objects.create(
        student=student,
        session=db_session,
        status="pending"
    )
    
    # Create Invoice
    import random
    total_amount = _course_total_with_hst(course)
    
    invoice = None
    max_retries = 5
    for _ in range(max_retries):
        invoice_number = f"INV-{timezone.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
        if not Invoice.objects.filter(number=invoice_number).exists():
            try:
                with transaction.atomic():
                    invoice = Invoice.objects.create(
                        enrollment=enrollment,
                        number=invoice_number,
                        issue_date=timezone.now().date(),
                        total_amount=total_amount,
                        status="draft",
                        notes=f"Enrollment for {course.title}"
                    )
                break
            except IntegrityError:
                continue
            except Exception:
                continue
    
    if not invoice:
        # Fallback to UUID if random fails repeatedly
        import uuid
        invoice_number = f"INV-{uuid.uuid4().hex[:12].upper()}"
        invoice = Invoice.objects.create(
            enrollment=enrollment,
            number=invoice_number,
            issue_date=timezone.now().date(),
            total_amount=total_amount,
            status="draft",
            notes=f"Enrollment for {course.title}"
        )
    
    payment_method = request.POST.get("payment_method", "stripe")
    if payment_method == "pay_later":
        student_name = f"{first_name} {last_name}".strip() or "Student"
        course_name = course.title
        amount_due = f"{invoice.total_amount:.2f}"

        if student and student.email:
            user_subject = "Enrollment Received (Pay in Office) - Sams Driving School"
            user_body = (
                f"<h2>Enrollment Received</h2>"
                f"<p>Hi {student_name},</p>"
                f"<p>Thanks for enrolling in <strong>{course_name}</strong>.</p>"
                f"<p>You selected <strong>Pay in Office / Pay Later</strong>. Your enrollment is received and pending payment.</p>"
                f"<h3>Invoice</h3>"
                f"<ul>"
                f"<li><strong>Invoice #:</strong> {invoice.number}</li>"
                f"<li><strong>Amount Due:</strong> ${amount_due}</li>"
                f"</ul>"
                f"<p>To complete payment and confirm your lesson time, please call <a href=\"tel:+16478891708\">+1 (647) 889-1708</a>.</p>"
                f"<p>Regards,<br/>Sams Driving School</p>"
            )
            exists = ScheduledEmail.objects.filter(
                recipient_email=student.email, subject=user_subject, body=user_body, channel="email"
            ).exclude(status="cancelled").exists()
            if not exists:
                _queue_and_send_email(recipient_email=student.email, subject=user_subject, body=user_body, to_student=student)

        admin_email = getattr(settings, "ENROLLMENT_NOTIFICATION_EMAIL", "")
        if admin_email:
            admin_subject = f"New Pay-in-Office Enrollment - Invoice {invoice.number}"
            admin_body = (
                f"<h2>New Enrollment (Pay in Office)</h2>"
                f"<ul>"
                f"<li><strong>Student:</strong> {student_name}</li>"
                f"<li><strong>Email:</strong> {student.email if student else email}</li>"
                f"<li><strong>Course:</strong> {course_name}</li>"
                f"<li><strong>Invoice #:</strong> {invoice.number}</li>"
                f"<li><strong>Amount Due:</strong> ${amount_due}</li>"
                f"</ul>"
            )
            exists = ScheduledEmail.objects.filter(
                recipient_email=admin_email, subject=admin_subject, body=admin_body, channel="email"
            ).exclude(status="cancelled").exists()
            if not exists:
                _queue_and_send_email(recipient_email=admin_email, subject=admin_subject, body=admin_body)

        return render(request, "enroll_success_pay_later.html", {
            "invoice": invoice, 
            "course": course,
            "student_name": student_name
        })
    
    # Redirect to Stripe Checkout
    return HttpResponseRedirect(reverse("stripe_checkout", args=[invoice.id]))


def requests_get_or_create_course(course_data):
    # Helper to map catalog data to DB model
    from .models import Course
    # We'll map by name
    course, created = Course.objects.get_or_create(
        name=course_data["title"],
        defaults={
            "price": float(course_data["price_display"]),
            "course_type": "bde" if "BDE" in course_data["title"] else "refresher",
            "summary": course_data.get("summary", "") or ""
        }
    )
    return course, created


def blog_grid_right_page(request):
    blogs = Blog.objects.filter(is_published=True).order_by("-published_at")
    q = (request.GET.get("q") or "").strip()
    category_slug = (request.GET.get("category") or "").strip()
    tag_slug = (request.GET.get("tag") or "").strip()
    if q:
        blogs = blogs.filter(Q(title__icontains=q) | Q(summary__icontains=q) | Q(content__icontains=q))

    blog_field_names = {f.name for f in Blog._meta.get_fields()}
    categories = []
    tags = []
    if "categories" in blog_field_names:
        category_model = Blog._meta.get_field("categories").related_model
        categories = category_model.objects.order_by("name")
        if category_slug:
            blogs = blogs.filter(categories__slug=category_slug)
    if "tags" in blog_field_names:
        tag_model = Blog._meta.get_field("tags").related_model
        tags = tag_model.objects.order_by("name")
        if tag_slug:
            blogs = blogs.filter(tags__slug=tag_slug)
    latest_blogs = blogs[:3]
    comments = (
        BlogComment.objects.filter(is_approved=True, blog__is_published=True)
        .select_related("blog")
        .order_by("-created_at")[:4]
    )
    return render(
        request,
        "blogs.html",
        {
            "blogs": blogs.distinct(),
            "latest_blogs": latest_blogs,
            "categories": categories,
            "tags": tags,
            "comments": comments,
            "q": q,
            "category": category_slug,
            "tag": tag_slug,
        },
    )


def blog_details_right_page(request, slug):
    blog = get_object_or_404(Blog, slug=slug, is_published=True)
    latest_blogs = (
        Blog.objects.filter(is_published=True).exclude(pk=blog.pk).order_by("-published_at")[:3]
    )
    comments = BlogComment.objects.filter(blog=blog, is_approved=True).order_by("-created_at")
    recent_comments = (
        BlogComment.objects.filter(is_approved=True, blog__is_published=True)
        .select_related("blog")
        .order_by("-created_at")[:6]
    )
    comment_form = BlogCommentForm()
    return render(
        request,
        "blog-details.html",
        {
            "blog": blog,
            "latest_blogs": latest_blogs,
            "comments": comments,
            "recent_comments": recent_comments,
            "comment_form": comment_form,
        },
    )


def blog_comment_create(request, slug):
    blog = get_object_or_404(Blog, slug=slug, is_published=True)
    if request.method != "POST":
        return HttpResponseRedirect(reverse("blog_details", args=[blog.slug]))

    form = BlogCommentForm(request.POST)
    if form.is_valid():
        BlogComment.objects.create(
            blog=blog,
            name=form.cleaned_data["name"],
            email=form.cleaned_data.get("email") or "",
            body=form.cleaned_data["body"],
            is_approved=True,
        )
        return HttpResponseRedirect(f"{reverse('blog_details', args=[blog.slug])}#comments")

    latest_blogs = (
        Blog.objects.filter(is_published=True).exclude(pk=blog.pk).order_by("-published_at")[:3]
    )
    comments = BlogComment.objects.filter(blog=blog, is_approved=True).order_by("-created_at")
    recent_comments = (
        BlogComment.objects.filter(is_approved=True, blog__is_published=True)
        .select_related("blog")
        .order_by("-created_at")[:6]
    )
    return render(
        request,
        "blog-details.html",
        {
            "blog": blog,
            "latest_blogs": latest_blogs,
            "comments": comments,
            "recent_comments": recent_comments,
            "comment_form": form,
        },
    )


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

    # Send acknowledgement to lead (HTML)
    if email:
        ack_subject = "We have received your message"
        ack_context = {
            "first_name": first_name,
            "subject": subject,
            "message": message,
        }
        ack_html = get_template("emails/contact_ack.html").render(ack_context)
        _queue_and_send_email(recipient_email=email, subject=ack_subject, body=ack_html, to_lead=lead)

    notification_email = getattr(settings, "ENROLLMENT_NOTIFICATION_EMAIL", "")
    if notification_email:
        admin_subject = "New Website Lead"
        admin_context = {
            "name": name,
            "email": email,
            "phone": phone,
            "subject": subject,
            "message": message,
        }
        admin_html = get_template("emails/contact_admin_notification.html").render(admin_context)
        _queue_and_send_email(recipient_email=notification_email, subject=admin_subject, body=admin_html)
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
    username = form.cleaned_data["username"]
    password = form.cleaned_data["password"]
    user = authenticate(request, username=username, password=password)
    if user:
        login(request, user)
        if user.is_staff or user.is_superuser:
            return HttpResponseRedirect("/admin/")
        return HttpResponseRedirect(reverse("home"))
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
        _queue_and_send_email(
            recipient_email=settings.ENROLLMENT_NOTIFICATION_EMAIL,
            subject="New Enrollment Request",
            body=f"{data['name']} requested {data.get('package','')} {data.get('preferred_location','')}",
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
        _queue_and_send_email(
            recipient_email=settings.ENROLLMENT_NOTIFICATION_EMAIL,
            subject="New Lesson Request",
            body=f"{data['name']} requested a lesson on {data.get('preferred_date','')} {data.get('preferred_time','')}",
        )
    return HttpResponseRedirect(reverse("course_details_page"))


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
        success_url=f"{settings.SITE_URL.rstrip('/')}/crm/stripe/success/{invoice.id}/?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.SITE_URL.rstrip('/')}/crm/stripe/cancel/{invoice.id}/",
        metadata={"invoice_id": str(invoice.id)},
    )
    invoice.stripe_checkout_session_id = session.id
    invoice.save(update_fields=["stripe_checkout_session_id"])
    return HttpResponseRedirect(session.url)


def stripe_success(request, invoice_id):
    session_id = (request.GET.get("session_id") or "").strip()
    if session_id and getattr(settings, "STRIPE_SECRET_KEY", ""):
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            session = stripe.checkout.Session.retrieve(session_id)
            session_invoice_id = (session.get("metadata") or {}).get("invoice_id")
            payment_status = session.get("payment_status")
            payment_intent_id = session.get("payment_intent")
            if session_invoice_id and str(session_invoice_id) == str(invoice_id) and payment_status == "paid":
                _mark_invoice_paid(invoice_id, payment_intent_id, session_id)
        except Exception:
            logger.exception("Stripe success handler failed for invoice_id=%s", invoice_id)
    return HttpResponseRedirect(reverse("course_page"))


def stripe_cancel(request, invoice_id):
    invoice = Invoice.objects.select_related("enrollment__session__course").filter(id=invoice_id).first()
    if invoice and invoice.enrollment and invoice.enrollment.session and invoice.enrollment.session.course:
        course_slug = invoice.enrollment.session.course.slug
        if course_slug:
            return HttpResponseRedirect(reverse("enroll_page", args=[course_slug]))
            
    return HttpResponseRedirect(reverse("course_page"))


@csrf_exempt
def stripe_webhook(request):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except Exception:
        logger.exception("Stripe webhook signature verification failed")
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
    if not payment_intent_id:
        return

    Payment.objects.get_or_create(
        stripe_payment_intent_id=payment_intent_id,
        defaults={
            "invoice": invoice,
            "amount": invoice.total_amount,
            "paid_at": timezone.now(),
            "method": "stripe",
            "status": "completed",
        },
    )

    student = invoice.enrollment.student
    course_name = invoice.enrollment.session.course.name if invoice.enrollment and invoice.enrollment.session else "Driving Course"

    if student and student.email:
        user_subject = "Payment Confirmation - Sams Driving School"
        user_context = {
            "student_name": f"{student.first_name} {student.last_name}".strip(),
            "course_name": course_name,
            "invoice_number": invoice.number,
            "amount": f"{invoice.total_amount:.2f}",
        }
        user_html = get_template("emails/purchase_success_user.html").render(user_context)
        exists = ScheduledEmail.objects.filter(
            recipient_email=student.email, subject=user_subject, body=user_html, channel="email"
        ).exclude(status="cancelled").exists()
        if not exists:
            _queue_and_send_email(recipient_email=student.email, subject=user_subject, body=user_html, to_student=student)

    admin_email = getattr(settings, "ENROLLMENT_NOTIFICATION_EMAIL", "")
    if admin_email:
        admin_subject = f"New Payment Received - Invoice {invoice.number}"
        admin_context = {
            "student_name": f"{student.first_name} {student.last_name}".strip() if student else "Unknown",
            "student_email": student.email if student else "Unknown",
            "invoice_number": invoice.number,
            "amount": f"{invoice.total_amount:.2f}",
            "course_name": course_name,
        }
        admin_html = get_template("emails/purchase_success_admin.html").render(admin_context)
        exists = ScheduledEmail.objects.filter(
            recipient_email=admin_email, subject=admin_subject, body=admin_html, channel="email"
        ).exclude(status="cancelled").exists()
        if not exists:
            _queue_and_send_email(recipient_email=admin_email, subject=admin_subject, body=admin_html)


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

def gallery(request):
    return render(request, "gallery.html")


def _settings_absolute_uri(request, path):
    site_url = getattr(settings, "SITE_URL", "") or ""
    if site_url:
        return f"{site_url.rstrip('/')}{path}"
    return request.build_absolute_uri(path)


@login_required
def google_calendar_connect(request):
    client_id = getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "") or ""
    if not client_id:
        messages.error(
            request,
            "Google OAuth client is not configured. Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET (or GOOGLE_OAUTH_CLIENT_SECRET_FILE).",
        )
        return HttpResponseRedirect("/admin/")

    redirect_uri = _settings_absolute_uri(request, reverse("google_calendar_callback"))
    state = uuid.uuid4().hex
    request.session["google_oauth_state"] = state

    auth_uri = getattr(settings, "GOOGLE_OAUTH_AUTH_URI", "") or "https://accounts.google.com/o/oauth2/auth"
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(getattr(settings, "GOOGLE_OAUTH_SCOPES", []) or ["https://www.googleapis.com/auth/calendar"]),
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return HttpResponseRedirect(f"{auth_uri}?{urlencode(params)}")


@login_required
def google_calendar_callback(request):
    error = request.GET.get("error") or ""
    if error:
        messages.error(request, f"Google OAuth failed: {error}")
        return HttpResponseRedirect("/admin/")

    state = request.GET.get("state") or ""
    if not state or state != (request.session.get("google_oauth_state") or ""):
        return JsonResponse({"detail": "invalid_state"}, status=400)

    code = request.GET.get("code") or ""
    if not code:
        return JsonResponse({"detail": "missing_code"}, status=400)

    client_id = getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "") or ""
    client_secret = getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "") or ""
    token_uri = getattr(settings, "GOOGLE_OAUTH_TOKEN_URI", "") or "https://oauth2.googleapis.com/token"
    if not (client_id and client_secret):
        return JsonResponse({"detail": "oauth_not_configured"}, status=500)

    redirect_uri = _settings_absolute_uri(request, reverse("google_calendar_callback"))
    payload = urlencode(
        {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")

    try:
        token_request = urlrequest.Request(
            token_uri,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urlrequest.urlopen(token_request, timeout=30) as response:
            token_data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return JsonResponse({"detail": f"token_exchange_failed: {exc}"}, status=502)

    access_token = token_data.get("access_token") or ""
    refresh_token = token_data.get("refresh_token") or ""
    expires_in = token_data.get("expires_in")
    if not access_token:
        return JsonResponse({"detail": "missing_access_token"}, status=502)

    token_expires_at = None
    try:
        if expires_in is not None:
            token_expires_at = timezone.now() + timedelta(seconds=int(expires_in))
    except Exception:
        token_expires_at = None

    account = CalendarAccount.objects.filter(owner=request.user, provider="google").order_by("-created_at").first()
    if account:
        account.access_token = access_token
        if refresh_token:
            account.refresh_token = refresh_token
        account.token_expires_at = token_expires_at
        account.active = True
        account.save(update_fields=["access_token", "refresh_token", "token_expires_at", "active"])
    else:
        CalendarAccount.objects.create(
            owner=request.user,
            provider="google",
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
            active=True,
        )

    messages.success(request, "Google Calendar connected.")
    return HttpResponseRedirect("/admin/")


@login_required
def google_calendar_disconnect(request):
    if request.method != "POST":
        return JsonResponse({"detail": "method_not_allowed"}, status=405)
    CalendarAccount.objects.filter(owner=request.user, provider="google").update(active=False)
    messages.success(request, "Google Calendar disconnected.")
    return JsonResponse({"ok": True})
