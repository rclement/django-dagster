import pytest
from django.contrib.auth.models import User


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="staff",
        password="password",
        is_staff=True,
    )


@pytest.fixture
def staff_client(client, staff_user):
    client.login(username="staff", password="password")
    return client


GRAPHQL_REPOSITORIES_RESPONSE = {
    "repositoriesOrError": {
        "nodes": [
            {
                "name": "my_repo",
                "location": {"name": "my_location"},
                "pipelines": [
                    {"name": "etl_job", "description": "Daily ETL pipeline"},
                    {"name": "ml_train", "description": ""},
                ],
            },
            {
                "name": "other_repo",
                "location": {"name": "other_location"},
                "pipelines": [
                    {"name": "report_job", "description": None},
                ],
            },
        ],
    },
}

GRAPHQL_RUNS_RESPONSE = {
    "runsOrError": {
        "results": [
            {
                "runId": "abc12345-def0-1234-5678-abcdef012345",
                "jobName": "etl_job",
                "status": "SUCCESS",
                "startTime": 1700000000.0,
                "endTime": 1700003600.0,
                "tags": [{"key": "env", "value": "prod"}],
            },
            {
                "runId": "fff99999-0000-1111-2222-333344445555",
                "jobName": "etl_job",
                "status": "FAILURE",
                "startTime": 1700010000.0,
                "endTime": 1700011000.0,
                "tags": [],
            },
        ],
    },
}


def _make_run_detail_response(
    run_id="abc12345-def0-1234-5678-abcdef012345",
    status="SUCCESS",
):
    return {
        "runOrError": {
            "__typename": "Run",
            "runId": run_id,
            "jobName": "etl_job",
            "status": status,
            "startTime": 1700000000.0,
            "endTime": 1700003600.0,
            "runConfigYaml": "ops:\n  my_op:\n    config:\n      param: value\n",
            "tags": [
                {"key": "env", "value": "prod"},
                {"key": "dagster/step_selection", "value": "all"},
            ],
            "stats": {
                "stepsSucceeded": 3,
                "stepsFailed": 0,
                "materializations": 2,
                "expectations": 1,
                "startTime": 1700000000.0,
                "endTime": 1700003600.0,
            },
        },
    }


GRAPHQL_RUN_DETAIL_RESPONSE = _make_run_detail_response()

GRAPHQL_RUN_EVENTS_RESPONSE = {
    "logsForRun": {
        "__typename": "EventConnection",
        "events": [
            {
                "__typename": "RunStartEvent",
                "message": "Started execution of run.",
                "timestamp": "1700000000000",
                "level": "DEBUG",
                "stepKey": None,
            },
            {
                "__typename": "StepStartEvent",
                "message": "Started execution of step.",
                "timestamp": "1700000001000",
                "level": "DEBUG",
                "stepKey": "my_op",
            },
            {
                "__typename": "LogMessageEvent",
                "message": "Processing data...",
                "timestamp": "1700000002000",
                "level": "INFO",
                "stepKey": "my_op",
            },
            {
                "__typename": "StepSuccessEvent",
                "message": "Finished execution of step.",
                "timestamp": "1700000003000",
                "level": "DEBUG",
                "stepKey": "my_op",
            },
            {
                "__typename": "RunSuccessEvent",
                "message": "Finished execution of run.",
                "timestamp": "1700000004000",
                "level": "DEBUG",
                "stepKey": None,
            },
        ],
        "cursor": "5",
        "hasMore": False,
    },
}

GRAPHQL_RUN_NOT_FOUND_RESPONSE = {
    "runOrError": {
        "__typename": "RunNotFoundError",
        "runId": "nonexistent",
        "message": "Run nonexistent not found",
    },
}
