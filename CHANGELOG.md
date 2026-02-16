# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-02-17

Initial release of Django Dagster, a Django plugin for interacting with a Dagster server through the Django admin interface.

### Added

- Native Django Admin integration with dedicated **Dagster** section
- Job list and detail views showing all jobs from a connected Dagster instance
- Run list with status and job filtering and column sorting
- Trigger new job executions with optional JSON run config, pre-filled with defaults
- Cancel running jobs and re-execute completed/failed runs
- Detailed run view with metadata, config, tags, and event logs
- Direct links to the Dagster UI from job and run detail views
- Optional granular permission system using Django's built-in permissions (`DAGSTER_PERMISSIONS_ENABLED`)
- Programmatic Python API: `get_jobs`, `get_runs`, `get_run`, `submit_job`, `cancel_run`, `reexecute_run`, `get_run_events`, `get_job_default_run_config`
- Support for Python 3.10–3.14 and Django 4.2, 5.2, 6.0

[Unreleased]: https://github.com/rclement/django-dagster/compare/0.1.0...HEAD
[0.1.0]: https://github.com/rclement/django-dagster/releases/tag/0.1.0
