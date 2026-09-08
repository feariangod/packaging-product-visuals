from pathlib import Path
import hashlib
import json

import yaml


REPO_ROOT = Path(__file__).parents[1]
EXAMPLES_ROOT = REPO_ROOT / "examples" / "fictional-pantry-product"
PERMISSION_KEYS = {
    "confidentiality",
    "inspect_allowed",
    "external_processing_allowed",
    "derivative_allowed",
    "redistribution_allowed",
    "publication_allowed",
    "attribution_status",
    "attribution_text",
    "attribution_fulfilled",
}
PERMISSION_VALUES = {
    "confidentiality": {"public", "private", "restricted"},
    "inspect_allowed": {True, False, "unknown"},
    "external_processing_allowed": {True, False, "unknown"},
    "derivative_allowed": {True, False, "unknown"},
    "redistribution_allowed": {True, False, "unknown"},
    "publication_allowed": {True, False, "unknown"},
    "attribution_status": {"required", "not-required", "unknown"},
    "attribution_fulfilled": {True, False, "not-applicable", "unknown"},
}
BOUNDED_STATUSES = {"requested", "passed", "draft", "blocked", "missing"}


def _permission_objects(value):
    if isinstance(value, dict):
        if "permissions" in value:
            yield value["permissions"]
        for child in value.values():
            yield from _permission_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _permission_objects(child)


def _fixture_documents():
    return sorted(EXAMPLES_ROOT.glob("*.yaml"))


def test_all_public_yaml_fixtures_parse():
    documents = _fixture_documents()
    assert {path.name for path in documents} == {
        "asset-provenance.yaml",
        "brief-compare.yaml",
        "brief-present.yaml",
        "brief-refine.yaml",
        "reference-manifest.yaml",
    }
    for path in documents:
        assert yaml.safe_load(path.read_text(encoding="utf-8")) is not None
    routing_cases = REPO_ROOT / "tests" / "routing-cases.yaml"
    assert yaml.safe_load(routing_cases.read_text(encoding="utf-8"))["cases"]


def test_routing_cases_cover_each_mode_and_adjacent_negative():
    cases = yaml.safe_load((REPO_ROOT / "tests" / "routing-cases.yaml").read_text(encoding="utf-8"))["cases"]
    assert {case["expected_mode"] for case in cases if case["expected_scope"] == "in-scope"} == {
        "compare",
        "refine",
        "present",
    }
    negative_ids = {
        case["id"] for case in cases if case["expected_scope"] == "out-of-scope"
    }
    assert negative_ids == {
        "reference-research-negative",
        "prompt-only-negative",
        "generic-photography-negative",
        "logo-negative",
        "campaign-negative",
        "print-ready-negative",
        "manufacturing-negative",
        "competitor-copy-negative",
        "ambiguous-negative",
    }


def test_three_mode_briefs_are_independent_and_complete():
    briefs = {
        path.stem.removeprefix("brief-"): yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in EXAMPLES_ROOT.glob("brief-*.yaml")
    }
    assert set(briefs) == {"compare", "refine", "present"}
    assert {brief["mode"] for brief in briefs.values()} == set(briefs)
    for mode, brief in briefs.items():
        assert brief["product"]["product_name"] == "PPV Fixture Citrus Pantry Mix"
        assert brief["product_baseline"]["id"] == "fictional-pantry-baseline-v1"
        assert brief["requested_artifacts"]
        assert brief["output"]["delivery"] in {"relative-path", "artifact-handle"}
        assert brief["qa_plan"]["required_gate_ids"]
        assert brief["qa_plan"]["review_profiles"]
        assert isinstance(brief["channel"]["aspect_ratio"], str)
        assert ":" in brief["channel"]["aspect_ratio"]
        assert all(
            item["status"] in BOUNDED_STATUSES for item in brief["requested_artifacts"]
        ), mode
        assert brief["output"]["retention_policy"] == "preserve"

    assert len(briefs["compare"]["comparison_directions"]) in {2, 3}
    assert briefs["refine"]["selection_lock"]["locked_fields"]
    assert briefs["refine"]["correction"]["failure_class"]
    assert briefs["refine"]["selection_lock"]["approved_by"] is None
    assert briefs["present"]["selection_lock"]["approved_by"] is None
    assert briefs["present"]["presentation"]["permitted_changes"]


def test_static_fixtures_cannot_self_authorize_and_use_rfc6901_overrides():
    for path in EXAMPLES_ROOT.glob("brief-*.yaml"):
        brief = yaml.safe_load(path.read_text(encoding="utf-8"))
        authorization = brief["processing_policy"]["authorization"]
        assert authorization == {
            "authority": "none",
            "basis": None,
            "confirmed_at_utc": None,
        }
        for override in brief["processing_policy"]["field_overrides"]:
            assert set(override) == {"json_pointer", "permissions"}
            assert override["json_pointer"].startswith("/")


def test_refine_and_present_use_independent_owned_sources_and_no_readable_copy():
    refine = yaml.safe_load((EXAMPLES_ROOT / "brief-refine.yaml").read_text(encoding="utf-8"))
    present = yaml.safe_load((EXAMPLES_ROOT / "brief-present.yaml").read_text(encoding="utf-8"))

    assert refine["product_baseline"]["object_count"] == 1
    assert refine["product_baseline"]["sku_order"] == ["fixture-pouch"]
    assert refine["selection_lock"]["source_scope"] == "whole-artifact"
    assert refine["selection_lock"]["source_artifact_id"] == "refine-source"
    assert refine["exact_copy"]["readable_copy_required"] is False
    assert refine["exact_copy"]["required"] == []

    assert present["product_baseline"]["object_count"] == 1
    assert present["product_baseline"]["sku_order"] == ["fixture-pouch"]
    assert present["selection_lock"]["source_scope"] == "named-objects"
    assert present["selection_lock"]["source_artifact_id"] == "present-source"
    assert present["selection_lock"]["source_object_ids"] == ["fixture-pouch"]
    assert present["presentation"]["selected_skus"] == ["fixture-pouch"]
    assert present["presentation"]["target_object_count"] == 1
    assert present["exact_copy"]["readable_copy_required"] is False
    assert present["exact_copy"]["required"] == []


def test_public_contract_closes_authorization_lock_and_qa_ambiguities():
    contracts = (
        REPO_ROOT
        / "skills"
        / "packaging-product-visuals"
        / "references"
        / "contracts.md"
    ).read_text(encoding="utf-8")
    workflow = (
        REPO_ROOT
        / "skills"
        / "packaging-product-visuals"
        / "references"
        / "workflow.md"
    ).read_text(encoding="utf-8")
    rights = (
        REPO_ROOT
        / "skills"
        / "packaging-product-visuals"
        / "references"
        / "rights-and-privacy.md"
    ).read_text(encoding="utf-8")
    assert "is never authorization" in rights.lower()
    assert "RFC 6901" in contracts
    assert "recompute the source SHA-256" in contracts
    assert "requested_artifacts:" in contracts
    assert "normalized_contract:" in contracts
    assert "canonical-runtime-contract-json" in contracts
    assert "longest matching recorded ancestor" in contracts
    assert "correction:" in contracts
    assert "presentation:" in contracts
    assert "qa_plan:" in contracts
    assert "artifact-handle" in contracts
    assert "canonical UTF-8 JSON" in contracts
    assert "generation_receipt.executor_id" in contracts
    assert "reviewer_id" in contracts
    assert "must differ from `generation_receipt.executor_id`" in contracts
    assert "longest matching RFC 6901" in rights
    assert "host artifact handles" in rights
    assert "do not change an external provider's" in rights
    assert "recompute the source SHA-256" in workflow


def test_qa_plans_include_mode_minimums_and_canonical_hash_slot():
    shared = {
        "artifact-type",
        "object-count",
        "package-geometry",
        "exact-copy",
        "invented-claims",
        "reference-role",
        "channel-fit",
        "artifact-integrity",
    }
    additions = {
        "compare": {"direction-comparability"},
        "refine": {"selection-lock", "named-failure-correction"},
        "present": {"selection-lock", "presentation-lock"},
    }
    for mode in additions:
        brief = yaml.safe_load((EXAMPLES_ROOT / f"brief-{mode}.yaml").read_text(encoding="utf-8"))
        plan = brief["qa_plan"]
        assert shared | additions[mode] <= set(plan["required_gate_ids"])
        assert plan["review_profiles"] == ["full-resolution", "contain-thumbnail"]
        assert plan["independent_review_required"] is True
        canonical = json.dumps(
            {
                key: plan[key]
                for key in (
                    "required_gate_ids",
                    "review_profiles",
                    "independent_review_required",
                )
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        assert plan["sha256"] == hashlib.sha256(canonical).hexdigest()


def test_selection_locks_pin_the_owned_source_hash():
    provenance = {
        item["id"]: item
        for item in yaml.safe_load(
            (EXAMPLES_ROOT / "asset-provenance.yaml").read_text(encoding="utf-8")
        )["assets"]
    }
    for mode in ("refine", "present"):
        brief = yaml.safe_load((EXAMPLES_ROOT / f"brief-{mode}.yaml").read_text(encoding="utf-8"))
        lock = brief["selection_lock"]
        assert lock["source_artifact_sha256"] == provenance[
            lock["source_artifact_id"]
        ]["sha256"]


def test_every_permission_object_uses_common_schema():
    for path in _fixture_documents():
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        for permissions in _permission_objects(document):
            assert set(permissions) == PERMISSION_KEYS, path.name
            for key, allowed in PERMISSION_VALUES.items():
                assert permissions[key] in allowed, (path.name, key, permissions[key])
            if permissions["attribution_status"] == "not-required":
                assert permissions["attribution_fulfilled"] == "not-applicable"


def test_asset_provenance_records_owned_files_and_hashes():
    provenance = yaml.safe_load(
        (EXAMPLES_ROOT / "asset-provenance.yaml").read_text(encoding="utf-8")
    )["assets"]
    by_id = {item["id"]: item for item in provenance}
    assert {item["id"] for item in provenance} == {
        "refine-source",
        "present-source",
        "corner-marker-reference",
        "compare-direction-a",
        "compare-direction-b-attempt-01",
        "compare-direction-b",
        "refined-package-attempt-01",
        "refined-package",
        "ecommerce-packshot",
    }
    for item in provenance:
        asset = EXAMPLES_ROOT / item["locator"]
        assert asset.is_file()
        assert hashlib.sha256(asset.read_bytes()).hexdigest() == item["sha256"]
        assert item["visible_trademarks"] == "none"
        assert item["embedded_private_data"] is False
        assert item["attribution_status"] == "not-required"
        assert item["attribution_fulfilled"] == "not-applicable"
        if "source_asset_id" in item:
            assert item["source_sha256"] == by_id[item["source_asset_id"]]["sha256"]
        if "reference_asset_id" in item:
            assert item["reference_sha256"] == by_id[item["reference_asset_id"]]["sha256"]
