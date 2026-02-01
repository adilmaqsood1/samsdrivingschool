from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from crm import views as crm_views


urlpatterns = [
    path("jet/", include(("jet.urls", "jet"), namespace="jet")),
    path("jet/dashboard/", include(("jet.dashboard.urls", "jet-dashboard"), namespace="jet-dashboard")),
    path("admin/", admin.site.urls),
    path("crm/", include("crm.urls")),
    path("", crm_views.index_page, name="home"),
    path("index/", crm_views.index_page, name="index_page"),
    path("about/", crm_views.about_page, name="about_page"),
    path("team/", crm_views.team_page, name="team_page"),
    path("team-details/", crm_views.team_details_page, name="team_details_page"),
    path("gallery/", crm_views.gallery_page, name="gallery_page"),
    path("faq/", crm_views.faq_page, name="faq_page"),
    path("login/", crm_views.login_page, name="login_page"),
    path("404/", crm_views.not_found_page, name="not_found_page"),
    path("course/", crm_views.course_page, name="course_page"),
    path("course-details/", crm_views.course_details_page, name="course_details_page"),
    path("blogs/", crm_views.blog_grid_right_page, name="blog_page"),
    path("blogs/<slug:slug>/", crm_views.blog_details_right_page, name="blog_details"),
    path("contact/", crm_views.contact_page, name="contact_page"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
