from pathlib import Path
from datetime import datetime
import hashlib
import json

import yaml


REPO_ROOT = Path(__file__).parents[1]
SKILL_ROOT = REPO_ROOT / "skills" / "packaging-product-visuals"
EXAMPLE_ROOT = REPO_ROOT / "examples" / "fictional-pantry-product"
LEGACY_RECEIPTS_PATH = REPO_ROOT / "tests" / "evals" / "forward-receipts.yaml"


def _canonical_sha256(value):
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def test_skill_leads_with_the_reusable_product_to_delivery_process():
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    lower_skill = skill.lower()

    assert skill.index("## Core Workflow") < skill.index("## Runtime Safety")
    for required_phrase in (
        "product category",
        "audience and buying task",
        "package construction",
        "target specification",
        "same-category packaging",
        "audience aesthetics",
        "comparable packaging directions",
        "channel needs determine the asset roles",
    ):
        assert required_phrase in lower_skill

    assert "Do not generate packaging directions before this decision gate passes." in skill
    assert "ProjectState" in skill[skill.index("## Implementation Map") :]


def test_public_example_documents_product_research_and_decision_contracts():
    workflow = yaml.safe_load(
        (EXAMPLE_ROOT / "full-workflow.yaml").read_text(encoding="utf-8")
    )
    contracts = workflow["contracts"]
    product_brief = contracts["product_brief"]
    research_board = contracts["research_board"]
    option_matrix = contracts["packaging_option_matrix"]
    decision_lock = contracts["decision_lock"]

    assert product_brief["product"]["usage_occasions"]
    assert product_brief["product"]["audience"]["description"] != "unknown"
    starting_point = product_brief["package_starting_point"]
    assert starting_point["construction"] != "unknown"
    assert starting_point["target_specification"] != "unknown"
    assert starting_point["status"] == "working"

    assert {
        "same-category-packaging",
        "audience-aesthetics",
        "package-construction",
        "package-specification",
    } <= set(research_board["scope"]["dimensions"])
    assert len(option_matrix["options"]) >= 2
    assert option_matrix["alternatives_retained"]

    assert decision_lock["origin"] == "workflow"
    assert decision_lock["product_brief_id"] == product_brief["id"]
    assert decision_lock["research_board_id"] == research_board["id"]
    assert decision_lock["packaging_option_matrix_id"] == option_matrix["id"]
    assert decision_lock["import_source_id"] is None
    assert decision_lock["import_source_sha256"] is None
    assert decision_lock["unknown_fields"] == []
    assert decision_lock["unverified_fields"] == []
    assert {
        "category",
        "audience_task",
        "usage_task",
        "package_construction",
        "target_specification_range",
        "variant_ids",
        "exact_copy",
    } <= set(decision_lock["frozen_fields"])

    hashes = decision_lock["source_contract_hashes"]
    assert hashes["product_brief_sha256"] == _canonical_sha256(product_brief)
    assert hashes["research_board_sha256"] == _canonical_sha256(research_board)
    assert hashes["packaging_option_matrix_sha256"] == _canonical_sha256(option_matrix)


def test_public_example_labels_historical_directions_as_retrospective_evidence():
    workflow = yaml.safe_load(
        (EXAMPLE_ROOT / "full-workflow.yaml").read_text(encoding="utf-8")
    )
    evidence_scope = workflow["evidence_scope"]
    history = evidence_scope["historical_direction_artifacts"]
    decision_lock = workflow["contracts"]["decision_lock"]
    compare_receipt = next(
        receipt
        for receipt in yaml.safe_load(
            LEGACY_RECEIPTS_PATH.read_text(encoding="utf-8")
        )["receipts"]
        if receipt["id"] == history["receipt_id"]
    )
    successful_generation_times = [
        attempt["executed_at_utc"]
        for attempt in compare_receipt["generation_receipt"]["attempts"]
        if attempt["outcome"] == "passed"
    ]

    assert evidence_scope["evidence_type"] == (
        "retrospective-upstream-contract-reconstruction-plus-forward-ecommerce-delivery"
    )
    assert history["generated_before_decision_lock"] is True
    assert history["post_lock_direction_generation_proven"] is False
    assert history["successful_generation_times_utc"] == successful_generation_times
    assert history["decision_lock_approved_at_utc"] == decision_lock["approved_at_utc"]
    assert max(datetime.fromisoformat(value.replace("Z", "+00:00")) for value in successful_generation_times) < datetime.fromisoformat(
        decision_lock["approved_at_utc"].replace("Z", "+00:00")
    )
    assert evidence_scope["dated_forward_scope"] == [
        "selection-refinement",
        "ecommerce-planning",
        "ecommerce-generation",
        "qa-delivery",
    ]
    assert "does not prove" in evidence_scope["limitation"].lower()


def test_generic_ecommerce_probe_uses_only_channel_requested_roles():
    scenarios = yaml.safe_load(
        (REPO_ROOT / "tests" / "evals" / "full-workflow-scenarios.yaml").read_text(
            encoding="utf-8"
        )
    )["scenarios"]
    gallery = next(item for item in scenarios if item["id"] == "approved-package-gallery")
    full_chain = next(item for item in scenarios if item["id"] == "three-sku-full-chain")

    assert gallery["ecommerce_roles"] == ["catalog", "context", "channel-variant"]
    assert "all supported roles" not in gallery["request"].lower()
    assert full_chain["ecommerce_roles"] == []
