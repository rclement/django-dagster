from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.admin.sites import AdminSite
from django.test import Client
from django.urls import reverse

from django_dagster.admin import DagsterJobAdmin, DagsterRunAdmin, _DagsterAdminBase
from django_dagster.models import DagsterJob, DagsterRun


@pytest.fixture
def perms_enabled(settings: Any) -> None:
    """Enable DAGSTER_PERMISSIONS_ENABLED for the test."""
    settings.DAGSTER_PERMISSIONS_ENABLED = True


# ---------------------------------------------------------------------------
# Admin registration
# ---------------------------------------------------------------------------


def test_models_registered() -> None:
    from django.contrib import admin

    assert DagsterJob in admin.site._registry
    assert DagsterRun in admin.site._registry


def test_job_admin_class() -> None:
    admin_instance = DagsterJobAdmin(DagsterJob, AdminSite())
    assert admin_instance is not None


def test_run_admin_class() -> None:
    admin_instance = DagsterRunAdmin(DagsterRun, AdminSite())
    assert admin_instance is not None


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

JOB_URLS = {
    "changelist": "admin:django_dagster_dagsterjob_changelist",
    "trigger": "admin:django_dagster_dagsterjob_trigger",
    "change": "admin:django_dagster_dagsterjob_change",
}

RUN_URLS = {
    "changelist": "admin:django_dagster_dagsterrun_changelist",
    "change": "admin:django_dagster_dagsterrun_change",
    "cancel": "admin:django_dagster_dagsterrun_cancel",
    "reexecute": "admin:django_dagster_dagsterrun_reexecute",
}


@pytest.mark.django_db
def test_urls_resolve() -> None:
    assert reverse(JOB_URLS["changelist"])
    assert reverse(JOB_URLS["trigger"], args=["etl_job"])
    assert reverse(JOB_URLS["change"], args=["etl_job"])
    assert reverse(RUN_URLS["changelist"])
    assert reverse(RUN_URLS["change"], args=["abc123"])
    assert reverse(RUN_URLS["cancel"], args=["abc123"])
    assert reverse(RUN_URLS["reexecute"], args=["abc123"])


# ---------------------------------------------------------------------------
# Static URL helper edge cases
# ---------------------------------------------------------------------------


def test_dagster_job_ui_url_none() -> None:
    result = _DagsterAdminBase._dagster_job_ui_url(
        None, {"name": "etl_job", "repository": "repo", "location": "loc"}
    )
    assert result is None


def test_dagster_run_ui_url_none() -> None:
    result = _DagsterAdminBase._dagster_run_ui_url(None, "abc")
    assert result is None


# ---------------------------------------------------------------------------
# Auth: all views require staff
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAuthRequired:
    def test_anonymous_job_changelist(self, client: Client) -> None:
        assert client.get(reverse(JOB_URLS["changelist"])).status_code == 302

    def test_anonymous_job_trigger(self, client: Client) -> None:
        assert (
            client.get(reverse(JOB_URLS["trigger"], args=["etl_job"])).status_code
            == 302
        )

    def test_anonymous_run_changelist(self, client: Client) -> None:
        assert client.get(reverse(RUN_URLS["changelist"])).status_code == 302

    def test_anonymous_run_change(self, client: Client) -> None:
        url = reverse(RUN_URLS["change"], args=["abc123"])
        assert client.get(url).status_code == 302

    def test_anonymous_cancel(self, client: Client) -> None:
        url = reverse(RUN_URLS["cancel"], args=["abc123"])
        assert client.post(url).status_code == 302

    def test_anonymous_reexecute(self, client: Client) -> None:
        url = reverse(RUN_URLS["reexecute"], args=["abc123"])
        assert client.post(url).status_code == 302

    def test_non_staff_redirected(self, client: Client, db: Any) -> None:
        from django.contrib.auth.models import User

        User.objects.create_user("regular", password="password")
        client.login(username="regular", password="password")
        assert client.get(reverse(JOB_URLS["changelist"])).status_code == 302
        assert client.get(reverse(RUN_URLS["changelist"])).status_code == 302


# ---------------------------------------------------------------------------
# Job list (changelist)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestJobListView:
    @patch("django_dagster.admin.client.get_jobs")
    def test_renders_jobs(self, mock_get_jobs: MagicMock, staff_client: Client) -> None:
        mock_get_jobs.return_value = [
            {
                "name": "etl_job",
                "description": "Daily ETL",
                "repository": "repo",
                "location": "loc",
            },
        ]

        resp = staff_client.get(reverse(JOB_URLS["changelist"]))

        assert resp.status_code == 200
        assert b"Dagster Jobs" in resp.content
        assert b"etl_job" in resp.content
        assert b"Daily ETL" in resp.content

    @patch("django_dagster.admin.client.get_jobs")
    def test_empty_jobs(self, mock_get_jobs: MagicMock, staff_client: Client) -> None:
        mock_get_jobs.return_value = []

        resp = staff_client.get(reverse(JOB_URLS["changelist"]))

        assert resp.status_code == 200
        assert b"No jobs found" in resp.content

    @patch("django_dagster.admin.client.get_jobs")
    def test_connection_error(
        self, mock_get_jobs: MagicMock, staff_client: Client
    ) -> None:
        mock_get_jobs.side_effect = ConnectionError("Connection refused")

        resp = staff_client.get(reverse(JOB_URLS["changelist"]))

        assert resp.status_code == 200
        assert b"Failed to connect to Dagster" in resp.content

    @patch("django_dagster.admin.client.get_jobs")
    def test_job_name_links_to_detail(
        self, mock_get_jobs: MagicMock, staff_client: Client
    ) -> None:
        mock_get_jobs.return_value = [
            {"name": "etl_job", "description": "", "repository": "r", "location": "l"},
        ]

        resp = staff_client.get(reverse(JOB_URLS["changelist"]))

        detail_url = reverse(JOB_URLS["change"], args=["etl_job"])
        assert detail_url.encode() in resp.content

    @patch("django_dagster.admin.client.get_jobs")
    def test_sort_by_name(self, mock_get_jobs: MagicMock, staff_client: Client) -> None:
        mock_get_jobs.return_value = [
            {"name": "b_job", "description": "", "repository": "r", "location": "l"},
            {"name": "a_job", "description": "", "repository": "r", "location": "l"},
        ]

        resp = staff_client.get(reverse(JOB_URLS["changelist"]) + "?o=name")

        assert resp.status_code == 200
        content = resp.content.decode()
        assert content.index("a_job") < content.index("b_job")

    @patch("django_dagster.admin.client.get_jobs")
    def test_config_recap_shown(
        self, mock_get_jobs: MagicMock, staff_client: Client
    ) -> None:
        mock_get_jobs.return_value = []

        resp = staff_client.get(reverse(JOB_URLS["changelist"]))

        assert resp.status_code == 200
        assert b"http://localhost:3000" in resp.content

    @patch("django_dagster.admin.client.get_jobs")
    def test_dagster_ui_links_shown(
        self, mock_get_jobs: MagicMock, staff_client: Client
    ) -> None:
        mock_get_jobs.return_value = [
            {
                "name": "etl_job",
                "description": "",
                "repository": "repo",
                "location": "loc",
            },
        ]

        resp = staff_client.get(reverse(JOB_URLS["changelist"]))

        assert resp.status_code == 200
        content = resp.content.decode()
        # Navigation links in the info bar
        assert "http://localhost:3000/jobs" in content
        assert "http://localhost:3000/runs" in content
        assert "http://localhost:3000/locations" in content
        # Per-job Dagster UI link
        assert "http://localhost:3000/locations/repo@loc/jobs/etl_job" in content


# ---------------------------------------------------------------------------
# Job detail (change view)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@patch("django_dagster.admin.client.get_runs")
class TestJobDetailView:
    @patch("django_dagster.admin.client.get_jobs")
    def test_renders_detail(
        self,
        mock_get_jobs: MagicMock,
        mock_get_runs: MagicMock,
        staff_client: Client,
    ) -> None:
        mock_get_jobs.return_value = [
            {
                "name": "etl_job",
                "description": "Daily ETL",
                "repository": "repo",
                "location": "loc",
            },
        ]
        mock_get_runs.return_value = []

        resp = staff_client.get(reverse(JOB_URLS["change"], args=["etl_job"]))

        assert resp.status_code == 200
        assert b"View Dagster Job" in resp.content
        assert b"etl_job" in resp.content
        assert b"Daily ETL" in resp.content
        assert b"repo" in resp.content
        assert b"loc" in resp.content

    @patch("django_dagster.admin.client.get_jobs")
    def test_has_trigger_button(
        self,
        mock_get_jobs: MagicMock,
        mock_get_runs: MagicMock,
        staff_client: Client,
    ) -> None:
        mock_get_jobs.return_value = [
            {"name": "etl_job", "description": "", "repository": "r", "location": "l"},
        ]
        mock_get_runs.return_value = []

        resp = staff_client.get(reverse(JOB_URLS["change"], args=["etl_job"]))

        assert b"Trigger New Run" in resp.content

    @patch("django_dagster.admin.client.get_jobs")
    def test_has_view_runs_button(
        self,
        mock_get_jobs: MagicMock,
        mock_get_runs: MagicMock,
        staff_client: Client,
    ) -> None:
        mock_get_jobs.return_value = [
            {"name": "etl_job", "description": "", "repository": "r", "location": "l"},
        ]
        mock_get_runs.return_value = []

        resp = staff_client.get(reverse(JOB_URLS["change"], args=["etl_job"]))

        assert b"View Runs" in resp.content

    @patch("django_dagster.admin.client.get_jobs")
    def test_not_found_redirects(
        self,
        mock_get_jobs: MagicMock,
        mock_get_runs: MagicMock,
        staff_client: Client,
    ) -> None:
        mock_get_jobs.return_value = [
            {
                "name": "other_job",
                "description": "",
                "repository": "r",
                "location": "l",
            },
        ]

        resp = staff_client.get(reverse(JOB_URLS["change"], args=["nonexistent_job"]))

        assert resp.status_code == 302
        assert reverse(JOB_URLS["changelist"]) in resp.url  # type: ignore[attr-defined]

    @patch("django_dagster.admin.client.get_jobs")
    def test_connection_error_redirects(
        self,
        mock_get_jobs: MagicMock,
        mock_get_runs: MagicMock,
        staff_client: Client,
    ) -> None:
        mock_get_jobs.side_effect = ConnectionError("refused")

        resp = staff_client.get(reverse(JOB_URLS["change"], args=["etl_job"]))

        assert resp.status_code == 302

    @patch("django_dagster.admin.client.get_jobs")
    def test_uses_fieldset_layout(
        self,
        mock_get_jobs: MagicMock,
        mock_get_runs: MagicMock,
        staff_client: Client,
    ) -> None:
        mock_get_jobs.return_value = [
            {
                "name": "etl_job",
                "description": "Daily ETL",
                "repository": "r",
                "location": "l",
            },
        ]
        mock_get_runs.return_value = []

        resp = staff_client.get(reverse(JOB_URLS["change"], args=["etl_job"]))

        assert b"fieldset" in resp.content
        assert b"submit-row" in resp.content

    @patch("django_dagster.admin.client.get_jobs")
    def test_dagster_ui_link_shown(
        self,
        mock_get_jobs: MagicMock,
        mock_get_runs: MagicMock,
        staff_client: Client,
    ) -> None:
        mock_get_jobs.return_value = [
            {
                "name": "etl_job",
                "description": "",
                "repository": "repo",
                "location": "loc",
            },
        ]
        mock_get_runs.return_value = []

        resp = staff_client.get(reverse(JOB_URLS["change"], args=["etl_job"]))

        assert resp.status_code == 200
        assert b"http://localhost:3000/locations/repo@loc/jobs/etl_job" in resp.content
        assert b"View in Dagster UI" in resp.content

    @patch("django_dagster.admin.client.get_jobs")
    def test_recent_runs_shown(
        self,
        mock_get_jobs: MagicMock,
        mock_get_runs: MagicMock,
        staff_client: Client,
    ) -> None:
        mock_get_jobs.return_value = [
            {"name": "etl_job", "description": "", "repository": "r", "location": "l"},
        ]
        mock_get_runs.return_value = [
            {
                "runId": "abc12345-def0-1234-5678-abcdef012345",
                "jobName": "etl_job",
                "status": "SUCCESS",
                "startTime": datetime(2023, 11, 14, tzinfo=timezone.utc),
                "endTime": None,
                "tags": [],
            },
        ]

        resp = staff_client.get(reverse(JOB_URLS["change"], args=["etl_job"]))

        assert resp.status_code == 200
        assert b"Recent Runs" in resp.content
        assert b"abc12345-def0-1234-5678-abcdef012345" in resp.content
        mock_get_runs.assert_called_once_with(job_name="etl_job", limit=10)

    @patch("django_dagster.admin.client.get_jobs")
    def test_recent_runs_fetch_error(
        self,
        mock_get_jobs: MagicMock,
        mock_get_runs: MagicMock,
        staff_client: Client,
    ) -> None:
        """When get_runs raises, the page still renders (covers except/pass branch)."""
        mock_get_jobs.return_value = [
            {"name": "etl_job", "description": "", "repository": "r", "location": "l"},
        ]
        mock_get_runs.side_effect = Exception("Connection refused")

        resp = staff_client.get(reverse(JOB_URLS["change"], args=["etl_job"]))

        assert resp.status_code == 200
        assert b"etl_job" in resp.content


# ---------------------------------------------------------------------------
# Trigger job (add view)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTriggerJobView:
    def _trigger_url(self, job_name: str = "etl_job") -> str:
        return reverse(JOB_URLS["trigger"], args=[job_name])

    @patch("django_dagster.admin.client.get_job_default_run_config")
    def test_get_renders_form(
        self, mock_default_config: MagicMock, staff_client: Client
    ) -> None:
        mock_default_config.return_value = {}

        resp = staff_client.get(self._trigger_url())

        assert resp.status_code == 200
        assert b"etl_job" in resp.content
        assert b"Trigger Dagster Job Run" in resp.content

    @patch("django_dagster.admin.client.get_job_default_run_config")
    def test_get_prefills_default_run_config(
        self, mock_default_config: MagicMock, staff_client: Client
    ) -> None:
        mock_default_config.return_value = {"ops": {"my_op": {"config": {"x": 1}}}}

        resp = staff_client.get(self._trigger_url())

        assert resp.status_code == 200
        assert (
            resp.context["run_config"]
            == '{\n  "ops": {\n    "my_op": {\n      "config": {\n        "x": 1\n      }\n    }\n  }\n}'
        )
        mock_default_config.assert_called_once_with("etl_job")

    @patch("django_dagster.admin.client.get_job_default_run_config")
    def test_get_empty_default_shows_empty_json(
        self, mock_default_config: MagicMock, staff_client: Client
    ) -> None:
        mock_default_config.return_value = {}

        resp = staff_client.get(self._trigger_url())

        assert resp.context["run_config"] == "{}"

    @patch("django_dagster.admin.client.get_job_default_run_config")
    def test_get_default_config_error_falls_back(
        self, mock_default_config: MagicMock, staff_client: Client
    ) -> None:
        mock_default_config.side_effect = Exception("API error")

        resp = staff_client.get(self._trigger_url())

        assert resp.status_code == 200
        assert resp.context["run_config"] == "{}"

    @patch("django_dagster.admin.client.submit_job")
    def test_post_triggers_job(
        self, mock_submit: MagicMock, staff_client: Client
    ) -> None:
        mock_submit.return_value = "new-run-123"

        resp = staff_client.post(
            self._trigger_url(),
            {"run_config": ""},
        )

        assert resp.status_code == 302
        assert "new-run-123" in resp.url  # type: ignore[attr-defined]
        mock_submit.assert_called_once_with("etl_job", run_config=None)

    @patch("django_dagster.admin.client.submit_job")
    def test_post_redirects_to_run_detail(
        self, mock_submit: MagicMock, staff_client: Client
    ) -> None:
        mock_submit.return_value = "new-run-123"

        resp = staff_client.post(
            self._trigger_url(),
            {"run_config": ""},
        )

        expected = reverse(RUN_URLS["change"], args=["new-run-123"])
        assert resp.url == expected  # type: ignore[attr-defined]

    @patch("django_dagster.admin.client.submit_job")
    def test_post_with_config(
        self, mock_submit: MagicMock, staff_client: Client
    ) -> None:
        mock_submit.return_value = "new-run-456"

        resp = staff_client.post(
            self._trigger_url(),
            {
                "run_config": '{"ops": {"x": {"config": {"k": 1}}}}',
            },
        )

        assert resp.status_code == 302
        mock_submit.assert_called_once_with(
            "etl_job",
            run_config={"ops": {"x": {"config": {"k": 1}}}},
        )

    def test_post_invalid_json(self, staff_client: Client) -> None:
        resp = staff_client.post(
            self._trigger_url(),
            {"run_config": "{bad json"},
        )

        assert resp.status_code == 200
        assert b"Invalid JSON config" in resp.content

    @patch("django_dagster.admin.client.submit_job")
    def test_post_dagster_error_preserves_form(
        self, mock_submit: MagicMock, staff_client: Client
    ) -> None:
        mock_submit.side_effect = Exception("JobNotFoundError")

        resp = staff_client.post(
            self._trigger_url(),
            {"run_config": '{"key": "val"}'},
        )

        assert resp.status_code == 200
        assert b"Failed to trigger job" in resp.content
        # Form values are preserved
        assert b"etl_job" in resp.content
        assert resp.context["run_config"] == '{"key": "val"}'


# ---------------------------------------------------------------------------
# Run list (changelist)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@patch("django_dagster.admin.client.get_jobs")
class TestRunListView:
    @patch("django_dagster.admin.client.get_runs")
    def test_renders_runs(
        self,
        mock_get_runs: MagicMock,
        mock_get_jobs: MagicMock,
        staff_client: Client,
    ) -> None:
        mock_get_jobs.return_value = []
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

        resp = staff_client.get(reverse(RUN_URLS["changelist"]))

        assert resp.status_code == 200
        # Full run ID displayed (not truncated)
        assert b"abc12345-def0-1234-5678-abcdef012345" in resp.content
        assert b"SUCCESS" in resp.content
        mock_get_runs.assert_called_once_with(job_name=None, statuses=None)

    @patch("django_dagster.admin.client.get_runs")
    def test_filters(
        self,
        mock_get_runs: MagicMock,
        mock_get_jobs: MagicMock,
        staff_client: Client,
    ) -> None:
        mock_get_jobs.return_value = []
        mock_get_runs.return_value = []

        resp = staff_client.get(
            reverse(RUN_URLS["changelist"]) + "?job=etl_job&status=FAILURE"
        )

        assert resp.status_code == 200
        mock_get_runs.assert_called_once_with(job_name="etl_job", statuses=["FAILURE"])

    @patch("django_dagster.admin.client.get_runs")
    def test_connection_error(
        self,
        mock_get_runs: MagicMock,
        mock_get_jobs: MagicMock,
        staff_client: Client,
    ) -> None:
        mock_get_jobs.return_value = []
        mock_get_runs.side_effect = ConnectionError("refused")

        resp = staff_client.get(reverse(RUN_URLS["changelist"]))

        assert resp.status_code == 200
        assert b"Failed to connect to Dagster" in resp.content

    @patch("django_dagster.admin.client.get_runs")
    def test_run_links_to_detail(
        self,
        mock_get_runs: MagicMock,
        mock_get_jobs: MagicMock,
        staff_client: Client,
    ) -> None:
        mock_get_jobs.return_value = []
        run_id = "abc12345-def0-1234-5678-abcdef012345"
        mock_get_runs.return_value = [
            {
                "runId": run_id,
                "jobName": "etl_job",
                "status": "SUCCESS",
                "startTime": datetime(2023, 11, 14, tzinfo=timezone.utc),
                "endTime": None,
                "tags": [],
            },
        ]

        resp = staff_client.get(reverse(RUN_URLS["changelist"]))

        change_url = reverse(RUN_URLS["change"], args=[run_id])
        assert change_url.encode() in resp.content

    @patch("django_dagster.admin.client.get_runs")
    def test_dagster_ui_links_shown(
        self,
        mock_get_runs: MagicMock,
        mock_get_jobs: MagicMock,
        staff_client: Client,
    ) -> None:
        mock_get_jobs.return_value = []
        run_id = "abc12345-def0-1234-5678-abcdef012345"
        mock_get_runs.return_value = [
            {
                "runId": run_id,
                "jobName": "etl_job",
                "status": "SUCCESS",
                "startTime": datetime(2023, 11, 14, tzinfo=timezone.utc),
                "endTime": None,
                "tags": [],
            },
        ]

        resp = staff_client.get(reverse(RUN_URLS["changelist"]))

        assert resp.status_code == 200
        assert f"http://localhost:3000/runs/{run_id}".encode() in resp.content

    @patch("django_dagster.admin.client.get_runs")
    def test_sort_by_status(
        self,
        mock_get_runs: MagicMock,
        mock_get_jobs: MagicMock,
        staff_client: Client,
    ) -> None:
        mock_get_jobs.return_value = []
        mock_get_runs.return_value = [
            {
                "runId": "run-b",
                "jobName": "job",
                "status": "SUCCESS",
                "startTime": None,
                "endTime": None,
                "tags": [],
            },
            {
                "runId": "run-a",
                "jobName": "job",
                "status": "FAILURE",
                "startTime": None,
                "endTime": None,
                "tags": [],
            },
        ]

        resp = staff_client.get(reverse(RUN_URLS["changelist"]) + "?o=status")

        assert resp.status_code == 200

    @patch("django_dagster.admin.client.get_runs")
    def test_sort_by_invalid_key(
        self,
        mock_get_runs: MagicMock,
        mock_get_jobs: MagicMock,
        staff_client: Client,
    ) -> None:
        """When the sort key is not in SORT_KEYS, runs are returned unsorted."""
        mock_get_jobs.return_value = []
        mock_get_runs.return_value = [
            {
                "runId": "run-a",
                "jobName": "job",
                "status": "SUCCESS",
                "startTime": None,
                "endTime": None,
                "tags": [],
            },
        ]

        resp = staff_client.get(reverse(RUN_URLS["changelist"]) + "?o=bogus_field")

        assert resp.status_code == 200

    @patch("django_dagster.admin.client.get_runs")
    def test_job_filter_sidebar(
        self,
        mock_get_runs: MagicMock,
        mock_get_jobs: MagicMock,
        staff_client: Client,
    ) -> None:
        mock_get_jobs.return_value = [
            {"name": "etl_job", "description": "", "repository": "r", "location": "l"},
            {
                "name": "report_job",
                "description": "",
                "repository": "r",
                "location": "l",
            },
        ]
        mock_get_runs.return_value = []

        resp = staff_client.get(reverse(RUN_URLS["changelist"]))

        assert resp.status_code == 200
        # Job filter sidebar should list job names
        assert b"By job" in resp.content
        assert b"etl_job" in resp.content
        assert b"report_job" in resp.content

    @patch("django_dagster.admin.client.get_runs")
    def test_job_sidebar_fetch_error(
        self,
        mock_get_runs: MagicMock,
        mock_get_jobs: MagicMock,
        staff_client: Client,
    ) -> None:
        """When get_jobs raises, the page still renders (covers except/pass branch)."""
        mock_get_jobs.side_effect = Exception("Connection refused")
        mock_get_runs.return_value = []

        resp = staff_client.get(reverse(RUN_URLS["changelist"]))

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Run detail (change view)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@patch("django_dagster.admin.client.get_runs")
class TestRunDetailView:
    def _make_run(self, status: str = "SUCCESS") -> dict[str, Any]:
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

    @patch("django_dagster.admin.client.get_run")
    def test_renders_detail(
        self,
        mock_get_run: MagicMock,
        mock_get_runs: MagicMock,
        staff_client: Client,
    ) -> None:
        mock_get_run.return_value = self._make_run()
        mock_get_runs.return_value = []

        run_id = "abc12345-def0-1234-5678-abcdef012345"
        resp = staff_client.get(reverse(RUN_URLS["change"], args=[run_id]))

        assert resp.status_code == 200
        assert b"etl_job" in resp.content
        assert b"SUCCESS" in resp.content
        assert b"env=prod" in resp.content
        # Full run ID displayed (not truncated)
        assert b"abc12345-def0-1234-5678-abcdef012345" in resp.content
        # Uses native Django admin layout
        assert b"fieldset" in resp.content
        assert b"submit-row" in resp.content
        # "All Runs" is a proper button
        assert b"All Runs" in resp.content

    @patch("django_dagster.admin.client.get_run")
    def test_dagster_ui_link_shown(
        self,
        mock_get_run: MagicMock,
        mock_get_runs: MagicMock,
        staff_client: Client,
    ) -> None:
        mock_get_run.return_value = self._make_run()
        mock_get_runs.return_value = []

        run_id = "abc12345-def0-1234-5678-abcdef012345"
        resp = staff_client.get(reverse(RUN_URLS["change"], args=[run_id]))

        assert resp.status_code == 200
        assert f"http://localhost:3000/runs/{run_id}".encode() in resp.content
        assert b"View in Dagster UI" in resp.content

    @patch("django_dagster.admin.client.get_run")
    def test_cancel_button_shown_for_running(
        self,
        mock_get_run: MagicMock,
        mock_get_runs: MagicMock,
        staff_client: Client,
    ) -> None:
        mock_get_run.return_value = self._make_run(status="STARTED")
        mock_get_runs.return_value = []

        run_id = "abc12345-def0-1234-5678-abcdef012345"
        resp = staff_client.get(reverse(RUN_URLS["change"], args=[run_id]))

        assert resp.status_code == 200
        assert b"Cancel Run" in resp.content

    @patch("django_dagster.admin.client.get_run")
    def test_reexecute_button_shown_for_failed(
        self,
        mock_get_run: MagicMock,
        mock_get_runs: MagicMock,
        staff_client: Client,
    ) -> None:
        mock_get_run.return_value = self._make_run(status="FAILURE")
        mock_get_runs.return_value = []

        run_id = "abc12345-def0-1234-5678-abcdef012345"
        resp = staff_client.get(reverse(RUN_URLS["change"], args=[run_id]))

        assert resp.status_code == 200
        assert b"Re-execute" in resp.content
        assert b"Cancel Run" not in resp.content

    @patch("django_dagster.admin.client.get_run")
    def test_reexecute_button_shown_for_success(
        self,
        mock_get_run: MagicMock,
        mock_get_runs: MagicMock,
        staff_client: Client,
    ) -> None:
        mock_get_run.return_value = self._make_run(status="SUCCESS")
        mock_get_runs.return_value = []

        run_id = "abc12345-def0-1234-5678-abcdef012345"
        resp = staff_client.get(reverse(RUN_URLS["change"], args=[run_id]))

        assert resp.status_code == 200
        assert b"Cancel Run" not in resp.content
        assert b"Re-execute" in resp.content

    @patch("django_dagster.admin.client.get_run_events")
    @patch("django_dagster.admin.client.get_run")
    def test_event_logs_shown(
        self,
        mock_get_run: MagicMock,
        mock_get_events: MagicMock,
        mock_get_runs: MagicMock,
        staff_client: Client,
    ) -> None:
        mock_get_run.return_value = self._make_run()
        mock_get_runs.return_value = []
        mock_get_events.return_value = {
            "events": [
                {
                    "event_type": "RunStartEvent",
                    "message": "Started execution of run.",
                    "timestamp": datetime(2023, 11, 14, tzinfo=timezone.utc),
                    "level": "DEBUG",
                    "stepKey": None,
                },
                {
                    "event_type": "LogMessageEvent",
                    "message": "Processing data...",
                    "timestamp": datetime(2023, 11, 14, 0, 1, tzinfo=timezone.utc),
                    "level": "INFO",
                    "stepKey": "my_op",
                },
            ],
            "cursor": "2",
            "has_more": False,
        }

        run_id = "abc12345-def0-1234-5678-abcdef012345"
        resp = staff_client.get(reverse(RUN_URLS["change"], args=[run_id]))

        assert resp.status_code == 200
        assert b"Event Log" in resp.content
        assert b"Started execution of run." in resp.content
        assert b"Processing data..." in resp.content
        assert b"RunStartEvent" in resp.content
        assert b"my_op" in resp.content

    @patch("django_dagster.admin.client.get_run_events")
    @patch("django_dagster.admin.client.get_run")
    def test_event_logs_error_graceful(
        self,
        mock_get_run: MagicMock,
        mock_get_events: MagicMock,
        mock_get_runs: MagicMock,
        staff_client: Client,
    ) -> None:
        mock_get_run.return_value = self._make_run()
        mock_get_runs.return_value = []
        mock_get_events.side_effect = Exception("Connection refused")

        run_id = "abc12345-def0-1234-5678-abcdef012345"
        resp = staff_client.get(reverse(RUN_URLS["change"], args=[run_id]))

        assert resp.status_code == 200
        # Should still render without event logs
        assert b"Event Log" not in resp.content

    @patch("django_dagster.admin.client.get_run_events")
    @patch("django_dagster.admin.client.get_run")
    def test_event_logs_none_response(
        self,
        mock_get_run: MagicMock,
        mock_get_events: MagicMock,
        mock_get_runs: MagicMock,
        staff_client: Client,
    ) -> None:
        """When get_run_events returns None, page renders without event logs."""
        mock_get_run.return_value = self._make_run()
        mock_get_runs.return_value = []
        mock_get_events.return_value = None

        run_id = "abc12345-def0-1234-5678-abcdef012345"
        resp = staff_client.get(reverse(RUN_URLS["change"], args=[run_id]))

        assert resp.status_code == 200
        assert b"Event Log" not in resp.content

    @patch("django_dagster.admin.client.get_run")
    def test_not_found_redirects(
        self,
        mock_get_run: MagicMock,
        mock_get_runs: MagicMock,
        staff_client: Client,
    ) -> None:
        mock_get_run.return_value = None

        resp = staff_client.get(reverse(RUN_URLS["change"], args=["nonexistent"]))

        assert resp.status_code == 302
        assert reverse(RUN_URLS["changelist"]) in resp.url  # type: ignore[attr-defined]

    @patch("django_dagster.admin.client.get_run")
    def test_error_redirects(
        self,
        mock_get_run: MagicMock,
        mock_get_runs: MagicMock,
        staff_client: Client,
    ) -> None:
        mock_get_run.side_effect = Exception("boom")

        resp = staff_client.get(reverse(RUN_URLS["change"], args=["some-id"]))

        assert resp.status_code == 302

    @patch("django_dagster.admin.client.get_run")
    def test_related_runs_shown(
        self,
        mock_get_run: MagicMock,
        mock_get_runs: MagicMock,
        staff_client: Client,
    ) -> None:
        mock_get_run.return_value = self._make_run()
        mock_get_runs.return_value = [
            {
                "runId": "abc12345-def0-1234-5678-abcdef012345",
                "jobName": "etl_job",
                "status": "SUCCESS",
                "startTime": datetime(2023, 11, 14, tzinfo=timezone.utc),
                "endTime": None,
                "tags": [],
            },
            {
                "runId": "zzz99999-0000-1111-2222-333344445555",
                "jobName": "etl_job",
                "status": "FAILURE",
                "startTime": datetime(2023, 11, 13, tzinfo=timezone.utc),
                "endTime": None,
                "tags": [],
            },
        ]

        run_id = "abc12345-def0-1234-5678-abcdef012345"
        resp = staff_client.get(reverse(RUN_URLS["change"], args=[run_id]))

        assert resp.status_code == 200
        assert b"Recent Runs for" in resp.content
        assert b"zzz99999-0000-1111-2222-333344445555" in resp.content
        mock_get_runs.assert_called_once_with(job_name="etl_job", limit=10)

    @patch("django_dagster.admin.client.get_run")
    def test_related_runs_fetch_error(
        self,
        mock_get_run: MagicMock,
        mock_get_runs: MagicMock,
        staff_client: Client,
    ) -> None:
        """When get_runs raises for related runs, the page still renders."""
        mock_get_run.return_value = self._make_run()
        mock_get_runs.side_effect = Exception("Connection refused")

        run_id = "abc12345-def0-1234-5678-abcdef012345"
        resp = staff_client.get(reverse(RUN_URLS["change"], args=[run_id]))

        assert resp.status_code == 200
        assert b"etl_job" in resp.content

    @patch("django_dagster.admin.client.get_jobs")
    @patch("django_dagster.admin.client.get_run")
    def test_dagster_ui_job_link_shown(
        self,
        mock_get_run: MagicMock,
        mock_get_jobs: MagicMock,
        mock_get_runs: MagicMock,
        staff_client: Client,
    ) -> None:
        """When get_jobs succeeds, the job Dagster UI link is shown."""
        mock_get_run.return_value = self._make_run()
        mock_get_runs.return_value = []
        mock_get_jobs.return_value = [
            {
                "name": "etl_job",
                "description": "ETL",
                "repository": "my_repo",
                "location": "my_location",
            },
        ]

        run_id = "abc12345-def0-1234-5678-abcdef012345"
        resp = staff_client.get(reverse(RUN_URLS["change"], args=[run_id]))

        assert resp.status_code == 200
        assert b"my_location/jobs/etl_job" in resp.content

    @patch("django_dagster.admin.client.get_jobs")
    @patch("django_dagster.admin.client.get_run")
    def test_dagster_ui_job_lookup_error(
        self,
        mock_get_run: MagicMock,
        mock_get_jobs: MagicMock,
        mock_get_runs: MagicMock,
        staff_client: Client,
    ) -> None:
        """When get_jobs raises during job UI URL lookup, page still renders."""
        mock_get_run.return_value = self._make_run()
        mock_get_runs.return_value = []
        mock_get_jobs.side_effect = Exception("Connection refused")

        run_id = "abc12345-def0-1234-5678-abcdef012345"
        resp = staff_client.get(reverse(RUN_URLS["change"], args=[run_id]))

        assert resp.status_code == 200
        assert b"etl_job" in resp.content

    @patch("django_dagster.admin.client.get_run")
    def test_no_dagster_url_setting(
        self,
        mock_get_run: MagicMock,
        mock_get_runs: MagicMock,
        staff_client: Client,
        settings: Any,
    ) -> None:
        """When DAGSTER_URL is not set, no Dagster UI links are shown."""
        mock_get_run.return_value = self._make_run()
        mock_get_runs.return_value = []
        settings.DAGSTER_URL = ""

        run_id = "abc12345-def0-1234-5678-abcdef012345"
        resp = staff_client.get(reverse(RUN_URLS["change"], args=[run_id]))

        assert resp.status_code == 200
        assert b"View in Dagster UI" not in resp.content


# ---------------------------------------------------------------------------
# Cancel run
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCancelRunView:
    @patch("django_dagster.admin.client.cancel_run")
    def test_cancel_success(self, mock_cancel: MagicMock, staff_client: Client) -> None:
        run_id = "abc12345-def0-1234-5678-abcdef012345"
        resp = staff_client.post(reverse(RUN_URLS["cancel"], args=[run_id]))

        assert resp.status_code == 302
        assert run_id in resp.url  # type: ignore[attr-defined]
        mock_cancel.assert_called_once_with(run_id)

    @patch("django_dagster.admin.client.cancel_run")
    def test_cancel_redirects_to_run_detail(
        self, mock_cancel: MagicMock, staff_client: Client
    ) -> None:
        run_id = "abc123"
        resp = staff_client.post(reverse(RUN_URLS["cancel"], args=[run_id]))

        expected = reverse(RUN_URLS["change"], args=[run_id])
        assert resp.url == expected  # type: ignore[attr-defined]

    @patch("django_dagster.admin.client.cancel_run")
    def test_cancel_error(self, mock_cancel: MagicMock, staff_client: Client) -> None:
        mock_cancel.side_effect = Exception("Already finished")

        run_id = "abc123"
        resp = staff_client.post(reverse(RUN_URLS["cancel"], args=[run_id]))

        assert resp.status_code == 302
        assert run_id in resp.url  # type: ignore[attr-defined]

    def test_cancel_get_redirects(self, staff_client: Client) -> None:
        """GET should not cancel, just redirect."""
        run_id = "abc123"
        resp = staff_client.get(reverse(RUN_URLS["cancel"], args=[run_id]))

        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Re-execute run
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestReexecuteRunView:
    @patch("django_dagster.admin.client.reexecute_run")
    def test_reexecute_success(
        self, mock_reexecute: MagicMock, staff_client: Client
    ) -> None:
        mock_reexecute.return_value = "new-run-id"

        run_id = "failed-run-123"
        resp = staff_client.post(reverse(RUN_URLS["reexecute"], args=[run_id]))

        assert resp.status_code == 302
        assert "new-run-id" in resp.url  # type: ignore[attr-defined]
        mock_reexecute.assert_called_once_with(run_id)

    @patch("django_dagster.admin.client.reexecute_run")
    def test_reexecute_redirects_to_new_run(
        self, mock_reexecute: MagicMock, staff_client: Client
    ) -> None:
        mock_reexecute.return_value = "new-run-id"

        resp = staff_client.post(reverse(RUN_URLS["reexecute"], args=["old-run-id"]))

        expected = reverse(RUN_URLS["change"], args=["new-run-id"])
        assert resp.url == expected  # type: ignore[attr-defined]

    @patch("django_dagster.admin.client.reexecute_run")
    def test_reexecute_error(
        self, mock_reexecute: MagicMock, staff_client: Client
    ) -> None:
        mock_reexecute.side_effect = Exception("Run not found")

        run_id = "bad-id"
        resp = staff_client.post(reverse(RUN_URLS["reexecute"], args=[run_id]))

        assert resp.status_code == 302
        assert run_id in resp.url  # type: ignore[attr-defined]

    def test_reexecute_get_redirects(self, staff_client: Client) -> None:
        """GET should not re-execute, just redirect."""
        run_id = "abc123"
        resp = staff_client.get(reverse(RUN_URLS["reexecute"], args=[run_id]))

        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Admin index integration
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAdminIndex:
    def test_dagster_section_with_both_models(self, staff_client: Client) -> None:
        resp = staff_client.get(reverse("admin:index"))

        assert resp.status_code == 200
        assert b"Dagster" in resp.content
        assert b"Jobs" in resp.content
        assert b"Runs" in resp.content

    def test_dagster_app_index(self, staff_client: Client) -> None:
        resp = staff_client.get(reverse("admin:app_list", args=["django_dagster"]))

        assert resp.status_code == 200
        assert b"Jobs" in resp.content
        assert b"Runs" in resp.content

    def test_jobs_no_add_link(self, staff_client: Client) -> None:
        """Jobs should not have an Add link on the index (trigger is per-job)."""
        resp = staff_client.get(reverse("admin:index"))

        assert b"/trigger/" not in resp.content


# ---------------------------------------------------------------------------
# Permissions (DAGSTER_PERMISSIONS_ENABLED=True)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.usefixtures("perms_enabled")
class TestPermissionsEnabled:
    """When DAGSTER_PERMISSIONS_ENABLED=True, Django permissions are enforced."""

    # -- No permissions -> no access ------------------------------------------

    def test_staff_no_perms_job_list_forbidden(self, client: Client, db: Any) -> None:
        from django.contrib.auth.models import User

        User.objects.create_user("noperms", password="pw", is_staff=True)
        client.login(username="noperms", password="pw")
        resp = client.get(reverse(JOB_URLS["changelist"]))
        assert resp.status_code == 403

    def test_staff_no_perms_run_list_forbidden(self, client: Client, db: Any) -> None:
        from django.contrib.auth.models import User

        User.objects.create_user("noperms", password="pw", is_staff=True)
        client.login(username="noperms", password="pw")
        resp = client.get(reverse(RUN_URLS["changelist"]))
        assert resp.status_code == 403

    def test_staff_no_perms_job_detail_forbidden(self, client: Client, db: Any) -> None:
        from django.contrib.auth.models import User

        User.objects.create_user("noperms", password="pw", is_staff=True)
        client.login(username="noperms", password="pw")
        resp = client.get(reverse(JOB_URLS["change"], args=["etl_job"]))
        assert resp.status_code == 403

    def test_staff_no_perms_run_detail_forbidden(self, client: Client, db: Any) -> None:
        from django.contrib.auth.models import User

        User.objects.create_user("noperms", password="pw", is_staff=True)
        client.login(username="noperms", password="pw")
        resp = client.get(reverse(RUN_URLS["change"], args=["some-run-id"]))
        assert resp.status_code == 403

    # -- View-only: can see but cannot trigger/cancel/reexecute ---------------

    @patch("django_dagster.admin.client.get_jobs")
    def test_viewer_can_see_job_list(
        self, mock_get_jobs: MagicMock, viewer_client: Client
    ) -> None:
        mock_get_jobs.return_value = [
            {"name": "etl_job", "description": "", "repository": "r", "location": "l"},
        ]
        resp = viewer_client.get(reverse(JOB_URLS["changelist"]))
        assert resp.status_code == 200
        assert b"etl_job" in resp.content

    @patch("django_dagster.admin.client.get_runs")
    @patch("django_dagster.admin.client.get_jobs")
    def test_viewer_can_see_job_detail(
        self,
        mock_get_jobs: MagicMock,
        mock_get_runs: MagicMock,
        viewer_client: Client,
    ) -> None:
        mock_get_jobs.return_value = [
            {
                "name": "etl_job",
                "description": "ETL",
                "repository": "r",
                "location": "l",
            },
        ]
        mock_get_runs.return_value = []
        resp = viewer_client.get(reverse(JOB_URLS["change"], args=["etl_job"]))
        assert resp.status_code == 200
        assert b"Trigger New Run" not in resp.content

    @patch("django_dagster.admin.client.get_job_default_run_config")
    def test_viewer_cannot_trigger_job(
        self, mock_cfg: MagicMock, viewer_client: Client
    ) -> None:
        resp = viewer_client.get(reverse(JOB_URLS["trigger"], args=["etl_job"]))
        assert resp.status_code == 403

    def test_viewer_cannot_trigger_job_post(self, viewer_client: Client) -> None:
        resp = viewer_client.post(
            reverse(JOB_URLS["trigger"], args=["etl_job"]),
            {"run_config": ""},
        )
        assert resp.status_code == 403

    @patch("django_dagster.admin.client.get_jobs")
    @patch("django_dagster.admin.client.get_runs")
    def test_viewer_can_see_run_list(
        self,
        mock_get_runs: MagicMock,
        mock_get_jobs: MagicMock,
        viewer_client: Client,
    ) -> None:
        mock_get_jobs.return_value = []
        mock_get_runs.return_value = []
        resp = viewer_client.get(reverse(RUN_URLS["changelist"]))
        assert resp.status_code == 200

    @patch("django_dagster.admin.client.get_runs")
    @patch("django_dagster.admin.client.get_run")
    def test_viewer_sees_no_cancel_button(
        self,
        mock_get_run: MagicMock,
        mock_get_runs: MagicMock,
        viewer_client: Client,
    ) -> None:
        mock_get_run.return_value = {
            "runId": "abc123",
            "jobName": "etl_job",
            "status": "STARTED",
            "startTime": None,
            "endTime": None,
            "runConfigYaml": "",
            "tags": [],
            "stats": None,
        }
        mock_get_runs.return_value = []
        resp = viewer_client.get(reverse(RUN_URLS["change"], args=["abc123"]))
        assert resp.status_code == 200
        assert b"Cancel Run" not in resp.content

    @patch("django_dagster.admin.client.get_runs")
    @patch("django_dagster.admin.client.get_run")
    def test_viewer_sees_no_reexecute_button(
        self,
        mock_get_run: MagicMock,
        mock_get_runs: MagicMock,
        viewer_client: Client,
    ) -> None:
        mock_get_run.return_value = {
            "runId": "abc123",
            "jobName": "etl_job",
            "status": "FAILURE",
            "startTime": None,
            "endTime": None,
            "runConfigYaml": "",
            "tags": [],
            "stats": None,
        }
        mock_get_runs.return_value = []
        resp = viewer_client.get(reverse(RUN_URLS["change"], args=["abc123"]))
        assert resp.status_code == 200
        assert b"Re-execute" not in resp.content

    def test_viewer_cannot_cancel_run(self, viewer_client: Client) -> None:
        resp = viewer_client.post(reverse(RUN_URLS["cancel"], args=["abc123"]))
        assert resp.status_code == 403

    def test_viewer_cannot_reexecute_run(self, viewer_client: Client) -> None:
        resp = viewer_client.post(reverse(RUN_URLS["reexecute"], args=["abc123"]))
        assert resp.status_code == 403

    # -- Full permissions: can do everything ----------------------------------

    @patch("django_dagster.admin.client.get_job_default_run_config")
    def test_full_perm_can_trigger(
        self, mock_cfg: MagicMock, full_perm_client: Client
    ) -> None:
        mock_cfg.return_value = {}
        resp = full_perm_client.get(reverse(JOB_URLS["trigger"], args=["etl_job"]))
        assert resp.status_code == 200

    @patch("django_dagster.admin.client.cancel_run")
    def test_full_perm_can_cancel(
        self, mock_cancel: MagicMock, full_perm_client: Client
    ) -> None:
        resp = full_perm_client.post(reverse(RUN_URLS["cancel"], args=["abc123"]))
        assert resp.status_code == 302
        mock_cancel.assert_called_once_with("abc123")

    @patch("django_dagster.admin.client.reexecute_run")
    def test_full_perm_can_reexecute(
        self, mock_reexecute: MagicMock, full_perm_client: Client
    ) -> None:
        mock_reexecute.return_value = "new-run"
        resp = full_perm_client.post(reverse(RUN_URLS["reexecute"], args=["abc123"]))
        assert resp.status_code == 302
        mock_reexecute.assert_called_once_with("abc123")

    @patch("django_dagster.admin.client.get_runs")
    @patch("django_dagster.admin.client.get_jobs")
    def test_full_perm_sees_trigger_button(
        self,
        mock_get_jobs: MagicMock,
        mock_get_runs: MagicMock,
        full_perm_client: Client,
    ) -> None:
        mock_get_jobs.return_value = [
            {"name": "etl_job", "description": "", "repository": "r", "location": "l"},
        ]
        mock_get_runs.return_value = []
        resp = full_perm_client.get(reverse(JOB_URLS["change"], args=["etl_job"]))
        assert resp.status_code == 200
        assert b"Trigger New Run" in resp.content

    # -- Superuser: always has access -----------------------------------------

    @patch("django_dagster.admin.client.get_jobs")
    def test_superuser_can_see_jobs(
        self, mock_get_jobs: MagicMock, superuser_client: Client
    ) -> None:
        mock_get_jobs.return_value = []
        resp = superuser_client.get(reverse(JOB_URLS["changelist"]))
        assert resp.status_code == 200

    @patch("django_dagster.admin.client.get_job_default_run_config")
    def test_superuser_can_trigger(
        self, mock_cfg: MagicMock, superuser_client: Client
    ) -> None:
        mock_cfg.return_value = {}
        resp = superuser_client.get(reverse(JOB_URLS["trigger"], args=["etl_job"]))
        assert resp.status_code == 200

    @patch("django_dagster.admin.client.cancel_run")
    def test_superuser_can_cancel(
        self, mock_cancel: MagicMock, superuser_client: Client
    ) -> None:
        resp = superuser_client.post(reverse(RUN_URLS["cancel"], args=["abc123"]))
        assert resp.status_code == 302

    # -- Dagster UI links hidden without access_dagster_ui perm ---------------

    @patch("django_dagster.admin.client.get_jobs")
    def test_viewer_job_list_no_dagster_ui_links(
        self, mock_get_jobs: MagicMock, viewer_client: Client
    ) -> None:
        mock_get_jobs.return_value = [
            {"name": "etl_job", "description": "", "repository": "r", "location": "l"},
        ]
        resp = viewer_client.get(reverse(JOB_URLS["changelist"]))
        assert resp.status_code == 200
        assert b"Dagster UI" not in resp.content
        assert "\u2197".encode() not in resp.content

    @patch("django_dagster.admin.client.get_runs")
    @patch("django_dagster.admin.client.get_jobs")
    def test_viewer_job_detail_no_dagster_ui_links(
        self,
        mock_get_jobs: MagicMock,
        mock_get_runs: MagicMock,
        viewer_client: Client,
    ) -> None:
        mock_get_jobs.return_value = [
            {
                "name": "etl_job",
                "description": "ETL",
                "repository": "r",
                "location": "l",
            },
        ]
        mock_get_runs.return_value = []
        resp = viewer_client.get(reverse(JOB_URLS["change"], args=["etl_job"]))
        assert resp.status_code == 200
        assert b"View in Dagster UI" not in resp.content

    @patch("django_dagster.admin.client.get_jobs")
    @patch("django_dagster.admin.client.get_runs")
    def test_viewer_run_list_no_dagster_ui_links(
        self,
        mock_get_runs: MagicMock,
        mock_get_jobs: MagicMock,
        viewer_client: Client,
    ) -> None:
        mock_get_jobs.return_value = []
        mock_get_runs.return_value = [
            {
                "runId": "abc123",
                "jobName": "etl_job",
                "status": "SUCCESS",
                "startTime": None,
                "endTime": None,
                "tags": [],
            },
        ]
        resp = viewer_client.get(reverse(RUN_URLS["changelist"]))
        assert resp.status_code == 200
        assert b"Dagster UI" not in resp.content

    @patch("django_dagster.admin.client.get_runs")
    @patch("django_dagster.admin.client.get_run")
    def test_viewer_run_detail_no_dagster_ui_links(
        self,
        mock_get_run: MagicMock,
        mock_get_runs: MagicMock,
        viewer_client: Client,
    ) -> None:
        mock_get_run.return_value = {
            "runId": "abc123",
            "jobName": "etl_job",
            "status": "SUCCESS",
            "startTime": None,
            "endTime": None,
            "runConfigYaml": "",
            "tags": [],
            "stats": None,
        }
        mock_get_runs.return_value = []
        resp = viewer_client.get(reverse(RUN_URLS["change"], args=["abc123"]))
        assert resp.status_code == 200
        assert b"View in Dagster UI" not in resp.content

    @patch("django_dagster.admin.client.get_jobs")
    def test_full_perm_sees_dagster_ui_links(
        self, mock_get_jobs: MagicMock, full_perm_client: Client
    ) -> None:
        mock_get_jobs.return_value = [
            {"name": "etl_job", "description": "", "repository": "r", "location": "l"},
        ]
        resp = full_perm_client.get(reverse(JOB_URLS["changelist"]))
        assert resp.status_code == 200
        assert b"Dagster UI" in resp.content

    @patch("django_dagster.admin.client.get_runs")
    @patch("django_dagster.admin.client.get_run")
    def test_full_perm_sees_dagster_ui_links_run_detail(
        self,
        mock_get_run: MagicMock,
        mock_get_runs: MagicMock,
        full_perm_client: Client,
    ) -> None:
        mock_get_run.return_value = {
            "runId": "abc123",
            "jobName": "etl_job",
            "status": "SUCCESS",
            "startTime": None,
            "endTime": None,
            "runConfigYaml": "",
            "tags": [],
            "stats": None,
        }
        mock_get_runs.return_value = []
        resp = full_perm_client.get(reverse(RUN_URLS["change"], args=["abc123"]))
        assert resp.status_code == 200
        assert b"View in Dagster UI" in resp.content

    # -- Admin index ----------------------------------------------------------

    def test_viewer_sees_dagster_in_index(self, viewer_client: Client) -> None:
        resp = viewer_client.get(reverse("admin:index"))
        assert resp.status_code == 200
        assert b"Dagster" in resp.content

    def test_no_perms_no_dagster_in_index(self, client: Client, db: Any) -> None:
        from django.contrib.auth.models import User

        User.objects.create_user("noperms", password="pw", is_staff=True)
        client.login(username="noperms", password="pw")
        resp = client.get(reverse("admin:index"))
        assert resp.status_code == 200
        # The Dagster section should not appear
        assert b"django_dagster" not in resp.content


@pytest.mark.django_db
class TestPermissionsDisabled:
    """Default (DAGSTER_PERMISSIONS_ENABLED=False): all staff = full access."""

    def test_staff_can_access_without_explicit_perms(
        self, staff_client: Client
    ) -> None:
        """Staff user with no explicit permissions can still see everything."""
        with patch("django_dagster.admin.client.get_jobs") as mock:
            mock.return_value = []
            resp = staff_client.get(reverse(JOB_URLS["changelist"]))
            assert resp.status_code == 200

    @patch("django_dagster.admin.client.get_job_default_run_config")
    def test_staff_can_trigger_without_explicit_perms(
        self, mock_cfg: MagicMock, staff_client: Client
    ) -> None:
        mock_cfg.return_value = {}
        resp = staff_client.get(reverse(JOB_URLS["trigger"], args=["etl_job"]))
        assert resp.status_code == 200

    @patch("django_dagster.admin.client.cancel_run")
    def test_staff_can_cancel_without_explicit_perms(
        self, mock_cancel: MagicMock, staff_client: Client
    ) -> None:
        resp = staff_client.post(reverse(RUN_URLS["cancel"], args=["abc123"]))
        assert resp.status_code == 302
