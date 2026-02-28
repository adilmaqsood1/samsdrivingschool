import uuid
from datetime import timedelta
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from ckeditor_uploader.fields import RichTextUploadingField


class Lead(models.Model):
    STATUS_CHOICES = [
        ("new", "New"),
        ("contacted", "Contacted"),
        ("qualified", "Qualified"),
        ("converted", "Converted"),
        ("closed", "Closed"),
    ]
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True)
    source = models.CharField(max_length=100, blank=True)
    interest = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_leads"
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip()


class EnrollmentRequest(models.Model):
    STATUS_CHOICES = [
        ("new", "New"),
        ("contacted", "Contacted"),
        ("converted", "Converted"),
        ("closed", "Closed"),
    ]
    name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True)
    package = models.CharField(max_length=150, blank=True)
    preferred_location = models.CharField(max_length=120, blank=True)
    preferred_schedule = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} {self.package}"


class LeadNote(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="lead_notes")
    note = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="lead_notes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.lead} note"


class LeadTask(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
    ]
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="lead_tasks")
    title = models.CharField(max_length=200)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="lead_tasks"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Student(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    address_line1 = models.CharField(max_length=200, blank=True)
    address_line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    license_number = models.CharField(max_length=100, blank=True)
    license_issue_date = models.DateField(null=True, blank=True)
    license_expiry_date = models.DateField(null=True, blank=True)
    license_status = models.CharField(max_length=100, blank=True)
    preferred_location = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        name = f"{self.first_name} {self.middle_name} {self.last_name}".strip()
        return " ".join(name.split())


class StudentDocument(models.Model):
    DOCUMENT_CHOICES = [
        ("id", "ID"),
        ("license", "License"),
        ("proof_of_address", "Proof Of Address"),
        ("other", "Other"),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=50, choices=DOCUMENT_CHOICES, default="other")
    file = models.FileField(upload_to="student_documents/")
    verified = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.student} {self.document_type}"


class Course(models.Model):
    COURSE_TYPES = [
        ("bde", "BDE"),
        ("defensive", "Defensive"),
        ("test_prep", "Test Prep"),
        ("refresher", "Refresher"),
    ]
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    image = models.CharField(max_length=255, blank=True)
    summary = models.TextField(blank=True)
    description = RichTextUploadingField(blank=True)
    overview = RichTextUploadingField(blank=True)
    session = models.CharField(max_length=200, blank=True)
    course_type = models.CharField(max_length=30, choices=COURSE_TYPES, default="bde")
    hours_theory = models.PositiveIntegerField(default=0)
    hours_homework = models.PositiveIntegerField(default=0)
    hours_incar = models.PositiveIntegerField(default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_label = models.CharField(max_length=50, blank=True, default="Per Person")
    enroll_package = models.CharField(max_length=200, blank=True)
    details = models.JSONField(default=list, blank=True)
    program_includes = models.JSONField(default=list, blank=True)
    program_options = models.JSONField(default=list, blank=True)
    g1_restrictions = models.JSONField(default=list, blank=True)
    fees = models.JSONField(default=dict, blank=True)
    policies = models.JSONField(default=list, blank=True)
    features = models.JSONField(default=list, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    @property
    def title(self):
        return self.name

    @property
    def price_display(self):
        return f"{self.price:.2f}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)[:170] or uuid.uuid4().hex[:12]
            candidate = base_slug
            suffix = 2
            while Course.objects.exclude(pk=self.pk).filter(slug=candidate).exists():
                suffix_str = f"-{suffix}"
                candidate = f"{base_slug[: (180 - len(suffix_str))]}{suffix_str}"
                suffix += 1
            self.slug = candidate
        super().save(*args, **kwargs)


class CourseModule(models.Model):
    MODULE_TYPES = [
        ("theory", "Theory"),
        ("homework", "Homework"),
        ("driving", "Driving"),
    ]
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="modules")
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    module_type = models.CharField(max_length=20, choices=MODULE_TYPES, default="theory")
    order = models.PositiveIntegerField(default=1)
    hours_required = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.course} {self.title}"


class CourseSession(models.Model):
    DELIVERY_CHOICES = [
        ("in_class", "In Class"),
        ("online", "Online"),
    ]
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="sessions")
    location = models.CharField(max_length=120, blank=True)
    delivery_mode = models.CharField(max_length=20, choices=DELIVERY_CHOICES, default="in_class")
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    capacity = models.PositiveIntegerField(default=0)
    enrollment_open = models.BooleanField(default=True)
    schedule_details = models.TextField(blank=True)

    def __str__(self):
        return f"{self.course} {self.start_date}"


class PaymentPlan(models.Model):
    FREQUENCY_CHOICES = [
        ("weekly", "Weekly"),
        ("biweekly", "Biweekly"),
        ("monthly", "Monthly"),
    ]
    name = models.CharField(max_length=150)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    installment_count = models.PositiveIntegerField(default=1)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default="monthly")
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Enrollment(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("active", "Active"),
        ("completed", "Completed"),
        ("dropped", "Dropped"),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="enrollments")
    session = models.ForeignKey(CourseSession, on_delete=models.CASCADE, related_name="enrollments")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    enrolled_at = models.DateTimeField(auto_now_add=True)
    payment_plan = models.ForeignKey(PaymentPlan, null=True, blank=True, on_delete=models.SET_NULL)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    dropped_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.student} {self.session}"


class StudentModuleProgress(models.Model):
    STATUS_CHOICES = [
        ("not_started", "Not Started"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
    ]
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name="module_progress")
    module = models.ForeignKey(CourseModule, on_delete=models.CASCADE, related_name="progress")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="not_started")
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.enrollment} {self.module}"


class Instructor(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="instructor_profile")
    phone = models.CharField(max_length=50, blank=True)
    license_number = models.CharField(max_length=100, blank=True)
    hire_date = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)
    home_location = models.CharField(max_length=120, blank=True)

    def __str__(self):
        return self.user.get_username()


class Vehicle(models.Model):
    name = models.CharField(max_length=150, blank=True)
    make = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=100, blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)
    plate_number = models.CharField(max_length=50, blank=True)
    active = models.BooleanField(default=True)
    location = models.CharField(max_length=120, blank=True)

    def __str__(self):
        return self.name or f"{self.make} {self.model}".strip()


class Classroom(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=120, blank=True)
    capacity = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Lesson(models.Model):
    LESSON_TYPES = [
        ("theory", "Theory"),
        ("driving", "Driving"),
    ]
    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("missed", "Missed"),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="lessons")
    instructor = models.ForeignKey(Instructor, null=True, blank=True, on_delete=models.SET_NULL, related_name="lessons")
    vehicle = models.ForeignKey(Vehicle, null=True, blank=True, on_delete=models.SET_NULL, related_name="lessons")
    classroom = models.ForeignKey(Classroom, null=True, blank=True, on_delete=models.SET_NULL, related_name="lessons")
    session = models.ForeignKey(CourseSession, null=True, blank=True, on_delete=models.SET_NULL, related_name="lessons")
    lesson_type = models.CharField(max_length=20, choices=LESSON_TYPES, default="driving")
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    pickup_address = models.CharField(max_length=200, blank=True)
    dropoff_address = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="scheduled")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student} {self.start_time}"

    def clean(self):
        if not self.end_time and self.start_time:
            self.end_time = self.start_time + timedelta(hours=1)
            
        if self.start_time >= self.end_time:
            raise ValidationError("End time must be after start time.")
        overlapping = Lesson.objects.filter(start_time__lt=self.end_time, end_time__gt=self.start_time)
        if self.pk:
            overlapping = overlapping.exclude(pk=self.pk)
        if self.instructor and overlapping.filter(instructor=self.instructor).exists():
            raise ValidationError("Instructor is already booked for this time.")
        if self.vehicle and overlapping.filter(vehicle=self.vehicle).exists():
            raise ValidationError("Vehicle is already booked for this time.")
        if self.classroom and overlapping.filter(classroom=self.classroom).exists():
            raise ValidationError("Classroom is already booked for this time.")
        
        # Validation rule: Max 5 lessons if not paid
        if self.student:
            # Check if student has paid in full
            # We check if there is any enrollment that is 'paid' or 'completed'
            has_paid = Enrollment.objects.filter(
                student=self.student, 
                status__in=["paid", "completed"]
            ).exists()
            
            if not has_paid:
                # Count existing lessons (excluding self)
                lesson_count = Lesson.objects.filter(student=self.student).exclude(pk=self.pk).count()
                if lesson_count >= 5:
                    raise ValidationError("Student has not paid in full. Maximum 5 lessons allowed.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class LessonAttendance(models.Model):
    STATUS_CHOICES = [
        ("attended", "Attended"),
        ("missed", "Missed"),
        ("cancelled", "Cancelled"),
        ("rescheduled", "Rescheduled"),
    ]
    lesson = models.OneToOneField(Lesson, on_delete=models.CASCADE, related_name="attendance")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="attended")
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="lesson_attendance"
    )
    recorded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.lesson} {self.status}"


class ConflictDetection(models.Model):
    CONFLICT_TYPES = [
        ("instructor", "Instructor Conflict"),
        ("vehicle", "Vehicle Conflict"),
        ("classroom", "Classroom Conflict"),
    ]
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="conflict_detections")
    conflict_type = models.CharField(max_length=20, choices=CONFLICT_TYPES)
    conflicting_lesson = models.ForeignKey(
        Lesson, on_delete=models.SET_NULL, null=True, blank=True, related_name="conflicts_with"
    )
    detected_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.lesson} {self.conflict_type}"


class LessonRequest(models.Model):
    STATUS_CHOICES = [
        ("new", "New"),
        ("scheduled", "Scheduled"),
        ("closed", "Closed"),
    ]
    name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True)
    preferred_date = models.DateField(null=True, blank=True)
    preferred_time = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} {self.status}"


class Invoice(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("issued", "Issued"),
        ("paid", "Paid"),
        ("overdue", "Overdue"),
        ("void", "Void"),
    ]
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name="invoices")
    number = models.CharField(max_length=50, unique=True)
    issue_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    notes = models.TextField(blank=True)
    stripe_payment_intent_id = models.CharField(max_length=200, blank=True)
    stripe_checkout_session_id = models.CharField(max_length=200, blank=True)
    stripe_customer_id = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.number


class PaymentSchedule(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("overdue", "Overdue"),
    ]
    plan = models.ForeignKey(PaymentPlan, on_delete=models.CASCADE, related_name="schedules")
    invoice = models.ForeignKey(Invoice, null=True, blank=True, on_delete=models.SET_NULL, related_name="schedules")
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    def __str__(self):
        return f"{self.plan} {self.due_date}"


class Payment(models.Model):
    METHOD_CHOICES = [
        ("stripe", "Stripe"),
        ("square", "Square"),
        ("cash", "Cash"),
        ("transfer", "Transfer"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    ]
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_at = models.DateTimeField()
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default="stripe")
    reference = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="completed")
    stripe_payment_intent_id = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.invoice} {self.amount}"


class Certificate(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("issued", "Issued"),
        ("submitted", "Submitted"),
    ]
    enrollment = models.OneToOneField(Enrollment, on_delete=models.CASCADE, related_name="certificate")
    certificate_number = models.CharField(max_length=100, unique=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    file = models.FileField(upload_to="certificates/", null=True, blank=True)

    def __str__(self):
        return self.certificate_number


class MinistrySubmission(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("submitted", "Submitted"),
        ("failed", "Failed"),
    ]
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name="ministry_submissions")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    submitted_at = models.DateTimeField(null=True, blank=True)
    external_reference = models.CharField(max_length=200, blank=True)
    file = models.FileField(upload_to="ministry_submissions/", null=True, blank=True)

    def __str__(self):
        return f"{self.enrollment} {self.status}"


class CommunicationTemplate(models.Model):
    CHANNEL_CHOICES = [
        ("email", "Email"),
        ("sms", "SMS"),
    ]
    name = models.CharField(max_length=150)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default="email")
    subject = models.CharField(max_length=200, blank=True)
    body = models.TextField()
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class CommunicationLog(models.Model):
    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("sent", "Sent"),
        ("failed", "Failed"),
    ]
    template = models.ForeignKey(CommunicationTemplate, null=True, blank=True, on_delete=models.SET_NULL)
    to_lead = models.ForeignKey(Lead, null=True, blank=True, on_delete=models.SET_NULL)
    to_student = models.ForeignKey(Student, null=True, blank=True, on_delete=models.SET_NULL)
    recipient_email = models.EmailField(blank=True)
    recipient_phone = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="queued")
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    def __str__(self):
        return f"{self.status} {self.recipient_email}"


class ScheduledEmail(models.Model):
    CHANNEL_CHOICES = [
        ("email", "Email"),
        ("sms", "SMS"),
    ]
    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("sent", "Sent"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]
    template = models.ForeignKey(CommunicationTemplate, null=True, blank=True, on_delete=models.SET_NULL)
    to_lead = models.ForeignKey(Lead, null=True, blank=True, on_delete=models.SET_NULL)
    to_student = models.ForeignKey(Student, null=True, blank=True, on_delete=models.SET_NULL)
    recipient_email = models.EmailField(blank=True)
    recipient_phone = models.CharField(max_length=50, blank=True)
    subject = models.CharField(max_length=200, blank=True)
    body = models.TextField()
    scheduled_for = models.DateTimeField()
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default="email")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="scheduled")
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.status} {self.recipient_email}"


class ReminderLog(models.Model):
    REMINDER_TYPES = [
        ("lesson_24h", "Lesson 24h"),
    ]
    lesson = models.ForeignKey(Lesson, null=True, blank=True, on_delete=models.CASCADE, related_name="reminder_logs")
    reminder_type = models.CharField(max_length=30, choices=REMINDER_TYPES)
    channel = models.CharField(max_length=20, choices=ScheduledEmail.CHANNEL_CHOICES, default="email")
    scheduled_for = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.reminder_type} {self.channel}"


class Notification(models.Model):
    LEVEL_CHOICES = [
        ("info", "Info"),
        ("success", "Success"),
        ("warning", "Warning"),
        ("error", "Error"),
    ]
    AUDIENCE_CHOICES = [
        ("staff", "All staff"),
        ("selected", "Selected users"),
    ]
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default="info")
    link_url = models.CharField(max_length=300, blank=True)
    audience = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default="staff")
    recipients = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="targeted_notifications"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_notifications",
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    def sync_receipts(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        if self.audience == "selected":
            target_ids = list(self.recipients.values_list("id", flat=True))
        else:
            target_ids = list(User.objects.filter(is_active=True, is_staff=True).values_list("id", flat=True))

        NotificationReceipt.objects.filter(notification=self).exclude(user_id__in=target_ids).delete()
        existing = set(
            NotificationReceipt.objects.filter(notification=self, user_id__in=target_ids).values_list("user_id", flat=True)
        )
        missing_ids = [uid for uid in target_ids if uid not in existing]
        if missing_ids:
            NotificationReceipt.objects.bulk_create(
                [NotificationReceipt(notification=self, user_id=uid) for uid in missing_ids],
                ignore_conflicts=True,
            )


class NotificationReceipt(models.Model):
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name="receipts")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_receipts")
    read_at = models.DateTimeField(null=True, blank=True)
    dismissed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("notification", "user")

    def __str__(self):
        return f"{self.user.get_username()} - {self.notification.title}"


class Event(models.Model):
    title = models.CharField(max_length=200)
    start = models.DateTimeField()
    end = models.DateTimeField()
    google_event_id = models.CharField(max_length=255, blank=True, null=True)


class CalendarAccount(models.Model):
    PROVIDER_CHOICES = [
        ("google", "Google"),
        ("outlook", "Outlook"),
    ]
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="calendar_accounts")
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    email = models.EmailField(blank=True)
    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    token_expires_at = models.DateTimeField(blank=True, null=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        label = self.email or self.owner.get_username()
        return f"{self.provider} {label}".strip()


class CalendarFeed(models.Model):
    FEED_CHOICES = [
        ("student", "Student"),
        ("instructor", "Instructor"),
    ]
    token = models.UUIDField(unique=True, editable=False, default=uuid.uuid4)
    feed_type = models.CharField(max_length=20, choices=FEED_CHOICES, default="student")
    student = models.ForeignKey(Student, null=True, blank=True, on_delete=models.SET_NULL)
    instructor = models.ForeignKey(Instructor, null=True, blank=True, on_delete=models.SET_NULL)
    include_past = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.feed_type} {self.token}"

class StaffProfile(models.Model):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("manager", "Manager"),
        ("instructor", "Instructor"),
        ("staff", "Staff"),
    ]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="staff")
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.get_username()} {self.role}"

class Blog(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    summary = RichTextUploadingField(blank=True)
    content = RichTextUploadingField(blank=True)
    author_name = models.CharField(max_length=120, blank=True)
    author_title = models.CharField(max_length=120, blank=True)
    cover_image = models.ImageField(upload_to="blog_covers/", blank=True)
    author_image = models.ImageField(upload_to="blog_authors/", blank=True)
    is_published = models.BooleanField(default=True)
    published_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title) or "blog"
            candidate = base_slug
            counter = 1
            while Blog.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                counter += 1
                candidate = f"{base_slug}-{counter}"
            self.slug = candidate
        super().save(*args, **kwargs)


class BlogComment(models.Model):
    blog = models.ForeignKey(Blog, on_delete=models.CASCADE, related_name="comments")
    name = models.CharField(max_length=120)
    email = models.EmailField(blank=True)
    body = models.TextField()
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.blog.title} - {self.name}"


class Testimonial(models.Model):
    name = models.CharField(max_length=120)
    role = models.CharField(max_length=120, blank=True)
    quote = models.TextField()
    rating = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    photo = models.ImageField(upload_to="testimonials/", blank=True)
    is_published = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "-updated_at"]

    def __str__(self):
        return self.name
