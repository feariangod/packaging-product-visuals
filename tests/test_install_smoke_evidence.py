import hashlib
import re
import subprocess
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).parents[1]
EVIDENCE_PATH = REPO_ROOT / "tests" / "evals" / "install-smoke-results.yaml"
SOURCE_SKILL = REPO_ROOT / "skills" / "packaging-product-visuals"
SHA256 = re.compile(r"[0-9a-f]{64}")


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


def _public_candidate_files():
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            "skills/packaging-product-visuals",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [REPO_ROOT / name for name in result.stdout.splitlines()]


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


def test_install_smoke_matrix_covers_the_five_required_fresh_sessions():
    evidence = yaml.safe_load(EVIDENCE_PATH.read_text(encoding="utf-8"))
    results = evidence["results"]
    candidate_files = _public_candidate_files()

    assert evidence["executed_on"] == "2026-09-08"
    assert evidence["runtime"] == {
        "client": "codex-cli",
        "client_version": "0.153.4",
        "model": "gpt-5.6-luna",
        "reasoning_effort": "low",
        "sandbox": "read-only",
        "ephemeral": True,
        "operating_system": {
            "name": "macOS",
            "version": "26.5",
            "build": "25F71",
            "architecture": "arm64",
        },
    }
    assert evidence["scenario"]["explicit_skill_invocation"] == "$packaging-product-visuals"
    assert evidence["method"]["accepted_fresh_session_count"] == 5
    assert evidence["method"]["standalone_session_count"] == 4
    assert evidence["method"]["plugin_session_count"] == 1
    assert evidence["method"]["public_candidate_file_count"] == len(candidate_files) == 7
    assert evidence["method"]["public_candidate_source"] == (
        "git ls-files --cached --others --exclude-standard"
    )
    assert evidence["method"]["source_skill_tree_sha256"] == (
        _public_candidate_tree_digest(candidate_files)
    )
    assert all("__pycache__" not in path.parts for path in candidate_files)
    assert all(path.suffix != ".pyc" for path in candidate_files)
    assert len(results) == 5
    assert {result["id"] for result in results} == {
        "explicit-codex-home-skills",
        "default-codex-home-skills",
        "user-agents-skills",
        "project-agents-skills",
        "local-marketplace-plugin",
    }


def test_each_install_smoke_session_loaded_the_skill_and_blocked_honestly():
    evidence = yaml.safe_load(EVIDENCE_PATH.read_text(encoding="utf-8"))
    source_digest = evidence["method"]["source_skill_tree_sha256"]

    assert SHA256.fullmatch(source_digest)
    for result in evidence["results"]:
        trace = result["load_trace"]
        outcome = result["outcome"]

        assert result["exit_code"] == 0
        assert SHA256.fullmatch(result["event_stream_sha256"])
        assert trace["event_type"] == "item.completed"
        assert trace["item_type"] == "command_execution"
        assert trace["skill_file"].endswith("/packaging-product-visuals/SKILL.md")
        assert trace["skill_read_exit_code"] == 0
        assert trace["reference_file"].endswith(
            "/packaging-product-visuals/references/contracts.md"
        )
        assert trace["reference_read_exit_code"] == 0
        assert outcome == {
            "skill_discovered": True,
            "skill_loaded": True,
            "relative_reference_resolved": True,
            "capability_gap_reported": "image_generation_unavailable",
            "status": "blocked",
            "artifact_invented": False,
            "files_written": False,
        }
        assert result["install_tree_sha256_before"] == source_digest
        assert result["install_tree_sha256_after"] == source_digest


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
    assert plugin["load_trace"]["initial_path_probe_exit_code"] == 1
    installation = evidence["plugin_installation"]
    cache_audit = installation.pop("cache_audit")
    assert installation == {
        "marketplace_name": "ppv-install-smoke",
        "marketplace_source": "isolated local filesystem marketplace",
        "distribution": "skills-only plugin",
        "distribution_contents": [
            ".codex-plugin/plugin.json",
            "skills/packaging-product-visuals/",
            "LICENSE",
        ],
        "marketplace_add_exit_code": 0,
        "plugin_add_exit_code": 0,
        "plugin_list_exit_code": 0,
        "plugin_id": "packaging-product-visuals@ppv-install-smoke",
        "plugin_version": "0.1.0",
        "installed": True,
        "enabled": True,
        "remote_catalog_required": False,
    }
    candidate_files = _public_candidate_files()
    expected_cache_files = sorted(
        [".codex-plugin/plugin.json", "LICENSE"]
        + [path.relative_to(REPO_ROOT).as_posix() for path in candidate_files]
    )
    assert cache_audit == {
        "installed_file_count": len(expected_cache_files),
        "installed_skill_file_count": len(candidate_files),
        "pyc_file_count": 0,
        "unexpected_files": [],
        "installed_files": expected_cache_files,
    }
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
        "skill_discovery_successes": sum(
            result["outcome"]["skill_discovered"] for result in results
        ),
        "skill_load_successes": sum(result["outcome"]["skill_loaded"] for result in results),
        "relative_reference_successes": sum(
            result["outcome"]["relative_reference_resolved"] for result in results
        ),
        "honest_capability_blocks": sum(
            result["outcome"]["status"] == "blocked" for result in results
        ),
        "invented_artifacts": sum(result["outcome"]["artifact_invented"] for result in results),
        "install_tree_mutations": sum(
            result["install_tree_sha256_before"] != result["install_tree_sha256_after"]
            for result in results
        ),
        "session_exit_failures": sum(result["exit_code"] != 0 for result in results),
    }
