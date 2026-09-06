"""Point the home hero slides at the real Sam's Driving School photos.

0026 put every slide on ``assets/images/gallery/1.jpeg`` (a generic
placeholder). This assigns the three storefront photos by display order
and moves the model default onto the branded student-driver shot. Slides
an admin has pointed at some other asset are left alone.
"""

from django.db import migrations, models

PLACEHOLDERS = ["", "assets/images/gallery/1.jpeg", "assets/images/backgrounds/slider-1-1.png"]

SAMS_PHOTOS = [
    "assets/images/sams/hero-student-driver.jpg",
    "assets/images/sams/hero-car-street.jpg",
    "assets/images/sams/lesson-in-car.jpg",
]
DEFAULT_PHOTO = SAMS_PHOTOS[0]


def set_sams_photos(apps, schema_editor):
    HomeHeroSlide = apps.get_model("crm", "HomeHeroSlide")
    slides = list(
        HomeHeroSlide.objects.filter(background_asset__in=PLACEHOLDERS).order_by(
            "display_order", "id"
        )
    )
    for i, slide in enumerate(slides):
        slide.background_asset = SAMS_PHOTOS[i % len(SAMS_PHOTOS)]
        slide.save(update_fields=["background_asset"])


def restore_placeholder(apps, schema_editor):
    HomeHeroSlide = apps.get_model("crm", "HomeHeroSlide")
    HomeHeroSlide.objects.filter(background_asset__in=SAMS_PHOTOS).update(
        background_asset="assets/images/gallery/1.jpeg"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0026_homeheroslide_photo_background"),
    ]

    operations = [
        migrations.AlterField(
            model_name="homeheroslide",
            name="background_asset",
            field=models.CharField(blank=True, default=DEFAULT_PHOTO, max_length=255),
        ),
        migrations.RunPython(set_sams_photos, restore_placeholder),
    ]
