from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import django
import pytest

if TYPE_CHECKING:
    from django.contrib.auth.models import User
    from django.test import Client

    from django_dagster.models import DagsterJob, DagsterRun

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.fixtures.settings")


def pytest_configure() -> None:
    django.setup()


@pytest.fixture
def staff_user(db: Any) -> User:
    from django.contrib.auth.models import User

    return User.objects.create_user(
        username="staff",
        password="password",
        is_staff=True,
    )


@pytest.fixture
def staff_client(client: Client, staff_user: User) -> Client:
    client.login(username="staff", password="password")
    return client


def _add_perms(
    user: User, model: type[DagsterJob] | type[DagsterRun], codenames: list[str]
) -> None:
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(model)
    for codename in codenames:
        perm = Permission.objects.get(content_type=ct, codename=codename)
        user.user_permissions.add(perm)


@pytest.fixture
def viewer_user(db: Any) -> User:
    """Staff user with only view permissions (no action permissions)."""
    from django.contrib.auth.models import User
    from django_dagster.models import DagsterJob, DagsterRun

    user = User.objects.create_user(
        username="viewer",
        password="password",
        is_staff=True,
    )
    _add_perms(user, DagsterJob, ["view_dagsterjob"])
    _add_perms(user, DagsterRun, ["view_dagsterrun"])
    return user


@pytest.fixture
def viewer_client(client: Client, viewer_user: User) -> Client:
    client.login(username="viewer", password="password")
    return client


@pytest.fixture
def full_perm_user(db: Any) -> User:
    """Staff user with all Dagster permissions."""
    from django.contrib.auth.models import User
    from django_dagster.models import DagsterJob, DagsterRun

    user = User.objects.create_user(
        username="full",
        password="password",
        is_staff=True,
    )
    _add_perms(
        user,
        DagsterJob,
        [
            "view_dagsterjob",
            "trigger_dagsterjob",
            "access_dagster_ui",
        ],
    )
    _add_perms(
        user,
        DagsterRun,
        [
            "view_dagsterrun",
            "cancel_dagsterrun",
            "reexecute_dagsterrun",
        ],
    )
    return user


@pytest.fixture
def full_perm_client(client: Client, full_perm_user: User) -> Client:
    client.login(username="full", password="password")
    return client


@pytest.fixture
def superuser(db: Any) -> User:
    from django.contrib.auth.models import User

    return User.objects.create_superuser(
        username="admin",
        password="password",
    )


@pytest.fixture
def superuser_client(client: Client, superuser: User) -> Client:
    client.login(username="admin", password="password")
    return client


# ---------------------------------------------------------------------------
# GraphQL response data fixtures (fresh copy per test for isolation)
# ---------------------------------------------------------------------------


@pytest.fixture
def graphql_repositories_response() -> dict[str, Any]:
    return {
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


@pytest.fixture
def graphql_runs_response() -> dict[str, Any]:
    return {
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


def make_run_detail_response(
    run_id: str = "abc12345-def0-1234-5678-abcdef012345",
    status: str = "SUCCESS",
) -> dict[str, Any]:
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


@pytest.fixture
def graphql_run_detail_response() -> dict[str, Any]:
    return make_run_detail_response()


@pytest.fixture
def graphql_run_events_response() -> dict[str, Any]:
    return {
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


@pytest.fixture
def graphql_run_not_found_response() -> dict[str, Any]:
    return {
        "runOrError": {
            "__typename": "RunNotFoundError",
            "runId": "nonexistent",
            "message": "Run nonexistent not found",
        },
    }
