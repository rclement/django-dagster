from __future__ import annotations

from datetime import datetime
from typing import Any

from django.conf import settings
from django.db import models


def dagster_ui_base() -> str | None:
    ui_url: str | None = getattr(settings, "DAGSTER_UI_URL", None)
    if ui_url:
        return ui_url.rstrip("/")
    dagster_url: str | None = getattr(settings, "DAGSTER_URL", None)
    return dagster_url.rstrip("/") if dagster_url else None


# ---------------------------------------------------------------------------
# ORM-like managers (defined before models so type annotations work)
# ---------------------------------------------------------------------------


class DagsterJobManager:
    """ORM-like manager for Dagster jobs (proxy to the Dagster GraphQL API)."""

    def all(self) -> list[DagsterJob]:
        """List all jobs across all repositories."""
        from . import client

        return [DagsterJob._from_api(j) for j in client.get_jobs()]

    def get(self, *, name: str, repository: str, location: str) -> DagsterJob:
        """Get a single job by its full selector. Raises DagsterJob.DoesNotExist if not found."""
        from . import client

        data = client.get_job(
            name, repository_name=repository, repository_location_name=location
        )
        if data is None:
            raise DagsterJob.DoesNotExist(
                f"DagsterJob with name '{name}' does not exist."
            )
        return DagsterJob._from_api(data)


class DagsterRunManager:
    """ORM-like manager for Dagster runs (proxy to the Dagster GraphQL API)."""

    def all(self, *, limit: int = 25) -> list[DagsterRun]:
        """List all runs."""
        return self.filter(limit=limit)

    def filter(
        self,
        *,
        job_name: str | None = None,
        statuses: list[str] | None = None,
        limit: int = 25,
        cursor: str | None = None,
    ) -> list[DagsterRun]:
        """List runs with optional filtering."""
        from . import client

        return [
            DagsterRun._from_api(r)
            for r in client.get_runs(
                limit=limit, cursor=cursor, job_name=job_name, statuses=statuses
            )
        ]

    def get(self, *, run_id: str) -> DagsterRun:
        """Get a single run by ID. Raises DagsterRun.DoesNotExist if not found."""
        from . import client

        data = client.get_run(run_id)
        if data is None:
            raise DagsterRun.DoesNotExist(
                f"DagsterRun with run_id '{run_id}' does not exist."
            )
        return DagsterRun._from_api(data)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class DagsterJob(models.Model):
    objects: DagsterJobManager

    class Meta:
        managed = False
        verbose_name = "Job"
        verbose_name_plural = "Jobs"
        permissions = [
            ("trigger_dagsterjob", "Can trigger Dagster jobs"),
            ("access_dagster_ui", "Can access the Dagster UI"),
        ]

    name: str
    description: str | None
    repository: str
    location: str
    dagster_ui_url: str | None
    dagster_location_ui_url: str | None

    @classmethod
    def _from_api(cls, data: dict[str, Any]) -> DagsterJob:
        instance = cls()
        instance.name = data["name"]
        instance.description = data["description"]
        instance.repository = data["repository"]
        instance.location = data["location"]
        ui_base = dagster_ui_base()
        instance.dagster_ui_url = (
            f"{ui_base}/locations/{instance.repository}@{instance.location}/jobs/{instance.name}"
            if ui_base
            else None
        )
        instance.dagster_location_ui_url = (
            f"{ui_base}/locations/{instance.location}" if ui_base else None
        )
        return instance

    def submit(
        self,
        run_config: dict[str, Any] | None = None,
        tags: dict[str, str] | None = None,
    ) -> str:
        """Submit this job for execution. Returns the run ID."""
        from . import client

        return client.submit_job(
            self.name,
            repository_location_name=self.location,
            repository_name=self.repository,
            run_config=run_config,
            tags=tags,
        )

    def get_default_run_config(self) -> dict[str, Any]:
        """Fetch the default run config for this job."""
        from . import client

        return client.get_job_default_run_config(
            self.name,
            repository_name=self.repository,
            repository_location_name=self.location,
        )

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<DagsterJob: {self.name}>"


class DagsterRun(models.Model):
    objects: DagsterRunManager

    class Meta:
        managed = False
        verbose_name = "Run"
        verbose_name_plural = "Runs"
        permissions = [
            ("cancel_dagsterrun", "Can cancel Dagster runs"),
            ("reexecute_dagsterrun", "Can re-execute Dagster runs"),
        ]

    run_id: str
    job_name: str
    repository: str
    location: str
    status: str
    start_time: datetime | None
    end_time: datetime | None
    tags: list[dict[str, str]]
    run_config_yaml: str | None
    stats: dict[str, Any] | None
    dagster_ui_url: str | None
    dagster_job_ui_url: str | None

    @classmethod
    def _from_api(cls, data: dict[str, Any]) -> DagsterRun:
        instance = cls()
        instance.run_id = data["runId"]
        instance.job_name = data["jobName"]
        instance.repository = data.get("repository", "")
        instance.location = data.get("location", "")
        instance.status = data["status"]
        instance.start_time = data.get("startTime")
        instance.end_time = data.get("endTime")
        instance.tags = data.get("tags", [])
        instance.run_config_yaml = data.get("runConfigYaml")
        raw_stats = data.get("stats")
        instance.stats = (
            {
                "steps_succeeded": raw_stats.get("stepsSucceeded", 0),
                "steps_failed": raw_stats.get("stepsFailed", 0),
                "materializations": raw_stats.get("materializations", 0),
                "expectations": raw_stats.get("expectations", 0),
            }
            if raw_stats
            else None
        )
        ui_base = dagster_ui_base()
        instance.dagster_ui_url = (
            f"{ui_base}/runs/{instance.run_id}" if ui_base else None
        )
        instance.dagster_job_ui_url = (
            f"{ui_base}/locations/{instance.repository}@{instance.location}/jobs/{instance.job_name}"
            if ui_base and instance.repository and instance.location
            else None
        )
        return instance

    def cancel(self) -> None:
        """Cancel this run."""
        from . import client

        client.cancel_run(self.run_id)

    def reexecute(self) -> str:
        """Re-execute this run with the same configuration. Returns the new run ID."""
        from . import client

        return client.reexecute_run(self.run_id)

    def get_events(
        self, cursor: str | None = None, limit: int = 1000
    ) -> dict[str, Any] | None:
        """Fetch event logs for this run."""
        from . import client

        result = client.get_run_events(self.run_id, cursor=cursor, limit=limit)
        if result is None:
            return None
        events = []
        for event in result["events"]:
            events.append(
                {
                    "event_type": event.get("event_type"),
                    "message": event.get("message"),
                    "timestamp": event.get("timestamp"),
                    "level": event.get("level"),
                    "step_key": event.get("stepKey"),
                }
            )
        return {
            "events": events,
            "cursor": result["cursor"],
            "has_more": result["has_more"],
        }

    def __str__(self) -> str:
        return self.run_id

    def __repr__(self) -> str:
        return f"<DagsterRun: {self.run_id}>"


# Assigned after class creation so Django's metaclass doesn't overwrite them
# with a default Manager.
DagsterJob.objects = DagsterJobManager()
DagsterRun.objects = DagsterRunManager()
