import json
from datetime import timedelta
from urllib.parse import quote
from django.conf import settings
from django.db.models import Count, Sum
from django.db.models.functions import TruncDay, TruncMonth
from django.utils import timezone
from .models import Enrollment, Invoice, Lead, Lesson, Payment, EnrollmentRequest, Student

def get_dashboard_data():
    data = {}
    
    # KPIs
    now = timezone.now()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    data['kpis'] = [
        {
            "label": "Total Students",
            "value": Student.objects.count(),
            "trend": "",
            "trend_class": "neutral"
        },
        {
            "label": "Revenue (Month)",
            "value": f"${(Payment.objects.filter(status='completed', paid_at__gte=start_of_month).aggregate(total=Sum('amount'))['total'] or 0):,.0f}",
            "trend": "This Month",
            "trend_class": "positive"
        },
        {
            "label": "New Leads",
            "value": Lead.objects.filter(created_at__gte=start_of_month).count(),
            "trend": "This Month",
            "trend_class": "neutral"
        },
        {
            "label": "Pending Enrollments",
            "value": EnrollmentRequest.objects.filter(status="new").count(),
            "trend": "Action Required",
            "trend_class": "negative" if EnrollmentRequest.objects.filter(status="new").count() > 0 else "neutral"
        },
    ]

    # Charts Helper
    def prepare_chart(qs, label_field, value_field, count_field="id", limit=None, is_date=False, date_format="%b %Y"):
        if is_date:
            rows = qs.annotate(key=label_field).values("key").annotate(value=value_field).order_by("key")
        else:
            rows = qs.values(label_field).annotate(value=value_field).order_by(f"-value")
            if limit:
                rows = rows[:limit]
        
        labels = []
        values = []
        for row in rows:
            key = row["key"] if is_date else row[label_field]
            if is_date and key:
                labels.append(key.strftime(date_format))
            else:
                labels.append(str(key or "Unknown"))
            values.append(float(row["value"] or 0))
        return json.dumps(labels), json.dumps(values)

    # Lead Status (Doughnut)
    labels, values = prepare_chart(Lead.objects.all(), "status", Count("id"))
    data['lead_status'] = {"labels": labels, "values": values}

    # Invoice Status (Pie)
    labels, values = prepare_chart(Invoice.objects.all(), "status", Count("id"))
    data['invoice_status'] = {"labels": labels, "values": values}

    # Leads by Month (Line) - Last 12 Months
    one_year_ago = timezone.now() - timedelta(days=365)
    labels, values = prepare_chart(
        Lead.objects.filter(created_at__gte=one_year_ago), 
        TruncMonth("created_at"), 
        Count("id"), 
        is_date=True
    )
    data['leads_by_month'] = {"labels": labels, "values": values}

    # Lesson Status (Radar) - Custom logic for radar labels
    lesson_rows = Lesson.objects.values("status").annotate(count=Count("id"))
    lesson_counts = {row["status"]: row["count"] for row in lesson_rows}
    lesson_labels = [label for _, label in Lesson.STATUS_CHOICES]
    lesson_values = [lesson_counts.get(val, 0) for val, _ in Lesson.STATUS_CHOICES]
    data['lesson_status'] = {"labels": json.dumps(lesson_labels), "values": json.dumps(lesson_values)}

    # Enrollments by Course (Bar)
    labels, values = prepare_chart(Enrollment.objects.all(), "session__course__name", Count("id"), limit=8)
    data['enrollments_by_course'] = {"labels": labels, "values": values}

    # Leads by Source (Bar)
    labels, values = prepare_chart(Lead.objects.all(), "source", Count("id"), limit=8)
    data['leads_by_source'] = {"labels": labels, "values": values}

    # Lessons Next 7 Days (Bar)
    start = timezone.now()
    end = start + timedelta(days=7)
    lessons_qs = Lesson.objects.filter(start_time__gte=start, start_time__lt=end, status="scheduled")
    rows = lessons_qs.annotate(day=TruncDay("start_time")).values("day").annotate(count=Count("id")).order_by("day")
    counts_by_day = {row["day"].date(): row["count"] for row in rows if row["day"]}
    days = [timezone.localdate(start) + timedelta(days=i) for i in range(7)]
    next_7_labels = [d.strftime("%a %d") for d in days]
    next_7_values = [counts_by_day.get(d, 0) for d in days]
    data['lessons_next_7_days'] = {"labels": json.dumps(next_7_labels), "values": json.dumps(next_7_values)}

    # Revenue by Month (Line) - Last 12 Months
    labels, values = prepare_chart(
        Payment.objects.filter(status="completed", paid_at__gte=one_year_ago), 
        TruncMonth("paid_at"), 
        Sum("amount"), 
        is_date=True
    )
    data['revenue_by_month'] = {"labels": labels, "values": values}

    # Invoice Amount by Status (Doughnut)
    labels, values = prepare_chart(Invoice.objects.all(), "status", Sum("total_amount"))
    data['invoice_amount_by_status'] = {"labels": labels, "values": values}

    # Vehicle Utilization (Bar) - Top 5 vehicles by lesson count
    labels, values = prepare_chart(Lesson.objects.filter(vehicle__isnull=False), "vehicle__name", Count("id"), limit=5)
    data['vehicle_utilization'] = {"labels": labels, "values": values}

    # Instructor Performance (Bar) - Top 5 instructors by completed lessons
    labels, values = prepare_chart(
        Lesson.objects.filter(instructor__isnull=False, status="completed"), 
        "instructor__user__first_name", 
        Count("id"), 
        limit=5
    )
    data['instructor_performance'] = {"labels": labels, "values": values}

    # Payment Method Distribution (Doughnut)
    labels, values = prepare_chart(Payment.objects.all(), "method", Count("id"))
    data['payment_method_distribution'] = {"labels": labels, "values": values}

    # Student License Status (Pie)
    labels, values = prepare_chart(Student.objects.exclude(license_status=""), "license_status", Count("id"))
    data['student_license_status'] = {"labels": labels, "values": values}

    # Sankey Data: Lead Source -> Status
    sankey_data = []
    # 1. Lead Source -> Status
    source_status_flows = Lead.objects.values('source', 'status').annotate(flow=Count('id'))
    
    # Normalize node names to prevent collisions if source and status have same name (unlikely but good practice)
    # But for display we want clean names. Sankey plugin handles distinct nodes by ID usually, but here we pass objects.
    # Let's simple format: {from: "Source: Website", to: "Status: New", flow: 10}
    
    for item in source_status_flows:
        src = item['source'] or "Unknown Source"
        stat = item['status'] or "Unknown Status"
        # Capitalize status for better display
        stat_display = stat.title()
        
        sankey_data.append({
            "from": src,
            "to": stat_display,
            "flow": item['flow']
        })
        
    data['lead_flow_sankey'] = json.dumps(sankey_data)

    # Recent Leads (Table)
    data['recent_leads'] = Lead.objects.order_by("-created_at")[:5]

    # Upcoming Lessons (Table)
    data['upcoming_lessons'] = Lesson.objects.filter(
        start_time__gte=timezone.now(), status="scheduled"
    ).order_by("start_time")[:5]

    # Recent Payments (Table)
    data['recent_payments'] = Payment.objects.filter(status="completed").order_by("-paid_at")[:5]
    
    embed_url = getattr(settings, "GOOGLE_CALENDAR_EMBED_URL", "") or ""
    calendar_id = getattr(settings, "GOOGLE_CALENDAR_ID", "") or ""
    tz = getattr(settings, "GOOGLE_CALENDAR_TIME_ZONE", "") or ""
    if not embed_url and calendar_id:
        embed_url = f"https://calendar.google.com/calendar/embed?src={quote(calendar_id)}"
        if tz:
            embed_url = f"{embed_url}&ctz={quote(tz)}"

    data["google_calendar_embed_url"] = embed_url
    data["google_calendar_id"] = calendar_id

    return data
