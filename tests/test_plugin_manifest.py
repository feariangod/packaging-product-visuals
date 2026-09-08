import json
from pathlib import Path


REPO_ROOT = Path(__file__).parents[1]


def test_plugin_manifest_matches_release_contract():
    manifest_path = REPO_ROOT / ".codex-plugin" / "plugin.json"
    assert manifest_path.is_file(), "plugin manifest is not present"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["name"] == "packaging-product-visuals"
    assert manifest["version"] == "0.1.0"
    assert manifest["description"]
    assert manifest["author"]["name"] == "feariangod"
    assert manifest["license"] == "Apache-2.0"
    assert manifest["skills"] == "./skills/"
    assert not ({"hooks", "apps", "mcpServers"} & manifest.keys())
    interface = manifest["interface"]
    assert interface["displayName"] == "Packaging Product Visuals"
    assert interface["shortDescription"]
    assert interface["longDescription"]
    assert interface["developerName"] == "feariangod"
    assert interface["category"] == "Design"
    assert interface["capabilities"]
    assert not {
        "Image generation",
        "Image editing",
        "Local artifact review",
    } & set(interface["capabilities"])
    assert "$packaging-product-visuals" in "\n".join(
        interface["defaultPrompt"]
    )


def test_openai_adapter_uses_explicit_skill_invocation():
    adapter_path = REPO_ROOT / "skills" / "packaging-product-visuals" / "agents" / "openai.yaml"
    assert adapter_path.is_file(), "Codex UI adapter is not present"
    text = adapter_path.read_text(encoding="utf-8")
    assert "$packaging-product-visuals" in text
    assert "display_name" in text
    assert "short_description" in text
