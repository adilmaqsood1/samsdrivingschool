from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0021_remove_course_description_remove_course_overview_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            "ALTER TABLE crm_scheduledemail CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]

