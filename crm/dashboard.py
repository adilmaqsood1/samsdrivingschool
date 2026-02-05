from jet.dashboard.dashboard import Dashboard
from jet.dashboard import modules
from datetime import timedelta
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDay, TruncMonth
from django.conf import settings
from django.utils import timezone

from .models import Enrollment, Invoice, Lead, Lesson, Payment


class BaseChartModule(modules.DashboardModule):
    template = "jet.dashboard/modules/analytics_charts.html"
    deletable = False
    chart_type = "bar"
    dataset_label = ""
    subtitle = ""
    x_title = ""
    y_title = ""
    min_height = 260
    supports_range_filter = True
    default_range_days = 180

    def get_range_value(self, request):
        if not request:
            return str(self.default_range_days)
        value = (request.GET.get("dash_range") or "").strip().lower()
        if value in {"30", "90", "180", "365", "all"}:
            return value
        return str(self.default_range_days)

    def get_since(self, request):
        value = self.get_range_value(request)
        if value == "all":
            return None
        try:
            days = int(value)
        except (TypeError, ValueError):
            days = self.default_range_days
        return timezone.now() - timedelta(days=days)

    def build_chart_data(self, request=None, since=None):
        return [], []

    def init_with_context(self, context):
        request = context.get("request")
        since = self.get_since(request) if self.supports_range_filter else None
        range_value = self.get_range_value(request) if self.supports_range_filter else ""
        range_label = ""
        if self.supports_range_filter:
            range_label = {
                "30": "Last 30 days",
                "90": "Last 90 days",
                "180": "Last 180 days",
                "365": "Last 365 days",
                "all": "All time",
            }.get(range_value, "")
        subtitle = self.subtitle
        if range_label:
            subtitle = f"{subtitle} • {range_label}" if subtitle else range_label
        labels, values = self.build_chart_data(request=request, since=since)
        stable_id = getattr(self.model, "id", None) or self.title.lower().replace(" ", "-")
        root_id = f"chart-widget-{stable_id}"
        canvas_id = f"chart-canvas-{stable_id}"
        summary_id = f"chart-summary-{stable_id}"
        labels_script_id = f"chart-labels-{stable_id}"
        values_script_id = f"chart-values-{stable_id}"

        self.context.update(
            {
                "root_id": root_id,
                "canvas_id": canvas_id,
                "summary_id": summary_id,
                "labels_script_id": labels_script_id,
                "values_script_id": values_script_id,
                "chart_title": self.title,
                "chart_type": self.chart_type,
                "dataset_label": self.dataset_label,
                "chart_subtitle": subtitle,
                "x_title": self.x_title,
                "y_title": self.y_title,
                "chart_labels": labels,
                "chart_values": values,
                "min_height": self.min_height,
                "supports_range_filter": self.supports_range_filter,
                "dash_range": range_value,
            }
        )


class LeadStatusDoughnutModule(BaseChartModule):
    title = "Lead Status"
    chart_type = "doughnut"
    dataset_label = "Leads"
    subtitle = "Pipeline distribution"

    def build_chart_data(self, request=None, since=None):
        qs = Lead.objects.all()
        if since:
            qs = qs.filter(created_at__gte=since)
        rows = (
            qs.values("status")
            .annotate(count=Count("id"))
            .order_by("status")
        )
        labels = [row["status"] or "Unknown" for row in rows]
        values = [row["count"] for row in rows]
        return labels, values


class InvoiceStatusPieModule(BaseChartModule):
    title = "Invoice Status"
    chart_type = "pie"
    dataset_label = "Invoices"
    subtitle = "Billing overview"

    def build_chart_data(self, request=None, since=None):
        qs = Invoice.objects.all()
        if since:
            qs = qs.filter(issue_date__gte=timezone.localdate(since))
        rows = (
            qs.values("status")
            .annotate(count=Count("id"))
            .order_by("status")
        )
        labels = [row["status"] or "Unknown" for row in rows]
        values = [row["count"] for row in rows]
        return labels, values


class LeadsByMonthLineModule(BaseChartModule):
    title = "Leads by Month"
    chart_type = "line"
    dataset_label = "Leads"
    subtitle = "Trend"
    x_title = "Month"
    y_title = "Leads"

    def build_chart_data(self, request=None, since=None):
        qs = Lead.objects.all()
        if since:
            qs = qs.filter(created_at__gte=since)
        rows = (
            qs
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )
        labels = [row["month"].strftime("%b %Y") for row in rows if row["month"]]
        values = [row["count"] for row in rows]
        return labels, values


class LessonStatusRadarModule(BaseChartModule):
    title = "Lesson Status"
    chart_type = "radar"
    dataset_label = "Lessons"
    subtitle = "By status"

    def build_chart_data(self, request=None, since=None):
        qs = Lesson.objects.all()
        if since:
            qs = qs.filter(start_time__gte=since)
        rows = qs.values("status").annotate(count=Count("id"))
        counts_by_status = {row["status"]: row["count"] for row in rows}

        labels = []
        values = []
        for value, label in getattr(Lesson, "STATUS_CHOICES", ()):
            labels.append(label)
            values.append(counts_by_status.get(value, 0))

        unknown_count = 0
        for status_value, count in counts_by_status.items():
            if status_value not in dict(getattr(Lesson, "STATUS_CHOICES", ())):
                unknown_count += count
        if unknown_count:
            labels.append("Unknown")
            values.append(unknown_count)

        return labels, values


class EnrollmentsByCourseBarModule(BaseChartModule):
    title = "Enrollments by Course"
    chart_type = "bar"
    dataset_label = "Enrollments"
    subtitle = "Top courses"
    x_title = "Course"
    y_title = "Enrollments"
    min_height = 320

    def build_chart_data(self, request=None, since=None):
        qs = Enrollment.objects.all()
        if since:
            qs = qs.filter(enrolled_at__gte=since)
        rows = (
            qs.values("session__course__name")
            .annotate(count=Count("id"))
            .order_by("-count", "session__course__name")[:8]
        )
        labels = [row["session__course__name"] or "Unknown" for row in rows]
        values = [row["count"] for row in rows]
        return labels, values


class LeadsBySourceBarModule(BaseChartModule):
    title = "Leads by Source"
    chart_type = "bar"
    dataset_label = "Leads"
    subtitle = "Top sources"
    x_title = "Source"
    y_title = "Leads"
    min_height = 320

    def build_chart_data(self, request=None, since=None):
        qs = Lead.objects.all()
        if since:
            qs = qs.filter(created_at__gte=since)
        rows = (
            qs.values("source")
            .annotate(count=Count("id"))
            .order_by("-count", "source")[:8]
        )
        labels = []
        values = []
        for row in rows:
            source = (row["source"] or "").strip()
            labels.append(source or "Unknown")
            values.append(row["count"])
        return labels, values


class LessonsNext7DaysBarModule(BaseChartModule):
    title = "Lessons Next 7 Days"
    chart_type = "bar"
    dataset_label = "Lessons"
    subtitle = "Scheduled lessons"
    x_title = "Day"
    y_title = "Lessons"
    min_height = 320
    supports_range_filter = False

    def build_chart_data(self, request=None, since=None):
        start = timezone.now()
        end = start + timedelta(days=7)

        rows = (
            Lesson.objects.filter(start_time__gte=start, start_time__lt=end, status="scheduled")
            .annotate(day=TruncDay("start_time"))
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        )
        counts_by_day = {}
        for row in rows:
            day = row["day"]
            if day:
                counts_by_day[day.date()] = row["count"]

        base_date = timezone.localdate(start)
        days = [base_date + timedelta(days=i) for i in range(7)]
        labels = [d.strftime("%a %d") for d in days]
        values = [counts_by_day.get(d, 0) for d in days]
        return labels, values


class RevenueByMonthLineModule(BaseChartModule):
    title = "Revenue by Month"
    chart_type = "line"
    dataset_label = "Revenue"
    subtitle = "Payments completed"
    x_title = "Month"
    y_title = "Amount"

    def build_chart_data(self, request=None, since=None):
        qs = Payment.objects.filter(status="completed")
        if since:
            qs = qs.filter(paid_at__gte=since)
        rows = (
            qs
            .annotate(month=TruncMonth("paid_at"))
            .values("month")
            .annotate(total=Sum("amount"))
            .order_by("month")
        )
        labels = [row["month"].strftime("%b %Y") for row in rows if row["month"]]
        values = [float(row["total"] or 0) for row in rows]
        return labels, values


class InvoiceAmountByStatusDoughnutModule(BaseChartModule):
    title = "Invoice Amount by Status"
    chart_type = "doughnut"
    dataset_label = "Amount"
    subtitle = "Sum of invoice totals"

    def build_chart_data(self, request=None, since=None):
        qs = Invoice.objects.all()
        if since:
            qs = qs.filter(issue_date__gte=timezone.localdate(since))
        rows = (
            qs.values("status")
            .annotate(total=Sum("total_amount"))
            .order_by("status")
        )
        labels = [row["status"] or "Unknown" for row in rows]
        values = [float(row["total"] or 0) for row in rows]
        return labels, values


class GoogleCalendarModule(modules.DashboardModule):
    title = "Google Calendar"
    template = "jet.dashboard/modules/google_calendar.html"
    deletable = False
    min_height = 520

    def init_with_context(self, context):
        from .models import CalendarAccount

        request = context.get("request")
        user = getattr(request, "user", None)
        account = None
        if user and user.is_authenticated:
            account = (
                CalendarAccount.objects.filter(owner=user, provider="google", active=True)
                .order_by("-created_at")
                .first()
            )

        embed_url = getattr(settings, "GOOGLE_CALENDAR_EMBED_URL", "") or ""
        is_oauth_configured = bool(getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "")) and bool(
            getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "")
        )
        self.context.update(
            {
                "embed_url": embed_url,
                "account_email": getattr(account, "email", "") if account else "",
                "is_connected": bool(account),
                "is_oauth_configured": is_oauth_configured,
                "connect_url": "/crm/oauth/google/start/",
                "manage_url": "/admin/crm/calendaraccount/",
                "min_height": self.min_height,
            }
        )


class KPIModule(modules.DashboardModule):
    title = "Key Performance Indicators"
    template = "jet.dashboard/modules/kpi_summary.html"
    deletable = False
    col_width = 12

    def init_with_context(self, context):
        from .models import EnrollmentRequest, Lead, Payment, Student

        total_students = Student.objects.count()
        
        # Revenue this month
        now = timezone.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        revenue_month = Payment.objects.filter(
            status="completed", paid_at__gte=start_of_month
        ).aggregate(total=Sum("amount"))["total"] or 0

        # New leads this month
        new_leads = Lead.objects.filter(created_at__gte=start_of_month).count()
        
        # Pending Enrollments
        pending_enrollments = EnrollmentRequest.objects.filter(status="new").count()

        self.kpis = [
            {"label": "Total Students", "value": total_students, "trend": "", "trend_class": "neutral"},
            {"label": "Revenue (Month)", "value": f"${revenue_month:,.0f}", "trend": "This Month", "trend_class": "positive"},
            {"label": "New Leads", "value": new_leads, "trend": "This Month", "trend_class": "neutral"},
            {"label": "Pending Enrollments", "value": pending_enrollments, "trend": "Action Required", "trend_class": "negative" if pending_enrollments > 0 else "neutral"},
        ]


class CustomIndexDashboard(Dashboard):
    columns = 3

    def init_with_context(self, context):
        from jet.dashboard.models import UserDashboardModule

        chart_modules = [
            ("crm.dashboard.KPIModule", KPIModule.title, 0, 0),
            ("crm.dashboard.LeadStatusDoughnutModule", LeadStatusDoughnutModule.title, 0, 1),
            ("crm.dashboard.InvoiceStatusPieModule", InvoiceStatusPieModule.title, 1, 1),
            ("crm.dashboard.LeadsByMonthLineModule", LeadsByMonthLineModule.title, 2, 1),
            ("crm.dashboard.LessonStatusRadarModule", LessonStatusRadarModule.title, 0, 2),
            ("crm.dashboard.EnrollmentsByCourseBarModule", EnrollmentsByCourseBarModule.title, 1, 2),
            ("crm.dashboard.LeadsBySourceBarModule", LeadsBySourceBarModule.title, 0, 3),
            ("crm.dashboard.LessonsNext7DaysBarModule", LessonsNext7DaysBarModule.title, 1, 3),
            ("crm.dashboard.RevenueByMonthLineModule", RevenueByMonthLineModule.title, 2, 2),
            ("crm.dashboard.InvoiceAmountByStatusDoughnutModule", InvoiceAmountByStatusDoughnutModule.title, 2, 3),
        ]
        other_modules = [
            ("crm.dashboard.GoogleCalendarModule", GoogleCalendarModule.title, 2, 1),
        ]

        user = context["request"].user
        if user.is_authenticated:
            base_qs = UserDashboardModule.objects.filter(user=user).filter(
                Q(app_label__isnull=True) | Q(app_label="")
            )
            has_legacy_module = base_qs.filter(
                module="jet.dashboard.modules.DashboardModule"
            ).exists()
            if has_legacy_module:
                base_qs.delete()

            base_qs.filter(module="crm.dashboard.AnalyticsChartsModule").delete()

            for module_path, title, column, order in chart_modules:
                exists = base_qs.filter(module=module_path).exists()
                if exists:
                    continue
                base_qs.filter(column=column, order__gte=order).update(order=F("order") + 1)
                UserDashboardModule.objects.create(
                    title=title,
                    app_label=None,
                    user=user,
                    module=module_path,
                    column=column,
                    order=order,
                    settings="",
                    children="",
                )
            for module_path, title, column, order in other_modules:
                exists = base_qs.filter(module=module_path).exists()
                if exists:
                    continue
                base_qs.filter(column=column, order__gte=order).update(order=F("order") + 1)
                UserDashboardModule.objects.create(
                    title=title,
                    app_label=None,
                    user=user,
                    module=module_path,
                    column=column,
                    order=order,
                    settings="",
                    children="",
                )

        self.children.append(LeadStatusDoughnutModule(column=0, order=0))
        self.children.append(InvoiceStatusPieModule(column=1, order=0))
        self.children.append(LeadsByMonthLineModule(column=2, order=0))
        self.children.append(LessonStatusRadarModule(column=0, order=1))
        self.children.append(EnrollmentsByCourseBarModule(column=1, order=1))
        self.children.append(LeadsBySourceBarModule(column=0, order=2))
        self.children.append(LessonsNext7DaysBarModule(column=1, order=2))
        self.children.append(RevenueByMonthLineModule(column=2, order=2))
        self.children.append(InvoiceAmountByStatusDoughnutModule(column=2, order=3))
        self.children.append(GoogleCalendarModule(column=2, order=1))
        self.children.append(
            modules.AppList(
                title="CRM",
                models=(
                    "crm.models.Lead",
                    "crm.models.Student",
                    "crm.models.Course",
                    "crm.models.CourseSession",
                    "crm.models.Enrollment",
                    "crm.models.Lesson",
                    "crm.models.Invoice",
                    "crm.models.Payment",
                    "crm.models.Certificate",
                ),
            )
        )
        self.children.append(
            modules.AppList(
                title="Operations",
                models=(
                    "crm.models.Instructor",
                    "crm.models.Vehicle",
                    "crm.models.Classroom",
                    "crm.models.PaymentPlan",
                    "crm.models.PaymentSchedule",
                    "crm.models.CommunicationTemplate",
                    "crm.models.CommunicationLog",
                    "crm.models.StaffProfile",
                ),
            )
        )
        self.children.append(modules.RecentActions(title="Recent Actions", limit=10))
