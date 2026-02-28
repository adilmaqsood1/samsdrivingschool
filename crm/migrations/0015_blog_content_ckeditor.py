from django.db import migrations
import ckeditor_uploader.fields


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0014_fill_blank_course_slugs"),
    ]

    operations = [
        migrations.AlterField(
            model_name="blog",
            name="content",
            field=ckeditor_uploader.fields.RichTextUploadingField(blank=True),
        ),
    ]

