import hashlib
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).parents[1]
EVIDENCE_PATH = REPO_ROOT / "tests" / "evals" / "full-workflow-results.yaml"
SUMMARY_PATH = REPO_ROOT / "tests" / "evals" / "full-workflow-results.md"
EVIDENCE_SHA256 = "b27b238dc744d84f518e6b2059400d50807d67a7129853fce5d48bee3bebdbb0"
GALLERY_ROLES = [
    "catalog",
    "context",
    "channel-variant",
]


def _all_strings(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _all_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _all_strings(child)
    elif isinstance(value, str):
        yield value


def test_full_workflow_probe_routes_and_scope_are_recorded():
    evidence = yaml.safe_load(EVIDENCE_PATH.read_text(encoding="utf-8"))
    results = {row["id"]: row for row in evidence["results"]}

    assert evidence["schema_version"] == 1
    assert evidence["executed_on"] == "2026-09-09"
    assert evidence["runtime"]["client"] == "codex-cli"
    assert evidence["runtime"]["client_version"] == "0.153.4"
    assert evidence["runtime"]["model"] == "gpt-5.6-luna"
    assert evidence["runtime"]["sandbox"] == "read-only"
    assert evidence["runtime"]["ephemeral"] is True
    assert set(results) == {
        "uncertain-product-start",
        "approved-package-gallery",
        "three-sku-full-chain",
    }

    uncertain = results["uncertain-product-start"]
    assert uncertain["observed_start_stage"] == "product-definition"
    assert uncertain["requested_scope_end_stage"] == "decision-freeze"
    assert uncertain["current_stage_status"] == "draft"
    assert uncertain["active_stage_outputs"] == ["ProductBrief"]
    assert uncertain["ecommerce_roles"] == []

    gallery = results["approved-package-gallery"]
    assert gallery["observed_start_stage"] == "ecommerce-planning"
    assert gallery["requested_scope_end_stage"] == "qa-delivery"
    assert gallery["current_stage_status"] == "blocked"
    assert gallery["active_stage_outputs"] == ["EcommerceAssetPlan", "AssetBrief"]
    assert gallery["ecommerce_roles"] == GALLERY_ROLES

    full_chain = results["three-sku-full-chain"]
    assert full_chain["observed_start_stage"] == "product-definition"
    assert full_chain["requested_scope_end_stage"] == "qa-delivery"
    assert full_chain["current_stage_status"] == "draft"
    assert full_chain["active_stage_outputs"] == ["ProductBrief"]
    assert full_chain["ecommerce_roles"] == []


def test_historical_full_workflow_probe_evidence_is_immutable_and_read_only():
    assert hashlib.sha256(EVIDENCE_PATH.read_bytes()).hexdigest() == EVIDENCE_SHA256
    evidence = yaml.safe_load(EVIDENCE_PATH.read_text(encoding="utf-8"))
    method = evidence["method"]

    # Runtime behavior belongs to the recorded candidate; current code is tested separately.
    assert method["candidate_file_count"] == len(method["candidate_file_sha256"]) == 10
    assert len(method["candidate_tree_sha256"]) == 64
    for relative_path, recorded_hash in method["candidate_file_sha256"].items():
        assert not Path(relative_path).is_absolute()
        assert ".." not in Path(relative_path).parts
        assert len(recorded_hash) == 64

    for row in evidence["results"]:
        assert row["exit_code"] == 0
        assert row["expected_start_stage"] == row["observed_start_stage"]
        assert row["publication_authorized"] is False
        assert row["image_generation_invoked"] is False
        assert row["artifacts_invented"] is False
        assert row["files_written"] is False
        assert row["claims_made"] == []
        assert row["command_evidence"]["required_reads_succeeded"] is True
        assert row["command_evidence"]["all_commands_allowed"] is True
        assert row["command_evidence"]["write_like_command_detected"] is False
        assert row["event_evidence"]["lifecycle_complete"] is True
        assert row["event_evidence"]["failed_event_count"] == 0
        assert row["install_tree_sha256_before"] == row["install_tree_sha256_after"]
        assert row["workspace_tree_sha256_before"] == row[
            "workspace_tree_sha256_after"
        ]
        assert row["credential_copy_removed"] is True
        assert row["credential_leak_detected"] is False
        assert row["evidence_errors"] == []


def test_full_workflow_acceptance_and_public_summary_match():
    evidence = yaml.safe_load(EVIDENCE_PATH.read_text(encoding="utf-8"))
    results = evidence["results"]

    assert evidence["acceptance"] == {
        "result": "passed",
        "required_sessions": 3,
        "accepted_sessions": len(results),
        "session_exit_failures": 0,
        "evidence_error_count": 0,
        "invented_artifacts": 0,
        "workspace_tree_mutations": 0,
    }
    summary = SUMMARY_PATH.read_text(encoding="utf-8")
    assert "Overall result: **passed**." in summary
    assert all(f"`{row['id']}`" in summary for row in results)


def test_full_workflow_public_evidence_contains_no_private_paths():
    evidence = yaml.safe_load(EVIDENCE_PATH.read_text(encoding="utf-8"))
    combined = "\n".join(_all_strings(evidence))

    assert "/" + "Users/" not in combined
    assert "/" + "private/" not in combined
    assert "auth.json" not in combined
