import json
from datetime import timedelta
from urllib import request as urlrequest
from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils import timezone

from crm.models import ScheduledEmail, CommunicationLog, Lesson, ReminderLog


def _send_sms(recipient_phone, message):
    webhook = getattr(settings, "SMS_WEBHOOK_URL", "")
    if not webhook:
        raise ValueError("SMS webhook is not configured")
    payload = json.dumps({"to": recipient_phone, "message": message}).encode("utf-8")
    req = urlrequest.Request(webhook, data=payload, headers={"Content-Type": "application/json"})
    token = getattr(settings, "SMS_WEBHOOK_TOKEN", "")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urlrequest.urlopen(req, timeout=30) as response:
        response.read()


def _enqueue_lesson_reminders(now):
    window_end = now + timedelta(hours=24)
    upcoming = (
        Lesson.objects.filter(start_time__gte=now, start_time__lte=window_end, status="scheduled")
        .select_related("student")
        .order_by("start_time")
    )
    for lesson in upcoming:
        reminder_time = lesson.start_time - timedelta(hours=24)
        if reminder_time < now:
            reminder_time = now
        exists = ReminderLog.objects.filter(lesson=lesson, reminder_type="lesson_24h").exists()
        if exists:
            continue
        ReminderLog.objects.create(lesson=lesson, reminder_type="lesson_24h", scheduled_for=reminder_time)
        student = lesson.student
        if student and student.email:
            ScheduledEmail.objects.create(
                to_student=student,
                recipient_email=student.email,
                subject="Lesson reminder",
                body=f"Your lesson is scheduled for {lesson.start_time}.",
                scheduled_for=reminder_time,
                channel="email",
            )
        if student and student.phone:
            ScheduledEmail.objects.create(
                to_student=student,
                recipient_phone=student.phone,
                subject="",
                body=f"Lesson reminder: {lesson.start_time}",
                scheduled_for=reminder_time,
                channel="sms",
            )


class Command(BaseCommand):
    help = "Send scheduled emails"

    def handle(self, *args, **options):
        now = timezone.now()
        _enqueue_lesson_reminders(now)
        due_emails = ScheduledEmail.objects.filter(status="scheduled", scheduled_for__lte=now)
        for scheduled in due_emails:
            scheduled.attempts += 1
            subject = scheduled.subject
            body = scheduled.body
            if scheduled.template:
                subject = scheduled.template.subject or subject
                body = scheduled.template.body or body
            try:
                if scheduled.channel == "sms":
                    recipient = scheduled.recipient_phone
                    if not recipient and scheduled.to_student:
                        recipient = scheduled.to_student.phone
                    if not recipient:
                        raise ValueError("Missing recipient phone")
                    _send_sms(recipient, body)
                    scheduled.status = "sent"
                    scheduled.sent_at = timezone.now()
                    scheduled.last_error = ""
                    scheduled.save(update_fields=["status", "sent_at", "last_error", "attempts"])
                    CommunicationLog.objects.create(
                        template=scheduled.template,
                        to_lead=scheduled.to_lead,
                        to_student=scheduled.to_student,
                        recipient_phone=recipient,
                        status="sent",
                        sent_at=scheduled.sent_at,
                    )
                else:
                    recipient = scheduled.recipient_email
                    if not recipient and scheduled.to_lead:
                        recipient = scheduled.to_lead.email
                    if not recipient and scheduled.to_student:
                        recipient = scheduled.to_student.email
                    if not recipient:
                        raise ValueError("Missing recipient email")
                    send_mail(subject, body, None, [recipient], fail_silently=False)
                    scheduled.status = "sent"
                    scheduled.sent_at = timezone.now()
                    scheduled.last_error = ""
                    scheduled.save(update_fields=["status", "sent_at", "last_error", "attempts"])
                    CommunicationLog.objects.create(
                        template=scheduled.template,
                        to_lead=scheduled.to_lead,
                        to_student=scheduled.to_student,
                        recipient_email=recipient,
                        status="sent",
                        sent_at=scheduled.sent_at,
                    )
            except Exception as exc:
                scheduled.status = "failed"
                scheduled.last_error = str(exc)
                scheduled.save(update_fields=["status", "last_error", "attempts"])
