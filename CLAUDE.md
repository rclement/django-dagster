# CLAUDE.md

## Project overview

Django plugin for interacting with a Dagster server. Provides Django Admin views and a programmatic Python API.

## Project structure

- `django_dagster/` - main app (admin, client, models, templates, static)
- `tests/` - test suite (pytest + pytest-django)
- `demo/` - demo Django+Dagster project for manual testing
- `tasks.py` - invoke tasks for QA, formatting, screenshots

## Dependencies

- Uses **uv** for dependency management
- After any change to `pyproject.toml` (version, dependencies), run `uv sync`
- Dev dependencies are in `[dependency-groups] dev`

## Common commands

- `uv run inv qa` - run the full QA pipeline (audit, vuln, lint, typing, test)
- `uv run inv format` - format code with ruff
- `uv run inv lint` - lint with ruff
- `uv run inv typing` - type-check with mypy
- `uv run inv test` - run tests with pytest + coverage
- `uv run inv audit` - dependency audit with pip-audit
- `uv run inv vuln` - security scan with bandit
- `uv run inv shots` - generate admin screenshots (requires demo server)

## Releases

- Version tags have **no `v` prefix** (e.g. `0.1.0`, not `v0.1.0`)
- Version is defined in `pyproject.toml` under `[project] version`
- Changelog follows [Keep a Changelog](https://keepachangelog.com/) format in `CHANGELOG.md`
- Release branches are named `release/<version>`
- Release commit message: `chore: release version <version>`
