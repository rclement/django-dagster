from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import (
    GRAPHQL_REPOSITORIES_RESPONSE,
    GRAPHQL_RUN_DETAIL_RESPONSE,
    GRAPHQL_RUN_EVENTS_RESPONSE,
    GRAPHQL_RUN_NOT_FOUND_RESPONSE,
    GRAPHQL_RUNS_RESPONSE,
    _make_run_detail_response,
)


@patch("django_dagster.client.DagsterGraphQLClient")
def test_get_client_parses_url(mock_cls, settings):
    settings.DAGSTER_URL = "https://dagster.example.com:8080"

    from django_dagster.client import get_client

    get_client()
    mock_cls.assert_called_once_with(
        hostname="dagster.example.com",
        port_number=8080,
        use_https=True,
    )


@patch("django_dagster.client.DagsterGraphQLClient")
def test_get_client_http_defaults(mock_cls, settings):
    settings.DAGSTER_URL = "http://localhost:3000"

    from django_dagster.client import get_client

    get_client()
    mock_cls.assert_called_once_with(
        hostname="localhost",
        port_number=3000,
        use_https=False,
    )


@patch("django_dagster.client.DagsterGraphQLClient")
def test_get_jobs(mock_cls):
    mock_client = MagicMock()
    mock_client._execute.return_value = GRAPHQL_REPOSITORIES_RESPONSE
    mock_cls.return_value = mock_client

    from django_dagster.client import get_jobs

    jobs = get_jobs()

    assert len(jobs) == 3
    assert jobs[0] == {
        "name": "etl_job",
        "description": "Daily ETL pipeline",
        "repository": "my_repo",
        "location": "my_location",
    }
    assert jobs[1]["name"] == "ml_train"
    assert jobs[2] == {
        "name": "report_job",
        "description": None,
        "repository": "other_repo",
        "location": "other_location",
    }


@patch("django_dagster.client.DagsterGraphQLClient")
def test_get_runs(mock_cls):
    mock_client = MagicMock()
    mock_client._execute.return_value = GRAPHQL_RUNS_RESPONSE
    mock_cls.return_value = mock_client

    from django_dagster.client import get_runs

    runs = get_runs()

    assert len(runs) == 2
    assert runs[0]["runId"] == "abc12345-def0-1234-5678-abcdef012345"
    assert runs[0]["status"] == "SUCCESS"
    # Timestamps should be converted to datetime
    assert isinstance(runs[0]["startTime"], datetime)
    assert runs[0]["startTime"] == datetime(2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc)


@patch("django_dagster.client.DagsterGraphQLClient")
def test_get_runs_with_filters(mock_cls):
    mock_client = MagicMock()
    mock_client._execute.return_value = {"runsOrError": {"results": []}}
    mock_cls.return_value = mock_client

    from django_dagster.client import get_runs

    get_runs(job_name="etl_job", statuses=["FAILURE"], cursor="some-cursor", limit=10)

    call_args = mock_client._execute.call_args
    variables = call_args[0][1]
    assert variables == {
        "limit": 10,
        "cursor": "some-cursor",
        "filter": {
            "pipelineName": "etl_job",
            "statuses": ["FAILURE"],
        },
    }


@patch("django_dagster.client.DagsterGraphQLClient")
def test_get_runs_no_filter_key_when_empty(mock_cls):
    mock_client = MagicMock()
    mock_client._execute.return_value = {"runsOrError": {"results": []}}
    mock_cls.return_value = mock_client

    from django_dagster.client import get_runs

    get_runs()

    call_args = mock_client._execute.call_args
    variables = call_args[0][1]
    assert "filter" not in variables
    assert variables == {"limit": 25}


@patch("django_dagster.client.DagsterGraphQLClient")
def test_get_run(mock_cls):
    mock_client = MagicMock()
    mock_client._execute.return_value = GRAPHQL_RUN_DETAIL_RESPONSE
    mock_cls.return_value = mock_client

    from django_dagster.client import get_run

    run = get_run("abc12345-def0-1234-5678-abcdef012345")

    assert run["runId"] == "abc12345-def0-1234-5678-abcdef012345"
    assert run["jobName"] == "etl_job"
    assert run["status"] == "SUCCESS"
    assert run["stats"]["stepsSucceeded"] == 3
    assert run["runConfigYaml"].startswith("ops:")
    assert isinstance(run["startTime"], datetime)


@patch("django_dagster.client.DagsterGraphQLClient")
def test_get_run_not_found(mock_cls):
    mock_client = MagicMock()
    mock_client._execute.return_value = GRAPHQL_RUN_NOT_FOUND_RESPONSE
    mock_cls.return_value = mock_client

    from django_dagster.client import get_run

    result = get_run("nonexistent")
    assert result is None


@patch("django_dagster.client.DagsterGraphQLClient")
def test_get_run_python_error(mock_cls):
    mock_client = MagicMock()
    mock_client._execute.return_value = {
        "runOrError": {
            "__typename": "PythonError",
            "message": "Something broke",
        },
    }
    mock_cls.return_value = mock_client

    from django_dagster.client import get_run

    with pytest.raises(Exception, match="Something broke"):
        get_run("some-id")


@patch("django_dagster.client.DagsterGraphQLClient")
def test_submit_job(mock_cls):
    mock_client = MagicMock()
    mock_client.submit_job_execution.return_value = "new-run-id-123"
    mock_cls.return_value = mock_client

    from django_dagster.client import submit_job

    run_id = submit_job(
        "etl_job",
        run_config={"ops": {"my_op": {"config": {"x": 1}}}},
        tags={"env": "test"},
    )

    assert run_id == "new-run-id-123"
    mock_client.submit_job_execution.assert_called_once_with(
        job_name="etl_job",
        repository_location_name=None,
        repository_name=None,
        run_config={"ops": {"my_op": {"config": {"x": 1}}}},
        tags={"env": "test"},
    )


@patch("django_dagster.client.DagsterGraphQLClient")
def test_cancel_run(mock_cls):
    mock_client = MagicMock()
    mock_cls.return_value = mock_client

    from django_dagster.client import cancel_run

    cancel_run("abc123")
    mock_client.terminate_run.assert_called_once_with("abc123")


@patch("django_dagster.client.DagsterGraphQLClient")
def test_reexecute_run(mock_cls):
    mock_client = MagicMock()
    # First call: get_run fetches the original run detail
    # Second call: submit_job triggers re-execution
    mock_client._execute.return_value = _make_run_detail_response(
        run_id="original-run-id", status="SUCCESS"
    )
    mock_client.submit_job_execution.return_value = "new-run-id"
    mock_cls.return_value = mock_client

    from django_dagster.client import reexecute_run

    new_id = reexecute_run("original-run-id")

    assert new_id == "new-run-id"
    # Should submit with same job name, parsed config, user tags only
    mock_client.submit_job_execution.assert_called_once_with(
        job_name="etl_job",
        repository_location_name=None,
        repository_name=None,
        run_config={"ops": {"my_op": {"config": {"param": "value"}}}},
        tags={"env": "prod"},
    )


@patch("django_dagster.client.DagsterGraphQLClient")
def test_reexecute_run_not_found(mock_cls):
    mock_client = MagicMock()
    mock_client._execute.return_value = GRAPHQL_RUN_NOT_FOUND_RESPONSE
    mock_cls.return_value = mock_client

    from django_dagster.client import reexecute_run

    with pytest.raises(ValueError, match="not found"):
        reexecute_run("nonexistent")


@patch("django_dagster.client.DagsterGraphQLClient")
def test_reexecute_run_empty_config(mock_cls):
    """When run config is empty YAML ({}), it should pass None."""
    mock_client = MagicMock()
    response = _make_run_detail_response()
    response["runOrError"]["runConfigYaml"] = "{}\n"
    response["runOrError"]["tags"] = []
    mock_client._execute.return_value = response
    mock_client.submit_job_execution.return_value = "new-id"
    mock_cls.return_value = mock_client

    from django_dagster.client import reexecute_run

    reexecute_run("some-id")

    mock_client.submit_job_execution.assert_called_once_with(
        job_name="etl_job",
        repository_location_name=None,
        repository_name=None,
        run_config=None,
        tags=None,
    )


@patch("django_dagster.client.DagsterGraphQLClient")
def test_get_run_events(mock_cls):
    mock_client = MagicMock()
    mock_client._execute.return_value = GRAPHQL_RUN_EVENTS_RESPONSE
    mock_cls.return_value = mock_client

    from django_dagster.client import get_run_events

    result = get_run_events("abc123")

    assert result is not None
    assert len(result["events"]) == 5
    assert result["cursor"] == "5"
    assert result["has_more"] is False
    # Timestamps should be converted to datetime
    assert isinstance(result["events"][0]["timestamp"], datetime)
    assert result["events"][0]["event_type"] == "RunStartEvent"
    assert result["events"][2]["message"] == "Processing data..."
    assert result["events"][2]["stepKey"] == "my_op"


@patch("django_dagster.client.DagsterGraphQLClient")
def test_get_run_events_not_found(mock_cls):
    mock_client = MagicMock()
    mock_client._execute.return_value = {
        "logsForRun": {
            "__typename": "RunNotFoundError",
            "message": "Run not found",
        },
    }
    mock_cls.return_value = mock_client

    from django_dagster.client import get_run_events

    result = get_run_events("nonexistent")
    assert result is None


@patch("django_dagster.client.DagsterGraphQLClient")
def test_get_run_events_python_error(mock_cls):
    mock_client = MagicMock()
    mock_client._execute.return_value = {
        "logsForRun": {
            "__typename": "PythonError",
            "message": "Something broke",
        },
    }
    mock_cls.return_value = mock_client

    from django_dagster.client import get_run_events

    with pytest.raises(Exception, match="Something broke"):
        get_run_events("some-id")


@patch("django_dagster.client.DagsterGraphQLClient")
def test_get_job_default_run_config(mock_cls):
    mock_client = MagicMock()
    # First call: get_jobs
    # Second call: runConfigSchemaOrError
    mock_client._execute.side_effect = [
        GRAPHQL_REPOSITORIES_RESPONSE,
        {
            "runConfigSchemaOrError": {
                "rootDefaultYaml": "ops:\n  my_op:\n    config:\n      param: value\n",
            }
        },
    ]
    mock_cls.return_value = mock_client

    from django_dagster.client import get_job_default_run_config

    config = get_job_default_run_config("etl_job")

    assert config == {"ops": {"my_op": {"config": {"param": "value"}}}}
    # Verify the selector was built correctly
    schema_call = mock_client._execute.call_args_list[1]
    variables = schema_call[0][1]
    assert variables["selector"] == {
        "pipelineName": "etl_job",
        "repositoryName": "my_repo",
        "repositoryLocationName": "my_location",
    }


@patch("django_dagster.client.DagsterGraphQLClient")
def test_get_job_default_run_config_empty(mock_cls):
    mock_client = MagicMock()
    mock_client._execute.side_effect = [
        GRAPHQL_REPOSITORIES_RESPONSE,
        {"runConfigSchemaOrError": {"rootDefaultYaml": "{}\n"}},
    ]
    mock_cls.return_value = mock_client

    from django_dagster.client import get_job_default_run_config

    config = get_job_default_run_config("etl_job")

    assert config == {}


@patch("django_dagster.client.DagsterGraphQLClient")
def test_get_job_default_run_config_unknown_job(mock_cls):
    mock_client = MagicMock()
    mock_client._execute.return_value = GRAPHQL_REPOSITORIES_RESPONSE
    mock_cls.return_value = mock_client

    from django_dagster.client import get_job_default_run_config

    config = get_job_default_run_config("nonexistent_job")

    assert config == {}


def test_parse_timestamp_none():
    from django_dagster.client import _parse_timestamp

    assert _parse_timestamp(None) is None


def test_parse_timestamp_converts():
    from django_dagster.client import _parse_timestamp

    result = _parse_timestamp(1700000000.0)
    assert result == datetime(2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc)
