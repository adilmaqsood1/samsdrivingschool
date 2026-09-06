"""Point the home hero slides at a real Sams Driving School photo.

Existing slides created before this change carry the old template
placeholder (``assets/images/backgrounds/slider-1-1.png``) or an empty
value; repoint those to the storefront photo. Slides an admin has already
customised to some other asset are left alone.
"""

from django.db import migrations, models

OLD_DEFAULT = "assets/images/backgrounds/slider-1-1.png"
NEW_DEFAULT = "assets/images/gallery/1.jpeg"


def set_photo_background(apps, schema_editor):
    HomeHeroSlide = apps.get_model("crm", "HomeHeroSlide")
    HomeHeroSlide.objects.filter(background_asset__in=["", OLD_DEFAULT]).update(
        background_asset=NEW_DEFAULT
    )


def restore_placeholder_background(apps, schema_editor):
    HomeHeroSlide = apps.get_model("crm", "HomeHeroSlide")
    HomeHeroSlide.objects.filter(background_asset=NEW_DEFAULT).update(
        background_asset=OLD_DEFAULT
    )


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0025_invoice_ga_client_id_invoice_ga_purchase_reported"),
    ]

    operations = [
        migrations.AlterField(
            model_name="homeheroslide",
            name="background_asset",
            field=models.CharField(
                blank=True, default="assets/images/gallery/1.jpeg", max_length=255
            ),
        ),
        migrations.RunPython(set_photo_background, restore_placeholder_background),
    ]
