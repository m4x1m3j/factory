import json
from pathlib import Path

import pytest

from factory.assets import AssetContext, AssetSyncError, AssetSynchronizer, AssetWriter


class MarkerAssetProvider:
    """Test provider used to verify provider orchestration is extensible."""

    name = "marker"

    def write_assets(self, context: AssetContext, write: AssetWriter) -> None:
        write("marker.txt", f"{len(context.personas)} personas\n")


def test_should_compile_copilot_and_opencode_assets(tmp_path: Path) -> None:
    result = AssetSynchronizer().synchronize(
        tmp_path,
        model_mapping={"code_generation": "openai/gpt-5"},
    )

    assert result.project_dir == tmp_path.resolve()
    assert (tmp_path / ".github/copilot-instructions.md").is_file()
    assert (tmp_path / ".github/agents/development.agent.md").is_file()
    assert (tmp_path / ".opencode/agents/security.md").is_file()
    assert (tmp_path / ".opencode/skills/task-done/SKILL.md").is_file()
    assert (tmp_path / ".githooks/pre-commit").stat().st_mode & 0o111
    opencode_plugin = tmp_path / ".opencode/plugins/factory-hooks.js"
    assert opencode_plugin.is_file()
    plugin = opencode_plugin.read_text(encoding="utf-8")
    assert '"tool.execute.before"' in plugin
    assert '"tool.execute.after"' in plugin
    assert "rtk ${command}" in plugin
    assert "just fix" in plugin

    opencode_agent = (tmp_path / ".opencode/agents/development.md").read_text(
        encoding="utf-8"
    )
    assert "tools:" not in opencode_agent
    assert "permission:\n  read: allow\n  edit: allow\n  bash: allow" in (
        opencode_agent
    )

    copilot = (tmp_path / ".github/agents/development.agent.md").read_text(
        encoding="utf-8"
    )
    assert "model: openai/gpt-5" in copilot
    assert "Implement the requested behavior" in copilot

    mcp = json.loads((tmp_path / ".vscode/mcp.json").read_text(encoding="utf-8"))
    assert mcp["servers"]["github"]["env"] == {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${env:GITHUB_TOKEN}"
    }

    opencode = json.loads((tmp_path / "opencode.json").read_text(encoding="utf-8"))
    assert opencode["agent"]["review"]["model"] == "reasoning"
    assert opencode["mcp"]["github"] == {
        "type": "remote",
        "url": "https://api.githubcopilot.com/mcp/",
        "headers": {"Authorization": "Bearer {env:GITHUB_TOKEN}"},
    }


def test_should_read_model_mapping_from_project_config(tmp_path: Path) -> None:
    config = tmp_path / ".factory/config.yaml"
    config.parent.mkdir()
    config.write_text(
        "agents:\n  models:\n    reasoning: anthropic/claude\n", encoding="utf-8"
    )

    AssetSynchronizer().sync(tmp_path)

    review = (tmp_path / ".opencode/agents/review.md").read_text(encoding="utf-8")
    assert "model: anthropic/claude" in review


def test_should_allow_custom_asset_provider_without_changing_synchronizer(
    tmp_path: Path,
) -> None:
    AssetSynchronizer(providers=(MarkerAssetProvider(),)).synchronize(tmp_path)

    assert (tmp_path / "marker.txt").read_text(encoding="utf-8") == "5 personas\n"
    assert (tmp_path / "AGENTS.md").is_file()
    assert not (tmp_path / ".github").exists()
    assert not (tmp_path / ".opencode").exists()


def test_should_reject_existing_generated_file_without_force(tmp_path: Path) -> None:
    target = tmp_path / ".github/copilot-instructions.md"
    target.parent.mkdir(parents=True)
    target.write_text("keep me", encoding="utf-8")

    with pytest.raises(AssetSyncError, match="Refusing to overwrite"):
        AssetSynchronizer().synchronize(tmp_path, force=False)

    assert target.read_text(encoding="utf-8") == "keep me"
