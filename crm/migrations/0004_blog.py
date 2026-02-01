from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0003_conflictdetection_reminderlog"),
    ]

    operations = [
        migrations.CreateModel(
            name="Blog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("slug", models.SlugField(blank=True, max_length=220, unique=True)),
                ("summary", models.TextField(blank=True)),
                ("content", models.TextField()),
                ("author_name", models.CharField(blank=True, max_length=120)),
                ("author_title", models.CharField(blank=True, max_length=120)),
                ("cover_image", models.ImageField(blank=True, upload_to="blog_covers/")),
                ("author_image", models.ImageField(blank=True, upload_to="blog_authors/")),
                ("is_published", models.BooleanField(default=True)),
                ("published_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
