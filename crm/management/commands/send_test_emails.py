from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.template.loader import get_template
from django.utils import timezone
import time

class Command(BaseCommand):
    help = 'Send test emails for all templates to a specified address'

    def handle(self, *args, **options):
        test_email = "ali@socialdots.ca"
        self.stdout.write(f"Sending test emails to {test_email}...")

        # 1. Contact Acknowledgement (User)
        self.stdout.write("Sending Contact Acknowledgement...")
        ack_context = {
            "first_name": "Adil",
            "subject": "Test Inquiry Subject",
            "message": "This is a test message from the contact form.",
        }
        ack_html = get_template("emails/contact_ack.html").render(ack_context)
        send_mail(
            "Test: We have received your message",
            "",
            None,
            [test_email],
            fail_silently=False,
            html_message=ack_html
        )
        time.sleep(1) # Pause to avoid rate limits

        # 2. Contact Notification (Admin)
        self.stdout.write("Sending Contact Notification (Admin)...")
        admin_context = {
            "name": "Adil Maqsood",
            "email": "adilmaqsood501@gmail.com",
            "phone": "123-456-7890",
            "subject": "Test Inquiry Subject",
            "message": "This is a test message from the contact form.",
        }
        admin_html = get_template("emails/contact_admin_notification.html").render(admin_context)
        send_mail(
            "Test: New Website Lead",
            "",
            None,
            [test_email],
            fail_silently=False,
            html_message=admin_html
        )
        time.sleep(1)

        # 3. Purchase Success (User)
        self.stdout.write("Sending Purchase Success (User)...")
        user_purchase_context = {
            "student_name": "Adil Maqsood",
            "course_name": "MTO Approved Beginner Driving Online Course",
            "invoice_number": "INV-2025-001",
            "amount": "649.75",
        }
        user_purchase_html = get_template("emails/purchase_success_user.html").render(user_purchase_context)
        send_mail(
            "Test: Payment Confirmation - Sams Driving School",
            "",
            None,
            [test_email],
            fail_silently=False,
            html_message=user_purchase_html
        )
        time.sleep(1)

        # 4. Purchase Success (Admin)
        self.stdout.write("Sending Purchase Success (Admin)...")
        admin_purchase_context = {
            "student_name": "Adil Maqsood",
            "student_email": "adilmaqsood501@gmail.com",
            "invoice_number": "INV-2025-001",
            "amount": "649.75",
            "course_name": "MTO Approved Beginner Driving Online Course",
        }
        admin_purchase_html = get_template("emails/purchase_success_admin.html").render(admin_purchase_context)
        send_mail(
            "Test: New Payment Received - Invoice INV-2025-001",
            "",
            None,
            [test_email],
            fail_silently=False,
            html_message=admin_purchase_html
        )
        time.sleep(1)

        # 5. Lesson Reminder
        self.stdout.write("Sending Lesson Reminder...")
        lesson_context = {
            "student_name": "Adil Maqsood",
            "lesson_type": "driving",
            "start_time": timezone.now() + timezone.timedelta(days=1),
            "end_time": timezone.now() + timezone.timedelta(days=1, hours=1),
            "instructor_name": "John Doe",
            "pickup_location": "123 Test St, Burlington, ON",
        }
        lesson_html = get_template("emails/lesson_reminder.html").render(lesson_context)
        send_mail(
            "Test: Upcoming Lesson Reminder",
            "",
            None,
            [test_email],
            fail_silently=False,
            html_message=lesson_html
        )

        self.stdout.write(self.style.SUCCESS(f"All 5 test emails sent to {test_email}"))
