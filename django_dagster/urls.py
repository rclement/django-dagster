from django.urls import path

from . import views

app_name = "dagster"

urlpatterns = [
    path("", views.job_list, name="job_list"),
    path("runs/", views.run_list, name="run_list"),
    path("runs/<str:run_id>/", views.run_detail, name="run_detail"),
    path("runs/<str:run_id>/cancel/", views.cancel_run_view, name="cancel_run"),
    path("runs/<str:run_id>/retry/", views.retry_run_view, name="retry_run"),
    path("trigger/", views.trigger_job, name="trigger_job"),
]
