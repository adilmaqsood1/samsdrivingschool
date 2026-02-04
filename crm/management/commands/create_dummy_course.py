from django.core.management.base import BaseCommand
from django.utils import timezone
from crm.models import Course, CourseSession

class Command(BaseCommand):
    help = 'Create a dummy course and session for testing'

    def handle(self, *args, **options):
        # Create Course
        course, created = Course.objects.get_or_create(
            name="Dummy Test Course",
            defaults={
                "description": "This is a dummy course for testing purposes.",
                "course_type": "bde",
                "hours_theory": 20,
                "hours_homework": 10,
                "hours_incar": 10,
                "price": 1.00,
                "active": True
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created course: {course.name}"))
        else:
            self.stdout.write(f"Course already exists: {course.name}")

        # Create Session
        start_date = timezone.now().date()
        end_date = start_date + timezone.timedelta(days=30)
        
        session, created = CourseSession.objects.get_or_create(
            course=course,
            start_date=start_date,
            defaults={
                "end_date": end_date,
                "location": "Online",
                "delivery_mode": "online",
                "capacity": 20,
                "enrollment_open": True,
                "schedule_details": "Mondays and Wednesdays 6pm - 8pm"
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f"Created session for {course.name} starting {start_date}"))
        else:
             self.stdout.write(f"Session already exists for {course.name} starting {session.start_date}")
