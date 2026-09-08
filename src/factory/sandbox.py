"""Containerized execution sandboxes for agent tasks.

The manager deliberately separates the repository's current worktree from the
workspace exposed to Docker. Disposable runs return a diff and remove the
temporary clone without creating a host branch. Agent workflows can opt into a
retained branch for pull request publication.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Protocol


class SandboxError(RuntimeError):
    """Raised when a sandbox cannot be prepared, run, or finalized."""


@dataclass(frozen=True, slots=True)
class SandboxConfig:
    """Runtime policy applied to every sandbox container."""

    image: str = "python:3.12-slim"
    agent_image: str | None = None
    dockerfile: str | None = None
    install_project: bool = True
    build_network: str = "default"
    network: str = "none"
    workdir: str = "/workspace"
    cpus: float | None = 2.0
    memory: str | None = "2g"
    pids_limit: int | None = 512
    user: str | None = None
    environment: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ContainerResult:
    """Observable result of a container process."""

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


@dataclass(frozen=True, slots=True)
class ExecutionSandbox:
    """Internal execution details for one isolated task."""

    task_id: str
    branch: str | None
    base_commit: str
    worktree: Path
    container_name: str


@dataclass(frozen=True, slots=True)
class SandboxResult:
    """Result returned after a sandbox has been finalized."""

    task_id: str
    branch: str | None
    base_commit: str
    exit_code: int
    stdout: str
    stderr: str
    diff: str
    changed_files: tuple[str, ...]
    timed_out: bool = False
    container_name: str = ""

    @property
    def succeeded(self) -> bool:
        """Whether the agent command completed successfully."""

        return self.exit_code == 0 and not self.timed_out


class ContainerRuntime(Protocol):
    """Runtime interface used by :class:`SandboxManager`."""

    def run(
        self,
        *,
        name: str,
        worktree: Path,
        command: Sequence[str],
        config: SandboxConfig,
        timeout: float | None,
    ) -> ContainerResult:
        """Run ``command`` with only ``worktree`` mounted into the container."""

    def prepare(
        self, *, name: str, worktree: Path, config: SandboxConfig
    ) -> SandboxConfig:
        """Build or otherwise prepare the project runtime image."""

    def cleanup(self, config: SandboxConfig) -> None:
        """Clean up runtime resources created by :meth:`prepare`."""


class DockerRuntime:
    """Docker implementation of the container runtime boundary."""

    def __init__(self, docker_bin: str = "docker") -> None:
        self.docker_bin = docker_bin

    def run(
        self,
        *,
        name: str,
        worktree: Path,
        command: Sequence[str],
        config: SandboxConfig,
        timeout: float | None,
    ) -> ContainerResult:
        """Run one ephemeral, resource-limited Docker container."""

        args = self.build_run_command(
            name=name,
            worktree=worktree,
            command=command,
            config=config,
        )
        try:
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError as error:
            raise SandboxError(
                f"Could not start Docker runtime '{self.docker_bin}': {error}"
            ) from error

        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            self._remove_container(name)
            timeout_message = f"Container timed out after {timeout} seconds"
            stderr = f"{stderr}\n{timeout_message}".strip()
            return ContainerResult(
                exit_code=124,
                stdout=stdout,
                stderr=stderr,
                timed_out=True,
            )

        return ContainerResult(
            exit_code=process.returncode,
            stdout=stdout,
            stderr=stderr,
        )

    def prepare(
        self, *, name: str, worktree: Path, config: SandboxConfig
    ) -> SandboxConfig:
        """Build a project image from the isolated clone when configured."""

        image = f"factory-sandbox-{name}"
        if not config.install_project:
            return config
        command = [
            self.docker_bin,
            "build",
            "--network",
            config.build_network,
            "--file",
            "-",
            "--tag",
            image,
            str(worktree),
        ]
        project_dockerfile = (
            worktree / config.dockerfile
            if config.dockerfile
            else worktree / "Dockerfile"
        )
        if config.agent_image is None and project_dockerfile.is_file():
            command[command.index("-")] = str(project_dockerfile)
            self._build_image(command, None)
            return replace(
                config,
                image=image,
                environment=self._project_environment(config.environment),
            )
        agent_stage = ""
        if config.agent_image:
            agent_stage = (
                "FROM "
                f"{config.agent_image} AS factory-agent\n"
                "FROM "
                f"{config.image}\n"
                "COPY --from=ghcr.io/astral-sh/uv:0.8.15 /uv /uvx /usr/local/bin/\n"
                "COPY --from=factory-agent "
                "/usr/local/bin/opencode /usr/local/bin/opencode\n"
            )
        base_dockerfile = (
            agent_stage
            if config.agent_image
            else (
                f"FROM {config.image}\n"
                "COPY --from=ghcr.io/astral-sh/uv:0.8.15 /uv /uvx /usr/local/bin/\n"
            )
        )
        dockerfile_input = (
            base_dockerfile + "WORKDIR /workspace\n"
            "COPY . .\n"
            "ENV UV_CACHE_DIR=/tmp/uv-cache\n"
            "ENV UV_PROJECT_ENVIRONMENT=/opt/factory-venv\n"
            "RUN if [ -f pyproject.toml ]; then "
            "uv sync --dev; fi\n"
            "RUN mkdir -p /tmp/uv-cache && "
            "chmod -R a+rwX /tmp/uv-cache /opt/factory-venv\n"
            "RUN printf '%s\\n' '#!/bin/sh' 'set -eu' "
            "'export PATH=/opt/factory-venv/bin:$PATH' 'exec \"$@\"' "
            "> /usr/local/bin/factory-entrypoint && "
            "chmod +x /usr/local/bin/factory-entrypoint\n"
            'ENTRYPOINT ["/usr/local/bin/factory-entrypoint"]\n'
        )

        self._build_image(command, dockerfile_input)
        return replace(
            config,
            image=image,
            environment=self._project_environment(config.environment),
        )

    def _build_image(self, command: list[str], dockerfile: str | None) -> bool:
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                input=dockerfile,
            )
        except OSError as error:
            raise SandboxError(f"Could not build sandbox image: {error}") from error
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip()
            raise SandboxError(f"Docker image build failed: {message}")
        return True

    @staticmethod
    def _project_environment(environment: Mapping[str, str]) -> dict[str, str]:
        environment = dict(environment)
        environment.setdefault("UV_CACHE_DIR", "/tmp/uv-cache")
        environment.setdefault("UV_NO_SYNC", "1")
        environment.setdefault("UV_PROJECT_ENVIRONMENT", "/opt/factory-venv")
        environment.setdefault(
            "PATH", "/opt/factory-venv/bin:/usr/local/bin:/usr/bin:/bin"
        )
        return environment

    def cleanup(self, config: SandboxConfig) -> None:
        """Remove a temporary image created by :meth:`prepare`."""

        if not config.image.startswith("factory-sandbox-"):
            return
        subprocess.run(
            [self.docker_bin, "image", "rm", "--force", config.image],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

    def build_run_command(
        self,
        *,
        name: str,
        worktree: Path,
        command: Sequence[str],
        config: SandboxConfig,
    ) -> list[str]:
        """Build the argument vector used for ``docker run``.

        The argument vector is intentionally exposed so callers can audit the
        isolation policy and tests can verify it without starting Docker.
        """

        if not config.image:
            raise SandboxError("A Docker image is required")
        if not config.workdir.startswith("/"):
            raise SandboxError("Container workdir must be an absolute path")
        if config.network == "host":
            raise SandboxError("Host networking is not allowed for sandboxes")

        user = config.user
        if user is None and hasattr(os, "getuid") and hasattr(os, "getgid"):
            user = f"{os.getuid()}:{os.getgid()}"

        args = [
            self.docker_bin,
            "run",
            "--rm",
            "--name",
            name,
            "--network",
            config.network,
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,nosuid,size=256m",
            "--workdir",
            config.workdir,
            "--mount",
            f"type=bind,source={worktree},target={config.workdir}",
        ]
        if user is not None:
            args.extend(["--user", user])
        if config.cpus is not None:
            args.extend(["--cpus", str(config.cpus)])
        if config.memory is not None:
            args.extend(["--memory", config.memory])
        if config.pids_limit is not None:
            args.extend(["--pids-limit", str(config.pids_limit)])
        for key, value in sorted(config.environment.items()):
            args.extend(["--env", f"{key}={value}"])

        args.append(config.image)
        args.extend(command)
        return args

    def _remove_container(self, name: str) -> None:
        """Best-effort cleanup after a Docker client timeout."""

        subprocess.run(
            [self.docker_bin, "rm", "--force", name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


class SandboxManager:
    """Create isolated Git workspaces and execute commands in Docker."""

    def __init__(
        self,
        repository: Path | str | None = None,
        *,
        config: SandboxConfig | None = None,
        runtime: ContainerRuntime | None = None,
        worktree_root: Path | str | None = None,
    ) -> None:
        self.repository = Path(repository or Path.cwd()).resolve()
        self.config = config or SandboxConfig()
        self.runtime = runtime or DockerRuntime()
        self._configured_worktree_root = (
            Path(worktree_root).resolve() if worktree_root is not None else None
        )
        self._temporary_worktree_root: Path | None = None

    def __enter__(self) -> SandboxManager:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        """Remove the manager-owned temporary worktree root."""

        if self._temporary_worktree_root is not None:
            shutil.rmtree(self._temporary_worktree_root, ignore_errors=True)
            self._temporary_worktree_root = None

    def run(
        self,
        task_id: str,
        command: Sequence[str],
        *,
        base_ref: str = "HEAD",
        timeout: float | None = None,
        config: SandboxConfig | None = None,
        persist_branch: bool = False,
    ) -> SandboxResult:
        """Run an agent task in an ephemeral container.

        The command receives a dedicated, self-contained Git workspace based on
        ``base_ref``. Changes are returned as a diff, while the primary
        repository worktree and its Git metadata are never mounted or edited.
        By default the run is disposable and creates no host branch. Set
        ``persist_branch`` when a caller needs to publish the changes later.
        """

        if not command:
            raise SandboxError("An agent command is required")

        runtime_config = self.config if config is None else config

        try:
            sandbox = self._prepare(task_id, base_ref, persist_branch)
        except BaseException:
            self.close()
            raise
        prepared_config = runtime_config
        try:
            prepare = getattr(self.runtime, "prepare", None)
            if prepare is not None:
                prepared_config = prepare(
                    name=sandbox.container_name,
                    worktree=sandbox.worktree,
                    config=runtime_config,
                )
            container_result: ContainerResult | None = None
            runtime_error: Exception | None = None
            try:
                container_result = self.runtime.run(
                    name=sandbox.container_name,
                    worktree=sandbox.worktree,
                    command=tuple(command),
                    config=prepared_config,
                    timeout=timeout,
                )
            except Exception as error:
                runtime_error = error

            try:
                self._commit_changes(sandbox, persist_branch)
                diff, changed_files = self._extract_changes(sandbox)
                if persist_branch and sandbox.branch is not None:
                    self._import_branch(sandbox)
            except Exception as error:
                if runtime_error is not None:
                    raise SandboxError(
                        "Sandbox failed and its changes could not be extracted: "
                        f"{error}"
                    ) from runtime_error
                raise

            if runtime_error is not None:
                raise runtime_error
            if container_result is None:  # pragma: no cover - defensive invariant
                raise SandboxError("Container runtime returned no result")

            return SandboxResult(
                task_id=sandbox.task_id,
                branch=sandbox.branch,
                base_commit=sandbox.base_commit,
                exit_code=container_result.exit_code,
                stdout=container_result.stdout,
                stderr=container_result.stderr,
                diff=diff,
                changed_files=changed_files,
                timed_out=container_result.timed_out,
                container_name=sandbox.container_name,
            )
        finally:
            self._remove_workspace(sandbox.worktree)
            self.close()
            cleanup = getattr(self.runtime, "cleanup", None)
            if cleanup is not None:
                cleanup(prepared_config)

    def _prepare(
        self, task_id: str, base_ref: str, persist_branch: bool
    ) -> ExecutionSandbox:
        self._validate_task_id(task_id)
        self._validate_repository()
        root = self._worktree_root()
        slug = self._slug(task_id)
        token = uuid.uuid4().hex[:12]
        branch = f"factory/{slug}-{token}" if persist_branch else None
        container_name = f"factory-{slug}-{token}"
        worktree = root / f"{slug}-{token}"
        base_commit = self._git(
            "rev-parse",
            "--verify",
            f"{base_ref}^{{commit}}",
        ).stdout.strip()
        try:
            self._git(
                "clone",
                "--no-local",
                "--no-hardlinks",
                "--no-checkout",
                str(self.repository),
                str(worktree),
            )
            if persist_branch:
                if branch is None:  # pragma: no cover - defensive invariant
                    raise SandboxError("Persistent sandbox is missing its branch name")
                self._git(
                    "checkout",
                    "--quiet",
                    "-b",
                    branch,
                    base_commit,
                    cwd=worktree,
                )
            else:
                self._git(
                    "checkout",
                    "--quiet",
                    "--detach",
                    base_commit,
                    cwd=worktree,
                )
            # The runtime only needs the workspace. Do not leave a remote that
            # points at the host repository inside the mounted clone.
            self._git(
                "remote",
                "remove",
                "origin",
                cwd=worktree,
            )
        except BaseException:
            self._remove_workspace(worktree)
            raise
        return ExecutionSandbox(
            task_id=task_id,
            branch=branch,
            base_commit=base_commit,
            worktree=worktree,
            container_name=container_name,
        )

    def _commit_changes(self, sandbox: ExecutionSandbox, persist_branch: bool) -> None:
        self._git("add", "--all", cwd=sandbox.worktree)
        staged = self._git(
            "diff",
            "--cached",
            "--quiet",
            cwd=sandbox.worktree,
            check=False,
        )
        if staged.returncode == 0:
            return
        if staged.returncode != 1:
            raise SandboxError(
                f"Could not inspect sandbox changes: {staged.stderr.strip()}"
            )
        self._git(
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "user.name=Factory Sandbox",
            "-c",
            "user.email=factory-sandbox@localhost",
            "commit",
            "--no-verify",
            "-m",
            f"Factory sandbox task: {sandbox.task_id}",
            cwd=sandbox.worktree,
        )

    def _extract_changes(
        self, sandbox: ExecutionSandbox
    ) -> tuple[str, tuple[str, ...]]:
        diff = self._git(
            "diff",
            "--no-ext-diff",
            "--binary",
            f"{sandbox.base_commit}..HEAD",
            cwd=sandbox.worktree,
        ).stdout
        files = self._git(
            "diff",
            "--name-only",
            f"{sandbox.base_commit}..HEAD",
            cwd=sandbox.worktree,
        ).stdout.splitlines()
        return diff, tuple(files)

    def _import_branch(self, sandbox: ExecutionSandbox) -> None:
        """Copy the isolated branch ref into the host repository."""

        self._git(
            "fetch",
            "--no-tags",
            str(sandbox.worktree),
            f"{sandbox.branch}:{sandbox.branch}",
        )

    def _validate_repository(self) -> None:
        if not self.repository.is_dir():
            raise SandboxError(f"Repository does not exist: {self.repository}")
        result = self._git("rev-parse", "--show-toplevel")
        git_root = Path(result.stdout.strip()).resolve()
        if git_root != self.repository:
            raise SandboxError(
                f"Repository path is not the Git worktree root: {self.repository}"
            )

    def _worktree_root(self) -> Path:
        if self._configured_worktree_root is not None:
            if self._configured_worktree_root == self.repository or (
                self.repository in self._configured_worktree_root.parents
            ):
                raise SandboxError(
                    "Sandbox workspace root must not be inside the repository"
                )
            self._configured_worktree_root.mkdir(parents=True, exist_ok=True)
            return self._configured_worktree_root
        if self._temporary_worktree_root is None:
            self._temporary_worktree_root = Path(
                tempfile.mkdtemp(prefix="factory-sandboxes-")
            )
        return self._temporary_worktree_root

    @staticmethod
    def _remove_workspace(worktree: Path) -> None:
        shutil.rmtree(worktree, ignore_errors=True)

    def _git(
        self,
        *args: str,
        cwd: Path | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=cwd or self.repository,
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as error:
            raise SandboxError(f"Could not execute Git: {error}") from error
        if check and result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip()
            raise SandboxError(f"Git {' '.join(args)} failed: {message}")
        return result

    @staticmethod
    def _slug(task_id: str) -> str:
        slug = re.sub(r"[^A-Za-z0-9._-]+", "-", task_id).strip("-._")
        return (slug or "task")[:40]

    @staticmethod
    def _validate_task_id(task_id: str) -> None:
        if not task_id.strip():
            raise SandboxError("Task ID must not be empty")
