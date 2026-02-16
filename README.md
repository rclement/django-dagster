# django-dagster

A Django plugin for interacting with a [Dagster](https://dagster.io/) server through the Django admin interface.

## Features

- Native Django Admin integration — shows up as a **Dagster** section
- List all jobs from connected Dagster instance
- View runs with status and job filtering, pagination
- Trigger new job executions with optional JSON/YAML run config
- Cancel running jobs
- Re-execute failed/canceled jobs
- View detailed run metadata (config, tags, event logs)
- Optional granular permission system using Django's built-in permissions

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

No URL configuration is needed — the plugin registers itself with the Django admin automatically. Navigate to `/admin/` and look for the **Dagster** section.

## Permissions

By default, all staff users (`is_staff=True`) have full access to all Dagster views and actions. To enable granular, Django-native permission control, add this to your settings:

```python
DAGSTER_PERMISSIONS_ENABLED = True
```

When enabled, access is governed by standard Django permissions that you can assign to users or groups via the Django admin:

| Permission | Codename | Grants access to |
|---|---|---|
| Can view Job | `view_dagsterjob` | View job list and job detail pages |
| Can view Run | `view_dagsterrun` | View run list and run detail pages |
| Can trigger Dagster jobs | `trigger_dagsterjob` | Trigger/submit a new job run |
| Can cancel Dagster runs | `cancel_dagsterrun` | Cancel a running job |
| Can re-execute Dagster runs | `reexecute_dagsterrun` | Re-execute a completed/failed run |

Superusers always have all permissions regardless of this setting.

## Programmatic API

The package also exposes a Python API for use outside the admin:

```python
from django_dagster import get_jobs, get_runs, get_run, submit_job, cancel_run, reexecute_run
```

## Demo

A self-contained demo project is available in the [`demo/`](demo/) directory with sample Dagster jobs and pre-configured users. See [`demo/README.md`](demo/README.md) for instructions.

## License

This project is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for details.
