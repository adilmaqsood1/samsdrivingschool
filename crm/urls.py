from django.urls import path
from . import views


urlpatterns = [
    path("lead/", views.lead_capture, name="lead_capture"),
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("enroll/", views.enroll_request, name="enroll_request"),
    path("enroll/process/", views.process_enrollment, name="process_enrollment"),
    path("enroll/<slug:course_slug>/", views.enroll_page, name="enroll_page"),
    path("lesson/request/", views.lesson_request, name="lesson_request"),
    path("notifications/unread-count/", views.notifications_unread_count, name="notifications_unread_count"),
    path("notifications/list/", views.notifications_list, name="notifications_list"),
    path(
        "notifications/<int:receipt_id>/mark-read/",
        views.notifications_mark_read,
        name="notifications_mark_read",
    ),
    path("gallery/", views.gallery, name="gallery"),
    path("notifications/mark-all-read/", views.notifications_mark_all_read, name="notifications_mark_all_read"),
    path("calendar/<uuid:token>/", views.calendar_feed, name="calendar_feed"),
    path("google-calendar/connect/", views.google_calendar_connect, name="google_calendar_connect"),
    path("google-calendar/callback/", views.google_calendar_callback, name="google_calendar_callback"),
    path("google-calendar/disconnect/", views.google_calendar_disconnect, name="google_calendar_disconnect"),
    # NOTE: the legacy /square/... and /stripe/... URLs are registered at the
    # project root in samsdriving/urls.py (not under the /crm/ include) and
    # remain the source of truth for payment flows.
]
