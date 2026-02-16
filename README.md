# django-dagster

A Django plugin for interacting with a [Dagster](https://dagster.io/) server through the Django admin interface.

## Features

- Native Django Admin integration — shows up as a **Dagster > Jobs** section
- List all jobs from connected Dagster instance
- View runs with status filtering
- Trigger new job executions with optional JSON run config
- Cancel running jobs
- Retry failed/canceled jobs
- View detailed run metadata (config, tags, step stats)

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

No URL configuration is needed — the plugin registers itself with the Django admin automatically.

Navigate to `/admin/` and look for the **Dagster** section.

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

**Example: read-only viewer group**

In the Django admin, create a group called "Dagster Viewers" and assign it the `view_dagsterjob` and `view_dagsterrun` permissions. Users in this group can browse jobs and runs but cannot trigger, cancel, or re-execute.

## Demo

The `demo/` directory contains a ready-to-run example with:

- A Django project wired to `django_dagster`
- Three sample Dagster jobs:
  - **etl_pipeline** — a classic Extract-Transform-Load pipeline
  - **generate_report_job** — a configurable report generator (pass JSON run config)
  - **slow_job** — a deliberately long-running job for testing cancellation

### Quick start

You need **two terminals** — one for Dagster, one for Django.

**Terminal 1 — Start Dagster:**

```bash
cd demo
uv sync
uv run dagster dev
```

Dagster will start at http://localhost:3000.

**Terminal 2 — Start Django:**

```bash
cd demo
uv run python manage.py setup_demo
uv run python manage.py runserver
```

Then open http://localhost:8000/admin/ and log in with one of the pre-created users:

- **admin** / **admin** — superuser with full access
- **viewer** / **viewer** — staff user with view-only access (cannot trigger, cancel, or re-execute)

The demo has `DAGSTER_PERMISSIONS_ENABLED = True` so you can see the permission system in action.

### Things to try

1. **Trigger a job** — click *Jobs*, then *Trigger* next to `etl_pipeline`
2. **Use run config** — trigger `generate_report_job` with:
   ```json
   {"ops": {"generate_report": {"config": {"report_name": "weekly", "num_sections": 5}}}}
   ```
3. **Cancel a running job** — trigger `slow_job`, then open the run detail and hit *Cancel Run*
4. **Retry a failed/canceled job** — after canceling, hit *Retry Run*
5. **Filter runs** — use the status dropdown on the *Runs* page
