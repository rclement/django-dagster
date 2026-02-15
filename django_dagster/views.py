import json

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from . import client


@staff_member_required
def job_list(request):
    jobs = None
    try:
        jobs = client.get_jobs()
    except Exception as e:
        messages.error(request, f"Failed to connect to Dagster: {e}")

    return render(
        request,
        "django_dagster/job_list.html",
        {"jobs": jobs, "title": "Dagster Jobs"},
    )


@staff_member_required
def run_list(request):
    job_name = request.GET.get("job")
    status = request.GET.get("status")
    statuses = [status] if status else None

    runs = None
    try:
        runs = client.get_runs(job_name=job_name, statuses=statuses)
    except Exception as e:
        messages.error(request, f"Failed to connect to Dagster: {e}")

    return render(
        request,
        "django_dagster/run_list.html",
        {
            "runs": runs,
            "current_job": job_name,
            "current_status": status,
            "title": "Dagster Runs",
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


@staff_member_required
def run_detail(request, run_id):
    run = None
    try:
        run = client.get_run(run_id)
    except Exception as e:
        messages.error(request, f"Failed to fetch run: {e}")

    if run is None:
        messages.error(request, f"Run {run_id} not found")
        return HttpResponseRedirect(reverse("dagster:run_list"))

    can_cancel = run["status"] in ("QUEUED", "NOT_STARTED", "STARTING", "STARTED")
    can_retry = run["status"] in ("FAILURE", "CANCELED")

    return render(
        request,
        "django_dagster/run_detail.html",
        {
            "run": run,
            "can_cancel": can_cancel,
            "can_retry": can_retry,
            "title": f"Run {run_id[:8]}…",
        },
    )


@staff_member_required
def trigger_job(request):
    if request.method == "POST":
        job_name = request.POST.get("job_name", "").strip()
        config_json = request.POST.get("run_config", "").strip()

        if not job_name:
            messages.error(request, "Job name is required")
            return render(
                request,
                "django_dagster/trigger_job.html",
                {"run_config": config_json, "title": "Trigger Job"},
            )

        run_config = None
        if config_json:
            try:
                run_config = json.loads(config_json)
            except json.JSONDecodeError as e:
                messages.error(request, f"Invalid JSON config: {e}")
                return render(
                    request,
                    "django_dagster/trigger_job.html",
                    {
                        "job_name": job_name,
                        "run_config": config_json,
                        "title": "Trigger Job",
                    },
                )

        try:
            run_id = client.submit_job(job_name, run_config=run_config)
            messages.success(
                request, f"Job '{job_name}' triggered. Run ID: {run_id}"
            )
            return HttpResponseRedirect(
                reverse("dagster:run_detail", args=[run_id])
            )
        except Exception as e:
            messages.error(request, f"Failed to trigger job: {e}")

    job_name = request.GET.get("job", "")

    # Fetch available jobs for the dropdown
    jobs = None
    try:
        jobs = client.get_jobs()
    except Exception:
        pass

    return render(
        request,
        "django_dagster/trigger_job.html",
        {
            "job_name": job_name,
            "jobs": jobs,
            "title": "Trigger Job",
        },
    )


@staff_member_required
def cancel_run_view(request, run_id):
    if request.method == "POST":
        try:
            client.cancel_run(run_id)
            messages.success(request, f"Run {run_id[:8]}… cancellation requested")
        except Exception as e:
            messages.error(request, f"Failed to cancel run: {e}")
    return HttpResponseRedirect(reverse("dagster:run_detail", args=[run_id]))


@staff_member_required
def retry_run_view(request, run_id):
    if request.method == "POST":
        try:
            new_run_id = client.retry_run(run_id)
            messages.success(
                request, f"Run retried. New run ID: {new_run_id}"
            )
            return HttpResponseRedirect(
                reverse("dagster:run_detail", args=[new_run_id])
            )
        except Exception as e:
            messages.error(request, f"Failed to retry run: {e}")
    return HttpResponseRedirect(reverse("dagster:run_detail", args=[run_id]))
