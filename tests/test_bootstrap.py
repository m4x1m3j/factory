from pathlib import Path

import pytest

from factory.bootstrap import BootstrapError, ProjectBootstrapper


def test_should_scaffold_python_project_when_archetype_is_supported(
    tmp_path: Path,
) -> None:
    # Given a clean destination
    project_dir = tmp_path / "forecast-service"

    # When the Python archetype is initialized
    result = ProjectBootstrapper().initialize(
        "forecast-service", "python", destination=tmp_path
    )

    # Then the target project contains core source, tooling, sandbox, CI, and config
    assert result == project_dir
    assert (project_dir / "pyproject.toml").is_file()
    assert (project_dir / "src/forecast_service/main.py").is_file()
    assert (project_dir / "tests/test_forecast_service.py").is_file()
    assert (project_dir / "Dockerfile").is_file()
    assert (project_dir / ".devcontainer/devcontainer.json").is_file()
    assert (project_dir / ".github/workflows/ci.yml").is_file()
    assert (project_dir / ".factory/config.yaml").is_file()
    justfile = (project_dir / "justfile").read_text(encoding="utf-8")
    assert "uv run pytest --cov=src/forecast_service" in justfile
    assert "{{ package_name }}" not in justfile
    assert (project_dir / ".github/copilot-instructions.md").is_file()
    assert (project_dir / ".github/agents/issue-developer.agent.md").is_file()
    assert (project_dir / ".opencode/agents/pr-reviewer.md").is_file()
    assert (project_dir / "opencode.json").is_file()


def test_should_write_project_metadata_when_project_is_initialized(
    tmp_path: Path,
) -> None:
    # Given a clean destination
    # When a named Python project is initialized
    ProjectBootstrapper().initialize("my-api", "python", destination=tmp_path)

    # Then generated metadata identifies project and engine settings
    config = (tmp_path / "my-api/.factory/config.yaml").read_text(encoding="utf-8")
    assert "name: my-api" in config
    assert "archetype: python" in config
    assert "specification: Dockerfile" in config
    assert "tier1:" in config
    assert "tier2:" in config


def test_should_support_python_mlops_alias_when_archetype_is_requested(
    tmp_path: Path,
) -> None:
    # Given a clean destination
    # When the Python MLOps archetype is initialized
    ProjectBootstrapper().initialize("ml-project", "python-mlops", destination=tmp_path)

    # Then a valid Python project is generated
    assert (tmp_path / "ml-project/pyproject.toml").is_file()
    assert "python-mlops` archetype" in (tmp_path / "ml-project/README.md").read_text(
        encoding="utf-8"
    )


def test_should_reject_unknown_archetype_when_initializing_project(
    tmp_path: Path,
) -> None:
    # Given an unsupported archetype
    # When project initialization is requested
    with pytest.raises(BootstrapError, match="Unknown archetype"):
        ProjectBootstrapper().initialize("demo", "unknown", destination=tmp_path)

    # Then no target directory is created
    assert not (tmp_path / "demo").exists()


def test_should_reject_non_empty_target_when_initializing_project(
    tmp_path: Path,
) -> None:
    # Given an existing project directory containing user data
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    (project_dir / "keep.txt").write_text("keep", encoding="utf-8")

    # When project initialization is requested
    with pytest.raises(BootstrapError, match="not empty"):
        ProjectBootstrapper().initialize("demo", "python", destination=tmp_path)

    # Then existing data remains unchanged
    assert (project_dir / "keep.txt").read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize(
    "name", ["", "../escape", ".", "bad/name", "-bad", "123-project"]
)
def test_should_reject_invalid_project_name_when_initializing_project(
    tmp_path: Path,
    name: str,
) -> None:
    # Given a project name that cannot safely identify a target directory
    # When project initialization is requested
    with pytest.raises(BootstrapError, match="Project name"):
        ProjectBootstrapper().initialize(name, "python", destination=tmp_path)

    # Then no project is created
    assert list(tmp_path.iterdir()) == []
