from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0023_invoice_payment_square_fields"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="invoice",
            name="stripe_checkout_session_id",
        ),
        migrations.RemoveField(
            model_name="invoice",
            name="stripe_customer_id",
        ),
        migrations.RemoveField(
            model_name="invoice",
            name="stripe_payment_intent_id",
        ),
        migrations.RemoveField(
            model_name="payment",
            name="stripe_payment_intent_id",
        ),
    ]

