import json
from typing import Any

from django.conf import settings
from django.contrib import admin, messages
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseRedirect,
)
from django.template.response import TemplateResponse
from django.urls import URLPattern, path, reverse

from . import client
from .models import DagsterJob, DagsterRun


# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------


class _DagsterAdminBase(admin.ModelAdmin):  # type: ignore[type-arg]
    """Common permission logic for Dagster admin classes."""

    @staticmethod
    def _permissions_enabled() -> bool:
        return getattr(settings, "DAGSTER_PERMISSIONS_ENABLED", False)

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_view_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        if self._permissions_enabled():
            return super().has_view_permission(request, obj)
        return bool(request.user.is_active and request.user.is_staff)

    def has_module_permission(self, request: HttpRequest) -> bool:
        if self._permissions_enabled():
            return super().has_module_permission(request)
        return bool(request.user.is_active and request.user.is_staff)

    def _check_view_perm(self, request: HttpRequest) -> HttpResponse | None:
        """Return HttpResponseForbidden if permissions are enabled and the
        user lacks view permission for this model, otherwise None."""
        if self._permissions_enabled() and not self.has_view_permission(request):
            return HttpResponseForbidden()
        return None

    def _can_access_dagster_ui(self, request: HttpRequest) -> bool:
        """Check whether the current user may see Dagster UI links."""
        if not self._permissions_enabled():
            return True
        return bool(request.user.has_perm("django_dagster.access_dagster_ui"))

    def _build_context(
        self, request: HttpRequest, extra: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        dagster_url: str | None = getattr(settings, "DAGSTER_URL", None)
        show_dagster_ui = bool(dagster_url) and self._can_access_dagster_ui(
            request,
        )
        context: dict[str, Any] = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "app_label": self.model._meta.app_label,
            "dagster_url": dagster_url if show_dagster_ui else None,
        }
        if show_dagster_ui and dagster_url:
            base = dagster_url.rstrip("/")
            context["dagster_ui_jobs_url"] = f"{base}/jobs"
            context["dagster_ui_runs_url"] = f"{base}/runs"
            context["dagster_ui_locations_url"] = f"{base}/deployment/locations"
        if extra:
            context.update(extra)
        return context

    @staticmethod
    def _dagster_job_ui_url(dagster_url: str | None, job: dict[str, Any]) -> str | None:
        """Build the Dagster UI URL for a specific job."""
        if not dagster_url:
            return None
        base = dagster_url.rstrip("/")
        repo = job.get("repository", "")
        location = job.get("location", "")
        name = job.get("name", "")
        return f"{base}/locations/{repo}@{location}/jobs/{name}"

    @staticmethod
    def _dagster_run_ui_url(dagster_url: str | None, run_id: str) -> str | None:
        """Build the Dagster UI URL for a specific run."""
        if not dagster_url:
            return None
        base = dagster_url.rstrip("/")
        return f"{base}/runs/{run_id}"


# ---------------------------------------------------------------------------
# Jobs  (list + detail + "add" = trigger)
# ---------------------------------------------------------------------------


@admin.register(DagsterJob)
class DagsterJobAdmin(_DagsterAdminBase):
    def has_add_permission(self, request: HttpRequest) -> bool:
        # No generic "Add" link on the admin index; trigger is per-job.
        return False

    def get_urls(self) -> list[URLPattern]:
        info = (self.model._meta.app_label, self.model._meta.model_name)
        return [
            path(
                "",
                self.admin_site.admin_view(self.job_list_view),
                name="%s_%s_changelist" % info,
            ),
            path(
                "<str:job_name>/trigger/",
                self.admin_site.admin_view(self.trigger_view),
                name="%s_%s_trigger" % info,
            ),
            path(
                "<str:job_name>/change/",
                self.admin_site.admin_view(self.job_detail_view),
                name="%s_%s_change" % info,
            ),
        ]

    # -- changelist ----------------------------------------------------------

    def job_list_view(self, request: HttpRequest) -> HttpResponse:
        denied = self._check_view_perm(request)
        if denied:
            return denied

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
                jobs,
                key=lambda j: j["name"],
                reverse=sort.startswith("-"),
            )

        dagster_url = getattr(settings, "DAGSTER_URL", None)
        show_dagster_ui = bool(dagster_url) and self._can_access_dagster_ui(
            request,
        )
        if jobs is not None and show_dagster_ui:
            for job in jobs:
                job["dagster_ui_url"] = self._dagster_job_ui_url(
                    dagster_url,
                    job,
                )

        context = self._build_context(
            request,
            {
                "title": "Dagster Jobs",
                "jobs": jobs,
                "current_sort": sort or "name",
            },
        )
        return TemplateResponse(request, "django_dagster/job_list.html", context)

    # -- change (detail) -----------------------------------------------------

    def job_detail_view(self, request: HttpRequest, job_name: str) -> HttpResponse:
        denied = self._check_view_perm(request)
        if denied:
            return denied

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
            self.message_user(request, f"Job '{job_name}' not found", messages.ERROR)
            return HttpResponseRedirect(
                reverse("admin:django_dagster_dagsterjob_changelist")
            )

        # Fetch recent runs for this job
        recent_runs = None
        try:
            recent_runs = client.get_runs(job_name=job_name, limit=10)
        except Exception:  # nosec B110
            pass

        dagster_url = getattr(settings, "DAGSTER_URL", None)
        show_dagster_ui = bool(dagster_url) and self._can_access_dagster_ui(
            request,
        )

        dagster_job_ui_url = None
        dagster_location_ui_url = None
        if show_dagster_ui and dagster_url:
            dagster_job_ui_url = self._dagster_job_ui_url(dagster_url, job)
            base = dagster_url.rstrip("/")
            dagster_location_ui_url = f"{base}/locations/{job['location']}"

        if recent_runs is not None and show_dagster_ui:
            for run in recent_runs:
                run["dagster_ui_url"] = self._dagster_run_ui_url(
                    dagster_url,
                    run["runId"],
                )

        can_trigger = not self._permissions_enabled() or request.user.has_perm(
            "django_dagster.trigger_dagsterjob"
        )

        context = self._build_context(
            request,
            {
                "title": "View Dagster Job",
                "job": job,
                "recent_runs": recent_runs,
                "can_trigger": can_trigger,
                "dagster_job_ui_url": dagster_job_ui_url,
                "dagster_location_ui_url": dagster_location_ui_url,
            },
        )
        return TemplateResponse(request, "django_dagster/job_detail.html", context)

    # -- add (trigger) -------------------------------------------------------

    def trigger_view(self, request: HttpRequest, job_name: str) -> HttpResponse:
        if self._permissions_enabled() and not request.user.has_perm(
            "django_dagster.trigger_dagsterjob"
        ):
            return HttpResponseForbidden()

        if request.method == "POST":
            config_json = request.POST.get("run_config", "").strip()

            run_config = None
            if config_json:
                try:
                    run_config = json.loads(config_json)
                except json.JSONDecodeError as e:
                    self.message_user(
                        request, f"Invalid JSON config: {e}", messages.ERROR
                    )
                    return self._render_trigger_form(
                        request,
                        job_name=job_name,
                        run_config=config_json,
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
                    request,
                    job_name=job_name,
                    run_config=config_json,
                )

        # GET: fetch default run config
        default_config = "{}"
        try:
            config = client.get_job_default_run_config(job_name)
            if config:
                default_config = json.dumps(config, indent=2)
        except Exception:  # nosec B110
            pass

        return self._render_trigger_form(
            request,
            job_name=job_name,
            run_config=default_config,
        )

    def _render_trigger_form(
        self, request: HttpRequest, job_name: str, run_config: str = ""
    ) -> TemplateResponse:
        context = self._build_context(
            request,
            {
                "title": "Trigger Dagster Job Run",
                "job_name": job_name,
                "run_config": run_config,
            },
        )
        return TemplateResponse(request, "django_dagster/trigger_job.html", context)


# ---------------------------------------------------------------------------
# Runs  (list + detail + cancel / re-execute)
# ---------------------------------------------------------------------------


@admin.register(DagsterRun)
class DagsterRunAdmin(_DagsterAdminBase):
    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def get_urls(self) -> list[URLPattern]:
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
                "<str:run_id>/re-execute/",
                self.admin_site.admin_view(self.reexecute_run_view),
                name="%s_%s_reexecute" % info,
            ),
        ]

    # -- changelist ----------------------------------------------------------

    SORT_KEYS: dict[str, str] = {
        "run_id": "runId",
        "job": "jobName",
        "status": "status",
        "started": "startTime",
        "ended": "endTime",
    }

    def run_list_view(self, request: HttpRequest) -> HttpResponse:
        denied = self._check_view_perm(request)
        if denied:
            return denied

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

        # Sort runs client-side
        sort = request.GET.get("o")
        if runs is not None and sort:
            raw = sort.lstrip("-")
            key = self.SORT_KEYS.get(raw)
            if key:
                runs = sorted(
                    runs,
                    key=lambda r: r.get(key) or "",
                    reverse=sort.startswith("-"),
                )

        dagster_url = getattr(settings, "DAGSTER_URL", None)
        show_dagster_ui = bool(dagster_url) and self._can_access_dagster_ui(
            request,
        )
        if runs is not None and show_dagster_ui:
            for run in runs:
                run["dagster_ui_url"] = self._dagster_run_ui_url(
                    dagster_url,
                    run["runId"],
                )

        # Fetch job list for the filter sidebar
        jobs = None
        try:
            jobs = client.get_jobs()
        except Exception:  # nosec B110
            pass

        context = self._build_context(
            request,
            {
                "title": "Dagster Runs",
                "runs": runs,
                "jobs": jobs,
                "current_job": job_name,
                "current_status": status,
                "current_sort": sort,
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
            },
        )
        return TemplateResponse(request, "django_dagster/run_list.html", context)

    # -- change (detail) -----------------------------------------------------

    def run_detail_view(self, request: HttpRequest, object_id: str) -> HttpResponse:
        denied = self._check_view_perm(request)
        if denied:
            return denied

        run = None
        try:
            run = client.get_run(object_id)
        except Exception as e:
            self.message_user(request, f"Failed to fetch run: {e}", messages.ERROR)

        if run is None:
            self.message_user(request, f"Run {object_id} not found", messages.ERROR)
            return HttpResponseRedirect(
                reverse("admin:django_dagster_dagsterrun_changelist")
            )

        status_can_cancel = run["status"] in (
            "QUEUED",
            "NOT_STARTED",
            "STARTING",
            "STARTED",
        )
        status_can_reexecute = run["status"] in (
            "SUCCESS",
            "FAILURE",
            "CANCELED",
        )

        if self._permissions_enabled():
            can_cancel = status_can_cancel and request.user.has_perm(
                "django_dagster.cancel_dagsterrun"
            )
            can_reexecute = status_can_reexecute and request.user.has_perm(
                "django_dagster.reexecute_dagsterrun"
            )
        else:
            can_cancel = status_can_cancel
            can_reexecute = status_can_reexecute

        # Fetch recent runs for the same job
        related_runs = None
        try:
            related_runs = client.get_runs(
                job_name=run["jobName"],
                limit=10,
            )
        except Exception:  # nosec B110
            pass

        # Fetch event logs for this run
        events = None
        try:
            events_data = client.get_run_events(object_id)
            if events_data:
                events = events_data["events"]
        except Exception:  # nosec B110
            pass

        dagster_url = getattr(settings, "DAGSTER_URL", None)
        show_dagster_ui = bool(dagster_url) and self._can_access_dagster_ui(
            request,
        )

        dagster_run_ui_url = None
        dagster_job_ui_url = None
        if show_dagster_ui:
            dagster_run_ui_url = self._dagster_run_ui_url(
                dagster_url,
                object_id,
            )
            # Look up the job to build its Dagster UI URL
            try:
                jobs = client.get_jobs()
                job = next(
                    (j for j in jobs if j["name"] == run["jobName"]),
                    None,
                )
                if job:
                    dagster_job_ui_url = self._dagster_job_ui_url(
                        dagster_url,
                        job,
                    )
            except Exception:  # nosec B110
                pass

        if related_runs is not None and show_dagster_ui:
            for r in related_runs:
                r["dagster_ui_url"] = self._dagster_run_ui_url(
                    dagster_url,
                    r["runId"],
                )

        context = self._build_context(
            request,
            {
                "title": f"Run {object_id}",
                "run": run,
                "can_cancel": can_cancel,
                "can_reexecute": can_reexecute,
                "related_runs": related_runs,
                "events": events,
                "dagster_run_ui_url": dagster_run_ui_url,
                "dagster_job_ui_url": dagster_job_ui_url,
            },
        )
        return TemplateResponse(request, "django_dagster/run_detail.html", context)

    # -- cancel --------------------------------------------------------------

    def cancel_run_view(self, request: HttpRequest, run_id: str) -> HttpResponse:
        if self._permissions_enabled() and not request.user.has_perm(
            "django_dagster.cancel_dagsterrun"
        ):
            return HttpResponseForbidden()

        if request.method == "POST":
            try:
                client.cancel_run(run_id)
                self.message_user(
                    request,
                    f"Run {run_id} cancellation requested",
                    messages.SUCCESS,
                )
            except Exception as e:
                self.message_user(request, f"Failed to cancel run: {e}", messages.ERROR)
        return HttpResponseRedirect(
            reverse("admin:django_dagster_dagsterrun_change", args=[run_id])
        )

    # -- re-execute ----------------------------------------------------------

    def reexecute_run_view(self, request: HttpRequest, run_id: str) -> HttpResponse:
        if self._permissions_enabled() and not request.user.has_perm(
            "django_dagster.reexecute_dagsterrun"
        ):
            return HttpResponseForbidden()

        if request.method == "POST":
            try:
                new_run_id = client.reexecute_run(run_id)
                self.message_user(
                    request,
                    f"Run re-executed. New run ID: {new_run_id}",
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
                    request, f"Failed to re-execute run: {e}", messages.ERROR
                )
        return HttpResponseRedirect(
            reverse("admin:django_dagster_dagsterrun_change", args=[run_id])
        )
