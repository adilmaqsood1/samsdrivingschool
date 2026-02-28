from django.db import migrations
import ckeditor_uploader.fields


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0015_blog_content_ckeditor"),
    ]

    operations = [
        migrations.AlterField(
            model_name="blog",
            name="summary",
            field=ckeditor_uploader.fields.RichTextUploadingField(blank=True),
        ),
    ]

