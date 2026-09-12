import json
import re
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).parents[1]
EXPECTED_CAPABILITIES = {
    "Product and packaging maturity routing",
    "Evidence-bounded packaging research",
    "Direction-by-SKU comparison and identity locks",
    "Ecommerce asset planning and role-specific handoffs",
    "Permission-aware delivery and QA",
    "Local bilingual review-pack preparation",
}
FORBIDDEN_INTERFACE_CLAIMS = {
    "hosted",
    "backend",
    "image generation",
    "image-generation",
    "generates images",
    "remote generation",
    "provider integration",
}


def _project_version():
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', pyproject, flags=re.MULTILINE)
    assert match
    return match.group(1)


def _interface_claims_are_bounded(interface):
    searchable = "\n".join(
        [
            interface["shortDescription"],
            interface["longDescription"],
            *interface["capabilities"],
            *interface["defaultPrompt"],
        ]
    ).lower()
    return set(interface["capabilities"]) == EXPECTED_CAPABILITIES and not any(
        token in searchable for token in FORBIDDEN_INTERFACE_CLAIMS
    )


def _public_manifest_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _public_manifest_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _public_manifest_strings(child)


def _manifest_claims_are_bounded(manifest):
    interface = manifest.get("interface", {})
    searchable = "\n".join(_public_manifest_strings(manifest)).lower()
    return (
        _interface_claims_are_bounded(interface)
        and not any(token in searchable for token in FORBIDDEN_INTERFACE_CLAIMS)
        and "local bilingual review-pack preparation" in searchable
        and "maturity routing" in searchable
    )


def _prompts_start_from_maturity(prompts):
    if len(prompts) != 3 or not all(
        "$packaging-product-visuals" in prompt for prompt in prompts
    ):
        return False
    normalized = [prompt.lower() for prompt in prompts]
    return (
        all(token in normalized[0] for token in ("product idea", "earliest incomplete", "definition", "research"))
        and all(token in normalized[1] for token in ("approved package identity", "ecommerce asset set"))
        and all(token in normalized[2] for token in ("correct", "existing package artifact", "locked identity"))
        and not any(
            token in "\n".join(normalized)
            for token in ("compare", "refine", "present", "neutral packshot")
        )
    )


def test_plugin_manifest_matches_release_contract():
    manifest_path = REPO_ROOT / ".codex-plugin" / "plugin.json"
    assert manifest_path.is_file(), "plugin manifest is not present"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["name"] == "packaging-product-visuals"
    assert manifest["version"] == _project_version() == "0.2.0"
    assert "stage-gated" in manifest["description"].lower()
    assert manifest["author"]["name"] == "feariangod"
    assert manifest["license"] == "Apache-2.0"
    assert manifest["skills"] == "./skills/"
    assert not ({"hooks", "apps", "mcpServers"} & manifest.keys())
    interface = manifest["interface"]
    assert interface["displayName"] == "Packaging Product Visuals"
    assert "packaging" in interface["shortDescription"].lower()
    assert "ecommerce" in interface["shortDescription"].lower()
    assert "maturity" in interface["longDescription"].lower()
    assert interface["developerName"] == "feariangod"
    assert interface["category"] == "Design"
    assert _interface_claims_are_bounded(interface)
    prompts = interface["defaultPrompt"]
    assert _prompts_start_from_maturity(prompts)

    mutation = json.loads(json.dumps(interface))
    mutation["capabilities"].append("Hosted image generation backend")
    assert not _interface_claims_are_bounded(mutation)


def test_plugin_claim_boundary_covers_every_public_manifest_string():
    manifest = json.loads(
        (REPO_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    assert _manifest_claims_are_bounded(manifest)

    description_mutation = json.loads(json.dumps(manifest))
    description_mutation["description"] += " Includes a hosted image generation backend."
    assert not _manifest_claims_are_bounded(description_mutation)

    keyword_mutation = json.loads(json.dumps(manifest))
    keyword_mutation["keywords"].append("image-generation-provider")
    assert not _manifest_claims_are_bounded(keyword_mutation)

    allowed_local_mutation = json.loads(json.dumps(manifest))
    allowed_local_mutation["keywords"].append("local-review-orchestration")
    assert _manifest_claims_are_bounded(allowed_local_mutation)


def test_openai_adapter_uses_explicit_skill_invocation():
    adapter_path = REPO_ROOT / "skills" / "packaging-product-visuals" / "agents" / "openai.yaml"
    assert adapter_path.is_file(), "Codex UI adapter is not present"
    adapter = yaml.safe_load(adapter_path.read_text(encoding="utf-8"))
    interface = adapter["interface"]
    prompt = interface["default_prompt"]
    assert interface["display_name"] == "Packaging Product Visuals"
    assert "packaging" in interface["short_description"].lower()
    assert "ecommerce" in interface["short_description"].lower()
    assert "$packaging-product-visuals" in prompt
    for phrase in ("earliest incomplete", "evidence", "permissions", "locks", "identity", "QA"):
        assert phrase.lower() in prompt.lower()
    assert adapter["policy"]["allow_implicit_invocation"] is True
