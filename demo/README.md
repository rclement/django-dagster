# django-dagster demo

A ready-to-run demo showcasing the django-dagster plugin.

## Quick start

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

Then open http://localhost:8000/admin/.

## Pre-created users

The `setup_demo` command creates the database and three users:

| Username | Password | Role | Access |
|----------|----------|------|--------|
| `admin` | `admin` | Superuser | Full access — can view, trigger, cancel, and re-execute |
| `operator` | `operator` | Staff (full Dagster access) | Can view, trigger, cancel, re-execute, and see Dagster UI links |
| `viewer` | `viewer` | Staff (view-only) | Can browse jobs and runs, but **cannot** trigger, cancel, or re-execute |

## Permissions

The plugin uses Django's standard permission system. Each user has explicit permissions assigned:

- `admin` is a superuser — Django grants all permissions implicitly
- `operator` has all Dagster permissions: `view_dagsterjob`, `trigger_dagsterjob`, `access_dagster_ui`, `view_dagsterrun`, `cancel_dagsterrun`, `reexecute_dagsterrun`
- `viewer` has only `view_dagsterjob` and `view_dagsterrun`

To modify permissions, log in as `admin`, go to **Authentication > Users**, edit a user, and adjust their permissions.

## Sample Dagster jobs

The demo includes three Dagster jobs defined in `dagster_jobs/sample.py`:

- **etl_pipeline** — a classic Extract-Transform-Load pipeline
- **generate_report_job** — a configurable report generator (accepts JSON run config)
- **slow_job** — a deliberately long-running job for testing cancellation

## Things to try

1. **As operator**: trigger `etl_pipeline`, view run detail, cancel `slow_job`, re-execute a failed run, follow Dagster UI links
2. **As viewer**: browse the same pages — notice the action buttons and Dagster UI links are hidden
3. **As admin**: edit the `viewer` user and add `trigger_dagsterjob` — the viewer will now see the Trigger button
