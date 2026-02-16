import logging

from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html

from django_dagster import get_run, submit_job

from .models import ReportRequest

logger = logging.getLogger(__name__)


@admin.register(ReportRequest)
class ReportRequestAdmin(admin.ModelAdmin):
    list_display = ["title", "report_type", "num_sections", "status_display", "run_link", "created_by", "created_at"]
    list_filter = ["report_type", "status"]
    readonly_fields = ["dagster_run_link", "status", "created_by", "created_at", "updated_at"]
    fields = ["title", "report_type", "num_sections", "dagster_run_link", "status", "created_by", "created_at", "updated_at"]

    def get_fields(self, request, obj=None):
        if obj is None:
            # Add form: only show the user-facing fields
            return ["title", "report_type", "num_sections"]
        return super().get_fields(request, obj)

    def status_display(self, obj):
        """Show status with colour coding."""
        colours = {
            "SUCCESS": "#28a745",
            "FAILURE": "#dc3545",
            "CANCELED": "#6c757d",
            "STARTED": "#007bff",
            "STARTING": "#007bff",
            "QUEUED": "#ffc107",
            "NOT_STARTED": "#ffc107",
        }
        colour = colours.get(obj.status, "#6c757d")
        return format_html('<span style="color:{}; font-weight:bold">{}</span>', colour, obj.status or "—")

    status_display.short_description = "Status"

    def dagster_run_link(self, obj):
        """Link to the built-in Dagster run admin detail page (used in detail view)."""
        if not obj.dagster_run_id:
            return "—"
        url = reverse("admin:django_dagster_dagsterrun_change", args=[obj.dagster_run_id])
        return format_html('<a href="{}">{}</a>', url, obj.dagster_run_id)

    dagster_run_link.short_description = "Dagster Run"

    def run_link(self, obj):
        """Shorter link for the list view."""
        if not obj.dagster_run_id:
            return "—"
        url = reverse("admin:django_dagster_dagsterrun_change", args=[obj.dagster_run_id])
        return format_html('<a href="{}">{}</a>', url, obj.dagster_run_id[:8])

    run_link.short_description = "Dagster Run"

    def save_model(self, request, obj, form, change):
        if not change:
            # New report request: trigger the Dagster job
            obj.created_by = request.user
            run_config = {
                "ops": {
                    "generate_report": {
                        "config": {
                            "report_name": f"{obj.report_type}_{obj.title}",
                            "num_sections": obj.num_sections,
                        }
                    }
                }
            }
            try:
                run_id = submit_job("generate_report_job", run_config=run_config)
                obj.dagster_run_id = run_id
                obj.status = "QUEUED"
                messages.success(request, f"Dagster job triggered — run ID: {run_id}")
            except Exception as e:
                logger.exception("Failed to trigger Dagster job")
                messages.error(request, f"Failed to trigger Dagster job: {e}")
        super().save_model(request, obj, form, change)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        # Refresh status from Dagster before rendering the detail view
        try:
            obj = self.get_object(request, object_id)
            if obj and obj.dagster_run_id:
                run = get_run(obj.dagster_run_id)
                if run and run["status"] != obj.status:
                    obj.status = run["status"]
                    obj.save(update_fields=["status", "updated_at"])
        except Exception:
            logger.exception("Failed to refresh Dagster run status")
        return super().change_view(request, object_id, form_url, extra_context)

    def has_change_permission(self, request, obj=None):
        # Report requests are immutable once created
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
