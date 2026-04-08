from django.db import migrations


def _convert_scheduledemail_to_utf8mb4(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    schema_editor.execute(
        "ALTER TABLE crm_scheduledemail CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0021_remove_course_description_remove_course_overview_and_more"),
    ]

    operations = [
        migrations.RunPython(_convert_scheduledemail_to_utf8mb4, reverse_code=migrations.RunPython.noop),
    ]
