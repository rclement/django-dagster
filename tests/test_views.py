from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from django.urls import reverse


# ---------------------------------------------------------------------------
# Auth: all views require staff
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAuthRequired:
    URLS = [
        "dagster:job_list",
        "dagster:run_list",
        "dagster:trigger_job",
    ]

    def test_anonymous_redirected(self, client):
        for name in self.URLS:
            resp = client.get(reverse(name))
            assert resp.status_code == 302
            assert "/admin/login/" in resp.url or "/accounts/login/" in resp.url

    def test_non_staff_redirected(self, client, db):
        from django.contrib.auth.models import User

        User.objects.create_user("regular", password="password")
        client.login(username="regular", password="password")

        for name in self.URLS:
            resp = client.get(reverse(name))
            assert resp.status_code == 302

    def test_run_detail_anonymous(self, client):
        resp = client.get(reverse("dagster:run_detail", args=["abc123"]))
        assert resp.status_code == 302

    def test_cancel_anonymous(self, client):
        resp = client.post(reverse("dagster:cancel_run", args=["abc123"]))
        assert resp.status_code == 302

    def test_retry_anonymous(self, client):
        resp = client.post(reverse("dagster:retry_run", args=["abc123"]))
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Job list view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestJobListView:
    @patch("django_dagster.views.client.get_jobs")
    def test_renders_jobs(self, mock_get_jobs, staff_client):
        mock_get_jobs.return_value = [
            {
                "name": "etl_job",
                "description": "Daily ETL",
                "repository": "repo",
                "location": "loc",
            },
        ]

        resp = staff_client.get(reverse("dagster:job_list"))

        assert resp.status_code == 200
        assert b"etl_job" in resp.content
        assert b"Daily ETL" in resp.content

    @patch("django_dagster.views.client.get_jobs")
    def test_empty_jobs(self, mock_get_jobs, staff_client):
        mock_get_jobs.return_value = []

        resp = staff_client.get(reverse("dagster:job_list"))

        assert resp.status_code == 200
        assert b"No jobs found" in resp.content

    @patch("django_dagster.views.client.get_jobs")
    def test_connection_error(self, mock_get_jobs, staff_client):
        mock_get_jobs.side_effect = ConnectionError("Connection refused")

        resp = staff_client.get(reverse("dagster:job_list"))

        assert resp.status_code == 200
        assert b"Failed to connect to Dagster" in resp.content


# ---------------------------------------------------------------------------
# Run list view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRunListView:
    @patch("django_dagster.views.client.get_runs")
    def test_renders_runs(self, mock_get_runs, staff_client):
        mock_get_runs.return_value = [
            {
                "runId": "abc12345-def0-1234-5678-abcdef012345",
                "jobName": "etl_job",
                "status": "SUCCESS",
                "startTime": datetime(2023, 11, 14, tzinfo=timezone.utc),
                "endTime": datetime(2023, 11, 14, 1, 0, tzinfo=timezone.utc),
                "tags": [],
            },
        ]

        resp = staff_client.get(reverse("dagster:run_list"))

        assert resp.status_code == 200
        assert b"abc12345" in resp.content
        assert b"SUCCESS" in resp.content
        mock_get_runs.assert_called_once_with(job_name=None, statuses=None)

    @patch("django_dagster.views.client.get_runs")
    def test_filters(self, mock_get_runs, staff_client):
        mock_get_runs.return_value = []

        resp = staff_client.get(
            reverse("dagster:run_list") + "?job=etl_job&status=FAILURE"
        )

        assert resp.status_code == 200
        mock_get_runs.assert_called_once_with(
            job_name="etl_job", statuses=["FAILURE"]
        )

    @patch("django_dagster.views.client.get_runs")
    def test_connection_error(self, mock_get_runs, staff_client):
        mock_get_runs.side_effect = ConnectionError("refused")

        resp = staff_client.get(reverse("dagster:run_list"))

        assert resp.status_code == 200
        assert b"Failed to connect to Dagster" in resp.content


# ---------------------------------------------------------------------------
# Run detail view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRunDetailView:
    def _make_run(self, status="SUCCESS"):
        return {
            "runId": "abc12345-def0-1234-5678-abcdef012345",
            "jobName": "etl_job",
            "status": status,
            "startTime": datetime(2023, 11, 14, tzinfo=timezone.utc),
            "endTime": datetime(2023, 11, 14, 1, 0, tzinfo=timezone.utc),
            "runConfigYaml": "ops:\n  my_op:\n    config:\n      x: 1\n",
            "tags": [{"key": "env", "value": "prod"}],
            "stats": {
                "stepsSucceeded": 3,
                "stepsFailed": 0,
                "materializations": 2,
                "expectations": 1,
                "startTime": 1700000000.0,
                "endTime": 1700003600.0,
            },
            "__typename": "Run",
        }

    @patch("django_dagster.views.client.get_run")
    def test_renders_detail(self, mock_get_run, staff_client):
        mock_get_run.return_value = self._make_run()

        run_id = "abc12345-def0-1234-5678-abcdef012345"
        resp = staff_client.get(reverse("dagster:run_detail", args=[run_id]))

        assert resp.status_code == 200
        assert b"etl_job" in resp.content
        assert b"SUCCESS" in resp.content
        assert b"env=prod" in resp.content

    @patch("django_dagster.views.client.get_run")
    def test_cancel_button_shown_for_running(self, mock_get_run, staff_client):
        mock_get_run.return_value = self._make_run(status="STARTED")

        run_id = "abc12345-def0-1234-5678-abcdef012345"
        resp = staff_client.get(reverse("dagster:run_detail", args=[run_id]))

        assert resp.status_code == 200
        assert b"Cancel Run" in resp.content

    @patch("django_dagster.views.client.get_run")
    def test_retry_button_shown_for_failed(self, mock_get_run, staff_client):
        mock_get_run.return_value = self._make_run(status="FAILURE")

        run_id = "abc12345-def0-1234-5678-abcdef012345"
        resp = staff_client.get(reverse("dagster:run_detail", args=[run_id]))

        assert resp.status_code == 200
        assert b"Retry Run" in resp.content
        # Cancel should not be shown for failed runs
        assert b"Cancel Run" not in resp.content

    @patch("django_dagster.views.client.get_run")
    def test_no_action_buttons_for_success(self, mock_get_run, staff_client):
        mock_get_run.return_value = self._make_run(status="SUCCESS")

        run_id = "abc12345-def0-1234-5678-abcdef012345"
        resp = staff_client.get(reverse("dagster:run_detail", args=[run_id]))

        assert resp.status_code == 200
        assert b"Cancel Run" not in resp.content
        assert b"Retry Run" not in resp.content

    @patch("django_dagster.views.client.get_run")
    def test_not_found_redirects(self, mock_get_run, staff_client):
        mock_get_run.return_value = None

        resp = staff_client.get(
            reverse("dagster:run_detail", args=["nonexistent"])
        )

        assert resp.status_code == 302
        assert reverse("dagster:run_list") in resp.url

    @patch("django_dagster.views.client.get_run")
    def test_error_redirects(self, mock_get_run, staff_client):
        mock_get_run.side_effect = Exception("boom")

        resp = staff_client.get(
            reverse("dagster:run_detail", args=["some-id"])
        )

        # Error sets run=None, which triggers redirect
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Trigger job view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTriggerJobView:
    @patch("django_dagster.views.client.get_jobs")
    def test_get_renders_form(self, mock_get_jobs, staff_client):
        mock_get_jobs.return_value = [
            {"name": "etl_job", "description": "", "repository": "r", "location": "l"},
        ]

        resp = staff_client.get(reverse("dagster:trigger_job"))

        assert resp.status_code == 200
        assert b"etl_job" in resp.content

    @patch("django_dagster.views.client.get_jobs")
    def test_get_prefills_job_name(self, mock_get_jobs, staff_client):
        mock_get_jobs.return_value = [
            {"name": "etl_job", "description": "", "repository": "r", "location": "l"},
        ]

        resp = staff_client.get(
            reverse("dagster:trigger_job") + "?job=etl_job"
        )

        assert resp.status_code == 200
        assert b"selected" in resp.content

    @patch("django_dagster.views.client.submit_job")
    def test_post_triggers_job(self, mock_submit, staff_client):
        mock_submit.return_value = "new-run-123"

        resp = staff_client.post(
            reverse("dagster:trigger_job"),
            {"job_name": "etl_job", "run_config": ""},
        )

        assert resp.status_code == 302
        assert "new-run-123" in resp.url
        mock_submit.assert_called_once_with("etl_job", run_config=None)

    @patch("django_dagster.views.client.submit_job")
    def test_post_with_config(self, mock_submit, staff_client):
        mock_submit.return_value = "new-run-456"

        resp = staff_client.post(
            reverse("dagster:trigger_job"),
            {
                "job_name": "etl_job",
                "run_config": '{"ops": {"x": {"config": {"k": 1}}}}',
            },
        )

        assert resp.status_code == 302
        mock_submit.assert_called_once_with(
            "etl_job",
            run_config={"ops": {"x": {"config": {"k": 1}}}},
        )

    @patch("django_dagster.views.client.get_jobs")
    def test_post_invalid_json(self, mock_get_jobs, staff_client):
        mock_get_jobs.return_value = []

        resp = staff_client.post(
            reverse("dagster:trigger_job"),
            {"job_name": "etl_job", "run_config": "{bad json"},
        )

        assert resp.status_code == 200
        assert b"Invalid JSON config" in resp.content

    @patch("django_dagster.views.client.get_jobs")
    def test_post_missing_job_name(self, mock_get_jobs, staff_client):
        mock_get_jobs.return_value = []

        resp = staff_client.post(
            reverse("dagster:trigger_job"),
            {"job_name": "", "run_config": ""},
        )

        assert resp.status_code == 200
        assert b"Job name is required" in resp.content

    @patch("django_dagster.views.client.get_jobs")
    @patch("django_dagster.views.client.submit_job")
    def test_post_dagster_error(self, mock_submit, mock_get_jobs, staff_client):
        mock_submit.side_effect = Exception("JobNotFoundError")
        mock_get_jobs.return_value = []

        resp = staff_client.post(
            reverse("dagster:trigger_job"),
            {"job_name": "missing_job", "run_config": ""},
        )

        # Falls through to GET rendering after error
        assert resp.status_code == 200
        assert b"Failed to trigger job" in resp.content


# ---------------------------------------------------------------------------
# Cancel run view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCancelRunView:
    @patch("django_dagster.views.client.cancel_run")
    def test_cancel_success(self, mock_cancel, staff_client):
        run_id = "abc12345-def0-1234-5678-abcdef012345"
        resp = staff_client.post(reverse("dagster:cancel_run", args=[run_id]))

        assert resp.status_code == 302
        assert run_id in resp.url
        mock_cancel.assert_called_once_with(run_id)

    @patch("django_dagster.views.client.cancel_run")
    def test_cancel_error(self, mock_cancel, staff_client):
        mock_cancel.side_effect = Exception("Already finished")

        run_id = "abc123"
        resp = staff_client.post(reverse("dagster:cancel_run", args=[run_id]))

        assert resp.status_code == 302
        assert run_id in resp.url

    def test_cancel_get_redirects(self, staff_client):
        """GET should not cancel, just redirect."""
        run_id = "abc123"
        resp = staff_client.get(reverse("dagster:cancel_run", args=[run_id]))

        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Retry run view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRetryRunView:
    @patch("django_dagster.views.client.retry_run")
    def test_retry_success(self, mock_retry, staff_client):
        mock_retry.return_value = "new-retry-id"

        run_id = "failed-run-123"
        resp = staff_client.post(reverse("dagster:retry_run", args=[run_id]))

        assert resp.status_code == 302
        assert "new-retry-id" in resp.url
        mock_retry.assert_called_once_with(run_id)

    @patch("django_dagster.views.client.retry_run")
    def test_retry_error(self, mock_retry, staff_client):
        mock_retry.side_effect = Exception("Run not found")

        run_id = "bad-id"
        resp = staff_client.post(reverse("dagster:retry_run", args=[run_id]))

        assert resp.status_code == 302
        assert run_id in resp.url

    def test_retry_get_redirects(self, staff_client):
        """GET should not retry, just redirect."""
        run_id = "abc123"
        resp = staff_client.get(reverse("dagster:retry_run", args=[run_id]))

        assert resp.status_code == 302
