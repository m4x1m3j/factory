"""Compile shared agent assets into supported harness configurations."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any, Protocol


class AssetSyncError(ValueError):
    """Raised when shared assets cannot be synchronized safely."""


@dataclass(frozen=True, slots=True)
class AssetSyncResult:
    """Files written by one asset synchronization run."""

    project_dir: Path
    written_files: tuple[Path, ...]


class AssetWriter(Protocol):
    """Callback used by providers to write generated files."""

    def __call__(
        self, relative_path: str, content: str, *, executable: bool = False
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class AssetContext:
    """Canonical inputs shared with each harness-specific asset provider."""

    skills: tuple[tuple[str, str], ...]
    global_instructions: str
    personas: tuple[Mapping[str, Any], ...]
    models: Mapping[str, str]
    mcp: Mapping[str, Any]
    read_json: Callable[[str], dict[str, Any]]
    opencode_plugin: str


class AssetProvider(Protocol):
    """Harness-specific compiler for canonical shared assets."""

    name: str

    def write_assets(self, context: AssetContext, write: AssetWriter) -> None: ...


class GitHubAssetProvider:
    """Compile canonical assets for GitHub Copilot and VS Code."""

    name = "github"

    def write_assets(self, context: AssetContext, write: AssetWriter) -> None:
        for relative_path, content in context.skills:
            write(f".github/{relative_path}", content)

        write(
            ".github/copilot-instructions.md",
            _render_instructions(context.global_instructions, context.personas),
        )
        for persona in context.personas:
            name = str(persona["name"])
            model = context.models.get(str(persona["model_tier"]), "")
            write(
                f".github/agents/{name}.agent.md",
                _render_github_agent(persona, context.global_instructions, model),
            )

        for hook_path, event in (
            ("hooks/pre-tool-use.json", "PreToolUse"),
            ("hooks/post-tool-use.json", "PostToolUse"),
        ):
            hook = context.read_json(hook_path)
            hook_event = str(hook.pop("event", event))
            write(
                f".github/hooks/{hook_path.rsplit('/', 1)[-1]}",
                json.dumps({"hooks": {hook_event: [hook]}}, indent=2) + "\n",
            )

        package = str(context.mcp["package"])
        token_env = str(context.mcp["token_env"])
        server_token_env = str(context.mcp.get("server_token_env", token_env))
        write(
            ".vscode/mcp.json",
            json.dumps(
                {
                    "servers": {
                        str(context.mcp["name"]): {
                            "command": "npx",
                            "args": ["-y", package],
                            "env": {server_token_env: f"${{env:{token_env}}}"},
                        }
                    }
                },
                indent=2,
            )
            + "\n",
        )


class OpenCodeAssetProvider:
    """Compile canonical assets for OpenCode."""

    name = "opencode"

    def write_assets(self, context: AssetContext, write: AssetWriter) -> None:
        for relative_path, content in context.skills:
            write(f".opencode/{relative_path}", content)

        for persona in context.personas:
            name = str(persona["name"])
            model = context.models.get(str(persona["model_tier"]), "")
            write(
                f".opencode/agents/{name}.md",
                _render_opencode_agent(persona, context.global_instructions, model),
            )

        write(".opencode/plugins/factory-hooks.js", context.opencode_plugin)
        write(
            "opencode.json",
            json.dumps(
                {
                    "$schema": "https://opencode.ai/config.json",
                    "mcp": {str(context.mcp["name"]): self._mcp_config(context)},
                    "agent": {
                        str(persona["name"]): {
                            "description": str(persona["description"]),
                            "model": context.models.get(str(persona["model_tier"]), ""),
                            "prompt": str(persona["prompt"]),
                            "permission": {
                                "read": "allow",
                                "edit": "allow",
                                "bash": "allow",
                            },
                        }
                        for persona in context.personas
                    },
                },
                indent=2,
            )
            + "\n",
        )

    @staticmethod
    def _mcp_config(context: AssetContext) -> dict[str, Any]:
        package = str(context.mcp["package"])
        token_env = str(context.mcp["token_env"])
        server_token_env = str(context.mcp.get("server_token_env", token_env))
        opencode_mcp = context.mcp.get("opencode")
        if not isinstance(opencode_mcp, dict):
            return {
                "type": "local",
                "command": ["npx", "-y", package],
                "environment": {server_token_env: f"{{env:{token_env}}}"},
            }

        config = dict(opencode_mcp)
        config["headers"] = {"Authorization": f"Bearer {{env:{token_env}}}"}
        return config


def _render_instructions(
    global_instructions: str, personas: Sequence[Mapping[str, Any]]
) -> str:
    sections = [global_instructions.rstrip(), "", "## Agent Personas", ""]
    for persona in personas:
        sections.extend(
            [
                f"### {persona['display_name']}",
                str(persona["prompt"]),
                "",
            ]
        )
    return "\n".join(sections)


def _render_github_agent(
    persona: Mapping[str, Any], global_instructions: str, model: str
) -> str:
    tools = ", ".join(str(tool) for tool in persona["tools"])
    return (
        "---\n"
        f"name: {persona['name']}\n"
        f"description: {persona['description']}\n"
        f"tools: {tools}\n"
        f"model: {model}\n"
        "---\n\n"
        f"{global_instructions.rstrip()}\n\n"
        f"## Persona\n{persona['prompt']}\n"
    )


def _render_opencode_agent(
    persona: Mapping[str, Any], global_instructions: str, model: str
) -> str:
    tool_permissions = {"read": "read", "write": "edit", "execute": "bash"}
    permissions = "\n".join(
        f"  {tool_permissions[str(tool)]}: allow" for tool in persona["tools"]
    )
    return (
        "---\n"
        f"name: {persona['name']}\n"
        f"description: {persona['description']}\n"
        f"model: {model}\n"
        "permission:\n"
        f"{permissions}\n"
        "---\n\n"
        f"{global_instructions.rstrip()}\n\n"
        f"## Persona\n{persona['prompt']}\n"
    )


class AssetSynchronizer:
    """Load canonical assets and delegate compilation to providers."""

    _default_models = {
        "reasoning": "reasoning",
        "code_generation": "code_generation",
        "fast_triage": "fast_triage",
    }

    def __init__(
        self,
        resource_dir: Traversable | None = None,
        *,
        providers: Sequence[AssetProvider] | None = None,
    ) -> None:
        self._resource_dir = resource_dir or files("factory").joinpath(
            "resources", "agent_assets"
        )
        self._providers = (
            tuple(providers)
            if providers is not None
            else (
                GitHubAssetProvider(),
                OpenCodeAssetProvider(),
            )
        )

    def synchronize(
        self,
        project_dir: Path | str,
        *,
        force: bool = True,
        model_mapping: Mapping[str, str] | None = None,
    ) -> AssetSyncResult:
        """Write all harness configurations into ``project_dir``.

        Existing generated paths are overwritten by default. Set ``force`` to
        false to make accidental overwrites an explicit error.
        """

        project_path = Path(project_dir).resolve()
        if project_path.exists() and not project_path.is_dir():
            raise AssetSyncError(f"Project path is not a directory: {project_path}")
        project_path.mkdir(parents=True, exist_ok=True)

        manifest = self._load_json("manifest.json")
        global_instructions = self._read_text(str(manifest["global_instructions"]))
        personas = [self._load_persona(str(path)) for path in manifest["personas"]]
        models = self._load_models(str(manifest["model_tiers"]))
        resolved_models = dict(self._default_models)
        resolved_models.update(
            {
                name: str(value["default"])
                for name, value in models.get("tiers", {}).items()
                if isinstance(value, dict) and isinstance(value.get("default"), str)
            }
        )
        resolved_models.update(self._project_model_mapping(project_path))
        if model_mapping is not None:
            resolved_models.update(model_mapping)

        written: list[Path] = []

        def write(
            relative_path: str, content: str, *, executable: bool = False
        ) -> None:
            path = project_path / relative_path
            if path.exists() and path.is_dir():
                raise AssetSyncError(f"Cannot overwrite directory: {path}")
            if path.exists() and not force:
                raise AssetSyncError(f"Refusing to overwrite existing file: {path}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            if executable:
                path.chmod(path.stat().st_mode | 0o111)
            written.append(path)

        mcp = self._load_json(str(manifest["mcp_template"]))
        context = AssetContext(
            skills=tuple(self._skill_files(str(manifest["skills_directory"]))),
            global_instructions=global_instructions,
            personas=tuple(personas),
            models=resolved_models,
            mcp=mcp,
            read_json=self._load_json,
            opencode_plugin=self._read_text(str(manifest["opencode_plugin"])),
        )
        for provider in self._providers:
            provider.write_assets(context, write)

        write("AGENTS.md", _render_instructions(global_instructions, personas))
        write(
            ".githooks/pre-commit",
            self._read_text("hooks/pre-commit"),
            executable=True,
        )

        return AssetSyncResult(project_dir=project_path, written_files=tuple(written))

    def sync(
        self,
        project_dir: Path | str,
        *,
        force: bool = True,
        model_mapping: Mapping[str, str] | None = None,
    ) -> AssetSyncResult:
        """Alias for :meth:`synchronize`."""

        return self.synchronize(project_dir, force=force, model_mapping=model_mapping)

    def _load_json(self, relative_path: str) -> dict[str, Any]:
        value = json.loads(self._read_text(relative_path))
        if not isinstance(value, dict):
            raise AssetSyncError(f"Asset must contain a JSON object: {relative_path}")
        return value

    def _read_text(self, relative_path: str) -> str:
        resource = self._resource_dir.joinpath(*relative_path.split("/"))
        if not resource.is_file():
            raise AssetSyncError(f"Missing shared asset: {relative_path}")
        return resource.read_text(encoding="utf-8")

    def _skill_files(self, relative_path: str) -> list[tuple[str, str]]:
        root = self._resource_dir.joinpath(*relative_path.split("/"))
        if not root.is_dir():
            raise AssetSyncError(f"Missing skills directory: {relative_path}")
        return self._resource_files(root, Path(relative_path))

    @classmethod
    def _resource_files(
        cls, resource_dir: Traversable, relative_path: Path
    ) -> list[tuple[str, str]]:
        result: list[tuple[str, str]] = []
        for resource in sorted(resource_dir.iterdir(), key=lambda item: item.name):
            resource_path = relative_path / resource.name
            if resource.is_dir():
                result.extend(cls._resource_files(resource, resource_path))
            elif resource.is_file():
                result.append(
                    (resource_path.as_posix(), resource.read_text(encoding="utf-8"))
                )
        return result

    def _load_persona(self, relative_path: str) -> dict[str, Any]:
        persona = self._load_json(relative_path)
        for field in ("name", "description", "model_tier", "prompt"):
            if not isinstance(persona.get(field), str) or not persona[field]:
                raise AssetSyncError(
                    f"Persona field is missing: {relative_path}#{field}"
                )
        if not isinstance(persona.get("tools"), list):
            raise AssetSyncError(f"Persona tools are missing: {relative_path}")
        return persona

    def _load_models(self, relative_path: str) -> dict[str, Any]:
        models = self._load_json(relative_path)
        if not isinstance(models.get("tiers"), dict):
            raise AssetSyncError(f"Model tiers are missing: {relative_path}")
        return models

    @staticmethod
    def _project_model_mapping(project_dir: Path) -> dict[str, str]:
        """Read simple model tier mappings from the project's YAML config."""

        config_path = project_dir / ".factory" / "config.yaml"
        if not config_path.is_file():
            return {}

        mappings: dict[str, str] = {}
        in_models = False
        section_indent = 0
        pattern = re.compile(
            r"^(?P<indent>\s+)(?P<tier>reasoning|code_generation|fast_triage):\s*(?P<value>[^#]+)"
        )
        for line in config_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            indent = len(line) - len(line.lstrip())
            if stripped in {"models:", "model_tiers:"}:
                in_models = True
                section_indent = indent
                continue
            if in_models and stripped and indent <= section_indent:
                in_models = False
            if not in_models:
                continue
            match = pattern.match(line)
            if match:
                mappings[match["tier"]] = match["value"].strip().strip("'\"")
        return mappings
