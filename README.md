# django-dagster

A Django plugin for interacting with a [Dagster](https://dagster.io/) server through the Django admin interface.

## Features

- List all jobs from connected Dagster instance
- View runs with status filtering
- Trigger new job executions with JSON run config
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

Include the URL configuration (must be before `admin.site.urls`):

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/dagster/", include("django_dagster.urls")),
    path("admin/", admin.site.urls),
]
```

Navigate to `/admin/dagster/` to access the Dagster dashboard.

## Demo

```bash
cd demo
uv sync
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Then open http://localhost:8000/admin/dagster/ (requires a running Dagster instance at `http://localhost:3000`).
