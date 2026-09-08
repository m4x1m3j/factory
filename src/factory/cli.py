"""Factory command-line interface."""

import json
from pathlib import Path

import typer

from factory.bootstrap import BootstrapError, ProjectBootstrapper
from factory.sandbox import SandboxConfig, SandboxError, SandboxManager

app = typer.Typer(
    name="factory",
    no_args_is_help=True,
    help="Build and operate AI software factories.",
)
project_app = typer.Typer(help="Manage target projects.")
app.add_typer(project_app, name="project")
sandbox_app = typer.Typer(help="Run isolated agent sandboxes.")
app.add_typer(sandbox_app, name="sandbox")


@project_app.command("init")
def init_project(
    name: str = typer.Argument(help="Name of new target project."),
    archetype: str = typer.Option(
        ..., "--archetype", "-a", help="Project archetype to scaffold."
    ),
    directory: Path | None = typer.Option(
        None,
        "--directory",
        "-d",
        help="Parent directory in which to create the target project.",
    ),
) -> None:
    """Initialize target project from predefined archetype."""

    try:
        project_dir = ProjectBootstrapper().initialize(
            name=name,
            archetype=archetype,
            destination=directory if directory is not None else Path.cwd(),
        )
    except BootstrapError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error

    typer.echo(f"Initialized {archetype} project in {project_dir}")


@project_app.command("archetypes")
def list_archetypes() -> None:
    """List available project archetypes."""

    for archetype in ProjectBootstrapper().list_archetypes():
        typer.echo(f"{archetype.name}: {archetype.description}")


@sandbox_app.command("run")
def run_sandbox(
    task_id: str = typer.Argument(help="Task identifier for the disposable run."),
    command: list[str] = typer.Argument(
        ..., help="Command to execute in the sandbox container."
    ),
    repository: Path | None = typer.Option(
        None, "--repository", "-C", help="Git repository to isolate."
    ),
    base_ref: str = typer.Option("HEAD", "--base-ref", help="Git base revision."),
    image: str = typer.Option(
        "python:3.12-slim",
        "--image",
        help="Container image for the command.",
    ),
    timeout: float | None = typer.Option(None, "--timeout"),
    as_json: bool = typer.Option(False, "--json", help="Print structured output."),
) -> None:
    """Execute a command in a temporary Docker sandbox."""

    try:
        manager = SandboxManager(
            repository or Path.cwd(), config=SandboxConfig(image=image)
        )
        result = manager.run(task_id, command, base_ref=base_ref, timeout=timeout)
    except SandboxError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error

    payload = {
        "task_id": result.task_id,
        "branch": result.branch,
        "base_commit": result.base_commit,
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
        "changed_files": result.changed_files,
        "diff": result.diff,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo("Sandbox branch: none (disposable run)")
        typer.echo(f"Exit code: {result.exit_code}")
        if result.changed_files:
            typer.echo("Changed files: " + ", ".join(result.changed_files))
        if result.stdout:
            typer.echo(result.stdout, nl=False)
        if result.stderr:
            typer.echo(result.stderr, err=True, nl=False)
    if not result.succeeded:
        raise typer.Exit(code=1)


def main() -> None:
    """Run Factory CLI."""

    app()
