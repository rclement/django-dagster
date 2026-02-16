import tempfile
import time
from pathlib import Path

import yaml
from invoke import task
from invoke.context import Context

app_path = "django_dagster"
tests_path = "tests"


@task
def format(ctx: Context) -> None:
    ctx.run("ruff format .", echo=True, pty=True)


@task
def audit(ctx: Context) -> None:
    ignored_vulns: list[str] = []
    options = [f"--ignore-vuln {vuln}" for vuln in ignored_vulns]
    ctx.run(f"pip-audit {' '.join(options)}", echo=True, pty=True)


@task
def vuln(ctx: Context) -> None:
    ctx.run(f"bandit -r {app_path}", echo=True, pty=True)


@task
def lint(ctx: Context) -> None:
    ctx.run("ruff check .", echo=True, pty=True)


@task
def typing(ctx: Context) -> None:
    ctx.run(f"mypy {app_path} {tests_path}", echo=True, pty=True)


@task
def test(ctx: Context) -> None:
    ctx.run(
        f"pytest -v --cov={app_path} --cov={tests_path} --cov-branch --cov-report=term-missing {tests_path}",
        echo=True,
        pty=True,
    )


@task(audit, vuln, lint, typing, test)
def qa(ctx: Context) -> None:
    pass


@task
def shots(ctx: Context) -> None:
    server_url = "http://localhost:8000"
    screenshots_path = Path(__file__).parent / "docs" / "screenshots"
    screenshots_path.mkdir(parents=True, exist_ok=True)

    login_js = "\n".join(
        [
            "document.getElementById('id_username').value = 'admin';",
            "document.getElementById('id_password').value = 'admin';",
            "document.querySelector('[type=submit]').click();",
        ]
    )
    click_first_run_js = "\n".join(
        [
            "const link = document.querySelector('#result_list tbody th a');",
            "if (link) window.location.href = link.href;",
        ]
    )

    shot_scraper_config = [
        # Auth: log in to Django admin
        {
            "url": f"{server_url}/admin/login/?next=/admin/",
            "javascript": login_js,
            "wait": 3000,
            "width": 1440,
            "height": 900,
            "output": "/tmp/_django_dagster_login.png",
        },
        # Trigger a job (shows success message + populates run data)
        {
            "url": f"{server_url}/admin/django_dagster/dagsterjob/etl_pipeline/trigger/",
            "javascript": "document.querySelector('#content form').submit();",
            "wait": 5000,
            "width": 1440,
            "height": 900,
            "output": str(screenshots_path / "job_trigger_success.png"),
        },
        # Jobs listing
        {
            "url": f"{server_url}/admin/django_dagster/dagsterjob/",
            "wait": 500,
            "width": 1440,
            "height": 900,
            "output": str(screenshots_path / "jobs_list.png"),
        },
        # Job detail
        {
            "url": f"{server_url}/admin/django_dagster/dagsterjob/etl_pipeline/change/",
            "wait": 500,
            "width": 1440,
            "height": 900,
            "output": str(screenshots_path / "job_detail.png"),
        },
        # Job trigger form
        {
            "url": f"{server_url}/admin/django_dagster/dagsterjob/etl_pipeline/trigger/",
            "wait": 500,
            "width": 1440,
            "height": 900,
            "output": str(screenshots_path / "job_trigger.png"),
        },
        # Runs listing
        {
            "url": f"{server_url}/admin/django_dagster/dagsterrun/",
            "wait": 500,
            "width": 1440,
            "height": 900,
            "output": str(screenshots_path / "runs_list.png"),
        },
        # Run detail (navigate to runs list, then click first run)
        {
            "url": f"{server_url}/admin/django_dagster/dagsterrun/",
            "javascript": click_first_run_js,
            "wait": 2000,
            "width": 1440,
            "height": 900,
            "output": str(screenshots_path / "run_detail.png"),
        },
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        shots_yml = Path(tmpdir) / "shots.yml"
        shots_yml.write_text(yaml.dump(shot_scraper_config))

        dagster_proc = ctx.run(
            "cd demo && uv run dagster dev",
            asynchronous=True,
            echo=True,
            pty=True,
        )
        django_proc = ctx.run(
            "cd demo && uv run python manage.py runserver --noreload",
            asynchronous=True,
            echo=True,
            pty=True,
        )
        ctx.run("uvx shot-scraper install", echo=True, pty=True)

        try:
            time.sleep(10)
            ctx.run(
                f"uvx shot-scraper multi {shots_yml} --retina",
                echo=True,
                pty=True,
            )
        finally:
            dagster_proc.runner.kill()
            django_proc.runner.kill()
