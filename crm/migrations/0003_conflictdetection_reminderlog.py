from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0002_invoice_stripe_checkout_session_id_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConflictDetection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "conflict_type",
                    models.CharField(
                        choices=[
                            ("instructor", "Instructor Conflict"),
                            ("vehicle", "Vehicle Conflict"),
                            ("classroom", "Classroom Conflict"),
                        ],
                        max_length=20,
                    ),
                ),
                ("detected_at", models.DateTimeField(auto_now_add=True)),
                ("resolved", models.BooleanField(default=False)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                (
                    "conflicting_lesson",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="conflicts_with",
                        to="crm.lesson",
                    ),
                ),
                (
                    "lesson",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="conflict_detections",
                        to="crm.lesson",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ReminderLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reminder_type", models.CharField(choices=[("lesson_24h", "Lesson 24h")], max_length=30)),
                (
                    "channel",
                    models.CharField(
                        choices=[("email", "Email"), ("sms", "SMS")], default="email", max_length=20
                    ),
                ),
                ("scheduled_for", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "lesson",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reminder_logs",
                        to="crm.lesson",
                    ),
                ),
            ],
        ),
    ]
