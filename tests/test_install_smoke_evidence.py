import hashlib
import re
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).parents[1]
EVIDENCE_PATH = REPO_ROOT / "tests" / "evals" / "install-smoke-results.yaml"
V01_EVIDENCE_PATH = REPO_ROOT / "tests" / "evals" / "v0.1-install-smoke-results.yaml"
SOURCE_SKILL = REPO_ROOT / "skills" / "packaging-product-visuals"
SHA256 = re.compile(r"[0-9a-f]{64}")
V01_EVIDENCE_SHA256 = "13b47b23fcf159e26517df0cbeef4e7f041d6141f5563003f86f0ab2de5d8d71"
V02_EVIDENCE_SHA256 = "48bec2b02aaa4245888261ed73cc9d1e6a17872c830bff6cfbf9e1321912d297"


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


def _public_candidate_tree_digest(paths):
    digest = hashlib.sha256()
    for path in sorted(
        paths,
        key=lambda candidate: candidate.relative_to(SOURCE_SKILL).as_posix(),
    ):
        digest.update(path.relative_to(SOURCE_SKILL).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def test_public_candidate_digest_does_not_inherit_platform_path_sorting():
    class CaseInsensitivePath:
        def __init__(self, relative_path, content):
            self.relative_path = relative_path
            self.content = content

        def __lt__(self, other):
            return self.relative_path.casefold() < other.relative_path.casefold()

        def relative_to(self, root):
            assert root == SOURCE_SKILL
            return Path(self.relative_path)

        def read_bytes(self):
            return self.content

    paths = [
        CaseInsensitivePath("SKILL.md", b"skill"),
        CaseInsensitivePath("agents/openai.yaml", b"agent"),
    ]
    expected = hashlib.sha256(
        b"SKILL.mdskillagents/openai.yamlagent"
    ).hexdigest()

    assert _public_candidate_tree_digest(paths) == expected


def test_v01_install_smoke_evidence_is_preserved_byte_for_byte():
    assert hashlib.sha256(V01_EVIDENCE_PATH.read_bytes()).hexdigest() == (
        V01_EVIDENCE_SHA256
    )
    evidence = yaml.safe_load(V01_EVIDENCE_PATH.read_text(encoding="utf-8"))
    assert evidence["schema_version"] == 1
    assert evidence["executed_on"] == "2026-09-08"
    assert evidence["plugin_installation"]["plugin_version"] == "0.1.0"


def test_historical_install_smoke_matrix_preserves_the_five_recorded_sessions():
    assert hashlib.sha256(EVIDENCE_PATH.read_bytes()).hexdigest() == V02_EVIDENCE_SHA256
    evidence = yaml.safe_load(EVIDENCE_PATH.read_text(encoding="utf-8"))
    results = evidence["results"]
    candidate_files = evidence["method"]["public_candidate_file_sha256"]

    assert evidence["schema_version"] == 2
    assert evidence["executed_on"] == "2026-09-09"
    runtime = evidence["runtime"]
    assert runtime["client"] == "codex-cli"
    assert runtime["client_version"] == "0.153.4"
    assert SHA256.fullmatch(runtime["client_executable_sha256"])
    assert runtime["model"] == "gpt-5.6-luna"
    assert runtime["reasoning_effort"] == "low"
    assert runtime["sandbox"] == "read-only"
    assert runtime["ephemeral"] is True
    assert runtime["operating_system"] == {
        "name": "macOS",
        "version": "26.5",
        "build": "25F71",
        "architecture": "arm64",
    }
    assert runtime["capture_basis"]["client_version"] == "codex --version"
    assert evidence["scenario"]["explicit_skill_invocation"] == "$packaging-product-visuals"
    assert evidence["method"]["required_fresh_session_count"] == 5
    assert evidence["method"]["standalone_session_count"] == 4
    assert evidence["method"]["plugin_session_count"] == 1
    assert evidence["method"]["runtime_discovery"] == (
        "codex app-server skills/list with forceReload=true for each layout"
    )
    assert evidence["method"]["public_candidate_file_count"] == len(candidate_files) == 10
    assert evidence["method"]["public_candidate_source"] == (
        "git ls-files --cached --others --exclude-standard"
    )
    # These immutable receipts describe the September 9 candidate, not today's source.
    assert SHA256.fullmatch(evidence["method"]["source_skill_tree_sha256"])
    assert all(SHA256.fullmatch(value) for value in candidate_files.values())
    assert all("__pycache__" not in Path(name).parts for name in candidate_files)
    assert all(Path(name).suffix != ".pyc" for name in candidate_files)
    assert len(results) == 5
    assert {result["id"] for result in results} == {
        "explicit-codex-home-skills",
        "default-codex-home-skills",
        "user-agents-skills",
        "project-agents-skills",
        "local-marketplace-plugin",
    }


def test_each_install_smoke_session_reports_only_observed_install_and_behavior_evidence():
    evidence = yaml.safe_load(EVIDENCE_PATH.read_text(encoding="utf-8"))
    source_digest = evidence["method"]["source_skill_tree_sha256"]

    assert SHA256.fullmatch(source_digest)
    for result in evidence["results"]:
        outcome = result["outcome"]

        assert result["exit_code"] == 0
        assert SHA256.fullmatch(result["event_stream_sha256"])
        assert result["event_evidence"]["lifecycle_complete"] is True
        assert result["event_evidence"]["failed_event_count"] == 0
        assert result["command_evidence"]["unexpected_command_count"] == 0
        assert result["command_evidence"]["nonzero_command_exit_count"] == 0
        assert result["command_evidence"]["write_like_command_detected"] is False
        assert outcome == {
            "skill_discovered_and_enabled": True,
            "structured_skill_invocation_reported": True,
            "reference_file_present_and_hashed": True,
            "agent_file_reads_observed": False,
            "capability_gap_reported": "image_generation_unavailable",
            "status": "blocked",
            "artifact_invented": False,
            "files_written": False,
        }
        assert result["install_tree_sha256_before"] == source_digest
        assert result["install_tree_sha256_after"] == source_digest
        assert result["workspace_tree_sha256_before"] == result[
            "workspace_tree_sha256_after"
        ]
        assert result["credential_copy_mode"] == "0600"
        assert result["credential_copy_removed"] is True
        assert result["credential_leak_detected"] is False
        assert result["evidence_errors"] == []


def test_standalone_and_plugin_config_isolation_are_explicit():
    evidence = yaml.safe_load(EVIDENCE_PATH.read_text(encoding="utf-8"))
    standalone = [
        result for result in evidence["results"] if result["distribution"] == "standalone"
    ]
    plugin = next(
        result
        for result in evidence["results"]
        if result["id"] == "local-marketplace-plugin"
    )

    assert len(standalone) == 4
    assert all(result["environment"]["ignore_user_config"] is True for result in standalone)
    assert plugin["environment"]["ignore_user_config"] is False
    assert "plugin enablement" in plugin["environment"]["ignore_user_config_reason"]
    assert plugin["discovered_skill_id"] == "packaging-product-visuals:packaging-product-visuals"
    installation = evidence["plugin_installation"]
    assert installation["marketplace_name"] == "ppv-install-smoke"
    assert installation["marketplace_source"] == "isolated local filesystem marketplace"
    assert installation["distribution"] == "skills-only plugin"
    assert installation["distribution_contents"] == [
        ".codex-plugin/plugin.json",
        "skills/packaging-product-visuals/",
        "LICENSE",
    ]
    assert installation["plugin_id"] == "packaging-product-visuals@ppv-install-smoke"
    assert installation["plugin_version"] == "0.2.0"
    assert installation["installed"] is True
    assert installation["enabled"] is True
    assert installation["plugin_list_source_inside_private_session"] is True
    assert installation["remote_catalog_required"] is False
    receipts = installation["command_receipts"]
    assert set(receipts) == {"marketplace-add", "plugin-add", "plugin-list"}
    for receipt in receipts.values():
        assert receipt["exit_code"] == 0
        assert receipt["json_output"] is True
        assert receipt["credential_leak_detected"] is False
        assert SHA256.fullmatch(receipt["stdout_sha256"])
        assert SHA256.fullmatch(receipt["stderr_sha256"])

    cache_audit = installation["cache_audit"]
    candidate_files = evidence["method"]["public_candidate_file_sha256"]
    expected_cache_files = sorted(
        [".codex-plugin/plugin.json", "LICENSE"]
        + [
            "skills/packaging-product-visuals/"
            + relative_path
            for relative_path in candidate_files
        ]
    )
    assert cache_audit["installed_file_count"] == len(expected_cache_files)
    assert cache_audit["installed_skill_file_count"] == len(candidate_files)
    assert cache_audit["pyc_file_count"] == 0
    assert cache_audit["unexpected_files"] == []
    assert cache_audit["missing_files"] == []
    assert cache_audit["installed_files"] == expected_cache_files
    assert not any("__pycache__" in name or name.endswith(".pyc") for name in expected_cache_files)


def test_install_smoke_evidence_contains_no_private_or_temporary_absolute_paths():
    evidence = yaml.safe_load(EVIDENCE_PATH.read_text(encoding="utf-8"))
    combined = "\n".join(_all_strings(evidence))

    assert "/" + "Users/" not in combined
    assert "/" + "private/" not in combined
    assert "auth.json" not in combined
    assert "ppv-install-smoke." not in combined


def test_install_smoke_acceptance_totals_match_the_rows():
    evidence = yaml.safe_load(EVIDENCE_PATH.read_text(encoding="utf-8"))
    acceptance = evidence["acceptance"]
    results = evidence["results"]

    assert acceptance == {
        "result": "passed",
        "accepted_sessions": len(results),
        "skill_discovery_and_enablement_successes": sum(
            result["outcome"]["skill_discovered_and_enabled"] for result in results
        ),
        "structured_skill_invocation_reports": sum(
            result["outcome"]["structured_skill_invocation_reported"]
            for result in results
        ),
        "reference_file_hash_successes": sum(
            result["outcome"]["reference_file_present_and_hashed"]
            for result in results
        ),
        "agent_file_read_successes": sum(
            result["outcome"]["agent_file_reads_observed"] for result in results
        ),
        "honest_capability_blocks": sum(
            result["outcome"]["status"] == "blocked" for result in results
        ),
        "invented_artifacts": sum(result["outcome"]["artifact_invented"] for result in results),
        "install_tree_mutations": sum(
            result["install_tree_sha256_before"] != result["install_tree_sha256_after"]
            for result in results
        ),
        "workspace_tree_mutations": sum(
            result["workspace_tree_sha256_before"]
            != result["workspace_tree_sha256_after"]
            for result in results
        ),
        "session_exit_failures": sum(result["exit_code"] != 0 for result in results),
        "evidence_error_count": sum(len(result["evidence_errors"]) for result in results),
    }
