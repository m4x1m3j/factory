"""Factory command-line interface."""

from pathlib import Path

import typer

from factory.bootstrap import BootstrapError, ProjectBootstrapper

app = typer.Typer(
    name="factory",
    no_args_is_help=True,
    help="Build and operate AI software factories.",
)
project_app = typer.Typer(help="Manage target projects.")
app.add_typer(project_app, name="project")


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


@project_app.command("sync-assets")
def sync_project_assets(
    directory: Path | None = typer.Option(
        None,
        "--directory",
        "-d",
        help="Target project directory. Defaults to the current directory.",
    ),
    force: bool = typer.Option(
        True,
        "--force/--no-force",
        help="Overwrite generated asset files when they already exist.",
    ),
) -> None:
    """Synchronize shared agent assets into a target project."""

    project_dir = directory if directory is not None else Path.cwd()
    try:
        result = ProjectBootstrapper().sync_assets(project_dir, force=force)
    except BootstrapError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error

    typer.echo(
        f"Synchronized {len(result.written_files)} agent asset files in "
        f"{result.project_dir}"
    )


def main() -> None:
    """Run Factory CLI."""

    app()
