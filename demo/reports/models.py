from django.conf import settings
from django.db import models


class ReportRequest(models.Model):
    REPORT_TYPES = [
        ("daily_summary", "Daily Summary"),
        ("weekly_digest", "Weekly Digest"),
        ("monthly_analysis", "Monthly Analysis"),
    ]

    title = models.CharField(max_length=200)
    report_type = models.CharField(max_length=50, choices=REPORT_TYPES)
    num_sections = models.PositiveIntegerField(
        default=3,
        help_text="Number of sections to include in the report.",
    )
    dagster_run_id = models.CharField(max_length=64, blank=True, editable=False)
    status = models.CharField(max_length=32, blank=True, default="", editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.get_report_type_display()})"
