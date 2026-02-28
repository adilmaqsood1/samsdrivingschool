from decimal import Decimal

from django.db import migrations, models
import ckeditor_uploader.fields


def seed_courses_from_embedded_catalog(apps, schema_editor):
    Course = apps.get_model("crm", "Course")

    if Course.objects.exists():
        return

    catalog = {
        "mto-approved-beginner-driving-online-course": {
            "slug": "mto-approved-beginner-driving-online-course",
            "title": "MTO Approved Beginner Driving Online Course",
            "session": "30 Hours Online + 10 Hours In-Car",
            "image": "assets/getto.png",
            "price_display": "575.00",
            "price_label": "Per Person",
            "enroll_package": "MTO Approved Beginner Driving Online Course",
            "summary": (
                "This Ministry approved online BDE course includes 30 hours of online learning and 10 hours of "
                "one-on-one in-car training with a qualified driving instructor."
            ),
            "details": [
                "During your 10 hours in-car training you will be taught defensive driving, collision avoidance, "
                "parking maneuvers, and highway driving.",
                "In the last in-car session, your mock road test is conducted using the same exam sheet an examiner "
                "uses, so you understand how the marking works.",
                "Upon successful completion of this program students will be certified online with MTO.",
                "BDE graduates with driver licence history may be eligible for an insurance discount.",
            ],
            "program_includes": [
                "30 hours of online learning",
                "10 hours one on one in-car training",
                "Each in-car session 60 minutes",
                "Certified online for MTO road test and insurance discount",
                "Free pickup and drop off from home, work or school locally (only for in car training within 10km radius of Sams driving school)",
            ],
            "fees": {
                "regular": "$675 +HST",
                "promotion_savings": "$100 +HST",
                "pay_only": "$575 +HST",
                "hst_rate_percent": "13%",
                "hst_amount": "74.75",
                "total": "649.75",
            },
            "policies": [
                "No refund will be made after the first in car session or student start online homework portion (whichever comes first).",
            ],
            "features": [
                {"label": "Session", "value": "40 Hours"},
                {"label": "Lessons", "value": "10 In-Car Sessions"},
                {"label": "Students", "value": "Online + 1-on-1"},
            ],
        },
        "senior-driver-training": {
            "slug": "senior-driver-training",
            "title": "Senior Driver Training",
            "session": "55 Alive + In-Vehicle Evaluation",
            "image": "assets/senior.png",
            "price_display": "50.00",
            "price_label": "Per Person",
            "enroll_package": "Senior Driver Training",
            "summary": (
                "Senior Drivers have come under scrutiny due to incidents that occur when physical, visual, or cognitive "
                "changes affect driving performance."
            ),
            "details": [
                "The Ministry of Transportation runs a Driver Refresher Course lasting about 2 hours prior to the written exam.",
                "Some seniors pass the written test but can still show signs of poor cognitive skills during certain driving tasks.",
                "Certain prescriptions can affect motor skills, especially when mixed with other drugs. Doctors may be obligated to notify the Ministry of Transportation if a patient is a threat to themselves and the public.",
                "Driving is a privilege and each driver needs to understand what is at stake.",
            ],
            "g1_restrictions": [
                "Must be accompanied by a licensed G Driver in good standing for 4 years",
                "Cannot drive from 12 Midnight to 5:00 am",
                "Cannot drive on any highway with a posted speed limit of 80 or higher",
                "Zero percent blood alcohol concentration",
                "No more passengers than working seatbelts",
            ],
            "program_options": [
                {
                    "title": "55 Alive Group Program",
                    "subtitle": "5 hours in class + in-vehicle evaluation",
                    "text": (
                        "A group program for 10 or more, including 5 hours of in-class instruction (one day or split sessions) "
                        "and an evaluation for each participant in their own vehicle. Workbooks and a power point show are included, "
                        "and completion includes a certificate some insurance companies may recognize."
                    ),
                },
                {
                    "title": "Individual Evaluation Option",
                    "subtitle": "Review laws + in-vehicle assessment",
                    "text": (
                        "An individual can arrange an office session to review Ontario Highway Traffic Laws and then schedule an instructor "
                        "to evaluate their driving in their own vehicle by completing several manoeuvres. This can also be certified."
                    ),
                },
            ],
            "program_includes": [
                "One hour training as per MTO requirement including all Parallel parking, Reverse parking and HWY driving if required to pass Ministry Road Test",
            ],
            "fees": {
                "regular": "$50 +HST",
                "promotion_savings": "$0 +HST",
                "pay_only": "$50 +HST",
                "hst_rate_percent": "13%",
                "hst_amount": "6.50",
                "total": "56.50",
            },
            "features": [
                {"label": "Session", "value": "1 Hour + Evaluation"},
                {"label": "Lessons", "value": "Parking + Highway (as needed)"},
                {"label": "Students", "value": "Seniors"},
            ],
        },
        "dummy-test-course": {
            "slug": "dummy-test-course",
            "title": "Dummy Test Course",
            "session": "Online + In-Car",
            "image": "assets/samslogo.png",
            "price_display": "1.00",
            "price_label": "Per Person",
            "enroll_package": "Dummy Test Course",
            "summary": "This is a dummy course for testing purposes.",
            "details": [
                "This course is used to test the enrollment and payment flow.",
                "It includes a dummy session and a dummy invoice.",
            ],
            "program_includes": [
                "Dummy Online Learning",
                "Dummy In-Car Training",
            ],
            "fees": {
                "regular": "$1.00 +HST",
                "promotion_savings": "0$ +HST",
                "pay_only": "$1.00 +HST",
                "hst_rate_percent": "13%",
                "hst_amount": "0.13",
                "total": "1.13",
            },
            "policies": [
                "No refunds for dummy courses.",
            ],
            "features": [
                {"label": "Session", "value": "Dummy Session"},
                {"label": "Lessons", "value": "Dummy Lessons"},
                {"label": "Students", "value": "Testers"},
            ],
        },
    }

    for slug, data in catalog.items():
        Course.objects.create(
            name=data["title"],
            slug=slug,
            image=data.get("image", ""),
            summary=data.get("summary", ""),
            description=data.get("summary", ""),
            overview="",
            session=data.get("session", ""),
            price=Decimal(data.get("price_display") or "0"),
            price_label=data.get("price_label", "Per Person"),
            enroll_package=data.get("enroll_package", data.get("title", "")),
            details=data.get("details", []),
            program_includes=data.get("program_includes", []),
            program_options=data.get("program_options", []),
            g1_restrictions=data.get("g1_restrictions", []),
            fees=data.get("fees", {}),
            policies=data.get("policies", []),
            features=data.get("features", []),
            display_order=0,
            active=True,
            course_type="bde" if "beginner" in slug else "refresher",
        )


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0012_student_license_expiry_date_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="course",
            name="slug",
            field=models.SlugField(blank=True, max_length=180, unique=True),
        ),
        migrations.AddField(
            model_name="course",
            name="image",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="course",
            name="summary",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="course",
            name="description",
            field=ckeditor_uploader.fields.RichTextUploadingField(blank=True),
        ),
        migrations.AddField(
            model_name="course",
            name="overview",
            field=ckeditor_uploader.fields.RichTextUploadingField(blank=True),
        ),
        migrations.AddField(
            model_name="course",
            name="session",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="course",
            name="price_label",
            field=models.CharField(blank=True, default="Per Person", max_length=50),
        ),
        migrations.AddField(
            model_name="course",
            name="enroll_package",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="course",
            name="details",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="course",
            name="program_includes",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="course",
            name="program_options",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="course",
            name="g1_restrictions",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="course",
            name="fees",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="course",
            name="policies",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="course",
            name="features",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="course",
            name="display_order",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(seed_courses_from_embedded_catalog, migrations.RunPython.noop),
    ]

