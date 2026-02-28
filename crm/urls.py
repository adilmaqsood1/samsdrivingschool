from django.urls import path, re_path
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
    path("stripe/checkout/<int:invoice_id>/", views.stripe_checkout, name="stripe_checkout"),
    path("stripe/success/<int:invoice_id>/", views.stripe_success, name="stripe_success"),
    path("stripe/cancel/<int:invoice_id>/", views.stripe_cancel, name="stripe_cancel"),
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
    re_path(r"^(?P<template_name>[^/]+\.html)$", views.template_page, name="template_page"),
]
