import uuid

from django.db import migrations
from django.utils.text import slugify


def _unique_slug(Course, base_slug, course_id):
    base_slug = (base_slug or "")[:170] or uuid.uuid4().hex[:12]
    candidate = base_slug
    suffix = 2
    while Course.objects.exclude(pk=course_id).filter(slug=candidate).exists():
        suffix_str = f"-{suffix}"
        candidate = f"{base_slug[: (180 - len(suffix_str))]}{suffix_str}"
        suffix += 1
    return candidate


def fill_blank_course_slugs(apps, schema_editor):
    Course = apps.get_model("crm", "Course")
    qs = Course.objects.filter(slug="")
    for course in qs.iterator():
        course.slug = _unique_slug(Course, slugify(course.name), course.id)
        course.save(update_fields=["slug"])


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0013_course_catalog_fields_and_ckeditor"),
    ]

    operations = [
        migrations.RunPython(fill_blank_course_slugs, migrations.RunPython.noop),
    ]

