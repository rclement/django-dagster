from django.apps import AppConfig


class DjangoDagsterConfig(AppConfig):
    name = "django_dagster"
    verbose_name = "Dagster"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from django.contrib import admin

        from django_dagster.admin import DagsterJobAdmin, DagsterRunAdmin
        from django_dagster.models import DagsterJob, DagsterRun

        admin.site.register(DagsterJob, DagsterJobAdmin)
        admin.site.register(DagsterRun, DagsterRunAdmin)
