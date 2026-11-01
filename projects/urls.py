from django.urls import path

from projects import views

app_name = "projects"

urlpatterns = [
    path("billionaire-block", views.billionaire_block, name="billionaire_block"),
    path("projects", views.project_list, name="list"),
    path("projects/<slug:slug>", views.project_detail, name="detail"),
    path("projects/<slug:slug>/<slug:page_slug>", views.project_landing, name="landing"),
]
