from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import re
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_ROOT = REPO_ROOT / "examples" / "fictional-pantry-product"
RECEIPTS_PATH = REPO_ROOT / "tests" / "evals" / "forward-receipts.yaml"
V02_FIXTURE_RECEIPTS_PATH = REPO_ROOT / "tests" / "evals" / "v0.2-forward-receipts.yaml"
V02_AUTHORIZATION_PATH = (
    EXAMPLE_ROOT / "forward-authorization-2026-09-09.yaml"
)
V02_FINAL_AUTHORIZATION_PATH = (
    EXAMPLE_ROOT / "final-build-authorization-2026-09-09.yaml"
)
V02_GENERATION_RECEIPT_PATH = (
    EXAMPLE_ROOT / "generation-receipt-v0.2-2026-09-09.yaml"
)
V02_QA_RESULT_PATH = EXAMPLE_ROOT / "qa-result-v0.2-2026-09-09.yaml"
V02_RUNTIME_RECEIPT_PATH = (
    EXAMPLE_ROOT / "runtime-receipt-v0.2-2026-09-09.yaml"
)
V02_GALLERY_ROOT = EXAMPLE_ROOT / "generated" / "v0.2" / "2026-09-09"
MODES = ("compare", "refine", "present")
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
COMMON_PROMPT_ROOTS = {
    "/mode",
    "/product",
    "/package",
    "/constraints",
    "/product_baseline",
    "/channel",
    "/requested_artifacts",
    "/qa_plan",
    "/generation_budget",
}
MODE_PROMPT_ROOTS = {
    "compare": {"/comparison_directions"},
    "refine": {"/selection_lock", "/correction"},
    "present": {"/selection_lock", "/presentation"},
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_hash(value: dict) -> str:
    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _canonical_qa_hash(plan: dict) -> str:
    return _canonical_hash(
        {
            key: plan[key]
            for key in (
                "required_gate_ids",
                "review_profiles",
                "independent_review_required",
            )
        }
    )


def _load_receipts() -> dict[str, dict]:
    payload = yaml.safe_load(RECEIPTS_PATH.read_text(encoding="utf-8"))
    assert payload["evidence_version"] == 2
    return {receipt["mode"]: receipt for receipt in payload["receipts"]}


def _expected_runtime_contract(mode: str, receipt: dict) -> dict:
    brief = yaml.safe_load(
        (EXAMPLE_ROOT / f"brief-{mode}.yaml").read_text(encoding="utf-8")
    )
    expected = deepcopy(brief)
    runtime = receipt["contract_snapshot"]["normalized_contract"]
    expected["processing_policy"]["authorization"] = runtime["processing_policy"][
        "authorization"
    ]
    if mode in {"refine", "present"}:
        expected["selection_lock"]["approved_by"] = runtime["selection_lock"][
            "approved_by"
        ]
        expected["selection_lock"]["approval_basis"] = runtime["selection_lock"][
            "approval_basis"
        ]
    return expected


def test_receipts_bind_non_authorizing_briefs_to_full_runtime_contracts():
    receipts = _load_receipts()
    assert set(receipts) == set(MODES)

    for mode, receipt in receipts.items():
        brief_path = EXAMPLE_ROOT / f"brief-{mode}.yaml"
        brief = yaml.safe_load(brief_path.read_text(encoding="utf-8"))
        snapshot = receipt["contract_snapshot"]
        runtime = snapshot["normalized_contract"]

        assert brief["processing_policy"]["authorization"] == {
            "authority": "none",
            "basis": None,
            "confirmed_at_utc": None,
        }
        assert receipt["source_brief"] == {
            "locator": brief_path.relative_to(REPO_ROOT).as_posix(),
            "sha256": _sha256(brief_path),
        }
        assert snapshot["snapshot_level"] == "full"
        assert snapshot["omissions"] == []
        assert snapshot["hash_basis"] == "canonical-runtime-contract-json"
        assert snapshot["sha256"] == _canonical_hash(runtime)
        assert runtime == _expected_runtime_contract(mode, receipt)

        authorization = runtime["processing_policy"]["authorization"]
        assert authorization["authority"] == "current-user"
        assert authorization["basis"].strip()
        assert authorization["confirmed_at_utc"].endswith("Z")
        if mode in {"refine", "present"}:
            assert brief["selection_lock"]["approved_by"] is None
            assert runtime["selection_lock"]["approved_by"] == "current-user"
            assert runtime["selection_lock"]["approval_basis"].strip()


def test_v02_fixture_receipts_preserve_v01_history_and_bind_completed_gallery_output():
    assert V02_FIXTURE_RECEIPTS_PATH.is_file()

    payload = yaml.safe_load(V02_FIXTURE_RECEIPTS_PATH.read_text(encoding="utf-8"))
    assert _sha256(RECEIPTS_PATH) == "72a03643558dc54dd334615de552a6623ee5ba0ed82ad36506c2f2f70fb8dc41"
    assert payload["schema_version"] == 1
    assert payload["evidence_kind"] == "static-fixture-readback"
    assert payload["legacy_receipts"] == {
        "locator": "tests/evals/forward-receipts.yaml",
        "sha256": "72a03643558dc54dd334615de552a6623ee5ba0ed82ad36506c2f2f70fb8dc41",
    }
    authorization = yaml.safe_load(
        V02_FINAL_AUTHORIZATION_PATH.read_text(encoding="utf-8")
    )
    assert payload["authorization"] == {
        "authority": "current-user",
        "record_id": authorization["id"],
        "confirmed_at_utc": authorization["authorization"]["confirmed_at_utc"],
        "record_created_at_utc": authorization["authorization"][
            "record_created_at_utc"
        ],
        "generation_authorized": True,
        "publication_authorized": False,
    }
    assert payload["source_fixture"]["sha256"] == _sha256(
        REPO_ROOT / payload["source_fixture"]["locator"]
    )
    assert payload["delivery_manifest"]["sha256"] == _sha256(
        REPO_ROOT / payload["delivery_manifest"]["locator"]
    )
    assert payload["forward_generation"] == {
        "status": "passed",
        "generation_receipt": {
            "locator": V02_GENERATION_RECEIPT_PATH.relative_to(REPO_ROOT).as_posix(),
            "sha256": _sha256(V02_GENERATION_RECEIPT_PATH),
        },
        "calls_used": 2,
        "maximum_total_calls": 4,
        "publication_performed": False,
    }
    assert payload["independent_qa"] == {
        "locator": V02_QA_RESULT_PATH.relative_to(REPO_ROOT).as_posix(),
        "sha256": _sha256(V02_QA_RESULT_PATH),
        "status": "passed",
        "p1": 0,
        "p2": 0,
        "required_gate_rows": 188,
    }
    assert payload["runtime_receipt"] == {
        "locator": V02_RUNTIME_RECEIPT_PATH.relative_to(REPO_ROOT).as_posix(),
        "sha256": _sha256(V02_RUNTIME_RECEIPT_PATH),
        "status": "passed",
    }
    workflow = yaml.safe_load(
        (EXAMPLE_ROOT / "full-workflow.yaml").read_text(encoding="utf-8")
    )
    manifest = yaml.safe_load(
        (EXAMPLE_ROOT / "delivery-manifest.yaml").read_text(encoding="utf-8")
    )
    asset_briefs = {
        brief["id"]: brief
        for brief in workflow["contracts"]["asset_briefs"]
    }
    assert workflow["contracts"]["selection_lock"]["status"] == "passed"
    assert workflow["contracts"]["ecommerce_asset_plan"]["status"] == "passed"
    assert all(brief["status"] == "passed" for brief in asset_briefs.values())
    manifest_rows = {
        row["requested_artifact_id"]: row for row in manifest["artifacts"]
    }
    receipt_ids = [
        row["requested_artifact_id"] for row in payload["gallery_artifacts"]
    ]
    assert len(manifest_rows) == len(manifest["requested_artifact_ids"])
    assert len(receipt_ids) == len(set(receipt_ids))
    assert Counter(receipt_ids) == Counter(manifest["requested_artifact_ids"])
    assert Counter(receipt_ids) == Counter(
        row["requested_artifact_id"] for row in manifest["artifacts"]
    )
    for receipt_row in payload["gallery_artifacts"]:
        manifest_row = manifest_rows[receipt_row["requested_artifact_id"]]
        brief = asset_briefs[manifest_row["asset_brief_id"]]
        assert receipt_row["asset_brief_id"] == brief["id"]
        assert receipt_row["role"] == manifest_row["role"] == brief["role"]
        assert (
            receipt_row["expected_package_identity_sha256"]
            == manifest_row["expected_package_identity_sha256"]
            == brief["package_identity_sha256"]
        )
        assert receipt_row["review_profile_ids"] == manifest_row["review_profile_ids"]
        assert receipt_row["artifact_id"] == manifest_row["artifact_id"]
        assert receipt_row["locator"] == manifest_row["locator"]
        assert receipt_row["sha256"] == manifest_row["sha256"]
        assert receipt_row["status"] == manifest_row["status"] == "passed"
        assert receipt_row["blocking_reason"] == manifest_row["blocking_reason"]
        assert receipt_row["blocking_reason"] is None
        artifact_path = REPO_ROOT / receipt_row["locator"]
        assert artifact_path.is_file()
        assert receipt_row["sha256"] == _sha256(artifact_path)
    assert manifest["completeness_status"] == "passed"
    assert manifest["per_image_qa_status"] == "pass"
    assert manifest["cross_set_qa_status"] == "pass"


def test_v02_historical_authorization_preserves_the_pre_correction_blocked_record():
    authorization = yaml.safe_load(V02_AUTHORIZATION_PATH.read_text(encoding="utf-8"))

    assert authorization["schema_version"] == 1
    assert authorization["id"] == "public-fictional-v02-approval-2026-09-09"
    assert authorization["evidence_kind"] == "current-user-generation-authorization"
    assert authorization["status"] == "blocked"
    assert authorization["historical_authorization_status"] == "passed"
    assert authorization["record_role"] == "superseded-pre-correction-authorization"
    assert authorization["superseded_by"] == (
        "public-fictional-v02-final-build-authorization-2026-09-09"
    )
    assert authorization["applies_to_final_run"] is False
    assert authorization["status_reason"] == (
        "This historical record binds the pre-correction transform only. It did not "
        "authorize the QA-corrected transform, and its blocked status does not describe "
        "the later final run, which has a separate current-user authorization record."
    )
    assert authorization["authorization"]["authority"] == "current-user"
    assert authorization["authorization"]["confirmed_at_utc"].startswith("2026-09-09T")
    assert authorization["authorization"]["confirmed_at_utc"].endswith("Z")

    scope = authorization["approved_scope"]
    assert scope["selection_lock_id"] == "fictional-pantry-selection-lock-v02"
    assert scope["selected_direction_id"] == "quiet-pantry"
    assert scope["selected_sku_ids"] == ["lemon-ginger", "berry-oat"]
    assert scope["required_roles"] == [
        "catalog",
        "detail",
        "usage",
        "specification",
        "context",
        "campaign",
        "channel-variant",
    ]
    assert scope["source_artifact_sha256"] == (
        "a2c1d38551febace8a1bfec48011e7e36528695e244ec892d2c4fa4ad3d4f4fb"
    )
    assert scope["package_identity_sha256"] == (
        "39d1ee7e7ea63ab815eadb9667ece008f3183db388350154d4a9f70ade1ab758"
    )
    assert authorization["transform_binding"] == {
        "locator": "transforms/v0.2/2026-09-09/transform-spec-2026-09-09.json",
        "sha256": "838ab559d9686d1e17e9d4e145c4a5ed60386fe6de6c143e56941a61df4f0952",
    }
    transform_path = EXAMPLE_ROOT / authorization["transform_binding"]["locator"]
    current_transform = authorization["current_transform_check"]
    assert current_transform == {
        "checked_on": "2026-09-09",
        "observed_sha256": _sha256(transform_path),
        "status": "mismatch",
        "generation_authorized": False,
        "requires_new_current_user_confirmation": True,
    }
    assert current_transform["observed_sha256"] != authorization["transform_binding"][
        "sha256"
    ]
    assert authorization["current_scope_status"] == {
        "decision_lock": "passed",
        "selection_lock": "passed",
        "ecommerce_asset_plan": "passed",
        "asset_briefs": "passed",
        "ecommerce_generation": "blocked",
        "qa_delivery": "not-run",
    }

    assert authorization["usage_scene_constraint"] == (
        "For this fictional concept, the unopened Berry Oat pouch may be shown beside "
        "one empty clear glass as a pre-opening setup. No preparation, dosage, serving, "
        "consumption, or performance instruction is defined."
    )
    assert authorization["specification_constraint"] == (
        "Show only the approved 240 g quantity as source-derived package pixels; do not "
        "invent dimensions, counts, callout labels, legal clearance, or production specifications."
    )

    qa = authorization["qa_plan"]
    assert len(qa["required_gate_ids"]) == 13
    assert len(qa["cross_set_required_gate_ids"]) == 6
    assert qa["required_profile_ids"] == ["full-resolution", "ecommerce-thumbnail"]
    assert qa["expected_gate_rows"] == 188
    assert qa["expected_gate_rows"] == (
        len(scope["required_roles"]) * len(qa["required_gate_ids"]) * 2
        + len(qa["cross_set_required_gate_ids"])
    )

    assert authorization["generation_budget"] == {
        "paid_calls_allowed": True,
        "maximum_total_calls": 4,
        "maximum_calls_per_background_plate": 2,
        "deterministic_roles": [
            "catalog",
            "detail",
            "specification",
            "campaign",
            "channel-variant",
        ],
        "external_background_plate_roles": ["usage", "context"],
    }
    assert authorization["output"] == {
        "root": "generated/v0.2/2026-09-09",
        "overwrite": False,
        "retention_policy": "preserve",
        "publication_authorized": False,
    }
    assert authorization["publication"] == {
        "authorized": False,
        "requires_new_current_user_confirmation": True,
    }


def test_v02_final_authorization_matches_current_transform_and_keeps_publication_closed():
    authorization = yaml.safe_load(
        V02_FINAL_AUTHORIZATION_PATH.read_text(encoding="utf-8")
    )

    assert authorization["schema_version"] == 1
    assert authorization["id"] == (
        "public-fictional-v02-final-build-authorization-2026-09-09"
    )
    assert authorization["evidence_kind"] == (
        "current-user-generation-authorization-public-record"
    )
    assert authorization["status"] == "passed"
    source_record = authorization["source_record"]
    assert source_record["snapshot_level"] == "redacted"
    assert source_record["sha256"] == (
        "a30e4a586b84afc0425f2d826f4acb9d631be6e6b1c1aa433309151f136f9da3"
    )
    assert source_record["record_created_at_utc"] == "2026-09-09T08:55:19Z"
    assert "write time" in source_record["timestamp_correction"]
    assert source_record["omissions"] == [
        "External local background-plate input locators were replaced with repository-relative retained artifact locators."
    ]
    assert source_record["additions"] == [
        "post_run_scope_status was added from the bound generation receipt and independent QA result; current_scope_status preserves the authorization-time values."
    ]
    auth = authorization["authorization"]
    assert auth["authority"] == "current-user"
    assert auth["basis"] == "同意"
    assert auth["confirmed_at_utc"] == "2026-09-09T08:47:30Z"
    assert auth["record_created_at_utc"] == "2026-09-09T08:55:19Z"
    assert auth["approval_message_sha256"] == (
        "905819e2e3a059a02087855e9f326d05c877c1767ec31dc012c5c44652840230"
    )
    assert re.fullmatch(r"[0-9a-f]{64}", auth["confirmation_evidence_sha256"])
    current_transform = authorization["current_transform_check"]
    transform_path = EXAMPLE_ROOT / authorization["transform_binding"]["locator"]
    assert current_transform == {
        "checked_on": "2026-09-09",
        "observed_sha256": _sha256(transform_path),
        "status": "match",
        "generation_authorized": True,
        "requires_new_current_user_confirmation": False,
    }
    assert authorization["transform_binding"]["sha256"] == current_transform[
        "observed_sha256"
    ]
    assert authorization["current_scope_status"] == {
        "selection_lock": "passed",
        "ecommerce_asset_plan": "passed",
        "asset_briefs": "passed",
        "ecommerce_generation": "authorized",
        "qa_delivery": "not-run",
    }
    assert authorization["post_run_scope_status"] == {
        "ecommerce_generation": "passed",
        "qa_delivery": "passed",
        "evidence": {
            "generation_receipt": {
                "locator": "examples/fictional-pantry-product/generation-receipt-v0.2-2026-09-09.yaml",
                "sha256": _sha256(EXAMPLE_ROOT / "generation-receipt-v0.2-2026-09-09.yaml"),
            },
            "qa_result": {
                "locator": "examples/fictional-pantry-product/qa-result-v0.2-2026-09-09.yaml",
                "sha256": _sha256(EXAMPLE_ROOT / "qa-result-v0.2-2026-09-09.yaml"),
            },
        },
    }
    assert len(authorization["background_plates"]) == 2
    assert sum(
        plate["clean_attempt"]["call_count"]
        for plate in authorization["background_plates"]
    ) == 2
    for plate in authorization["background_plates"]:
        path = REPO_ROOT / plate["locator"]
        assert plate["locator_type"] == "relative_path"
        assert not Path(plate["locator"]).is_absolute()
        assert path.is_file()
        assert plate["sha256"] == _sha256(path)
        assert plate["provenance"]["embedded_private_data"] is False
        assert plate["provenance"]["publication_allowed"] is False
    assert authorization["publication"] == {
        "authorized": False,
        "performed": False,
        "requires_new_current_user_confirmation": True,
    }


def test_receipts_cover_every_prompt_bound_root_and_object():
    receipts = _load_receipts()

    for mode, receipt in receipts.items():
        runtime = receipt["contract_snapshot"]["normalized_contract"]
        resolved = receipt["contract_snapshot"]["resolved_permissions"]
        field_roots = {
            item["subject_id_or_path"]
            for item in resolved
            if item["subject_type"] == "field"
        }
        assert field_roots == COMMON_PROMPT_ROOTS | MODE_PROMPT_ROOTS[mode]

        by_type = {
            subject_type: {
                item["subject_id_or_path"]
                for item in resolved
                if item["subject_type"] == subject_type
            }
            for subject_type in {"fact", "source", "copy", "asset", "output"}
        }
        assert by_type["fact"] == {
            item["id"] for item in runtime["product"]["verified_facts"]
        }
        assert by_type["source"] == {item["id"] for item in runtime["sources"]}
        assert by_type["copy"] == {"/exact_copy"}
        assert by_type["asset"] == {item["id"] for item in runtime["assets"]}
        assert by_type["output"] == {"/output"}

        for item in resolved:
            assert set(item["permissions"]) == PERMISSION_KEYS
            assert item["permissions"]["external_processing_allowed"] is True
            assert item["permissions"]["derivative_allowed"] is True
            assert item["permissions"]["publication_allowed"] is True
            assert item["authorization_source"] == "current-user"


def test_artifacts_are_safe_relative_paths_inside_the_declared_output_root():
    receipts = _load_receipts()

    for receipt in receipts.values():
        runtime = receipt["contract_snapshot"]["normalized_contract"]
        output_root = (REPO_ROOT / runtime["output"]["root"]).resolve()
        assert runtime["output"]["delivery"] == "relative-path"
        assert not Path(runtime["output"]["root"]).is_absolute()

        assert [item["id"] for item in receipt["artifacts"]] == receipt[
            "requested_artifact_ids"
        ]
        for artifact in receipt["artifacts"]:
            locator = Path(artifact["locator"])
            assert artifact["locator_type"] == "relative_path"
            assert not locator.is_absolute()
            assert ".." not in locator.parts
            artifact_path = (REPO_ROOT / locator).resolve()
            assert artifact_path.is_relative_to(output_root)
            assert artifact_path.is_file()
            assert artifact["sha256"] == _sha256(artifact_path)
            assert artifact["status"] == "passed"
            assert artifact["blocking_reason"] is None


def test_attempt_ledgers_preserve_every_forward_run_output_within_budget():
    receipts = _load_receipts()
    expected_counts = {"compare": 3, "refine": 2, "present": 1}

    for mode, receipt in receipts.items():
        runtime = receipt["contract_snapshot"]["normalized_contract"]
        attempts = receipt["generation_receipt"]["attempts"]
        assert len(attempts) == expected_counts[mode]
        assert len(attempts) <= runtime["generation_budget"]["maximum_total_calls"]
        assert runtime["output"]["retention_policy"] == "preserve"
        assert len({attempt["attempt_id"] for attempt in attempts}) == len(attempts)

        passed_outputs = set()
        times = []
        for attempt in attempts:
            times.append(
                datetime.fromisoformat(
                    attempt["executed_at_utc"].replace("Z", "+00:00")
                )
            )
            assert attempt["outputs"]
            for output in attempt["outputs"]:
                path = REPO_ROOT / output["locator"]
                assert output["locator_type"] == "relative_path"
                assert path.is_file()
                assert output["sha256"] == _sha256(path)
                if attempt["outcome"] == "passed":
                    passed_outputs.add(output["locator"])
        assert times == sorted(times)
        assert {artifact["locator"] for artifact in receipt["artifacts"]} <= passed_outputs

    refine_attempts = receipts["refine"]["generation_receipt"]["attempts"]
    assert [attempt["outcome"] for attempt in refine_attempts] == ["failed", "passed"]
    assert refine_attempts[0]["failure_class"] == "selection-lock-drift"
    compare_attempts = receipts["compare"]["generation_receipt"]["attempts"]
    assert [attempt["outcome"] for attempt in compare_attempts] == [
        "passed",
        "failed",
        "passed",
    ]
    assert compare_attempts[1]["failure_class"] == "direction-comparability"


def test_refine_and_present_use_independent_fixed_source_locks():
    receipts = _load_receipts()
    expected = {
        "refine": (
            "refine-source",
            "assets/refine-source.png",
            ["refine-source", "present-source"],
        ),
        "present": (
            "present-source",
            "assets/present-source.png",
            ["present-source"],
        ),
    }

    for mode, (asset_id, locator, input_asset_ids) in expected.items():
        receipt = receipts[mode]
        runtime = receipt["contract_snapshot"]["normalized_contract"]
        lock = runtime["selection_lock"]
        source_path = EXAMPLE_ROOT / locator
        assert lock["source_artifact_id"] == asset_id
        assert lock["source_artifact_sha256"] == _sha256(source_path)
        assert lock["approved_by"] == "current-user"
        assert lock["approval_basis"].strip()
        assert receipt["generation_receipt"]["input_asset_ids"] == input_asset_ids


def test_receipts_bind_qa_plans_and_complete_required_pass_matrices():
    receipts = _load_receipts()

    for receipt in receipts.values():
        runtime = receipt["contract_snapshot"]["normalized_contract"]
        plan = runtime["qa_plan"]
        assert plan["sha256"] == _canonical_qa_hash(plan)
        assert receipt["qa"]["plan_sha256"] == plan["sha256"]

        expected = {
            (artifact_id, gate_id, profile)
            for artifact_id in receipt["requested_artifact_ids"]
            for gate_id in plan["required_gate_ids"]
            for profile in plan["review_profiles"]
        }
        gates = receipt["qa"]["gates"]
        actual = [
            (gate["artifact_id"], gate["gate_id"], gate["profile"])
            for gate in gates
        ]
        assert set(actual) == expected
        assert len(actual) == len(expected)
        assert set(Counter(actual).values()) == {1}
        assert all(gate["level"] == "required" for gate in gates)
        assert all(gate["status"] == "pass" for gate in gates)
        assert all(gate["evidence"].strip() for gate in gates)
        assert receipt["status"] == "passed"
        assert receipt["qa"]["required_failures"] == []

        assert plan["independent_review_required"] is True
        assert receipt["qa"]["reviewed_by"] == "independent-agent"
        assert receipt["qa"]["reviewer_id"].strip()
        assert receipt["qa"]["reviewer_id"] != receipt["generation_receipt"][
            "executor_id"
        ]
