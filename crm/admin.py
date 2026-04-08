import csv
import json
import uuid
from urllib import request as urlrequest
from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from utils.gcalendar import get_calendar_service, upsert_event
from .models import (
    Lead,
    LeadNote,
    LeadTask,
    EnrollmentRequest,
    Student,
    StudentDocument,
    Course,
    CourseSession,
    Enrollment,
    StudentModuleProgress,
    Instructor,
    Vehicle,
    Classroom,
    Lesson,
    LessonAttendance,
    Invoice,
    PaymentPlan,
    PaymentSchedule,
    Payment,
    Certificate,
    MinistrySubmission,
    CommunicationTemplate,
    CommunicationLog,
    ScheduledEmail,
    ConflictDetection,
    ReminderLog,
    CalendarFeed,
    CalendarAccount,
    StaffProfile,
    Notification,
    NotificationReceipt,
    HomeHeroSlide,
    Blog,
    BlogComment,
    Testimonial,
    Event,
)


class ExportCsvMixin:
    actions = ["export_as_csv"]

    def export_as_csv(self, request, queryset):
        meta = self.model._meta
        field_names = [field.name for field in meta.fields]
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f"attachment; filename={meta.model_name}.csv"
        writer = csv.writer(response)
        writer.writerow(field_names)
        for obj in queryset:
            writer.writerow([getattr(obj, field) for field in field_names])
        return response

    export_as_csv.short_description = "Export selected to CSV"


def _pdf_escape(value):
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_simple_pdf(lines):
    content_lines = []
    y = 720
    for line in lines:
        content_lines.append(f"1 0 0 1 72 {y} Tm ({_pdf_escape(line)}) Tj")
        y -= 24
    content_stream = "BT /F1 18 Tf 0 0 0 rg " + " ".join(content_lines) + " ET"
    content_bytes = content_stream.encode("utf-8")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(content_bytes)).encode("utf-8") + b" >>\nstream\n" + content_bytes + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    parts = [b"%PDF-1.4\n"]
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(sum(len(part) for part in parts))
        parts.append(f"{index} 0 obj\n".encode("utf-8"))
        parts.append(obj)
        parts.append(b"\nendobj\n")
    xref_start = sum(len(part) for part in parts)
    xref_lines = [f"xref\n0 {len(objects) + 1}\n".encode("utf-8")]
    xref_lines.append(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        xref_lines.append(f"{offset:010d} 00000 n \n".encode("utf-8"))
    trailer = f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode(
        "utf-8"
    )
    return b"".join(parts + xref_lines + [trailer])


def _certificate_number(enrollment):
    return f"CERT-{enrollment.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}"


# --- Inlines ---

class LeadNoteInline(admin.TabularInline):
    model = LeadNote
    extra = 1

class LeadTaskInline(admin.TabularInline):
    model = LeadTask
    extra = 1

class StudentDocumentInline(admin.TabularInline):
    model = StudentDocument
    extra = 0

class StudentModuleProgressInline(admin.TabularInline):
    model = StudentModuleProgress
    extra = 0
    readonly_fields = ("completed_at", "updated_at")

class MinistrySubmissionInline(admin.TabularInline):
    model = MinistrySubmission
    extra = 0
    readonly_fields = ("submitted_at",)

# class CertificateInline(admin.TabularInline):
#     model = Certificate
#     extra = 0
#     readonly_fields = ("issued_at", "submitted_at")

class PaymentScheduleInline(admin.TabularInline):
    model = PaymentSchedule
    extra = 0

class LessonAttendanceInline(admin.TabularInline):
    model = LessonAttendance
    extra = 0

class ConflictDetectionInline(admin.TabularInline):
    model = ConflictDetection
    fk_name = "lesson"
    extra = 0
    readonly_fields = ("detected_at",)

class ReminderLogInline(admin.TabularInline):
    model = ReminderLog
    extra = 0
    readonly_fields = ("created_at",)

class BlogCommentInline(admin.TabularInline):
    model = BlogComment
    extra = 0


# --- Admin Registrations ---

@admin.register(Lead)
class LeadAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("first_name", "last_name", "email", "phone", "status", "assigned_to", "created_at")
    list_filter = ("status", "assigned_to", "created_at")
    search_fields = ("first_name", "last_name", "email", "phone", "source", "interest")
    inlines = [LeadNoteInline, LeadTaskInline]


@admin.register(Student)
class StudentAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("first_name", "last_name", "email", "phone", "preferred_location", "created_at")
    search_fields = ("first_name", "last_name", "email", "phone")
    inlines = [StudentDocumentInline]


class CourseAdminForm(forms.ModelForm):
    promotion_savings = forms.CharField(required=False, label="Offer / Save Badge")

    class Meta:
        model = Course
        fields = ("name", "slug", "summary", "course_type", "price", "active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        obj = getattr(self, "instance", None)
        if obj:
            fees = obj.fees if isinstance(obj.fees, dict) else {}
            current = fees.get("promotion_savings", "")
            if current and current != "0$ +HST":
                self.fields["promotion_savings"].initial = current

    def save(self, commit=True):
        obj = super().save(commit=False)
        promo = (self.cleaned_data.get("promotion_savings") or "").strip()
        fees = obj.fees if isinstance(obj.fees, dict) else {}
        if promo:
            fees["promotion_savings"] = promo
        else:
            fees.pop("promotion_savings", None)
        obj.fees = fees

        if commit:
            obj.save()
            self.save_m2m()
        return obj



@admin.register(Course)
class CourseAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("name", "slug", "course_type", "price", "active")
    list_filter = ("course_type", "active")
    form = CourseAdminForm
    search_fields = ("name", "slug", "summary")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(CourseSession)
class CourseSessionAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("course", "location", "delivery_mode", "start_date", "capacity", "enrollment_open")
    list_filter = ("delivery_mode", "location", "enrollment_open")


@admin.register(Enrollment)
class EnrollmentAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("student", "session", "status", "enrolled_at", "balance")
    list_filter = ("status",)
    search_fields = ("student__first_name", "student__last_name")
    actions = ["submit_ministry"]
    inlines = [StudentModuleProgressInline, MinistrySubmissionInline]

    def submit_ministry(self, request, queryset):
        submitted = 0
        for enrollment in queryset.select_related("student", "session__course"):
            submission, _ = MinistrySubmission.objects.get_or_create(enrollment=enrollment)
            student_name = f"{enrollment.student.first_name} {enrollment.student.last_name}".strip()
            course_name = enrollment.session.course.name if enrollment.session and enrollment.session.course else ""
            csv_content = "enrollment_id,student,course,submitted_at\n"
            csv_content += f"{enrollment.id},{student_name},{course_name},{timezone.now().isoformat()}\n"
            submission.file.save(
                f"ministry-submission-{enrollment.id}.csv", ContentFile(csv_content.encode("utf-8")), save=False
            )
            submission.status = "submitted"
            submission.submitted_at = timezone.now()
            submission.external_reference = submission.external_reference or f"SUB-{enrollment.id}"
            submission.save()
            submitted += 1
        if submitted:
            self.message_user(request, f"Submitted {submitted} enrollment(s).", level=messages.SUCCESS)


@admin.register(EnrollmentRequest)
class EnrollmentRequestAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("name", "email", "phone", "package", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("name", "email", "phone")


@admin.register(Instructor)
class InstructorAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("user", "phone", "license_number", "active")


@admin.register(Blog)
class BlogAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("title", "author_name", "is_published", "published_at", "updated_at")
    list_filter = ("is_published", "published_at")
    search_fields = ("title", "summary", "content", "author_name")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [BlogCommentInline]


@admin.register(HomeHeroSlide)
class HomeHeroSlideAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("title_line_1", "is_active", "display_order", "updated_at")
    list_filter = ("is_active", "updated_at")
    search_fields = ("title_line_1", "title_line_2", "title_line_3", "button_text", "button_url")
    list_editable = ("is_active", "display_order")


# BlogTag hidden (less necessary)


@admin.register(Testimonial)
class TestimonialAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("name", "role", "rating", "is_published", "display_order", "updated_at")
    list_filter = ("is_published", "rating")
    search_fields = ("name", "role", "quote")
    list_editable = ("is_published", "display_order")


@admin.register(Vehicle)
class VehicleAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("name", "make", "model", "year", "plate_number", "active", "location")
    list_filter = ("active", "location")


@admin.register(Classroom)
class ClassroomAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("name", "location", "capacity")


@admin.register(Lesson)
class LessonAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("student", "lesson_type", "start_time", "end_time", "status", "instructor")
    list_filter = ("lesson_type", "status")
    search_fields = ("student__first_name", "student__last_name")
    actions = ["detect_conflicts"]
    inlines = [LessonAttendanceInline, ConflictDetectionInline, ReminderLogInline]

    def detect_conflicts(self, request, queryset):
        created = 0
        for lesson in queryset.select_related("instructor", "vehicle", "classroom"):
            overlaps = Lesson.objects.filter(start_time__lt=lesson.end_time, end_time__gt=lesson.start_time).exclude(
                pk=lesson.pk
            )
            if lesson.instructor:
                conflicts = overlaps.filter(instructor=lesson.instructor)
                for conflict in conflicts:
                    _, was_created = ConflictDetection.objects.get_or_create(
                        lesson=lesson,
                        conflict_type="instructor",
                        conflicting_lesson=conflict,
                    )
                    if was_created:
                        created += 1
            if lesson.vehicle:
                conflicts = overlaps.filter(vehicle=lesson.vehicle)
                for conflict in conflicts:
                    _, was_created = ConflictDetection.objects.get_or_create(
                        lesson=lesson,
                        conflict_type="vehicle",
                        conflicting_lesson=conflict,
                    )
                    if was_created:
                        created += 1
            if lesson.classroom:
                conflicts = overlaps.filter(classroom=lesson.classroom)
                for conflict in conflicts:
                    _, was_created = ConflictDetection.objects.get_or_create(
                        lesson=lesson,
                        conflict_type="classroom",
                        conflicting_lesson=conflict,
                    )
                    if was_created:
                        created += 1
        if created:
            self.message_user(request, f"Detected {created} conflict(s).", level=messages.SUCCESS)


@admin.register(Invoice)
class InvoiceAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("number", "enrollment", "issue_date", "due_date", "total_amount", "status", "square_payment_link_id", "square_order_id")
    list_filter = ("status",)
    search_fields = ("number",)
    actions = ["create_square_checkout"]

    def create_square_checkout(self, request, queryset):
        if not getattr(settings, "SQUARE_ACCESS_TOKEN", "") or not getattr(settings, "SQUARE_LOCATION_ID", ""):
            self.message_user(request, "Square settings are not configured.", level=messages.ERROR)
            return

        base_url = "https://connect.squareup.com"
        if getattr(settings, "SQUARE_ENVIRONMENT", "production").lower() == "sandbox":
            base_url = "https://connect.squareupsandbox.com"

        checkout_links = []
        for invoice in queryset:
            success_url = f"{settings.SITE_URL.rstrip('/')}{reverse('square_success_public', args=[invoice.id])}"
            cents = int((invoice.total_amount or 0) * 100)
            payload = {
                "idempotency_key": str(uuid.uuid4()),
                "quick_pay": {
                    "name": f"Invoice {invoice.number}",
                    "price_money": {"amount": cents, "currency": "CAD"},
                    "location_id": settings.SQUARE_LOCATION_ID,
                },
                "checkout_options": {"redirect_url": success_url},
                "description": f"Invoice {invoice.number} (id={invoice.id})",
            }

            customer_email = ""
            if invoice.enrollment and invoice.enrollment.student:
                customer_email = invoice.enrollment.student.email or ""
            if customer_email:
                payload["pre_populated_data"] = {"buyer_email": customer_email}

            req = urlrequest.Request(
                f"{base_url}/v2/online-checkout/payment-links",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {settings.SQUARE_ACCESS_TOKEN}",
                    "Content-Type": "application/json",
                    "Square-Version": getattr(settings, "SQUARE_VERSION", "2022-08-17"),
                },
                method="POST",
            )
            try:
                with urlrequest.urlopen(req, timeout=20) as resp:
                    raw = resp.read().decode("utf-8")
                data = json.loads(raw or "{}")
            except Exception as exc:
                self.message_user(request, f"Square checkout creation failed for invoice {invoice.number}: {exc}", level=messages.ERROR)
                continue

            payment_link = data.get("payment_link") or {}
            url = payment_link.get("url") or ""
            invoice.square_payment_link_id = payment_link.get("id") or ""
            invoice.square_order_id = payment_link.get("order_id") or ""
            invoice.save(update_fields=["square_payment_link_id", "square_order_id"])
            if url:
                checkout_links.append(f'<a href="{url}" target="_blank">Invoice {invoice.number} checkout</a>')
        if checkout_links:
            self.message_user(request, mark_safe("<br/>".join(checkout_links)), level=messages.SUCCESS)

    create_square_checkout.short_description = "Create Square checkout links"


@admin.register(PaymentPlan)
class PaymentPlanAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("name", "total_amount", "installment_count", "frequency", "active")
    list_filter = ("frequency", "active")
    inlines = [PaymentScheduleInline]


@admin.register(Payment)
class PaymentAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("invoice", "amount", "paid_at", "method", "status", "square_payment_id", "reference")
    list_filter = ("method", "status")


# @admin.register(Certificate)
# class CertificateAdmin(ExportCsvMixin, admin.ModelAdmin):
#     list_display = ("certificate_number", "enrollment", "status", "issued_at", "submitted_at")
#     list_filter = ("status",)
#     actions = ["generate_pdf"]
#
#     def generate_pdf(self, request, queryset):
#         generated = 0
#         for certificate in queryset.select_related("enrollment__student", "enrollment__session__course"):
#             enrollment = certificate.enrollment
#             if not enrollment:
#                 continue
#             student_name = f"{enrollment.student.first_name} {enrollment.student.last_name}".strip()
#             course_name = enrollment.session.course.name if enrollment.session and enrollment.session.course else ""
#             lines = [
#                 "Certificate of Completion",
#                 f"Student: {student_name}",
#                 f"Course: {course_name}",
#                 f"Enrollment ID: {enrollment.id}",
#                 f"Issued: {timezone.now().strftime('%Y-%m-%d')}",
#             ]
#             pdf_bytes = _build_simple_pdf(lines)
#             certificate.file.save(f"certificate-{enrollment.id}.pdf", ContentFile(pdf_bytes), save=False)
#             certificate.status = "issued"
#             certificate.issued_at = timezone.now()
#             certificate.save()
#             generated += 1
#         if generated:
#             self.message_user(request, f"Generated {generated} certificate PDF(s).", level=messages.SUCCESS)


@admin.register(CommunicationTemplate)
class CommunicationTemplateAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("name", "channel", "active")
    list_filter = ("channel", "active")
    search_fields = ("name", "subject", "body")


@admin.register(CalendarAccount)
class CalendarAccountAdmin(admin.ModelAdmin):
    list_display = ("provider", "owner", "email", "active", "token_expires_at", "created_at")
    list_filter = ("provider", "active", "created_at")
    search_fields = ("email", "owner__username", "owner__email")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "start", "end", "google_event_id")
    readonly_fields = ("google_event_id",)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        try:
            service = get_calendar_service(request.user)
            google_event_id = upsert_event(
                service=service,
                title=obj.title,
                start=obj.start,
                end=obj.end,
                google_event_id=obj.google_event_id,
            )
            if google_event_id and google_event_id != (obj.google_event_id or ""):
                obj.google_event_id = google_event_id
                obj.save(update_fields=["google_event_id"])
        except Exception as e:
            self.message_user(
                request,
                f"Google Calendar sync failed: {e}",
                level=messages.WARNING,
            )


@admin.register(StaffProfile)
class StaffProfileAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("user", "role", "active")
    list_filter = ("role", "active")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "level", "audience", "active", "created_at")
    list_filter = ("level", "audience", "active", "created_at")
    search_fields = ("title", "body", "link_url")
    filter_horizontal = ("recipients",)
    actions = ["resync_receipts", "activate_notifications", "deactivate_notifications"]

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        obj.sync_receipts()

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if form.instance:
            form.instance.sync_receipts()

    def resync_receipts(self, request, queryset):
        for notification in queryset:
            notification.sync_receipts()
        self.message_user(request, "Receipts synced.", level=messages.SUCCESS)

    def activate_notifications(self, request, queryset):
        updated = queryset.update(active=True)
        if updated:
            self.message_user(request, f"Activated {updated} notification(s).", level=messages.SUCCESS)

    def deactivate_notifications(self, request, queryset):
        updated = queryset.update(active=False)
        if updated:
            self.message_user(request, f"Deactivated {updated} notification(s).", level=messages.SUCCESS)
