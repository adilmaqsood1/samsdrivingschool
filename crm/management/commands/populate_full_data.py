import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from crm.models import (
    Student, Instructor, Vehicle, Course, CourseSession, Enrollment, 
    Lesson, Invoice, Payment, Classroom
)

User = get_user_model()

class Command(BaseCommand):
    help = 'Populate database with comprehensive dummy data for all dashboard charts'

    def handle(self, *args, **options):
        self.stdout.write("Starting data population...")
        
        # 1. Create Instructors & Users
        instructors = []
        instructor_names = ['Michael Chen', 'Sarah Connor', 'David Kim', 'Emily Davis', 'Robert Wilson']
        
        for name in instructor_names:
            first, last = name.split()
            username = f"{first.lower()}.{last.lower()}"
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(username=username, email=f"{username}@example.com", password="password123", first_name=first, last_name=last)
                instructor = Instructor.objects.create(
                    user=user,
                    phone=f"555-{random.randint(100,999)}-{random.randint(1000,9999)}",
                    license_number=f"LIC-{random.randint(10000,99999)}",
                    hire_date=timezone.now().date() - timedelta(days=random.randint(30, 1000))
                )
                instructors.append(instructor)
            else:
                try:
                    instructors.append(Instructor.objects.get(user__username=username))
                except Instructor.DoesNotExist:
                    pass # User exists but not instructor, skip or handle if needed

        self.stdout.write(f"Ensured {len(instructors)} instructors.")

        # 2. Create Vehicles
        vehicles = []
        vehicle_data = [
            ('Toyota', 'Corolla', 2022), ('Honda', 'Civic', 2023), 
            ('Hyundai', 'Elantra', 2021), ('Mazda', '3', 2022), ('Kia', 'Forte', 2023)
        ]
        
        for make, model, year in vehicle_data:
            name = f"{make} {model}"
            vehicle, created = Vehicle.objects.get_or_create(
                name=name,
                defaults={
                    'make': make, 'model': model, 'year': year,
                    'plate_number': f"ABC-{random.randint(100,999)}",
                    'active': True
                }
            )
            vehicles.append(vehicle)
            
        self.stdout.write(f"Ensured {len(vehicles)} vehicles.")

        # 3. Create Courses & Sessions
        courses = []
        course_names = ['BDE Beginner', 'BDE Advanced', 'Defensive Driving', 'G2 Exit Prep', 'G Exit Prep']
        
        for name in course_names:
            course, _ = Course.objects.get_or_create(
                name=name,
                defaults={'price': random.choice([599, 699, 899, 1200]), 'active': True}
            )
            courses.append(course)

        sessions = []
        start_date = timezone.now().date() - timedelta(days=60)
        for course in courses:
            session, _ = CourseSession.objects.get_or_create(
                course=course,
                start_date=start_date,
                defaults={'location': 'Main Branch', 'capacity': 20}
            )
            sessions.append(session)

        # 4. Create Students & Enrollments
        students = []
        student_names = [
            'Alice Spring', 'Bob Summer', 'Charlie Fall', 'Diana Winter', 
            'Evan North', 'Fiona South', 'George East', 'Hannah West',
            'Ian Cloud', 'Julia Rain', 'Kevin Storm', 'Laura Snow',
            'Mike Thunder', 'Nina Wind', 'Oscar Frost', 'Paula Hail'
        ]
        
        license_statuses = ['G1', 'G2', 'G', 'None']

        for name in student_names:
            first, last = name.split()
            username = f"student.{first.lower()}"
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(username=username, email=f"{username}@example.com", password="password123", first_name=first, last_name=last)
                student = Student.objects.create(
                    user=user,
                    first_name=first,
                    last_name=last,
                    email=f"{username}@example.com",
                    phone=f"555-{random.randint(100,999)}-{random.randint(1000,9999)}",
                    license_status=random.choice(license_statuses)
                )
                students.append(student)
                
                # Enroll in a random session
                session = random.choice(sessions)
                enrollment, _ = Enrollment.objects.get_or_create(
                    student=student,
                    session=session,
                    defaults={'status': 'active', 'balance': 0}
                )
            else:
                try:
                    stud = Student.objects.get(user__username=username)
                    students.append(stud)
                except Student.DoesNotExist:
                    pass

        self.stdout.write(f"Ensured {len(students)} students.")

        # 5. Create Lessons (History & Future)
        # We need historical lessons for "Instructor Performance" and "Vehicle Utilization"
        # We need future lessons for "Scheduled Lessons (Next 7 Days)"
        
        now = timezone.now()
        
        # Historical (Last 6 months)
        for _ in range(100):
            days_ago = random.randint(1, 180)
            lesson_date = now - timedelta(days=days_ago)
            start_time = lesson_date.replace(hour=random.randint(8, 18), minute=0, second=0)
            end_time = start_time + timedelta(hours=1)
            
            student = random.choice(students)
            instructor = random.choice(instructors)
            vehicle = random.choice(vehicles)
            
            try:
                Lesson.objects.create(
                    student=student,
                    instructor=instructor,
                    vehicle=vehicle,
                    start_time=start_time,
                    end_time=end_time,
                    status='completed',
                    lesson_type='driving'
                )
            except ValidationError:
                continue

        # Future (Next 7 days)
        for _ in range(20):
            days_future = random.randint(0, 7)
            lesson_date = now + timedelta(days=days_future)
            start_time = lesson_date.replace(hour=random.randint(8, 18), minute=0, second=0)
            end_time = start_time + timedelta(hours=1)
            
            student = random.choice(students)
            instructor = random.choice(instructors)
            vehicle = random.choice(vehicles)
            
            # Find enrollment for student
            enrollment = Enrollment.objects.filter(student=student).first()
            session = enrollment.session if enrollment else None

            try:
                Lesson.objects.create(
                    student=student,
                    instructor=instructor,
                    vehicle=vehicle,
                    session=session,
                    start_time=start_time,
                    end_time=end_time,
                    status='scheduled',
                    lesson_type='driving'
                )
            except ValidationError:
                continue

        self.stdout.write("Created ~120 lessons (history & future).")

        # 6. Create Payments (Revenue Trend)
        # Create payments over last 12 months
        payment_methods = ['stripe', 'square', 'cash', 'transfer']
        
        for _ in range(80):
            days_ago = random.randint(0, 365)
            payment_date = now - timedelta(days=days_ago)
            amount = random.choice([100, 200, 500, 600, 800])
            
            # Need an invoice for payment
            student = random.choice(students)
            enrollment = Enrollment.objects.filter(student=student).first()
            if not enrollment: continue

            invoice = Invoice.objects.create(
                enrollment=enrollment,
                number=f"INV-{random.randint(10000, 99999)}",
                issue_date=payment_date.date(),
                total_amount=amount,
                status='paid'
            )
            
            Payment.objects.create(
                invoice=invoice,
                amount=amount,
                paid_at=payment_date,
                method=random.choice(payment_methods),
                status='completed'
            )

        self.stdout.write("Created ~80 payments for revenue trend.")
        self.stdout.write(self.style.SUCCESS("Comprehensive dummy data population complete."))
