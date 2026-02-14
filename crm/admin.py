import csv
import stripe
from django.conf import settings
from django.contrib import admin, messages
from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.utils import timezone
from django.utils.safestring import mark_safe
from googleapiclient.errors import HttpError
from utils.gcalendar import get_calendar_service
from .models import (
    Lead,
    LeadNote,
    LeadTask,
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
    StaffProfile,
    Notification,
    NotificationReceipt,
    Blog,
    BlogCategory,
    BlogTag,
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

class CertificateInline(admin.TabularInline):
    model = Certificate
    extra = 0
    readonly_fields = ("issued_at", "submitted_at")

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


@admin.register(Course)
class CourseAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("name", "course_type", "price", "active")
    list_filter = ("course_type", "active")
    search_fields = ("name", "description")


@admin.register(CourseSession)
class CourseSessionAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("course", "location", "delivery_mode", "start_date", "capacity", "enrollment_open")
    list_filter = ("delivery_mode", "location", "enrollment_open")


@admin.register(Enrollment)
class EnrollmentAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("student", "session", "status", "enrolled_at", "balance")
    list_filter = ("status",)
    search_fields = ("student__first_name", "student__last_name")
    actions = ["issue_certificates", "submit_ministry"]
    inlines = [StudentModuleProgressInline, MinistrySubmissionInline, CertificateInline]

    def issue_certificates(self, request, queryset):
        issued = 0
        for enrollment in queryset.select_related("student", "session__course"):
            certificate, created = Certificate.objects.get_or_create(
                enrollment=enrollment,
                defaults={"certificate_number": _certificate_number(enrollment)},
            )
            if certificate.status == "issued" and certificate.file:
                continue
            student_name = f"{enrollment.student.first_name} {enrollment.student.last_name}".strip()
            course_name = enrollment.session.course.name if enrollment.session and enrollment.session.course else ""
            lines = [
                "Certificate of Completion",
                f"Student: {student_name}",
                f"Course: {course_name}",
                f"Enrollment ID: {enrollment.id}",
                f"Issued: {timezone.now().strftime('%Y-%m-%d')}",
            ]
            pdf_bytes = _build_simple_pdf(lines)
            certificate.file.save(f"certificate-{enrollment.id}.pdf", ContentFile(pdf_bytes), save=False)
            certificate.status = "issued"
            certificate.issued_at = timezone.now()
            certificate.save()
            issued += 1
        if issued:
            self.message_user(request, f"Issued {issued} certificate(s).", level=messages.SUCCESS)

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


@admin.register(BlogCategory)
class BlogCategoryAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("name", "slug", "updated_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


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
    list_display = ("number", "enrollment", "issue_date", "due_date", "total_amount", "status", "stripe_checkout_session_id")
    list_filter = ("status",)
    search_fields = ("number",)
    actions = ["create_stripe_checkout"]

    def create_stripe_checkout(self, request, queryset):
        if not settings.STRIPE_SECRET_KEY:
            self.message_user(request, "Stripe secret key is not configured.", level=messages.ERROR)
            return
        stripe.api_key = settings.STRIPE_SECRET_KEY
        checkout_links = []
        for invoice in queryset:
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
            checkout_links.append(f'<a href="{session.url}" target="_blank">Invoice {invoice.number} checkout</a>')
        if checkout_links:
            self.message_user(request, mark_safe("<br/>".join(checkout_links)), level=messages.SUCCESS)

    create_stripe_checkout.short_description = "Create Stripe checkout sessions"


@admin.register(PaymentPlan)
class PaymentPlanAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("name", "total_amount", "installment_count", "frequency", "active")
    list_filter = ("frequency", "active")
    inlines = [PaymentScheduleInline]


@admin.register(Payment)
class PaymentAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("invoice", "amount", "paid_at", "method", "status", "stripe_payment_intent_id")
    list_filter = ("method", "status")


@admin.register(Certificate)
class CertificateAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("certificate_number", "enrollment", "status", "issued_at", "submitted_at")
    list_filter = ("status",)
    actions = ["generate_pdf"]

    def generate_pdf(self, request, queryset):
        generated = 0
        for certificate in queryset.select_related("enrollment__student", "enrollment__session__course"):
            enrollment = certificate.enrollment
            if not enrollment:
                continue
            student_name = f"{enrollment.student.first_name} {enrollment.student.last_name}".strip()
            course_name = enrollment.session.course.name if enrollment.session and enrollment.session.course else ""
            lines = [
                "Certificate of Completion",
                f"Student: {student_name}",
                f"Course: {course_name}",
                f"Enrollment ID: {enrollment.id}",
                f"Issued: {timezone.now().strftime('%Y-%m-%d')}",
            ]
            pdf_bytes = _build_simple_pdf(lines)
            certificate.file.save(f"certificate-{enrollment.id}.pdf", ContentFile(pdf_bytes), save=False)
            certificate.status = "issued"
            certificate.issued_at = timezone.now()
            certificate.save()
            generated += 1
        if generated:
            self.message_user(request, f"Generated {generated} certificate PDF(s).", level=messages.SUCCESS)


@admin.register(CommunicationTemplate)
class CommunicationTemplateAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("name", "channel", "active")
    list_filter = ("channel", "active")
    search_fields = ("name", "subject", "body")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "start", "end", "google_event_id")
    readonly_fields = ("google_event_id",)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        tz = getattr(settings, "GOOGLE_CALENDAR_TIME_ZONE", "Asia/Karachi")
        calendar_id = getattr(settings, "GOOGLE_CALENDAR_ID", "") or "primary"
        body = {
            "summary": obj.title,
            "start": {"dateTime": obj.start.isoformat(), "timeZone": tz},
            "end": {"dateTime": obj.end.isoformat(), "timeZone": tz},
        }

        try:
            service = get_calendar_service()

            if obj.google_event_id:
                try:
                    service.events().update(
                        calendarId=calendar_id, eventId=obj.google_event_id, body=body
                    ).execute()
                    return
                except HttpError as e:
                    status = getattr(getattr(e, "resp", None), "status", None)
                    if status != 404:
                        raise

            event = service.events().insert(calendarId=calendar_id, body=body).execute()
            google_event_id = event.get("id", "")
            if google_event_id and google_event_id != obj.google_event_id:
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
