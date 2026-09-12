# Contributing to Factory

Thank you for contributing to Factory! This document provides instructions for setting up your development environment, adhering to code quality standards, and submitting contributions.

---

## 1. Prerequisites & Environment Setup

Factory uses [`uv`](https://docs.astral.sh/uv/) for fast Python package and environment management.

### Prerequisites

- Python 3.11 or newer
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) installed
- [`just`](https://github.com/casey/just) command runner
- [`rtk`](https://github.com/rtk-ai/rtk) command-output proxy
- Git

### Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/m4x1m3j/factory.git
   cd factory
   ```

2. Bootstrap the Linux development environment:

   ```bash
   ./preinstall.sh
   ```

   The script installs `uv`, `just`, and `rtk`, syncs development dependencies,
   and configures pre-commit hooks. It requires `curl`.

3. Or install project dependencies and pre-commit hooks after `uv` and `just`
   are already available:

   ```bash
   just install
   # or manually:
   uv sync --dev
   uv run pre-commit install
   ```

---

## 2. Quick Commands (`just`)

A [`justfile`](justfile) is provided to run common development commands conveniently:

| Command | Description |
| --- | --- |
| `just` / `just --list` | List all available recipes |
| `just install` | Install dev dependencies and pre-commit Git hooks |
| `just check` | Run all quality checks (lint, format check, typecheck) |
| `just fix` | Automatically format code and fix autofixable lint errors |
| `just test` | Run test suite with pytest |
| `just test-cov` | Run tests with coverage reporting |
| `just lint` | Run Ruff linter |
| `just format` | Auto-format code with Ruff |
| `just format-check` | Check code formatting without writing changes |
| `just typecheck` | Run static type checking with mypy |
| `just precommit` | Run all pre-commit hooks across the repository |
| `just all` | Run all quality checks and tests at once |

---

## 3. Code Quality & Formatting

We maintain code quality using **Ruff** (linting and formatting) and **mypy** (static type checking).

### Pre-commit Hooks

Pre-commit hooks automatically verify and format your changes on every `git commit`. To run all hooks against the entire repository manually:

```bash
uv run pre-commit run --all-files
```

The pre-commit configuration includes:

- General hygiene (`trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-toml`, `check-added-large-files`)
- Ruff linter (`ruff check --fix`)
- Ruff formatter (`ruff format`)
- Mypy type checker (`mypy`)

### Linting & Formatting with Ruff

- **Check lint issues:**

  ```bash
  uv run ruff check .
  ```

- **Auto-fix lint issues:**

  ```bash
  uv run ruff check --fix .
  ```

- **Check code formatting:**

  ```bash
  uv run ruff format --check .
  ```

- **Auto-format code:**

  ```bash
  uv run ruff format .
  ```

### Static Type Checking with Mypy

All core codebase definitions in `src/factory` require type annotations. Note that archetype template resources (`src/factory/resources`) are excluded from type checking because they contain templating placeholders.

Run type checks:

```bash
uv run mypy src tests
```

---

## 4. Running Tests

Factory uses `pytest` and `pytest-cov` for testing.

- **Run all unit tests:**

  ```bash
  uv run pytest
  ```

- **Run tests with coverage:**

  ```bash
  uv run pytest --cov=src/factory
  ```

---

## 5. Continuous Integration (CI)

Every push to `main` and all pull requests trigger our GitHub Actions CI pipeline (`.github/workflows/ci.yml`), which executes two parallel jobs:

1. **Code Quality:** Verifies linting (`ruff check`), formatting (`ruff format --check`), and static typing (`mypy`).
2. **Tests:** Executes the complete test suite with coverage (`pytest --cov=src/factory`).

All CI checks must pass before pull requests can be merged.

---

## 6. Development Workflow & Submitting Changes

1. Create a feature branch from `main`:

   ```bash
   git checkout -b <issue-number>-<short-description>
   ```

2. Make your changes, adding tests and type annotations where appropriate.
3. Verify that all quality checks and tests pass locally:

   ```bash
   just all
   # or manually:
   uv run pre-commit run --all-files
   uv run pytest --cov=src/factory
   ```

4. Commit your changes and push your branch to GitHub.
5. Open a Pull Request against `main`, referencing the issue you are addressing.
