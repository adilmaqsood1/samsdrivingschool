"""Make the red Corolla the primary hero car, retire the black-car shot, and
tighten the hero copy.

Owner direction: the branded red Corolla is the face of the school; drop the
black "STUDENT DRIVER" car, and the landing copy needs work.

Image changes: slides still on the black-car photo are repointed to the
red-car photo; the lesson slide moves to the female-instructor photo.

Copy changes: the three near-identical "Are You Looking to ..." headlines are
replaced with distinct, benefit-led lines. A promo slide (e.g. "Summer
Special") or any headline an admin has already rewritten is left untouched.
"""

from django.db import migrations, models

RED_CAR = "assets/images/sams/hero-car-street.jpg"
INSTRUCTOR = "assets/images/sams/instructor-lesson.jpg"
# Photos this migration retires (files removed from the repo in the same change).
BLACK_CAR = "assets/images/sams/hero-student-driver.jpg"
OLD_LESSON = "assets/images/sams/lesson-in-car.jpg"

# The three stock slides all start line 1 with "Are You Looking"; line 2 tells
# them apart. old line-2 text -> (line 1, line 2, line 3, button text, background)
COPY = {
    "to learn": (
        "Pass Your", "Road Test", "the First Try", "Book a Lesson", RED_CAR,
    ),
    "for a Car for the": (
        "Learn to Drive", "with Milton &", "Burlington's Best", "See Our Programs", INSTRUCTOR,
    ),
    "to master": (
        "G2 & G Road", "Test Packages", "Instructor's car on test day", "Book Your Package", RED_CAR,
    ),
}


def apply_changes(apps, schema_editor):
    HomeHeroSlide = apps.get_model("crm", "HomeHeroSlide")
    # Any slide still on the retired black-car shot moves to the red car.
    HomeHeroSlide.objects.filter(background_asset=BLACK_CAR).update(background_asset=RED_CAR)
    # Rewrite the three stock headlines and pin their backgrounds explicitly.
    for slide in HomeHeroSlide.objects.all():
        if (slide.title_line_1 or "").strip() != "Are You Looking":
            continue
        new = COPY.get((slide.title_line_2 or "").strip())
        if not new:
            continue
        (slide.title_line_1, slide.title_line_2, slide.title_line_3,
         slide.button_text, slide.background_asset) = new
        slide.save(update_fields=[
            "title_line_1", "title_line_2", "title_line_3",
            "button_text", "background_asset",
        ])


def restore(apps, schema_editor):
    HomeHeroSlide = apps.get_model("crm", "HomeHeroSlide")
    # The retired photos are gone from the repo, so roll images back to the red car.
    reverse = {v[0]: line2 for line2, v in COPY.items()}
    for slide in HomeHeroSlide.objects.all():
        line2 = reverse.get((slide.title_line_1 or "").strip())
        if line2:
            slide.title_line_1 = "Are You Looking"
            slide.title_line_2 = line2
            slide.background_asset = RED_CAR
            slide.save(update_fields=["title_line_1", "title_line_2", "background_asset"])


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0027_hero_sams_photos"),
    ]

    operations = [
        migrations.AlterField(
            model_name="homeheroslide",
            name="background_asset",
            field=models.CharField(blank=True, default=RED_CAR, max_length=255),
        ),
        migrations.RunPython(apply_changes, restore),
    ]
