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
) -> None:
    """Initialize target project from predefined archetype."""

    try:
        project_dir = ProjectBootstrapper().initialize(
            name=name,
            archetype=archetype,
            destination=Path.cwd(),
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


def main() -> None:
    """Run Factory CLI."""

    app()
