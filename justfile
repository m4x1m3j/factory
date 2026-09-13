# List available recipes
default:
    @just --list

# Install dependencies, pre-commit hooks, AI assets
install:
    uv sync --dev
    uv run pre-commit install
    uv run factory project sync-assets

# Run tests
test *args:
    uv run pytest {{args}}

# Run tests with coverage
test-cov:
    uv run pytest --cov=src/factory

# Check code for lint errors
lint:
    uv run ruff check .

# Check code formatting
format-check:
    uv run ruff format --check .

# Format code
format:
    uv run ruff format .

# Run static type checking with mypy
typecheck:
    uv run mypy src tests

# Run all quality checks (lint, format-check, typecheck)
check: lint format-check typecheck

# Automatically fix lint and format issues
fix: format
    uv run ruff check --fix .

# Run all pre-commit hooks across the repository
precommit:
    uv run pre-commit run --all-files

# Run all quality checks and tests
all: check test
