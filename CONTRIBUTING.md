# Contributing Guidelines

## Project overview

Django plugin for interacting with a Dagster server. Provides Django Admin views and a programmatic Python API.

## Project structure

- `django_dagster/` - main app (admin, client, models, templates, static)
- `tests/` - test suite (pytest + pytest-django)
- `demo/` - demo Django+Dagster project for manual testing
- `tasks.py` - invoke tasks for QA and utility commands (code formatting, screenshots, etc.)

## Environment setup

**Requirements:**
- [uv](https://docs.astral.sh/uv/) package manager

**Setup steps:**
1. Clone the repository
2. Install dependencies: `uv sync`
3. Verify setup: `uv run inv qa`

**Running the demo server:**
1. Navigate to demo directory: `cd demo`
2. Start Dagster: `uv run dagster dev`
3. In another terminal, start Django: `uv run python manage.py runserver`
4. Access Django Admin at http://localhost:8000/admin/
5. Access Dagster UI at http://localhost:3000

## Development

Follow the following pragmatic software engineering practices:

- Avoid over-engineered solutions, prefer simplicity and add complexity only when required (start small and simple)
- Avoid premature abstractions, especially in the beginning (e.g. prefer having a single well defined module than ten different ones containing a single entity each)
- Prefer explicit symbol names and logic structure over extensive comments
- Prefer functional programming over object-oriented programming (use the "functional core, imperative shell" pattern)
- When writing tests, use only test functions with well-thought fixture dependencies, but avoid test classes
- Test suites should match the source module architecture (e.g. `my_module.py` should have a `test_my_module.py` test suite)
- Design tests in a top-down fashion: start with functional tests from the user perspective with maximum dependencies, then focus with unit testing on surgical parts when needed to test subtle edge-cases
- Ideally, follow some pragmatic TDD workflow: write a test first, ensure it fails, implement the most simple solution, ensure it succeeds, iterate on another test

## Code style

**Enforced by tooling:**
- Linting: `ruff` (run `uv run inv lint` or `uv run inv format`)
- Type checking: `mypy` (run `uv run inv typing`)
- Security: `bandit` (run `uv run inv vuln`)

**Conventions:**
- Use type hints for all function signatures
- Prefer Google-style docstrings for public APIs
- Keep imports organized (standard library → third-party → local)
- Line length: 120 characters (enforced by ruff)
- Use explicit names; avoid cryptic abbreviations

## Testing

**Coverage requirement:**
- Test coverage must be 100% (enforced in CI)
- Run tests with coverage: `uv run inv test`

**Test organization:**
- Test files match source structure: `my_module.py` → `tests/test_my_module.py`
- Use test functions only (no test classes)
- Use fixtures for setup/teardown and shared dependencies
- Fixtures should be defined in `conftest.py` if shared among test modules or at the top of the test module if locally scoped

**Test types:**
1. **Functional tests** (priority): Test from user perspective with full dependencies
2. **Unit tests**: Test specific edge cases and internal logic

**Running tests:**
- All tests: `uv run inv test`
- Specific test: `uv run pytest tests/test_my_module.py::test_function_name`

## Dependencies

- Uses **uv** for dependency management
- After any change to `pyproject.toml` (version, dependencies), run `uv sync`
- Dev dependencies are in `[dependency-groups] dev` and must be pinned to exact version (ideally, the latest available)

## Common commands

- `uv run inv qa` - run the full QA pipeline (audit, vuln, lint, typing, test)
- `uv run inv audit` - dependency auditing (pip-audit)
- `uv run inv vuln` - security scanning (bandit)
- `uv run inv lint` - linting (ruff)
- `uv run inv typing` - type-checking (mypy)
- `uv run inv test` - running tests (pytest + coverage)
- `uv run inv format` - code formatting (ruff)
- `uv run inv shots` - generate admin screenshots (requires demo server)

## Git commits

**Branch naming:**
- Main branch is `main`
- Always commit new work in a feature branch with a proper prefix:
  - `feat/` - new features
  - `fix/` - bug fixes
  - `chore/` - maintenance tasks
  - `docs/` - documentation changes
  - `refactor/` - code refactoring
  - `test/` - test-related changes
  - `release/` - release preparation

**Commit format:**
- Use [Conventional Commits](https://www.conventionalcommits.org/) format: `<type>(<scope>): <description>`
- Common scopes:
  - `admin` - Django admin interface
  - `client` - Dagster client API
  - `api` - public Python API
  - `models` - Django models
  - `tests` - test suite
  - `deps` - dependencies
  - `readme` - README file
  - `ci` - CI/CD configuration
- Scope is optional for changes that span multiple areas
- Examples:
  - `feat(admin): add job cancellation button`
  - `fix(client): handle connection timeout properly`
  - `docs(readme): update installation instructions`
  - `chore(deps): update pytest to 8.0.0`

**Breaking changes:**
- Mark breaking changes with `!` after the scope: `feat(api)!: change return type of list_runs`
- Add `BREAKING CHANGE:` footer in commit body explaining the change and migration path
- Example:
  ```
  feat(api)!: change return type of list_runs

  BREAKING CHANGE: list_runs() now returns a dict instead of a list.
  Migration: access runs via result['runs'] instead of iterating directly.
  ```

**Quality requirements:**
- Test coverage must be 100% (enforced in CI)
- All QA checks must pass (`uv run inv qa`)

## Pull requests

**Creating a PR:**
1. Ensure your branch is up to date with `main`
2. Run full QA suite: `uv run inv qa`
3. Clean up commit history: `git rebase -i` to squash/reword commits
4. Push your branch to the remote repository
5. Create a pull request on GitHub

**PR description should include:**
- Summary of changes
- Motivation/context
- Related issue numbers (if applicable)
- Testing performed
- Screenshots (for UI changes)

**Review process:**
- PRs are merged using rebase-merge onto `main` (no merge commits, no squash merges)
- All CI checks must pass
- Keep commit history clean and logical

**Changelog updates:**
- Update `CHANGELOG.md` in PRs under the "Unreleased" section
- Follow [Keep a Changelog](https://keepachangelog.com/) format (Added, Changed, Fixed, etc.)
- During release preparation, the "Unreleased" section is versioned and dated

## Releases

- Version tags have **no `v` prefix** (e.g. `0.1.0`, not `v0.1.0`)
- Current version is defined in `pyproject.toml`
- Changelog follows [Keep a Changelog](https://keepachangelog.com/) format in `CHANGELOG.md`
- Changelog is allowed to not log everything (especially internals), priority is given to the user's perspective
- Release branches are named `release/<version>`
- Release branches should only contain a single commit updating the changelog and the project version number
- Release commit message: `chore: release version <version>`
- When a release branch is rebased onto the main branch, add and push a tag with the version number onto the main branch.