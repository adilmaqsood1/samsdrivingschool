from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0022_convert_scheduledemail_to_utf8mb4"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="square_order_id",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="invoice",
            name="square_payment_id",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="invoice",
            name="square_payment_link_id",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="payment",
            name="square_payment_id",
            field=models.CharField(blank=True, max_length=200),
        ),
    ]

