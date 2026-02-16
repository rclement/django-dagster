from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import yaml
from dagster_graphql import DagsterGraphQLClient
from django.conf import settings


def get_client() -> DagsterGraphQLClient:
    """Create a DagsterGraphQLClient from Django settings."""
    parsed = urlparse(settings.DAGSTER_URL)
    return DagsterGraphQLClient(
        hostname=parsed.hostname or "localhost",
        port_number=parsed.port,
        use_https=parsed.scheme == "https",
    )


def get_jobs() -> list[dict[str, Any]]:
    """List all jobs across all repositories."""
    client = get_client()
    result = client._execute(
        """
        query {
            repositoriesOrError {
                ... on RepositoryConnection {
                    nodes {
                        name
                        location { name }
                        pipelines { name description }
                    }
                }
            }
        }
        """
    )
    jobs: list[dict[str, Any]] = []
    for repo in result["repositoriesOrError"]["nodes"]:
        for pipeline in repo["pipelines"]:
            jobs.append(
                {
                    "name": pipeline["name"],
                    "description": pipeline["description"],
                    "repository": repo["name"],
                    "location": repo["location"]["name"],
                }
            )
    return jobs


def _parse_timestamp(ts: Any) -> datetime | None:
    """Convert a unix timestamp (float or None) to a datetime."""
    if ts is None:
        return None
    return datetime.fromtimestamp(float(ts), tz=timezone.utc)


def _format_run(run: dict[str, Any]) -> dict[str, Any]:
    """Convert raw GraphQL run data into a display-friendly dict."""
    run["startTime"] = _parse_timestamp(run.get("startTime"))
    run["endTime"] = _parse_timestamp(run.get("endTime"))
    return run


def get_runs(
    limit: int = 25,
    cursor: str | None = None,
    job_name: str | None = None,
    statuses: list[str] | None = None,
) -> list[dict[str, Any]]:
    """List runs with optional filtering."""
    client = get_client()
    run_filter: dict[str, Any] = {}
    if job_name:
        run_filter["pipelineName"] = job_name
    if statuses:
        run_filter["statuses"] = statuses

    variables: dict[str, Any] = {"limit": limit}
    if cursor:
        variables["cursor"] = cursor
    if run_filter:
        variables["filter"] = run_filter

    result = client._execute(
        """
        query($limit: Int, $cursor: String, $filter: RunsFilter) {
            runsOrError(limit: $limit, cursor: $cursor, filter: $filter) {
                ... on Runs {
                    results {
                        runId
                        jobName
                        status
                        startTime
                        endTime
                        tags { key value }
                    }
                }
            }
        }
        """,
        variables,
    )
    return [_format_run(r) for r in result["runsOrError"]["results"]]


def get_run(run_id: str) -> dict[str, Any] | None:
    """Get detailed metadata for a single run."""
    client = get_client()
    result = client._execute(
        """
        query($runId: ID!) {
            runOrError(runId: $runId) {
                __typename
                ... on Run {
                    runId
                    jobName
                    status
                    startTime
                    endTime
                    runConfigYaml
                    tags { key value }
                    stats {
                        ... on RunStatsSnapshot {
                            stepsSucceeded
                            stepsFailed
                            materializations
                            expectations
                            startTime
                            endTime
                        }
                    }
                }
                ... on RunNotFoundError { runId message }
                ... on PythonError { message }
            }
        }
        """,
        {"runId": run_id},
    )
    run_data = result["runOrError"]
    if run_data["__typename"] == "RunNotFoundError":
        return None
    if run_data["__typename"] == "PythonError":
        raise Exception(run_data["message"])
    return _format_run(run_data)


def get_run_events(
    run_id: str, cursor: str | None = None, limit: int = 1000
) -> dict[str, Any] | None:
    """Fetch event logs for a run."""
    client = get_client()
    variables: dict[str, Any] = {"runId": run_id}
    if cursor:
        variables["afterCursor"] = cursor
    if limit:
        variables["limit"] = limit

    result = client._execute(
        """
        query($runId: ID!, $afterCursor: String, $limit: Int) {
            logsForRun(runId: $runId, afterCursor: $afterCursor, limit: $limit) {
                ... on EventConnection {
                    events {
                        __typename
                        ... on MessageEvent {
                            message
                            timestamp
                            level
                            stepKey
                        }
                    }
                    cursor
                    hasMore
                }
                ... on RunNotFoundError { message }
                ... on PythonError { message }
            }
        }
        """,
        variables,
    )
    data = result["logsForRun"]
    typename = data.get("__typename", "EventConnection")
    if typename == "RunNotFoundError":
        return None
    if typename == "PythonError":
        raise Exception(data["message"])

    events = data.get("events", [])
    for event in events:
        # Event log timestamps are in milliseconds; convert to seconds.
        raw_ts = event.get("timestamp")
        event["timestamp"] = _parse_timestamp(
            str(float(raw_ts) / 1000) if raw_ts else None
        )
        # Rename __typename so Django templates can access it (no leading _)
        if "__typename" in event:
            event["event_type"] = event.pop("__typename")

    return {
        "events": events,
        "cursor": data.get("cursor"),
        "has_more": data.get("hasMore", False),
    }


def get_job_default_run_config(job_name: str) -> dict[str, Any]:
    """Fetch the default run config for a job from the Dagster API.

    Returns a dict (possibly empty) with the default config values.
    """
    # Find the job's repository info
    jobs = get_jobs()
    job = next((j for j in jobs if j["name"] == job_name), None)
    if job is None:
        return {}

    client = get_client()
    result = client._execute(
        """
        query($selector: PipelineSelector!) {
            runConfigSchemaOrError(selector: $selector) {
                ... on RunConfigSchema {
                    rootDefaultYaml
                }
            }
        }
        """,
        {
            "selector": {
                "pipelineName": job_name,
                "repositoryName": job["repository"],
                "repositoryLocationName": job["location"],
            }
        },
    )
    schema = result.get("runConfigSchemaOrError", {})
    raw_yaml = schema.get("rootDefaultYaml", "")
    if raw_yaml:
        parsed = yaml.safe_load(raw_yaml)
        if isinstance(parsed, dict) and parsed:
            return parsed
    return {}


def submit_job(
    job_name: str,
    repository_location_name: str | None = None,
    repository_name: str | None = None,
    run_config: dict[str, Any] | None = None,
    tags: dict[str, str] | None = None,
) -> str:
    """Submit a job for execution. Returns the run ID."""
    client = get_client()
    return client.submit_job_execution(
        job_name=job_name,
        repository_location_name=repository_location_name,
        repository_name=repository_name,
        run_config=run_config,
        tags=tags,
    )


def cancel_run(run_id: str) -> None:
    """Cancel a running job."""
    client = get_client()
    client.terminate_run(run_id)


def reexecute_run(run_id: str) -> str:
    """Re-execute a run with the same configuration."""
    run = get_run(run_id)
    if run is None:
        raise ValueError(f"Run {run_id} not found")

    run_config = (
        yaml.safe_load(run["runConfigYaml"]) if run.get("runConfigYaml") else None
    )
    if isinstance(run_config, dict) and not run_config:
        run_config = None

    # Filter out dagster system tags
    tags = {
        t["key"]: t["value"]
        for t in run.get("tags", [])
        if not t["key"].startswith("dagster/")
    } or None

    return submit_job(
        job_name=run["jobName"],
        run_config=run_config,
        tags=tags,
    )
