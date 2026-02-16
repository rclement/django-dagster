import json

from django.conf import settings
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from . import client
from .models import DagsterJob, DagsterRun


# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------


class _DagsterAdminBase(admin.ModelAdmin):
    """Common permission logic for Dagster admin classes."""

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_staff

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_staff

    def _build_context(self, request, extra=None):
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "app_label": self.model._meta.app_label,
            "dagster_url": getattr(settings, "DAGSTER_URL", None),
        }
        if extra:
            context.update(extra)
        return context


# ---------------------------------------------------------------------------
# Jobs  (list + detail + "add" = trigger)
# ---------------------------------------------------------------------------


@admin.register(DagsterJob)
class DagsterJobAdmin(_DagsterAdminBase):
    def has_add_permission(self, request):
        return request.user.is_active and request.user.is_staff

    def get_urls(self):
        info = (self.model._meta.app_label, self.model._meta.model_name)
        return [
            path(
                "",
                self.admin_site.admin_view(self.job_list_view),
                name="%s_%s_changelist" % info,
            ),
            path(
                "add/",
                self.admin_site.admin_view(self.trigger_view),
                name="%s_%s_add" % info,
            ),
            path(
                "<str:job_name>/change/",
                self.admin_site.admin_view(self.job_detail_view),
                name="%s_%s_change" % info,
            ),
        ]

    # -- changelist ----------------------------------------------------------

    def job_list_view(self, request):
        jobs = None
        try:
            jobs = client.get_jobs()
        except Exception as e:
            self.message_user(
                request, f"Failed to connect to Dagster: {e}", messages.ERROR
            )

        # Sort jobs by name
        sort = request.GET.get("o")
        if jobs is not None and sort in ("name", "-name"):
            jobs = sorted(
                jobs, key=lambda j: j["name"],
                reverse=sort.startswith("-"),
            )

        context = self._build_context(request, {
            "title": "Dagster Jobs",
            "jobs": jobs,
            "current_sort": sort or "name",
        })
        return TemplateResponse(
            request, "django_dagster/job_list.html", context
        )

    # -- change (detail) -----------------------------------------------------

    def job_detail_view(self, request, job_name):
        job = None
        try:
            jobs = client.get_jobs()
            for j in jobs:
                if j["name"] == job_name:
                    job = j
                    break
        except Exception as e:
            self.message_user(
                request, f"Failed to connect to Dagster: {e}", messages.ERROR
            )

        if job is None:
            self.message_user(
                request, f"Job '{job_name}' not found", messages.ERROR
            )
            return HttpResponseRedirect(
                reverse("admin:django_dagster_dagsterjob_changelist")
            )

        # Fetch recent runs for this job
        recent_runs = None
        try:
            recent_runs = client.get_runs(job_name=job_name, limit=10)
        except Exception:
            pass

        context = self._build_context(request, {
            "title": "View Dagster Job",
            "job": job,
            "recent_runs": recent_runs,
        })
        return TemplateResponse(
            request, "django_dagster/job_detail.html", context
        )

    # -- add (trigger) -------------------------------------------------------

    def trigger_view(self, request):
        if request.method == "POST":
            job_name = request.POST.get("job_name", "").strip()
            config_json = request.POST.get("run_config", "").strip()

            if not job_name:
                self.message_user(
                    request, "Job name is required", messages.ERROR
                )
                return self._render_trigger_form(
                    request, run_config=config_json,
                )

            run_config = None
            if config_json:
                try:
                    run_config = json.loads(config_json)
                except json.JSONDecodeError as e:
                    self.message_user(
                        request, f"Invalid JSON config: {e}", messages.ERROR
                    )
                    return self._render_trigger_form(
                        request, job_name=job_name, run_config=config_json,
                    )

            try:
                run_id = client.submit_job(job_name, run_config=run_config)
                self.message_user(
                    request,
                    f"Job '{job_name}' triggered. Run ID: {run_id}",
                    messages.SUCCESS,
                )
                return HttpResponseRedirect(
                    reverse(
                        "admin:django_dagster_dagsterrun_change",
                        args=[run_id],
                    )
                )
            except Exception as e:
                self.message_user(
                    request, f"Failed to trigger job: {e}", messages.ERROR
                )
                return self._render_trigger_form(
                    request, job_name=job_name, run_config=config_json,
                )

        return self._render_trigger_form(
            request, job_name=request.GET.get("job", ""),
        )

    def _render_trigger_form(self, request, job_name="", run_config=""):
        jobs = None
        try:
            jobs = client.get_jobs()
        except Exception:
            pass

        context = self._build_context(request, {
            "title": "Trigger Job",
            "job_name": job_name,
            "run_config": run_config,
            "jobs": jobs,
        })
        return TemplateResponse(
            request, "django_dagster/trigger_job.html", context
        )


# ---------------------------------------------------------------------------
# Runs  (list + detail + cancel / retry)
# ---------------------------------------------------------------------------


@admin.register(DagsterRun)
class DagsterRunAdmin(_DagsterAdminBase):
    def has_add_permission(self, request):
        return False

    def get_urls(self):
        info = (self.model._meta.app_label, self.model._meta.model_name)
        return [
            path(
                "",
                self.admin_site.admin_view(self.run_list_view),
                name="%s_%s_changelist" % info,
            ),
            path(
                "<str:object_id>/change/",
                self.admin_site.admin_view(self.run_detail_view),
                name="%s_%s_change" % info,
            ),
            path(
                "<str:run_id>/cancel/",
                self.admin_site.admin_view(self.cancel_run_view),
                name="%s_%s_cancel" % info,
            ),
            path(
                "<str:run_id>/retry/",
                self.admin_site.admin_view(self.retry_run_view),
                name="%s_%s_retry" % info,
            ),
        ]

    # -- changelist ----------------------------------------------------------

    def run_list_view(self, request):
        job_name = request.GET.get("job")
        status = request.GET.get("status")
        statuses = [status] if status else None

        runs = None
        try:
            runs = client.get_runs(job_name=job_name, statuses=statuses)
        except Exception as e:
            self.message_user(
                request, f"Failed to connect to Dagster: {e}", messages.ERROR
            )

        # Fetch job list for the filter dropdown
        jobs = None
        try:
            jobs = client.get_jobs()
        except Exception:
            pass

        context = self._build_context(request, {
            "title": "Dagster Runs",
            "runs": runs,
            "jobs": jobs,
            "current_job": job_name,
            "current_status": status,
            "statuses": [
                "QUEUED",
                "NOT_STARTED",
                "STARTING",
                "STARTED",
                "SUCCESS",
                "FAILURE",
                "CANCELING",
                "CANCELED",
            ],
        })
        return TemplateResponse(
            request, "django_dagster/run_list.html", context
        )

    # -- change (detail) -----------------------------------------------------

    def run_detail_view(self, request, object_id):
        run = None
        try:
            run = client.get_run(object_id)
        except Exception as e:
            self.message_user(
                request, f"Failed to fetch run: {e}", messages.ERROR
            )

        if run is None:
            self.message_user(
                request, f"Run {object_id} not found", messages.ERROR
            )
            return HttpResponseRedirect(
                reverse("admin:django_dagster_dagsterrun_changelist")
            )

        can_cancel = run["status"] in (
            "QUEUED", "NOT_STARTED", "STARTING", "STARTED",
        )
        can_retry = run["status"] in ("FAILURE", "CANCELED")

        # Fetch recent runs for the same job
        related_runs = None
        try:
            related_runs = client.get_runs(
                job_name=run["jobName"], limit=10,
            )
        except Exception:
            pass

        context = self._build_context(request, {
            "title": f"Run {object_id}",
            "run": run,
            "can_cancel": can_cancel,
            "can_retry": can_retry,
            "related_runs": related_runs,
        })
        return TemplateResponse(
            request, "django_dagster/run_detail.html", context
        )

    # -- cancel --------------------------------------------------------------

    def cancel_run_view(self, request, run_id):
        if request.method == "POST":
            try:
                client.cancel_run(run_id)
                self.message_user(
                    request,
                    f"Run {run_id} cancellation requested",
                    messages.SUCCESS,
                )
            except Exception as e:
                self.message_user(
                    request, f"Failed to cancel run: {e}", messages.ERROR
                )
        return HttpResponseRedirect(
            reverse("admin:django_dagster_dagsterrun_change", args=[run_id])
        )

    # -- retry ---------------------------------------------------------------

    def retry_run_view(self, request, run_id):
        if request.method == "POST":
            try:
                new_run_id = client.retry_run(run_id)
                self.message_user(
                    request,
                    f"Run retried. New run ID: {new_run_id}",
                    messages.SUCCESS,
                )
                return HttpResponseRedirect(
                    reverse(
                        "admin:django_dagster_dagsterrun_change",
                        args=[new_run_id],
                    )
                )
            except Exception as e:
                self.message_user(
                    request, f"Failed to retry run: {e}", messages.ERROR
                )
        return HttpResponseRedirect(
            reverse("admin:django_dagster_dagsterrun_change", args=[run_id])
        )
