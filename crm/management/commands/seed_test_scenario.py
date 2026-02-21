from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from crm.models import Student, Course, CourseSession, Enrollment, Lesson, Invoice, Payment, Instructor
import datetime

class Command(BaseCommand):
    help = 'Seeds data for testing new features and validation rules'

    def handle(self, *args, **options):
        self.stdout.write("Starting test scenario seeding...")
        
        User = get_user_model()
        
        # Ensure a course exists
        course, _ = Course.objects.get_or_create(
            name="Test Course BDE",
            defaults={'price': 600.00, 'active': True}
        )
        
        session, _ = CourseSession.objects.get_or_create(
            course=course,
            start_date=timezone.now().date(),
            defaults={'location': 'Test Location', 'capacity': 10}
        )

        # Ensure an instructor exists
        instructor_user, _ = User.objects.get_or_create(username="inst_test", defaults={'email': 'inst@test.com'})
        instructor, _ = Instructor.objects.get_or_create(user=instructor_user, defaults={'active': True})

        # 1. Create "John Unpaid"
        u_unpaid, _ = User.objects.get_or_create(username="john_unpaid", defaults={'email': 'john@unpaid.com'})
        s_unpaid, _ = Student.objects.get_or_create(
            user=u_unpaid,
            defaults={
                'first_name': 'John', 'last_name': 'Unpaid', 'email': 'john@unpaid.com',
                'license_number': 'L12345', 'license_issue_date': timezone.now().date()
            }
        )
        
        # Enrollment for Unpaid
        e_unpaid, _ = Enrollment.objects.get_or_create(
            student=s_unpaid, session=session,
            defaults={'status': 'pending'}
        )
        
        # 2. Create "Jane Paid"
        u_paid, _ = User.objects.get_or_create(username="jane_paid", defaults={'email': 'jane@paid.com'})
        s_paid, _ = Student.objects.get_or_create(
            user=u_paid,
            defaults={
                'first_name': 'Jane', 'last_name': 'Paid', 'email': 'jane@paid.com',
                'license_number': 'L67890'
            }
        )
        
        # Enrollment for Paid
        e_paid, _ = Enrollment.objects.get_or_create(
            student=s_paid, session=session,
            defaults={'status': 'paid'}
        )
        
        # 3. Test Validation Rule: Unpaid Student
        self.stdout.write(f"Testing validation for {s_unpaid} (Unpaid)...")
        
        # Clear existing lessons for clean test
        Lesson.objects.filter(student=s_unpaid).delete()
        
        for i in range(1, 7):
            start = timezone.now() + datetime.timedelta(days=i)
            end = start + datetime.timedelta(hours=1)
            try:
                Lesson.objects.create(
                    student=s_unpaid,
                    instructor=instructor,
                    start_time=start,
                    end_time=end,
                    status='scheduled'
                )
                self.stdout.write(self.style.SUCCESS(f"  Lesson {i} created."))
            except ValidationError as e:
                self.stdout.write(self.style.WARNING(f"  Lesson {i} blocked as expected: {e}"))

        # 4. Test Validation Rule: Paid Student
        self.stdout.write(f"Testing validation for {s_paid} (Paid)...")
        
        # Clear existing lessons
        Lesson.objects.filter(student=s_paid).delete()
        
        for i in range(1, 7):
            start = timezone.now() + datetime.timedelta(days=i)
            end = start + datetime.timedelta(hours=1)
            try:
                Lesson.objects.create(
                    student=s_paid,
                    instructor=instructor,
                    start_time=start,
                    end_time=end,
                    status='scheduled'
                )
                self.stdout.write(self.style.SUCCESS(f"  Lesson {i} created."))
            except ValidationError as e:
                self.stdout.write(self.style.ERROR(f"  Lesson {i} unexpectedly blocked: {e}"))

        # 5. Test Default Duration
        self.stdout.write("Testing default duration...")
        try:
            lesson_default = Lesson.objects.create(
                student=s_paid,
                instructor=instructor,
                start_time=timezone.now() + datetime.timedelta(days=10),
                status='scheduled'
                # end_time omitted
            )
            duration = lesson_default.end_time - lesson_default.start_time
            if duration == datetime.timedelta(hours=1):
                 self.stdout.write(self.style.SUCCESS(f"  Default duration worked: {duration}"))
            else:
                 self.stdout.write(self.style.ERROR(f"  Default duration failed: {duration}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  Default duration test failed with error: {e}"))

        self.stdout.write(self.style.SUCCESS("Test scenario seeding complete."))
