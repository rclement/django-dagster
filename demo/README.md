# django-dagster demo

A ready-to-run demo showcasing the django-dagster plugin with permissions enabled.

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

The `setup_demo` command creates the database and two users:

| Username | Password | Role | Access |
|----------|----------|------|--------|
| `admin` | `admin` | Superuser | Full access — can view, trigger, cancel, and re-execute |
| `viewer` | `viewer` | Staff (view-only) | Can browse jobs and runs, but **cannot** trigger, cancel, or re-execute |

Log in as `admin` to see all action buttons (Trigger, Cancel, Re-execute). Then log in as `viewer` to see the same pages without those buttons.

## Permissions

This demo has `DAGSTER_PERMISSIONS_ENABLED = True` in settings. The `viewer` user is assigned only the `view_dagsterjob` and `view_dagsterrun` permissions.

To grant the viewer additional permissions, log in as `admin`, go to the Users section, edit the `viewer` user, and add permissions like `trigger_dagsterjob`, `cancel_dagsterrun`, or `reexecute_dagsterrun`.

## Sample Dagster jobs

The demo includes three Dagster jobs defined in `dagster_jobs/sample.py`:

- **etl_pipeline** — a classic Extract-Transform-Load pipeline
- **generate_report_job** — a configurable report generator (accepts JSON run config)
- **slow_job** — a deliberately long-running job for testing cancellation

## Things to try

1. **As admin**: trigger `etl_pipeline`, view run detail, cancel `slow_job`, re-execute a failed run
2. **As viewer**: browse the same pages — notice the action buttons are hidden
3. **Grant permissions**: as admin, edit the `viewer` user and add `trigger_dagsterjob` — the viewer will now see the Trigger button
