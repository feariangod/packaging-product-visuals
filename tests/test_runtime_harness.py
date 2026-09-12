import hashlib
import json
import shlex
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import importlib.util


HARNESS_PATH = Path(__file__).parent / "evals" / "runtime_harness.py"
REPO_ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("runtime_harness", HARNESS_PATH)
assert SPEC is not None and SPEC.loader is not None
harness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(harness)


def _write_fake_codex(run_root: Path) -> str:
    executable = run_root.parent / "bin" / "codex"
    harness._write_bytes(
        executable,
        b"#!/bin/sh\nprintf 'codex-cli 1.2.3\\n'\n",
        private=True,
    )
    executable.chmod(0o700)
    return harness._resolve_codex_executable(str(executable))


def _write_runtime_receipt(
    run_root: Path,
    codex_bin: str,
) -> tuple[dict[str, object], dict[str, str]]:
    values = {
        "client-version": ([codex_bin, "--version"], "codex-cli 1.2.3\n"),
        "uname-system": (["/usr/bin/uname", "-s"], "Linux\n"),
        "uname-release": (["/usr/bin/uname", "-r"], "6.1.0-test\n"),
        "uname-build": (["/usr/bin/uname", "-v"], "test kernel build\n"),
        "uname-architecture": (["/usr/bin/uname", "-m"], "x86_64\n"),
    }
    commands = {}
    outputs = {}
    for label, (argv, stdout_text) in values.items():
        stdout = stdout_text.encode("utf-8")
        stderr = b""
        stdout_path = run_root / "runtime" / f"{label}.stdout.txt"
        stderr_path = run_root / "runtime" / f"{label}.stderr.txt"
        harness._write_bytes(stdout_path, stdout, private=True)
        harness._write_bytes(stderr_path, stderr, private=True)
        commands[label] = {
            "argv": argv,
            "exit_code": 0,
            "stdout_relative_path": stdout_path.relative_to(run_root).as_posix(),
            "stdout_sha256": harness.sha256_bytes(stdout),
            "stderr_relative_path": stderr_path.relative_to(run_root).as_posix(),
            "stderr_sha256": harness.sha256_bytes(stderr),
        }
        outputs[label] = stdout_text.strip()
    runtime = harness._runtime_from_command_outputs(
        client_line=outputs["client-version"],
        system_name=outputs["uname-system"],
        system_release=outputs["uname-release"],
        system_build=outputs["uname-build"],
        architecture=outputs["uname-architecture"],
        model=harness.MODEL,
        client_executable_sha256=harness.file_sha256(Path(codex_bin)),
    )
    receipt_path = run_root / "runtime" / "runtime-receipt.json"
    harness.write_json(
        receipt_path,
        {
            "public_runtime": runtime,
            "client_executable": {
                "resolved_path": codex_bin,
                "sha256": harness.file_sha256(Path(codex_bin)),
            },
            "commands": commands,
        },
        private=True,
    )
    return runtime, {
        "relative_path": receipt_path.relative_to(run_root).as_posix(),
        "sha256": harness.file_sha256(receipt_path),
    }


def _empty_runtime_temp_symlink_cleanup() -> dict[str, object]:
    return {
        "removed_count": 0,
        "removed": [],
    }


def _write_skill_discovery_artifacts(
    session: Path,
    install: Path,
    project: Path,
    codex_bin: str,
    *,
    scope: str,
    plugin_id: str | None = None,
) -> dict[str, object]:
    request_bytes = harness._skills_list_request_bytes(project)
    stdout = (
        json.dumps({"id": 0, "result": {"userAgent": "test"}}, sort_keys=True)
        + "\n"
        + json.dumps(
            {
                "id": 1,
                "result": {
                    "data": [
                        {
                            "cwd": str(project),
                            "skills": [
                                {
                                    "name": (
                                        f"{harness.SKILL_NAME}:{harness.SKILL_NAME}"
                                        if plugin_id
                                        else harness.SKILL_NAME
                                    ),
                                    "path": str(install / "SKILL.md"),
                                    "scope": scope,
                                    "enabled": True,
                                    "pluginId": plugin_id,
                                }
                            ],
                            "errors": [],
                        }
                    ]
                },
            },
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    stderr = b""
    harness._write_bytes(session / "skills-list.request.jsonl", request_bytes, private=True)
    harness._write_bytes(session / "skills-list.raw.jsonl", stdout, private=True)
    harness._write_bytes(session / "skills-list.stderr.raw.txt", stderr, private=True)
    return {
        "argv": [codex_bin, "app-server", "--stdio"],
        "request_sha256": harness.sha256_bytes(request_bytes),
        "stdout_sha256": harness.sha256_bytes(stdout),
        "stderr_sha256": harness.sha256_bytes(stderr),
        "force_reload": True,
        "credential_leak_detected": False,
    }


def _write_valid_probe_manifest(run_root: Path) -> Path:
    if harness.os.name != "posix":
        raise unittest.SkipTest("private runtime fixtures require POSIX permission semantics")
    auth_source = run_root.parent / "auth-source.json"
    auth_source.write_text('{"token":"abcdefghijklmnop"}', encoding="utf-8")
    auth_source.chmod(0o600)
    codex_bin = _write_fake_codex(run_root)
    candidate = harness.discover_candidate(REPO_ROOT)
    results = []
    receipt_rows = []
    scenarios = {row["id"]: row for row in harness.load_scenarios(REPO_ROOT)}
    for scenario_id in harness.PROBE_REFERENCES:
        scenario = scenarios[scenario_id]
        session = run_root / scenario_id
        install = session / "codex-home" / "skills" / harness.SKILL_NAME
        project = session / "project"
        project.mkdir(parents=True)
        harness._copy_candidate(REPO_ROOT, candidate, install)
        mappings = {
            str(install): "$CODEX_HOME/skills/packaging-product-visuals",
            str(session / "codex-home"): "$CODEX_HOME",
            str(session / "home"): "$HOME",
            str(project): "<project>",
            str(session): "<private-session-root>",
            str(run_root): "<private-run-root>",
            str(REPO_ROOT): "<repo>",
        }
        final = {
            "scenario_id": scenario_id,
            "skill_invoked": True,
            "observed_start_stage": scenario["expected_start_stage"],
            "requested_scope_end_stage": scenario["expected_scope_end_stage"],
            "current_stage_status": "blocked",
            "active_stage_outputs": scenario["active_stage_outputs"],
            "ecommerce_roles": scenario["ecommerce_roles"],
            "claims_made": [],
            "publication_authorized": False,
            "image_generation_invoked": False,
            "artifacts_invented": False,
            "files_written": False,
            "capability_limits": ["the run is an isolated behavior probe"],
        }
        events = [{"type": "thread.started"}, {"type": "turn.started"}]
        required_paths = [
            install / relative for relative in harness.PROBE_REFERENCES[scenario_id]
        ]
        for index, path in enumerate(required_paths):
            item_id = f"read-{index}"
            events.extend(
                [
                    {
                        "type": "item.started",
                        "item": {"id": item_id, "type": "command_execution"},
                    },
                    {
                        "type": "item.completed",
                        "item": {
                            "id": item_id,
                            "type": "command_execution",
                            "command": f"sed -n '1,220p' -- '{path}'",
                            "aggregated_output": harness._content_marker(path) + "\n",
                            "exit_code": 0,
                        },
                    },
                ]
            )
        events.extend(
            [
                {
                    "type": "item.completed",
                    "item": {
                        "id": "final-message",
                        "type": "agent_message",
                        "text": json.dumps(final, sort_keys=True),
                    },
                },
                {"type": "turn.completed"},
            ]
        )
        raw_bytes = (
            "\n".join(json.dumps(event, sort_keys=True) for event in events) + "\n"
        ).encode("utf-8")
        sanitized_bytes = harness.sanitize_jsonl_bytes(raw_bytes, mappings)
        harness._write_bytes(session / "events.raw.jsonl", raw_bytes, private=True)
        harness._write_bytes(
            session / "events.sanitized.jsonl", sanitized_bytes, private=True
        )
        harness._write_bytes(session / "stderr.raw.txt", b"", private=True)
        harness.write_json(session / "last-message.json", final, private=True)
        harness.write_json(
            session / "output-schema.json",
            harness.probe_output_schema(scenario, REPO_ROOT),
            private=True,
        )
        harness.write_text(
            session / "prompt.txt",
            harness._probe_prompt(scenario, install),
            private=True,
        )
        install_tree = harness.tree_snapshot(install)
        project_tree = harness.tree_snapshot(project)
        command_evidence = harness._sanitized_command_receipt(
            harness.audit_command_events(
                events,
                required_paths,
                require_content_markers=True,
            ),
            mappings,
        )
        result = {
            "id": scenario_id,
            "exit_code": 0,
            "event_stream_sha256": harness.sha256_bytes(sanitized_bytes),
            "structured_response_sha256": harness.sha256_bytes(
                json.dumps(final, sort_keys=True).encode("utf-8")
            ),
            "expected_start_stage": scenario["expected_start_stage"],
            "observed_start_stage": final["observed_start_stage"],
            "requested_scope_end_stage": final["requested_scope_end_stage"],
            "current_stage_status": final["current_stage_status"],
            "active_stage_outputs": final["active_stage_outputs"],
            "ecommerce_roles": final["ecommerce_roles"],
            "claims_made": final["claims_made"],
            "publication_authorized": final["publication_authorized"],
            "image_generation_invoked": final["image_generation_invoked"],
            "artifacts_invented": final["artifacts_invented"],
            "files_written": False,
            "capability_limits": final["capability_limits"],
            "command_evidence": command_evidence,
            "event_evidence": harness.audit_event_lifecycle(events),
            "install_tree_sha256_before": install_tree["tree_sha256"],
            "install_tree_sha256_after": install_tree["tree_sha256"],
            "workspace_tree_sha256_before": project_tree["tree_sha256"],
            "workspace_tree_sha256_after": project_tree["tree_sha256"],
            "credential_copy_mode": "0600",
            "credential_store": "file",
            "credential_copy_removed": True,
            "credential_leak_detected": False,
            "evidence_errors": [],
        }
        receipt = {
            "codex_argv": harness._codex_argv(
                codex_bin,
                project,
                harness._resolved(session / "output-schema.json"),
                harness._resolved(session / "last-message.json"),
                harness.MODEL,
                True,
            ),
            "raw_event_stream_sha256": harness.sha256_bytes(raw_bytes),
            "sanitized_event_stream_sha256": harness.sha256_bytes(sanitized_bytes),
            "stderr_sha256": harness.sha256_bytes(b""),
            "auth_copy_removed": True,
            "runtime_temp_symlink_cleanup": _empty_runtime_temp_symlink_cleanup(),
            "secret_leak_files": [],
            "absolute_path_mappings": mappings,
            "private_artifacts": harness._private_artifact_receipts(session),
            "summary": result,
        }
        receipt_path = session / "private-receipt.json"
        harness.write_json(receipt_path, receipt, private=True)
        receipt_rows.append(
            {
                "session_id": scenario_id,
                "relative_path": receipt_path.relative_to(run_root).as_posix(),
                "sha256": harness.file_sha256(receipt_path),
            }
        )
        results.append(result)
    runtime, runtime_receipt = _write_runtime_receipt(run_root, codex_bin)
    projection = {
        "schema_version": 1,
        "executed_on": "2026-09-09",
        "runtime": runtime,
        "method": harness._probe_method_receipt(candidate, REPO_ROOT),
        "results": results,
        "acceptance": harness._accept_probe_results(results),
    }
    manifest = {
        "schema_version": 1,
        "suite": "workflow-probes",
        "executed_on": "2026-09-09",
        "started_at_local": "2026-09-09T12:00:00+08:00",
        "auth_source_sha256": harness.file_sha256(auth_source),
        "candidate": candidate,
        "harness_artifacts": harness.harness_artifact_receipts(REPO_ROOT),
        "runtime_receipt": runtime_receipt,
        "session_receipts": receipt_rows,
        "public_projection": projection,
    }
    manifest_path = run_root / "run-manifest.json"
    harness.write_json(manifest_path, manifest, private=True)
    return manifest_path


def _write_valid_install_manifest(run_root: Path) -> Path:
    if harness.os.name != "posix":
        raise unittest.SkipTest("private runtime fixtures require POSIX permission semantics")
    auth_source = run_root.parent / "auth-source.json"
    auth_source.write_text('{"token":"abcdefghijklmnop"}', encoding="utf-8")
    auth_source.chmod(0o600)
    codex_bin = _write_fake_codex(run_root)
    candidate = harness.discover_candidate(REPO_ROOT)
    final = {
        "scenario_id": "install-smoke-image-unavailable",
        "skill_invoked": True,
        "status": "blocked",
        "capability_gap": "image_generation_unavailable",
        "artifact_invented": False,
        "files_written": False,
        "explanation": "Image generation is unavailable in this isolated smoke test.",
    }
    results = []
    receipt_rows = []

    def write_agent_artifacts(
        session: Path,
        install: Path,
        project: Path,
        mappings: dict[str, str],
    ) -> dict[str, object]:
        required_paths = [install / "SKILL.md", install / "references/contracts.md"]
        events = [{"type": "thread.started"}, {"type": "turn.started"}]
        for index, path in enumerate(required_paths):
            item_id = f"read-{index}"
            events.extend(
                [
                    {
                        "type": "item.started",
                        "item": {"id": item_id, "type": "command_execution"},
                    },
                    {
                        "type": "item.completed",
                        "item": {
                            "id": item_id,
                            "type": "command_execution",
                            "command": f"sed -n '1,220p' -- '{path}'",
                            "aggregated_output": harness._content_marker(path) + "\n",
                            "exit_code": 0,
                        },
                    },
                ]
            )
        events.extend(
            [
                {
                    "type": "item.completed",
                    "item": {
                        "id": "final-message",
                        "type": "agent_message",
                        "text": json.dumps(final, sort_keys=True),
                    },
                },
                {"type": "turn.completed"},
            ]
        )
        raw_bytes = (
            "\n".join(json.dumps(event, sort_keys=True) for event in events) + "\n"
        ).encode("utf-8")
        sanitized_bytes = harness.sanitize_jsonl_bytes(raw_bytes, mappings)
        harness._write_bytes(session / "events.raw.jsonl", raw_bytes, private=True)
        harness._write_bytes(
            session / "events.sanitized.jsonl", sanitized_bytes, private=True
        )
        harness._write_bytes(session / "stderr.raw.txt", b"", private=True)
        harness.write_json(session / "last-message.json", final, private=True)
        harness.write_json(
            session / "output-schema.json",
            harness.install_output_schema(REPO_ROOT),
            private=True,
        )
        harness.write_text(
            session / "prompt.txt",
            harness._install_prompt(install),
            private=True,
        )
        return {
            "raw_bytes": raw_bytes,
            "sanitized_bytes": sanitized_bytes,
            "events": events,
            "command_evidence": harness._sanitized_command_receipt(
                harness.audit_command_events(
                    events,
                    required_paths,
                    require_content_markers=True,
                ),
                mappings,
            ),
            "event_evidence": harness.audit_event_lifecycle(events),
            "install_tree": harness.tree_snapshot(install),
            "project_tree": harness.tree_snapshot(project),
        }

    for layout in harness.STANDALONE_LAYOUTS:
        session = run_root / layout["id"]
        session.mkdir(parents=True)
        paths = harness._layout_paths(session, layout["id"])
        home = paths["home"]
        project = paths["project"]
        codex_home = paths["codex_home"]
        install = paths["install"]
        assert isinstance(home, Path)
        assert isinstance(project, Path)
        assert isinstance(codex_home, Path)
        assert isinstance(install, Path)
        harness._copy_candidate(REPO_ROOT, candidate, install)
        mappings = {
            str(install): layout["install_relative_path"],
            str(codex_home): (
                "$CODEX_HOME" if paths["env_codex_home"] else "$HOME/.codex"
            ),
            str(home): "$HOME",
            str(project): "<project>",
            str(session): "<private-session-root>",
            str(run_root): "<private-run-root>",
            str(REPO_ROOT): "<repo>",
        }
        artifacts = write_agent_artifacts(session, install, project, mappings)
        skill_discovery = _write_skill_discovery_artifacts(
            session,
            install,
            project,
            codex_bin,
            scope="repo" if layout["id"] == "project-agents-skills" else "user",
        )
        command_evidence = artifacts["command_evidence"]
        assert isinstance(command_evidence, dict)
        result = {
            "id": layout["id"],
            "distribution": "standalone",
            "environment": {
                "home": "isolated temporary home",
                "codex_home": (
                    "explicitly set to an isolated temporary Codex home"
                    if paths["env_codex_home"]
                    else "unset and derived from the isolated home"
                ),
                "install_relative_path": layout["install_relative_path"],
                "cwd": layout["cwd"],
                "ignore_user_config": True,
            },
            "exit_code": 0,
            "event_stream_sha256": harness.sha256_bytes(artifacts["sanitized_bytes"]),
            "structured_response_sha256": harness.sha256_bytes(
                json.dumps(final, sort_keys=True).encode("utf-8")
            ),
            "command_evidence": command_evidence,
            "event_evidence": artifacts["event_evidence"],
            "outcome": {
                "skill_discovered_and_enabled": True,
                "structured_skill_invocation_reported": True,
                "reference_file_present_and_hashed": True,
                "agent_file_reads_observed": command_evidence[
                    "required_reads_succeeded"
                ],
                "capability_gap_reported": "image_generation_unavailable",
                "status": "blocked",
                "artifact_invented": False,
                "files_written": False,
            },
            "install_tree_sha256_before": artifacts["install_tree"]["tree_sha256"],
            "install_tree_sha256_after": artifacts["install_tree"]["tree_sha256"],
            "workspace_tree_sha256_before": artifacts["project_tree"]["tree_sha256"],
            "workspace_tree_sha256_after": artifacts["project_tree"]["tree_sha256"],
            "credential_copy_mode": "0600",
            "credential_store": "file",
            "credential_copy_removed": True,
            "credential_leak_detected": False,
            "evidence_errors": [],
        }
        receipt = {
            "codex_argv": harness._codex_argv(
                codex_bin,
                project,
                harness._resolved(session / "output-schema.json"),
                harness._resolved(session / "last-message.json"),
                harness.MODEL,
                True,
            ),
            "raw_event_stream_sha256": harness.sha256_bytes(artifacts["raw_bytes"]),
            "sanitized_event_stream_sha256": harness.sha256_bytes(
                artifacts["sanitized_bytes"]
            ),
            "stderr_sha256": harness.sha256_bytes(b""),
            "auth_copy_removed": True,
            "runtime_temp_symlink_cleanup": _empty_runtime_temp_symlink_cleanup(),
            "skill_discovery": skill_discovery,
            "secret_leak_files": [],
            "absolute_path_mappings": mappings,
            "private_artifacts": harness._private_artifact_receipts(session),
            "summary": result,
        }
        receipt_path = session / "private-receipt.json"
        harness.write_json(receipt_path, receipt, private=True)
        receipt_rows.append(
            {
                "session_id": layout["id"],
                "relative_path": receipt_path.relative_to(run_root).as_posix(),
                "sha256": harness.file_sha256(receipt_path),
            }
        )
        results.append(result)

    plugin_version = harness.load_plugin_version(REPO_ROOT)
    plugin_id = f"{harness.SKILL_NAME}@{harness.MARKETPLACE_NAME}"
    session = run_root / "local-marketplace-plugin"
    home = session / "home"
    codex_home = session / "codex-home"
    project = session / "project"
    marketplace = session / "marketplace"
    cache_root = codex_home / "plugins" / "cache" / harness.SKILL_NAME / plugin_version
    install = cache_root / "skills" / harness.SKILL_NAME
    home.mkdir(parents=True)
    project.mkdir()
    marketplace.mkdir()
    (cache_root / ".codex-plugin").mkdir(parents=True)
    (cache_root / ".codex-plugin" / "plugin.json").write_bytes(
        (REPO_ROOT / ".codex-plugin" / "plugin.json").read_bytes()
    )
    (cache_root / "LICENSE").write_bytes((REPO_ROOT / "LICENSE").read_bytes())
    harness._copy_candidate(REPO_ROOT, candidate, install)
    mappings = {
        str(install): f"<plugin-cache>/skills/{harness.SKILL_NAME}",
        str(cache_root): "<plugin-cache>",
        str(session): "<private-session-root>",
        str(run_root): "<private-run-root>",
        str(REPO_ROOT): "<repo>",
        str(codex_bin): "<codex-bin>",
        str(home): "$HOME",
        str(codex_home): "$CODEX_HOME",
        str(project): "<project>",
        str(marketplace): "<private-marketplace>",
    }
    artifacts = write_agent_artifacts(session, install, project, mappings)
    skill_discovery = _write_skill_discovery_artifacts(
        session,
        install,
        project,
        codex_bin,
        scope="plugin",
        plugin_id=plugin_id,
    )
    plugin_command_argv = harness._plugin_command_argv(
        codex_bin,
        marketplace,
        plugin_id,
    )
    command_receipts = {}
    plugin_outputs = {
        "marketplace-add": {},
        "plugin-add": {},
        "plugin-list": {
            "installed": [
                {
                    "pluginId": plugin_id,
                    "installed": True,
                    "enabled": True,
                    "version": plugin_version,
                    "source": {"path": str(cache_root)},
                }
            ]
        },
    }
    for label, argv in plugin_command_argv.items():
        stdout = json.dumps(plugin_outputs[label], sort_keys=True).encode("utf-8")
        stderr = b""
        harness._write_bytes(session / f"{label}.stdout.raw.json", stdout, private=True)
        harness._write_bytes(session / f"{label}.stderr.raw.txt", stderr, private=True)
        command_receipts[label] = harness._sanitize_value(
            {
                "argv": argv,
                "exit_code": 0,
                "stdout_sha256": harness.sha256_bytes(stdout),
                "stderr_sha256": harness.sha256_bytes(stderr),
                "json_output": True,
                "credential_leak_detected": False,
            },
            mappings,
        )
    cache_audit = harness._plugin_cache_audit(cache_root, candidate, REPO_ROOT)
    installation = {
        "marketplace_name": harness.MARKETPLACE_NAME,
        "marketplace_source": "isolated local filesystem marketplace",
        "distribution": "skills-only plugin",
        "distribution_contents": [
            ".codex-plugin/plugin.json",
            f"skills/{harness.SKILL_NAME}/",
            "LICENSE",
        ],
        "command_receipts": command_receipts,
        "plugin_id": plugin_id,
        "plugin_version": plugin_version,
        "installed": True,
        "enabled": True,
        "plugin_list_source_inside_private_session": True,
        "remote_catalog_required": False,
        "cache_audit": cache_audit,
    }
    plugin_result = {
        "id": "local-marketplace-plugin",
        "distribution": "skills-only-plugin",
        "environment": {
            "home": "isolated temporary home",
            "codex_home": "explicitly set to the isolated plugin-install Codex home",
            "install_relative_path": f"<plugin-cache>/skills/{harness.SKILL_NAME}",
            "cwd": "isolated empty project outside the marketplace and install cache",
            "ignore_user_config": False,
            "ignore_user_config_reason": (
                "plugin enablement is the isolated config generated by marketplace and plugin add"
            ),
        },
        "exit_code": 0,
        "event_stream_sha256": harness.sha256_bytes(artifacts["sanitized_bytes"]),
        "discovered_skill_id": f"{harness.SKILL_NAME}:{harness.SKILL_NAME}",
        "command_evidence": artifacts["command_evidence"],
        "event_evidence": artifacts["event_evidence"],
        "outcome": {
            "skill_discovered_and_enabled": True,
            "structured_skill_invocation_reported": True,
            "reference_file_present_and_hashed": True,
            "agent_file_reads_observed": artifacts["command_evidence"][
                "required_reads_succeeded"
            ],
            "capability_gap_reported": "image_generation_unavailable",
            "status": "blocked",
            "artifact_invented": False,
            "files_written": False,
        },
        "install_tree_sha256_before": artifacts["install_tree"]["tree_sha256"],
        "install_tree_sha256_after": artifacts["install_tree"]["tree_sha256"],
        "workspace_tree_sha256_before": artifacts["project_tree"]["tree_sha256"],
        "workspace_tree_sha256_after": artifacts["project_tree"]["tree_sha256"],
        "credential_copy_mode": "0600",
        "credential_store": "file",
        "credential_copy_removed": True,
        "credential_leak_detected": False,
        "evidence_errors": [],
    }
    plugin_receipt = {
        "codex_argv": harness._codex_argv(
            codex_bin,
            project,
            harness._resolved(session / "output-schema.json"),
            harness._resolved(session / "last-message.json"),
            harness.MODEL,
            False,
        ),
        "plugin_command_argv": plugin_command_argv,
        "raw_event_stream_sha256": harness.sha256_bytes(artifacts["raw_bytes"]),
        "sanitized_event_stream_sha256": harness.sha256_bytes(
            artifacts["sanitized_bytes"]
        ),
        "stderr_sha256": harness.sha256_bytes(b""),
        "auth_copy_removed": True,
        "runtime_temp_symlink_cleanup": _empty_runtime_temp_symlink_cleanup(),
        "skill_discovery": skill_discovery,
        "secret_leak_files": [],
        "absolute_path_mappings": mappings,
        "private_artifacts": harness._private_artifact_receipts(session),
        "plugin_installation": installation,
        "summary": plugin_result,
    }
    plugin_receipt_path = session / "private-receipt.json"
    harness.write_json(plugin_receipt_path, plugin_receipt, private=True)
    receipt_rows.append(
        {
            "session_id": "local-marketplace-plugin",
            "relative_path": plugin_receipt_path.relative_to(run_root).as_posix(),
            "sha256": harness.file_sha256(plugin_receipt_path),
        }
    )
    results.append(plugin_result)

    runtime, runtime_receipt = _write_runtime_receipt(run_root, codex_bin)
    projection = {
        "schema_version": 2,
        "executed_on": "2026-09-09",
        "runtime": runtime,
        "scenario": harness._install_scenario_receipt(),
        "method": harness._install_method_receipt(candidate, REPO_ROOT),
        "plugin_installation": installation,
        "results": results,
        "acceptance": harness._accept_install_results(results),
    }
    manifest = {
        "schema_version": 1,
        "suite": "install-smoke",
        "executed_on": "2026-09-09",
        "started_at_local": "2026-09-09T12:00:00+08:00",
        "auth_source_sha256": harness.file_sha256(auth_source),
        "candidate": candidate,
        "harness_artifacts": harness.harness_artifact_receipts(REPO_ROOT),
        "runtime_receipt": runtime_receipt,
        "session_receipts": receipt_rows,
        "public_projection": projection,
    }
    manifest_path = run_root / "run-manifest.json"
    harness.write_json(manifest_path, manifest, private=True)
    return manifest_path


def _auth_for_manifest(manifest_path: Path) -> Path:
    return manifest_path.parent.parent / "auth-source.json"


def _codex_for_manifest(manifest_path: Path) -> Path:
    return manifest_path.parent.parent / "bin" / "codex"


def _verify_probe_manifest(manifest_path: Path, **kwargs: object) -> dict[str, object]:
    return harness.verify_private_run_manifest(
        manifest_path,
        REPO_ROOT,
        auth_source=_auth_for_manifest(manifest_path),
        codex_bin=str(_codex_for_manifest(manifest_path)),
        **kwargs,
    )


def _rewrite_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


class Task6HarnessTests(unittest.TestCase):
    def test_private_runtime_rejects_non_posix_before_io_or_process_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            actions = (
                lambda: harness._validated_auth_source(root / "repo", root / "auth.json"),
                lambda: harness._copy_auth(root / "auth.json", root / "home"),
                lambda: harness._write_bytes(root / "private" / "raw.json", b"{}", private=True),
                lambda: harness._preflight(root / "repo", root / "audit", root / "auth.json", "codex"),
                lambda: harness.verify_private_run_manifest(root / "manifest.json", root / "repo"),
            )
            for index, action in enumerate(actions):
                with (
                    self.subTest(entrypoint=index),
                    mock.patch.object(harness, "os", SimpleNamespace(name="nt")),
                    mock.patch.object(harness, "_resolved", side_effect=AssertionError("filesystem probe")),
                    mock.patch.object(harness, "_run_capture", side_effect=AssertionError("process execution")),
                    mock.patch.object(harness.shutil, "copyfile", side_effect=AssertionError("credential copy")),
                    mock.patch.object(Path, "mkdir", side_effect=AssertionError("directory creation")),
                    mock.patch.object(Path, "read_text", side_effect=AssertionError("file read")),
                    self.assertRaisesRegex(harness.HarnessError, "requires POSIX"),
                ):
                    action()
            self.assertEqual(list(root.iterdir()), [])

    def test_tree_digest_matches_release_evidence_algorithm(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "agents").mkdir()
            (root / "SKILL.md").write_bytes(b"skill")
            (root / "agents" / "openai.yaml").write_bytes(b"agent")

            expected = hashlib.sha256(
                b"SKILL.mdskillagents/openai.yamlagent"
            ).hexdigest()

            self.assertEqual(
                harness.tree_digest(
                    root,
                    [Path("agents/openai.yaml"), Path("SKILL.md")],
                ),
                expected,
            )

    def test_audit_root_inside_public_worktree_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()

            with self.assertRaisesRegex(harness.HarnessError, "outside"):
                harness.require_private_audit_root(repo, repo / ".private-audit")

    def test_sanitized_event_stream_replaces_longest_paths_before_hashing(self):
        private_run = "/private/run"
        private_home = private_run + "/" + "home"
        raw = (
            '{"type":"item.completed","item":{"type":"command_execution",'
            f'"command":"cat {private_home}/.codex/auth.json"}}\n'
        ).encode()
        mappings = {
            private_run: "<private-run>",
            private_home: "<isolated-home>",
        }

        sanitized = harness.sanitize_jsonl_bytes(raw, mappings)

        self.assertNotIn(("/private" + "/").encode(), sanitized)
        self.assertIn(b"<isolated-home>/.codex/auth.json", sanitized)
        self.assertEqual(
            harness.sha256_bytes(sanitized),
            hashlib.sha256(sanitized).hexdigest(),
        )
        self.assertFalse(
            harness._public_projection_is_sanitized(
                {"value": "/var/folders/example/private.txt"}
            )
        )
        self.assertFalse(
            harness._public_projection_is_sanitized(
                {"value": "C:\\Users\\example\\private.txt"}
            )
        )

    def test_command_trace_requires_successful_real_reads_and_rejects_write_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            install_root = Path(tmp) / "packaging-product-visuals"
            (install_root / "references").mkdir(parents=True)
            (install_root / "SKILL.md").write_text("# Packaging Skill\n", encoding="utf-8")
            (install_root / "references" / "contracts.md").write_text(
                "# Contracts\n", encoding="utf-8"
            )
            events = [
                {
                    "type": "item.completed",
                    "item": {
                        "id": "item-1",
                        "type": "command_execution",
                        "command": f"sed -n '1,220p' -- '{install_root / 'SKILL.md'}'",
                        "aggregated_output": "# Packaging Skill\n",
                        "exit_code": 0,
                    },
                },
                {
                    "type": "item.completed",
                    "item": {
                        "id": "item-2",
                        "type": "command_execution",
                        "command": f"cat -- '{install_root / 'references/contracts.md'}'",
                        "aggregated_output": "# Contracts\n",
                        "exit_code": 0,
                    },
                },
            ]

            receipt = harness.audit_command_events(
                events,
                [
                    install_root / "SKILL.md",
                    install_root / "references/contracts.md",
                ],
                require_content_markers=True,
            )

            self.assertTrue(receipt["required_reads_succeeded"])
            self.assertFalse(receipt["write_like_command_detected"])
            self.assertEqual(receipt["successful_command_count"], 2)
            self.assertEqual(len(receipt["commands"]), 2)
            self.assertRegex(receipt["commands"][0]["command_sha256"], r"^[0-9a-f]{64}$")

            write_events = events + [
                {
                    "type": "item.completed",
                    "item": {
                        "type": "command_execution",
                        "command": "touch output.png",
                        "exit_code": 1,
                    },
                }
            ]
            receipt = harness.audit_command_events(
                write_events,
                [install_root / "SKILL.md"],
            )
            self.assertTrue(receipt["write_like_command_detected"])

            link_events = events + [
                {
                    "type": "item.completed",
                    "item": {
                        "type": "command_execution",
                        "command": "ln -s source target",
                        "exit_code": 1,
                    },
                }
            ]
            receipt = harness.audit_command_events(
                link_events,
                [install_root / "SKILL.md"],
            )
            self.assertTrue(receipt["write_like_command_detected"])

            forged_events = [
                {
                    "type": "item.completed",
                    "item": {
                        "type": "command_execution",
                        "command": (
                            "printf '# Packaging Skill\\n' # cat -- "
                            f"{install_root / 'SKILL.md'}"
                        ),
                        "aggregated_output": "# Packaging Skill\n",
                        "exit_code": 0,
                    },
                }
            ]
            receipt = harness.audit_command_events(
                forged_events,
                [install_root / "SKILL.md"],
                require_content_markers=True,
            )
            self.assertFalse(receipt["required_reads_succeeded"])

    def test_shell_wrapped_env_root_reads_survive_private_paths_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix="install smoke ") as tmp:
            install_root = Path(tmp) / "packaging-product-visuals"
            (install_root / "references").mkdir(parents=True)
            (install_root / "SKILL.md").write_text("# Packaging Skill\n", encoding="utf-8")
            contracts = install_root / "references" / "contracts.md"
            contracts.write_text("# Contracts\n", encoding="utf-8")
            required_paths = [install_root / "SKILL.md", contracts]
            events = []
            for index, path in enumerate(required_paths):
                relative = path.relative_to(install_root).as_posix()
                inner = f'sed -n 1,220p "$PPV_SKILL_ROOT/{relative}"'
                events.append(
                    {
                        "type": "item.completed",
                        "item": {
                            "id": f"item-{index}",
                            "type": "command_execution",
                            "command": f"/bin/zsh -lc {shlex.quote(inner)}",
                            "aggregated_output": harness._content_marker(path) + "\n",
                            "exit_code": 0,
                        },
                    }
                )

            receipt = harness.audit_command_events(
                events,
                required_paths,
                require_content_markers=True,
            )
            public_receipt = harness._sanitized_command_receipt(
                receipt,
                {str(install_root): "$CODEX_HOME/skills/packaging-product-visuals"},
            )

            self.assertTrue(receipt["required_reads_succeeded"])
            self.assertFalse(receipt["write_like_command_detected"])
            self.assertTrue(harness._public_projection_is_sanitized(public_receipt))
            self.assertNotIn("/bin/zsh", json.dumps(public_receipt))
            self.assertTrue(
                all(
                    command["command"].startswith("sed -n 1,220p ")
                    for command in public_receipt["commands"]
                )
            )

            extra_events = events + [
                {
                    "type": "item.completed",
                    "item": {
                        "id": "extra-command",
                        "type": "command_execution",
                        "command": "python -c 'raise SystemExit(1)'",
                        "exit_code": 1,
                    },
                }
            ]
            receipt = harness.audit_command_events(
                extra_events,
                [
                    install_root / "SKILL.md",
                    install_root / "references/contracts.md",
                ],
                require_content_markers=True,
            )
            self.assertFalse(receipt["required_reads_succeeded"])
            self.assertEqual(receipt["unexpected_command_count"], 1)

    def test_event_lifecycle_rejects_external_or_mutating_items(self):
        events = [
            {"type": "thread.started"},
            {"type": "turn.started"},
            {
                "type": "item.started",
                "item": {"id": "read-1", "type": "command_execution"},
            },
            {
                "type": "item.completed",
                "item": {
                    "id": "read-1",
                    "type": "command_execution",
                    "exit_code": 0,
                },
            },
            {"type": "turn.completed"},
        ]
        receipt = harness.audit_event_lifecycle(events)
        self.assertTrue(receipt["lifecycle_complete"])
        self.assertEqual(receipt["disallowed_item_types"], [])

        disallowed_events = events[:3] + [
            {"type": "item.completed", "item": {"type": "file_change"}}
        ] + events[3:]
        receipt = harness.audit_event_lifecycle(disallowed_events)
        self.assertEqual(receipt["disallowed_item_types"], ["file_change"])

        out_of_order = [events[-1], *events[:-1]]
        receipt = harness.audit_event_lifecycle(out_of_order)
        self.assertFalse(receipt["lifecycle_complete"])
        self.assertFalse(receipt["event_order_valid"])

        nonzero = json.loads(json.dumps(events))
        nonzero[3]["item"]["exit_code"] = 1
        receipt = harness.audit_event_lifecycle(nonzero)
        self.assertFalse(receipt["lifecycle_complete"])
        self.assertEqual(receipt["nonzero_command_exit_count"], 1)

        reversed_pair = [events[0], events[1], events[3], events[2], events[4]]
        receipt = harness.audit_event_lifecycle(reversed_pair)
        self.assertFalse(receipt["lifecycle_complete"])
        self.assertFalse(receipt["command_pair_order_valid"])

    def test_probe_output_is_closed_and_scenario_bound(self):
        scenario = {
            "id": "approved-package-gallery",
            "expected_start_stage": "ecommerce-planning",
            "expected_scope_end_stage": "qa-delivery",
            "active_stage_outputs": ["EcommerceAssetPlan", "AssetBrief"],
            "ecommerce_roles": ["catalog", "detail"],
            "prohibited_claims": ["publication authorization"],
        }
        result = {
            "scenario_id": "approved-package-gallery",
            "skill_invoked": True,
            "observed_start_stage": "ecommerce-planning",
            "requested_scope_end_stage": "qa-delivery",
            "current_stage_status": "blocked",
            "active_stage_outputs": ["EcommerceAssetPlan", "AssetBrief"],
            "ecommerce_roles": ["catalog", "detail"],
            "claims_made": [],
            "publication_authorized": False,
            "image_generation_invoked": False,
            "artifacts_invented": False,
            "files_written": False,
            "capability_limits": ["approved source artifact and hash are missing"],
        }

        self.assertEqual(harness.validate_probe_output(result, scenario), [])

        result["capability_limits"] = [
            "approved source artifact and hash are missing",
            "approved source artifact and hash are missing",
        ]
        errors = harness.validate_probe_output(result, scenario)
        self.assertTrue(any("unique" in error for error in errors))
        result["capability_limits"] = ["approved source artifact and hash are missing"]

        result["unexpected"] = True
        errors = harness.validate_probe_output(result, scenario)
        self.assertTrue(any("unexpected keys" in error for error in errors))

    def test_dry_run_plan_contains_no_observed_runtime_claims(self):
        candidate = {
            "source": "git ls-files --cached --others --exclude-standard",
            "file_count": 10,
            "tree_sha256": "a" * 64,
            "files": ["SKILL.md"],
        }
        scenarios = [
            {
                "id": "uncertain-product-start",
                "expected_start_stage": "product-definition",
                "expected_scope_end_stage": "decision-freeze",
                "active_stage_outputs": ["ProductBrief"],
                "ecommerce_roles": [],
                "prohibited_claims": ["health benefit"],
            }
        ]

        plan = harness.build_dry_run_plan(candidate, scenarios, "0.2.0")
        flattened = str(plan)

        self.assertNotIn("executed_on", plan)
        self.assertEqual(len(plan["install_smoke"]["sessions"]), 5)
        self.assertEqual(plan["behavior_probes"]["count"], 1)
        self.assertNotIn("exit_code", flattened)
        self.assertNotIn("event_stream_sha256", flattened)
        self.assertNotIn("accepted", flattened)
        self.assertNotIn("/" + "Users/", flattened)

    def test_execution_clock_uses_the_sampled_local_timestamp(self):
        sampled = datetime(
            2026,
            9,
            9,
            14,
            30,
            15,
            tzinfo=timezone(timedelta(hours=8)),
        )

        clock = harness.capture_local_execution_clock(sampled)

        self.assertEqual(clock["executed_on"], "2026-09-09")
        self.assertEqual(clock["started_at_local"], "2026-09-09T14:30:15+08:00")

    def test_real_execution_requires_flag_and_exact_candidate_digest(self):
        candidate = {"tree_sha256": "a" * 64}

        self.assertFalse(
            harness.require_execution_authorized(
                execute=False,
                dry_run=False,
                confirmed_digest=None,
                candidate=candidate,
            )
        )
        with self.assertRaisesRegex(harness.HarnessError, "digest"):
            harness.require_execution_authorized(
                execute=True,
                dry_run=False,
                confirmed_digest="b" * 64,
                candidate=candidate,
            )
        self.assertTrue(
            harness.require_execution_authorized(
                execute=True,
                dry_run=False,
                confirmed_digest="a" * 64,
                candidate=candidate,
            )
        )
        with self.assertRaisesRegex(harness.HarnessError, "exactly 5"):
            harness.require_execution_authorized(
                execute=True,
                dry_run=False,
                confirmed_digest="a" * 64,
                candidate=candidate,
                max_agent_sessions=4,
                required_agent_sessions=5,
            )

    def test_external_schema_files_are_closed_and_scenario_bound(self):
        install_schema = harness.install_output_schema(REPO_ROOT)
        self.assertFalse(install_schema["additionalProperties"])
        self.assertEqual(set(install_schema["required"]), harness.INSTALL_OUTPUT_KEYS)
        self.assertEqual(
            install_schema["properties"]["scenario_id"]["enum"],
            ["install-smoke-image-unavailable"],
        )
        self.assertEqual(
            install_schema["properties"]["capability_gap"]["enum"],
            ["image_generation_unavailable"],
        )
        self.assertEqual(install_schema["properties"]["skill_invoked"]["enum"], [True])
        self.assertEqual(install_schema["properties"]["files_written"]["enum"], [False])
        install_prompt = harness._install_prompt(Path("/private-skill"))
        self.assertNotIn("sed -n", install_prompt)
        self.assertIn("Do not run shell commands", install_prompt)
        self.assertNotIn("/private-skill", install_prompt)

        scenario = harness.load_scenarios(REPO_ROOT)[0]
        probe_schema = harness.probe_output_schema(scenario, REPO_ROOT)
        self.assertFalse(probe_schema["additionalProperties"])
        self.assertNotIn("uniqueItems", json.dumps(probe_schema, sort_keys=True))
        self.assertNotIn("const", probe_schema["properties"]["scenario_id"])
        self.assertNotIn("const", probe_schema["properties"]["active_stage_outputs"])
        self.assertIn("requested_scope_end_stage", probe_schema["properties"])
        self.assertNotIn("const", probe_schema["properties"]["skill_invoked"])
        prompt = harness._probe_prompt(scenario, Path("/private-skill"))
        self.assertNotIn(scenario["expected_start_stage"], prompt)
        self.assertNotIn(scenario["expected_scope_end_stage"], prompt)
        normalized_prompt = " ".join(prompt.split())
        self.assertIn("only the outputs named in the router row", normalized_prompt)
        self.assertIn("furthest stage explicitly requested", normalized_prompt)
        for output_name in scenario["active_stage_outputs"]:
            self.assertNotIn(output_name, prompt)

        with tempfile.TemporaryDirectory() as tmp:
            invalid_root = Path(tmp)
            invalid_schema = {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "items": {
                        "type": "array",
                        "uniqueItems": True,
                        "items": {"type": "string"},
                    }
                },
            }
            (invalid_root / "schema.json").write_text(
                json.dumps(invalid_schema),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(harness.HarnessError, "uniqueItems"):
                harness._load_schema(invalid_root, Path("schema.json"))

    def test_skill_discovery_protocol_verifies_runtime_path_and_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            install = root / "home" / ".codex" / "skills" / harness.SKILL_NAME
            project.mkdir()
            candidate = harness.discover_candidate(REPO_ROOT)
            harness._copy_candidate(REPO_ROOT, candidate, install)
            response = {
                "id": 1,
                "result": {
                    "data": [
                        {
                            "cwd": str(project),
                            "skills": [
                                {
                                    "name": harness.SKILL_NAME,
                                    "path": str(install / "SKILL.md"),
                                    "scope": "user",
                                    "enabled": True,
                                    "pluginId": None,
                                }
                            ],
                            "errors": [],
                        }
                    ]
                },
            }

            evidence = harness._skill_discovery_evidence(
                response,
                project=project,
                install=install,
                candidate=candidate,
            )

            self.assertTrue(evidence["verified"])
            self.assertEqual(evidence["matching_skill_count"], 1)
            self.assertTrue(evidence["relative_reference_verified"])
            request = harness._skills_list_request_bytes(project).decode("utf-8")
            self.assertIn('"forceReload":true', request)

            response["result"]["data"][0]["skills"][0]["name"] = (
                f"{harness.SKILL_NAME}:{harness.SKILL_NAME}"
            )
            response["result"]["data"][0]["skills"][0]["pluginId"] = (
                f"{harness.SKILL_NAME}@{harness.MARKETPLACE_NAME}"
            )
            plugin_evidence = harness._skill_discovery_evidence(
                response,
                project=project,
                install=install,
                candidate=candidate,
            )
            self.assertTrue(plugin_evidence["verified"])

    def test_install_outcome_uses_protocol_discovery_not_optional_agent_reads(self):
        final = {
            "skill_invoked": True,
            "capability_gap": "image_generation_unavailable",
            "status": "blocked",
            "artifact_invented": False,
            "files_written": False,
        }
        command_receipt = {"write_like_command_detected": False}

        outcome = harness._install_outcome(
            final=final,
            discovery_verified=True,
            project_mutated=False,
            command_receipt=command_receipt,
        )

        self.assertTrue(outcome["skill_discovered_and_enabled"])
        self.assertTrue(outcome["structured_skill_invocation_reported"])
        self.assertFalse(outcome["reference_file_present_and_hashed"])
        self.assertFalse(outcome["agent_file_reads_observed"])
        self.assertFalse(outcome["files_written"])

    @unittest.skipUnless(harness.os.name == "posix", "Codex runtime fixture uses a POSIX shell executable")
    def test_codex_runtime_temp_symlink_cleanup_is_narrow_and_auditable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session = root / "session"
            arg0 = session / "codex-home" / "tmp" / "arg0" / "codex-arg0AbC123"
            arg0.mkdir(parents=True)
            runtime = root / "runtime" / "codex"
            runtime.parent.mkdir()
            runtime.write_text(
                "#!/bin/sh\nprintf 'codex-cli 1.2.3\\n'\n",
                encoding="utf-8",
            )
            runtime.chmod(0o700)
            for name in harness.CODEX_RUNTIME_TEMP_SYMLINK_NAMES:
                (arg0 / name).symlink_to(runtime)

            receipt = harness._remove_codex_runtime_temp_symlinks(
                session,
                str(runtime),
            )

            self.assertEqual(receipt["removed_count"], 3)
            self.assertEqual(len(receipt["removed"]), 3)
            self.assertFalse(any(path.is_symlink() for path in session.rglob("*")))
            self.assertEqual(harness._secret_leak_files(session, (b"not-present",)), [])
            self.assertEqual(
                {row["target_client_version"] for row in receipt["removed"]},
                {"1.2.3"},
            )

    @unittest.skipUnless(harness.os.name == "posix", "Codex runtime fixture uses POSIX symlinks")
    def test_codex_runtime_temp_symlink_cleanup_rejects_unexpected_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session = root / "session"
            session.mkdir()
            runtime = root / "codex"
            runtime.write_text(
                "#!/bin/sh\nprintf 'codex-cli 1.2.3\\n'\n",
                encoding="utf-8",
            )
            runtime.chmod(0o700)
            unexpected = session / "unexpected-link"
            unexpected.symlink_to(runtime)

            with self.assertRaisesRegex(harness.HarnessError, "unexpected symlink"):
                harness._remove_codex_runtime_temp_symlinks(session, str(runtime))
            self.assertTrue(unexpected.is_symlink())

    @unittest.skipUnless(harness.os.name == "posix", "private marketplace fixture requires POSIX permission semantics")
    def test_local_marketplace_entry_uses_a_local_path_source(self):
        candidate = harness.discover_candidate(REPO_ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            marketplace_root = Path(tmp) / "marketplace"
            harness._create_marketplace(REPO_ROOT, marketplace_root, candidate)

            manifest = json.loads(
                (marketplace_root / ".agents" / "plugins" / "marketplace.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                manifest["plugins"][0]["source"],
                {
                    "source": "local",
                    "path": "./plugins/packaging-product-visuals",
                },
            )

    def test_subprocess_runner_explicitly_disables_shell(self):
        completed = subprocess_result = mock.Mock(returncode=0, stdout=b"", stderr=b"")
        with mock.patch.object(harness.subprocess, "run", return_value=completed) as run:
            observed = harness._run_capture(["codex", "--version"], cwd=REPO_ROOT)

        self.assertIs(observed, subprocess_result)
        self.assertIs(run.call_args.kwargs["shell"], False)

    def test_safe_default_writes_plan_without_calling_real_suite(self):
        candidate = {
            "source": "git ls-files --cached --others --exclude-standard",
            "file_count": 1,
            "tree_sha256": "a" * 64,
            "files": ["SKILL.md"],
            "file_sha256": {"SKILL.md": "b" * 64},
            "git_head": "c" * 40,
            "git_status": "clean",
            "git_status_sha256": "d" * 64,
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            auth = tmp_root / "source-auth.json"
            auth.write_text('{"token":"abcdefghijklmnop"}', encoding="utf-8")
            auth.chmod(0o600)
            output = tmp_root / "install-plan.yaml"
            with (
                mock.patch.object(
                    harness,
                    "_preflight",
                    return_value={"candidate": candidate},
                ),
                mock.patch.object(harness, "run_install_smoke") as real_run,
            ):
                exit_code = harness.main(
                    [
                        "install-smoke",
                        "--repo-root",
                        str(REPO_ROOT),
                        "--audit-root",
                        str(tmp_root / "audit"),
                        "--auth-source",
                        str(auth),
                        "--output",
                        str(output),
                    ]
                )

            self.assertEqual(exit_code, 0)
            real_run.assert_not_called()
            plan = harness.yaml.safe_load(output.read_text(encoding="utf-8"))
            self.assertEqual(plan["execution_mode"], "dry-run")
            self.assertFalse(plan["dry_run_guarantees"]["codex_exec_invoked"])

    def test_execute_passes_the_confirmed_candidate_into_the_real_suite(self):
        candidate = {
            "source": "git ls-files --cached --others --exclude-standard",
            "file_count": 1,
            "tree_sha256": "a" * 64,
            "files": ["SKILL.md"],
            "file_sha256": {"SKILL.md": "b" * 64},
            "git_head": "c" * 40,
            "git_status": "clean",
            "git_status_sha256": "d" * 64,
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            auth = tmp_root / "source-auth.json"
            auth.write_text('{"token":"abcdefghijklmnop"}', encoding="utf-8")
            auth.chmod(0o600)
            output = tmp_root / "install-results.yaml"
            manifest_path = tmp_root / "audit" / "run-manifest.json"
            with (
                mock.patch.object(
                    harness,
                    "_preflight",
                    return_value={"candidate": candidate},
                ),
                mock.patch.object(
                    harness,
                    "run_install_smoke",
                    return_value=manifest_path,
                ) as real_run,
                mock.patch.object(
                    harness,
                    "verify_private_run_manifest",
                    return_value={"acceptance": {"result": "passed"}},
                ),
            ):
                exit_code = harness.main(
                    [
                        "install-smoke",
                        "--repo-root",
                        str(REPO_ROOT),
                        "--audit-root",
                        str(tmp_root / "audit"),
                        "--auth-source",
                        str(auth),
                        "--execute",
                        "--confirm-tree-sha256",
                        candidate["tree_sha256"],
                        "--max-agent-sessions",
                        "5",
                        "--output",
                        str(output),
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(real_run.call_args.kwargs["candidate"], candidate)

    @unittest.skipUnless(harness.os.name == "posix", "private session fixtures require POSIX permission semantics")
    def test_session_wrappers_remove_credentials_after_pre_execution_errors(self):
        candidate = harness.discover_candidate(REPO_ROOT)
        scenario = harness.load_scenarios(REPO_ROOT)[0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            auth = root / "source-auth.json"
            auth.write_text('{"token":"abcdefghijklmnop"}', encoding="utf-8")
            auth.chmod(0o600)
            cases = (
                (
                    "standalone",
                    lambda run_root: harness._standalone_session(
                        repo_root=REPO_ROOT,
                        run_root=run_root,
                        layout=harness.STANDALONE_LAYOUTS[0],
                        candidate=candidate,
                        auth_source=auth,
                        codex_bin="codex",
                        model=harness.MODEL,
                        timeout=1,
                    ),
                ),
                (
                    "plugin",
                    lambda run_root: harness._plugin_session(
                        repo_root=REPO_ROOT,
                        run_root=run_root,
                        candidate=candidate,
                        plugin_version=harness.load_plugin_version(REPO_ROOT),
                        auth_source=auth,
                        codex_bin="codex",
                        model=harness.MODEL,
                        timeout=1,
                    ),
                ),
                (
                    "probe",
                    lambda run_root: harness._probe_session(
                        repo_root=REPO_ROOT,
                        run_root=run_root,
                        scenario=scenario,
                        candidate=candidate,
                        auth_source=auth,
                        codex_bin="codex",
                        model=harness.MODEL,
                        timeout=1,
                    ),
                ),
            )
            for name, invoke in cases:
                run_root = root / name
                with (
                    self.subTest(name=name),
                    mock.patch.object(
                        harness,
                        "_credential_secret_values",
                        side_effect=harness.HarnessError("fixture failure"),
                    ),
                    self.assertRaisesRegex(harness.HarnessError, "fixture failure"),
                ):
                    invoke(run_root)
                self.assertEqual(list(run_root.rglob(harness.AUTH_BASENAME)), [])

    def test_plugin_cache_audit_rejects_stale_candidate_content(self):
        candidate = harness.discover_candidate(REPO_ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            cache_root = Path(tmp) / "cache"
            (cache_root / ".codex-plugin").mkdir(parents=True)
            (cache_root / "skills").mkdir()
            (cache_root / ".codex-plugin" / "plugin.json").write_bytes(
                (REPO_ROOT / ".codex-plugin" / "plugin.json").read_bytes()
            )
            (cache_root / "LICENSE").write_bytes((REPO_ROOT / "LICENSE").read_bytes())
            harness._copy_candidate(
                REPO_ROOT,
                candidate,
                cache_root / "skills" / harness.SKILL_NAME,
            )

            audit = harness._plugin_cache_audit(cache_root, candidate, REPO_ROOT)
            self.assertEqual(audit["unexpected_files"], [])
            self.assertEqual(audit["missing_files"], [])

            (cache_root / "skills" / harness.SKILL_NAME / "SKILL.md").write_text(
                "stale\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(harness.HarnessError, "confirmed candidate"):
                harness._plugin_cache_audit(cache_root, candidate, REPO_ROOT)

    def test_private_manifest_must_verify_before_public_projection(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "workflow-run"
            manifest_path = _write_valid_probe_manifest(run_root)

            verified = _verify_probe_manifest(
                manifest_path,
                expected_suite="workflow-probes",
            )
            self.assertEqual(verified["private_audit_receipt"]["verification"], "passed")
            self.assertRegex(
                verified["private_audit_receipt"]["run_manifest_sha256"],
                r"^[0-9a-f]{64}$",
            )

            first_raw = run_root / next(iter(harness.PROBE_REFERENCES)) / "events.raw.jsonl"
            first_raw.write_text("tampered\n", encoding="utf-8")
            with self.assertRaisesRegex(harness.HarnessError, "hash"):
                _verify_probe_manifest(manifest_path)

    def test_private_manifest_rejects_duplicate_receipt_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = _write_valid_probe_manifest(Path(tmp) / "workflow-run")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["session_receipts"] = [manifest["session_receipts"][0]] * 3
            _rewrite_json(manifest_path, manifest)

            with self.assertRaisesRegex(harness.HarnessError, "session IDs"):
                _verify_probe_manifest(manifest_path)

    def test_private_manifest_recomputes_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = _write_valid_probe_manifest(Path(tmp) / "workflow-run")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["public_projection"]["acceptance"]["accepted_sessions"] = 0
            _rewrite_json(manifest_path, manifest)

            with self.assertRaisesRegex(harness.HarnessError, "acceptance"):
                _verify_probe_manifest(manifest_path)

    def test_private_manifest_rejects_extra_public_projection_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = _write_valid_probe_manifest(Path(tmp) / "workflow-run")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["public_projection"]["unexpected_claim"] = "passed anyway"
            _rewrite_json(manifest_path, manifest)

            with self.assertRaisesRegex(harness.HarnessError, "projection"):
                _verify_probe_manifest(manifest_path)

    def test_private_manifest_rejects_extra_result_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "workflow-run"
            manifest_path = _write_valid_probe_manifest(run_root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            first_result = manifest["public_projection"]["results"][0]
            first_result["unexpected_claim"] = "passed anyway"
            receipt_row = manifest["session_receipts"][0]
            receipt_path = run_root / receipt_row["relative_path"]
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["summary"] = first_result
            _rewrite_json(receipt_path, receipt)
            receipt_row["sha256"] = harness.file_sha256(receipt_path)
            _rewrite_json(manifest_path, manifest)

            with self.assertRaisesRegex(harness.HarnessError, "shape"):
                _verify_probe_manifest(manifest_path)

    def test_private_manifest_rejects_fabricated_public_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = _write_valid_probe_manifest(Path(tmp) / "workflow-run")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["public_projection"]["runtime"]["sandbox"] = "workspace-write"
            _rewrite_json(manifest_path, manifest)

            with self.assertRaisesRegex(harness.HarnessError, "runtime"):
                _verify_probe_manifest(manifest_path)

    def test_private_manifest_rejects_non_codex_version_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "workflow-run"
            manifest_path = _write_valid_probe_manifest(run_root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            runtime_receipt_path = run_root / manifest["runtime_receipt"]["relative_path"]
            runtime_receipt = json.loads(
                runtime_receipt_path.read_text(encoding="utf-8")
            )
            stdout_path = run_root / runtime_receipt["commands"]["client-version"][
                "stdout_relative_path"
            ]
            stdout_path.write_text("not-codex 9.9.9\n", encoding="utf-8")
            runtime_receipt["commands"]["client-version"][
                "stdout_sha256"
            ] = harness.file_sha256(stdout_path)
            runtime_receipt["public_runtime"]["client_version"] = "9.9.9"
            manifest["public_projection"]["runtime"] = runtime_receipt["public_runtime"]
            _rewrite_json(runtime_receipt_path, runtime_receipt)
            manifest["runtime_receipt"]["sha256"] = harness.file_sha256(
                runtime_receipt_path
            )
            _rewrite_json(manifest_path, manifest)

            with self.assertRaisesRegex(harness.HarnessError, "version output"):
                _verify_probe_manifest(manifest_path)

    def test_private_manifest_rejects_unverified_codex_argv(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "workflow-run"
            manifest_path = _write_valid_probe_manifest(run_root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            receipt_row = manifest["session_receipts"][0]
            receipt_path = run_root / receipt_row["relative_path"]
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["codex_argv"] = ["codex", "exec", "--not-the-audited-command"]
            _rewrite_json(receipt_path, receipt)
            receipt_row["sha256"] = harness.file_sha256(receipt_path)
            _rewrite_json(manifest_path, manifest)

            with self.assertRaisesRegex(harness.HarnessError, "argv"):
                _verify_probe_manifest(manifest_path)

    @unittest.skipUnless(harness.os.name == "posix", "private CLI receipt fixture requires POSIX permission semantics")
    def test_private_plugin_cli_receipt_retains_the_exact_argv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session = root / "session"
            project = session / "project"
            project.mkdir(parents=True)
            argv = [str(root / "codex"), "plugin", "list", "--json"]
            completed = harness.subprocess.CompletedProcess(
                argv,
                0,
                stdout=b'{"installed": []}',
                stderr=b"",
            )
            with mock.patch.object(harness, "_run_capture", return_value=completed):
                _, parsed, receipt = harness._run_private_cli_command(
                    argv,
                    label="plugin-list",
                    session_root=session,
                    cwd=project,
                    env={},
                    timeout=1,
                    secret_values=(),
                )

            self.assertEqual(receipt["argv"], argv)
            self.assertEqual(parsed, {"installed": []})
            expected = harness._plugin_command_argv(
                argv[0],
                root / "marketplace",
                f"{harness.SKILL_NAME}@{harness.MARKETPLACE_NAME}",
            )
            self.assertEqual(expected["plugin-list"][0], argv[0])
            self.assertIn(str(root / "marketplace"), expected["marketplace-add"])

    def test_install_manifest_rejects_private_and_public_plugin_argv_tampering(self):
        for tamper_target in ("private", "public"):
            with self.subTest(tamper_target=tamper_target), tempfile.TemporaryDirectory() as tmp:
                run_root = Path(tmp) / "smoke-run"
                manifest_path = _write_valid_install_manifest(run_root)
                _verify_probe_manifest(manifest_path, expected_suite="install-smoke")
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                receipt_row = next(
                    row
                    for row in manifest["session_receipts"]
                    if row["session_id"] == "local-marketplace-plugin"
                )
                receipt_path = run_root / receipt_row["relative_path"]
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                if tamper_target == "private":
                    receipt["plugin_command_argv"]["plugin-list"].append("--tampered")
                else:
                    public_argv = manifest["public_projection"]["plugin_installation"][
                        "command_receipts"
                    ]["plugin-list"]["argv"]
                    public_argv.append("--tampered")
                    receipt["plugin_installation"] = manifest["public_projection"][
                        "plugin_installation"
                    ]
                _rewrite_json(receipt_path, receipt)
                receipt_row["sha256"] = harness.file_sha256(receipt_path)
                _rewrite_json(manifest_path, manifest)

                with self.assertRaisesRegex(harness.HarnessError, "plugin command argv"):
                    _verify_probe_manifest(manifest_path, expected_suite="install-smoke")

    def test_private_manifest_recomputes_raw_event_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "workflow-run"
            manifest_path = _write_valid_probe_manifest(run_root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            first = manifest["session_receipts"][0]
            receipt_path = run_root / first["relative_path"]
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            raw_path = receipt_path.parent / "events.raw.jsonl"
            sanitized_path = receipt_path.parent / "events.sanitized.jsonl"
            raw_bytes = b'{"type":"thread.started"}\n'
            sanitized_bytes = harness.sanitize_jsonl_bytes(
                raw_bytes, receipt["absolute_path_mappings"]
            )
            raw_path.write_bytes(raw_bytes)
            sanitized_path.write_bytes(sanitized_bytes)
            receipt["raw_event_stream_sha256"] = harness.sha256_bytes(raw_bytes)
            receipt["sanitized_event_stream_sha256"] = harness.sha256_bytes(
                sanitized_bytes
            )
            receipt["private_artifacts"]["events.raw.jsonl"] = harness.file_sha256(
                raw_path
            )
            receipt["private_artifacts"][
                "events.sanitized.jsonl"
            ] = harness.file_sha256(sanitized_path)
            summary = receipt["summary"]
            summary["event_stream_sha256"] = harness.sha256_bytes(sanitized_bytes)
            summary["event_evidence"] = harness.audit_event_lifecycle(
                harness.parse_jsonl(raw_bytes)
            )
            projected = next(
                row
                for row in manifest["public_projection"]["results"]
                if row["id"] == first["session_id"]
            )
            projected.update(summary)
            _rewrite_json(receipt_path, receipt)
            first["sha256"] = harness.file_sha256(receipt_path)
            _rewrite_json(manifest_path, manifest)

            with self.assertRaisesRegex(harness.HarnessError, "lifecycle"):
                _verify_probe_manifest(manifest_path)

    def test_private_manifest_binds_the_retained_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "workflow-run"
            manifest_path = _write_valid_probe_manifest(run_root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            first = manifest["session_receipts"][0]
            receipt_path = run_root / first["relative_path"]
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            prompt_path = receipt_path.parent / "prompt.txt"
            prompt_path.write_text(
                "Return product-definition and the expected contracts.\n",
                encoding="utf-8",
            )
            receipt["private_artifacts"]["prompt.txt"] = harness.file_sha256(
                prompt_path
            )
            _rewrite_json(receipt_path, receipt)
            first["sha256"] = harness.file_sha256(receipt_path)
            _rewrite_json(manifest_path, manifest)

            with self.assertRaisesRegex(harness.HarnessError, "prompt"):
                _verify_probe_manifest(manifest_path)

    def test_private_manifest_rescans_secret_material(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "workflow-run"
            manifest_path = _write_valid_probe_manifest(run_root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            first = manifest["session_receipts"][0]
            receipt_path = run_root / first["relative_path"]
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            stderr_path = receipt_path.parent / "stderr.raw.txt"
            stderr_path.write_text("abcdefghijklmnop\n", encoding="utf-8")
            receipt["stderr_sha256"] = harness.file_sha256(stderr_path)
            receipt["private_artifacts"]["stderr.raw.txt"] = harness.file_sha256(
                stderr_path
            )
            _rewrite_json(receipt_path, receipt)
            first["sha256"] = harness.file_sha256(receipt_path)
            _rewrite_json(manifest_path, manifest)

            with self.assertRaisesRegex(harness.HarnessError, "credential material"):
                _verify_probe_manifest(manifest_path)

    def test_outputs_are_not_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "result.yaml"
            harness.write_yaml(output, {"result": "first"})
            with self.assertRaisesRegex(harness.HarnessError, "overwrite"):
                harness.write_yaml(output, {"result": "second"})


if __name__ == "__main__":
    unittest.main()
