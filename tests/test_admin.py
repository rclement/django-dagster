from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from django.contrib.admin.sites import AdminSite
from django.urls import reverse

from django_dagster.admin import DagsterJobAdmin, DagsterRunAdmin
from django_dagster.models import DagsterJob, DagsterRun

# ---------------------------------------------------------------------------
# Admin registration
# ---------------------------------------------------------------------------


def test_models_registered():
    from django.contrib import admin

    assert DagsterJob in admin.site._registry
    assert DagsterRun in admin.site._registry


def test_job_admin_class():
    admin_instance = DagsterJobAdmin(DagsterJob, AdminSite())
    assert admin_instance is not None


def test_run_admin_class():
    admin_instance = DagsterRunAdmin(DagsterRun, AdminSite())
    assert admin_instance is not None


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

JOB_URLS = {
    "changelist": "admin:django_dagster_dagsterjob_changelist",
    "add": "admin:django_dagster_dagsterjob_add",
    "change": "admin:django_dagster_dagsterjob_change",
}

RUN_URLS = {
    "changelist": "admin:django_dagster_dagsterrun_changelist",
    "change": "admin:django_dagster_dagsterrun_change",
    "cancel": "admin:django_dagster_dagsterrun_cancel",
    "retry": "admin:django_dagster_dagsterrun_retry",
}


@pytest.mark.django_db
def test_urls_resolve():
    assert reverse(JOB_URLS["changelist"])
    assert reverse(JOB_URLS["add"])
    assert reverse(JOB_URLS["change"], args=["etl_job"])
    assert reverse(RUN_URLS["changelist"])
    assert reverse(RUN_URLS["change"], args=["abc123"])
    assert reverse(RUN_URLS["cancel"], args=["abc123"])
    assert reverse(RUN_URLS["retry"], args=["abc123"])


# ---------------------------------------------------------------------------
# Auth: all views require staff
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAuthRequired:
    def test_anonymous_job_changelist(self, client):
        assert client.get(reverse(JOB_URLS["changelist"])).status_code == 302

    def test_anonymous_job_add(self, client):
        assert client.get(reverse(JOB_URLS["add"])).status_code == 302

    def test_anonymous_run_changelist(self, client):
        assert client.get(reverse(RUN_URLS["changelist"])).status_code == 302

    def test_anonymous_run_change(self, client):
        url = reverse(RUN_URLS["change"], args=["abc123"])
        assert client.get(url).status_code == 302

    def test_anonymous_cancel(self, client):
        url = reverse(RUN_URLS["cancel"], args=["abc123"])
        assert client.post(url).status_code == 302

    def test_anonymous_retry(self, client):
        url = reverse(RUN_URLS["retry"], args=["abc123"])
        assert client.post(url).status_code == 302

    def test_non_staff_redirected(self, client, db):
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
    def test_renders_jobs(self, mock_get_jobs, staff_client):
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
    def test_empty_jobs(self, mock_get_jobs, staff_client):
        mock_get_jobs.return_value = []

        resp = staff_client.get(reverse(JOB_URLS["changelist"]))

        assert resp.status_code == 200
        assert b"No jobs found" in resp.content

    @patch("django_dagster.admin.client.get_jobs")
    def test_connection_error(self, mock_get_jobs, staff_client):
        mock_get_jobs.side_effect = ConnectionError("Connection refused")

        resp = staff_client.get(reverse(JOB_URLS["changelist"]))

        assert resp.status_code == 200
        assert b"Failed to connect to Dagster" in resp.content

    @patch("django_dagster.admin.client.get_jobs")
    def test_job_name_links_to_detail(self, mock_get_jobs, staff_client):
        mock_get_jobs.return_value = [
            {"name": "etl_job", "description": "", "repository": "r", "location": "l"},
        ]

        resp = staff_client.get(reverse(JOB_URLS["changelist"]))

        detail_url = reverse(JOB_URLS["change"], args=["etl_job"])
        assert detail_url.encode() in resp.content

    @patch("django_dagster.admin.client.get_jobs")
    def test_sort_by_name(self, mock_get_jobs, staff_client):
        mock_get_jobs.return_value = [
            {"name": "b_job", "description": "", "repository": "r", "location": "l"},
            {"name": "a_job", "description": "", "repository": "r", "location": "l"},
        ]

        resp = staff_client.get(
            reverse(JOB_URLS["changelist"]) + "?o=name"
        )

        assert resp.status_code == 200
        content = resp.content.decode()
        assert content.index("a_job") < content.index("b_job")

    @patch("django_dagster.admin.client.get_jobs")
    def test_config_recap_shown(self, mock_get_jobs, staff_client):
        mock_get_jobs.return_value = []

        resp = staff_client.get(reverse(JOB_URLS["changelist"]))

        assert resp.status_code == 200
        assert b"http://localhost:3000" in resp.content


# ---------------------------------------------------------------------------
# Job detail (change view)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@patch("django_dagster.admin.client.get_runs")
class TestJobDetailView:
    @patch("django_dagster.admin.client.get_jobs")
    def test_renders_detail(self, mock_get_jobs, mock_get_runs, staff_client):
        mock_get_jobs.return_value = [
            {"name": "etl_job", "description": "Daily ETL", "repository": "repo", "location": "loc"},
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
    def test_has_trigger_button(self, mock_get_jobs, mock_get_runs, staff_client):
        mock_get_jobs.return_value = [
            {"name": "etl_job", "description": "", "repository": "r", "location": "l"},
        ]
        mock_get_runs.return_value = []

        resp = staff_client.get(reverse(JOB_URLS["change"], args=["etl_job"]))

        assert b"Trigger New Run" in resp.content

    @patch("django_dagster.admin.client.get_jobs")
    def test_has_view_runs_button(self, mock_get_jobs, mock_get_runs, staff_client):
        mock_get_jobs.return_value = [
            {"name": "etl_job", "description": "", "repository": "r", "location": "l"},
        ]
        mock_get_runs.return_value = []

        resp = staff_client.get(reverse(JOB_URLS["change"], args=["etl_job"]))

        assert b"View Runs" in resp.content

    @patch("django_dagster.admin.client.get_jobs")
    def test_not_found_redirects(self, mock_get_jobs, mock_get_runs, staff_client):
        mock_get_jobs.return_value = [
            {"name": "other_job", "description": "", "repository": "r", "location": "l"},
        ]

        resp = staff_client.get(
            reverse(JOB_URLS["change"], args=["nonexistent_job"])
        )

        assert resp.status_code == 302
        assert reverse(JOB_URLS["changelist"]) in resp.url

    @patch("django_dagster.admin.client.get_jobs")
    def test_connection_error_redirects(self, mock_get_jobs, mock_get_runs, staff_client):
        mock_get_jobs.side_effect = ConnectionError("refused")

        resp = staff_client.get(
            reverse(JOB_URLS["change"], args=["etl_job"])
        )

        assert resp.status_code == 302

    @patch("django_dagster.admin.client.get_jobs")
    def test_uses_fieldset_layout(self, mock_get_jobs, mock_get_runs, staff_client):
        mock_get_jobs.return_value = [
            {"name": "etl_job", "description": "Daily ETL", "repository": "r", "location": "l"},
        ]
        mock_get_runs.return_value = []

        resp = staff_client.get(reverse(JOB_URLS["change"], args=["etl_job"]))

        assert b"fieldset" in resp.content
        assert b"submit-row" in resp.content

    @patch("django_dagster.admin.client.get_jobs")
    def test_recent_runs_shown(self, mock_get_jobs, mock_get_runs, staff_client):
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


# ---------------------------------------------------------------------------
# Trigger job (add view)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTriggerJobView:
    @patch("django_dagster.admin.client.get_jobs")
    def test_get_renders_form(self, mock_get_jobs, staff_client):
        mock_get_jobs.return_value = [
            {"name": "etl_job", "description": "", "repository": "r", "location": "l"},
        ]

        resp = staff_client.get(reverse(JOB_URLS["add"]))

        assert resp.status_code == 200
        assert b"etl_job" in resp.content

    @patch("django_dagster.admin.client.get_jobs")
    def test_get_prefills_job_name(self, mock_get_jobs, staff_client):
        mock_get_jobs.return_value = [
            {"name": "etl_job", "description": "", "repository": "r", "location": "l"},
        ]

        resp = staff_client.get(reverse(JOB_URLS["add"]) + "?job=etl_job")

        assert resp.status_code == 200
        assert b"selected" in resp.content

    @patch("django_dagster.admin.client.submit_job")
    def test_post_triggers_job(self, mock_submit, staff_client):
        mock_submit.return_value = "new-run-123"

        resp = staff_client.post(
            reverse(JOB_URLS["add"]),
            {"job_name": "etl_job", "run_config": ""},
        )

        assert resp.status_code == 302
        assert "new-run-123" in resp.url
        mock_submit.assert_called_once_with("etl_job", run_config=None)

    @patch("django_dagster.admin.client.submit_job")
    def test_post_redirects_to_run_detail(self, mock_submit, staff_client):
        mock_submit.return_value = "new-run-123"

        resp = staff_client.post(
            reverse(JOB_URLS["add"]),
            {"job_name": "etl_job", "run_config": ""},
        )

        expected = reverse(RUN_URLS["change"], args=["new-run-123"])
        assert resp.url == expected

    @patch("django_dagster.admin.client.submit_job")
    def test_post_with_config(self, mock_submit, staff_client):
        mock_submit.return_value = "new-run-456"

        resp = staff_client.post(
            reverse(JOB_URLS["add"]),
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

    @patch("django_dagster.admin.client.get_jobs")
    def test_post_invalid_json(self, mock_get_jobs, staff_client):
        mock_get_jobs.return_value = []

        resp = staff_client.post(
            reverse(JOB_URLS["add"]),
            {"job_name": "etl_job", "run_config": "{bad json"},
        )

        assert resp.status_code == 200
        assert b"Invalid JSON config" in resp.content

    @patch("django_dagster.admin.client.get_jobs")
    def test_post_missing_job_name(self, mock_get_jobs, staff_client):
        mock_get_jobs.return_value = []

        resp = staff_client.post(
            reverse(JOB_URLS["add"]),
            {"job_name": "", "run_config": ""},
        )

        assert resp.status_code == 200
        assert b"Job name is required" in resp.content

    @patch("django_dagster.admin.client.get_jobs")
    @patch("django_dagster.admin.client.submit_job")
    def test_post_dagster_error_preserves_form(
        self, mock_submit, mock_get_jobs, staff_client
    ):
        mock_submit.side_effect = Exception("JobNotFoundError")
        mock_get_jobs.return_value = [
            {"name": "etl_job", "description": "", "repository": "r", "location": "l"},
        ]

        resp = staff_client.post(
            reverse(JOB_URLS["add"]),
            {"job_name": "etl_job", "run_config": '{"key": "val"}'},
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
    def test_renders_runs(self, mock_get_runs, mock_get_jobs, staff_client):
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
    def test_filters(self, mock_get_runs, mock_get_jobs, staff_client):
        mock_get_jobs.return_value = []
        mock_get_runs.return_value = []

        resp = staff_client.get(
            reverse(RUN_URLS["changelist"]) + "?job=etl_job&status=FAILURE"
        )

        assert resp.status_code == 200
        mock_get_runs.assert_called_once_with(
            job_name="etl_job", statuses=["FAILURE"]
        )

    @patch("django_dagster.admin.client.get_runs")
    def test_connection_error(self, mock_get_runs, mock_get_jobs, staff_client):
        mock_get_jobs.return_value = []
        mock_get_runs.side_effect = ConnectionError("refused")

        resp = staff_client.get(reverse(RUN_URLS["changelist"]))

        assert resp.status_code == 200
        assert b"Failed to connect to Dagster" in resp.content

    @patch("django_dagster.admin.client.get_runs")
    def test_run_links_to_detail(self, mock_get_runs, mock_get_jobs, staff_client):
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
    def test_job_filter_is_dropdown(self, mock_get_runs, mock_get_jobs, staff_client):
        mock_get_jobs.return_value = [
            {"name": "etl_job", "description": "", "repository": "r", "location": "l"},
            {"name": "report_job", "description": "", "repository": "r", "location": "l"},
        ]
        mock_get_runs.return_value = []

        resp = staff_client.get(reverse(RUN_URLS["changelist"]))

        assert resp.status_code == 200
        # Job filter should be a <select> with job names as options
        assert b'<select id="id_job"' in resp.content
        assert b"etl_job" in resp.content
        assert b"report_job" in resp.content


# ---------------------------------------------------------------------------
# Run detail (change view)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@patch("django_dagster.admin.client.get_runs")
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

    @patch("django_dagster.admin.client.get_run")
    def test_renders_detail(self, mock_get_run, mock_get_runs, staff_client):
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
    def test_cancel_button_shown_for_running(self, mock_get_run, mock_get_runs, staff_client):
        mock_get_run.return_value = self._make_run(status="STARTED")
        mock_get_runs.return_value = []

        run_id = "abc12345-def0-1234-5678-abcdef012345"
        resp = staff_client.get(reverse(RUN_URLS["change"], args=[run_id]))

        assert resp.status_code == 200
        assert b"Cancel Run" in resp.content

    @patch("django_dagster.admin.client.get_run")
    def test_retry_button_shown_for_failed(self, mock_get_run, mock_get_runs, staff_client):
        mock_get_run.return_value = self._make_run(status="FAILURE")
        mock_get_runs.return_value = []

        run_id = "abc12345-def0-1234-5678-abcdef012345"
        resp = staff_client.get(reverse(RUN_URLS["change"], args=[run_id]))

        assert resp.status_code == 200
        assert b"Retry Run" in resp.content
        assert b"Cancel Run" not in resp.content

    @patch("django_dagster.admin.client.get_run")
    def test_no_action_buttons_for_success(self, mock_get_run, mock_get_runs, staff_client):
        mock_get_run.return_value = self._make_run(status="SUCCESS")
        mock_get_runs.return_value = []

        run_id = "abc12345-def0-1234-5678-abcdef012345"
        resp = staff_client.get(reverse(RUN_URLS["change"], args=[run_id]))

        assert resp.status_code == 200
        assert b"Cancel Run" not in resp.content
        assert b"Retry Run" not in resp.content

    @patch("django_dagster.admin.client.get_run")
    def test_not_found_redirects(self, mock_get_run, mock_get_runs, staff_client):
        mock_get_run.return_value = None

        resp = staff_client.get(
            reverse(RUN_URLS["change"], args=["nonexistent"])
        )

        assert resp.status_code == 302
        assert reverse(RUN_URLS["changelist"]) in resp.url

    @patch("django_dagster.admin.client.get_run")
    def test_error_redirects(self, mock_get_run, mock_get_runs, staff_client):
        mock_get_run.side_effect = Exception("boom")

        resp = staff_client.get(
            reverse(RUN_URLS["change"], args=["some-id"])
        )

        assert resp.status_code == 302

    @patch("django_dagster.admin.client.get_run")
    def test_related_runs_shown(self, mock_get_run, mock_get_runs, staff_client):
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


# ---------------------------------------------------------------------------
# Cancel run
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCancelRunView:
    @patch("django_dagster.admin.client.cancel_run")
    def test_cancel_success(self, mock_cancel, staff_client):
        run_id = "abc12345-def0-1234-5678-abcdef012345"
        resp = staff_client.post(reverse(RUN_URLS["cancel"], args=[run_id]))

        assert resp.status_code == 302
        assert run_id in resp.url
        mock_cancel.assert_called_once_with(run_id)

    @patch("django_dagster.admin.client.cancel_run")
    def test_cancel_redirects_to_run_detail(self, mock_cancel, staff_client):
        run_id = "abc123"
        resp = staff_client.post(reverse(RUN_URLS["cancel"], args=[run_id]))

        expected = reverse(RUN_URLS["change"], args=[run_id])
        assert resp.url == expected

    @patch("django_dagster.admin.client.cancel_run")
    def test_cancel_error(self, mock_cancel, staff_client):
        mock_cancel.side_effect = Exception("Already finished")

        run_id = "abc123"
        resp = staff_client.post(reverse(RUN_URLS["cancel"], args=[run_id]))

        assert resp.status_code == 302
        assert run_id in resp.url

    def test_cancel_get_redirects(self, staff_client):
        """GET should not cancel, just redirect."""
        run_id = "abc123"
        resp = staff_client.get(reverse(RUN_URLS["cancel"], args=[run_id]))

        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Retry run
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRetryRunView:
    @patch("django_dagster.admin.client.retry_run")
    def test_retry_success(self, mock_retry, staff_client):
        mock_retry.return_value = "new-retry-id"

        run_id = "failed-run-123"
        resp = staff_client.post(reverse(RUN_URLS["retry"], args=[run_id]))

        assert resp.status_code == 302
        assert "new-retry-id" in resp.url
        mock_retry.assert_called_once_with(run_id)

    @patch("django_dagster.admin.client.retry_run")
    def test_retry_redirects_to_new_run(self, mock_retry, staff_client):
        mock_retry.return_value = "new-retry-id"

        resp = staff_client.post(
            reverse(RUN_URLS["retry"], args=["old-run-id"])
        )

        expected = reverse(RUN_URLS["change"], args=["new-retry-id"])
        assert resp.url == expected

    @patch("django_dagster.admin.client.retry_run")
    def test_retry_error(self, mock_retry, staff_client):
        mock_retry.side_effect = Exception("Run not found")

        run_id = "bad-id"
        resp = staff_client.post(reverse(RUN_URLS["retry"], args=[run_id]))

        assert resp.status_code == 302
        assert run_id in resp.url

    def test_retry_get_redirects(self, staff_client):
        """GET should not retry, just redirect."""
        run_id = "abc123"
        resp = staff_client.get(reverse(RUN_URLS["retry"], args=[run_id]))

        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Admin index integration
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAdminIndex:
    def test_dagster_section_with_both_models(self, staff_client):
        resp = staff_client.get(reverse("admin:index"))

        assert resp.status_code == 200
        assert b"Dagster" in resp.content
        assert b"Jobs" in resp.content
        assert b"Runs" in resp.content

    def test_dagster_app_index(self, staff_client):
        resp = staff_client.get(
            reverse("admin:app_list", args=["django_dagster"])
        )

        assert resp.status_code == 200
        assert b"Jobs" in resp.content
        assert b"Runs" in resp.content

    def test_jobs_has_add_link(self, staff_client):
        """The Jobs entry should have an Add (+) link in the admin index."""
        resp = staff_client.get(reverse("admin:index"))

        add_url = reverse(JOB_URLS["add"])
        assert add_url.encode() in resp.content
