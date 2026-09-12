import hashlib
import json
from datetime import datetime
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).parents[1]
EVALS_ROOT = REPO_ROOT / "tests" / "evals"
V01_ROUTING_CASES_PATH = EVALS_ROOT / "v0.1-routing-cases.yaml"


def test_behavior_probe_output_schemas_are_valid_json():
    for name in (
        "routing-output.schema.json",
        "routing-batch-output.schema.json",
        "contract-probe-output.schema.json",
    ):
        document = json.loads((EVALS_ROOT / name).read_text(encoding="utf-8"))
        assert document["$schema"].startswith("https://json-schema.org/")
        assert document["additionalProperties"] is False


def test_v01_fresh_session_routing_results_match_archived_declared_cases():
    declared = {
        case["id"]: case
        for case in yaml.safe_load(
            V01_ROUTING_CASES_PATH.read_text(encoding="utf-8")
        )["cases"]
    }
    evidence = yaml.safe_load((EVALS_ROOT / "routing-results.yaml").read_text(encoding="utf-8"))
    observed = evidence["results"]

    assert evidence["runtime"]["ephemeral"] is True
    assert evidence["runtime"]["ignore_user_config"] is True
    assert evidence["runtime"]["sandbox"] == "read-only"
    assert evidence["runtime"]["home_isolated_per_run"] is True
    assert evidence["runtime"]["codex_home_isolated_per_run"] is True
    assert evidence["runtime"]["only_user_installed_skill"] == "packaging-product-visuals"
    assert evidence["method"]["fresh_session_count"] == 36
    assert evidence["method"]["trials_per_case"] == 3
    assert evidence["method"]["underlying_request_explicit_skill_requested"] is False
    assert evidence["method"]["failed_retries"] == 0
    assert len(observed) == 36

    by_case = {case_id: [] for case_id in declared}
    for result in observed:
        assert result["case_id"] in declared
        by_case[result["case_id"]].append(result)
        assert result["client"] == "codex-cli 0.153.4"
        assert result["model"] == "gpt-5.6-luna"
        assert result["reasoning_effort"] == "low"
        assert result["explicit_skill_requested"] is False
        assert isinstance(result["skill_file_read_observed"], bool)
        assert result["successful_attempt"] >= 1

    assert set(by_case) == set(declared)
    high_risk_misroutes = 0
    for case_id, expected in declared.items():
        results = by_case[case_id]
        assert len(results) == 3
        assert {result["trial"] for result in results} == {1, 2, 3}

        for result in results:
            assert result["scope"] == expected["expected_scope"]
            assert result["mode"] == expected["expected_mode"]
            if expected["expected_scope"] == "in-scope":
                assert result["selected_skill"] == expected["expected_route"]
            else:
                if result["selected_skill"] is not None or result["mode"] is not None:
                    high_risk_misroutes += 1
                assert result["selected_skill"] is None
                assert result["mode"] is None

        if expected["expected_scope"] == "in-scope":
            assert any(result["skill_file_read_observed"] for result in results)

    assert high_risk_misroutes == 0
    assert evidence["acceptance"]["positive_hits"] == 9
    assert evidence["acceptance"]["negative_null_routes"] == 27
    assert evidence["acceptance"]["high_risk_misroutes"] == 0


def test_fresh_session_contract_probe_matches_declared_outcomes():
    declared_cases = yaml.safe_load(
        (EVALS_ROOT / "contract-probe-cases.yaml").read_text(encoding="utf-8")
    )["cases"]
    declared = {case["id"]: case["expected_decision"] for case in declared_cases}
    evidence = yaml.safe_load(
        (EVALS_ROOT / "contract-probe-results.yaml").read_text(encoding="utf-8")
    )
    observed = {case["id"]: case["decision"] for case in evidence["results"]}

    assert evidence["runtime"]["ephemeral"] is True
    assert evidence["runtime"]["ignore_user_config"] is True
    assert evidence["runtime"]["sandbox"] == "read-only"
    assert evidence["runtime"]["home_isolated"] is True
    assert evidence["runtime"]["codex_home_isolated"] is True
    assert evidence["runtime"]["only_user_installed_skill"] == "packaging-product-visuals"
    assert evidence["runtime"]["client"] == "codex-cli"
    assert evidence["runtime"]["client_version"] == "0.153.4"
    assert evidence["runtime"]["model"] == "gpt-5.6-luna"
    assert evidence["runtime"]["reasoning_effort"] == "low"
    assert evidence["method"]["fresh_session_count"] == 1
    assert evidence["method"]["cases_in_session"] == len(declared_cases)
    assert evidence["method"]["failed_retries"] == 0
    assert evidence["method"]["skill_file_read_observed"] is True
    assert [result["id"] for result in evidence["results"]] == [
        case["id"] for case in declared_cases
    ]
    assert observed == declared

    execution = evidence["evidence"]
    assert execution["exit_code"] == 0
    assert evidence["executed_at_utc"] == execution["completed_at_utc"]
    assert datetime.fromisoformat(execution["started_at_utc"].replace("Z", "+00:00"))
    assert datetime.fromisoformat(execution["completed_at_utc"].replace("Z", "+00:00"))

    structured_output = {"results": evidence["results"]}
    canonical = json.dumps(
        structured_output,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    recorded_hash = execution["structured_output_hash"]
    assert recorded_hash["algorithm"] == "sha256"
    assert recorded_hash["basis"] == "canonical-json-results-object"
    assert recorded_hash["canonical_byte_length"] == len(canonical)
    assert recorded_hash["digest"] == hashlib.sha256(canonical).hexdigest()

    evidence_text = (EVALS_ROOT / "contract-probe-results.yaml").read_text(encoding="utf-8")
    forbidden_roots = tuple("/" + part for part in ("Users/", "private/", "tmp/"))
    assert not any(path in evidence_text for path in forbidden_roots)
