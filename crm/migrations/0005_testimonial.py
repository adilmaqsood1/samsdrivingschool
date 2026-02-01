from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0004_blog"),
    ]

    operations = [
        migrations.CreateModel(
            name="Testimonial",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("role", models.CharField(blank=True, max_length=120)),
                ("quote", models.TextField()),
                (
                    "rating",
                    models.PositiveSmallIntegerField(
                        default=5,
                        validators=[MinValueValidator(1), MaxValueValidator(5)],
                    ),
                ),
                ("photo", models.ImageField(blank=True, upload_to="testimonials/")),
                ("is_published", models.BooleanField(default=True)),
                ("display_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["display_order", "-updated_at"],
            },
        ),
    ]
