import json
from urllib import request as urlrequest
from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils import timezone

from crm.models import CommunicationLog


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


class Command(BaseCommand):
    help = "Send queued communications"

    def handle(self, *args, **options):
        logs = CommunicationLog.objects.filter(status="queued").select_related("template", "to_lead", "to_student")
        for log in logs:
            template = log.template
            if not template:
                log.status = "failed"
                log.error_message = "Missing template"
                log.save(update_fields=["status", "error_message"])
                continue
            try:
                if template.channel == "sms":
                    recipient = log.recipient_phone
                    if not recipient and log.to_lead:
                        recipient = log.to_lead.phone
                    if not recipient and log.to_student:
                        recipient = log.to_student.phone
                    if not recipient:
                        raise ValueError("Missing recipient phone")
                    _send_sms(recipient, template.body)
                else:
                    recipient = log.recipient_email
                    if not recipient and log.to_lead:
                        recipient = log.to_lead.email
                    if not recipient and log.to_student:
                        recipient = log.to_student.email
                    if not recipient:
                        raise ValueError("Missing recipient email")
                    send_mail(template.subject, template.body, None, [recipient], fail_silently=False)
                log.status = "sent"
                log.sent_at = timezone.now()
                log.error_message = ""
                log.save(update_fields=["status", "sent_at", "error_message"])
            except Exception as exc:
                log.status = "failed"
                log.error_message = str(exc)
                log.save(update_fields=["status", "error_message"])
