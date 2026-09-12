from pathlib import Path
from collections import Counter
import hashlib
import json

from PIL import Image
import yaml


REPO_ROOT = Path(__file__).parents[1]
EXAMPLES_ROOT = REPO_ROOT / "examples" / "fictional-pantry-product"
FULL_WORKFLOW_PATH = EXAMPLES_ROOT / "full-workflow.yaml"
CONCEPT_DECISION_PATH = EXAMPLES_ROOT / "fictional-concept-decision.yaml"
DELIVERY_MANIFEST_PATH = EXAMPLES_ROOT / "delivery-manifest.yaml"
FORWARD_AUTHORIZATION_PATH = (
    EXAMPLES_ROOT / "forward-authorization-2026-09-09.yaml"
)
FINAL_AUTHORIZATION_PATH = (
    EXAMPLES_ROOT / "final-build-authorization-2026-09-09.yaml"
)
GENERATION_RECEIPT_PATH = (
    EXAMPLES_ROOT / "generation-receipt-v0.2-2026-09-09.yaml"
)
QA_RESULT_PATH = EXAMPLES_ROOT / "qa-result-v0.2-2026-09-09.yaml"
RUNTIME_RECEIPT_PATH = (
    EXAMPLES_ROOT / "runtime-receipt-v0.2-2026-09-09.yaml"
)
V02_GALLERY_ROOT = EXAMPLES_ROOT / "generated" / "v0.2" / "2026-09-09"
V02_REVIEW_ROOT = EXAMPLES_ROOT / "review" / "v0.2" / "2026-09-09"
LEGACY_FORWARD_RECEIPTS_PATH = REPO_ROOT / "tests" / "evals" / "forward-receipts.yaml"
FULL_WORKFLOW_SCENARIOS_PATH = (
    REPO_ROOT / "tests" / "evals" / "full-workflow-scenarios.yaml"
)
V02_CONTRACT_CASES_PATH = (
    REPO_ROOT / "tests" / "evals" / "v0.2-contract-cases.yaml"
)
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
FULL_WORKFLOW_SCENARIO_KEYS = {
    "id",
    "request",
    "expected_start_stage",
    "expected_scope_end_stage",
    "active_stage_outputs",
    "ecommerce_roles",
    "prohibited_claims",
}
ECOMMERCE_ROLES = {
    "catalog",
    "detail",
    "usage",
    "specification",
    "context",
    "campaign",
    "channel-variant",
}
STAGE_IDS = {
    "product-definition",
    "research-options",
    "decision-freeze",
    "packaging-directions",
    "selection-refinement",
    "ecommerce-planning",
    "ecommerce-generation",
    "qa-delivery",
}
V02_CONTRACTS = {
    "ProjectState",
    "ProductBrief",
    "ResearchBoard",
    "PackagingOptionMatrix",
    "DecisionLock",
    "SeriesSystem",
    "PackagingDirectionSet",
    "SelectionLock",
    "EcommerceAssetPlan",
    "AssetBrief",
    "DeliveryManifest",
    "RuntimeReceipt",
}


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


def _resolve_field_permissions(processing_policy, json_pointer):
    matches = [
        override
        for override in processing_policy["field_overrides"]
        if json_pointer == override["json_pointer"]
        or json_pointer.startswith(f'{override["json_pointer"]}/')
    ]
    if not matches:
        return processing_policy["default_permissions"], "run-default"

    longest = max(len(item["json_pointer"].split("/")) for item in matches)
    winners = [
        item for item in matches if len(item["json_pointer"].split("/")) == longest
    ]
    assert len(winners) == 1, f"conflicting permission overrides for {json_pointer}"
    return winners[0]["permissions"], "field-override"


def _v02_contract_cases():
    return yaml.safe_load(V02_CONTRACT_CASES_PATH.read_text(encoding="utf-8"))


def _is_sha256(value):
    return isinstance(value, str) and len(value) == 64 and set(value) <= set("0123456789abcdef")


def _trusted_approval_is_bound(item, sources):
    if item["approved_by"] != "trusted-record":
        return item["approved_by"] is None
    source = sources.get(item["approval_source_id"])
    return (
        source is not None
        and item["approval_record_id"] in source["record_ids"]
        and item["approval_basis"].strip()
    )


def _approved_items_resolve(items, selected_ids):
    by_id = {item["id"]: item for item in items}
    if len(by_id) != len(items) or len(set(selected_ids)) != len(selected_ids):
        return False
    for item_id in selected_ids:
        item = by_id.get(item_id)
        if not item or item["value"] == "unknown" or item["approval_state"] != "approved":
            return False
        if not item["source_id"] or not item["approved_by"] or not item["approval_basis"]:
            return False
    return True


def _decision_lock_is_valid(lock):
    decision_fields = {
        "category",
        "audience_task",
        "usage_task",
        "package_construction",
        "target_specification_range",
    }
    unknown_fields = set(lock["unknown_fields"])
    unverified_fields = set(lock["unverified_fields"])
    value_unknowns = {field for field in decision_fields if lock[field] == "unknown"}
    if value_unknowns != unknown_fields:
        return False
    if (unknown_fields | unverified_fields) & set(lock["frozen_fields"]):
        return False
    if (unknown_fields | unverified_fields) & set(lock["verified_prompt_fact_fields"]):
        return False
    if not _approved_items_resolve(lock["claim_items"], lock["claim_item_ids"]):
        return False
    if not _approved_items_resolve(lock["exact_copy_items"], lock["exact_copy_item_ids"]):
        return False

    hashes = lock["source_contract_hashes"]
    if hashes.get("hash_basis") != "canonical-sorted-compact-utf8-json":
        return False
    if lock["origin"] == "workflow":
        if unknown_fields or unverified_fields:
            return False
        upstream_ids = (
            lock["product_brief_id"],
            lock["research_board_id"],
            lock["packaging_option_matrix_id"],
        )
        upstream_hashes = (
            hashes["product_brief_sha256"],
            hashes["research_board_sha256"],
            hashes["packaging_option_matrix_sha256"],
        )
        return (
            all(upstream_ids)
            and all(_is_sha256(value) for value in upstream_hashes)
            and lock["import_source_id"] is None
            and lock["import_source_sha256"] is None
        )
    if lock["origin"] == "imported-approved-package":
        upstream_ids = (
            lock["product_brief_id"],
            lock["research_board_id"],
            lock["packaging_option_matrix_id"],
        )
        upstream_hashes = (
            hashes["product_brief_sha256"],
            hashes["research_board_sha256"],
            hashes["packaging_option_matrix_sha256"],
        )
        return (
            all(value is None for value in upstream_ids)
            and all(value is None for value in upstream_hashes)
            and bool(lock["import_source_id"])
            and _is_sha256(lock["import_source_sha256"])
        )
    return False


def _non_rendering_receipt_is_valid(receipt):
    if receipt["requested_artifact_ids"] or receipt["artifacts"]:
        return False
    if any(receipt[key] is not None for key in ("generation_receipt", "qa_plan", "qa")):
        return False
    if receipt["status"] == "passed":
        return all(item["status"] == "passed" for item in receipt["stage_outputs"]) and all(
            check["status"] == "pass"
            for check in receipt["stage_checks"]
            if check["required"]
        )
    return True


def _artifact_join_is_valid(case):
    requested_ids = case["requested_artifact_ids"]
    artifacts = case["artifacts"]
    if len(set(requested_ids)) != len(requested_ids):
        return False
    if Counter(item["requested_artifact_id"] for item in artifacts) != Counter(requested_ids):
        return False
    produced_ids = [item["artifact_id"] for item in artifacts if item["artifact_id"]]
    if len(set(produced_ids)) != len(produced_ids):
        return False
    for item in artifacts:
        if item["status"] in {"passed", "draft"}:
            if not item["artifact_id"] or not item["locator"] or not item["locator_type"]:
                return False
        elif item["status"] in {"blocked", "missing"}:
            if any(item[key] is not None for key in ("artifact_id", "locator", "locator_type", "sha256")):
                return False
        else:
            return False
    return True


def _qa_cardinality_is_valid(case):
    profiles = case["review_profiles"]
    profile_ids = [profile["profile_id"] for profile in profiles]
    if len(profile_ids) != len(set(profile_ids)):
        return False
    required_profiles = [profile for profile in profiles if profile["required"]]
    full = [profile for profile in required_profiles if profile["profile_scope"] == "full-resolution"]
    if len(full) != 1 or full[0]["profile_id"] != "full-resolution":
        return False

    expected = []
    for requested_id in case["requested_artifact_ids"]:
        for gate_id in case["required_gate_ids"]:
            for profile in required_profiles:
                expected.append(
                    (gate_id, requested_id, profile["profile_scope"], profile["profile_id"])
                )
    expected.extend(
        (gate_id, None, "cross-set", "cross-set")
        for gate_id in case["cross_set_required_gate_ids"]
    )
    actual = [
        (
            gate["gate_id"],
            gate["requested_artifact_id"],
            gate["profile_scope"],
            gate["profile_id"],
        )
        for gate in case["gates"]
    ]
    return Counter(actual) == Counter(expected) and all(gate["status"] == "pass" for gate in case["gates"])


def _matrix_is_selection_eligible(case):
    expected_pairs = {
        (direction_id, sku_id)
        for direction_id in case["direction_ids"]
        for sku_id in case["sku_ids"]
    }
    rows = case["rows"]
    pairs = [(row["direction_id"], row["sku_id"]) for row in rows]
    return (
        len(pairs) == len(set(pairs))
        and set(pairs) == expected_pairs
        and Counter(row["requested_artifact_id"] for row in rows)
        == Counter(case["requested_artifact_ids"])
        and all(
            row["status"] == "passed"
            and row["artifact_id"]
            and row["locator"]
            and row["comparison_gates_passed"]
            for row in rows
        )
    )


def _asset_brief_is_valid(brief):
    if brief["status"] == "passed":
        required_values = (
            brief["job"],
            brief["audience_task"],
            brief["package_state"],
            brief["crop"]["aspect_ratio"],
        )
        return (
            not brief["unknown_fields"]
            and all(value not in (None, "", "unknown") for value in required_values)
            and isinstance(brief["target_object_count"], int)
            and _is_sha256(brief["package_identity_sha256"])
            and bool(brief["review_profile_ids"])
            and bool(brief["approved_by"])
            and bool(brief["approval_basis"])
        )
    if brief["status"] == "draft":
        gaps = set()
        for field in ("job", "audience_task", "package_state"):
            if brief[field] in (None, "", "unknown"):
                gaps.add(field)
        if brief["target_object_count"] in (None, "", "unknown"):
            gaps.add("target_object_count")
        if not brief["composition"]:
            gaps.add("composition")
        if not brief["camera"]:
            gaps.add("camera")
        if brief["crop"]["aspect_ratio"] in (None, "", "unknown"):
            gaps.add("crop.aspect_ratio")
        if not brief["package_identity_sha256"]:
            gaps.add("package_identity_sha256")
        if not brief["review_profile_ids"]:
            gaps.add("review_profile_ids")
        return set(brief["unknown_fields"]) == gaps and not brief["approved_by"]
    return False


def test_all_public_yaml_fixtures_parse():
    documents = _fixture_documents()
    assert {path.name for path in documents} == {
        "asset-provenance.yaml",
        "brief-compare.yaml",
        "brief-present.yaml",
        "brief-refine.yaml",
        "delivery-manifest.yaml",
        "final-build-authorization-2026-09-09.yaml",
        "fictional-concept-decision.yaml",
        "fictional-research-input.yaml",
        "forward-authorization-2026-09-09.yaml",
        "full-workflow.yaml",
        "generation-receipt-v0.2-2026-09-09.yaml",
        "qa-result-v0.2-2026-09-09.yaml",
        "reference-manifest.yaml",
        "runtime-receipt-v0.2-2026-09-09.yaml",
    }
    for path in documents:
        assert yaml.safe_load(path.read_text(encoding="utf-8")) is not None
    routing_cases = REPO_ROOT / "tests" / "routing-cases.yaml"
    assert yaml.safe_load(routing_cases.read_text(encoding="utf-8"))["cases"]


def test_full_workflow_fixture_binds_the_completed_public_gallery_chain():
    assert FULL_WORKFLOW_PATH.is_file()
    assert DELIVERY_MANIFEST_PATH.is_file()

    workflow = yaml.safe_load(FULL_WORKFLOW_PATH.read_text(encoding="utf-8"))
    manifest = yaml.safe_load(DELIVERY_MANIFEST_PATH.read_text(encoding="utf-8"))
    contracts = workflow["contracts"]
    provenance = {
        item["id"]: item
        for item in yaml.safe_load(
            (EXAMPLES_ROOT / "asset-provenance.yaml").read_text(encoding="utf-8")
        )["assets"]
    }
    legacy_compare_receipt = next(
        receipt
        for receipt in yaml.safe_load(
            LEGACY_FORWARD_RECEIPTS_PATH.read_text(encoding="utf-8")
        )["receipts"]
        if receipt["id"] == "compare-forward-2026-09-08"
    )
    sources = {source["id"]: source for source in workflow["sources"]}

    planning_authorization = yaml.safe_load(
        FORWARD_AUTHORIZATION_PATH.read_text(encoding="utf-8")
    )
    final_authorization = yaml.safe_load(
        FINAL_AUTHORIZATION_PATH.read_text(encoding="utf-8")
    )
    concept_decision = yaml.safe_load(
        CONCEPT_DECISION_PATH.read_text(encoding="utf-8")
    )
    runtime_authorization = workflow["processing_policy"]["authorization"]
    assert runtime_authorization["authority"] == "current-user"
    assert runtime_authorization["record_id"] == final_authorization["id"]
    assert runtime_authorization["generation_authorized"] is True
    assert runtime_authorization["publication_authorized"] is False
    assert runtime_authorization["confirmed_at_utc"] == final_authorization["authorization"][
        "confirmed_at_utc"
    ]
    assert runtime_authorization["basis"].strip()
    assert manifest["processing_policy"]["authorization"] == runtime_authorization
    assert {item["id"] for item in workflow["sources"]} >= {
        "fictional-authoring-record",
        "fixture-research-input",
        "fixture-concept-decision",
        "fixture-present-reference",
        "fixture-refine-reference",
        "fixture-asset-register",
        "compare-direction-a-source",
        "compare-direction-b-source",
        "legacy-forward-receipts",
        "public-fictional-v02-authorization",
        "public-fictional-v02-final-authorization",
    }
    assert all(
        not Path(item["locator"]).is_absolute()
        and ".." not in Path(item["locator"]).parts
        for item in workflow["sources"]
    )
    assert all(
        item["sha256"]
        == hashlib.sha256((REPO_ROOT / item["locator"]).read_bytes()).hexdigest()
        for item in workflow["sources"]
    )
    assert all(
        not Path(item["locator"]).is_absolute()
        and ".." not in Path(item["locator"]).parts
        for item in provenance.values()
    )

    expected_contracts = {
        "product_brief",
        "research_board",
        "packaging_option_matrix",
        "decision_lock",
        "series_system",
        "packaging_direction_set",
        "selection_lock",
        "ecommerce_asset_plan",
        "asset_briefs",
        "qa_plan",
    }
    assert expected_contracts <= contracts.keys()
    product_brief = contracts["product_brief"]
    decision_lock = contracts["decision_lock"]
    direction_set = contracts["packaging_direction_set"]
    selection_lock = contracts["selection_lock"]
    ecommerce_plan = contracts["ecommerce_asset_plan"]
    asset_briefs = contracts["asset_briefs"]
    qa_plan = contracts["qa_plan"]

    assert workflow["project_state"]["active_decision_lock_id"] == decision_lock["id"]
    auth_source = sources["public-fictional-v02-authorization"]
    assert auth_source["locator"] == FORWARD_AUTHORIZATION_PATH.relative_to(
        REPO_ROOT
    ).as_posix()
    assert auth_source["record_ids"] == [planning_authorization["id"]]
    assert auth_source["sha256"] == hashlib.sha256(
        FORWARD_AUTHORIZATION_PATH.read_bytes()
    ).hexdigest()

    assert workflow["project_state"]["active_selection_lock_id"] == selection_lock["id"]
    final_auth_source = sources["public-fictional-v02-final-authorization"]
    assert final_auth_source["locator"] == FINAL_AUTHORIZATION_PATH.relative_to(
        REPO_ROOT
    ).as_posix()
    assert final_auth_source["record_ids"] == [final_authorization["id"]]
    assert final_auth_source["sha256"] == hashlib.sha256(
        FINAL_AUTHORIZATION_PATH.read_bytes()
    ).hexdigest()

    assert workflow["project_state"]["current_stage_id"] == "qa-delivery"
    assert workflow["project_state"]["earliest_incomplete_stage_id"] is None
    stage_statuses = {
        stage["stage_id"]: stage["status"]
        for stage in workflow["project_state"]["stages"]
    }
    assert stage_statuses == {
        "product-definition": "passed",
        "research-options": "passed",
        "decision-freeze": "passed",
        "packaging-directions": "passed",
        "selection-refinement": "passed",
        "ecommerce-planning": "passed",
        "ecommerce-generation": "passed",
        "qa-delivery": "passed",
    }
    stages = {
        stage["stage_id"]: stage for stage in workflow["project_state"]["stages"]
    }
    for stage in stages.values():
        assert stage["contract_id"] in stage["contract_ids"]
        assert stage["contract_ids"]
        assert stage["gate_decision_id"] is not None
    assert stages["product-definition"]["gate_decision_id"] == concept_decision["id"]
    assert product_brief["approval_record_id"] == concept_decision["id"]
    approved_claim = concept_decision["decision"]["approved_claims"][
        "claim-fictional-product"
    ]
    assert product_brief["product"]["claim_items"][0]["value"] == approved_claim
    assert decision_lock["claim_items"][0]["value"] == approved_claim
    assert stages["research-options"]["contract_ids"] == [
        "fictional-pantry-research-board-v02",
        "fictional-pantry-option-matrix-v02",
    ]
    assert stages["decision-freeze"]["contract_ids"] == [
        "fictional-pantry-decision-lock-v02",
        "fictional-pantry-series-system-v02",
    ]
    assert stages["ecommerce-planning"]["contract_ids"] == [
        "fictional-pantry-ecommerce-plan-v02",
        "gallery-catalog",
        "gallery-detail",
        "gallery-usage",
        "gallery-specification",
        "gallery-context",
        "gallery-campaign",
        "gallery-channel-variant",
    ]
    assert stages["qa-delivery"]["contract_ids"] == [
        "fictional-pantry-delivery-manifest-v02",
        "fictional-pantry-image-qa-result-v02-2026-09-09",
        "fictional-pantry-runtime-receipt-v02-2026-09-09",
    ]
    assert decision_lock["origin"] == "workflow"
    assert _trusted_approval_is_bound(product_brief, sources)
    assert _trusted_approval_is_bound(decision_lock, sources)
    assert decision_lock["approved_by"] == "trusted-record"
    assert decision_lock["approval_source_id"] == "fixture-concept-decision"
    assert decision_lock["approval_record_id"] == "fictional-pantry-concept-decision-v02"
    assert decision_lock["approval_basis"].strip()
    assert decision_lock["import_source_id"] is None
    assert decision_lock["import_source_sha256"] is None
    assert decision_lock["product_brief_id"] == product_brief["id"]
    assert decision_lock["research_board_id"] == contracts["research_board"]["id"]
    assert decision_lock["packaging_option_matrix_id"] == contracts[
        "packaging_option_matrix"
    ]["id"]
    assert decision_lock["source_contract_hashes"]["hash_basis"] == (
        "canonical-sorted-compact-utf8-json"
    )
    assert decision_lock["source_contract_hashes"]["product_brief_sha256"] == hashlib.sha256(
        json.dumps(
            product_brief,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    assert decision_lock["source_contract_hashes"]["research_board_sha256"] == hashlib.sha256(
        json.dumps(
            contracts["research_board"],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    assert decision_lock["source_contract_hashes"]["packaging_option_matrix_sha256"] == hashlib.sha256(
        json.dumps(
            contracts["packaging_option_matrix"],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    assert product_brief["product"]["audience"]["description"] != "unknown"
    assert product_brief["product"]["usage_occasions"]
    assert product_brief["package_starting_point"]["status"] == "working"
    assert decision_lock["unknown_fields"] == []
    assert decision_lock["unverified_fields"] == []
    assert not set(decision_lock["unknown_fields"]) & set(decision_lock["frozen_fields"])
    assert not set(decision_lock["unknown_fields"]) & set(
        decision_lock["verified_prompt_fact_fields"]
    )
    for field in (
        "audience_task",
        "usage_task",
        "package_construction",
        "target_specification_range",
    ):
        assert field in decision_lock["frozen_fields"]
        assert field in decision_lock["verified_prompt_fact_fields"]
        assert field not in decision_lock["open_fields"]
    assert decision_lock["claim_items"] == [
        {
            "id": "claim-fictional-product",
            "value": "Fictional dry pantry mix for testing only.",
            "source_id": "legacy-forward-receipts",
            "approval_state": "approved",
            "approved_by": "trusted-record",
            "approval_basis": "Recorded public compare receipt contains this exact fictional claim.",
            "approval_source_id": "legacy-forward-receipts",
            "approval_record_id": "compare-forward-2026-09-08",
            "permissions": product_brief["product"]["claim_items"][0]["permissions"],
        }
    ]
    assert _approved_items_resolve(
        product_brief["product"]["claim_items"], decision_lock["claim_item_ids"]
    )
    for item in (
        product_brief["product"]["claim_items"]
        + product_brief["exact_copy"]["exact_copy_items"]
        + decision_lock["claim_items"]
        + decision_lock["exact_copy_items"]
    ):
        assert _trusted_approval_is_bound(item, sources)
    assert _approved_items_resolve(
        product_brief["exact_copy"]["exact_copy_items"],
        decision_lock["exact_copy_item_ids"],
    )
    direction_ids = {direction["id"] for direction in direction_set["directions"]}
    sku_ids = {variant["id"] for variant in product_brief["product"]["variants"]}
    rows = direction_set["direction_by_sku_matrix"]
    assert {(row["direction_id"], row["sku_id"]) for row in rows} == {
        (direction_id, sku_id)
        for direction_id in direction_ids
        for sku_id in sku_ids
    }
    artifacts = {
        artifact["requested_artifact_id"]: artifact
        for artifact in direction_set["artifacts"]
    }
    assert set(artifacts) == {
        artifact["id"] for artifact in direction_set["requested_artifacts"]
    }
    assert all(row["status"] == "passed" for row in rows)
    assert all(row["comparison_gates_passed"] is True for row in rows)
    for row in rows:
        artifact = artifacts[row["requested_artifact_id"]]
        source = provenance[artifact["source_asset_id"]]
        assert artifact["artifact_id"] == row["artifact_id"]
        assert artifact["status"] == "passed"
        assert (REPO_ROOT / artifact["locator"]).resolve() == (
            EXAMPLES_ROOT / source["locator"]
        ).resolve()
        assert artifact["sha256"] == source["sha256"]
        assert artifact["source_object_id"] == row["sku_id"]
        assert artifact["direction_id"] == row["direction_id"]
        receipt_binding = artifact["source_receipt"]
        assert receipt_binding == {
            "source_id": "legacy-forward-receipts",
            "receipt_id": legacy_compare_receipt["id"],
            "receipt_sha256": hashlib.sha256(
                LEGACY_FORWARD_RECEIPTS_PATH.read_bytes()
            ).hexdigest(),
            "requested_artifact_id": artifact["source_asset_id"],
        }
        legacy_artifact = next(
            item
            for item in legacy_compare_receipt["artifacts"]
            if item["id"] == receipt_binding["requested_artifact_id"]
        )
        assert legacy_artifact["sha256"] == artifact["sha256"]
        assert legacy_artifact["locator"] == artifact["locator"]
        expected_qa_pairs = {
            (gate_id, profile)
            for gate_id in legacy_compare_receipt["contract_snapshot"][
                "normalized_contract"
            ]["qa_plan"]["required_gate_ids"]
            for profile in legacy_compare_receipt["contract_snapshot"][
                "normalized_contract"
            ]["qa_plan"]["review_profiles"]
        }
        actual_qa_gates = [
            gate
            for gate in legacy_compare_receipt["qa"]["gates"]
            if gate["artifact_id"] == legacy_artifact["id"]
        ]
        assert Counter((gate["gate_id"], gate["profile"]) for gate in actual_qa_gates) == Counter(
            expected_qa_pairs
        )
        assert all(gate["status"] == "pass" for gate in actual_qa_gates)

    assert selection_lock["selected_direction_id"] in direction_ids
    assert selection_lock["source_scope"] == "named-objects"
    selected_rows = [
        row
        for row in rows
        if row["direction_id"] == selection_lock["selected_direction_id"]
    ]
    assert {row["sku_id"] for row in selected_rows} == sku_ids
    assert {
        artifacts[row["requested_artifact_id"]]["source_object_id"]
        for row in selected_rows
    } == set(selection_lock["source_object_ids"])
    assert set(selection_lock["selected_matrix_artifact_ids"]) == {
        row["artifact_id"] for row in selected_rows
    }
    assert {
        artifacts[row["requested_artifact_id"]]["source_asset_id"]
        for row in selected_rows
    } == {selection_lock["source_artifact_id"]}
    source = provenance[selection_lock["source_artifact_id"]]
    assert selection_lock["source_artifact_sha256"] == source["sha256"]
    identity = selection_lock["package_identity_snapshot"]
    identity_digest = hashlib.sha256(
        json.dumps(
            identity,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    assert selection_lock["package_identity_hash_basis"] == "canonical-package-identity-json"
    assert selection_lock["package_identity_sha256"] == identity_digest
    assert ecommerce_plan["package_identity_sha256"] == identity_digest
    assert selection_lock["status"] == "passed"
    assert selection_lock["approved_by"] == "current-user"
    assert selection_lock["approval_basis"].strip()
    assert selection_lock["approved_at_utc"] == planning_authorization["authorization"][
        "confirmed_at_utc"
    ]
    assert ecommerce_plan["status"] == "passed"
    assert ecommerce_plan["approved_by"] == "current-user"
    assert ecommerce_plan["approval_basis"].strip()
    assert ecommerce_plan["output"] == final_authorization["output"]
    assert ecommerce_plan["output"]["publication_authorized"] is False
    assert set(ecommerce_plan["required_roles"]) == ECOMMERCE_ROLES
    assert _approved_items_resolve(
        product_brief["exact_copy"]["exact_copy_items"],
        ecommerce_plan["exact_copy_item_ids"],
    )
    profile_ids = {profile["profile_id"] for profile in qa_plan["review_profiles"]}
    assert profile_ids == set(ecommerce_plan["channel"]["review_profile_ids"])
    assert [
        profile["profile_id"]
        for profile in qa_plan["review_profiles"]
        if profile["required"] and profile["profile_scope"] == "full-resolution"
    ] == ["full-resolution"]
    assert ecommerce_plan["cross_set_required_gate_ids"] == qa_plan[
        "cross_set_required_gate_ids"
    ]
    assert qa_plan["required_gate_ids"] == final_authorization["qa_plan"][
        "required_gate_ids"
    ]
    assert qa_plan["cross_set_required_gate_ids"] == final_authorization["qa_plan"][
        "cross_set_required_gate_ids"
    ]
    assert len(qa_plan["required_gate_ids"]) == 13
    assert len(qa_plan["cross_set_required_gate_ids"]) == 6
    assert qa_plan["expected_gate_rows"] == 188
    assert qa_plan["expected_gate_rows"] == (
        len(asset_briefs)
        * len(qa_plan["required_gate_ids"])
        * len([profile for profile in qa_plan["review_profiles"] if profile["required"]])
        + len(qa_plan["cross_set_required_gate_ids"])
    )
    qa_hash_basis = {
        key: qa_plan[key]
        for key in (
            "required_gate_ids",
            "cross_set_required_gate_ids",
            "review_profiles",
            "independent_review_required",
        )
    }
    assert qa_plan["sha256"] == hashlib.sha256(
        json.dumps(
            qa_hash_basis,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()

    briefs_by_id = {brief["id"]: brief for brief in asset_briefs}
    assert set(ecommerce_plan["asset_brief_ids"]) == set(briefs_by_id)
    assert {brief["role"] for brief in asset_briefs} == ECOMMERCE_ROLES
    assert all(brief["status"] == "passed" for brief in asset_briefs)
    assert all(brief["blocking_reason"] is None for brief in asset_briefs)
    assert all(brief["package_identity_sha256"] == identity_digest for brief in asset_briefs)
    assert all(brief["approved_by"] == "current-user" for brief in asset_briefs)
    assert all(brief["approval_basis"].strip() for brief in asset_briefs)
    expected_graph = {
        "gallery-catalog": (None, ["compare-direction-a"]),
        "gallery-detail": ("gallery-catalog", ["gallery-catalog"]),
        "gallery-usage": (
            "gallery-catalog",
            ["gallery-catalog", "gallery-usage-background-plate"],
        ),
        "gallery-specification": ("gallery-detail", ["gallery-detail"]),
        "gallery-context": (
            "gallery-catalog",
            ["gallery-catalog", "gallery-context-background-plate"],
        ),
        "gallery-campaign": ("gallery-catalog", ["gallery-catalog"]),
        "gallery-channel-variant": ("gallery-catalog", ["gallery-catalog"]),
    }
    assert {
        brief_id: (
            brief["parent_asset_brief_id"],
            brief["required_input_asset_ids"],
        )
        for brief_id, brief in briefs_by_id.items()
    } == expected_graph

    usage_brief = briefs_by_id["gallery-usage"]
    assert usage_brief["job"] == (
        "Show the approved fictional pre-opening setup with one sealed Berry Oat pouch "
        "and one empty clear glass."
    )
    assert usage_brief["audience_task"] == (
        "Recognize the package state before opening without inferring preparation, dosage, "
        "serving, consumption, or performance."
    )
    assert usage_brief["package_state"] == (
        "One unopened Berry Oat pouch beside one empty clear glass; no opened package, "
        "powder, prepared drink, or use instruction."
    )
    assert usage_brief["composition"]["layout"] == (
        "one unopened pouch beside exactly one empty clear glass on a neutral pre-opening surface"
    )

    specification_brief = briefs_by_id["gallery-specification"]
    assert specification_brief["job"] == (
        "Present the approved 240 g quantity as a deterministic magnified detail alongside "
        "the sealed Lemon Ginger pouch."
    )
    assert specification_brief["required_input_asset_ids"] == ["gallery-detail"]
    assert specification_brief["composition"]["layout"] == (
        "one complete pouch plus one magnified inset cropped from the existing 240 g source pixels"
    )
    assert "callout" not in json.dumps(specification_brief).lower()
    assert len(
        {
            json.dumps(
                {
                    key: brief[key]
                    for key in (
                        "package_state",
                        "composition",
                        "camera",
                        "crop",
                        "background",
                        "required_input_asset_ids",
                        "permitted_scene_changes",
                    )
                },
                sort_keys=True,
            )
            for brief in asset_briefs
        }
    ) == len(asset_briefs)
    assert all(
        brief["package_state"]
        and brief["composition"]
        and brief["camera"]
        and brief["crop"]["aspect_ratio"]
        and brief["background"]
        and brief["required_input_asset_ids"]
        and brief["permitted_scene_changes"]
        for brief in asset_briefs
    )

    assert manifest["project_state_id"] == workflow["project_state"]["id"]
    assert manifest["decision_lock_id"] == decision_lock["id"]
    assert manifest["selection_lock_id"] == selection_lock["id"]
    assert manifest["ecommerce_asset_plan_id"] == ecommerce_plan["id"]
    assert manifest["qa_plan_id"] == qa_plan["id"]
    bindings = manifest["source_bindings"]
    assert bindings["decision_lock_hash_basis"] == "canonical-sorted-compact-utf8-json"
    assert bindings["decision_lock_sha256"] == hashlib.sha256(
        json.dumps(
            decision_lock,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    assert bindings["selection_source_artifact_id"] == selection_lock["source_artifact_id"]
    assert bindings["selection_source_sha256"] == selection_lock["source_artifact_sha256"]
    assert bindings["planning_authorization_record_id"] == planning_authorization["id"]
    assert bindings["planning_authorization_sha256"] == hashlib.sha256(
        FORWARD_AUTHORIZATION_PATH.read_bytes()
    ).hexdigest()
    assert bindings["final_authorization_record_id"] == final_authorization["id"]
    assert bindings["final_authorization_public_record_sha256"] == hashlib.sha256(
        FINAL_AUTHORIZATION_PATH.read_bytes()
    ).hexdigest()
    assert bindings["final_authorization_source_sha256"] == final_authorization[
        "source_record"
    ]["sha256"]
    assert bindings["authorized_transform_sha256"] == bindings["current_transform_sha256"]
    assert bindings["authorized_transform_sha256"] == final_authorization[
        "transform_binding"
    ]["sha256"]
    assert bindings["transform_binding_status"] == "match"
    assert bindings["generation_receipt_sha256"] == hashlib.sha256(
        GENERATION_RECEIPT_PATH.read_bytes()
    ).hexdigest()
    assert bindings["final_build_report_sha256"] == hashlib.sha256(
        (V02_GALLERY_ROOT / "final-build-report.json").read_bytes()
    ).hexdigest()
    assert bindings["plate_provenance_sha256"] == hashlib.sha256(
        (V02_GALLERY_ROOT / "plate-provenance.json").read_bytes()
    ).hexdigest()
    assert bindings["qa_result_sha256"] == hashlib.sha256(
        QA_RESULT_PATH.read_bytes()
    ).hexdigest()
    assert bindings["review_manifest_sha256"] == hashlib.sha256(
        (V02_REVIEW_ROOT / "manifest.json").read_bytes()
    ).hexdigest()
    assert set(manifest["requested_artifact_ids"]) == {
        artifact["requested_artifact_id"] for artifact in manifest["artifacts"]
    }
    assert Counter(manifest["requested_artifact_ids"]) == Counter(
        artifact["requested_artifact_id"] for artifact in manifest["artifacts"]
    )
    assert len(manifest["requested_artifact_ids"]) == len(
        set(manifest["requested_artifact_ids"])
    )
    assert {artifact["asset_brief_id"] for artifact in manifest["artifacts"]} == set(
        briefs_by_id
    )
    expected_files = {
        "gallery-catalog": "gallery-catalog-2026-09-09.png",
        "gallery-detail": "gallery-detail-2026-09-09.png",
        "gallery-usage": "gallery-usage-2026-09-09.png",
        "gallery-specification": "gallery-specification-2026-09-09.png",
        "gallery-context": "gallery-context-2026-09-09.png",
        "gallery-campaign": "gallery-campaign-2026-09-09.png",
        "gallery-channel-variant": "gallery-channel-variant-2026-09-09.png",
    }
    for artifact in manifest["artifacts"]:
        requested_id = artifact["requested_artifact_id"]
        path = V02_GALLERY_ROOT / expected_files[requested_id]
        assert artifact["artifact_id"] == f"{requested_id}-2026-09-09"
        assert artifact["locator"] == path.relative_to(REPO_ROOT).as_posix()
        assert artifact["locator_type"] == "relative_path"
        assert artifact["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert artifact["status"] == "passed"
        assert artifact["blocking_reason"] is None
    assert all(
        artifact["expected_package_identity_sha256"] == identity_digest
        for artifact in manifest["artifacts"]
    )
    assert all(set(artifact["review_profile_ids"]) == profile_ids for artifact in manifest["artifacts"])
    assert manifest["per_image_qa_status"] == "pass"
    assert manifest["cross_set_qa_status"] == "pass"
    assert manifest["completeness_status"] == "passed"
    assert manifest["remaining_work"]
    assert any("publication" in item.lower() for item in manifest["remaining_work"])

    build_report = json.loads(
        (V02_GALLERY_ROOT / "final-build-report.json").read_text(encoding="utf-8")
    )
    assert build_report["status"] == "draft"
    assert build_report["qa"]["actual_gate_rows"] == 188
    assert all(row["status"] == "unverified" for row in build_report["qa"]["rows"])

    serialized = json.dumps({"workflow": workflow, "manifest": manifest})
    assert "refined-package" not in serialized
    assert "ecommerce-packshot" not in serialized


def test_public_gallery_qa_and_runtime_receipts_close_all_188_required_rows():
    workflow = yaml.safe_load(FULL_WORKFLOW_PATH.read_text(encoding="utf-8"))
    manifest = yaml.safe_load(DELIVERY_MANIFEST_PATH.read_text(encoding="utf-8"))
    generation = yaml.safe_load(GENERATION_RECEIPT_PATH.read_text(encoding="utf-8"))
    qa = yaml.safe_load(QA_RESULT_PATH.read_text(encoding="utf-8"))
    runtime = yaml.safe_load(RUNTIME_RECEIPT_PATH.read_text(encoding="utf-8"))
    qa_plan = workflow["contracts"]["qa_plan"]

    assert qa["schema_version"] == 2
    assert qa["status"] == "passed"
    assert qa["plan_sha256"] == qa_plan["sha256"]
    assert qa["reviewed_by"] == "independent-agent"
    assert qa["reviewer_id"] == "public_gallery_qa"
    assert qa["reviewer_id"] != generation["executor_id"]
    assert qa["severity_summary"] == {"p1": 0, "p2": 0}
    assert qa["required_failures"] == []
    assert len(qa["gates"]) == 188

    artifact_ids = {
        row["requested_artifact_id"]: row["artifact_id"]
        for row in manifest["artifacts"]
    }
    per_image = [gate for gate in qa["gates"] if gate["scope"] == "per-image"]
    cross_set = [gate for gate in qa["gates"] if gate["scope"] == "cross-set"]
    expected_per_image = {
        (requested_id, gate_id, profile["profile_id"])
        for requested_id in manifest["requested_artifact_ids"]
        for gate_id in qa_plan["required_gate_ids"]
        for profile in qa_plan["review_profiles"]
        if profile["required"]
    }
    assert len(per_image) == 182
    assert {
        (gate["requested_artifact_id"], gate["gate_id"], gate["profile_id"])
        for gate in per_image
    } == expected_per_image
    assert all(
        gate["artifact_id"] == artifact_ids[gate["requested_artifact_id"]]
        for gate in per_image
    )
    assert len(cross_set) == 6
    assert {gate["gate_id"] for gate in cross_set} == set(
        qa_plan["cross_set_required_gate_ids"]
    )
    assert all(
        gate["requested_artifact_id"] is None
        and gate["artifact_id"] is None
        and gate["profile_scope"] == "cross-set"
        and gate["profile_id"] == "cross-set"
        for gate in cross_set
    )
    assert all(
        gate["level"] == "required"
        and gate["status"] == "pass"
        and gate["requirement"].strip()
        and gate["evidence"].strip()
        for gate in qa["gates"]
    )

    assert runtime["schema_version"] == 2
    assert runtime["project_state_id"] == workflow["project_state"]["id"]
    assert runtime["stage_id"] == "qa-delivery"
    assert runtime["internal_operation"] == "inspect"
    assert runtime["status"] == "passed"
    assert runtime["source_brief"] == {
        "locator": FULL_WORKFLOW_PATH.relative_to(REPO_ROOT).as_posix(),
        "sha256": hashlib.sha256(FULL_WORKFLOW_PATH.read_bytes()).hexdigest(),
    }
    assert runtime["requested_artifact_ids"] == manifest["requested_artifact_ids"]
    assert all(output["status"] == "passed" for output in runtime["stage_outputs"])
    assert all(
        not check["required"] or check["status"] == "pass"
        for check in runtime["stage_checks"]
    )
    assert runtime["generation_receipt"] == generation
    assert runtime["qa_plan"] == qa_plan
    assert runtime["qa"] == qa
    assert runtime["contract_snapshot"]["snapshot_level"] == "redacted"
    assert runtime["contract_snapshot"]["omissions"] == [
        "Full DecisionLock and SelectionLock bodies are omitted; their IDs and package-identity digest remain in the normalized contract.",
        "Source and asset permission objects are omitted; their authoritative values remain in the bound workflow, authorization, generation, and delivery records.",
    ]
    assert runtime["contract_snapshot"]["hash_basis"] == (
        "canonical-runtime-contract-json"
    )
    assert runtime["contract_snapshot"]["sha256"] == hashlib.sha256(
        json.dumps(
            runtime["contract_snapshot"]["normalized_contract"],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    assert all(
        set(item["permissions"]) == PERMISSION_KEYS
        for item in runtime["contract_snapshot"]["resolved_permissions"]
    )
    assert {
        item["subject_type"]
        for item in runtime["contract_snapshot"]["resolved_permissions"]
    } <= {"field", "output"}
    normalized_policy = runtime["contract_snapshot"]["normalized_contract"][
        "processing_policy"
    ]
    for item in runtime["contract_snapshot"]["resolved_permissions"]:
        if item["subject_type"] not in {"field", "output"}:
            continue
        expected_permissions, expected_source = _resolve_field_permissions(
            normalized_policy, item["subject_id_or_path"]
        )
        assert item["permissions"] == expected_permissions
        assert item["resolution_source"] == expected_source

    manifest_artifact_permissions, _ = _resolve_field_permissions(
        manifest["processing_policy"], "/artifacts"
    )
    assert manifest_artifact_permissions["redistribution_allowed"] is False
    assert manifest_artifact_permissions["publication_allowed"] is False
    assert all(row["status"] == "passed" for row in runtime["artifacts"])
    assert runtime["remaining_work"]
    assert any("publication" in item.lower() for item in runtime["remaining_work"])


def test_routing_cases_cover_maturity_stages_and_operational_negative_boundaries():
    cases = yaml.safe_load((REPO_ROOT / "tests" / "routing-cases.yaml").read_text(encoding="utf-8"))["cases"]
    in_scope = [case for case in cases if case["expected_scope"] == "in-scope"]
    assert {case["expected_start_stage"] for case in in_scope} == STAGE_IDS
    assert all(case["expected_route"] == "packaging-product-visuals" for case in in_scope)
    assert all("expected_mode" not in case for case in cases)
    negative_ids = {
        case["id"] for case in cases if case["expected_scope"] == "out-of-scope"
    }
    assert negative_ids == {
        "prompt-only-negative",
        "generic-photography-negative",
        "logo-negative",
        "print-ready-negative",
        "media-buying-negative",
        "influencer-operations-negative",
        "manufacturing-negative",
        "competitor-copy-negative",
        "ambiguous-negative",
    }

    by_id = {case["id"]: case for case in cases}
    assert by_id["research-options-start"]["expected_scope"] == "in-scope"
    assert by_id["ecommerce-planning-start"]["expected_scope"] == "in-scope"
    assert "context" in by_id["ecommerce-planning-start"]["prompt"].lower()
    assert "campaign" in by_id["ecommerce-planning-start"]["prompt"].lower()


def test_full_workflow_scenarios_cover_product_start_gallery_and_three_sku_chain():
    scenarios = yaml.safe_load(
        FULL_WORKFLOW_SCENARIOS_PATH.read_text(encoding="utf-8")
    )["scenarios"]

    assert [scenario["id"] for scenario in scenarios] == [
        "uncertain-product-start",
        "approved-package-gallery",
        "three-sku-full-chain",
    ]
    for scenario in scenarios:
        assert FULL_WORKFLOW_SCENARIO_KEYS <= scenario.keys()
        assert scenario["request"]
        assert scenario["active_stage_outputs"]
        assert scenario["expected_scope_end_stage"] in STAGE_IDS
        assert scenario["prohibited_claims"]

    by_id = {scenario["id"]: scenario for scenario in scenarios}
    assert (
        by_id["uncertain-product-start"]["expected_start_stage"]
        == "product-definition"
    )
    assert (
        by_id["approved-package-gallery"]["expected_start_stage"]
        == "ecommerce-planning"
    )
    assert (
        by_id["three-sku-full-chain"]["expected_start_stage"]
        == "product-definition"
    )
    assert by_id["approved-package-gallery"]["ecommerce_roles"] == [
        "catalog",
        "context",
        "channel-variant",
    ]
    assert by_id["three-sku-full-chain"]["ecommerce_roles"] == []
    assert by_id["uncertain-product-start"]["active_stage_outputs"] == ["ProductBrief"]
    assert by_id["uncertain-product-start"]["expected_scope_end_stage"] == "decision-freeze"
    assert by_id["approved-package-gallery"]["active_stage_outputs"] == [
        "EcommerceAssetPlan",
        "AssetBrief",
    ]
    assert by_id["approved-package-gallery"]["expected_scope_end_stage"] == "qa-delivery"
    gallery_request = by_id["approved-package-gallery"]["request"].lower()
    assert "qa delivery" in gallery_request
    for role in by_id["approved-package-gallery"]["ecommerce_roles"]:
        assert role in gallery_request
    assert by_id["three-sku-full-chain"]["active_stage_outputs"] == ["ProductBrief"]
    assert by_id["three-sku-full-chain"]["expected_scope_end_stage"] == "qa-delivery"


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


def test_v02_contracts_cover_workflow_state_sku_matrix_and_cross_asset_identity():
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

    assert all(contract in contracts for contract in V02_CONTRACTS)
    assert "direction-by-SKU matrix" in contracts
    assert "package identity" in contracts.lower()
    assert "across assets" in contracts.lower()
    assert "approval_source_id:" in contracts
    assert "approval_record_id:" in contracts
    assert "canonical-sorted-compact-utf8-json" in contracts
    assert "selected_matrix_artifact_ids:" in contracts
    assert "earliest incomplete stage" in workflow


def test_v02_contract_case_fixture_covers_nine_semantic_rules():
    cases = _v02_contract_cases()
    assert cases["schema_version"] == 1
    assert {
        "decision_lock_cases",
        "imported_delivery_chain",
        "non_rendering_receipt_cases",
        "package_identity_case",
        "artifact_join_cases",
        "qa_profile_cases",
        "item_reference_cases",
        "direction_matrix_cases",
        "qa_minimum_case",
        "asset_brief_cases",
        "legacy_present_cases",
    } <= cases.keys()


def test_decision_lock_origin_rules_allow_only_explicit_safe_unknowns():
    cases = _v02_contract_cases()["decision_lock_cases"]
    for case in cases:
        assert _decision_lock_is_valid(case["lock"]) is case["expected_valid"], case["id"]

    chain = _v02_contract_cases()["imported_delivery_chain"]
    assert chain["decision_lock"]["origin"] == "imported-approved-package"
    assert chain["selection_lock"]["decision_lock_id"] == chain["decision_lock"]["id"]
    assert chain["delivery_manifest"]["decision_lock_id"] == chain["decision_lock"]["id"]
    assert chain["delivery_manifest"]["selection_lock_id"] == chain["selection_lock"]["id"]

    contracts = (
        REPO_ROOT
        / "skills"
        / "packaging-product-visuals"
        / "references"
        / "contracts.md"
    ).read_text(encoding="utf-8")
    assert "unknown_fields:" in contracts
    assert "unverified_fields:" in contracts
    assert "verified_prompt_fact_fields:" in contracts


def test_non_rendering_status_and_identity_digest_are_executable():
    cases = _v02_contract_cases()
    for case in cases["non_rendering_receipt_cases"]:
        assert _non_rendering_receipt_is_valid(case["receipt"]) is case["expected_valid"], case["id"]

    identity = cases["package_identity_case"]
    canonical = json.dumps(
        identity["snapshot"], sort_keys=True, separators=(",", ":")
    ).encode()
    digest = hashlib.sha256(canonical).hexdigest()
    assert identity["hash_basis"] == "canonical-package-identity-json"
    assert digest == identity["expected_sha256"]
    assert set(identity["linked_digests"].values()) == {digest}
    assert len(set(identity["mismatched_linked_digests"].values())) > 1


def test_artifact_joins_and_multiple_profile_gate_cardinality_are_exact():
    cases = _v02_contract_cases()
    for case in cases["artifact_join_cases"]:
        assert _artifact_join_is_valid(case) is case["expected_valid"], case["id"]
    for case in cases["qa_profile_cases"]:
        assert _qa_cardinality_is_valid(case) is case["expected_valid"], case["id"]


def test_item_references_and_matrix_selection_are_semantically_validated():
    cases = _v02_contract_cases()
    for case in cases["item_reference_cases"]:
        valid = _approved_items_resolve(case["claim_items"], case["claim_item_ids"])
        valid = valid and _approved_items_resolve(
            case["exact_copy_items"], case["exact_copy_item_ids"]
        )
        assert valid is case["expected_valid"], case["id"]
    for case in cases["direction_matrix_cases"]:
        assert _matrix_is_selection_eligible(case) is case["expected_selection_eligible"], case["id"]


def test_required_visual_gates_and_asset_brief_generation_gate_are_enforced():
    cases = _v02_contract_cases()
    minimum = cases["qa_minimum_case"]
    assert minimum["anatomy_applicable"] is True
    assert {"product-anatomy", "visual-hierarchy-identity"} <= set(
        minimum["required_gate_ids"]
    )
    assert "direction-comparability" in minimum["direction_required_gate_ids"]
    assert "cross-asset-sku-consistency" in minimum["cross_set_required_gate_ids"]

    by_id = {case["id"]: case for case in cases["asset_brief_cases"]}
    for case in by_id.values():
        brief = case["brief"]
        valid = _asset_brief_is_valid(brief)
        generation_eligible = valid and brief["status"] == "passed"
        assert valid is case["expected_valid"], case["id"]
        assert generation_eligible is case["expected_generation_eligible"], case["id"]

    contracts = (
        REPO_ROOT
        / "skills"
        / "packaging-product-visuals"
        / "references"
        / "contracts.md"
    ).read_text(encoding="utf-8")
    assert "AssetBrief:" in contracts
    assert "status: passed | draft | blocked" in contracts
    assert "unknown_fields:" in contracts


def test_legacy_present_mapping_is_catalog_only_draft_and_never_generation_ready():
    cases = _v02_contract_cases()
    briefs = {case["brief"]["id"]: case["brief"] for case in cases["asset_brief_cases"]}
    for case in cases["legacy_present_cases"]:
        assert case["normalized_stage_id"] == "ecommerce-planning"
        assert case["expected_generation_eligible"] is False
        assert _is_sha256(case["preserved_legacy_receipt_hash"])
        brief_id = case["normalized_asset_brief_id"]
        if brief_id is None:
            assert case["expected_role"] is None
            continue
        brief = briefs[brief_id]
        assert brief["role"] == case["expected_role"] == "catalog"
        assert brief["status"] == case["expected_status"] == "draft"
        assert _asset_brief_is_valid(brief)
        assert brief["unknown_fields"]


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
    assert {
        "refine-source",
        "present-source",
        "corner-marker-reference",
        "compare-direction-a",
        "compare-direction-b-attempt-01",
        "compare-direction-b",
        "refined-package-attempt-01",
        "refined-package",
        "ecommerce-packshot",
        "gallery-usage-background-attempt-01-v02",
        "gallery-context-background-attempt-01-v02",
        "lemon-ginger-mask-v02",
        "berry-oat-mask-v02",
        "gallery-catalog-v02",
        "gallery-detail-v02",
        "gallery-usage-v02",
        "gallery-specification-v02",
        "gallery-context-v02",
        "gallery-campaign-v02",
        "gallery-channel-variant-v02",
        "gallery-catalog-thumbnail-v02",
        "gallery-detail-thumbnail-v02",
        "gallery-usage-thumbnail-v02",
        "gallery-specification-thumbnail-v02",
        "gallery-context-thumbnail-v02",
        "gallery-campaign-thumbnail-v02",
        "gallery-channel-variant-thumbnail-v02",
    } == {item["id"] for item in provenance}
    public_images = {
        path.relative_to(EXAMPLES_ROOT).as_posix()
        for path in EXAMPLES_ROOT.rglob("*")
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    }
    assert {item["locator"] for item in provenance} == public_images
    for item in provenance:
        asset = EXAMPLES_ROOT / item["locator"]
        assert asset.is_file()
        assert hashlib.sha256(asset.read_bytes()).hexdigest() == item["sha256"]
        with Image.open(asset) as image:
            assert list(image.size) == item["expected_dimensions"]
            assert image.mode == item["expected_mode"]
        assert item["visible_trademarks"] == "none"
        assert item["embedded_private_data"] is False
        assert item["attribution_status"] == "not-required"
        assert item["attribution_fulfilled"] == "not-applicable"
        if "source_asset_id" in item:
            assert item["source_sha256"] == by_id[item["source_asset_id"]]["sha256"]
        if "reference_asset_id" in item:
            assert item["reference_sha256"] == by_id[item["reference_asset_id"]]["sha256"]
        if "supporting_asset_id" in item:
            assert item["supporting_sha256"] == by_id[item["supporting_asset_id"]][
                "sha256"
            ]
