from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/dagster/", include("django_dagster.urls")),
    path("admin/", admin.site.urls),
]
