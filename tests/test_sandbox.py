from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from factory.bootstrap import ProjectBootstrapper
from factory.sandbox import (
    ContainerResult,
    DockerRuntime,
    SandboxConfig,
    SandboxError,
    SandboxManager,
)


class FakeRuntime:
    def __init__(self, exit_code: int = 0) -> None:
        self.exit_code = exit_code
        self.worktree: Path | None = None
        self.command: Sequence[str] = ()
        self.config: SandboxConfig | None = None
        self.has_self_contained_git = False

    def run(
        self,
        *,
        name: str,
        worktree: Path,
        command: Sequence[str],
        config: SandboxConfig,
        timeout: float | None,
    ) -> ContainerResult:
        self.worktree = worktree
        self.command = command
        self.config = config
        self.has_self_contained_git = (worktree / ".git").is_dir()
        (worktree / "generated.txt").write_text("generated", encoding="utf-8")
        return ContainerResult(self.exit_code, "agent output", "agent error")

    def prepare(
        self, *, name: str, worktree: Path, config: SandboxConfig
    ) -> SandboxConfig:
        return config

    def cleanup(self, config: SandboxConfig) -> None:
        pass


class AssetValidationRuntime(FakeRuntime):
    def run(
        self,
        *,
        name: str,
        worktree: Path,
        command: Sequence[str],
        config: SandboxConfig,
        timeout: float | None,
    ) -> ContainerResult:
        assert (worktree / ".github/copilot-instructions.md").is_file()
        assert (worktree / ".github/agents/development.agent.md").is_file()
        assert (worktree / ".github/hooks/pre-tool-use.json").is_file()
        assert (worktree / ".opencode/skills/caveman/SKILL.md").is_file()
        assert (worktree / ".opencode/agents/security.md").is_file()

        mcp = json.loads((worktree / ".vscode/mcp.json").read_text(encoding="utf-8"))
        assert mcp["servers"]["github"]["env"]["GITHUB_PERSONAL_ACCESS_TOKEN"] == (
            "${env:GITHUB_TOKEN}"
        )
        opencode = json.loads((worktree / "opencode.json").read_text(encoding="utf-8"))
        assert set(opencode["agent"]) == {
            "development",
            "review",
            "security",
            "architecture",
            "product-management",
        }
        return ContainerResult(0, "validated", "")


def test_project_runtime_builds_an_image_with_uv_and_project_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    (worktree / "pyproject.toml").write_text(
        "[project]\nname='demo'\n", encoding="utf-8"
    )
    calls: list[tuple[list[str], str | None]] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        value = kwargs.get("input")
        calls.append((command, value if isinstance(value, str) else None))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("factory.sandbox.subprocess.run", run)
    config = DockerRuntime().prepare(
        name="task",
        worktree=worktree,
        config=SandboxConfig(),
    )

    assert config.image == "factory-sandbox-task"
    assert config.environment["UV_CACHE_DIR"] == "/tmp/uv-cache"
    assert config.environment["UV_NO_SYNC"] == "1"
    assert config.environment["UV_PROJECT_ENVIRONMENT"] == "/opt/factory-venv"
    assert calls
    dockerfile = calls[0][1] or ""
    assert "uv sync --dev; fi" in dockerfile
    assert "WORKDIR /workspace" in dockerfile
    assert "uv sync --dev --directory /workspace" not in dockerfile
    assert "ENV UV_CACHE_DIR=/tmp/uv-cache" in dockerfile
    assert "chmod -R a+rwX /tmp/uv-cache /opt/factory-venv" in dockerfile


def test_reference_project_assets_validate_inside_isolated_sandbox(
    tmp_path: Path,
) -> None:
    project = ProjectBootstrapper().initialize(
        "reference-project", "python", destination=tmp_path
    )
    create_repository(project)
    subprocess.run(["git", "-C", str(project), "add", "--all"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(project),
            "commit",
            "-m",
            "generated reference project",
        ],
        check=True,
    )

    result = SandboxManager(project, runtime=AssetValidationRuntime()).run(
        "asset-validation", ["factory", "validate-assets"]
    )

    assert result.succeeded
    assert result.stdout == "validated"


def create_repository(path: Path) -> None:
    subprocess.run(["git", "init", "--initial-branch", "main", path], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"], check=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "test@example.com"],
        check=True,
    )
    (path / "README.md").write_text("original\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-m", "initial"], check=True)


def test_run_is_disposable_by_default_and_does_not_create_a_branch(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    create_repository(repository)
    runtime = FakeRuntime()

    result = SandboxManager(repository, runtime=runtime).run(
        "issue-7", ["agent", "--task", "implement"]
    )

    assert result.succeeded
    assert result.branch is None
    assert result.changed_files == ("generated.txt",)
    assert "generated.txt" in result.diff
    assert (repository / "README.md").read_text(encoding="utf-8") == "original\n"
    assert not (repository / "generated.txt").exists()
    assert (
        subprocess.run(
            ["git", "-C", str(repository), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        == ""
    )
    assert runtime.worktree is not None
    assert runtime.worktree != repository
    assert not runtime.worktree.exists()
    assert runtime.has_self_contained_git
    assert tuple(runtime.command) == ("agent", "--task", "implement")
    assert runtime.config is not None
    assert runtime.config.network == "none"

    branches = subprocess.run(
        ["git", "-C", str(repository), "branch", "--list", "factory/*"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert branches.stdout == ""


def test_persistent_run_extracts_a_branch_for_pr_publication(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    create_repository(repository)

    result = SandboxManager(repository, runtime=FakeRuntime()).run(
        "issue-7", ["agent"], persist_branch=True
    )

    assert result.branch is not None
    assert result.branch.startswith("factory/issue-7-")
    branch_file = subprocess.run(
        ["git", "-C", str(repository), "show", f"{result.branch}:generated.txt"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert branch_file.stdout == "generated"


def test_nonzero_agent_result_still_extracts_partial_changes(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    create_repository(repository)

    result = SandboxManager(repository, runtime=FakeRuntime(exit_code=42)).run(
        "failed-task", ["agent"]
    )

    assert result.exit_code == 42
    assert not result.succeeded
    assert result.changed_files == ("generated.txt",)


def test_docker_command_has_no_host_mount_or_network(tmp_path: Path) -> None:
    runtime = DockerRuntime()
    command = runtime.build_run_command(
        name="factory-task",
        worktree=tmp_path / "worktree",
        command=["sh", "-c", "printf ok"],
        config=SandboxConfig(),
    )

    assert command[:3] == ["docker", "run", "--rm"]
    assert "--network" in command
    assert command[command.index("--network") + 1] == "none"
    assert "--cap-drop" in command
    assert command[command.index("--cap-drop") + 1] == "ALL"
    assert "--mount" in command
    mount = command[command.index("--mount") + 1]
    assert "target=/workspace" in mount
    assert str(Path.cwd()) not in mount
    assert command[-4:] == ["python:3.12-slim", "sh", "-c", "printf ok"]


def test_docker_command_rejects_host_networking(tmp_path: Path) -> None:
    with pytest.raises(SandboxError, match="Host networking"):
        DockerRuntime().build_run_command(
            name="factory-task",
            worktree=tmp_path / "worktree",
            command=["true"],
            config=SandboxConfig(network="host"),
        )
