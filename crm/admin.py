import csv
import stripe
from django.conf import settings
from django.contrib import admin, messages
from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.utils import timezone
from django.utils.safestring import mark_safe
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
    CalendarAccount,
    StaffProfile,
    Notification,
    NotificationReceipt,
    Blog,
    BlogCategory,
    BlogTag,
    BlogComment,
    Testimonial,
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


@admin.register(Lead)
class LeadAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("first_name", "last_name", "email", "phone", "status", "assigned_to", "created_at")
    list_filter = ("status", "assigned_to", "created_at")
    search_fields = ("first_name", "last_name", "email", "phone", "source", "interest")


@admin.register(LeadNote)
class LeadNoteAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("lead", "created_by", "created_at")
    search_fields = ("lead__first_name", "lead__last_name", "note")


@admin.register(LeadTask)
class LeadTaskAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("title", "lead", "status", "due_date", "assigned_to")
    list_filter = ("status", "due_date")
    search_fields = ("title", "lead__first_name", "lead__last_name")


@admin.register(Student)
class StudentAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("first_name", "last_name", "email", "phone", "preferred_location", "created_at")
    search_fields = ("first_name", "last_name", "email", "phone")


@admin.register(StudentDocument)
class StudentDocumentAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("student", "document_type", "verified", "uploaded_at")
    list_filter = ("document_type", "verified")


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


@admin.register(BlogCategory)
class BlogCategoryAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("name", "slug", "updated_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(BlogTag)
class BlogTagAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("name", "slug", "updated_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(BlogComment)
class BlogCommentAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("blog", "name", "is_approved", "created_at")
    list_filter = ("is_approved", "created_at")
    search_fields = ("blog__title", "name", "email", "body")


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


@admin.register(PaymentSchedule)
class PaymentScheduleAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("plan", "invoice", "due_date", "amount", "status")
    list_filter = ("status", "due_date")


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


@admin.register(StudentModuleProgress)
class StudentModuleProgressAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("enrollment", "module", "status", "score", "completed_at", "updated_at")
    list_filter = ("status",)


@admin.register(LessonAttendance)
class LessonAttendanceAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("lesson", "status", "recorded_by", "recorded_at")
    list_filter = ("status",)


@admin.register(MinistrySubmission)
class MinistrySubmissionAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("enrollment", "status", "submitted_at", "external_reference")
    list_filter = ("status",)


@admin.register(CommunicationTemplate)
class CommunicationTemplateAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("name", "channel", "active")
    list_filter = ("channel", "active")
    search_fields = ("name", "subject", "body")


@admin.register(CommunicationLog)
class CommunicationLogAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("template", "recipient_email", "status", "sent_at")
    list_filter = ("status",)


@admin.register(ScheduledEmail)
class ScheduledEmailAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("recipient_email", "scheduled_for", "status", "attempts", "sent_at")
    list_filter = ("status", "scheduled_for")


@admin.register(ConflictDetection)
class ConflictDetectionAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("lesson", "conflict_type", "conflicting_lesson", "resolved", "detected_at")
    list_filter = ("conflict_type", "resolved")


@admin.register(ReminderLog)
class ReminderLogAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("lesson", "reminder_type", "channel", "scheduled_for", "created_at")
    list_filter = ("reminder_type", "channel")


@admin.register(CalendarFeed)
class CalendarFeedAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("feed_type", "student", "instructor", "active", "token")
    list_filter = ("feed_type", "active")


@admin.register(CalendarAccount)
class CalendarAccountAdmin(ExportCsvMixin, admin.ModelAdmin):
    list_display = ("owner", "provider", "email", "active", "token_expires_at")
    list_filter = ("provider", "active")


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


@admin.register(NotificationReceipt)
class NotificationReceiptAdmin(admin.ModelAdmin):
    list_display = ("notification", "user", "read_at", "dismissed_at", "created_at")
    list_filter = ("read_at", "dismissed_at", "created_at", "notification__level")
    search_fields = ("notification__title", "user__username", "user__email")
    autocomplete_fields = ("notification", "user")
    actions = ["mark_read", "mark_unread", "dismiss", "clear_dismiss"]

    def mark_read(self, request, queryset):
        now = timezone.now()
        updated = queryset.filter(read_at__isnull=True).update(read_at=now)
        if updated:
            self.message_user(request, f"Marked {updated} as read.", level=messages.SUCCESS)

    def mark_unread(self, request, queryset):
        updated = queryset.exclude(read_at__isnull=True).update(read_at=None)
        if updated:
            self.message_user(request, f"Marked {updated} as unread.", level=messages.SUCCESS)

    def dismiss(self, request, queryset):
        now = timezone.now()
        updated = queryset.filter(dismissed_at__isnull=True).update(dismissed_at=now)
        if updated:
            self.message_user(request, f"Dismissed {updated}.", level=messages.SUCCESS)

    def clear_dismiss(self, request, queryset):
        updated = queryset.exclude(dismissed_at__isnull=True).update(dismissed_at=None)
        if updated:
            self.message_user(request, f"Cleared dismiss for {updated}.", level=messages.SUCCESS)
