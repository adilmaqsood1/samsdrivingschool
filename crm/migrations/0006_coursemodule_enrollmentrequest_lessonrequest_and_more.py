from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('crm', '0005_testimonial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseModule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=150)),
                ('description', models.TextField(blank=True)),
                ('module_type', models.CharField(choices=[('theory', 'Theory'), ('homework', 'Homework'), ('driving', 'Driving')], default='theory', max_length=20)),
                ('order', models.PositiveIntegerField(default=1)),
                ('hours_required', models.PositiveIntegerField(default=0)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='modules', to='crm.course')),
            ],
        ),
        migrations.CreateModel(
            name='EnrollmentRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('email', models.EmailField(max_length=254)),
                ('phone', models.CharField(blank=True, max_length=50)),
                ('package', models.CharField(blank=True, max_length=150)),
                ('preferred_location', models.CharField(blank=True, max_length=120)),
                ('preferred_schedule', models.CharField(blank=True, max_length=200)),
                ('notes', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('new', 'New'), ('contacted', 'Contacted'), ('converted', 'Converted'), ('closed', 'Closed')], default='new', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='LessonRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('email', models.EmailField(max_length=254)),
                ('phone', models.CharField(blank=True, max_length=50)),
                ('preferred_date', models.DateField(blank=True, null=True)),
                ('preferred_time', models.CharField(blank=True, max_length=100)),
                ('notes', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('new', 'New'), ('scheduled', 'Scheduled'), ('closed', 'Closed')], default='new', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AddField(
            model_name='communicationlog',
            name='recipient_phone',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='scheduledemail',
            name='channel',
            field=models.CharField(choices=[('email', 'Email'), ('sms', 'SMS')], default='email', max_length=20),
        ),
        migrations.AddField(
            model_name='scheduledemail',
            name='recipient_phone',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.CreateModel(
            name='StudentModuleProgress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('not_started', 'Not Started'), ('in_progress', 'In Progress'), ('completed', 'Completed')], default='not_started', max_length=20)),
                ('score', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('enrollment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='module_progress', to='crm.enrollment')),
                ('module', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='progress', to='crm.coursemodule')),
            ],
        ),
        migrations.CreateModel(
            name='MinistrySubmission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('submitted', 'Submitted'), ('failed', 'Failed')], default='pending', max_length=20)),
                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                ('external_reference', models.CharField(blank=True, max_length=200)),
                ('file', models.FileField(blank=True, null=True, upload_to='ministry_submissions/')),
                ('enrollment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ministry_submissions', to='crm.enrollment')),
            ],
        ),
        migrations.CreateModel(
            name='LessonAttendance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('attended', 'Attended'), ('missed', 'Missed'), ('cancelled', 'Cancelled'), ('rescheduled', 'Rescheduled')], default='attended', max_length=20)),
                ('notes', models.TextField(blank=True)),
                ('recorded_at', models.DateTimeField(auto_now_add=True)),
                ('lesson', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='attendance', to='crm.lesson')),
                ('recorded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lesson_attendance', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
