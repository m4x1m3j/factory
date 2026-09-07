"""Target project bootstrapping from project archetypes."""

from __future__ import annotations

import keyword
import re
from dataclasses import dataclass
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path


class BootstrapError(ValueError):
    """Raised when a target project cannot be initialized."""


@dataclass(frozen=True)
class Archetype:
    """A named project template available to the Project Bootstrapper."""

    name: str
    description: str
    resource: str


PROJECT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
PLACEHOLDER_PATTERN = re.compile(
    r"\{\{\s*(?P<name>project_name|package_name|archetype_name)\s*\}\}"
)


ARCHETYPES: dict[str, Archetype] = {
    "python": Archetype(
        name="python",
        description="Python project using uv, pytest, Ruff, and a container sandbox.",
        resource="python",
    ),
    "python-mlops": Archetype(
        name="python-mlops",
        description=(
            "Python MLOps project using uv, pytest, Ruff, and a container sandbox."
        ),
        resource="python",
    ),
}


class ProjectBootstrapper:
    """Create target project files from a registered archetype."""

    def __init__(self, archetypes: dict[str, Archetype] | None = None) -> None:
        self._archetypes = archetypes if archetypes is not None else ARCHETYPES

    def initialize(
        self,
        name: str,
        archetype: str,
        destination: Path | None = None,
    ) -> Path:
        """Initialize and return a new target project directory.

        Parameters
        ----------
        name:
            Project directory and package name. Names use letters, digits, dots,
            underscores, and hyphens, and must start with an alphanumeric
            character.
        archetype:
            Registered project archetype identifier.
        destination:
            Parent directory in which the target project is created.

        Raises
        ------
        BootstrapError
            If the name or archetype is invalid, or the target is not empty.
        """

        self._validate_name(name)
        destination = Path.cwd() if destination is None else destination
        template = self._archetypes.get(archetype)
        if template is None:
            available = ", ".join(sorted(self._archetypes))
            raise BootstrapError(
                f"Unknown archetype '{archetype}'. Available archetypes: {available}"
            )

        package_name = name.replace("-", "_").replace(".", "_")
        if not package_name.isidentifier() or keyword.iskeyword(package_name):
            raise BootstrapError(
                "Project name must produce a valid Python package name after "
                "replacing '-' and '.' with '_'."
            )

        project_dir = destination / name
        self._validate_target_directory(project_dir)

        context = {
            "project_name": name,
            "package_name": package_name,
            "archetype_name": archetype,
        }
        resource_dir = files("factory").joinpath(
            "resources", "archetypes", template.resource
        )
        for relative_path, content in self._resource_files(resource_dir):
            rendered_path = self._render(relative_path, context)
            file_path = project_dir / rendered_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(self._render(content, context), encoding="utf-8")

        return project_dir

    def list_archetypes(self) -> tuple[Archetype, ...]:
        """Return registered archetypes in stable name order."""

        return tuple(self._archetypes[name] for name in sorted(self._archetypes))

    @staticmethod
    def _resource_files(
        resource_dir: Traversable, relative_path: Path = Path()
    ) -> list[tuple[str, str]]:
        files_to_copy: list[tuple[str, str]] = []
        for resource in resource_dir.iterdir():
            resource_path = relative_path / resource.name
            if resource.is_dir():
                files_to_copy.extend(
                    ProjectBootstrapper._resource_files(resource, resource_path)
                )
            elif resource.is_file():
                files_to_copy.append(
                    (resource_path.as_posix(), resource.read_text(encoding="utf-8"))
                )
        return files_to_copy

    @staticmethod
    def _render(value: str, context: dict[str, str]) -> str:
        return PLACEHOLDER_PATTERN.sub(lambda match: context[match["name"]], value)

    @staticmethod
    def _validate_name(name: str) -> None:
        if not PROJECT_NAME_PATTERN.fullmatch(name):
            raise BootstrapError(
                "Project name must start with a letter or digit and contain "
                "only letters, digits, '.', '_' or '-'."
            )

    @staticmethod
    def _validate_target_directory(project_dir: Path) -> None:
        if project_dir.exists():
            if not project_dir.is_dir():
                raise BootstrapError(f"Target '{project_dir}' is not a directory")
            if any(project_dir.iterdir()):
                raise BootstrapError(f"Target directory '{project_dir}' is not empty")
        else:
            project_dir.mkdir(parents=True)
