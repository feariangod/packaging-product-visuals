from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

from PIL import Image
import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "examples" / "fictional-pantry-product"
SCRIPT_PATH = FIXTURE_ROOT / "build_v02_gallery.py"
TRANSFORM_ROOT = FIXTURE_ROOT / "transforms" / "v0.2" / "2026-09-09"
SPEC_PATH = TRANSFORM_ROOT / "transform-spec-2026-09-09.json"
SOURCE_PATH = FIXTURE_ROOT / "generated" / "compare-direction-a.png"
FINAL_OUTPUT_ROOT = FIXTURE_ROOT / "generated" / "v0.2" / "2026-09-09"
STALE_AUTHORIZATION_PATH = FIXTURE_ROOT / "forward-authorization-2026-09-09.yaml"
PACKAGE_IDENTITY_SHA256 = "39d1ee7e7ea63ab815eadb9667ece008f3183db388350154d4a9f70ade1ab758"

EXPECTED_READY = {
    "gallery-catalog",
    "gallery-detail",
    "gallery-specification",
    "gallery-campaign",
    "gallery-channel-variant",
}
EXPECTED_BLOCKED = {"gallery-usage", "gallery-context"}
EXPECTED_FILENAMES = {
    "gallery-catalog": "gallery-catalog-2026-09-09.png",
    "gallery-detail": "gallery-detail-2026-09-09.png",
    "gallery-specification": "gallery-specification-2026-09-09.png",
    "gallery-campaign": "gallery-campaign-2026-09-09.png",
    "gallery-channel-variant": "gallery-channel-variant-2026-09-09.png",
}
EXPECTED_FINAL_FILENAMES = {
    **EXPECTED_FILENAMES,
    "gallery-usage": "gallery-usage-2026-09-09.png",
    "gallery-context": "gallery-context-2026-09-09.png",
}
EXPECTED_ROLES = [
    "catalog",
    "detail",
    "usage",
    "specification",
    "context",
    "campaign",
    "channel-variant",
]
EXPECTED_GATE_IDS = [
    "artifact-type",
    "object-count",
    "package-geometry",
    "exact-copy",
    "invented-claims",
    "reference-role",
    "visual-hierarchy-identity",
    "product-anatomy",
    "channel-fit",
    "artifact-integrity",
    "selection-lock",
    "asset-role",
    "package-identity",
]
EXPECTED_CROSS_SET_GATE_IDS = [
    "set-completeness",
    "cross-asset-package-identity",
    "cross-asset-sku-consistency",
    "cross-asset-claims-consistency",
    "sequence-role-coverage",
    "cross-asset-channel-fit",
]
EXPECTED_PROFILE_IDS = ["full-resolution", "ecommerce-thumbnail"]


def _run(*args: object, fixture_root: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(SCRIPT_PATH)]
    if fixture_root is not None:
        command.extend(["--fixture-root", str(fixture_root)])
    command.extend(str(arg) for arg in args)
    return subprocess.run(command, text=True, capture_output=True, check=False)


def _load_module():
    spec = importlib.util.spec_from_file_location("build_v02_gallery", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ignore_committed_final_output(directory: str, names: list[str]) -> set[str]:
    if Path(directory) == FINAL_OUTPUT_ROOT.parent:
        return {FINAL_OUTPUT_ROOT.name} & set(names)
    return set()


def _copy_fixture(tmp_path: Path, name: str = "fixture") -> Path:
    copied = tmp_path / name
    shutil.copytree(
        FIXTURE_ROOT,
        copied,
        symlinks=True,
        ignore=_ignore_committed_final_output,
    )
    return copied


def _tree_digest(root: Path) -> str | None:
    if not root.exists() and not root.is_symlink():
        return None
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix().encode()
        if path.is_symlink():
            digest.update(b"L")
            digest.update(relative)
            digest.update(path.readlink().as_posix().encode())
        elif path.is_dir():
            digest.update(b"D")
            digest.update(relative)
        else:
            digest.update(b"F")
            digest.update(relative)
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _write_rgb_png(path: Path, dimensions: tuple[int, int], color: tuple[int, int, int]) -> None:
    image = Image.new("RGB", dimensions, color)
    image.save(path, format="PNG", optimize=False, compress_level=9)


def _make_final_authorization(
    tmp_path: Path, copied_fixture: Path
) -> tuple[Path, dict[str, object], dict[str, Path]]:
    external_root = tmp_path / "external-final-inputs"
    external_root.mkdir()
    plates = {
        "gallery-usage-background-plate": external_root / "usage-clean-attempt.png",
        "gallery-context-background-plate": external_root / "context-clean-attempt.png",
    }
    _write_rgb_png(plates["gallery-usage-background-plate"], (1200, 1500), (229, 226, 218))
    _write_rgb_png(plates["gallery-context-background-plate"], (1920, 1080), (215, 224, 214))
    spec_path = (
        copied_fixture
        / "transforms"
        / "v0.2"
        / "2026-09-09"
        / SPEC_PATH.name
    )
    source_sha = json.loads(spec_path.read_text(encoding="utf-8"))["source"]["sha256"]

    plate_records = []
    for role, supporting_id, dimensions in [
        ("usage", "gallery-usage-background-plate", [1200, 1500]),
        ("context", "gallery-context-background-plate", [1920, 1080]),
    ]:
        plate_path = plates[supporting_id]
        plate_records.append(
            {
                "supporting_asset_id": supporting_id,
                "role": role,
                "locator_type": "absolute_path",
                "locator": str(plate_path.resolve()),
                "sha256": module_sha256(plate_path),
                "dimensions": dimensions,
                "mode": "RGB",
                "icc_profile_present": False,
                "retained_locator": (
                    f"attempts/gallery-{role}/background-attempt-01-2026-09-09.png"
                ),
                "clean_attempt": {
                    "attempt_id": f"gallery-{role}-background-attempt-01-2026-09-09",
                    "outcome": "passed",
                    "call_count": 1,
                    "failure_class": None,
                    "provider": "test-fixture-provider",
                    "model": "test-fixture-model",
                    "executed_at_utc": "2026-09-09T02:00:00Z",
                    "prompt_sha256": ("1" if role == "usage" else "2") * 64,
                    "checks": {
                        "artifact_type": "passed",
                        "dimensions": "passed",
                        "no_packaging": "passed",
                        "no_text": "passed",
                        "placement_zone": "passed",
                    },
                },
                "provenance": {
                    "created_by": "external-image-generation",
                    "source_material": "fictional text-only background prompt",
                    "visible_trademarks": "none",
                    "embedded_private_data": False,
                    "redistribution_allowed": False,
                    "publication_allowed": False,
                    "documented_issue": "none",
                },
            }
        )

    approval_basis = (
        "Current user re-confirmed this exact local-only transform and plate package."
    )
    payload: dict[str, object] = {
        "schema_version": 1,
        "id": "public-fictional-v02-final-build-authorization-2026-09-09",
        "evidence_kind": "current-user-generation-authorization",
        "status": "passed",
        "authorization": {
            "authority": "current-user",
            "basis": approval_basis,
            "confirmed_at_utc": "2026-09-09T02:05:00Z",
            "approval_message_sha256": hashlib.sha256(
                approval_basis.encode("utf-8")
            ).hexdigest(),
        },
        "approved_scope": {
            "selection_lock_id": "fictional-pantry-selection-lock-v02",
            "ecommerce_asset_plan_id": "fictional-pantry-ecommerce-plan-v02",
            "selected_direction_id": "quiet-pantry",
            "selected_sku_ids": ["lemon-ginger", "berry-oat"],
            "required_roles": EXPECTED_ROLES,
            "source_artifact_id": "compare-direction-a",
            "source_artifact_sha256": source_sha,
            "package_identity_sha256": PACKAGE_IDENTITY_SHA256,
        },
        "transform_binding": {
            "locator": "transforms/v0.2/2026-09-09/transform-spec-2026-09-09.json",
            "sha256": module_sha256(spec_path),
        },
        "current_transform_check": {
            "checked_on": "2026-09-09",
            "observed_sha256": module_sha256(spec_path),
            "status": "match",
            "generation_authorized": True,
            "requires_new_current_user_confirmation": False,
        },
        "current_scope_status": {
            "selection_lock": "passed",
            "ecommerce_asset_plan": "passed",
            "asset_briefs": "passed",
            "ecommerce_generation": "authorized",
            "qa_delivery": "not-run",
        },
        "usage_scene_constraint": (
            "For this fictional concept, the unopened Berry Oat pouch may be shown beside one "
            "empty clear glass as a pre-opening setup. No preparation, dosage, serving, "
            "consumption, or performance instruction is defined."
        ),
        "specification_constraint": (
            "Show only the approved 240 g quantity as source-derived package pixels; do not "
            "invent dimensions, counts, callout labels, legal clearance, or production specifications."
        ),
        "qa_plan": {
            "required_gate_ids": EXPECTED_GATE_IDS,
            "cross_set_required_gate_ids": EXPECTED_CROSS_SET_GATE_IDS,
            "required_profile_ids": EXPECTED_PROFILE_IDS,
            "independent_review_required": True,
            "expected_gate_rows": 188,
        },
        "generation_budget": {
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
        },
        "background_plates": plate_records,
        "output": {
            "root": "generated/v0.2/2026-09-09",
            "overwrite": False,
            "retention_policy": "preserve",
            "publication_authorized": False,
        },
        "publication": {
            "authorized": False,
            "requires_new_current_user_confirmation": True,
        },
    }
    authorization_path = external_root / "exact-authorization.yaml"
    authorization_path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8"
    )
    return authorization_path, payload, plates


def test_default_command_is_read_only_preflight_and_does_not_create_final_output():
    assert SCRIPT_PATH.is_file()
    before = SOURCE_PATH.read_bytes()
    final_before = _tree_digest(FINAL_OUTPUT_ROOT)
    assert final_before is not None

    result = _run()

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["schema_version"] == 1
    assert report["run_date"] == "2026-09-09"
    assert report["mode"] == "preflight"
    assert report["authorization"] == "not-claimed"
    assert {row["requested_artifact_id"] for row in report["ready"]} == EXPECTED_READY
    assert {row["requested_artifact_id"] for row in report["blocked"]} == EXPECTED_BLOCKED
    assert all(row["reason"] == "required supporting plate is missing" for row in report["blocked"])
    assert _tree_digest(FINAL_OUTPUT_ROOT) == final_before
    assert SOURCE_PATH.read_bytes() == before


def test_transform_spec_is_closed_and_records_complete_reproducibility_contract():
    assert SPEC_PATH.is_file()
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))

    assert set(spec) == {
        "final_output_root",
        "graph",
        "id",
        "masks",
        "rendering",
        "run_date",
        "schema_version",
        "source",
    }
    assert spec["schema_version"] == 1
    assert spec["run_date"] == "2026-09-09"
    assert spec["final_output_root"] == "generated/v0.2/2026-09-09"
    assert set(spec["source"]) == {
        "dimensions",
        "icc_profile_present",
        "icc_profile_sha256",
        "locator",
        "mode",
        "sha256",
    }
    assert spec["source"]["dimensions"] == [1448, 1086]
    assert spec["source"]["mode"] == "RGB"
    assert spec["source"]["icc_profile_present"] is False
    assert spec["source"]["icc_profile_sha256"] is None
    assert set(spec["rendering"]) == {
        "package_resize_filter",
        "png",
        "source_color_interpretation",
    }
    assert spec["rendering"]["package_resize_filter"] == "none"
    assert spec["rendering"]["png"] == {
        "compress_level": 9,
        "format": "PNG",
        "optimize": False,
    }

    mask_ids = {mask["id"] for mask in spec["masks"]}
    assert mask_ids == {"lemon-ginger-mask", "berry-oat-mask"}
    for mask in spec["masks"]:
        assert set(mask) == {
            "crop_rect",
            "dimensions",
            "feather_radius",
            "id",
            "locator",
            "mode",
            "polygon",
            "sha256",
            "sku_id",
        }
        assert mask["mode"] == "L"
        assert mask["dimensions"] == [1448, 1086]
        assert mask["feather_radius"] == 1.0
        assert len(mask["crop_rect"]) == 4
        assert len(mask["polygon"]) >= 8

    graph = {row["requested_artifact_id"]: row for row in spec["graph"]}
    assert set(graph) == EXPECTED_READY | EXPECTED_BLOCKED
    assert graph["gallery-catalog"]["required_input_asset_ids"] == ["compare-direction-a"]
    assert graph["gallery-detail"]["parent_asset_brief_id"] == "gallery-catalog"
    assert graph["gallery-specification"]["parent_asset_brief_id"] == "gallery-detail"
    assert graph["gallery-channel-variant"]["parent_asset_brief_id"] == "gallery-catalog"
    assert graph["gallery-usage"]["blocked_without"] == ["gallery-usage-background-plate"]
    assert graph["gallery-context"]["blocked_without"] == ["gallery-context-background-plate"]
    assert {key for key, row in graph.items() if row["preview_enabled"]} == EXPECTED_READY

    campaign = graph["gallery-campaign"]
    campaign_positions = {
        placement["id"]: placement["destination_xy"]
        for placement in campaign["placements"]
    }
    assert campaign_positions == {
        "campaign-lemon-ginger-primary": [610, 175],
        "campaign-berry-oat-primary": [1240, 45],
    }
    assert campaign["decorations"] == [
        {
            "type": "rectangle",
            "box": [540, 120, 1240, 1080],
            "fill": [239, 196, 70],
        },
        {
            "type": "rectangle",
            "box": [1170, 0, 1920, 1010],
            "fill": [173, 65, 63],
        },
    ]
    assert min(position[0] for position in campaign_positions.values()) >= 600

    channel_variant = graph["gallery-channel-variant"]
    assert channel_variant["canvas"]["background"] == [244, 239, 230]
    assert channel_variant["decorations"] == []
    assert channel_variant["shadow"] is None


def test_masks_are_hash_bound_reviewable_8_bit_grayscale_assets():
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    for record in spec["masks"]:
        path = FIXTURE_ROOT / record["locator"]
        assert path.is_file() and not path.is_symlink()
        with Image.open(path) as image:
            image.load()
            assert image.mode == "L"
            assert image.size == (1448, 1086)
            assert image.info.get("icc_profile") is None
            extrema = image.getextrema()
            assert extrema[0] == 0
            assert extrema[1] == 255
            assert len(set(image.tobytes())) > 2
        assert module_sha256(path) == record["sha256"]


def test_preview_build_is_atomic_and_reports_five_deterministic_assets(tmp_path):
    output = tmp_path / "preview"
    final_before = _tree_digest(FINAL_OUTPUT_ROOT)
    assert final_before is not None

    result = _run("--build-preview", output)

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert output.is_dir()
    assert not list(tmp_path.glob(".preview.staging-*"))
    assert report == json.loads((output / "preview-report.json").read_text(encoding="utf-8"))
    assert report["mode"] == "preview"
    assert report["authorization"] == "not-claimed"
    assert report["final_output_root_written"] is False
    artifacts = {row["requested_artifact_id"]: row for row in report["artifacts"]}
    assert set(artifacts) == EXPECTED_READY | EXPECTED_BLOCKED
    assert {key for key, row in artifacts.items() if row["status"] == "preview"} == EXPECTED_READY
    assert {key for key, row in artifacts.items() if row["status"] == "blocked"} == EXPECTED_BLOCKED
    for artifact_id, filename in EXPECTED_FILENAMES.items():
        row = artifacts[artifact_id]
        path = output / filename
        assert row["locator"] == filename
        assert path.is_file() and not path.is_symlink()
        assert module_sha256(path) == row["sha256"]
        with Image.open(path) as image:
            image.load()
            assert list(image.size) == row["dimensions"]
            assert image.mode == "RGB"
            assert image.info.get("icc_profile") is None
        for check in row["package_face_checks"]:
            assert check["source_opaque_sha256"] == check["output_opaque_sha256"]
            assert check["opaque_pixel_count"] > 1000
    assert _tree_digest(FINAL_OUTPUT_ROOT) == final_before


def test_verify_preview_detects_an_internal_package_face_edit(tmp_path):
    output = tmp_path / "preview"
    assert _run("--build-preview", output).returncode == 0
    report = json.loads((output / "preview-report.json").read_text(encoding="utf-8"))
    campaign = next(
        row for row in report["artifacts"] if row["requested_artifact_id"] == "gallery-campaign"
    )
    point = campaign["package_face_checks"][0]["sample_output_point"]
    path = output / campaign["locator"]
    with Image.open(path) as image:
        edited = image.convert("RGB")
    edited.putpixel(tuple(point), (255, 0, 255))
    edited.save(path, format="PNG", optimize=False, compress_level=9)

    result = _run("--verify-preview", output)

    assert result.returncode != 0
    assert "package face" in result.stderr.lower()


def test_wrong_source_hash_and_unknown_spec_field_fail_before_output(tmp_path):
    payload = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    payload["source"]["sha256"] = "0" * 64
    wrong_hash = tmp_path / "wrong-hash.json"
    wrong_hash.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "wrong-hash-output"

    result = _run("--spec", wrong_hash, "--build-preview", output)

    assert result.returncode != 0
    assert "source sha256 mismatch" in result.stderr.lower()
    assert not output.exists()
    assert not list(tmp_path.glob(".wrong-hash-output.staging-*"))

    payload = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    payload["unexpected"] = True
    unknown = tmp_path / "unknown.json"
    unknown.write_text(json.dumps(payload), encoding="utf-8")
    result = _run("--spec", unknown)
    assert result.returncode != 0
    assert "unexpected" in result.stderr.lower()


def test_symlink_inputs_reserved_outputs_and_existing_outputs_are_rejected(tmp_path):
    copied = _copy_fixture(tmp_path)
    copied_spec = copied / "transforms" / "v0.2" / "2026-09-09" / SPEC_PATH.name
    payload = json.loads(copied_spec.read_text(encoding="utf-8"))
    mask_path = copied / payload["masks"][0]["locator"]
    real_mask = mask_path.with_name("real-mask.png")
    mask_path.rename(real_mask)
    mask_path.symlink_to(real_mask.name)
    output = tmp_path / "symlink-output"

    result = _run(
        "--spec",
        copied_spec,
        "--build-preview",
        output,
        fixture_root=copied,
    )

    assert result.returncode != 0
    assert "symlink" in result.stderr.lower()
    assert not output.exists()

    reserved = copied / "generated" / "v0.2" / "2026-09-09"
    result = _run(
        "--spec",
        copied_spec,
        "--build-preview",
        reserved,
        fixture_root=copied,
    )
    assert result.returncode != 0
    assert "unsafe preview output" in result.stderr.lower()

    existing = tmp_path / "existing"
    existing.mkdir()
    sentinel = existing / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    result = _run("--build-preview", existing)
    assert result.returncode != 0
    assert "existing output" in result.stderr.lower()
    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_runtime_render_failure_removes_staging_and_leaves_no_partial_output(
    tmp_path, monkeypatch
):
    module = _load_module()
    output = tmp_path / "preview"
    real_render = module.render_preview_asset
    calls = 0

    def fail_after_first(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected render failure")
        return real_render(*args, **kwargs)

    monkeypatch.setattr(module, "render_preview_asset", fail_after_first)

    try:
        module.build_preview(SPEC_PATH, FIXTURE_ROOT, output)
    except RuntimeError as error:
        assert str(error) == "injected render failure"
    else:
        raise AssertionError("expected injected render failure")

    assert not output.exists()
    assert not list(tmp_path.glob(".preview.staging-*"))


def test_preview_report_is_closed_and_static_fields_are_rebuilt(tmp_path):
    pristine = tmp_path / "pristine"
    assert _run("--build-preview", pristine).returncode == 0

    variants = {
        "top-extra": lambda payload: payload.__setitem__("publication_status", "published"),
        "written-final-root": lambda payload: payload.__setitem__(
            "final_output_root_written", True
        ),
        "artifact-extra": lambda payload: payload["artifacts"][0].__setitem__(
            "publication_status", "published"
        ),
        "artifact-status": lambda payload: payload["artifacts"][0].__setitem__(
            "status", "approved"
        ),
        "duplicate-artifact": lambda payload: payload["artifacts"].append(
            dict(payload["artifacts"][0])
        ),
    }
    for name, mutate in variants.items():
        output = tmp_path / name
        shutil.copytree(pristine, output)
        report_path = output / "preview-report.json"
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        mutate(payload)
        report_path.write_text(json.dumps(payload), encoding="utf-8")

        result = _run("--verify-preview", output)

        assert result.returncode != 0, name
        assert "preview report" in result.stderr.lower(), (name, result.stderr)


def test_verifier_rejects_blocked_artifacts_and_any_unexpected_output_entry(tmp_path):
    pristine = tmp_path / "pristine"
    assert _run("--build-preview", pristine).returncode == 0
    catalog = pristine / EXPECTED_FILENAMES["gallery-catalog"]

    variants = {
        "blocked-usage": lambda output: shutil.copyfile(
            catalog, output / "gallery-usage-2026-09-09.png"
        ),
        "extra-json": lambda output: (output / "extra.json").write_text(
            "{}", encoding="utf-8"
        ),
        "extra-directory": lambda output: (output / "extra").mkdir(),
    }
    for name, add_entry in variants.items():
        output = tmp_path / name
        shutil.copytree(pristine, output)
        add_entry(output)

        result = _run("--verify-preview", output)

        assert result.returncode != 0, name
        assert "unexpected preview output entry" in result.stderr.lower(), (
            name,
            result.stderr,
        )


def test_reports_use_public_relative_locators_only(tmp_path):
    result = _run()
    assert result.returncode == 0, result.stderr
    preflight_report = json.loads(result.stdout)
    assert preflight_report["transform_spec"]["locator"] == SPEC_PATH.relative_to(
        FIXTURE_ROOT
    ).as_posix()
    assert preflight_report["final_output_root"] == "generated/v0.2/2026-09-09"

    output = tmp_path / "preview"
    assert _run("--build-preview", output).returncode == 0
    preview_report = json.loads((output / "preview-report.json").read_text(encoding="utf-8"))
    assert preview_report["transform_spec"]["locator"] == SPEC_PATH.relative_to(
        FIXTURE_ROOT
    ).as_posix()
    assert not any(
        value.startswith("/")
        for value in _all_string_values(preflight_report) + _all_string_values(preview_report)
    )


def test_inputs_are_rechecked_before_atomic_preview_commit(tmp_path, monkeypatch):
    module = _load_module()
    copied = _copy_fixture(tmp_path)
    copied_spec = copied / "transforms" / "v0.2" / "2026-09-09" / SPEC_PATH.name
    copied_source = copied / "generated" / "compare-direction-a.png"
    output = tmp_path / "preview"
    real_render = module.render_preview_asset
    calls = 0

    def replace_source_after_first_render(*args, **kwargs):
        nonlocal calls
        image = real_render(*args, **kwargs)
        calls += 1
        if calls == 1:
            with Image.open(copied_source) as opened:
                changed = opened.convert("RGB")
            pixel = changed.getpixel((0, 0))
            changed.putpixel((0, 0), tuple(255 - channel for channel in pixel))
            changed.save(copied_source, format="PNG", optimize=False, compress_level=9)
        return image

    monkeypatch.setattr(module, "render_preview_asset", replace_source_after_first_render)

    with pytest.raises(module.ContractError, match="source.*changed during preview build"):
        module.build_preview(copied_spec, copied, output)

    assert not output.exists()
    assert not list(tmp_path.glob(".preview.staging-*"))


def test_final_build_requires_a_new_exact_current_transform_authorization(tmp_path):
    module = _load_module()
    assert module.TRUSTED_FINAL_AUTHORIZATION_SHA256 is None
    final_before = _tree_digest(FINAL_OUTPUT_ROOT)
    assert final_before is not None
    missing = _run("--build-final")

    assert missing.returncode != 0
    assert "--authorization is required" in missing.stderr.lower()
    assert _tree_digest(FINAL_OUTPUT_ROOT) == final_before

    stale = _run("--build-final", "--authorization", STALE_AUTHORIZATION_PATH)

    assert stale.returncode != 0
    assert "trusted authorization sha256 is not configured" in stale.stderr.lower()
    assert _tree_digest(FINAL_OUTPUT_ROOT) == final_before

    copied = _copy_fixture(tmp_path)
    copied_spec = copied / "transforms" / "v0.2" / "2026-09-09" / SPEC_PATH.name
    authorization_path, _, _ = _make_final_authorization(tmp_path, copied)
    exact_but_untrusted = _run(
        "--spec",
        copied_spec,
        "--build-final",
        "--authorization",
        authorization_path,
        fixture_root=copied,
    )
    assert exact_but_untrusted.returncode != 0
    assert "trusted authorization sha256 is not configured" in exact_but_untrusted.stderr.lower()
    assert not (copied / "generated" / "v0.2" / "2026-09-09").exists()


def test_authorized_final_build_is_atomic_draft_and_preserves_external_plates(tmp_path):
    module = _load_module()
    final_before = _tree_digest(FINAL_OUTPUT_ROOT)
    assert final_before is not None
    copied = _copy_fixture(tmp_path)
    copied_spec = copied / "transforms" / "v0.2" / "2026-09-09" / SPEC_PATH.name
    preview = tmp_path / "preview"
    assert _run(
        "--spec", copied_spec, "--build-preview", preview, fixture_root=copied
    ).returncode == 0
    authorization_path, authorization, plates = _make_final_authorization(tmp_path, copied)

    report = module.build_final(
        copied_spec,
        copied,
        authorization_path,
        trusted_authorization_sha256=module_sha256(authorization_path),
    )

    output = copied / "generated" / "v0.2" / "2026-09-09"
    assert output.is_dir() and not output.is_symlink()
    assert not list(output.parent.glob(".2026-09-09.staging-*"))
    assert {path.name for path in output.iterdir()} == {
        *EXPECTED_FINAL_FILENAMES.values(),
        "attempts",
        "final-build-report.json",
        "plate-provenance.json",
    }
    assert report == json.loads((output / "final-build-report.json").read_text(encoding="utf-8"))
    assert report["mode"] == "authorized-final-build"
    assert report["status"] == "draft"
    assert report["selected_direction_id"] == "quiet-pantry"
    assert report["package_identity_sha256"] == PACKAGE_IDENTITY_SHA256
    assert report["authorization"] == {
        "approval_message_sha256": authorization["authorization"][
            "approval_message_sha256"
        ],
        "authority": "current-user",
        "confirmed_at_utc": "2026-09-09T02:05:00Z",
        "id": authorization["id"],
        "sha256": module_sha256(authorization_path),
    }
    assert report["publication_authorized"] is False
    assert report["final_output_root"] == "generated/v0.2/2026-09-09"
    assert report["final_output_root_written"] is True
    assert report["call_budget"] == {
        "actual_total_calls": 2,
        "maximum_calls_per_background_plate": 2,
        "maximum_total_calls": 4,
    }
    assert report["qa"]["status"] == "pending-independent-review"
    assert report["qa"]["independent_review_required"] is True
    assert report["qa"]["expected_gate_rows"] == 188
    assert report["qa"]["actual_gate_rows"] == 188
    assert len(report["qa"]["rows"]) == 188
    assert len({row["row_id"] for row in report["qa"]["rows"]}) == 188
    assert all(row["status"] == "unverified" for row in report["qa"]["rows"])
    assert all(row["evidence"] is None for row in report["qa"]["rows"])
    assert all(row["reviewer_id"] is None for row in report["qa"]["rows"])

    artifacts = {row["requested_artifact_id"]: row for row in report["artifacts"]}
    assert set(artifacts) == set(EXPECTED_FINAL_FILENAMES)
    assert all(row["status"] == "draft" for row in artifacts.values())
    assert all(row["review_status"] == "pending-independent-qa" for row in artifacts.values())
    for artifact_id, filename in EXPECTED_FINAL_FILENAMES.items():
        path = output / filename
        assert path.is_file() and not path.is_symlink()
        assert module_sha256(path) == artifacts[artifact_id]["sha256"]
        assert all(
            check["source_opaque_sha256"] == check["output_opaque_sha256"]
            for check in artifacts[artifact_id]["package_face_checks"]
        )
    for artifact_id in EXPECTED_READY:
        assert (output / EXPECTED_FINAL_FILENAMES[artifact_id]).read_bytes() == (
            preview / EXPECTED_FINAL_FILENAMES[artifact_id]
        ).read_bytes()
    assert artifacts["gallery-usage"]["dimensions"] == [1200, 1500]
    assert artifacts["gallery-context"]["dimensions"] == [1920, 1080]

    provenance_path = output / "plate-provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    assert report["plate_provenance"] == {
        "locator": "plate-provenance.json",
        "sha256": module_sha256(provenance_path),
    }
    provenance_rows = {row["supporting_asset_id"]: row for row in provenance["plates"]}
    for supporting_id, source_path in plates.items():
        row = provenance_rows[supporting_id]
        retained = output / row["retained_locator"]
        assert retained.read_bytes() == source_path.read_bytes()
        assert row["sha256"] == module_sha256(retained)
    assert not any(
        value.startswith("/")
        for value in _all_string_values(report) + _all_string_values(provenance)
    )
    assert _tree_digest(FINAL_OUTPUT_ROOT) == final_before


@pytest.mark.parametrize(
    ("case", "expected_error"),
    [
        ("authority", "authority"),
        ("direction", "selected_direction_id"),
        ("roles", "required_roles"),
        ("source", "source_artifact_sha256"),
        ("package-identity", "package_identity_sha256"),
        ("transform", "transform binding sha256 mismatch"),
        ("qa-rows", "expected_gate_rows"),
        ("output", "output.root"),
        ("publication", "publication"),
        ("call-budget", "maximum_total_calls"),
        ("plate-call-count", "call_count"),
    ],
)
def test_final_build_rejects_any_authorization_scope_or_budget_drift(
    tmp_path, case, expected_error
):
    module = _load_module()
    copied = _copy_fixture(tmp_path)
    copied_spec = copied / "transforms" / "v0.2" / "2026-09-09" / SPEC_PATH.name
    authorization_path, payload, _ = _make_final_authorization(tmp_path, copied)
    mutated = copy.deepcopy(payload)
    if case == "authority":
        mutated["authorization"]["authority"] = "assistant"
    elif case == "direction":
        mutated["approved_scope"]["selected_direction_id"] = "bright-counter"
    elif case == "roles":
        mutated["approved_scope"]["required_roles"] = EXPECTED_ROLES[:-1]
    elif case == "source":
        mutated["approved_scope"]["source_artifact_sha256"] = "0" * 64
    elif case == "package-identity":
        mutated["approved_scope"]["package_identity_sha256"] = "0" * 64
    elif case == "transform":
        mutated["transform_binding"]["sha256"] = "0" * 64
    elif case == "qa-rows":
        mutated["qa_plan"]["expected_gate_rows"] = 187
    elif case == "output":
        mutated["output"]["root"] = "generated/v0.2/surprise"
    elif case == "publication":
        mutated["publication"]["authorized"] = True
    elif case == "call-budget":
        mutated["generation_budget"]["maximum_total_calls"] = 5
    elif case == "plate-call-count":
        mutated["background_plates"][0]["clean_attempt"]["call_count"] = 3
    authorization_path.write_text(
        yaml.safe_dump(mutated, sort_keys=False, allow_unicode=False), encoding="utf-8"
    )

    with pytest.raises(module.ContractError, match=expected_error):
        module.build_final(
            copied_spec,
            copied,
            authorization_path,
            trusted_authorization_sha256=module_sha256(authorization_path),
        )
    output = copied / "generated" / "v0.2" / "2026-09-09"
    assert not output.exists()
    assert not list(copied.rglob(".*.staging-*"))


def test_final_build_binds_the_whole_record_and_exact_user_message(tmp_path):
    module = _load_module()
    copied = _copy_fixture(tmp_path)
    copied_spec = copied / "transforms" / "v0.2" / "2026-09-09" / SPEC_PATH.name
    authorization_path, payload, _ = _make_final_authorization(tmp_path, copied)

    with pytest.raises(module.ContractError, match="authorization record sha256 mismatch"):
        module.build_final(
            copied_spec,
            copied,
            authorization_path,
            trusted_authorization_sha256="0" * 64,
        )

    payload["authorization"]["approval_message_sha256"] = "b" * 64
    authorization_path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8"
    )
    with pytest.raises(module.ContractError, match="approval_message_sha256 mismatch"):
        module.build_final(
            copied_spec,
            copied,
            authorization_path,
            trusted_authorization_sha256=module_sha256(authorization_path),
        )
    assert not (copied / "generated" / "v0.2" / "2026-09-09").exists()


def test_background_plates_must_be_external_to_the_repository_not_only_fixture(tmp_path):
    module = _load_module()
    simulated_repo = tmp_path / "simulated-repo"
    simulated_repo.mkdir()
    (simulated_repo / ".git").mkdir()
    copied = simulated_repo / "examples" / "fictional-pantry-product"
    copied.parent.mkdir(parents=True)
    shutil.copytree(
        FIXTURE_ROOT,
        copied,
        symlinks=True,
        ignore=_ignore_committed_final_output,
    )
    copied_spec = copied / "transforms" / "v0.2" / "2026-09-09" / SPEC_PATH.name
    authorization_path, payload, plates = _make_final_authorization(tmp_path, copied)
    internal_plate = simulated_repo / "private-inputs" / "usage.png"
    internal_plate.parent.mkdir()
    shutil.copyfile(plates["gallery-usage-background-plate"], internal_plate)
    payload["background_plates"][0]["locator"] = str(internal_plate.resolve())
    payload["background_plates"][0]["sha256"] = module_sha256(internal_plate)
    authorization_path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8"
    )

    with pytest.raises(module.ContractError, match="must be repo-external"):
        module.build_final(
            copied_spec,
            copied,
            authorization_path,
            trusted_authorization_sha256=module_sha256(authorization_path),
        )
    assert not (copied / "generated" / "v0.2" / "2026-09-09").exists()


def test_plate_provenance_rejects_path_like_provider_or_model(tmp_path):
    module = _load_module()
    copied = _copy_fixture(tmp_path)
    copied_spec = copied / "transforms" / "v0.2" / "2026-09-09" / SPEC_PATH.name
    authorization_path, payload, _ = _make_final_authorization(tmp_path, copied)
    payload["background_plates"][0]["clean_attempt"]["provider"] = (
        "/private/provider-state"
    )
    authorization_path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8"
    )

    with pytest.raises(module.ContractError, match="provider must be a non-path identifier"):
        module.build_final(
            copied_spec,
            copied,
            authorization_path,
            trusted_authorization_sha256=module_sha256(authorization_path),
        )
    assert not (copied / "generated" / "v0.2" / "2026-09-09").exists()


@pytest.mark.parametrize("case", ["inside-fixture", "symlink", "wrong-hash", "existing-output"])
def test_final_build_rejects_unsafe_plates_and_existing_output(tmp_path, case):
    module = _load_module()
    case_root = tmp_path / case
    case_root.mkdir()
    copied = _copy_fixture(case_root)
    copied_spec = copied / "transforms" / "v0.2" / "2026-09-09" / SPEC_PATH.name
    authorization_path, payload, plates = _make_final_authorization(case_root, copied)
    if case == "inside-fixture":
        internal = copied / "usage-clean-attempt.png"
        shutil.copyfile(plates["gallery-usage-background-plate"], internal)
        payload["background_plates"][0]["locator"] = str(internal.resolve())
        payload["background_plates"][0]["sha256"] = module_sha256(internal)
    elif case == "symlink":
        symlink = case_root / "usage-symlink.png"
        symlink.symlink_to(plates["gallery-usage-background-plate"])
        payload["background_plates"][0]["locator"] = str(symlink)
    elif case == "wrong-hash":
        payload["background_plates"][0]["sha256"] = "0" * 64
    else:
        output = copied / "generated" / "v0.2" / "2026-09-09"
        output.mkdir(parents=True)
        (output / "keep.txt").write_text("keep", encoding="utf-8")
    authorization_path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8"
    )

    with pytest.raises(module.ContractError):
        module.build_final(
            copied_spec,
            copied,
            authorization_path,
            trusted_authorization_sha256=module_sha256(authorization_path),
        )
    output = copied / "generated" / "v0.2" / "2026-09-09"
    if case == "existing-output":
        assert (output / "keep.txt").read_text(encoding="utf-8") == "keep"
    else:
        assert not output.exists()
    assert not list(copied.rglob(".*.staging-*"))


def test_final_render_failure_removes_staging_and_final_root(tmp_path, monkeypatch):
    module = _load_module()
    copied = _copy_fixture(tmp_path)
    copied_spec = copied / "transforms" / "v0.2" / "2026-09-09" / SPEC_PATH.name
    authorization_path, _, _ = _make_final_authorization(tmp_path, copied)
    real_render = module.render_final_asset
    calls = 0

    def fail_after_first(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected final render failure")
        return real_render(*args, **kwargs)

    monkeypatch.setattr(module, "render_final_asset", fail_after_first)

    with pytest.raises(RuntimeError, match="injected final render failure"):
        module.build_final(
            copied_spec,
            copied,
            authorization_path,
            trusted_authorization_sha256=module_sha256(authorization_path),
        )

    output = copied / "generated" / "v0.2" / "2026-09-09"
    assert not output.exists()
    assert not list(copied.rglob(".*.staging-*"))


def test_final_inputs_are_rechecked_before_atomic_commit(tmp_path, monkeypatch):
    module = _load_module()
    copied = _copy_fixture(tmp_path)
    copied_spec = copied / "transforms" / "v0.2" / "2026-09-09" / SPEC_PATH.name
    authorization_path, _, plates = _make_final_authorization(tmp_path, copied)
    usage_plate = plates["gallery-usage-background-plate"]
    real_render = module.render_final_asset
    calls = 0

    def replace_plate_after_first_render(*args, **kwargs):
        nonlocal calls
        image = real_render(*args, **kwargs)
        calls += 1
        if calls == 1:
            with Image.open(usage_plate) as opened:
                changed = opened.convert("RGB")
            changed.putpixel((0, 0), (0, 0, 0))
            changed.save(usage_plate, format="PNG", optimize=False, compress_level=9)
        return image

    monkeypatch.setattr(module, "render_final_asset", replace_plate_after_first_render)

    with pytest.raises(module.ContractError, match="background plate.*changed during final build"):
        module.build_final(
            copied_spec,
            copied,
            authorization_path,
            trusted_authorization_sha256=module_sha256(authorization_path),
        )

    output = copied / "generated" / "v0.2" / "2026-09-09"
    assert not output.exists()
    assert not list(copied.rglob(".*.staging-*"))


def test_final_atomic_commit_never_replaces_a_racing_output_directory(tmp_path, monkeypatch):
    module = _load_module()
    copied = _copy_fixture(tmp_path)
    copied_spec = copied / "transforms" / "v0.2" / "2026-09-09" / SPEC_PATH.name
    authorization_path, _, _ = _make_final_authorization(tmp_path, copied)
    output = copied / "generated" / "v0.2" / "2026-09-09"
    real_assert_snapshot = module._assert_snapshot_unchanged

    def create_racing_output(snapshot, phase):
        real_assert_snapshot(snapshot, phase)
        if phase == "final build":
            output.mkdir()
            (output / "keep.txt").write_text("racing output", encoding="utf-8")

    monkeypatch.setattr(module, "_assert_snapshot_unchanged", create_racing_output)

    with pytest.raises(module.ContractError, match="atomic final output already exists"):
        module.build_final(
            copied_spec,
            copied,
            authorization_path,
            trusted_authorization_sha256=module_sha256(authorization_path),
        )

    assert (output / "keep.txt").read_text(encoding="utf-8") == "racing output"
    assert {path.name for path in output.iterdir()} == {"keep.txt"}
    assert not list(output.parent.glob(".2026-09-09.staging-*"))


@pytest.mark.parametrize("existing_kind", ["empty-directory", "nonempty-directory", "file"])
def test_atomic_rename_preserves_every_existing_destination(tmp_path, existing_kind):
    module = _load_module()
    source = tmp_path / "staging"
    source.mkdir()
    (source / "new.txt").write_text("new", encoding="utf-8")
    destination = tmp_path / "published"
    if existing_kind == "file":
        destination.write_text("keep", encoding="utf-8")
    else:
        destination.mkdir()
        if existing_kind == "nonempty-directory":
            (destination / "keep.txt").write_text("keep", encoding="utf-8")
    before = _tree_digest(tmp_path)

    with pytest.raises(module.ContractError, match="atomic final output already exists"):
        module._atomic_rename_no_replace(source, destination)

    assert _tree_digest(tmp_path) == before


def test_windows_atomic_rename_uses_native_no_replace_without_loading_libc(tmp_path, monkeypatch):
    module = _load_module()
    calls = []
    monkeypatch.setattr(module, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(module.os, "rename", lambda source, destination: calls.append((source, destination)))

    def reject_libc(*args, **kwargs):
        pytest.fail("Windows rename must not load a POSIX library")

    monkeypatch.setattr(module.ctypes, "CDLL", reject_libc)
    source, destination = tmp_path / "staging", tmp_path / "published"
    module._atomic_rename_no_replace(source, destination)

    assert calls == [(source, destination)]


def module_sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _all_string_values(value: object) -> list[str]:
    if isinstance(value, dict):
        return [item for child in value.values() for item in _all_string_values(child)]
    if isinstance(value, list):
        return [item for child in value for item in _all_string_values(child)]
    return [value] if isinstance(value, str) else []
