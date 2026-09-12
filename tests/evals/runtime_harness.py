#!/usr/bin/env python3
"""Auditable Task 6 install-smoke and fresh-agent probe harness.

Raw events, isolated homes, credentials, and absolute path mappings stay under a
caller-provided private audit root outside the public worktree. Generated
summaries contain only derived observations and sanitized hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import queue
import re
import shlex
import shutil
import stat
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


SKILL_NAME = "packaging-product-visuals"
MARKETPLACE_NAME = "ppv-install-smoke"
MODEL = "gpt-5.6-luna"
REASONING_EFFORT = "low"
AUTH_STORE_CONFIG = 'cli_auth_credentials_store="file"'
TOOL_DIR = Path(__file__).resolve().parent
DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GENERATED_ROOT = DEFAULT_REPO_ROOT / ".superpowers" / "task-6-generated"
SCENARIO_PATH = Path("tests/evals/full-workflow-scenarios.yaml")
INSTALL_SCHEMA_PATH = Path("tests/evals/install-smoke-output.schema.json")
PROBE_SCHEMA_PATH = Path("tests/evals/full-workflow-output.schema.json")
AUTH_BASENAME = "auth.json"
CODEX_RUNTIME_TEMP_SYMLINK_NAMES = (
    "apply_patch",
    "applypatch",
    "codex-execve-wrapper",
)
CODEX_RUNTIME_ARG0_DIR = re.compile(r"codex-[A-Za-z0-9]+")
UNSUPPORTED_STRUCTURED_OUTPUT_KEYWORDS = frozenset({"uniqueItems"})

STANDALONE_LAYOUTS = (
    {
        "id": "explicit-codex-home-skills",
        "install_relative_path": "$CODEX_HOME/skills/packaging-product-visuals",
        "codex_home": "explicit",
        "cwd": "isolated empty project outside the install tree",
    },
    {
        "id": "default-codex-home-skills",
        "install_relative_path": "$HOME/.codex/skills/packaging-product-visuals",
        "codex_home": "derived",
        "cwd": "isolated empty project outside the install tree",
    },
    {
        "id": "user-agents-skills",
        "install_relative_path": "$HOME/.agents/skills/packaging-product-visuals",
        "codex_home": "derived",
        "cwd": "isolated empty project outside the install tree",
    },
    {
        "id": "project-agents-skills",
        "install_relative_path": "<project>/.agents/skills/packaging-product-visuals",
        "codex_home": "derived",
        "cwd": "isolated project containing only the project-local install",
    },
)

PROBE_REFERENCES = {
    "uncertain-product-start": (
        "SKILL.md",
        "references/workflow.md",
        "references/contracts.md",
        "references/product-and-research.md",
        "references/packaging-directions.md",
    ),
    "approved-package-gallery": (
        "SKILL.md",
        "references/workflow.md",
        "references/contracts.md",
        "references/ecommerce-assets.md",
        "references/rights-and-privacy.md",
    ),
    "three-sku-full-chain": (
        "SKILL.md",
        "references/workflow.md",
        "references/contracts.md",
        "references/product-and-research.md",
        "references/packaging-directions.md",
        "references/ecommerce-assets.md",
    ),
}

WRITE_COMMAND = re.compile(
    r"(?:^|[\s;&|'\"])(?:/[^\s'\"]+/)?(?:touch|rm|mv|cp|install|mkdir|rmdir|truncate|dd|tee|ln)\b"
    r"|(?<![0-9])>>?\s*[^&|\s]+"
)
DISALLOWED_ITEM_TYPES = {
    "file_change",
    "image_generation",
    "mcp_tool_call",
    "subagent",
    "web_search",
}


class HarnessError(RuntimeError):
    """A validation or execution failure that must produce a nonzero exit."""


def _require_private_runtime_support() -> None:
    if os.name != "posix":
        raise HarnessError("private runtime harness requires POSIX permission semantics")


def capture_local_execution_clock(sampled: datetime | None = None) -> dict[str, str]:
    observed = sampled or datetime.now().astimezone()
    if observed.tzinfo is None or observed.utcoffset() is None:
        observed = observed.astimezone()
    observed = observed.replace(microsecond=0)
    return {
        "executed_on": observed.date().isoformat(),
        "started_at_local": observed.isoformat(),
    }


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _resolved(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def require_private_audit_root(repo_root: Path, audit_root: Path) -> Path:
    repo = _resolved(repo_root)
    audit = _resolved(audit_root)
    if audit == repo or _is_relative_to(audit, repo):
        raise HarnessError("private audit root must be outside the public worktree")
    return audit


def require_safe_summary_path(
    repo_root: Path,
    output_path: Path,
    allow_public_output: bool = False,
) -> Path:
    repo = _resolved(repo_root)
    output = _resolved(output_path)
    if _is_relative_to(output, repo) and not _is_relative_to(output, repo / ".superpowers"):
        if not allow_public_output:
            raise HarnessError(
                "summary output inside the public worktree requires --allow-public-output"
            )
    if output.exists() or output.is_symlink():
        raise HarnessError(f"refusing to overwrite existing output: {output.name}")
    return output


def _write_bytes(path: Path, data: bytes, private: bool = False) -> None:
    if private:
        _require_private_runtime_support()
    if path.exists() or path.is_symlink():
        raise HarnessError(f"refusing to overwrite existing output: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if private:
        path.parent.chmod(0o700)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_bytes(data)
    if private:
        temporary.chmod(0o600)
    temporary.replace(path)


def write_yaml(path: Path, value: Any, private: bool = False) -> None:
    rendered = yaml.safe_dump(
        value,
        sort_keys=False,
        allow_unicode=True,
        width=100,
    ).encode("utf-8")
    _write_bytes(path, rendered, private=private)


def write_json(path: Path, value: Any, private: bool = False) -> None:
    rendered = (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    _write_bytes(path, rendered, private=private)


def write_text(path: Path, value: str, private: bool = False) -> None:
    _write_bytes(path, value.encode("utf-8"), private=private)


def _regular_files(root: Path) -> list[Path]:
    if not root.is_dir():
        raise HarnessError(f"tree root does not exist: {root}")
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise HarnessError(f"symlink is not allowed in audited trees: {path}")
        if path.is_file():
            files.append(path.relative_to(root))
    return sorted(files, key=lambda path: path.as_posix())


def _symlink_paths(root: Path) -> list[Path]:
    if not root.is_dir():
        raise HarnessError(f"tree root does not exist: {root}")
    links: list[Path] = []
    for directory_name, directory_names, file_names in os.walk(root, followlinks=False):
        directory = Path(directory_name)
        for name in list(directory_names):
            path = directory / name
            if path.is_symlink():
                links.append(path.relative_to(root))
                directory_names.remove(name)
        for name in file_names:
            path = directory / name
            if path.is_symlink():
                links.append(path.relative_to(root))
    return sorted(links, key=lambda path: path.as_posix())


def _is_codex_runtime_temp_symlink(relative_path: Path) -> bool:
    parts = relative_path.parts
    return (
        len(parts) >= 5
        and parts[-5] in {"codex-home", ".codex"}
        and parts[-4:-2] == ("tmp", "arg0")
        and CODEX_RUNTIME_ARG0_DIR.fullmatch(parts[-2]) is not None
        and parts[-1] in CODEX_RUNTIME_TEMP_SYMLINK_NAMES
    )


def _remove_codex_runtime_temp_symlinks(
    session_root: Path,
    codex_bin: str,
) -> dict[str, Any]:
    links = _symlink_paths(session_root)
    unexpected = [path for path in links if not _is_codex_runtime_temp_symlink(path)]
    if unexpected:
        raise HarnessError(
            f"unexpected symlink in private runtime tree: {unexpected[0].as_posix()}"
        )
    if not links:
        return {"removed_count": 0, "removed": []}

    expected_version = _parse_codex_version(
        _command_version([codex_bin, "--version"], session_root)
    )
    target_evidence: dict[Path, dict[str, str]] = {}
    removed: list[dict[str, str]] = []
    for relative_path in links:
        path = session_root / relative_path
        raw_target = Path(os.readlink(path))
        if not raw_target.is_absolute():
            raise HarnessError("Codex runtime temp symlink target was not absolute")
        try:
            target = path.resolve(strict=True)
        except OSError as error:
            raise HarnessError("Codex runtime temp symlink target was unavailable") from error
        if target.name != "codex" or not target.is_file() or not os.access(target, os.X_OK):
            raise HarnessError("Codex runtime temp symlink target was not an executable Codex file")
        if target not in target_evidence:
            target_version = _parse_codex_version(
                _command_version([str(target), "--version"], session_root)
            )
            if target_version != expected_version:
                raise HarnessError("Codex runtime temp symlink target version did not match")
            target_evidence[target] = {
                "target_basename": target.name,
                "target_sha256": file_sha256(target),
                "target_client_version": target_version,
            }
        removed.append(
            {
                "relative_path": relative_path.as_posix(),
                **target_evidence[target],
            }
        )

    for relative_path in links:
        (session_root / relative_path).unlink()
    if _symlink_paths(session_root):
        raise HarnessError("runtime temp symlink cleanup was incomplete")
    return {
        "removed_count": len(removed),
        "removed": removed,
    }


def tree_digest(root: Path, relative_paths: list[Path] | tuple[Path, ...] | None = None) -> str:
    paths = list(relative_paths) if relative_paths is not None else _regular_files(root)
    digest = hashlib.sha256()
    for relative_path in sorted(paths, key=lambda path: path.as_posix()):
        candidate = root / relative_path
        if candidate.is_symlink() or not candidate.is_file():
            raise HarnessError(f"tree entry is not a regular file: {relative_path.as_posix()}")
        digest.update(relative_path.as_posix().encode("utf-8"))
        digest.update(candidate.read_bytes())
    return digest.hexdigest()


def tree_snapshot(root: Path) -> dict[str, Any]:
    relative_paths = _regular_files(root)
    return {
        "file_count": len(relative_paths),
        "files": [path.as_posix() for path in relative_paths],
        "tree_sha256": tree_digest(root, relative_paths),
    }


def _run_capture(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    input_bytes: bytes | None = None,
    timeout: int = 900,
) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            argv,
            shell=False,
            cwd=cwd,
            env=env,
            input=input_bytes,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise HarnessError(f"command timed out after {timeout}s: {argv[0]}") from error


def _skills_list_request_messages(cwd: Path) -> list[dict[str, Any]]:
    return [
        {
            "method": "initialize",
            "id": 0,
            "params": {
                "clientInfo": {
                    "name": "packaging-product-visuals-audit",
                    "title": "Packaging Product Visuals Audit",
                    "version": "1.0.0",
                },
                "capabilities": {"experimentalApi": True},
            },
        },
        {"method": "initialized", "params": {}},
        {
            "method": "skills/list",
            "id": 1,
            "params": {"cwds": [str(cwd)], "forceReload": True},
        },
    ]


def _skills_list_request_bytes(cwd: Path) -> bytes:
    return (
        "".join(
            json.dumps(
                message,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
            for message in _skills_list_request_messages(cwd)
        )
    ).encode("utf-8")


def _skills_list_response(stdout: bytes) -> dict[str, Any]:
    responses: list[dict[str, Any]] = []
    for line_number, line in enumerate(stdout.decode("utf-8", errors="strict").splitlines(), 1):
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as error:
            raise HarnessError(f"app-server returned invalid JSONL at line {line_number}") from error
        if isinstance(message, dict) and message.get("id") == 1:
            responses.append(message)
    if len(responses) != 1:
        raise HarnessError("app-server skills/list did not return exactly one response")
    return responses[0]


def _skill_discovery_evidence(
    response: dict[str, Any],
    *,
    project: Path,
    install: Path,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    if response.get("error") is not None:
        raise HarnessError("app-server skills/list returned an error")
    result = response.get("result")
    data = result.get("data") if isinstance(result, dict) else None
    if not isinstance(data, list):
        raise HarnessError("app-server skills/list response omitted data")
    cwd_rows = [
        row
        for row in data
        if isinstance(row, dict)
        and isinstance(row.get("cwd"), str)
        and _resolved(Path(row["cwd"])) == _resolved(project)
    ]
    if len(cwd_rows) != 1:
        raise HarnessError("app-server skills/list did not return the audited cwd exactly once")
    row = cwd_rows[0]
    parse_errors = row.get("errors")
    skills = row.get("skills")
    if not isinstance(parse_errors, list) or parse_errors:
        raise HarnessError("app-server skills/list reported a parse error")
    if not isinstance(skills, list):
        raise HarnessError("app-server skills/list response omitted skills")
    matches = [
        skill
        for skill in skills
        if isinstance(skill, dict)
        and skill.get("name") in {SKILL_NAME, f"{SKILL_NAME}:{SKILL_NAME}"}
    ]
    if len(matches) != 1:
        raise HarnessError("app-server skills/list did not find exactly one audited Skill")
    entry = matches[0]
    observed_path = entry.get("path")
    expected_path = install / "SKILL.md"
    if (
        entry.get("enabled") is not True
        or not isinstance(observed_path, str)
        or _resolved(Path(observed_path)) != _resolved(expected_path)
    ):
        raise HarnessError("app-server skills/list did not enable the exact installed Skill")
    file_hashes = candidate.get("file_sha256")
    if not isinstance(file_hashes, dict):
        raise HarnessError("candidate file hash inventory is unavailable")
    contracts_path = install / "references" / "contracts.md"
    if (
        expected_path.is_symlink()
        or not expected_path.is_file()
        or contracts_path.is_symlink()
        or not contracts_path.is_file()
        or file_sha256(expected_path) != file_hashes.get("SKILL.md")
        or file_sha256(contracts_path) != file_hashes.get("references/contracts.md")
    ):
        raise HarnessError("discovered Skill or relative reference did not match the candidate")
    return {
        "verified": True,
        "matching_skill_count": 1,
        "enabled": True,
        "scope": entry.get("scope"),
        "plugin_id": entry.get("pluginId"),
        "relative_reference_verified": True,
    }


def _run_skill_discovery_protocol(
    *,
    session_root: Path,
    project: Path,
    install: Path,
    candidate: dict[str, Any],
    codex_bin: str,
    env: dict[str, str],
    timeout: int,
    secret_values: tuple[bytes, ...],
) -> tuple[bool, dict[str, Any], list[str]]:
    messages = _skills_list_request_messages(project)
    request_bytes = _skills_list_request_bytes(project)
    argv = [codex_bin, "app-server", "--stdio"]
    process = subprocess.Popen(
        argv,
        shell=False,
        cwd=project,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None
    stdout_queue: queue.Queue[bytes | None] = queue.Queue()
    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []

    def read_stdout() -> None:
        for line in iter(process.stdout.readline, b""):
            stdout_chunks.append(line)
            stdout_queue.put(line)
        stdout_queue.put(None)

    def read_stderr() -> None:
        for chunk in iter(lambda: process.stderr.read(4096), b""):
            stderr_chunks.append(chunk)

    stdout_thread = threading.Thread(target=read_stdout, daemon=True)
    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    stdout_thread.start()
    stderr_thread.start()

    def send(message: dict[str, Any]) -> None:
        process.stdin.write(
            (
                json.dumps(
                    message,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8")
        )
        process.stdin.flush()

    response: dict[str, Any] | None = None
    protocol_error: str | None = None
    deadline = time.monotonic() + min(timeout, 30)
    try:
        send(messages[0])
        initialized = False
        while time.monotonic() < deadline:
            remaining = max(0.01, deadline - time.monotonic())
            try:
                line = stdout_queue.get(timeout=remaining)
            except queue.Empty:
                protocol_error = "app-server skills/list timed out"
                break
            if line is None:
                protocol_error = "app-server exited before skills/list completed"
                break
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(message, dict):
                continue
            if message.get("id") == 0 and not initialized:
                if message.get("error") is not None:
                    protocol_error = "app-server initialize returned an error"
                    break
                send(messages[1])
                send(messages[2])
                initialized = True
            elif message.get("id") == 1:
                response = message
                break
            elif message.get("id") is not None and message.get("method"):
                send(
                    {
                        "id": message["id"],
                        "error": {"code": -32601, "message": "Not implemented"},
                    }
                )
        else:
            protocol_error = "app-server skills/list timed out"
    finally:
        try:
            process.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)

    stdout = b"".join(stdout_chunks)
    stderr = b"".join(stderr_chunks)
    _write_bytes(session_root / "skills-list.request.jsonl", request_bytes, private=True)
    _write_bytes(session_root / "skills-list.raw.jsonl", stdout, private=True)
    _write_bytes(session_root / "skills-list.stderr.raw.txt", stderr, private=True)
    leak_detected = _contains_secret_material([stdout, stderr], secret_values)
    errors: list[str] = []
    verified = False
    if protocol_error is not None:
        errors.append(protocol_error)
    elif response is None:
        errors.append("app-server skills/list response was unavailable")
    else:
        try:
            verified = _skill_discovery_evidence(
                response,
                project=project,
                install=install,
                candidate=candidate,
            )["verified"]
        except HarnessError as error:
            errors.append(str(error))
    if leak_detected:
        errors.append("credential material appeared in app-server skills/list output")
    receipt = {
        "argv": argv,
        "request_sha256": sha256_bytes(request_bytes),
        "stdout_sha256": sha256_bytes(stdout),
        "stderr_sha256": sha256_bytes(stderr),
        "force_reload": True,
        "credential_leak_detected": leak_detected,
    }
    return verified, receipt, errors


def _require_success(process: subprocess.CompletedProcess[bytes], label: str) -> bytes:
    if process.returncode != 0:
        detail = process.stderr.decode("utf-8", errors="replace").strip()
        raise HarnessError(f"{label} failed with exit {process.returncode}: {detail[:500]}")
    return process.stdout


def discover_candidate(repo_root: Path) -> dict[str, Any]:
    skill_root = repo_root / "skills" / SKILL_NAME
    process = _run_capture(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            f"skills/{SKILL_NAME}",
        ],
        cwd=repo_root,
    )
    output = _require_success(process, "candidate inventory")
    repo_relative = [Path(line) for line in output.decode().splitlines() if line.strip()]
    if not repo_relative:
        raise HarnessError("candidate inventory is empty")
    skill_relative: list[Path] = []
    for path in repo_relative:
        try:
            relative = path.relative_to(Path("skills") / SKILL_NAME)
        except ValueError as error:
            raise HarnessError(f"candidate escaped Skill root: {path}") from error
        candidate = repo_root / path
        if candidate.is_symlink() or not candidate.is_file():
            raise HarnessError(f"candidate entry is not a regular file: {path}")
        if "__pycache__" in relative.parts or relative.suffix == ".pyc":
            raise HarnessError(f"generated Python artifact entered candidate: {path}")
        skill_relative.append(relative)
    skill_relative.sort(key=lambda path: path.as_posix())
    status = _run_capture(
        ["git", "status", "--porcelain", "--", f"skills/{SKILL_NAME}"],
        cwd=repo_root,
    )
    status_bytes = _require_success(status, "candidate status")
    head = _command_version(["git", "rev-parse", "HEAD"], repo_root)
    return {
        "source": "git ls-files --cached --others --exclude-standard",
        "file_count": len(skill_relative),
        "tree_sha256": tree_digest(skill_root, skill_relative),
        "files": [path.as_posix() for path in skill_relative],
        "file_sha256": {
            path.as_posix(): file_sha256(skill_root / path) for path in skill_relative
        },
        "git_head": head,
        "git_status": "dirty" if status_bytes.strip() else "clean",
        "git_status_sha256": sha256_bytes(status_bytes),
    }


def load_scenarios(repo_root: Path) -> list[dict[str, Any]]:
    path = repo_root / SCENARIO_PATH
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    scenarios = value.get("scenarios") if isinstance(value, dict) else None
    if not isinstance(scenarios, list) or not scenarios:
        raise HarnessError("full-workflow scenario file has no scenarios")
    ids = [scenario.get("id") for scenario in scenarios]
    if len(ids) != len(set(ids)) or set(ids) != set(PROBE_REFERENCES):
        raise HarnessError("full-workflow scenario IDs do not match the three probe contracts")
    return scenarios


def load_plugin_version(repo_root: Path) -> str:
    path = repo_root / ".codex-plugin" / "plugin.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("name") != SKILL_NAME or not isinstance(value.get("version"), str):
        raise HarnessError("plugin manifest name/version is invalid")
    return value["version"]


def harness_artifact_receipts(repo_root: Path) -> dict[str, str]:
    return {
        "runtime_harness_sha256": file_sha256(Path(__file__).resolve()),
        "install_schema_sha256": file_sha256(repo_root / INSTALL_SCHEMA_PATH),
        "probe_schema_sha256": file_sha256(repo_root / PROBE_SCHEMA_PATH),
        "scenario_sha256": file_sha256(repo_root / SCENARIO_PATH),
        "plugin_manifest_sha256": file_sha256(
            repo_root / ".codex-plugin" / "plugin.json"
        ),
    }


def require_candidate_unchanged(repo_root: Path, expected: dict[str, Any]) -> None:
    observed = discover_candidate(repo_root)
    if observed != expected:
        raise HarnessError("Skill candidate changed during the audited run")


def _command_version(argv: list[str], cwd: Path) -> str:
    process = _run_capture(argv, cwd=cwd, timeout=30)
    return _require_success(process, "version probe").decode("utf-8", errors="replace").strip()


def _resolve_codex_executable(codex_bin: str) -> str:
    candidate = shutil.which(codex_bin) if os.sep not in codex_bin else codex_bin
    if not candidate:
        raise HarnessError("codex executable is unavailable")
    try:
        resolved = Path(candidate).expanduser().resolve(strict=True)
    except OSError as error:
        raise HarnessError("codex executable could not be resolved") from error
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise HarnessError("codex executable is not an executable file")
    return str(resolved)


def _parse_codex_version(client_line: str) -> str:
    match = re.fullmatch(
        r"codex-cli[ \t]+([0-9A-Za-z][0-9A-Za-z._+\-]*)",
        client_line.strip(),
    )
    if match is None:
        raise HarnessError("Codex version output did not match 'codex-cli <version>'")
    return match.group(1)


def observed_runtime(repo_root: Path, codex_bin: str, model: str) -> dict[str, Any]:
    executable = _resolve_codex_executable(codex_bin)
    client_line = _command_version([executable, "--version"], repo_root)
    client_version = _parse_codex_version(client_line)
    os_name = platform.system()
    os_version = platform.release()
    os_build = platform.version()
    if os_name == "Darwin" and shutil.which("sw_vers"):
        os_name = "macOS"
        os_version = _command_version(["sw_vers", "-productVersion"], repo_root)
        os_build = _command_version(["sw_vers", "-buildVersion"], repo_root)
    return {
        "client": "codex-cli",
        "client_version": client_version,
        "client_executable_sha256": file_sha256(Path(executable)),
        "model": model,
        "reasoning_effort": REASONING_EFFORT,
        "sandbox": "read-only",
        "ephemeral": True,
        "operating_system": {
            "name": os_name,
            "version": os_version,
            "build": os_build,
            "architecture": platform.machine(),
        },
        "capture_basis": {
            "client_version": "codex --version",
            "operating_system": "runtime platform probes and sw_vers on macOS",
            "invocation_settings": "generated codex exec argv",
        },
    }


def _runtime_from_command_outputs(
    *,
    client_line: str,
    system_name: str,
    system_release: str,
    system_build: str,
    architecture: str,
    model: str,
    client_executable_sha256: str,
    macos_version: str | None = None,
    macos_build: str | None = None,
) -> dict[str, Any]:
    client_version = _parse_codex_version(client_line)
    if not re.fullmatch(r"[0-9a-f]{64}", client_executable_sha256):
        raise HarnessError("Codex executable SHA-256 was invalid")
    os_name = system_name
    os_version = system_release
    os_build = system_build
    if system_name == "Darwin":
        if not macos_version or not macos_build:
            raise HarnessError("macOS runtime receipt omitted sw_vers output")
        os_name = "macOS"
        os_version = macos_version
        os_build = macos_build
    return {
        "client": "codex-cli",
        "client_version": client_version,
        "client_executable_sha256": client_executable_sha256,
        "model": model,
        "reasoning_effort": REASONING_EFFORT,
        "sandbox": "read-only",
        "ephemeral": True,
        "operating_system": {
            "name": os_name,
            "version": os_version,
            "build": os_build,
            "architecture": architecture,
        },
        "capture_basis": {
            "client_version": "codex --version",
            "operating_system": "uname and sw_vers on macOS",
            "invocation_settings": "generated codex exec argv",
        },
    }


def _capture_runtime_command(
    *,
    run_root: Path,
    label: str,
    argv: list[str],
    cwd: Path,
) -> tuple[str, dict[str, Any]]:
    process = _run_capture(argv, cwd=cwd, timeout=30)
    runtime_root = run_root / "runtime"
    stdout_path = runtime_root / f"{label}.stdout.txt"
    stderr_path = runtime_root / f"{label}.stderr.txt"
    _write_bytes(stdout_path, process.stdout, private=True)
    _write_bytes(stderr_path, process.stderr, private=True)
    if process.returncode != 0:
        raise HarnessError(f"runtime probe {label} exited {process.returncode}")
    value = process.stdout.decode("utf-8", errors="strict").strip()
    if not value:
        raise HarnessError(f"runtime probe {label} returned empty output")
    return value, {
        "argv": argv,
        "exit_code": process.returncode,
        "stdout_relative_path": stdout_path.relative_to(run_root).as_posix(),
        "stdout_sha256": sha256_bytes(process.stdout),
        "stderr_relative_path": stderr_path.relative_to(run_root).as_posix(),
        "stderr_sha256": sha256_bytes(process.stderr),
    }


def capture_runtime_evidence(
    repo_root: Path,
    codex_bin: str,
    model: str,
    run_root: Path,
) -> tuple[dict[str, Any], dict[str, str]]:
    executable = _resolve_codex_executable(codex_bin)
    executable_sha256 = file_sha256(Path(executable))
    commands: dict[str, dict[str, Any]] = {}

    def capture(label: str, argv: list[str]) -> str:
        value, receipt = _capture_runtime_command(
            run_root=run_root,
            label=label,
            argv=argv,
            cwd=repo_root,
        )
        commands[label] = receipt
        return value

    uname = shutil.which("uname") or "uname"
    client_line = capture("client-version", [executable, "--version"])
    system_name = capture("uname-system", [uname, "-s"])
    system_release = capture("uname-release", [uname, "-r"])
    system_build = capture("uname-build", [uname, "-v"])
    architecture = capture("uname-architecture", [uname, "-m"])
    macos_version = None
    macos_build = None
    if system_name == "Darwin":
        sw_vers = shutil.which("sw_vers")
        if not sw_vers:
            raise HarnessError("sw_vers is unavailable on Darwin")
        macos_version = capture("sw-vers-version", [sw_vers, "-productVersion"])
        macos_build = capture("sw-vers-build", [sw_vers, "-buildVersion"])
    runtime = _runtime_from_command_outputs(
        client_line=client_line,
        system_name=system_name,
        system_release=system_release,
        system_build=system_build,
        architecture=architecture,
        model=model,
        client_executable_sha256=executable_sha256,
        macos_version=macos_version,
        macos_build=macos_build,
    )
    receipt_path = run_root / "runtime" / "runtime-receipt.json"
    write_json(
        receipt_path,
        {
            "public_runtime": runtime,
            "client_executable": {
                "resolved_path": executable,
                "sha256": executable_sha256,
            },
            "commands": commands,
        },
        private=True,
    )
    return runtime, {
        "relative_path": receipt_path.relative_to(run_root).as_posix(),
        "sha256": file_sha256(receipt_path),
    }


def _sanitize_value(value: Any, mappings: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize_value(child, mappings) for key, child in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(child, mappings) for child in value]
    if isinstance(value, str):
        result = value
        for source, replacement in sorted(mappings.items(), key=lambda item: len(item[0]), reverse=True):
            if source:
                result = result.replace(source, replacement)
        return result
    return value


def sanitize_jsonl_bytes(raw: bytes, mappings: dict[str, str]) -> bytes:
    rendered: list[str] = []
    for line in raw.decode("utf-8", errors="replace").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            sanitized = _sanitize_value(line, mappings)
            rendered.append(str(sanitized))
        else:
            sanitized = _sanitize_value(value, mappings)
            rendered.append(
                json.dumps(sanitized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            )
    return (("\n".join(rendered) + "\n") if rendered else "").encode("utf-8")


def parse_jsonl(raw: bytes) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(raw.decode("utf-8", errors="strict").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise HarnessError(f"invalid JSONL at line {line_number}") from error
        if not isinstance(value, dict):
            raise HarnessError(f"JSONL line {line_number} is not an object")
        events.append(value)
    if not events:
        raise HarnessError("codex event stream is empty")
    return events


def _completed_command_items(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for event in events:
        item = event.get("item")
        if (
            event.get("type") == "item.completed"
            and isinstance(item, dict)
            and item.get("type") == "command_execution"
        ):
            items.append(item)
    return items


def _content_marker(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and stripped != "---" and len(stripped) >= 4:
            return stripped
    raise HarnessError(f"required read target has no usable content marker: {path}")


def _unwrapped_command_tokens(command: str) -> list[str] | None:
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return None
    if not tokens:
        return None
    if (
        len(tokens) == 3
        and Path(tokens[0]).name in {"sh", "bash", "zsh"}
        and tokens[1] in {"-c", "-lc"}
    ):
        try:
            tokens = shlex.split(tokens[2], posix=True)
        except ValueError:
            return None
    return tokens


def _exact_read_target(command: str) -> str | None:
    tokens = _unwrapped_command_tokens(command)
    if not tokens:
        return None
    executable = Path(tokens[0]).name
    if executable == "cat":
        if len(tokens) == 2:
            return tokens[1]
        if len(tokens) == 3 and tokens[1] == "--":
            return tokens[2]
    if executable == "sed":
        if len(tokens) == 4 and tokens[1:3] == ["-n", "1,220p"]:
            return tokens[3]
        if len(tokens) == 5 and tokens[1:4] == ["-n", "1,220p", "--"]:
            return tokens[4]
    return None


def _resolved_read_target(command: str, required_paths: list[Path]) -> str | None:
    target = _exact_read_target(command)
    if target is None:
        return None
    skill_roots = [path.parent for path in required_paths if path.name == "SKILL.md"]
    if len(skill_roots) != 1:
        return target
    skill_root = skill_roots[0]
    for prefix in ("$PPV_SKILL_ROOT", "${PPV_SKILL_ROOT}"):
        if target == prefix:
            return str(skill_root)
        if target.startswith(prefix + "/"):
            relative = Path(target[len(prefix) + 1 :])
            if relative.is_absolute() or ".." in relative.parts:
                return None
            return str(skill_root / relative)
    return target


def _public_command_text(command: str) -> str:
    tokens = _unwrapped_command_tokens(command)
    target = _exact_read_target(command)
    if tokens and target is not None:
        if Path(tokens[0]).name == "cat":
            return shlex.join(["cat", target])
        return shlex.join(["sed", "-n", "1,220p", target])
    try:
        outer_tokens = shlex.split(command, posix=True)
    except ValueError:
        return command
    if outer_tokens and Path(outer_tokens[0]).is_absolute():
        outer_tokens[0] = f"<executable:{Path(outer_tokens[0]).name}>"
        return shlex.join(outer_tokens)
    return command


def audit_command_events(
    events: list[dict[str, Any]],
    required_paths: list[Path],
    *,
    require_content_markers: bool = False,
) -> Path:
    commands = _completed_command_items(events)
    successful = [item for item in commands if item.get("exit_code") == 0]
    all_text = [str(item.get("command", "")) for item in commands]
    expected_targets = [str(path) for path in required_paths]
    observed_targets = [
        _resolved_read_target(str(item.get("command", "")), required_paths)
        for item in commands
    ]
    unexpected_command_count = sum(
        target not in expected_targets for target in observed_targets
    )
    nonzero_command_exit_count = sum(item.get("exit_code") != 0 for item in commands)
    target_counts = {
        target: observed_targets.count(target) for target in expected_targets
    }
    duplicate_required_read_count = sum(
        max(0, count - 1) for count in target_counts.values()
    )
    all_commands_allowed = (
        len(commands) == len(expected_targets)
        and unexpected_command_count == 0
        and nonzero_command_exit_count == 0
        and all(count == 1 for count in target_counts.values())
    )
    reads: list[dict[str, Any]] = []
    for required_path in required_paths:
        marker = _content_marker(required_path) if require_content_markers else None
        matching_items = [
            item
            for item in successful
            if _resolved_read_target(
                str(item.get("command", "")), required_paths
            )
            == str(required_path)
        ]
        marker_observed = marker is None or any(
            marker in str(item.get("aggregated_output", "")) for item in matching_items
        )
        reads.append(
            {
                "path": str(required_path),
                "target_sha256": file_sha256(required_path),
                "content_marker_sha256": sha256_bytes(marker.encode("utf-8")) if marker else None,
                "path_read_command_observed": bool(matching_items),
                "content_marker_observed": marker_observed,
                "succeeded": bool(matching_items) and marker_observed,
            }
        )
    command_receipts = []
    for item in commands:
        command = str(item.get("command", ""))
        output = str(item.get("aggregated_output", ""))
        item_id = str(item.get("id", ""))
        command_receipts.append(
            {
                "item_id_sha256": sha256_bytes(item_id.encode("utf-8")),
                "command": command,
                "command_sha256": sha256_bytes(command.encode("utf-8")),
                "exit_code": item.get("exit_code"),
                "output_sha256": sha256_bytes(output.encode("utf-8")),
            }
        )
    return {
        "completed_command_count": len(commands),
        "successful_command_count": len(successful),
        "commands": command_receipts,
        "required_reads": reads,
        "required_reads_succeeded": (
            bool(reads)
            and all(read["succeeded"] for read in reads)
            and all_commands_allowed
        ),
        "all_commands_allowed": all_commands_allowed,
        "unexpected_command_count": unexpected_command_count,
        "duplicate_required_read_count": duplicate_required_read_count,
        "nonzero_command_exit_count": nonzero_command_exit_count,
        "write_like_command_detected": any(
            _exact_read_target(command) is None and WRITE_COMMAND.search(command)
            for command in all_text
        ),
    }


def audit_event_lifecycle(events: list[dict[str, Any]]) -> dict[str, Any]:
    event_type_counts: dict[str, int] = {}
    item_type_counts: dict[str, int] = {}
    disallowed: set[str] = set()
    failed_event_count = 0
    command_started_counts: dict[str, int] = {}
    command_completed_counts: dict[str, int] = {}
    command_started_indexes: dict[str, list[int]] = {}
    command_completed_indexes: dict[str, list[int]] = {}
    missing_command_item_ids = 0
    item_event_indexes: list[int] = []
    nonzero_command_exit_count = 0
    event_indexes: dict[str, list[int]] = {
        "thread.started": [],
        "turn.started": [],
        "turn.completed": [],
    }
    for index, event in enumerate(events):
        event_type = str(event.get("type", "<missing>"))
        event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
        if event_type in event_indexes:
            event_indexes[event_type].append(index)
        if "error" in event_type or "failed" in event_type:
            failed_event_count += 1
        item = event.get("item")
        if isinstance(item, dict):
            item_event_indexes.append(index)
            item_id = item.get("id")
            item_type = str(item.get("type", "<missing>"))
            item_type_counts[item_type] = item_type_counts.get(item_type, 0) + 1
            if item_type == "command_execution" and event_type in {
                "item.started",
                "item.completed",
            }:
                if not isinstance(item_id, str) or not item_id:
                    missing_command_item_ids += 1
                elif event_type == "item.started":
                    command_started_counts[item_id] = command_started_counts.get(item_id, 0) + 1
                    command_started_indexes.setdefault(item_id, []).append(index)
                else:
                    command_completed_counts[item_id] = (
                        command_completed_counts.get(item_id, 0) + 1
                    )
                    command_completed_indexes.setdefault(item_id, []).append(index)
                    if item.get("exit_code") != 0:
                        nonzero_command_exit_count += 1
                        failed_event_count += 1
            if item_type in DISALLOWED_ITEM_TYPES:
                disallowed.add(item_type)
            if item.get("status") == "failed":
                failed_event_count += 1
    single_thread_turn = all(
        len(event_indexes[event_type]) == 1
        for event_type in ("thread.started", "turn.started", "turn.completed")
    )
    event_order_valid = False
    if single_thread_turn:
        thread_index = event_indexes["thread.started"][0]
        turn_start_index = event_indexes["turn.started"][0]
        turn_complete_index = event_indexes["turn.completed"][0]
        event_order_valid = (
            thread_index < turn_start_index < turn_complete_index
            and all(turn_start_index < index < turn_complete_index for index in item_event_indexes)
        )
    command_ids = set(command_started_counts) | set(command_completed_counts)
    incomplete_item_count = sum(
        command_started_counts.get(item_id, 0) != 1
        or command_completed_counts.get(item_id, 0) != 1
        for item_id in command_ids
    ) + missing_command_item_ids
    unmatched_completed_item_count = sum(
        item_id not in command_started_counts for item_id in command_completed_counts
    )
    duplicate_item_event_count = sum(
        max(0, count - 1)
        for count in (*command_started_counts.values(), *command_completed_counts.values())
    )
    command_pair_order_valid = all(
        len(command_started_indexes.get(item_id, [])) == 1
        and len(command_completed_indexes.get(item_id, [])) == 1
        and command_started_indexes[item_id][0] < command_completed_indexes[item_id][0]
        for item_id in command_ids
    )
    lifecycle_complete = (
        single_thread_turn
        and event_order_valid
        and incomplete_item_count == 0
        and unmatched_completed_item_count == 0
        and duplicate_item_event_count == 0
        and command_pair_order_valid
        and nonzero_command_exit_count == 0
    )
    return {
        "jsonl_line_count": len(events),
        "event_type_counts": dict(sorted(event_type_counts.items())),
        "item_type_counts": dict(sorted(item_type_counts.items())),
        "single_thread_turn": single_thread_turn,
        "event_order_valid": event_order_valid,
        "lifecycle_complete": lifecycle_complete,
        "failed_event_count": failed_event_count,
        "incomplete_item_count": incomplete_item_count,
        "unmatched_completed_item_count": unmatched_completed_item_count,
        "duplicate_item_event_count": duplicate_item_event_count,
        "command_pair_order_valid": command_pair_order_valid,
        "nonzero_command_exit_count": nonzero_command_exit_count,
        "disallowed_item_types": sorted(disallowed),
    }


def _last_agent_message(events: list[dict[str, Any]]) -> Any | None:
    messages: list[str] = []
    for event in events:
        item = event.get("item")
        if (
            event.get("type") == "item.completed"
            and isinstance(item, dict)
            and item.get("type") == "agent_message"
            and isinstance(item.get("text"), str)
        ):
            messages.append(item["text"])
    if not messages:
        return None
    try:
        return json.loads(messages[-1])
    except json.JSONDecodeError:
        return None


INSTALL_OUTPUT_KEYS = {
    "scenario_id",
    "skill_invoked",
    "status",
    "capability_gap",
    "artifact_invented",
    "files_written",
    "explanation",
}


def _unsupported_schema_keyword_paths(value: Any, path: str = "$") -> list[str]:
    matches: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in UNSUPPORTED_STRUCTURED_OUTPUT_KEYWORDS:
                matches.append(child_path)
            matches.extend(_unsupported_schema_keyword_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            matches.extend(_unsupported_schema_keyword_paths(child, f"{path}[{index}]"))
    return matches


def _load_schema(repo_root: Path, relative_path: Path) -> dict[str, Any]:
    value = json.loads((repo_root / relative_path).read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("additionalProperties") is not False:
        raise HarnessError(f"output schema is not closed: {relative_path.as_posix()}")
    unsupported = _unsupported_schema_keyword_paths(value)
    if unsupported:
        keyword = unsupported[0].rsplit(".", 1)[-1]
        raise HarnessError(
            f"output schema uses unsupported structured-output keyword {keyword}: "
            f"{unsupported[0]}"
        )
    return value


def install_output_schema(repo_root: Path = DEFAULT_REPO_ROOT) -> dict[str, Any]:
    return _load_schema(repo_root, INSTALL_SCHEMA_PATH)


def validate_install_output(value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["structured output is not an object"]
    keys = set(value)
    if keys != INSTALL_OUTPUT_KEYS:
        errors.append(f"unexpected keys: expected {sorted(INSTALL_OUTPUT_KEYS)}, got {sorted(keys)}")
    expected = {
        "scenario_id": "install-smoke-image-unavailable",
        "skill_invoked": True,
        "status": "blocked",
        "capability_gap": "image_generation_unavailable",
        "artifact_invented": False,
        "files_written": False,
    }
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            errors.append(f"{key} did not match the closed install-smoke contract")
    if not isinstance(value.get("explanation"), str) or not value.get("explanation", "").strip():
        errors.append("explanation must be a non-empty string")
    return errors


def _install_outcome(
    *,
    final: dict[str, Any],
    discovery_verified: bool,
    project_mutated: bool,
    command_receipt: dict[str, Any],
) -> dict[str, Any]:
    reference_present_and_hashed = any(
        read.get("path", "").endswith("references/contracts.md")
        and re.fullmatch(r"[0-9a-f]{64}", str(read.get("target_sha256", "")))
        for read in command_receipt.get("required_reads", [])
    )
    return {
        "skill_discovered_and_enabled": discovery_verified,
        "structured_skill_invocation_reported": final.get("skill_invoked") is True,
        "reference_file_present_and_hashed": reference_present_and_hashed,
        "agent_file_reads_observed": command_receipt.get("required_reads_succeeded") is True,
        "capability_gap_reported": final.get("capability_gap"),
        "status": final.get("status"),
        "artifact_invented": final.get("artifact_invented"),
        "files_written": project_mutated
        or command_receipt.get("write_like_command_detected") is True
        or final.get("files_written") is not False,
    }


PROBE_OUTPUT_KEYS = {
    "scenario_id",
    "skill_invoked",
    "observed_start_stage",
    "requested_scope_end_stage",
    "current_stage_status",
    "active_stage_outputs",
    "ecommerce_roles",
    "claims_made",
    "publication_authorized",
    "image_generation_invoked",
    "artifacts_invented",
    "files_written",
    "capability_limits",
}


def probe_output_schema(
    scenario: dict[str, Any], repo_root: Path = DEFAULT_REPO_ROOT
) -> dict[str, Any]:
    if scenario.get("id") not in PROBE_REFERENCES:
        raise HarnessError("probe scenario is not part of the audited scenario set")
    return json.loads(json.dumps(_load_schema(repo_root, PROBE_SCHEMA_PATH)))


def validate_probe_output(value: Any, scenario: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["structured output is not an object"]
    keys = set(value)
    if keys != PROBE_OUTPUT_KEYS:
        errors.append(f"unexpected keys: expected {sorted(PROBE_OUTPUT_KEYS)}, got {sorted(keys)}")
    exact = {
        "scenario_id": scenario["id"],
        "skill_invoked": True,
        "observed_start_stage": scenario["expected_start_stage"],
        "requested_scope_end_stage": scenario["expected_scope_end_stage"],
        "active_stage_outputs": scenario["active_stage_outputs"],
        "ecommerce_roles": scenario["ecommerce_roles"],
        "claims_made": [],
        "publication_authorized": False,
        "image_generation_invoked": False,
        "artifacts_invented": False,
        "files_written": False,
    }
    for key, expected in exact.items():
        if value.get(key) != expected:
            errors.append(f"{key} did not match scenario {scenario['id']}")
    if value.get("current_stage_status") not in {"draft", "blocked"}:
        errors.append("current_stage_status must be draft or blocked")
    limits = value.get("capability_limits")
    if not isinstance(limits, list) or not limits or not all(
        isinstance(item, str) and item.strip() for item in limits
    ):
        errors.append("capability_limits must contain at least one non-empty string")
    elif len(limits) != len(set(limits)):
        errors.append("capability_limits must contain unique strings")
    return errors


def _standalone_plan_rows() -> list[dict[str, Any]]:
    rows = []
    for layout in STANDALONE_LAYOUTS:
        rows.append(
            {
                "id": layout["id"],
                "distribution": "standalone",
                "status": "planned",
                "install_relative_path": layout["install_relative_path"],
                "home": "isolated per session",
                "codex_home": layout["codex_home"],
                "cwd": layout["cwd"],
                "ignore_user_config": True,
                "runtime_discovery": "app-server skills/list with forceReload=true",
                "relative_reference_check": "candidate hash under the discovered Skill root",
            }
        )
    rows.append(
        {
            "id": "local-marketplace-plugin",
            "distribution": "skills-only-plugin",
            "status": "planned",
            "install_relative_path": "<plugin-cache>/skills/packaging-product-visuals",
            "home": "isolated per session",
            "codex_home": "explicit",
            "cwd": "isolated empty project outside marketplace and cache",
            "ignore_user_config": False,
            "runtime_discovery": "app-server skills/list with forceReload=true",
            "relative_reference_check": "candidate hash under the discovered Skill root",
            "plugin_checks": [
                "local marketplace add JSON receipt",
                "plugin add JSON receipt",
                "plugin list JSON receipt",
                "unique manifest-based cache discovery, exact inventory, and pre/post hash",
            ],
        }
    )
    return rows


def build_dry_run_plan(
    candidate: dict[str, Any],
    scenarios: list[dict[str, Any]],
    plugin_version: str,
    model: str = MODEL,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "execution_mode": "dry-run",
        "candidate": candidate,
        "requested_runtime": {
            "client": "codex-cli",
            "model": model,
            "reasoning_effort": REASONING_EFFORT,
            "sandbox": "read-only",
            "ephemeral": True,
        },
        "privacy_boundary": {
            "raw_root": "<private-audit-root>",
            "raw_events_public": False,
            "credentials_public": False,
            "absolute_path_mappings_public": False,
            "credential_copies_removed_after_each_session": True,
        },
        "install_smoke": {
            "count": 5,
            "plugin_version_from_manifest": plugin_version,
            "sessions": _standalone_plan_rows(),
        },
        "behavior_probes": {
            "count": len(scenarios),
            "sessions": [
                {
                    "id": scenario["id"],
                    "status": "planned",
                    "expected_start_stage": scenario["expected_start_stage"],
                    "expected_scope_end_stage": scenario["expected_scope_end_stage"],
                    "active_stage_outputs": scenario["active_stage_outputs"],
                    "ecommerce_roles": scenario["ecommerce_roles"],
                    "required_reads": list(PROBE_REFERENCES[scenario["id"]]),
                    "closed_output_schema": True,
                }
                for scenario in scenarios
            ],
        },
        "dry_run_guarantees": {
            "codex_exec_invoked": False,
            "plugin_commands_invoked": False,
            "image_tools_invoked": False,
            "runtime_result_fields_emitted": False,
        },
        "execution_requirements": {
            "execute_flag": "--execute",
            "candidate_confirmation": "--confirm-tree-sha256 <observed candidate digest>",
            "session_limit": "--max-agent-sessions 5, 3, or 8 for the selected suite",
            "audit_root": "existing writable ancestor outside the public worktree",
            "auth_source": "explicit nonempty private JSON file",
        },
    }


def require_execution_authorized(
    *,
    execute: bool,
    dry_run: bool,
    confirmed_digest: str | None,
    candidate: dict[str, Any],
    max_agent_sessions: int | None = None,
    required_agent_sessions: int | None = None,
) -> bool:
    if not execute:
        return False
    if dry_run:
        raise HarnessError("--execute and --dry-run are mutually exclusive")
    if confirmed_digest != candidate["tree_sha256"]:
        raise HarnessError("--confirm-tree-sha256 must equal the observed candidate digest")
    if required_agent_sessions is not None and max_agent_sessions != required_agent_sessions:
        raise HarnessError(
            f"--max-agent-sessions must be exactly {required_agent_sessions} for this suite"
        )
    return True


def render_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Task 6 Harness Dry Run",
        "",
        "Prepared as a non-executing plan. No Codex session, plugin mutation, or image call ran.",
        "",
        "## Candidate",
        "",
        f"- Files: {plan['candidate']['file_count']}",
        f"- Tree SHA-256: `{plan['candidate']['tree_sha256']}`",
        "",
        "## Install Smoke",
        "",
        "| Session | Distribution | State |",
        "| --- | --- | --- |",
    ]
    for session in plan["install_smoke"]["sessions"]:
        lines.append(f"| `{session['id']}` | {session['distribution']} | planned |")
    lines.extend(
        [
            "",
            "## Fresh-Agent Probes",
            "",
            "| Scenario | Expected start | State |",
            "| --- | --- | --- |",
        ]
    )
    for probe in plan["behavior_probes"]["sessions"]:
        lines.append(f"| `{probe['id']}` | `{probe['expected_start_stage']}` | planned |")
    lines.extend(
        [
            "",
            "Observed runtime fields are intentionally absent. They are generated only from real commands.",
            "",
        ]
    )
    return "\n".join(lines)


def _preflight(
    repo_root: Path,
    audit_root: Path,
    auth_source: Path,
    codex_bin: str,
) -> dict[str, Any]:
    _require_private_runtime_support()
    repo = _resolved(repo_root)
    if not (repo / ".git").exists():
        git_probe = _run_capture(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo)
        if git_probe.returncode != 0 or git_probe.stdout.strip() != b"true":
            raise HarnessError("repo root is not a Git worktree")
    audit = require_private_audit_root(repo, audit_root)
    nearest = audit
    while not nearest.exists() and nearest != nearest.parent:
        nearest = nearest.parent
    if not nearest.exists() or not os.access(nearest, os.W_OK):
        raise HarnessError("private audit root has no writable existing ancestor")
    executable = _resolve_codex_executable(codex_bin)
    auth, _ = _validated_auth_source(repo, auth_source)
    candidate = discover_candidate(repo)
    scenarios = load_scenarios(repo)
    plugin_version = load_plugin_version(repo)
    public_harness_files = [
        Path(__file__).resolve(),
        repo / INSTALL_SCHEMA_PATH,
        repo / PROBE_SCHEMA_PATH,
    ]
    for public_file in public_harness_files:
        if not public_file.is_file():
            raise HarnessError(f"public harness file is missing: {public_file.name}")
        ignored = _run_capture(
            ["git", "check-ignore", "-q", str(public_file.relative_to(repo))],
            cwd=repo,
        )
        if ignored.returncode == 0:
            raise HarnessError(f"public harness file is ignored: {public_file.name}")
    install_schema = install_output_schema(repo)
    probe_schema = _load_schema(repo, PROBE_SCHEMA_PATH)
    if set(install_schema.get("required", [])) != INSTALL_OUTPUT_KEYS:
        raise HarnessError("install output schema required keys drifted")
    if set(probe_schema.get("required", [])) != PROBE_OUTPUT_KEYS:
        raise HarnessError("full-workflow output schema required keys drifted")
    observed_clock = capture_local_execution_clock()
    return {
        "schema_version": 1,
        "observed_on": observed_clock["executed_on"],
        "mode": "preflight",
        "result": "passed",
        "checks": {
            "repo_is_git_worktree": True,
            "private_audit_root_outside_worktree": True,
            "private_audit_parent_writable": True,
            "codex_executable_available": True,
            "auth_source_present_nonempty_and_private": True,
            "auth_source_json_has_scannable_secret_values": True,
            "public_harness_files_not_ignored": True,
            "candidate_inventory_read_from_git": True,
            "scenario_contracts_loaded": len(scenarios) == 3,
            "plugin_manifest_loaded": True,
        },
        "candidate": candidate,
        "scenario_ids": [scenario["id"] for scenario in scenarios],
        "plugin_version_from_manifest": plugin_version,
        "harness_files": harness_artifact_receipts(repo),
        "client_version": _parse_codex_version(
            _command_version([executable, "--version"], repo)
        ),
        "privacy": {
            "audit_root": "<private-audit-root>",
            "auth_source": "<auth-source>",
        },
    }


def _copy_candidate(repo_root: Path, candidate: dict[str, Any], target: Path) -> None:
    require_candidate_unchanged(repo_root, candidate)
    source_root = repo_root / "skills" / SKILL_NAME
    target.mkdir(parents=True, exist_ok=False)
    for relative_name in candidate["files"]:
        relative = Path(relative_name)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_root / relative, destination)
    installed = tree_snapshot(target)
    if (
        installed["files"] != candidate["files"]
        or installed["file_count"] != candidate["file_count"]
        or installed["tree_sha256"] != candidate["tree_sha256"]
    ):
        raise HarnessError("copied Skill tree did not match the confirmed candidate")
    for relative_name, expected_hash in candidate["file_sha256"].items():
        if file_sha256(target / relative_name) != expected_hash:
            raise HarnessError("copied Skill file did not match the confirmed candidate")
    require_candidate_unchanged(repo_root, candidate)


def _copy_auth(auth_source: Path, codex_home: Path) -> Path:
    _require_private_runtime_support()
    codex_home.mkdir(parents=True, exist_ok=True)
    destination = codex_home / AUTH_BASENAME
    shutil.copyfile(auth_source, destination)
    destination.chmod(0o600)
    return destination


def _credential_secret_values(auth_source: Path) -> tuple[bytes, ...]:
    try:
        value = json.loads(auth_source.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HarnessError("Codex auth source is not valid UTF-8 JSON") from error
    strings: set[bytes] = set()

    def collect(child: Any) -> None:
        if isinstance(child, dict):
            for nested in child.values():
                collect(nested)
        elif isinstance(child, list):
            for nested in child:
                collect(nested)
        elif isinstance(child, str) and len(child) >= 12:
            strings.add(child.encode("utf-8"))

    collect(value)
    if not strings:
        raise HarnessError("Codex auth source contains no scannable credential values")
    return tuple(sorted(strings, key=len, reverse=True))


def _validated_auth_source(
    repo_root: Path,
    auth_source: Path,
) -> tuple[Path, tuple[bytes, ...]]:
    _require_private_runtime_support()
    repo = _resolved(repo_root)
    auth = _resolved(auth_source)
    if not auth.is_file() or auth.stat().st_size == 0:
        raise HarnessError("Codex auth source is missing or empty")
    if auth == repo or _is_relative_to(auth, repo):
        raise HarnessError("Codex auth source must be outside the public worktree")
    if stat.S_IMODE(auth.stat().st_mode) & 0o077:
        raise HarnessError("Codex auth source must not be group/world accessible")
    return auth, _credential_secret_values(auth)


def _contains_secret_material(blobs: list[bytes], secrets: tuple[bytes, ...]) -> bool:
    return any(secret in blob for secret in secrets for blob in blobs)


def _secret_leak_files(root: Path, secrets: tuple[bytes, ...]) -> list[str]:
    leaks: list[str] = []
    for relative_path in _regular_files(root):
        path = root / relative_path
        if _contains_secret_material([path.read_bytes()], secrets):
            leaks.append(relative_path.as_posix())
    return leaks


def _remove_auth_copies(run_root: Path) -> bool:
    for auth_path in run_root.rglob(AUTH_BASENAME):
        if auth_path.is_file() or auth_path.is_symlink():
            auth_path.unlink()
    return not any(path.is_file() for path in run_root.rglob(AUTH_BASENAME))


def _private_artifact_receipts(session_root: Path) -> dict[str, str]:
    receipts: dict[str, str] = {}
    for path in _regular_files(session_root):
        if path.name in {AUTH_BASENAME, "private-receipt.json"}:
            continue
        receipts[path.as_posix()] = file_sha256(session_root / path)
    return receipts


def _isolated_env(home: Path, codex_home: Path | None) -> dict[str, str]:
    allowed = {
        "PATH",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TERM",
        "TMPDIR",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "no_proxy",
    }
    env = {key: value for key, value in os.environ.items() if key in allowed}
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(home / ".config")
    env["XDG_CACHE_HOME"] = str(home / ".cache")
    env["XDG_DATA_HOME"] = str(home / ".local" / "share")
    isolated_tmp = home / "tmp"
    isolated_tmp.mkdir(parents=True, exist_ok=True)
    env["TMPDIR"] = str(isolated_tmp)
    if codex_home is not None:
        env["CODEX_HOME"] = str(codex_home)
    return env


def _install_prompt(skill_root: Path) -> str:
    _ = skill_root
    return f"""Use ${SKILL_NAME} for this isolated read-only install smoke.

Do not run shell commands or invoke any tool. Respond to this request: create one
rendered packaging concept image. Image
generation and editing are intentionally unavailable in this runtime. Do not invoke
an image tool, do not write any file, and do not claim an artifact exists. Return
only the JSON object required by the supplied output schema.
"""


def _probe_prompt(scenario: dict[str, Any], skill_root: Path) -> str:
    _ = skill_root
    reads = "\n".join(
        "- "
        + f'sed -n 1,220p "$PPV_SKILL_ROOT/{relative}"'
        for relative in PROBE_REFERENCES[scenario["id"]]
    )
    return f"""Use ${SKILL_NAME} for this isolated read-only behavior probe.

Run every exact read-only shell command below separately before answering. Do not
add wrappers, pipes, comments, redirections, substitutions, or extra commands:
{reads}

Scenario request:
{scenario['request']}

Evaluate routing and contract behavior only. Do not create files, contracts, images,
or publication claims. Do not invoke image generation. Derive the start stage,
requested scope end stage, ecommerce roles, current status, and limitations from the
installed Skill and the scenario. For active_stage_outputs, include only the outputs
named in the router row for the observed start stage; do not include upstream
prerequisites or downstream stages. For requested_scope_end_stage, return the furthest
stage explicitly requested by the scenario. Return only the JSON object required by
the supplied output schema.
"""


def _codex_argv(
    codex_bin: str,
    cwd: Path,
    schema_path: Path,
    last_message_path: Path,
    model: str,
    ignore_user_config: bool,
) -> list[str]:
    argv = [
        codex_bin,
        "exec",
        "--json",
        "--ephemeral",
        "--ignore-rules",
        "--skip-git-repo-check",
        "-C",
        str(cwd),
        "-m",
        model,
        "-c",
        f'model_reasoning_effort="{REASONING_EFFORT}"',
        "-c",
        AUTH_STORE_CONFIG,
        "-s",
        "read-only",
        "--output-schema",
        str(schema_path),
        "-o",
        str(last_message_path),
        "-",
    ]
    if ignore_user_config:
        argv.insert(3, "--ignore-user-config")
    return argv


def _parse_last_message(path: Path) -> Any:
    if not path.is_file():
        raise HarnessError("Codex did not write the structured last message")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise HarnessError("Codex last message is not valid JSON") from error


def _run_codex(
    *,
    codex_bin: str,
    model: str,
    session_root: Path,
    cwd: Path,
    env: dict[str, str],
    prompt: str,
    schema: dict[str, Any],
    ignore_user_config: bool,
    timeout: int,
    path_mappings: dict[str, str],
    secret_values: tuple[bytes, ...],
) -> dict[str, Any]:
    schema_path = session_root / "output-schema.json"
    prompt_path = session_root / "prompt.txt"
    final_path = session_root / "last-message.json"
    raw_events_path = session_root / "events.raw.jsonl"
    sanitized_events_path = session_root / "events.sanitized.jsonl"
    stderr_path = session_root / "stderr.raw.txt"
    write_json(schema_path, schema, private=True)
    write_text(prompt_path, prompt, private=True)
    argv = _codex_argv(
        codex_bin,
        cwd,
        schema_path,
        final_path,
        model,
        ignore_user_config,
    )
    process = _run_capture(
        argv,
        cwd=cwd,
        env=env,
        input_bytes=prompt.encode("utf-8"),
        timeout=timeout,
    )
    _write_bytes(raw_events_path, process.stdout, private=True)
    _write_bytes(stderr_path, process.stderr, private=True)
    sanitized = sanitize_jsonl_bytes(process.stdout, path_mappings)
    _write_bytes(sanitized_events_path, sanitized, private=True)
    events = parse_jsonl(process.stdout) if process.stdout else []
    final = _parse_last_message(final_path) if final_path.is_file() else None
    final_bytes = final_path.read_bytes() if final_path.is_file() else b""
    last_event_message = _last_agent_message(events) if events else None
    return {
        "argv": argv,
        "exit_code": process.returncode,
        "raw_event_stream_sha256": sha256_bytes(process.stdout),
        "sanitized_event_stream_sha256": sha256_bytes(sanitized),
        "stderr_sha256": sha256_bytes(process.stderr),
        "events": events,
        "event_lifecycle": audit_event_lifecycle(events) if events else None,
        "final": final,
        "final_message_matches_event": final is not None and last_event_message == final,
        "credential_material_detected": _contains_secret_material(
            [process.stdout, process.stderr, final_bytes], secret_values
        ),
    }


def _layout_paths(session_root: Path, layout_id: str) -> dict[str, Path | None]:
    home = session_root / "home"
    project = session_root / "project"
    home.mkdir(parents=True)
    project.mkdir(parents=True)
    if layout_id == "explicit-codex-home-skills":
        codex_home = session_root / "codex-home"
        install = codex_home / "skills" / SKILL_NAME
        env_codex_home: Path | None = codex_home
    elif layout_id == "default-codex-home-skills":
        codex_home = home / ".codex"
        install = codex_home / "skills" / SKILL_NAME
        env_codex_home = None
    elif layout_id == "user-agents-skills":
        codex_home = home / ".codex"
        install = home / ".agents" / "skills" / SKILL_NAME
        env_codex_home = None
    elif layout_id == "project-agents-skills":
        codex_home = home / ".codex"
        install = project / ".agents" / "skills" / SKILL_NAME
        env_codex_home = None
    else:
        raise HarnessError(f"unknown standalone layout: {layout_id}")
    return {
        "home": home,
        "project": project,
        "codex_home": codex_home,
        "env_codex_home": env_codex_home,
        "install": install,
    }


def _sanitized_command_receipt(
    command_receipt: dict[str, Any], mappings: dict[str, str]
) -> dict[str, Any]:
    normalized = json.loads(json.dumps(command_receipt))
    for command in normalized.get("commands", []):
        if isinstance(command, dict) and isinstance(command.get("command"), str):
            command["command"] = _public_command_text(command["command"])
    return _sanitize_value(normalized, mappings)


def _standalone_session_impl(
    *,
    repo_root: Path,
    run_root: Path,
    layout: dict[str, str],
    candidate: dict[str, Any],
    auth_source: Path,
    codex_bin: str,
    model: str,
    timeout: int,
) -> tuple[dict[str, Any], list[str]]:
    session_root = run_root / layout["id"]
    session_root.mkdir(parents=True, mode=0o700)
    paths = _layout_paths(session_root, layout["id"])
    home = paths["home"]
    project = paths["project"]
    codex_home = paths["codex_home"]
    install = paths["install"]
    assert isinstance(home, Path)
    assert isinstance(project, Path)
    assert isinstance(codex_home, Path)
    assert isinstance(install, Path)
    _copy_candidate(repo_root, candidate, install)
    _copy_auth(auth_source, codex_home)
    secret_values = _credential_secret_values(auth_source)
    before_install = tree_snapshot(install)
    before_project = tree_snapshot(project)
    mappings = {
        str(install): layout["install_relative_path"],
        str(codex_home): "$CODEX_HOME" if paths["env_codex_home"] else "$HOME/.codex",
        str(home): "$HOME",
        str(project): "<project>",
        str(session_root): "<private-session-root>",
        str(run_root): "<private-run-root>",
        str(repo_root): "<repo>",
        str(auth_source): "<auth-source>",
    }
    env = _isolated_env(home, paths["env_codex_home"])
    env["PPV_SKILL_ROOT"] = str(install)
    errors: list[str] = []
    discovery_verified, skill_discovery_receipt, discovery_errors = (
        _run_skill_discovery_protocol(
            session_root=session_root,
            project=project,
            install=install,
            candidate=candidate,
            codex_bin=codex_bin,
            env=env,
            timeout=timeout,
            secret_values=secret_values,
        )
    )
    errors.extend(discovery_errors)
    try:
        execution = _run_codex(
            codex_bin=codex_bin,
            model=model,
            session_root=session_root,
            cwd=project,
            env=env,
            prompt=_install_prompt(install),
            schema=install_output_schema(repo_root),
            ignore_user_config=True,
            timeout=timeout,
            path_mappings=mappings,
            secret_values=secret_values,
        )
    finally:
        credential_removed = _remove_auth_copies(session_root)
    runtime_temp_symlink_cleanup = _remove_codex_runtime_temp_symlinks(
        session_root,
        codex_bin,
    )
    secret_leak_files = _secret_leak_files(session_root, secret_values)
    after_install = tree_snapshot(install)
    after_project = tree_snapshot(project)
    if execution["exit_code"] != 0:
        errors.append(f"codex exec exited {execution['exit_code']}")
    required_paths = [install / "SKILL.md", install / "references/contracts.md"]
    if not execution["events"]:
        errors.append("event stream was empty or unavailable")
    command_receipt = audit_command_events(
        execution["events"] if execution["events"] else [],
        required_paths,
        require_content_markers=True,
    )
    if (
        command_receipt["unexpected_command_count"]
        or command_receipt["duplicate_required_read_count"]
        or command_receipt["nonzero_command_exit_count"]
        or command_receipt["write_like_command_detected"]
    ):
        errors.append("agent session ran a failed, unexpected, duplicated, or write-like command")
    lifecycle = execution.get("event_lifecycle")
    if not lifecycle or not lifecycle["lifecycle_complete"]:
        errors.append("event stream lifecycle was incomplete")
    elif (
        lifecycle["failed_event_count"]
        or lifecycle["incomplete_item_count"]
        or lifecycle["disallowed_item_types"]
    ):
        errors.append("event stream contained failed or disallowed events")
    if not execution.get("final_message_matches_event"):
        errors.append("last agent_message did not match --output-last-message")
    if execution.get("credential_material_detected"):
        errors.append("credential material appeared in Codex output")
    if secret_leak_files:
        errors.append("credential material appeared in private session artifacts")
    if execution["final"] is None:
        errors.append("structured final output was unavailable")
        final_errors = []
        final: dict[str, Any] = {}
    else:
        final = execution["final"]
        final_errors = validate_install_output(final)
        errors.extend(final_errors)
    install_mutated = before_install != after_install
    project_mutated = before_project != after_project
    if install_mutated:
        errors.append("installed Skill tree mutated")
    if project_mutated:
        errors.append("isolated project tree mutated")
    if not credential_removed:
        errors.append("credential copy was not removed")
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
        "exit_code": execution["exit_code"],
        "event_stream_sha256": execution["sanitized_event_stream_sha256"],
        "structured_response_sha256": sha256_bytes(
            json.dumps(_sanitize_value(final, mappings), sort_keys=True).encode("utf-8")
        ),
        "command_evidence": _sanitized_command_receipt(command_receipt, mappings),
        "event_evidence": lifecycle,
        "outcome": _install_outcome(
            final=final,
            discovery_verified=discovery_verified,
            project_mutated=project_mutated,
            command_receipt=command_receipt,
        ),
        "install_tree_sha256_before": before_install["tree_sha256"],
        "install_tree_sha256_after": after_install["tree_sha256"],
        "workspace_tree_sha256_before": before_project["tree_sha256"],
        "workspace_tree_sha256_after": after_project["tree_sha256"],
        "credential_copy_mode": "0600",
        "credential_store": "file",
        "credential_copy_removed": credential_removed,
        "credential_leak_detected": execution.get("credential_material_detected", False)
        or bool(secret_leak_files),
        "evidence_errors": errors,
    }
    write_json(
        session_root / "private-receipt.json",
        {
            "codex_argv": execution["argv"],
            "raw_event_stream_sha256": execution["raw_event_stream_sha256"],
            "sanitized_event_stream_sha256": execution["sanitized_event_stream_sha256"],
            "stderr_sha256": execution["stderr_sha256"],
            "auth_copy_removed": credential_removed,
            "runtime_temp_symlink_cleanup": runtime_temp_symlink_cleanup,
            "skill_discovery": skill_discovery_receipt,
            "secret_leak_files": secret_leak_files,
            "absolute_path_mappings": mappings,
            "private_artifacts": _private_artifact_receipts(session_root),
            "summary": result,
        },
        private=True,
    )
    return result, errors


def _standalone_session(
    *,
    repo_root: Path,
    run_root: Path,
    layout: dict[str, str],
    candidate: dict[str, Any],
    auth_source: Path,
    codex_bin: str,
    model: str,
    timeout: int,
) -> tuple[dict[str, Any], list[str]]:
    session_root = run_root / layout["id"]
    try:
        return _standalone_session_impl(
            repo_root=repo_root,
            run_root=run_root,
            layout=layout,
            candidate=candidate,
            auth_source=auth_source,
            codex_bin=codex_bin,
            model=model,
            timeout=timeout,
        )
    finally:
        if session_root.exists():
            _remove_auth_copies(session_root)


def _run_private_cli_command(
    argv: list[str],
    *,
    label: str,
    session_root: Path,
    cwd: Path,
    env: dict[str, str],
    timeout: int,
    secret_values: tuple[bytes, ...],
) -> tuple[subprocess.CompletedProcess[bytes], Any | None, dict[str, Any]]:
    process = _run_capture(argv, cwd=cwd, env=env, timeout=timeout)
    stdout_path = session_root / f"{label}.stdout.raw.json"
    stderr_path = session_root / f"{label}.stderr.raw.txt"
    _write_bytes(stdout_path, process.stdout, private=True)
    _write_bytes(stderr_path, process.stderr, private=True)
    value: Any | None = None
    if process.stdout:
        try:
            value = json.loads(process.stdout)
        except json.JSONDecodeError:
            value = None
    receipt = {
        "argv": argv,
        "exit_code": process.returncode,
        "stdout_sha256": sha256_bytes(process.stdout),
        "stderr_sha256": sha256_bytes(process.stderr),
        "json_output": value is not None,
        "credential_leak_detected": _contains_secret_material(
            [process.stdout, process.stderr], secret_values
        ),
    }
    return process, value, receipt


def _plugin_command_argv(
    codex_bin: str,
    marketplace: Path,
    plugin_id: str,
) -> dict[str, list[str]]:
    return {
        "marketplace-add": [
            codex_bin,
            "plugin",
            "marketplace",
            "add",
            "-c",
            AUTH_STORE_CONFIG,
            "--json",
            str(marketplace),
        ],
        "plugin-add": [
            codex_bin,
            "plugin",
            "add",
            "-c",
            AUTH_STORE_CONFIG,
            "--json",
            plugin_id,
        ],
        "plugin-list": [
            codex_bin,
            "plugin",
            "list",
            "-c",
            AUTH_STORE_CONFIG,
            "--json",
        ],
    }


def _plugin_entry(plugin_list: Any, expected_id: str) -> dict[str, Any] | None:
    if not isinstance(plugin_list, dict):
        return None
    installed = plugin_list.get("installed")
    if not isinstance(installed, list):
        return None
    for entry in installed:
        if isinstance(entry, dict) and entry.get("pluginId") == expected_id:
            return entry
    return None


def _find_plugin_cache_root(codex_home: Path, version: str) -> Path:
    cache_root = codex_home / "plugins" / "cache"
    matches: list[Path] = []
    if cache_root.is_dir():
        for manifest_path in cache_root.rglob(".codex-plugin/plugin.json"):
            if manifest_path.is_symlink():
                raise HarnessError("plugin cache manifest must not be a symlink")
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as error:
                raise HarnessError("plugin cache contains an invalid manifest") from error
            if manifest.get("name") == SKILL_NAME and manifest.get("version") == version:
                matches.append(manifest_path.parent.parent)
    if len(matches) != 1:
        raise HarnessError(
            "plugin cache must contain exactly one manifest matching the plugin name/version"
        )
    return matches[0]


def _plugin_cache_audit(
    cache_root: Path,
    candidate: dict[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    skill_root = cache_root / "skills" / SKILL_NAME
    skill_snapshot = tree_snapshot(skill_root)
    if (
        skill_snapshot["files"] != candidate["files"]
        or skill_snapshot["file_count"] != candidate["file_count"]
        or skill_snapshot["tree_sha256"] != candidate["tree_sha256"]
    ):
        raise HarnessError("installed plugin Skill tree did not match the confirmed candidate")
    manifest_path = cache_root / ".codex-plugin" / "plugin.json"
    license_path = cache_root / "LICENSE"
    if not manifest_path.is_file() or file_sha256(manifest_path) != file_sha256(
        repo_root / ".codex-plugin" / "plugin.json"
    ):
        raise HarnessError("installed plugin manifest did not match the release candidate")
    if not license_path.is_file() or file_sha256(license_path) != file_sha256(
        repo_root / "LICENSE"
    ):
        raise HarnessError("installed plugin license did not match the release candidate")
    installed_names = [path.as_posix() for path in _regular_files(cache_root)]
    expected_names = sorted(
        [".codex-plugin/plugin.json", "LICENSE"]
        + [f"skills/{SKILL_NAME}/{name}" for name in candidate["files"]]
    )
    unexpected = sorted(set(installed_names) - set(expected_names))
    missing = sorted(set(expected_names) - set(installed_names))
    audit = {
        "cache_root_basis": "unique isolated cache manifest matching plugin name and version",
        "installed_file_count": len(installed_names),
        "installed_skill_file_count": len(
            [name for name in installed_names if name.startswith(f"skills/{SKILL_NAME}/")]
        ),
        "pyc_file_count": len(
            [name for name in installed_names if name.endswith(".pyc") or "__pycache__" in name]
        ),
        "unexpected_files": unexpected,
        "missing_files": missing,
        "installed_files": installed_names,
    }
    if unexpected or missing or audit["pyc_file_count"]:
        raise HarnessError("plugin cache inventory was not the exact skills-only distribution")
    return audit


def _create_marketplace(
    repo_root: Path,
    marketplace_root: Path,
    candidate: dict[str, Any],
) -> Path:
    plugin_root = marketplace_root / "plugins" / SKILL_NAME
    (plugin_root / ".codex-plugin").mkdir(parents=True)
    shutil.copy2(repo_root / ".codex-plugin" / "plugin.json", plugin_root / ".codex-plugin")
    shutil.copy2(repo_root / "LICENSE", plugin_root / "LICENSE")
    _copy_candidate(repo_root, candidate, plugin_root / "skills" / SKILL_NAME)
    manifest = {
        "name": MARKETPLACE_NAME,
        "interface": {"displayName": "Packaging Product Visuals Install Smoke"},
        "plugins": [
            {
                "name": SKILL_NAME,
                "source": {
                    "source": "local",
                    "path": f"./plugins/{SKILL_NAME}",
                },
                "policy": {
                    "installation": "AVAILABLE",
                    "authentication": "ON_INSTALL",
                },
                "category": "Design",
            }
        ],
    }
    write_json(marketplace_root / ".agents" / "plugins" / "marketplace.json", manifest, private=True)
    return plugin_root


def _plugin_session_impl(
    *,
    repo_root: Path,
    run_root: Path,
    candidate: dict[str, Any],
    plugin_version: str,
    auth_source: Path,
    codex_bin: str,
    model: str,
    timeout: int,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    session_root = run_root / "local-marketplace-plugin"
    session_root.mkdir(parents=True, mode=0o700)
    home = session_root / "home"
    codex_home = session_root / "codex-home"
    project = session_root / "project"
    marketplace = session_root / "marketplace"
    home.mkdir()
    project.mkdir()
    _create_marketplace(repo_root, marketplace, candidate)
    _copy_auth(auth_source, codex_home)
    secret_values = _credential_secret_values(auth_source)
    env = _isolated_env(home, codex_home)
    mappings = {
        str(session_root): "<private-session-root>",
        str(run_root): "<private-run-root>",
        str(repo_root): "<repo>",
        str(auth_source): "<auth-source>",
        str(codex_bin): "<codex-bin>",
        str(home): "$HOME",
        str(codex_home): "$CODEX_HOME",
        str(project): "<project>",
        str(marketplace): "<private-marketplace>",
    }
    command_receipts: dict[str, Any] = {}
    plugin_command_argv: dict[str, list[str]] = {}
    errors: list[str] = []
    plugin_id = f"{SKILL_NAME}@{MARKETPLACE_NAME}"
    commands = _plugin_command_argv(codex_bin, marketplace, plugin_id)
    before_project = tree_snapshot(project)
    plugin_list: Any | None = None
    plugin_source_private = False
    for label, argv in commands.items():
        process, value, receipt = _run_private_cli_command(
            argv,
            label=label,
            session_root=session_root,
            cwd=project,
            env=env,
            timeout=timeout,
            secret_values=secret_values,
        )
        plugin_command_argv[label] = list(argv)
        command_receipts[label] = _sanitize_value(receipt, mappings)
        if receipt["credential_leak_detected"]:
            errors.append(f"credential material appeared in {label} output")
            break
        if process.returncode != 0:
            errors.append(f"{label} exited {process.returncode}")
            break
        if value is None:
            errors.append(f"{label} did not return JSON")
            break
        if label == "plugin-list":
            plugin_list = value
    cache_root: Path | None = None
    before_install = {"file_count": 0, "files": [], "tree_sha256": sha256_bytes(b"")}
    execution: dict[str, Any] = {
        "argv": [],
        "exit_code": -1,
        "raw_event_stream_sha256": sha256_bytes(b""),
        "sanitized_event_stream_sha256": sha256_bytes(b""),
        "stderr_sha256": sha256_bytes(b""),
        "events": [],
        "event_lifecycle": None,
        "final": None,
        "final_message_matches_event": False,
        "credential_material_detected": False,
    }
    command_evidence = {
        "completed_command_count": 0,
        "successful_command_count": 0,
        "commands": [],
        "required_reads": [],
        "required_reads_succeeded": False,
        "all_commands_allowed": False,
        "unexpected_command_count": 0,
        "duplicate_required_read_count": 0,
        "nonzero_command_exit_count": 0,
        "write_like_command_detected": False,
    }
    discovery_verified = False
    skill_discovery_receipt = {
        "argv": [codex_bin, "app-server", "--stdio"],
        "request_sha256": sha256_bytes(_skills_list_request_bytes(project)),
        "stdout_sha256": sha256_bytes(b""),
        "stderr_sha256": sha256_bytes(b""),
        "force_reload": True,
        "credential_leak_detected": False,
    }
    if not errors:
        entry = _plugin_entry(plugin_list, plugin_id)
        if entry is None:
            errors.append("plugin list did not contain the expected plugin ID")
        elif entry.get("installed") is not True or entry.get("enabled") is not True:
            errors.append("plugin list did not report installed=true and enabled=true")
        elif entry.get("version") != plugin_version:
            errors.append("plugin list version did not match plugin manifest")
        else:
            source = entry.get("source")
            source_path = source.get("path") if isinstance(source, dict) else None
            if isinstance(source_path, str):
                plugin_source_private = _is_relative_to(_resolved(Path(source_path)), session_root)
            if not plugin_source_private:
                errors.append("plugin list source did not stay inside the private session root")
    if not errors:
        try:
            cache_root = _find_plugin_cache_root(codex_home, plugin_version)
        except HarnessError as error:
            errors.append(str(error))
    if cache_root is not None:
        install = cache_root / "skills" / SKILL_NAME
        mappings[str(cache_root)] = (
            "<plugin-cache>"
        )
        mappings[str(install)] = (
            f"<plugin-cache>/skills/{SKILL_NAME}"
        )
        before_install = tree_snapshot(install)
        try:
            _plugin_cache_audit(cache_root, candidate, repo_root)
        except HarnessError as error:
            errors.append(str(error))
    plugin_runtime_ready = cache_root is not None and not errors
    if plugin_runtime_ready:
        assert cache_root is not None
        install = cache_root / "skills" / SKILL_NAME
        env["PPV_SKILL_ROOT"] = str(install)
        discovery_verified, skill_discovery_receipt, discovery_errors = (
            _run_skill_discovery_protocol(
                session_root=session_root,
                project=project,
                install=install,
                candidate=candidate,
                codex_bin=codex_bin,
                env=env,
                timeout=timeout,
                secret_values=secret_values,
            )
        )
        errors.extend(discovery_errors)
    if plugin_runtime_ready:
        assert cache_root is not None
        install = cache_root / "skills" / SKILL_NAME
        try:
            execution = _run_codex(
                codex_bin=codex_bin,
                model=model,
                session_root=session_root,
                cwd=project,
                env=env,
                prompt=_install_prompt(install),
                schema=install_output_schema(repo_root),
                ignore_user_config=False,
                timeout=timeout,
                path_mappings=mappings,
                secret_values=secret_values,
            )
        finally:
            credential_removed = _remove_auth_copies(session_root)
        command_evidence = audit_command_events(
            execution["events"] if execution["events"] else [],
            [install / "SKILL.md", install / "references/contracts.md"],
            require_content_markers=True,
        )
        if execution["exit_code"] != 0:
            errors.append(f"codex exec exited {execution['exit_code']}")
        if (
            command_evidence["unexpected_command_count"]
            or command_evidence["duplicate_required_read_count"]
            or command_evidence["nonzero_command_exit_count"]
            or command_evidence["write_like_command_detected"]
        ):
            errors.append("agent session ran a failed, unexpected, duplicated, or write-like command")
        lifecycle = execution["event_lifecycle"]
        if not lifecycle or not lifecycle["lifecycle_complete"]:
            errors.append("event stream lifecycle was incomplete")
        elif (
            lifecycle["failed_event_count"]
            or lifecycle["incomplete_item_count"]
            or lifecycle["disallowed_item_types"]
        ):
            errors.append("event stream contained failed or disallowed events")
        if not execution["final_message_matches_event"]:
            errors.append("last agent_message did not match --output-last-message")
        if execution["credential_material_detected"]:
            errors.append("credential material appeared in Codex output")
    else:
        credential_removed = _remove_auth_copies(session_root)
    runtime_temp_symlink_cleanup = _remove_codex_runtime_temp_symlinks(
        session_root,
        codex_bin,
    )
    secret_leak_files = _secret_leak_files(session_root, secret_values)
    after_project = tree_snapshot(project)
    after_install = tree_snapshot(cache_root / "skills" / SKILL_NAME) if cache_root else before_install
    final = execution["final"] if isinstance(execution["final"], dict) else {}
    if cache_root is not None:
        errors.extend(validate_install_output(final))
    if before_install != after_install:
        errors.append("installed plugin Skill tree mutated")
    if before_project != after_project:
        errors.append("isolated project tree mutated")
    if not credential_removed:
        errors.append("credential copy was not removed")
    if secret_leak_files:
        errors.append("credential material appeared in private session artifacts")
    installed_files = _regular_files(cache_root) if cache_root else []
    installed_names = [path.as_posix() for path in installed_files]
    expected_names = sorted(
        [".codex-plugin/plugin.json", "LICENSE"]
        + [f"skills/{SKILL_NAME}/{name}" for name in candidate["files"]]
    )
    unexpected = sorted(set(installed_names) - set(expected_names))
    missing = sorted(set(expected_names) - set(installed_names))
    if unexpected or missing:
        errors.append("plugin cache inventory did not match the skills-only distribution")
    entry = _plugin_entry(plugin_list, plugin_id) or {}
    result = {
        "id": "local-marketplace-plugin",
        "distribution": "skills-only-plugin",
        "environment": {
            "home": "isolated temporary home",
            "codex_home": "explicitly set to the isolated plugin-install Codex home",
            "install_relative_path": (
                f"<plugin-cache>/skills/{SKILL_NAME}"
            ),
            "cwd": "isolated empty project outside the marketplace and install cache",
            "ignore_user_config": False,
            "ignore_user_config_reason": (
                "plugin enablement is the isolated config generated by marketplace and plugin add"
            ),
        },
        "exit_code": execution["exit_code"],
        "event_stream_sha256": execution["sanitized_event_stream_sha256"],
        "discovered_skill_id": f"{SKILL_NAME}:{SKILL_NAME}",
        "command_evidence": _sanitized_command_receipt(command_evidence, mappings),
        "event_evidence": execution["event_lifecycle"],
        "outcome": _install_outcome(
            final=final,
            discovery_verified=discovery_verified,
            project_mutated=before_project != after_project,
            command_receipt=command_evidence,
        ),
        "install_tree_sha256_before": before_install["tree_sha256"],
        "install_tree_sha256_after": after_install["tree_sha256"],
        "workspace_tree_sha256_before": before_project["tree_sha256"],
        "workspace_tree_sha256_after": after_project["tree_sha256"],
        "credential_copy_mode": "0600",
        "credential_store": "file",
        "credential_copy_removed": credential_removed,
        "credential_leak_detected": execution["credential_material_detected"]
        or any(receipt["credential_leak_detected"] for receipt in command_receipts.values())
        or skill_discovery_receipt["credential_leak_detected"]
        or bool(secret_leak_files),
        "evidence_errors": errors,
    }
    installation = {
        "marketplace_name": MARKETPLACE_NAME,
        "marketplace_source": "isolated local filesystem marketplace",
        "distribution": "skills-only plugin",
        "distribution_contents": [
            ".codex-plugin/plugin.json",
            f"skills/{SKILL_NAME}/",
            "LICENSE",
        ],
        "command_receipts": command_receipts,
        "plugin_id": plugin_id,
        "plugin_version": plugin_version,
        "installed": entry.get("installed") is True,
        "enabled": entry.get("enabled") is True,
        "plugin_list_source_inside_private_session": plugin_source_private,
        "remote_catalog_required": False,
        "cache_audit": {
            "cache_root_basis": "unique isolated cache manifest matching plugin name and version",
            "installed_file_count": len(installed_names),
            "installed_skill_file_count": len(
                [name for name in installed_names if name.startswith(f"skills/{SKILL_NAME}/")]
            ),
            "pyc_file_count": len(
                [name for name in installed_names if name.endswith(".pyc") or "__pycache__" in name]
            ),
            "unexpected_files": unexpected,
            "missing_files": missing,
            "installed_files": installed_names,
        },
    }
    write_json(
        session_root / "private-receipt.json",
        {
            "codex_argv": execution["argv"],
            "plugin_command_argv": plugin_command_argv,
            "raw_event_stream_sha256": execution["raw_event_stream_sha256"],
            "sanitized_event_stream_sha256": execution["sanitized_event_stream_sha256"],
            "stderr_sha256": execution["stderr_sha256"],
            "auth_copy_removed": credential_removed,
            "runtime_temp_symlink_cleanup": runtime_temp_symlink_cleanup,
            "skill_discovery": skill_discovery_receipt,
            "secret_leak_files": secret_leak_files,
            "absolute_path_mappings": mappings,
            "private_artifacts": _private_artifact_receipts(session_root),
            "plugin_installation": installation,
            "summary": result,
        },
        private=True,
    )
    return result, installation, errors


def _plugin_session(
    *,
    repo_root: Path,
    run_root: Path,
    candidate: dict[str, Any],
    plugin_version: str,
    auth_source: Path,
    codex_bin: str,
    model: str,
    timeout: int,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    session_root = run_root / "local-marketplace-plugin"
    try:
        return _plugin_session_impl(
            repo_root=repo_root,
            run_root=run_root,
            candidate=candidate,
            plugin_version=plugin_version,
            auth_source=auth_source,
            codex_bin=codex_bin,
            model=model,
            timeout=timeout,
        )
    finally:
        if session_root.exists():
            _remove_auth_copies(session_root)


def _accept_install_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "result": "passed" if len(results) == 5 and not any(row["evidence_errors"] for row in results) else "failed",
        "accepted_sessions": sum(not row["evidence_errors"] for row in results),
        "skill_discovery_and_enablement_successes": sum(
            row["outcome"]["skill_discovered_and_enabled"] for row in results
        ),
        "structured_skill_invocation_reports": sum(
            row["outcome"]["structured_skill_invocation_reported"] for row in results
        ),
        "reference_file_hash_successes": sum(
            row["outcome"]["reference_file_present_and_hashed"] for row in results
        ),
        "agent_file_read_successes": sum(
            row["outcome"]["agent_file_reads_observed"] for row in results
        ),
        "honest_capability_blocks": sum(row["outcome"]["status"] == "blocked" for row in results),
        "invented_artifacts": sum(row["outcome"]["artifact_invented"] is True for row in results),
        "install_tree_mutations": sum(
            row["install_tree_sha256_before"] != row["install_tree_sha256_after"]
            for row in results
        ),
        "workspace_tree_mutations": sum(
            row["workspace_tree_sha256_before"] != row["workspace_tree_sha256_after"]
            for row in results
        ),
        "session_exit_failures": sum(row["exit_code"] != 0 for row in results),
        "evidence_error_count": sum(len(row["evidence_errors"]) for row in results),
    }


def _accept_probe_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "result": "passed"
        if len(results) == 3 and not any(row["evidence_errors"] for row in results)
        else "failed",
        "required_sessions": 3,
        "accepted_sessions": sum(not row["evidence_errors"] for row in results),
        "session_exit_failures": sum(row["exit_code"] != 0 for row in results),
        "evidence_error_count": sum(len(row["evidence_errors"]) for row in results),
        "invented_artifacts": sum(row["artifacts_invented"] is True for row in results),
        "workspace_tree_mutations": sum(
            row["workspace_tree_sha256_before"] != row["workspace_tree_sha256_after"]
            for row in results
        ),
    }


def _install_scenario_receipt() -> dict[str, Any]:
    return {
        "explicit_skill_invocation": f"${SKILL_NAME}",
        "requested_artifact": "one rendered packaging concept image",
        "required_reference": "references/contracts.md",
        "intentionally_unavailable_capability": "image generation or editing",
        "expected_status": "blocked",
    }


def _install_method_receipt(
    candidate: dict[str, Any],
    repo_root: Path = DEFAULT_REPO_ROOT,
) -> dict[str, Any]:
    return {
        "required_fresh_session_count": 5,
        "standalone_session_count": 4,
        "plugin_session_count": 1,
        "home_isolated_per_session": True,
        "codex_home_isolated_per_session": True,
        "cwd_isolated_per_session": True,
        "credentials": "copied as 0600, removed after each session, omitted from summary",
        "runtime_discovery": "codex app-server skills/list with forceReload=true for each layout",
        "agent_command_reads": "optional; any observed command must remain exact, read-only, and successful",
        "event_hash_basis": "canonical JSONL after absolute-path sanitization; raw bytes retained privately",
        "install_tree_hash_basis": "SHA-256 over sorted relative paths followed by file bytes",
        "public_candidate_file_count": candidate["file_count"],
        "public_candidate_source": candidate["source"],
        "source_skill_tree_sha256": candidate["tree_sha256"],
        "public_candidate_file_sha256": candidate["file_sha256"],
        "git_head": candidate["git_head"],
        "git_status": candidate["git_status"],
        "git_status_sha256": candidate["git_status_sha256"],
        "harness_artifacts": harness_artifact_receipts(repo_root),
    }


def _probe_method_receipt(
    candidate: dict[str, Any],
    repo_root: Path = DEFAULT_REPO_ROOT,
) -> dict[str, Any]:
    return {
        "fresh_session_per_scenario": True,
        "explicit_skill_invocation": f"${SKILL_NAME}",
        "closed_output_schema": True,
        "read_only": True,
        "raw_events_retained_outside_repository": True,
        "event_hash_basis": "canonical JSONL after absolute-path sanitization",
        "candidate_file_count": candidate["file_count"],
        "candidate_tree_sha256": candidate["tree_sha256"],
        "candidate_file_sha256": candidate["file_sha256"],
        "git_head": candidate["git_head"],
        "git_status": candidate["git_status"],
        "git_status_sha256": candidate["git_status_sha256"],
        "harness_artifacts": harness_artifact_receipts(repo_root),
    }


def _write_private_run_manifest(
    *,
    run_root: Path,
    suite: str,
    repo_root: Path,
    candidate: dict[str, Any],
    public_projection: dict[str, Any],
    execution_clock: dict[str, str],
    auth_source: Path,
    runtime_receipt: dict[str, str],
) -> Path:
    session_receipts = []
    for receipt_path in sorted(run_root.glob("*/private-receipt.json")):
        session_receipts.append(
            {
                "session_id": receipt_path.parent.name,
                "relative_path": receipt_path.relative_to(run_root).as_posix(),
                "sha256": file_sha256(receipt_path),
            }
        )
    manifest = {
        "schema_version": 1,
        "suite": suite,
        "executed_on": execution_clock["executed_on"],
        "started_at_local": execution_clock["started_at_local"],
        "auth_source_sha256": file_sha256(auth_source),
        "runtime_receipt": runtime_receipt,
        "candidate": candidate,
        "harness_artifacts": harness_artifact_receipts(repo_root),
        "session_receipts": session_receipts,
        "public_projection": public_projection,
    }
    manifest_path = run_root / "run-manifest.json"
    write_json(manifest_path, manifest, private=True)
    return manifest_path


def _verify_relative_private_file(root: Path, relative_name: str, expected_hash: str) -> Path:
    relative = Path(relative_name)
    if relative.is_absolute() or ".." in relative.parts:
        raise HarnessError("private manifest contains an unsafe relative path")
    path = _resolved(root / relative)
    if not _is_relative_to(path, root) or path.is_symlink() or not path.is_file():
        raise HarnessError("private manifest references a missing or unsafe file")
    if file_sha256(path) != expected_hash:
        raise HarnessError("private artifact hash did not match its manifest")
    return path


def _public_projection_is_sanitized(value: Any) -> bool:
    unix_absolute = re.compile(r"(?<![A-Za-z0-9_.:>$~/\-])/(?!/)[^\s'\"<>]+")
    windows_absolute = re.compile(r"(?:^|[\s'\"])[A-Za-z]:[\\/][^\s'\"<>]+")
    if isinstance(value, dict):
        return all(
            _public_projection_is_sanitized(key) and _public_projection_is_sanitized(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return all(_public_projection_is_sanitized(child) for child in value)
    if isinstance(value, str):
        return (
            unix_absolute.search(value) is None
            and windows_absolute.search(value) is None
            and AUTH_BASENAME not in value
        )
    return True


def _mapped_session_path(
    receipt_path: Path,
    mappings: dict[str, str],
    replacement: str,
) -> Path:
    matches = [source for source, target in mappings.items() if target == replacement]
    if len(matches) != 1:
        raise HarnessError(f"private receipt has no unique mapping for {replacement}")
    path = Path(matches[0])
    resolved = _resolved(path)
    if not _is_relative_to(resolved, receipt_path.parent):
        raise HarnessError("private receipt mapped path escaped its session root")
    if resolved.is_symlink() or not resolved.is_dir():
        raise HarnessError("private receipt mapped tree is missing or unsafe")
    return path


def _artifact_path(
    receipt_path: Path,
    artifacts: dict[str, Any],
    relative_name: str,
) -> Path:
    expected_hash = artifacts.get(relative_name)
    if not isinstance(expected_hash, str):
        raise HarnessError(f"private session receipt is missing {relative_name}")
    return _verify_relative_private_file(
        receipt_path.parent,
        relative_name,
        expected_hash,
    )


def _verify_skill_discovery_receipt(
    *,
    receipt_path: Path,
    receipt: dict[str, Any],
    artifacts: dict[str, Any],
    project: Path,
    install: Path,
    candidate: dict[str, Any],
    codex_bin: str,
) -> bool:
    discovery = receipt.get("skill_discovery")
    expected_keys = {
        "argv",
        "request_sha256",
        "stdout_sha256",
        "stderr_sha256",
        "force_reload",
        "credential_leak_detected",
    }
    if not isinstance(discovery, dict) or set(discovery) != expected_keys:
        raise HarnessError("private Skill discovery receipt has an unexpected shape")
    request_path = _artifact_path(receipt_path, artifacts, "skills-list.request.jsonl")
    stdout_path = _artifact_path(receipt_path, artifacts, "skills-list.raw.jsonl")
    stderr_path = _artifact_path(receipt_path, artifacts, "skills-list.stderr.raw.txt")
    request_bytes = request_path.read_bytes()
    stdout = stdout_path.read_bytes()
    stderr = stderr_path.read_bytes()
    if (
        discovery.get("argv") != [codex_bin, "app-server", "--stdio"]
        or discovery.get("request_sha256") != sha256_bytes(request_bytes)
        or discovery.get("stdout_sha256") != sha256_bytes(stdout)
        or discovery.get("stderr_sha256") != sha256_bytes(stderr)
        or discovery.get("force_reload") is not True
        or discovery.get("credential_leak_detected") is not False
    ):
        raise HarnessError("private Skill discovery receipt did not match its artifacts")
    if request_bytes != _skills_list_request_bytes(project):
        raise HarnessError("private skills/list request did not match the audited cwd")
    evidence = _skill_discovery_evidence(
        _skills_list_response(stdout),
        project=project,
        install=install,
        candidate=candidate,
    )
    if evidence.get("verified") is not True:
        raise HarnessError("private skills/list evidence did not verify the installed Skill")
    return True


def _verify_runtime_evidence(
    manifest: dict[str, Any],
    run_root: Path,
    codex_bin: str,
) -> dict[str, Any]:
    executable = _resolve_codex_executable(codex_bin)
    executable_sha256 = file_sha256(Path(executable))
    manifest_receipt = manifest.get("runtime_receipt")
    if not isinstance(manifest_receipt, dict) or set(manifest_receipt) != {
        "relative_path",
        "sha256",
    }:
        raise HarnessError("private run manifest has no closed runtime receipt")
    receipt_path = _verify_relative_private_file(
        run_root,
        str(manifest_receipt.get("relative_path", "")),
        str(manifest_receipt.get("sha256", "")),
    )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if not isinstance(receipt, dict) or set(receipt) != {
        "public_runtime",
        "client_executable",
        "commands",
    }:
        raise HarnessError("private runtime receipt has an unexpected shape")
    commands = receipt.get("commands")
    runtime = receipt.get("public_runtime")
    client_executable = receipt.get("client_executable")
    if (
        not isinstance(commands, dict)
        or not isinstance(runtime, dict)
        or not isinstance(client_executable, dict)
        or set(client_executable) != {"resolved_path", "sha256"}
    ):
        raise HarnessError("private runtime receipt is incomplete")
    if client_executable != {
        "resolved_path": executable,
        "sha256": executable_sha256,
    }:
        raise HarnessError("private runtime receipt did not match the resolved Codex executable")

    def read_command(label: str) -> tuple[str, list[str]]:
        command = commands.get(label)
        if not isinstance(command, dict) or set(command) != {
            "argv",
            "exit_code",
            "stdout_relative_path",
            "stdout_sha256",
            "stderr_relative_path",
            "stderr_sha256",
        }:
            raise HarnessError(f"runtime command receipt {label} is incomplete")
        stdout_path = _verify_relative_private_file(
            run_root,
            str(command["stdout_relative_path"]),
            str(command["stdout_sha256"]),
        )
        _verify_relative_private_file(
            run_root,
            str(command["stderr_relative_path"]),
            str(command["stderr_sha256"]),
        )
        argv = command.get("argv")
        if command.get("exit_code") != 0 or not isinstance(argv, list) or not all(
            isinstance(item, str) for item in argv
        ):
            raise HarnessError(f"runtime command receipt {label} did not succeed")
        value = stdout_path.read_text(encoding="utf-8").strip()
        if not value:
            raise HarnessError(f"runtime command receipt {label} was empty")
        return value, argv

    client_line, client_argv = read_command("client-version")
    if client_argv != [executable, "--version"]:
        raise HarnessError("runtime Codex version argv did not match --codex-bin")
    system_name, system_argv = read_command("uname-system")
    system_release, release_argv = read_command("uname-release")
    system_build, build_argv = read_command("uname-build")
    architecture, architecture_argv = read_command("uname-architecture")
    for argv, flag in (
        (system_argv, "-s"),
        (release_argv, "-r"),
        (build_argv, "-v"),
        (architecture_argv, "-m"),
    ):
        if len(argv) != 2 or Path(argv[0]).name != "uname" or argv[1] != flag:
            raise HarnessError("runtime uname argv did not match the harness contract")
    macos_version = None
    macos_build = None
    expected_labels = {
        "client-version",
        "uname-system",
        "uname-release",
        "uname-build",
        "uname-architecture",
    }
    if system_name == "Darwin":
        macos_version, version_argv = read_command("sw-vers-version")
        macos_build, macos_build_argv = read_command("sw-vers-build")
        if (
            len(version_argv) != 2
            or Path(version_argv[0]).name != "sw_vers"
            or version_argv[1] != "-productVersion"
            or len(macos_build_argv) != 2
            or Path(macos_build_argv[0]).name != "sw_vers"
            or macos_build_argv[1] != "-buildVersion"
        ):
            raise HarnessError("runtime sw_vers argv did not match the harness contract")
        expected_labels.update({"sw-vers-version", "sw-vers-build"})
    if set(commands) != expected_labels:
        raise HarnessError("private runtime command set was incomplete or unexpected")
    model = runtime.get("model")
    if not isinstance(model, str) or not model:
        raise HarnessError("private runtime receipt has no model")
    rebuilt = _runtime_from_command_outputs(
        client_line=client_line,
        system_name=system_name,
        system_release=system_release,
        system_build=system_build,
        architecture=architecture,
        model=model,
        client_executable_sha256=executable_sha256,
        macos_version=macos_version,
        macos_build=macos_build,
    )
    if runtime != rebuilt:
        raise HarnessError("public runtime did not derive from retained runtime commands")
    return rebuilt


def _verify_plugin_installation(
    *,
    receipt_path: Path,
    receipt: dict[str, Any],
    projection: dict[str, Any],
    candidate: dict[str, Any],
    repo_root: Path,
    codex_bin: str,
) -> None:
    installation = receipt.get("plugin_installation")
    if not isinstance(installation, dict) or installation != projection.get(
        "plugin_installation"
    ):
        raise HarnessError("plugin installation receipt did not match the public projection")
    if set(installation) != {
        "marketplace_name",
        "marketplace_source",
        "distribution",
        "distribution_contents",
        "command_receipts",
        "plugin_id",
        "plugin_version",
        "installed",
        "enabled",
        "plugin_list_source_inside_private_session",
        "remote_catalog_required",
        "cache_audit",
    }:
        raise HarnessError("plugin installation receipt has an unexpected shape")
    mappings = receipt["absolute_path_mappings"]
    marketplace = _mapped_session_path(receipt_path, mappings, "<private-marketplace>")
    expected_plugin_id = f"{SKILL_NAME}@{MARKETPLACE_NAME}"
    expected_plugin_argv = _plugin_command_argv(
        codex_bin,
        marketplace,
        expected_plugin_id,
    )
    if receipt.get("plugin_command_argv") != expected_plugin_argv:
        raise HarnessError("private plugin command argv did not match the harness contract")
    cache_root = _mapped_session_path(receipt_path, mappings, "<plugin-cache>")
    skill_root = cache_root / "skills" / SKILL_NAME
    skill_snapshot = tree_snapshot(skill_root)
    if (
        skill_snapshot["files"] != candidate["files"]
        or skill_snapshot["file_count"] != candidate["file_count"]
        or skill_snapshot["tree_sha256"] != candidate["tree_sha256"]
    ):
        raise HarnessError("installed plugin Skill tree did not match the confirmed candidate")
    if file_sha256(cache_root / ".codex-plugin" / "plugin.json") != file_sha256(
        repo_root / ".codex-plugin" / "plugin.json"
    ):
        raise HarnessError("installed plugin manifest did not match the release candidate")
    if file_sha256(cache_root / "LICENSE") != file_sha256(repo_root / "LICENSE"):
        raise HarnessError("installed plugin license did not match the release candidate")

    installed_names = [path.as_posix() for path in _regular_files(cache_root)]
    expected_names = sorted(
        [".codex-plugin/plugin.json", "LICENSE"]
        + [f"skills/{SKILL_NAME}/{name}" for name in candidate["files"]]
    )
    unexpected = sorted(set(installed_names) - set(expected_names))
    missing = sorted(set(expected_names) - set(installed_names))
    cache_audit = {
        "cache_root_basis": "unique isolated cache manifest matching plugin name and version",
        "installed_file_count": len(installed_names),
        "installed_skill_file_count": len(
            [name for name in installed_names if name.startswith(f"skills/{SKILL_NAME}/")]
        ),
        "pyc_file_count": len(
            [name for name in installed_names if name.endswith(".pyc") or "__pycache__" in name]
        ),
        "unexpected_files": unexpected,
        "missing_files": missing,
        "installed_files": installed_names,
    }
    if set(installation.get("cache_audit", {})) != set(cache_audit):
        raise HarnessError("plugin cache audit has an unexpected shape")
    if installation.get("cache_audit") != cache_audit:
        raise HarnessError("plugin cache audit did not match the private installed tree")
    if unexpected or missing or cache_audit["pyc_file_count"]:
        raise HarnessError("plugin cache inventory was not the exact skills-only distribution")

    if (
        installation.get("marketplace_name") != MARKETPLACE_NAME
        or installation.get("marketplace_source")
        != "isolated local filesystem marketplace"
        or installation.get("distribution") != "skills-only plugin"
        or installation.get("distribution_contents")
        != [
            ".codex-plugin/plugin.json",
            f"skills/{SKILL_NAME}/",
            "LICENSE",
        ]
        or installation.get("plugin_id") != expected_plugin_id
        or installation.get("plugin_version") != load_plugin_version(repo_root)
        or installation.get("installed") is not True
        or installation.get("enabled") is not True
        or installation.get("plugin_list_source_inside_private_session") is not True
        or installation.get("remote_catalog_required") is not False
    ):
        raise HarnessError("plugin installation status did not meet the audited contract")

    command_receipts = installation.get("command_receipts")
    expected_labels = ("marketplace-add", "plugin-add", "plugin-list")
    if not isinstance(command_receipts, dict) or set(command_receipts) != set(expected_labels):
        raise HarnessError("plugin command receipt set was incomplete")
    plugin_list: Any | None = None
    for label in expected_labels:
        command_receipt = command_receipts[label]
        if not isinstance(command_receipt, dict) or set(command_receipt) != {
            "argv",
            "exit_code",
            "stdout_sha256",
            "stderr_sha256",
            "json_output",
            "credential_leak_detected",
        }:
            raise HarnessError("plugin command receipt was not an object")
        if command_receipt.get("argv") != _sanitize_value(
            expected_plugin_argv[label], mappings
        ):
            raise HarnessError("public plugin command argv did not match private execution")
        stdout_path = _artifact_path(
            receipt_path,
            receipt["private_artifacts"],
            f"{label}.stdout.raw.json",
        )
        stderr_path = _artifact_path(
            receipt_path,
            receipt["private_artifacts"],
            f"{label}.stderr.raw.txt",
        )
        stdout = stdout_path.read_bytes()
        stderr = stderr_path.read_bytes()
        if (
            command_receipt.get("exit_code") != 0
            or command_receipt.get("stdout_sha256") != sha256_bytes(stdout)
            or command_receipt.get("stderr_sha256") != sha256_bytes(stderr)
            or command_receipt.get("json_output") is not True
            or command_receipt.get("credential_leak_detected") is not False
        ):
            raise HarnessError("plugin command receipt did not match its raw artifacts")
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError as error:
            raise HarnessError("plugin command output was not valid JSON") from error
        if label == "plugin-list":
            plugin_list = parsed
    entry = _plugin_entry(plugin_list, expected_plugin_id)
    if not isinstance(entry, dict):
        raise HarnessError("plugin list did not contain the expected plugin")
    source = entry.get("source")
    source_path = source.get("path") if isinstance(source, dict) else None
    if (
        entry.get("installed") is not True
        or entry.get("enabled") is not True
        or entry.get("version") != load_plugin_version(repo_root)
        or not isinstance(source_path, str)
        or not _is_relative_to(_resolved(Path(source_path)), receipt_path.parent)
    ):
        raise HarnessError("plugin list raw output did not verify the installed plugin")


def _verify_public_result_shape(suite: str, result: dict[str, Any]) -> None:
    common_integrity_keys = {
        "id",
        "exit_code",
        "event_stream_sha256",
        "command_evidence",
        "event_evidence",
        "install_tree_sha256_before",
        "install_tree_sha256_after",
        "workspace_tree_sha256_before",
        "workspace_tree_sha256_after",
        "credential_copy_mode",
        "credential_store",
        "credential_copy_removed",
        "credential_leak_detected",
        "evidence_errors",
    }
    if suite == "workflow-probes":
        expected_keys = common_integrity_keys | {
            "structured_response_sha256",
            "expected_start_stage",
            "observed_start_stage",
            "requested_scope_end_stage",
            "current_stage_status",
            "active_stage_outputs",
            "ecommerce_roles",
            "claims_made",
            "publication_authorized",
            "image_generation_invoked",
            "artifacts_invented",
            "files_written",
            "capability_limits",
        }
        if set(result) != expected_keys:
            raise HarnessError("probe result has an unexpected public shape")
        return

    expected_keys = common_integrity_keys | {
        "distribution",
        "environment",
        "outcome",
    }
    session_id = result.get("id")
    if session_id == "local-marketplace-plugin":
        expected_keys.add("discovered_skill_id")
        expected_environment = {
            "home": "isolated temporary home",
            "codex_home": "explicitly set to the isolated plugin-install Codex home",
            "install_relative_path": f"<plugin-cache>/skills/{SKILL_NAME}",
            "cwd": "isolated empty project outside the marketplace and install cache",
            "ignore_user_config": False,
            "ignore_user_config_reason": (
                "plugin enablement is the isolated config generated by marketplace and plugin add"
            ),
        }
        if (
            result.get("distribution") != "skills-only-plugin"
            or result.get("discovered_skill_id") != f"{SKILL_NAME}:{SKILL_NAME}"
            or result.get("environment") != expected_environment
        ):
            raise HarnessError("plugin result environment did not match the harness contract")
    else:
        expected_keys.add("structured_response_sha256")
        layout = next(
            (item for item in STANDALONE_LAYOUTS if item["id"] == session_id),
            None,
        )
        if layout is None:
            raise HarnessError("standalone result has an unknown layout")
        expected_environment = {
            "home": "isolated temporary home",
            "codex_home": (
                "explicitly set to an isolated temporary Codex home"
                if session_id == "explicit-codex-home-skills"
                else "unset and derived from the isolated home"
            ),
            "install_relative_path": layout["install_relative_path"],
            "cwd": layout["cwd"],
            "ignore_user_config": True,
        }
        if (
            result.get("distribution") != "standalone"
            or result.get("environment") != expected_environment
        ):
            raise HarnessError("standalone result environment did not match the harness contract")
    if set(result) != expected_keys:
        raise HarnessError("install result has an unexpected public shape")
    if not isinstance(result.get("outcome"), dict) or set(result["outcome"]) != {
        "skill_discovered_and_enabled",
        "structured_skill_invocation_reported",
        "reference_file_present_and_hashed",
        "agent_file_reads_observed",
        "capability_gap_reported",
        "status",
        "artifact_invented",
        "files_written",
    }:
        raise HarnessError("install outcome has an unexpected public shape")


def _verify_session_receipt(
    *,
    suite: str,
    receipt_path: Path,
    receipt: dict[str, Any],
    result: dict[str, Any],
    candidate: dict[str, Any],
    repo_root: Path,
    runtime: dict[str, Any],
    codex_bin: str,
) -> None:
    expected_receipt_keys = {
        "codex_argv",
        "raw_event_stream_sha256",
        "sanitized_event_stream_sha256",
        "stderr_sha256",
        "auth_copy_removed",
        "runtime_temp_symlink_cleanup",
        "secret_leak_files",
        "absolute_path_mappings",
        "private_artifacts",
        "summary",
    }
    if suite == "install-smoke" and result.get("id") == "local-marketplace-plugin":
        expected_receipt_keys.update({"plugin_command_argv", "plugin_installation"})
    if suite == "install-smoke":
        expected_receipt_keys.add("skill_discovery")
    if not isinstance(receipt, dict) or set(receipt) != expected_receipt_keys:
        raise HarnessError("private session receipt has an unexpected shape")
    if receipt.get("summary") != result:
        raise HarnessError("private session summary did not match the public projection")
    if receipt.get("auth_copy_removed") is not True:
        raise HarnessError("private session receipt did not verify credential cleanup")
    cleanup = receipt.get("runtime_temp_symlink_cleanup")
    if not isinstance(cleanup, dict) or set(cleanup) != {"removed_count", "removed"}:
        raise HarnessError("runtime temp symlink cleanup receipt has an unexpected shape")
    removed = cleanup.get("removed")
    if (
        not isinstance(cleanup.get("removed_count"), int)
        or not isinstance(removed, list)
        or cleanup["removed_count"] != len(removed)
    ):
        raise HarnessError("runtime temp symlink cleanup receipt count did not match")
    seen_runtime_links: set[str] = set()
    for row in removed:
        if not isinstance(row, dict) or set(row) != {
            "relative_path",
            "target_basename",
            "target_sha256",
            "target_client_version",
        }:
            raise HarnessError("runtime temp symlink cleanup row has an unexpected shape")
        relative_name = row.get("relative_path")
        relative_path = Path(relative_name) if isinstance(relative_name, str) else Path("/")
        if (
            not isinstance(relative_name, str)
            or relative_path.is_absolute()
            or ".." in relative_path.parts
            or not _is_codex_runtime_temp_symlink(relative_path)
            or relative_name in seen_runtime_links
        ):
            raise HarnessError("runtime temp symlink cleanup row was unsafe or duplicated")
        if (
            row.get("target_basename") != "codex"
            or not re.fullmatch(r"[0-9a-f]{64}", str(row.get("target_sha256", "")))
            or row.get("target_client_version") != runtime.get("client_version")
        ):
            raise HarnessError("runtime temp symlink cleanup target evidence was invalid")
        seen_runtime_links.add(relative_name)
    if _symlink_paths(receipt_path.parent):
        raise HarnessError("a symlink remained in the verified private session")
    if receipt.get("secret_leak_files") != []:
        raise HarnessError("private session receipt reported credential material")
    if any(
        path.exists() or path.is_symlink()
        for path in receipt_path.parent.rglob(AUTH_BASENAME)
    ):
        raise HarnessError("credential copy remained in the private session")
    mappings = receipt.get("absolute_path_mappings")
    artifacts = receipt.get("private_artifacts")
    if not isinstance(mappings, dict) or not mappings or not all(
        isinstance(source, str) and isinstance(target, str)
        for source, target in mappings.items()
    ):
        raise HarnessError("private session path mappings were missing or invalid")
    if not isinstance(artifacts, dict) or not artifacts:
        raise HarnessError("private session receipt has no raw artifact manifest")
    for relative_name, expected_hash in artifacts.items():
        _verify_relative_private_file(
            receipt_path.parent,
            str(relative_name),
            str(expected_hash),
        )

    raw_path = _artifact_path(receipt_path, artifacts, "events.raw.jsonl")
    sanitized_path = _artifact_path(receipt_path, artifacts, "events.sanitized.jsonl")
    stderr_path = _artifact_path(receipt_path, artifacts, "stderr.raw.txt")
    last_message_path = _artifact_path(receipt_path, artifacts, "last-message.json")
    prompt_path = _artifact_path(receipt_path, artifacts, "prompt.txt")
    schema_path = _artifact_path(receipt_path, artifacts, "output-schema.json")
    raw = raw_path.read_bytes()
    sanitized = sanitized_path.read_bytes()
    stderr = stderr_path.read_bytes()
    recomputed_sanitized = sanitize_jsonl_bytes(raw, mappings)
    if sanitized != recomputed_sanitized:
        raise HarnessError("sanitized event stream did not derive from the raw JSONL")
    if (
        receipt.get("raw_event_stream_sha256") != sha256_bytes(raw)
        or receipt.get("sanitized_event_stream_sha256") != sha256_bytes(sanitized)
        or receipt.get("stderr_sha256") != sha256_bytes(stderr)
        or result.get("event_stream_sha256") != sha256_bytes(sanitized)
    ):
        raise HarnessError("private event or stderr hashes did not match their artifacts")

    events = parse_jsonl(raw)
    lifecycle = audit_event_lifecycle(events)
    if lifecycle != result.get("event_evidence"):
        raise HarnessError("event lifecycle receipt did not derive from raw JSONL")
    if (
        not lifecycle["lifecycle_complete"]
        or lifecycle["failed_event_count"]
        or lifecycle["incomplete_item_count"]
        or lifecycle["disallowed_item_types"]
    ):
        raise HarnessError("raw event lifecycle was incomplete, failed, or disallowed")

    try:
        final = json.loads(last_message_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise HarnessError("private last message was not valid JSON") from error
    if _last_agent_message(events) != final:
        raise HarnessError("private last message did not match the raw agent event")

    if suite == "workflow-probes":
        scenario_by_id = {row["id"]: row for row in load_scenarios(repo_root)}
        scenario = scenario_by_id[result["id"]]
        expected_reference_names = PROBE_REFERENCES[result["id"]]
        install_token = f"$CODEX_HOME/skills/{SKILL_NAME}"
        final_errors = validate_probe_output(final, scenario)
    else:
        scenario = None
        expected_reference_names = ("SKILL.md", "references/contracts.md")
        environment = result.get("environment")
        if not isinstance(environment, dict):
            raise HarnessError("install result has no environment receipt")
        install_token = str(environment.get("install_relative_path", ""))
        final_errors = validate_install_output(final)
    if final_errors:
        raise HarnessError("private last message failed the closed output contract")

    install_root = _mapped_session_path(receipt_path, mappings, install_token)
    project_root = _mapped_session_path(receipt_path, mappings, "<project>")
    discovery_verified = False
    if suite == "install-smoke":
        discovery_verified = _verify_skill_discovery_receipt(
            receipt_path=receipt_path,
            receipt=receipt,
            artifacts=artifacts,
            project=project_root,
            install=install_root,
            candidate=candidate,
            codex_bin=codex_bin,
        )
    expected_schema = (
        probe_output_schema(scenario, repo_root)
        if suite == "workflow-probes"
        else install_output_schema(repo_root)
    )
    expected_prompt = (
        _probe_prompt(scenario, install_root)
        if suite == "workflow-probes"
        else _install_prompt(install_root)
    )
    expected_schema_bytes = (
        json.dumps(expected_schema, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    if prompt_path.read_bytes() != expected_prompt.encode("utf-8"):
        raise HarnessError("retained private prompt did not match the harness-generated prompt")
    if schema_path.read_bytes() != expected_schema_bytes:
        raise HarnessError("retained private output schema did not match the public schema")
    ignore_user_config = (
        True
        if suite == "workflow-probes"
        else bool(result["environment"]["ignore_user_config"])
    )
    expected_argv = _codex_argv(
        codex_bin,
        project_root,
        schema_path,
        last_message_path,
        str(runtime["model"]),
        ignore_user_config,
    )
    if receipt.get("codex_argv") != expected_argv:
        raise HarnessError("private Codex argv did not match the verified runtime contract")
    required_paths = [install_root / relative for relative in expected_reference_names]
    command_evidence = _sanitized_command_receipt(
        audit_command_events(events, required_paths, require_content_markers=True),
        mappings,
    )
    if command_evidence != result.get("command_evidence"):
        raise HarnessError("command evidence did not derive from raw command events")
    if suite == "workflow-probes":
        if (
            not command_evidence["required_reads_succeeded"]
            or command_evidence["write_like_command_detected"]
        ):
            raise HarnessError("required exact reads failed or a write-like command was observed")
    elif (
        command_evidence["unexpected_command_count"]
        or command_evidence["duplicate_required_read_count"]
        or command_evidence["nonzero_command_exit_count"]
        or command_evidence["write_like_command_detected"]
    ):
        raise HarnessError("install agent ran a failed, unexpected, duplicated, or write-like command")

    install_snapshot = tree_snapshot(install_root)
    project_snapshot = tree_snapshot(project_root)
    if (
        install_snapshot["files"] != candidate["files"]
        or install_snapshot["file_count"] != candidate["file_count"]
        or install_snapshot["tree_sha256"] != candidate["tree_sha256"]
    ):
        raise HarnessError("installed Skill tree did not match the confirmed candidate")
    if (
        result.get("install_tree_sha256_before") != install_snapshot["tree_sha256"]
        or result.get("install_tree_sha256_after") != install_snapshot["tree_sha256"]
        or result.get("workspace_tree_sha256_before") != project_snapshot["tree_sha256"]
        or result.get("workspace_tree_sha256_after") != project_snapshot["tree_sha256"]
    ):
        raise HarnessError("session tree hashes did not match the retained private trees")
    if (
        result.get("exit_code") != 0
        or result.get("credential_copy_mode") != "0600"
        or result.get("credential_store") != "file"
        or result.get("credential_copy_removed") is not True
        or result.get("credential_leak_detected") is not False
        or result.get("evidence_errors") != []
    ):
        raise HarnessError("session summary did not meet execution and credential invariants")

    response_hash = sha256_bytes(
        json.dumps(_sanitize_value(final, mappings), sort_keys=True).encode("utf-8")
    )
    if "structured_response_sha256" in result and result.get(
        "structured_response_sha256"
    ) != response_hash:
        raise HarnessError("structured response hash did not match the private last message")
    if suite == "workflow-probes":
        public_final = _sanitize_value(final, mappings)
        expected_fields = {
            "expected_start_stage": scenario["expected_start_stage"],
            "observed_start_stage": public_final["observed_start_stage"],
            "requested_scope_end_stage": public_final["requested_scope_end_stage"],
            "current_stage_status": public_final["current_stage_status"],
            "active_stage_outputs": public_final["active_stage_outputs"],
            "ecommerce_roles": public_final["ecommerce_roles"],
            "claims_made": public_final["claims_made"],
            "publication_authorized": public_final["publication_authorized"],
            "image_generation_invoked": public_final["image_generation_invoked"],
            "artifacts_invented": public_final["artifacts_invented"],
            "files_written": False,
            "capability_limits": public_final["capability_limits"],
        }
        if any(result.get(key) != value for key, value in expected_fields.items()):
            raise HarnessError("probe summary did not derive from the private last message")
    else:
        expected_outcome = _install_outcome(
            final=final,
            discovery_verified=discovery_verified,
            project_mutated=False,
            command_receipt=command_evidence,
        )
        if result.get("outcome") != expected_outcome:
            raise HarnessError("install summary did not derive from the private last message")


def verify_private_run_manifest(
    manifest_path: Path,
    repo_root: Path,
    expected_suite: str | None = None,
    require_passed: bool = True,
    auth_source: Path | None = None,
    codex_bin: str = "codex",
) -> dict[str, Any]:
    _require_private_runtime_support()
    repo = _resolved(repo_root)
    executable = _resolve_codex_executable(codex_bin)
    manifest_file = _resolved(manifest_path)
    require_private_audit_root(repo, manifest_file.parent)
    if manifest_file.is_symlink() or not manifest_file.is_file():
        raise HarnessError("private run manifest is missing or is a symlink")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if auth_source is None:
        raise HarnessError("private manifest verification requires --auth-source")
    auth, secret_values = _validated_auth_source(repo, auth_source)
    if manifest.get("auth_source_sha256") != file_sha256(auth):
        raise HarnessError("private run manifest did not match the supplied auth source")
    suite = manifest.get("suite")
    if suite not in {"install-smoke", "workflow-probes"}:
        raise HarnessError("private run manifest has an unknown suite")
    if expected_suite is not None and suite != expected_suite:
        raise HarnessError("private run manifest suite did not match the requested projection")
    executed_on = manifest.get("executed_on")
    started_at_local = manifest.get("started_at_local")
    try:
        started_at = datetime.fromisoformat(str(started_at_local))
        parsed_date = datetime.strptime(str(executed_on), "%Y-%m-%d").date()
    except ValueError as error:
        raise HarnessError("private run manifest has an invalid local execution timestamp") from error
    if started_at.tzinfo is None or started_at.utcoffset() is None:
        raise HarnessError("private run manifest local execution timestamp has no UTC offset")
    if started_at.date() != parsed_date:
        raise HarnessError("private run manifest date did not match its local start timestamp")
    candidate = manifest.get("candidate")
    if not isinstance(candidate, dict) or candidate != discover_candidate(repo):
        raise HarnessError("private run manifest candidate no longer matches the worktree")
    if manifest.get("harness_artifacts") != harness_artifact_receipts(repo):
        raise HarnessError("private run manifest harness/schema inputs no longer match")
    projection = manifest.get("public_projection")
    if not isinstance(projection, dict) or not _public_projection_is_sanitized(projection):
        raise HarnessError("public projection contains an unsanitized private path")
    if projection.get("executed_on") != executed_on:
        raise HarnessError("public projection date did not match the private run manifest")
    run_root = manifest_file.parent
    rebuilt_runtime = _verify_runtime_evidence(manifest, run_root, executable)
    if projection.get("runtime") != rebuilt_runtime:
        raise HarnessError("public projection runtime did not match verified runtime evidence")
    expected_ids = (
        {layout["id"] for layout in STANDALONE_LAYOUTS} | {"local-marketplace-plugin"}
        if suite == "install-smoke"
        else set(PROBE_REFERENCES)
    )
    expected_count = len(expected_ids)
    receipt_rows = manifest.get("session_receipts")
    if not isinstance(receipt_rows, list) or len(receipt_rows) != expected_count:
        raise HarnessError("private run manifest has the wrong session receipt count")
    projection_results = projection.get("results")
    if not isinstance(projection_results, list) or len(projection_results) != expected_count:
        raise HarnessError("public projection has the wrong result count")
    projected_by_id = {row.get("id"): row for row in projection_results if isinstance(row, dict)}
    if len(projected_by_id) != expected_count or set(projected_by_id) != expected_ids:
        raise HarnessError("public projection result IDs are missing, duplicated, or unexpected")
    receipt_ids = [row.get("session_id") for row in receipt_rows if isinstance(row, dict)]
    if len(receipt_ids) != expected_count or set(receipt_ids) != expected_ids:
        raise HarnessError("private receipt session IDs are missing, duplicated, or unexpected")
    if _secret_leak_files(run_root, secret_values):
        raise HarnessError("credential material remained in private run artifacts")
    for receipt_row in receipt_rows:
        if not isinstance(receipt_row, dict):
            raise HarnessError("private session receipt entry is not an object")
        receipt_path = _verify_relative_private_file(
            run_root,
            str(receipt_row.get("relative_path", "")),
            str(receipt_row.get("sha256", "")),
        )
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        session_id = receipt_row.get("session_id")
        if receipt_path.parent.name != session_id:
            raise HarnessError("private receipt session ID did not match its directory")
        result = projected_by_id[session_id]
        _verify_public_result_shape(suite, result)
        _verify_session_receipt(
            suite=suite,
            receipt_path=receipt_path,
            receipt=receipt,
            result=result,
            candidate=candidate,
            repo_root=repo,
            runtime=rebuilt_runtime,
            codex_bin=executable,
        )
        if suite == "install-smoke" and session_id == "local-marketplace-plugin":
            _verify_plugin_installation(
                receipt_path=receipt_path,
                receipt=receipt,
                projection=projection,
                candidate=candidate,
                repo_root=repo,
                codex_bin=executable,
            )
    acceptance = projection.get("acceptance")
    recomputed_acceptance = (
        _accept_install_results(projection_results)
        if suite == "install-smoke"
        else _accept_probe_results(projection_results)
    )
    if acceptance != recomputed_acceptance:
        raise HarnessError("public acceptance did not derive from verified session results")
    if suite == "install-smoke":
        expected_projection = {
            "schema_version": 2,
            "executed_on": executed_on,
            "runtime": rebuilt_runtime,
            "scenario": _install_scenario_receipt(),
            "method": _install_method_receipt(candidate, repo),
            "plugin_installation": projection.get("plugin_installation"),
            "results": projection_results,
            "acceptance": recomputed_acceptance,
        }
    else:
        expected_projection = {
            "schema_version": 1,
            "executed_on": executed_on,
            "runtime": rebuilt_runtime,
            "method": _probe_method_receipt(candidate, repo),
            "results": projection_results,
            "acceptance": recomputed_acceptance,
        }
    if projection != expected_projection:
        raise HarnessError("public projection did not match the closed verified suite projection")
    if require_passed and (
        not isinstance(recomputed_acceptance, dict)
        or recomputed_acceptance.get("result") != "passed"
    ):
        raise HarnessError("private run did not pass; public evidence projection is forbidden")
    public_projection = json.loads(json.dumps(projection))
    public_projection["private_audit_receipt"] = {
        "raw_root": "<private-audit-root>",
        "run_manifest_sha256": file_sha256(manifest_file),
        "verification": "passed",
    }
    return public_projection


def run_install_smoke(
    *,
    repo_root: Path,
    audit_root: Path,
    auth_source: Path,
    codex_bin: str,
    model: str,
    timeout: int,
    candidate: dict[str, Any],
) -> Path:
    repo = _resolved(repo_root)
    executable = _resolve_codex_executable(codex_bin)
    audit = require_private_audit_root(repo, audit_root)
    require_candidate_unchanged(repo, candidate)
    plugin_version = load_plugin_version(repo)
    execution_clock = capture_local_execution_clock()
    run_root = (
        audit
        / SKILL_NAME
        / plugin_version
        / f"install-{execution_clock['executed_on']}-{uuid.uuid4().hex[:12]}"
    )
    run_root.mkdir(parents=True, mode=0o700)
    runtime, runtime_receipt = capture_runtime_evidence(
        repo,
        executable,
        model,
        run_root,
    )
    require_candidate_unchanged(repo, candidate)
    results: list[dict[str, Any]] = []
    for layout in STANDALONE_LAYOUTS:
        require_candidate_unchanged(repo, candidate)
        result, _ = _standalone_session(
            repo_root=repo,
            run_root=run_root,
            layout=layout,
            candidate=candidate,
            auth_source=auth_source,
            codex_bin=executable,
            model=model,
            timeout=timeout,
        )
        results.append(result)
        require_candidate_unchanged(repo, candidate)
    require_candidate_unchanged(repo, candidate)
    plugin_result, installation, _ = _plugin_session(
        repo_root=repo,
        run_root=run_root,
        candidate=candidate,
        plugin_version=plugin_version,
        auth_source=auth_source,
        codex_bin=executable,
        model=model,
        timeout=timeout,
    )
    results.append(plugin_result)
    require_candidate_unchanged(repo, candidate)
    evidence = {
        "schema_version": 2,
        "executed_on": execution_clock["executed_on"],
        "runtime": runtime,
        "scenario": _install_scenario_receipt(),
        "method": _install_method_receipt(candidate, repo),
        "plugin_installation": installation,
        "results": results,
        "acceptance": _accept_install_results(results),
    }
    return _write_private_run_manifest(
        run_root=run_root,
        suite="install-smoke",
        repo_root=repo,
        candidate=candidate,
        public_projection=evidence,
        execution_clock=execution_clock,
        auth_source=auth_source,
        runtime_receipt=runtime_receipt,
    )


def _probe_session_impl(
    *,
    repo_root: Path,
    run_root: Path,
    scenario: dict[str, Any],
    candidate: dict[str, Any],
    auth_source: Path,
    codex_bin: str,
    model: str,
    timeout: int,
) -> Path:
    session_root = run_root / scenario["id"]
    session_root.mkdir(parents=True, mode=0o700)
    home = session_root / "home"
    codex_home = session_root / "codex-home"
    project = session_root / "project"
    install = codex_home / "skills" / SKILL_NAME
    home.mkdir()
    project.mkdir()
    _copy_candidate(repo_root, candidate, install)
    _copy_auth(auth_source, codex_home)
    secret_values = _credential_secret_values(auth_source)
    before_install = tree_snapshot(install)
    before_project = tree_snapshot(project)
    mappings = {
        str(install): "$CODEX_HOME/skills/packaging-product-visuals",
        str(codex_home): "$CODEX_HOME",
        str(home): "$HOME",
        str(project): "<project>",
        str(session_root): "<private-session-root>",
        str(run_root): "<private-run-root>",
        str(repo_root): "<repo>",
        str(auth_source): "<auth-source>",
    }
    env = _isolated_env(home, codex_home)
    env["PPV_SKILL_ROOT"] = str(install)
    try:
        execution = _run_codex(
            codex_bin=codex_bin,
            model=model,
            session_root=session_root,
            cwd=project,
            env=env,
            prompt=_probe_prompt(scenario, install),
            schema=probe_output_schema(scenario, repo_root),
            ignore_user_config=True,
            timeout=timeout,
            path_mappings=mappings,
            secret_values=secret_values,
        )
    finally:
        credential_removed = _remove_auth_copies(session_root)
    runtime_temp_symlink_cleanup = _remove_codex_runtime_temp_symlinks(
        session_root,
        codex_bin,
    )
    secret_leak_files = _secret_leak_files(session_root, secret_values)
    after_install = tree_snapshot(install)
    after_project = tree_snapshot(project)
    required_paths = [install / relative for relative in PROBE_REFERENCES[scenario["id"]]]
    command_receipt = (
        audit_command_events(
            execution["events"], required_paths, require_content_markers=True
        )
        if execution["events"]
        else {
            "completed_command_count": 0,
            "successful_command_count": 0,
            "commands": [],
            "required_reads": [],
            "required_reads_succeeded": False,
            "write_like_command_detected": False,
        }
    )
    final = execution["final"] if isinstance(execution["final"], dict) else {}
    public_final = _sanitize_value(final, mappings)
    errors = validate_probe_output(final, scenario)
    if execution["exit_code"] != 0:
        errors.append(f"codex exec exited {execution['exit_code']}")
    if not command_receipt["required_reads_succeeded"]:
        errors.append("required Skill and stage-reference reads were not observed")
    if command_receipt["write_like_command_detected"]:
        errors.append("a write-like agent command was observed")
    lifecycle = execution.get("event_lifecycle")
    if not lifecycle or not lifecycle["lifecycle_complete"]:
        errors.append("event stream lifecycle was incomplete")
    elif (
        lifecycle["failed_event_count"]
        or lifecycle["incomplete_item_count"]
        or lifecycle["disallowed_item_types"]
    ):
        errors.append("event stream contained failed or disallowed events")
    if not execution.get("final_message_matches_event"):
        errors.append("last agent_message did not match --output-last-message")
    if execution.get("credential_material_detected"):
        errors.append("credential material appeared in Codex output")
    if secret_leak_files:
        errors.append("credential material appeared in private session artifacts")
    if before_install != after_install:
        errors.append("installed Skill tree mutated")
    if before_project != after_project:
        errors.append("isolated project tree mutated")
    if not credential_removed:
        errors.append("credential copy was not removed")
    result = {
        "id": scenario["id"],
        "exit_code": execution["exit_code"],
        "event_stream_sha256": execution["sanitized_event_stream_sha256"],
        "structured_response_sha256": sha256_bytes(
            json.dumps(_sanitize_value(final, mappings), sort_keys=True).encode("utf-8")
        ),
        "expected_start_stage": scenario["expected_start_stage"],
        "observed_start_stage": public_final.get("observed_start_stage"),
        "requested_scope_end_stage": public_final.get("requested_scope_end_stage"),
        "current_stage_status": public_final.get("current_stage_status"),
        "active_stage_outputs": public_final.get("active_stage_outputs"),
        "ecommerce_roles": public_final.get("ecommerce_roles"),
        "claims_made": public_final.get("claims_made"),
        "publication_authorized": public_final.get("publication_authorized"),
        "image_generation_invoked": public_final.get("image_generation_invoked"),
        "artifacts_invented": public_final.get("artifacts_invented"),
        "files_written": before_project != after_project
        or command_receipt["write_like_command_detected"]
        or final.get("files_written") is not False,
        "capability_limits": public_final.get("capability_limits"),
        "command_evidence": _sanitized_command_receipt(command_receipt, mappings),
        "event_evidence": lifecycle,
        "install_tree_sha256_before": before_install["tree_sha256"],
        "install_tree_sha256_after": after_install["tree_sha256"],
        "workspace_tree_sha256_before": before_project["tree_sha256"],
        "workspace_tree_sha256_after": after_project["tree_sha256"],
        "credential_copy_mode": "0600",
        "credential_store": "file",
        "credential_copy_removed": credential_removed,
        "credential_leak_detected": execution.get("credential_material_detected", False)
        or bool(secret_leak_files),
        "evidence_errors": errors,
    }
    write_json(
        session_root / "private-receipt.json",
        {
            "codex_argv": execution["argv"],
            "raw_event_stream_sha256": execution["raw_event_stream_sha256"],
            "sanitized_event_stream_sha256": execution["sanitized_event_stream_sha256"],
            "stderr_sha256": execution["stderr_sha256"],
            "auth_copy_removed": credential_removed,
            "runtime_temp_symlink_cleanup": runtime_temp_symlink_cleanup,
            "secret_leak_files": secret_leak_files,
            "absolute_path_mappings": mappings,
            "private_artifacts": _private_artifact_receipts(session_root),
            "summary": result,
        },
        private=True,
    )
    return result


def _probe_session(
    *,
    repo_root: Path,
    run_root: Path,
    scenario: dict[str, Any],
    candidate: dict[str, Any],
    auth_source: Path,
    codex_bin: str,
    model: str,
    timeout: int,
) -> dict[str, Any]:
    session_root = run_root / scenario["id"]
    try:
        return _probe_session_impl(
            repo_root=repo_root,
            run_root=run_root,
            scenario=scenario,
            candidate=candidate,
            auth_source=auth_source,
            codex_bin=codex_bin,
            model=model,
            timeout=timeout,
        )
    finally:
        if session_root.exists():
            _remove_auth_copies(session_root)


def run_probes(
    *,
    repo_root: Path,
    audit_root: Path,
    auth_source: Path,
    codex_bin: str,
    model: str,
    timeout: int,
    candidate: dict[str, Any],
) -> Path:
    repo = _resolved(repo_root)
    executable = _resolve_codex_executable(codex_bin)
    audit = require_private_audit_root(repo, audit_root)
    require_candidate_unchanged(repo, candidate)
    scenarios = load_scenarios(repo)
    plugin_version = load_plugin_version(repo)
    execution_clock = capture_local_execution_clock()
    run_root = (
        audit
        / SKILL_NAME
        / plugin_version
        / f"probes-{execution_clock['executed_on']}-{uuid.uuid4().hex[:12]}"
    )
    run_root.mkdir(parents=True, mode=0o700)
    runtime, runtime_receipt = capture_runtime_evidence(
        repo,
        executable,
        model,
        run_root,
    )
    require_candidate_unchanged(repo, candidate)
    results = []
    for scenario in scenarios:
        require_candidate_unchanged(repo, candidate)
        results.append(
            _probe_session(
            repo_root=repo,
            run_root=run_root,
            scenario=scenario,
            candidate=candidate,
            auth_source=auth_source,
            codex_bin=executable,
            model=model,
            timeout=timeout,
        )
        )
        require_candidate_unchanged(repo, candidate)
    acceptance = _accept_probe_results(results)
    evidence = {
        "schema_version": 1,
        "executed_on": execution_clock["executed_on"],
        "runtime": runtime,
        "method": _probe_method_receipt(candidate, repo),
        "results": results,
        "acceptance": acceptance,
    }
    return _write_private_run_manifest(
        run_root=run_root,
        suite="workflow-probes",
        repo_root=repo,
        candidate=candidate,
        public_projection=evidence,
        execution_clock=execution_clock,
        auth_source=auth_source,
        runtime_receipt=runtime_receipt,
    )


def render_probe_markdown(evidence: dict[str, Any]) -> str:
    lines = [
        "# v0.2 Fresh-Agent Full-Workflow Results",
        "",
        f"Recorded {evidence['executed_on']} from three isolated read-only Codex sessions.",
        "Raw events and absolute path mappings are retained outside the repository.",
        "",
        "| Scenario | Start stage | State | Command reads | Result |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in evidence["results"]:
        result = "passed" if not row["evidence_errors"] else "failed"
        read_state = "passed" if row["command_evidence"]["required_reads_succeeded"] else "failed"
        lines.append(
            f"| `{row['id']}` | `{row['observed_start_stage']}` | "
            f"`{row['current_stage_status']}` | {read_state} | {result} |"
        )
    lines.extend(
        [
            "",
            "## Acceptance",
            "",
            f"Overall result: **{evidence['acceptance']['result']}**.",
            "",
            "A final marker was necessary but not sufficient: each row also required successful",
            "installed-file command reads, unchanged Skill/workspace hashes, and no write-like command.",
            "",
        ]
    )
    return "\n".join(lines)


def _common_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--audit-root", type=Path, required=True)
    parser.add_argument("--auth-source", type=Path, required=True)
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--timeout", type=int, default=900)


def _execution_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-tree-sha256")
    parser.add_argument("--max-agent-sessions", type=int)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight", help="validate boundaries without sessions")
    _common_parser(preflight)
    preflight.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_GENERATED_ROOT / "preflight.generated.yaml",
    )

    install = subparsers.add_parser("install-smoke", help="run or plan five install sessions")
    _common_parser(install)
    _execution_parser(install)
    install.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_GENERATED_ROOT / "install-smoke-results.generated.yaml",
    )
    install.add_argument("--allow-public-output", action="store_true")

    probes = subparsers.add_parser("probes", help="run or plan three behavior probes")
    _common_parser(probes)
    _execution_parser(probes)
    probes.add_argument(
        "--yaml-output",
        type=Path,
        default=DEFAULT_GENERATED_ROOT / "full-workflow-results.generated.yaml",
    )
    probes.add_argument(
        "--markdown-output",
        type=Path,
        default=DEFAULT_GENERATED_ROOT / "full-workflow-results.generated.md",
    )
    probes.add_argument("--allow-public-output", action="store_true")

    all_command = subparsers.add_parser("all", help="run or plan install smoke and probes")
    _common_parser(all_command)
    _execution_parser(all_command)
    all_command.add_argument(
        "--plan-yaml-output",
        type=Path,
        default=DEFAULT_GENERATED_ROOT / "task-6-dry-run.generated.yaml",
    )
    all_command.add_argument(
        "--plan-markdown-output",
        type=Path,
        default=DEFAULT_GENERATED_ROOT / "task-6-dry-run.generated.md",
    )
    all_command.add_argument(
        "--install-output",
        type=Path,
        default=DEFAULT_GENERATED_ROOT / "install-smoke-results.generated.yaml",
    )
    all_command.add_argument(
        "--probe-yaml-output",
        type=Path,
        default=DEFAULT_GENERATED_ROOT / "full-workflow-results.generated.yaml",
    )
    all_command.add_argument(
        "--probe-markdown-output",
        type=Path,
        default=DEFAULT_GENERATED_ROOT / "full-workflow-results.generated.md",
    )
    all_command.add_argument("--allow-public-output", action="store_true")

    verify = subparsers.add_parser(
        "verify", help="verify a private run manifest and project public evidence"
    )
    verify.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    verify.add_argument("--run-manifest", type=Path, required=True)
    verify.add_argument("--auth-source", type=Path, required=True)
    verify.add_argument("--codex-bin", default="codex")
    verify.add_argument("--yaml-output", type=Path, required=True)
    verify.add_argument("--markdown-output", type=Path)
    verify.add_argument("--allow-public-output", action="store_true")
    return parser


def _write_plan(
    repo_root: Path,
    yaml_output: Path,
    markdown_output: Path | None,
    model: str = MODEL,
) -> dict[str, Any]:
    repo = _resolved(repo_root)
    plan = build_dry_run_plan(
        discover_candidate(repo),
        load_scenarios(repo),
        load_plugin_version(repo),
        model,
    )
    write_yaml(require_safe_summary_path(repo, yaml_output), plan)
    if markdown_output is not None:
        write_text(require_safe_summary_path(repo, markdown_output), render_plan_markdown(plan))
    return plan


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "verify":
            repo = _resolved(args.repo_root)
            manifest_path = _resolved(args.run_manifest)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            suite = manifest.get("suite")
            evidence = verify_private_run_manifest(
                manifest_path,
                repo,
                expected_suite=suite if isinstance(suite, str) else None,
                auth_source=args.auth_source,
                codex_bin=args.codex_bin,
            )
            if args.markdown_output is not None and suite != "workflow-probes":
                raise HarnessError(
                    "--markdown-output is supported only for workflow-probes manifests"
                )
            yaml_output = require_safe_summary_path(
                repo, args.yaml_output, args.allow_public_output
            )
            markdown_output = (
                require_safe_summary_path(
                    repo, args.markdown_output, args.allow_public_output
                )
                if args.markdown_output is not None
                else None
            )
            write_yaml(yaml_output, evidence)
            if markdown_output is not None:
                write_text(markdown_output, render_probe_markdown(evidence))
            print(f"private manifest verified; public projection written to {yaml_output}")
            return 0

        preflight = _preflight(
            args.repo_root,
            args.audit_root,
            args.auth_source,
            args.codex_bin,
        )
        repo = _resolved(args.repo_root)
        if args.command == "preflight":
            output = require_safe_summary_path(repo, args.output)
            write_yaml(output, preflight)
            print(f"preflight passed; summary written to {output}")
            return 0

        if args.command == "install-smoke":
            output = require_safe_summary_path(repo, args.output, args.allow_public_output)
            candidate = preflight["candidate"]
            authorized = require_execution_authorized(
                execute=args.execute,
                dry_run=args.dry_run,
                confirmed_digest=args.confirm_tree_sha256,
                candidate=candidate,
                max_agent_sessions=args.max_agent_sessions,
                required_agent_sessions=5,
            )
            if not authorized:
                plan = build_dry_run_plan(
                    candidate, load_scenarios(repo), load_plugin_version(repo), args.model
                )
                write_yaml(output, {**plan, "behavior_probes": {"count": 0, "sessions": []}})
                print(f"plan passed; install plan written to {output}")
                return 0
            manifest_path = run_install_smoke(
                repo_root=repo,
                audit_root=args.audit_root,
                auth_source=_resolved(args.auth_source),
                codex_bin=args.codex_bin,
                model=args.model,
                timeout=args.timeout,
                candidate=candidate,
            )
            evidence = verify_private_run_manifest(
                manifest_path,
                repo,
                expected_suite="install-smoke",
                auth_source=args.auth_source,
                codex_bin=args.codex_bin,
            )
            write_yaml(output, evidence)
            return 0

        if args.command == "probes":
            yaml_output = require_safe_summary_path(
                repo, args.yaml_output, args.allow_public_output
            )
            markdown_output = require_safe_summary_path(
                repo, args.markdown_output, args.allow_public_output
            )
            candidate = preflight["candidate"]
            authorized = require_execution_authorized(
                execute=args.execute,
                dry_run=args.dry_run,
                confirmed_digest=args.confirm_tree_sha256,
                candidate=candidate,
                max_agent_sessions=args.max_agent_sessions,
                required_agent_sessions=3,
            )
            if not authorized:
                plan = build_dry_run_plan(
                    candidate, load_scenarios(repo), load_plugin_version(repo), args.model
                )
                probe_plan = {
                    **plan,
                    "install_smoke": {"count": 0, "sessions": []},
                }
                write_yaml(yaml_output, probe_plan)
                write_text(markdown_output, render_plan_markdown(probe_plan))
                print(f"plan passed; probe plan written to {yaml_output}")
                return 0
            manifest_path = run_probes(
                repo_root=repo,
                audit_root=args.audit_root,
                auth_source=_resolved(args.auth_source),
                codex_bin=args.codex_bin,
                model=args.model,
                timeout=args.timeout,
                candidate=candidate,
            )
            evidence = verify_private_run_manifest(
                manifest_path,
                repo,
                expected_suite="workflow-probes",
                auth_source=args.auth_source,
                codex_bin=args.codex_bin,
            )
            write_yaml(yaml_output, evidence)
            write_text(markdown_output, render_probe_markdown(evidence))
            return 0

        if args.command == "all":
            candidate = preflight["candidate"]
            authorized = require_execution_authorized(
                execute=args.execute,
                dry_run=args.dry_run,
                confirmed_digest=args.confirm_tree_sha256,
                candidate=candidate,
                max_agent_sessions=args.max_agent_sessions,
                required_agent_sessions=8,
            )
            if not authorized:
                _write_plan(
                    repo,
                    args.plan_yaml_output,
                    args.plan_markdown_output,
                    args.model,
                )
                print(
                    "plan passed; no Codex agent session, plugin mutation command, "
                    "or image command was invoked"
                )
                return 0
            install_output = require_safe_summary_path(
                repo, args.install_output, args.allow_public_output
            )
            probe_yaml = require_safe_summary_path(
                repo, args.probe_yaml_output, args.allow_public_output
            )
            probe_markdown = require_safe_summary_path(
                repo, args.probe_markdown_output, args.allow_public_output
            )
            install_manifest = run_install_smoke(
                repo_root=repo,
                audit_root=args.audit_root,
                auth_source=_resolved(args.auth_source),
                codex_bin=args.codex_bin,
                model=args.model,
                timeout=args.timeout,
                candidate=candidate,
            )
            install_evidence = verify_private_run_manifest(
                install_manifest,
                repo,
                expected_suite="install-smoke",
                auth_source=args.auth_source,
                codex_bin=args.codex_bin,
            )
            write_yaml(install_output, install_evidence)
            probe_manifest = run_probes(
                repo_root=repo,
                audit_root=args.audit_root,
                auth_source=_resolved(args.auth_source),
                codex_bin=args.codex_bin,
                model=args.model,
                timeout=args.timeout,
                candidate=candidate,
            )
            probe_evidence = verify_private_run_manifest(
                probe_manifest,
                repo,
                expected_suite="workflow-probes",
                auth_source=args.auth_source,
                codex_bin=args.codex_bin,
            )
            write_yaml(probe_yaml, probe_evidence)
            write_text(probe_markdown, render_probe_markdown(probe_evidence))
            return 0
    except (HarnessError, OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    raise AssertionError("unreachable command")


if __name__ == "__main__":
    raise SystemExit(main())
