import json
from importlib.resources import files


def test_should_package_complete_shared_agent_asset_manifest() -> None:
    asset_root = files("factory").joinpath("resources", "agent_assets")
    manifest = json.loads(
        asset_root.joinpath("manifest.json").read_text(encoding="utf-8")
    )

    assert manifest["version"] == 1
    assert asset_root.joinpath(manifest["global_instructions"]).is_file()
    assert asset_root.joinpath(manifest["model_tiers"]).is_file()
    assert len(manifest["personas"]) == 5
    assert asset_root.joinpath(manifest["mcp_template"]).is_file()

    personas = [
        json.loads(asset_root.joinpath(path).read_text(encoding="utf-8"))
        for path in manifest["personas"]
    ]
    assert {persona["name"] for persona in personas} == {
        "development",
        "review",
        "security",
        "architecture",
        "product-management",
    }
    assert all(persona["tools"] == ["read", "write", "execute"] for persona in personas)


def test_should_define_portable_hook_and_mcp_templates() -> None:
    asset_root = files("factory").joinpath("resources", "agent_assets")

    pre_tool = json.loads(
        asset_root.joinpath("hooks", "pre-tool-use.json").read_text(encoding="utf-8")
    )
    post_tool = json.loads(
        asset_root.joinpath("hooks", "post-tool-use.json").read_text(encoding="utf-8")
    )
    mcp = json.loads(
        asset_root.joinpath("mcp", "github.json").read_text(encoding="utf-8")
    )

    assert pre_tool["event"] == "PreToolUse"
    assert post_tool["event"] == "PostToolUse"
    assert post_tool["command"] == "just fix"
    assert "just all" in asset_root.joinpath("hooks", "pre-commit").read_text(
        encoding="utf-8"
    )
    assert mcp["token_env"] == "GITHUB_TOKEN"
    assert mcp["server_token_env"] == "GITHUB_PERSONAL_ACCESS_TOKEN"
    assert mcp["package"] == "@modelcontextprotocol/server-github"
    assert mcp["opencode"] == {
        "type": "remote",
        "url": "https://api.githubcopilot.com/mcp/",
    }
