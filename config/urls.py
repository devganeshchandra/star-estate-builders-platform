from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

from core.sitemaps import builder_sitemap
from core.views import healthz, robots_txt
from leads.views import submit_enquiry

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/enquiries", submit_enquiry, name="submit_enquiry"),
    path("sitemap.xml", builder_sitemap, name="sitemap"),
    path("healthz", healthz),
    path("robots.txt", robots_txt),
    path("", include("projects.urls")),
    path("", include("content.urls")),
    path("", include("core.urls")),
]

# Uploaded files. In production you may prefer to serve /media/ from the web
# server or a CDN instead; this keeps a single-process deployment working.
urlpatterns.insert(0, re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}))

handler404 = "core.errors.not_found"
