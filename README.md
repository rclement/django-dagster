# django-dagster

[![PyPI](https://img.shields.io/pypi/v/django-dagster.svg)](https://pypi.org/project/django-dagster/)
[![Python Versions](https://img.shields.io/pypi/pyversions/django-dagster?logo=python&logoColor=white)](https://pypi.org/project/django-dagster/)
[![CI/CD](https://github.com/rclement/django-dagster/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/rclement/django-dagster/actions/workflows/ci-cd.yml)
[![License](https://img.shields.io/github/license/rclement/django-dagster)](https://github.com/rclement/django-dagster/blob/main/LICENSE)

A Django plugin for interacting with a [Dagster](https://dagster.io/) server through the Django admin interface.

## Features

- Native Django Admin integration — shows up as a **Dagster** section
- List all jobs from connected Dagster instance
- View runs with status and job filtering
- Trigger new job executions with optional JSON run config
- Cancel running jobs
- Re-execute failed/canceled jobs
- View detailed run metadata (config, tags, event logs)
- Granular permission system using Django's built-in permissions

## Screenshots

| Jobs list | Job detail |
|---|---|
| ![Jobs list](https://raw.githubusercontent.com/rclement/django-dagster/main/docs/screenshots/jobs_list.png) | ![Job detail](https://raw.githubusercontent.com/rclement/django-dagster/main/docs/screenshots/job_detail.png) |

| Trigger job | Trigger success |
|---|---|
| ![Trigger job](https://raw.githubusercontent.com/rclement/django-dagster/main/docs/screenshots/job_trigger.png) | ![Trigger success](https://raw.githubusercontent.com/rclement/django-dagster/main/docs/screenshots/job_trigger_success.png) |

| Runs list | Run detail |
|---|---|
| ![Runs list](https://raw.githubusercontent.com/rclement/django-dagster/main/docs/screenshots/runs_list.png) | ![Run detail](https://raw.githubusercontent.com/rclement/django-dagster/main/docs/screenshots/run_detail.png) |

## Requirements

- Python 3.10+
- Django 4.2+

## Installation

```bash
pip install django-dagster
```

## Configuration

Add `django_dagster` to `INSTALLED_APPS` and set `DAGSTER_URL` in your Django settings:

```python
INSTALLED_APPS = [
    ...
    "django_dagster",
]

DAGSTER_URL = "http://localhost:3000"
```

Then run migrations to create the permission models:

```bash
python manage.py migrate django_dagster
```

No URL configuration or manual admin registration is needed. Navigate to `/admin/` and look for the **Dagster** section.

## Permissions

Access is governed by standard Django permissions that you can assign to users or groups via the Django admin. Superusers always have full access.

| Permission | Codename | Grants access to |
|---|---|---|
| Can view Job | `view_dagsterjob` | View job list and job detail pages |
| Can view Run | `view_dagsterrun` | View run list and run detail pages |
| Can trigger Dagster jobs | `trigger_dagsterjob` | Trigger/submit a new job run |
| Can cancel Dagster runs | `cancel_dagsterrun` | Cancel a running job |
| Can re-execute Dagster runs | `reexecute_dagsterrun` | Re-execute a completed/failed run |
| Can access the Dagster UI | `access_dagster_ui` | Show direct links to the Dagster UI |

To customise behaviour — for example, granting all staff users full access by default — unregister the defaults and register your own subclass in your project's `admin.py`:

```python
from django.contrib import admin
from django_dagster.admin import DagsterJobAdmin, DagsterRunAdmin
from django_dagster.models import DagsterJob, DagsterRun

def _is_active_staff(request):
    return request.user.is_active and request.user.is_staff

class MyDagsterJobAdmin(DagsterJobAdmin):
    def has_module_permission(self, request):
        return _is_active_staff(request)

    def has_view_permission(self, request, obj=None):
        return _is_active_staff(request)

    def has_trigger_dagsterjob_permission(self, request):
        return _is_active_staff(request)

    def has_access_dagster_ui_permission(self, request):
        return _is_active_staff(request)

class MyDagsterRunAdmin(DagsterRunAdmin):
    def has_module_permission(self, request):
        return _is_active_staff(request)

    def has_view_permission(self, request, obj=None):
        return _is_active_staff(request)

    def has_cancel_dagsterrun_permission(self, request):
        return _is_active_staff(request)

    def has_reexecute_dagsterrun_permission(self, request):
        return _is_active_staff(request)

    def has_access_dagster_ui_permission(self, request):
        return _is_active_staff(request)

admin.site.unregister(DagsterJob)
admin.site.unregister(DagsterRun)
admin.site.register(DagsterJob, MyDagsterJobAdmin)
admin.site.register(DagsterRun, MyDagsterRunAdmin)
```

## Programmatic API

The package also exposes a Python API for use outside the admin:

```python
from django_dagster import get_jobs, get_runs, get_run, submit_job, cancel_run, reexecute_run
```

## Demo

A self-contained demo project is available in the [`demo/`](demo/) directory with sample Dagster jobs and pre-configured users. See [`demo/README.md`](demo/README.md) for instructions.

## License

This project is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for details.
