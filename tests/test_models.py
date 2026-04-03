from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from django_dagster.models import DagsterJob, DagsterRun

from tests.conftest import make_run_detail_response


# ---------------------------------------------------------------------------
# Package-level lazy exports
# ---------------------------------------------------------------------------


def test_package_exports_dagster_job() -> None:
    import django_dagster

    assert django_dagster.DagsterJob is DagsterJob


def test_package_exports_dagster_run() -> None:
    import django_dagster

    assert django_dagster.DagsterRun is DagsterRun


def test_package_unknown_attr_raises() -> None:
    import django_dagster

    with pytest.raises(AttributeError, match="no attribute"):
        django_dagster.nonexistent  # noqa: B018


# ---------------------------------------------------------------------------
# DagsterJob
# ---------------------------------------------------------------------------


class TestDagsterJobFromApi:
    def test_creates_instance(self) -> None:
        data = {
            "name": "etl_job",
            "description": "Daily ETL pipeline",
            "repository": "my_repo",
            "location": "my_location",
        }
        job = DagsterJob._from_api(data)

        assert job.name == "etl_job"
        assert job.description == "Daily ETL pipeline"
        assert job.repository == "my_repo"
        assert job.location == "my_location"

    def test_str(self) -> None:
        job = DagsterJob._from_api(
            {"name": "etl_job", "description": "", "repository": "r", "location": "l"}
        )
        assert str(job) == "etl_job"

    def test_repr(self) -> None:
        job = DagsterJob._from_api(
            {"name": "etl_job", "description": "", "repository": "r", "location": "l"}
        )
        assert repr(job) == "<DagsterJob: etl_job>"


class TestDagsterJobManager:
    @patch("django_dagster.client.DagsterGraphQLClient")
    def test_all(
        self,
        mock_cls: MagicMock,
        graphql_repositories_response: dict[str, Any],
    ) -> None:
        mock_client = MagicMock()
        mock_client._execute.return_value = graphql_repositories_response
        mock_cls.return_value = mock_client

        jobs = DagsterJob.objects.all()

        assert len(jobs) == 3
        assert all(isinstance(j, DagsterJob) for j in jobs)
        assert jobs[0].name == "etl_job"
        assert jobs[0].repository == "my_repo"
        assert jobs[0].location == "my_location"

    @patch("django_dagster.client.DagsterGraphQLClient")
    def test_get(
        self,
        mock_cls: MagicMock,
        graphql_pipeline_response: dict[str, Any],
    ) -> None:
        mock_client = MagicMock()
        mock_client._execute.return_value = graphql_pipeline_response
        mock_cls.return_value = mock_client

        job = DagsterJob.objects.get(
            name="etl_job", repository="my_repo", location="my_location"
        )

        assert isinstance(job, DagsterJob)
        assert job.name == "etl_job"

    @patch("django_dagster.client.DagsterGraphQLClient")
    def test_get_not_found(
        self,
        mock_cls: MagicMock,
        graphql_pipeline_not_found_response: dict[str, Any],
    ) -> None:
        mock_client = MagicMock()
        mock_client._execute.return_value = graphql_pipeline_not_found_response
        mock_cls.return_value = mock_client

        with pytest.raises(DagsterJob.DoesNotExist):
            DagsterJob.objects.get(
                name="nonexistent", repository="my_repo", location="my_location"
            )


class TestDagsterJobSubmit:
    @patch("django_dagster.client.DagsterGraphQLClient")
    def test_submit(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.submit_job_execution.return_value = "new-run-id"
        mock_cls.return_value = mock_client

        job = DagsterJob._from_api(
            {
                "name": "etl_job",
                "description": "",
                "repository": "my_repo",
                "location": "my_location",
            }
        )
        run_id = job.submit(
            run_config={"ops": {"x": {"config": {"k": 1}}}},
            tags={"env": "test"},
        )

        assert run_id == "new-run-id"
        mock_client.submit_job_execution.assert_called_once_with(
            job_name="etl_job",
            repository_location_name="my_location",
            repository_name="my_repo",
            run_config={"ops": {"x": {"config": {"k": 1}}}},
            tags={"env": "test"},
        )

    @patch("django_dagster.client.DagsterGraphQLClient")
    def test_submit_no_config(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.submit_job_execution.return_value = "run-123"
        mock_cls.return_value = mock_client

        job = DagsterJob._from_api(
            {"name": "etl_job", "description": "", "repository": "r", "location": "l"}
        )
        run_id = job.submit()

        assert run_id == "run-123"
        mock_client.submit_job_execution.assert_called_once_with(
            job_name="etl_job",
            repository_location_name="l",
            repository_name="r",
            run_config=None,
            tags=None,
        )


class TestDagsterJobDefaultRunConfig:
    @patch("django_dagster.client.DagsterGraphQLClient")
    def test_get_default_run_config(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client._execute.return_value = {
            "runConfigSchemaOrError": {
                "rootDefaultYaml": "ops:\n  my_op:\n    config:\n      param: value\n",
            }
        }
        mock_cls.return_value = mock_client

        job = DagsterJob._from_api(
            {
                "name": "etl_job",
                "description": "",
                "repository": "my_repo",
                "location": "my_location",
            }
        )
        config = job.get_default_run_config()

        assert config == {"ops": {"my_op": {"config": {"param": "value"}}}}
        # Should use the job's repo info directly (no extra get_jobs call)
        mock_client._execute.assert_called_once()
        variables = mock_client._execute.call_args[0][1]
        assert variables["selector"] == {
            "pipelineName": "etl_job",
            "repositoryName": "my_repo",
            "repositoryLocationName": "my_location",
        }


# ---------------------------------------------------------------------------
# DagsterRun
# ---------------------------------------------------------------------------


class TestDagsterRunFromApi:
    def test_creates_instance(self) -> None:
        data = {
            "runId": "abc12345-def0-1234-5678-abcdef012345",
            "jobName": "etl_job",
            "status": "SUCCESS",
            "startTime": datetime(2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc),
            "endTime": datetime(2023, 11, 14, 23, 13, 20, tzinfo=timezone.utc),
            "tags": [{"key": "env", "value": "prod"}],
            "runConfigYaml": "ops:\n  my_op:\n    config:\n      x: 1\n",
            "stats": {
                "stepsSucceeded": 3,
                "stepsFailed": 0,
                "materializations": 2,
                "expectations": 1,
            },
        }
        run = DagsterRun._from_api(data)

        assert run.run_id == "abc12345-def0-1234-5678-abcdef012345"
        assert run.job_name == "etl_job"
        assert run.status == "SUCCESS"
        assert run.start_time == datetime(2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc)
        assert run.end_time == datetime(2023, 11, 14, 23, 13, 20, tzinfo=timezone.utc)
        assert run.tags == [{"key": "env", "value": "prod"}]
        assert run.run_config_yaml == "ops:\n  my_op:\n    config:\n      x: 1\n"
        assert run.stats == {
            "steps_succeeded": 3,
            "steps_failed": 0,
            "materializations": 2,
            "expectations": 1,
        }

    def test_creates_instance_without_stats(self) -> None:
        data: dict[str, Any] = {
            "runId": "abc123",
            "jobName": "etl_job",
            "status": "STARTED",
            "startTime": None,
            "endTime": None,
            "tags": [],
        }
        run = DagsterRun._from_api(data)

        assert run.stats is None
        assert run.run_config_yaml is None

    def test_str(self) -> None:
        run = DagsterRun._from_api(
            {
                "runId": "abc123",
                "jobName": "j",
                "status": "SUCCESS",
                "startTime": None,
                "endTime": None,
            }
        )
        assert str(run) == "abc123"

    def test_repr(self) -> None:
        run = DagsterRun._from_api(
            {
                "runId": "abc123",
                "jobName": "j",
                "status": "SUCCESS",
                "startTime": None,
                "endTime": None,
            }
        )
        assert repr(run) == "<DagsterRun: abc123>"


class TestDagsterRunManager:
    @patch("django_dagster.client.DagsterGraphQLClient")
    def test_all(
        self, mock_cls: MagicMock, graphql_runs_response: dict[str, Any]
    ) -> None:
        mock_client = MagicMock()
        mock_client._execute.return_value = graphql_runs_response
        mock_cls.return_value = mock_client

        runs = DagsterRun.objects.all()

        assert len(runs) == 2
        assert all(isinstance(r, DagsterRun) for r in runs)
        assert runs[0].run_id == "abc12345-def0-1234-5678-abcdef012345"
        assert runs[0].status == "SUCCESS"
        assert isinstance(runs[0].start_time, datetime)

    @patch("django_dagster.client.DagsterGraphQLClient")
    def test_filter(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client._execute.return_value = {"runsOrError": {"results": []}}
        mock_cls.return_value = mock_client

        runs = DagsterRun.objects.filter(
            job_name="etl_job", statuses=["FAILURE"], limit=10
        )

        assert runs == []
        call_args = mock_client._execute.call_args
        variables = call_args[0][1]
        assert variables["filter"]["pipelineName"] == "etl_job"
        assert variables["filter"]["statuses"] == ["FAILURE"]
        assert variables["limit"] == 10

    @patch("django_dagster.client.DagsterGraphQLClient")
    def test_get(
        self,
        mock_cls: MagicMock,
        graphql_run_detail_response: dict[str, Any],
    ) -> None:
        mock_client = MagicMock()
        mock_client._execute.return_value = graphql_run_detail_response
        mock_cls.return_value = mock_client

        run = DagsterRun.objects.get(run_id="abc12345-def0-1234-5678-abcdef012345")

        assert isinstance(run, DagsterRun)
        assert run.run_id == "abc12345-def0-1234-5678-abcdef012345"
        assert run.job_name == "etl_job"
        assert run.repository == "my_repo"
        assert run.location == "my_location"

    @patch("django_dagster.client.DagsterGraphQLClient")
    def test_get_not_found(
        self,
        mock_cls: MagicMock,
        graphql_run_not_found_response: dict[str, Any],
    ) -> None:
        mock_client = MagicMock()
        mock_client._execute.return_value = graphql_run_not_found_response
        mock_cls.return_value = mock_client

        with pytest.raises(DagsterRun.DoesNotExist):
            DagsterRun.objects.get(run_id="nonexistent")


class TestDagsterRunCancel:
    @patch("django_dagster.client.DagsterGraphQLClient")
    def test_cancel(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        run = DagsterRun._from_api(
            {
                "runId": "abc123",
                "jobName": "j",
                "status": "STARTED",
                "startTime": None,
                "endTime": None,
            }
        )
        run.cancel()

        mock_client.terminate_run.assert_called_once_with("abc123")


class TestDagsterRunReexecute:
    @patch("django_dagster.client.DagsterGraphQLClient")
    def test_reexecute(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client._execute.return_value = make_run_detail_response(
            run_id="original-run-id", status="SUCCESS"
        )
        mock_client.submit_job_execution.return_value = "new-run-id"
        mock_cls.return_value = mock_client

        run = DagsterRun._from_api(
            {
                "runId": "original-run-id",
                "jobName": "etl_job",
                "status": "SUCCESS",
                "startTime": None,
                "endTime": None,
            }
        )
        new_id = run.reexecute()

        assert new_id == "new-run-id"


class TestDagsterRunGetEvents:
    @patch("django_dagster.client.DagsterGraphQLClient")
    def test_get_events(
        self,
        mock_cls: MagicMock,
        graphql_run_events_response: dict[str, Any],
    ) -> None:
        mock_client = MagicMock()
        mock_client._execute.return_value = graphql_run_events_response
        mock_cls.return_value = mock_client

        run = DagsterRun._from_api(
            {
                "runId": "abc123",
                "jobName": "j",
                "status": "SUCCESS",
                "startTime": None,
                "endTime": None,
            }
        )
        result = run.get_events()

        assert result is not None
        assert len(result["events"]) == 5
        # Events should have snake_case keys
        event = result["events"][0]
        assert "step_key" in event
        assert "event_type" in event
        assert isinstance(event["timestamp"], datetime)

    @patch("django_dagster.client.DagsterGraphQLClient")
    def test_get_events_not_found(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client._execute.return_value = {
            "logsForRun": {
                "__typename": "RunNotFoundError",
                "message": "Run not found",
            },
        }
        mock_cls.return_value = mock_client

        run = DagsterRun._from_api(
            {
                "runId": "nonexistent",
                "jobName": "j",
                "status": "SUCCESS",
                "startTime": None,
                "endTime": None,
            }
        )
        result = run.get_events()

        assert result is None
