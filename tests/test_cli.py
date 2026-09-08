from pathlib import Path

from typer.testing import CliRunner

from factory.cli import app

runner = CliRunner()


def test_should_initialize_project_when_cli_command_is_valid(
    tmp_path: Path, monkeypatch
) -> None:
    # Given a clean working directory
    monkeypatch.chdir(tmp_path)

    # When the project init command is invoked
    result = runner.invoke(
        app,
        ["project", "init", "cli-demo", "--archetype", "python"],
        catch_exceptions=False,
    )

    # Then command succeeds and creates project in current directory
    assert result.exit_code == 0
    assert "Initialized python project" in result.stdout
    assert (tmp_path / "cli-demo").exists()


def test_should_report_error_when_cli_archetype_is_unknown(
    tmp_path: Path, monkeypatch
) -> None:
    # Given a clean working directory
    monkeypatch.chdir(tmp_path)

    # When an unknown archetype is requested
    result = runner.invoke(
        app,
        ["project", "init", "cli-demo", "--archetype", "unknown"],
        catch_exceptions=False,
    )

    # Then command fails with available archetype guidance
    assert result.exit_code == 1
    assert "Unknown archetype" in result.output


def test_should_initialize_project_in_requested_directory(
    tmp_path: Path, monkeypatch
) -> None:
    # Given a working directory different from the requested destination
    working_dir = tmp_path / "working"
    destination = tmp_path / "projects"
    working_dir.mkdir()
    monkeypatch.chdir(working_dir)

    # When the project init command receives a directory option
    result = runner.invoke(
        app,
        [
            "project",
            "init",
            "directory-demo",
            "--archetype",
            "python",
            "--directory",
            str(destination),
        ],
        catch_exceptions=False,
    )

    # Then the project is created below the requested directory
    assert result.exit_code == 0
    assert (destination / "directory-demo").is_dir()
    assert not (working_dir / "directory-demo").exists()


def test_should_synchronize_assets_in_current_directory(
    tmp_path: Path, monkeypatch
) -> None:
    # Given a target project directory
    monkeypatch.chdir(tmp_path)

    # When the asset sync command is invoked
    result = runner.invoke(app, ["project", "sync-assets"], catch_exceptions=False)

    # Then both harness configurations are generated
    assert result.exit_code == 0
    assert "Synchronized" in result.stdout
    assert (tmp_path / ".github/copilot-instructions.md").is_file()
    assert (tmp_path / ".opencode/agents/security.md").is_file()


def test_should_synchronize_assets_in_requested_directory(
    tmp_path: Path, monkeypatch
) -> None:
    # Given a working directory different from the target project
    working_dir = tmp_path / "working"
    project_dir = tmp_path / "project"
    working_dir.mkdir()
    project_dir.mkdir()
    monkeypatch.chdir(working_dir)

    # When the asset sync command receives a directory option
    result = runner.invoke(
        app,
        ["project", "sync-assets", "--directory", str(project_dir)],
        catch_exceptions=False,
    )

    # Then assets are written to the requested target
    assert result.exit_code == 0
    assert (project_dir / ".vscode/mcp.json").is_file()
    assert not (working_dir / ".vscode").exists()
