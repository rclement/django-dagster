import json
from datetime import datetime, timezone
from urllib.parse import urlparse

import yaml
from dagster_graphql import DagsterGraphQLClient
from django.conf import settings


def get_client():
    """Create a DagsterGraphQLClient from Django settings."""
    parsed = urlparse(settings.DAGSTER_URL)
    return DagsterGraphQLClient(
        hostname=parsed.hostname,
        port_number=parsed.port,
        use_https=parsed.scheme == "https",
    )


def get_jobs():
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
    jobs = []
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


def _parse_timestamp(ts):
    """Convert a unix timestamp (float or None) to a datetime."""
    if ts is None:
        return None
    return datetime.fromtimestamp(float(ts), tz=timezone.utc)


def _format_run(run):
    """Convert raw GraphQL run data into a display-friendly dict."""
    run["startTime"] = _parse_timestamp(run.get("startTime"))
    run["endTime"] = _parse_timestamp(run.get("endTime"))
    return run


def get_runs(limit=25, cursor=None, job_name=None, statuses=None):
    """List runs with optional filtering."""
    client = get_client()
    run_filter = {}
    if job_name:
        run_filter["pipelineName"] = job_name
    if statuses:
        run_filter["statuses"] = statuses

    variables = {"limit": limit}
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


def get_run(run_id):
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


def get_run_events(run_id, cursor=None, limit=1000):
    """Fetch event logs for a run."""
    client = get_client()
    variables = {"runId": run_id}
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
                        message
                        timestamp
                        level
                        stepKey
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
        event["timestamp"] = _parse_timestamp(event.get("timestamp"))
        # Rename __typename so Django templates can access it (no leading _)
        if "__typename" in event:
            event["event_type"] = event.pop("__typename")

    return {
        "events": events,
        "cursor": data.get("cursor"),
        "has_more": data.get("hasMore", False),
    }


def submit_job(
    job_name,
    repository_location_name=None,
    repository_name=None,
    run_config=None,
    tags=None,
):
    """Submit a job for execution. Returns the run ID."""
    client = get_client()
    return client.submit_job_execution(
        job_name=job_name,
        repository_location_name=repository_location_name,
        repository_name=repository_name,
        run_config=run_config,
        tags=tags,
    )


def cancel_run(run_id):
    """Cancel a running job."""
    client = get_client()
    client.terminate_run(run_id)


def reexecute_run(run_id):
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
    tags = (
        {
            t["key"]: t["value"]
            for t in run.get("tags", [])
            if not t["key"].startswith("dagster/")
        }
        or None
    )

    return submit_job(
        job_name=run["jobName"],
        run_config=run_config,
        tags=tags,
    )
