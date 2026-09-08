from pathlib import Path


REPO_ROOT = Path(__file__).parents[1]

REQUIRED_FILES = {
    ".codex-plugin/plugin.json",
    "skills/packaging-product-visuals/SKILL.md",
    "skills/packaging-product-visuals/agents/openai.yaml",
    "skills/packaging-product-visuals/references/contracts.md",
    "skills/packaging-product-visuals/references/workflow.md",
    "skills/packaging-product-visuals/references/rights-and-privacy.md",
    "skills/packaging-product-visuals/references/packaging-qa.md",
}


def test_required_skill_files_exist():
    missing = {path for path in REQUIRED_FILES if not (REPO_ROOT / path).is_file()}
    assert not missing, f"missing required package files: {sorted(missing)}"


def test_required_directories_are_named_for_installable_skill():
    skill_dir = REPO_ROOT / "skills" / "packaging-product-visuals"
    assert skill_dir.name == "packaging-product-visuals"
    assert skill_dir.is_dir()
