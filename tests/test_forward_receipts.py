from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_ROOT = REPO_ROOT / "examples" / "fictional-pantry-product"
RECEIPTS_PATH = REPO_ROOT / "tests" / "evals" / "forward-receipts.yaml"
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
