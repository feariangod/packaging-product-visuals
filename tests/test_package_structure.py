from pathlib import Path


REPO_ROOT = Path(__file__).parents[1]

REQUIRED_FILES = {
    ".codex-plugin/plugin.json",
    "skills/packaging-product-visuals/SKILL.md",
    "skills/packaging-product-visuals/agents/openai.yaml",
    "skills/packaging-product-visuals/references/contracts.md",
    "skills/packaging-product-visuals/references/workflow.md",
    "skills/packaging-product-visuals/references/product-and-research.md",
    "skills/packaging-product-visuals/references/packaging-directions.md",
    "skills/packaging-product-visuals/references/ecommerce-assets.md",
    "skills/packaging-product-visuals/references/rights-and-privacy.md",
    "skills/packaging-product-visuals/references/packaging-qa.md",
    "skills/packaging-product-visuals/references/typography-system.md",
    "skills/packaging-product-visuals/references/package-master.md",
    "skills/packaging-product-visuals/scripts/prepare_package_master.py",
}
STAGE_IDS = (
    "product-definition",
    "research-options",
    "decision-freeze",
    "packaging-directions",
    "selection-refinement",
    "ecommerce-planning",
    "ecommerce-generation",
    "qa-delivery",
)


def test_required_skill_files_exist():
    missing = {path for path in REQUIRED_FILES if not (REPO_ROOT / path).is_file()}
    assert not missing, f"missing required package files: {sorted(missing)}"


def test_required_directories_are_named_for_installable_skill():
    skill_dir = REPO_ROOT / "skills" / "packaging-product-visuals"
    assert skill_dir.name == "packaging-product-visuals"
    assert skill_dir.is_dir()


def test_workflow_routes_from_the_earliest_incomplete_stage_through_decision_freeze():
    workflow_path = (
        REPO_ROOT
        / "skills"
        / "packaging-product-visuals"
        / "references"
        / "workflow.md"
    )
    workflow = workflow_path.read_text(encoding="utf-8")
    lowered = workflow.lower()

    assert "earliest incomplete stage" in workflow
    assert "route research-only" not in lowered
    assert "campaign, prepress" not in lowered
    for stage_id in STAGE_IDS:
        assert f"`{stage_id}`" in workflow
    assert "DecisionLock" in workflow
    assert "frozen fields" in workflow.lower()


def test_ecommerce_asset_reference_defines_all_supported_roles_and_identity_lock():
    asset_planning_path = (
        REPO_ROOT
        / "skills"
        / "packaging-product-visuals"
        / "references"
        / "ecommerce-assets.md"
    )
    assert asset_planning_path.is_file()
    asset_planning = asset_planning_path.read_text(encoding="utf-8")

    for role in (
        "catalog",
        "detail",
        "usage",
        "specification",
        "context",
        "campaign",
        "channel-variant",
    ):
        assert f"`{role}`" in asset_planning
    assert "package identity" in asset_planning.lower()


def test_skill_uses_maturity_routing_and_keeps_operational_boundaries():
    skill = (
        REPO_ROOT / "skills" / "packaging-product-visuals" / "SKILL.md"
    ).read_text(encoding="utf-8").lower()

    assert "## select a mode" not in skill
    assert "earliest incomplete stage" in skill
    assert "route research-only" not in skill
    assert "campaign art" not in skill
    assert "campaign" in skill
    assert "media buying" in skill
    assert "influencer operations" in skill


def test_workflow_imports_approved_packages_and_legacy_present_fail_closed():
    workflow = (
        REPO_ROOT
        / "skills"
        / "packaging-product-visuals"
        / "references"
        / "workflow.md"
    ).read_text(encoding="utf-8")

    assert "imported-approved-package" in workflow
    assert "catalog" in workflow
    assert "stop at `ecommerce-planning`" in workflow
    assert "must not expand" in workflow
    assert "legacy receipt" in workflow.lower()


def test_qa_reference_restores_single_image_checks_and_profile_cardinality():
    qa = (
        REPO_ROOT
        / "skills"
        / "packaging-product-visuals"
        / "references"
        / "packaging-qa.md"
    ).read_text(encoding="utf-8")

    assert "`product-anatomy`" in qa
    assert "`visual-hierarchy-identity`" in qa
    assert "profile_id" in qa
    assert "full-resolution" in qa
    assert "named-profile" in qa
    assert "cross-set" in qa
