#!/usr/bin/env python3
"""Validate and build the fictional v0.2 deterministic gallery transforms.

The default command is deliberately read-only. Preview rendering is available only
through an explicit output directory outside the public fixture root. A final local
build additionally requires an exact current-user authorization record and remains
draft pending independent QA; this module never authorizes publication.
"""

from __future__ import annotations

import argparse
import ctypes
import errno
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
from typing import Any
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFilter
import yaml


RUN_DATE = "2026-09-09"
DEFAULT_SPEC = Path("transforms/v0.2/2026-09-09/transform-spec-2026-09-09.json")
AUTHORIZATION = "not-claimed"
BLOCKED_REASON = "required supporting plate is missing"
FINAL_STATUS = "draft"
FINAL_REVIEW_STATUS = "pending-independent-qa"
FINAL_AUTHORIZATION_ID = "public-fictional-v02-final-build-authorization-2026-09-09"
# Set only after the current user re-confirms the complete post-review record.
TRUSTED_FINAL_AUTHORIZATION_SHA256: str | None = None
SELECTION_LOCK_ID = "fictional-pantry-selection-lock-v02"
ECOMMERCE_ASSET_PLAN_ID = "fictional-pantry-ecommerce-plan-v02"
SELECTED_DIRECTION_ID = "quiet-pantry"
SELECTED_SKU_IDS = ["lemon-ginger", "berry-oat"]
SOURCE_ARTIFACT_ID = "compare-direction-a"
PACKAGE_IDENTITY_SHA256 = "39d1ee7e7ea63ab815eadb9667ece008f3183db388350154d4a9f70ade1ab758"
REQUIRED_ROLES = [
    "catalog",
    "detail",
    "usage",
    "specification",
    "context",
    "campaign",
    "channel-variant",
]
DETERMINISTIC_ROLES = [
    "catalog",
    "detail",
    "specification",
    "campaign",
    "channel-variant",
]
BACKGROUND_PLATE_ROLES = ["usage", "context"]
REQUIRED_GATE_IDS = [
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
CROSS_SET_GATE_IDS = [
    "set-completeness",
    "cross-asset-package-identity",
    "cross-asset-sku-consistency",
    "cross-asset-claims-consistency",
    "sequence-role-coverage",
    "cross-asset-channel-fit",
]
PROFILE_IDS = ["full-resolution", "ecommerce-thumbnail"]
EXPECTED_QA_ROWS = 188
USAGE_SCENE_CONSTRAINT = (
    "For this fictional concept, the unopened Berry Oat pouch may be shown beside one "
    "empty clear glass as a pre-opening setup. No preparation, dosage, serving, "
    "consumption, or performance instruction is defined."
)
SPECIFICATION_CONSTRAINT = (
    "Show only the approved 240 g quantity as source-derived package pixels; do not "
    "invent dimensions, counts, callout labels, legal clearance, or production specifications."
)

ROOT_KEYS = {
    "final_output_root",
    "graph",
    "id",
    "masks",
    "rendering",
    "run_date",
    "schema_version",
    "source",
}
SOURCE_KEYS = {
    "dimensions",
    "icc_profile_present",
    "icc_profile_sha256",
    "locator",
    "mode",
    "sha256",
}
MASK_KEYS = {
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
RENDERING_KEYS = {
    "package_resize_filter",
    "png",
    "source_color_interpretation",
}
PNG_KEYS = {"compress_level", "format", "optimize"}
GRAPH_KEYS = {
    "blocked_without",
    "canvas",
    "crop_rect",
    "decorations",
    "derived_insets",
    "face_check_mask_ids",
    "final_filename",
    "operation",
    "parent_asset_brief_id",
    "placements",
    "preview_enabled",
    "requested_artifact_id",
    "required_input_asset_ids",
    "role",
    "shadow",
}
CANVAS_KEYS = {"background", "dimensions", "mode"}
PLACEMENT_KEYS = {
    "affine_matrix",
    "destination_xy",
    "id",
    "mask_crop_rect",
    "mask_id",
    "resize_filter",
    "source_asset_id",
    "source_crop_rect",
}
INSET_KEYS = {
    "border_color",
    "border_width",
    "destination_rect",
    "id",
    "resize_filter",
    "source_asset_id",
    "source_crop_rect",
}
SHADOW_KEYS = {"blur_radius", "color", "offset", "opacity"}
REPORT_ROOT_KEYS = {
    "artifacts",
    "authorization",
    "final_output_root",
    "final_output_root_written",
    "masks",
    "mode",
    "run_date",
    "schema_version",
    "source",
    "transform_spec",
}
REPORT_TRANSFORM_SPEC_KEYS = {"locator", "sha256"}
REPORT_SOURCE_KEYS = {"locator", "sha256"}
REPORT_MASK_KEYS = {"id", "locator", "sha256"}
REPORT_PREVIEW_ARTIFACT_KEYS = {
    "dimensions",
    "icc_profile_present",
    "input_bindings",
    "locator",
    "mode",
    "package_face_checks",
    "requested_artifact_id",
    "role",
    "sha256",
    "status",
}
REPORT_BLOCKED_ARTIFACT_KEYS = {
    "dimensions",
    "input_bindings",
    "locator",
    "missing_input_asset_ids",
    "mode",
    "package_face_checks",
    "reason",
    "requested_artifact_id",
    "role",
    "sha256",
    "status",
}
REPORT_INPUT_BINDING_KEYS = {"asset_id", "sha256", "status"}
REPORT_FACE_CHECK_KEYS = {
    "mask_id",
    "opaque_pixel_count",
    "output_opaque_sha256",
    "output_rect",
    "sample_output_point",
    "source_asset_id",
    "source_opaque_sha256",
    "source_rect",
}
AUTH_ROOT_KEYS = {
    "approved_scope",
    "authorization",
    "background_plates",
    "current_scope_status",
    "current_transform_check",
    "evidence_kind",
    "generation_budget",
    "id",
    "output",
    "publication",
    "qa_plan",
    "schema_version",
    "specification_constraint",
    "status",
    "transform_binding",
    "usage_scene_constraint",
}
AUTHORIZATION_KEYS = {
    "approval_message_sha256",
    "authority",
    "basis",
    "confirmed_at_utc",
}
APPROVED_SCOPE_KEYS = {
    "ecommerce_asset_plan_id",
    "package_identity_sha256",
    "required_roles",
    "selected_direction_id",
    "selected_sku_ids",
    "selection_lock_id",
    "source_artifact_id",
    "source_artifact_sha256",
}
TRANSFORM_BINDING_KEYS = {"locator", "sha256"}
CURRENT_TRANSFORM_CHECK_KEYS = {
    "checked_on",
    "generation_authorized",
    "observed_sha256",
    "requires_new_current_user_confirmation",
    "status",
}
CURRENT_SCOPE_STATUS_KEYS = {
    "asset_briefs",
    "ecommerce_asset_plan",
    "ecommerce_generation",
    "qa_delivery",
    "selection_lock",
}
QA_PLAN_KEYS = {
    "cross_set_required_gate_ids",
    "expected_gate_rows",
    "independent_review_required",
    "required_gate_ids",
    "required_profile_ids",
}
GENERATION_BUDGET_KEYS = {
    "deterministic_roles",
    "external_background_plate_roles",
    "maximum_calls_per_background_plate",
    "maximum_total_calls",
    "paid_calls_allowed",
}
AUTH_OUTPUT_KEYS = {
    "overwrite",
    "publication_authorized",
    "retention_policy",
    "root",
}
PUBLICATION_KEYS = {"authorized", "requires_new_current_user_confirmation"}
BACKGROUND_PLATE_KEYS = {
    "clean_attempt",
    "dimensions",
    "icc_profile_present",
    "locator",
    "locator_type",
    "mode",
    "provenance",
    "retained_locator",
    "role",
    "sha256",
    "supporting_asset_id",
}
CLEAN_ATTEMPT_KEYS = {
    "attempt_id",
    "call_count",
    "checks",
    "executed_at_utc",
    "failure_class",
    "model",
    "outcome",
    "prompt_sha256",
    "provider",
}
PLATE_CHECK_KEYS = {
    "artifact_type",
    "dimensions",
    "no_packaging",
    "no_text",
    "placement_zone",
}
PROVENANCE_KEYS = {
    "created_by",
    "documented_issue",
    "embedded_private_data",
    "publication_allowed",
    "redistribution_allowed",
    "source_material",
    "visible_trademarks",
}

GRAPH_ORDER = [
    "gallery-catalog",
    "gallery-detail",
    "gallery-usage",
    "gallery-specification",
    "gallery-context",
    "gallery-campaign",
    "gallery-channel-variant",
]
EXPECTED_GRAPH = {
    "gallery-catalog": {
        "role": "catalog",
        "parent": None,
        "inputs": ["compare-direction-a"],
        "preview": True,
        "blocked": [],
        "operation": "identity_copy",
        "dimensions": [1448, 1086],
    },
    "gallery-detail": {
        "role": "detail",
        "parent": "gallery-catalog",
        "inputs": ["gallery-catalog"],
        "preview": True,
        "blocked": [],
        "operation": "direct_crop",
        "dimensions": [720, 900],
    },
    "gallery-usage": {
        "role": "usage",
        "parent": "gallery-catalog",
        "inputs": ["gallery-catalog", "gallery-usage-background-plate"],
        "preview": False,
        "blocked": ["gallery-usage-background-plate"],
        "operation": "blocked_composite",
        "dimensions": [1200, 1500],
    },
    "gallery-specification": {
        "role": "specification",
        "parent": "gallery-detail",
        "inputs": ["gallery-detail"],
        "preview": True,
        "blocked": [],
        "operation": "composite",
        "dimensions": [1200, 1200],
    },
    "gallery-context": {
        "role": "context",
        "parent": "gallery-catalog",
        "inputs": ["gallery-catalog", "gallery-context-background-plate"],
        "preview": False,
        "blocked": ["gallery-context-background-plate"],
        "operation": "blocked_composite",
        "dimensions": [1920, 1080],
    },
    "gallery-campaign": {
        "role": "campaign",
        "parent": "gallery-catalog",
        "inputs": ["gallery-catalog"],
        "preview": True,
        "blocked": [],
        "operation": "composite",
        "dimensions": [1920, 1080],
    },
    "gallery-channel-variant": {
        "role": "channel-variant",
        "parent": "gallery-catalog",
        "inputs": ["gallery-catalog"],
        "preview": True,
        "blocked": [],
        "operation": "composite",
        "dimensions": [1200, 1200],
    },
}


class ContractError(ValueError):
    """Raised when the closed transform contract or an artifact is invalid."""


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _expect_mapping(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{context} must be an object")
    return value


def _expect_keys(value: Any, expected: set[str], context: str) -> dict[str, Any]:
    mapping = _expect_mapping(value, context)
    actual = set(mapping)
    extra = sorted(actual - expected)
    missing = sorted(expected - actual)
    if extra:
        raise ContractError(f"{context} has unexpected field(s): {', '.join(extra)}")
    if missing:
        raise ContractError(f"{context} is missing field(s): {', '.join(missing)}")
    return mapping


def _expect_list(value: Any, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise ContractError(f"{context} must be an array")
    return value


def _expect_int(value: Any, context: str, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractError(f"{context} must be an integer")
    if minimum is not None and value < minimum:
        raise ContractError(f"{context} must be at least {minimum}")
    return value


def _expect_number(value: Any, context: str, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{context} must be numeric")
    number = float(value)
    if number < minimum:
        raise ContractError(f"{context} must be at least {minimum}")
    return number


def _expect_string(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise ContractError(f"{context} must be a non-empty string")
    return value


def _expect_non_path_identifier(value: Any, context: str) -> str:
    identifier = _expect_string(value, context)
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    if (
        identifier[0] not in allowed[:-3]
        or any(character not in allowed for character in identifier)
        or any(ord(character) < 32 for character in identifier)
    ):
        raise ContractError(f"{context} must be a non-path identifier")
    return identifier


def _expect_sha256(value: Any, context: str) -> str:
    digest = _expect_string(value, context)
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ContractError(f"{context} must be a lowercase sha256 digest")
    return digest


def _expect_bool(value: Any, expected: bool, context: str) -> None:
    if value is not expected:
        raise ContractError(f"{context} must be {str(expected).lower()}")


def _expect_exact(value: Any, expected: Any, context: str) -> None:
    if type(value) is not type(expected) or value != expected:
        raise ContractError(f"{context} mismatch: expected {expected!r}, got {value!r}")


def _expect_run_timestamp(value: Any, context: str) -> str:
    timestamp = _expect_string(value, context)
    if not timestamp.startswith(f"{RUN_DATE}T") or not timestamp.endswith("Z"):
        raise ContractError(f"{context} must be a UTC timestamp on {RUN_DATE}")
    return timestamp


def _dimensions(value: Any, context: str) -> tuple[int, int]:
    values = _expect_list(value, context)
    if len(values) != 2:
        raise ContractError(f"{context} must contain width and height")
    return (
        _expect_int(values[0], f"{context}[0]", 1),
        _expect_int(values[1], f"{context}[1]", 1),
    )


def _color(value: Any, context: str) -> tuple[int, int, int]:
    values = _expect_list(value, context)
    if len(values) != 3:
        raise ContractError(f"{context} must contain three RGB values")
    channels = tuple(_expect_int(channel, context, 0) for channel in values)
    if any(channel > 255 for channel in channels):
        raise ContractError(f"{context} RGB values must be at most 255")
    return channels  # type: ignore[return-value]


def _rect(value: Any, bounds: tuple[int, int], context: str) -> tuple[int, int, int, int]:
    values = _expect_list(value, context)
    if len(values) != 4:
        raise ContractError(f"{context} must contain four integer coordinates")
    left, top, right, bottom = (
        _expect_int(item, f"{context}[{index}]", 0) for index, item in enumerate(values)
    )
    if right <= left or bottom <= top:
        raise ContractError(f"{context} must have positive width and height")
    if right > bounds[0] or bottom > bounds[1]:
        raise ContractError(f"{context} exceeds {bounds[0]}x{bounds[1]} bounds")
    return left, top, right, bottom


def _xy(value: Any, context: str) -> tuple[int, int]:
    values = _expect_list(value, context)
    if len(values) != 2:
        raise ContractError(f"{context} must contain x and y")
    return (
        _expect_int(values[0], f"{context}[0]", 0),
        _expect_int(values[1], f"{context}[1]", 0),
    )


def _safe_locator(locator: Any, context: str) -> Path:
    if not isinstance(locator, str) or not locator:
        raise ContractError(f"{context} must be a non-empty string")
    pure = PurePosixPath(locator)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise ContractError(f"{context} must be a safe fixture-relative locator")
    return Path(*pure.parts)


def _contains_path(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _repository_root(fixture_root: Path) -> Path:
    resolved_fixture = Path(fixture_root).resolve(strict=True)
    for candidate in (resolved_fixture, *resolved_fixture.parents):
        if (candidate / ".git").exists() or (
            (candidate / "pyproject.toml").is_file()
            and (candidate / ".codex-plugin" / "plugin.json").is_file()
        ):
            return candidate
    return resolved_fixture


def _reject_symlink_chain(path: Path, stop: Path | None, context: str) -> None:
    current = path
    while True:
        if current.is_symlink():
            raise ContractError(f"{context} must not use a symlink: {current}")
        if stop is not None and current == stop:
            break
        if current.parent == current:
            break
        current = current.parent


def _checked_fixture_file(fixture_root: Path, locator: Any, context: str) -> Path:
    relative = _safe_locator(locator, context)
    path = fixture_root / relative
    _reject_symlink_chain(path, fixture_root, context)
    if not path.is_file():
        raise ContractError(f"{context} does not exist: {path}")
    resolved_root = fixture_root.resolve(strict=True)
    resolved_path = path.resolve(strict=True)
    if not _contains_path(resolved_root, resolved_path):
        raise ContractError(f"{context} escapes the fixture root")
    return path


def _load_image(path: Path) -> Image.Image:
    return _load_image_bytes(path.read_bytes(), str(path))


def _load_image_bytes(data: bytes, context: str) -> Image.Image:
    try:
        opened_source = BytesIO(data)
        opened = Image.open(opened_source)
        opened.load()
    except (OSError, ValueError) as error:
        raise ContractError(f"cannot decode {context} as an image: {error}") from error
    image = opened.copy()
    opened.close()
    return image


def _icc_state(image: Image.Image) -> tuple[bool, str | None]:
    profile = image.info.get("icc_profile")
    if profile is None:
        return False, None
    if isinstance(profile, str):
        profile = profile.encode("utf-8")
    return True, sha256(profile).hexdigest()


def _rebuild_mask(record: dict[str, Any]) -> Image.Image:
    size = _dimensions(record["dimensions"], f"mask {record['id']} dimensions")
    image = Image.new("L", size, 0)
    points = [tuple(point) for point in record["polygon"]]
    ImageDraw.Draw(image).polygon(points, fill=255)
    return image.filter(ImageFilter.GaussianBlur(float(record["feather_radius"])))


def _validate_source(
    spec: dict[str, Any], fixture_root: Path
) -> tuple[Path, Image.Image]:
    source = _expect_keys(spec["source"], SOURCE_KEYS, "source")
    path = _checked_fixture_file(fixture_root, source["locator"], "source locator")
    source_bytes = path.read_bytes()
    actual_file_hash = sha256(source_bytes).hexdigest()
    if actual_file_hash != source["sha256"]:
        raise ContractError(
            f"source sha256 mismatch: expected {source['sha256']}, got {actual_file_hash}"
        )
    image = _load_image_bytes(source_bytes, "source")
    expected_size = _dimensions(source["dimensions"], "source dimensions")
    if image.size != expected_size:
        raise ContractError(f"source dimensions mismatch: expected {expected_size}, got {image.size}")
    if image.mode != source["mode"]:
        raise ContractError(f"source mode mismatch: expected {source['mode']}, got {image.mode}")
    actual_present, actual_hash = _icc_state(image)
    if actual_present is not source["icc_profile_present"]:
        raise ContractError("source ICC profile presence mismatch")
    if actual_hash != source["icc_profile_sha256"]:
        raise ContractError("source ICC profile sha256 mismatch")
    if image.mode != "RGB" or actual_present:
        raise ContractError("source must be 8-bit RGB with no embedded ICC profile")
    return path, image


def _validate_masks(
    spec: dict[str, Any], fixture_root: Path, source_size: tuple[int, int]
) -> tuple[dict[str, Path], dict[str, Image.Image]]:
    records = _expect_list(spec["masks"], "masks")
    if len(records) != 2:
        raise ContractError("masks must contain exactly two named-object records")
    paths: dict[str, Path] = {}
    images: dict[str, Image.Image] = {}
    for index, raw_record in enumerate(records):
        record = _expect_keys(raw_record, MASK_KEYS, f"masks[{index}]")
        mask_id = record["id"]
        if not isinstance(mask_id, str) or not mask_id or mask_id in paths:
            raise ContractError(f"masks[{index}].id must be a unique non-empty string")
        if not isinstance(record["sku_id"], str) or not record["sku_id"]:
            raise ContractError(f"masks[{index}].sku_id must be a non-empty string")
        if record["mode"] != "L":
            raise ContractError(f"mask {mask_id} mode must be L")
        if _dimensions(record["dimensions"], f"mask {mask_id} dimensions") != source_size:
            raise ContractError(f"mask {mask_id} dimensions must match the source")
        _expect_number(record["feather_radius"], f"mask {mask_id} feather_radius")
        _rect(record["crop_rect"], source_size, f"mask {mask_id} crop_rect")
        polygon = _expect_list(record["polygon"], f"mask {mask_id} polygon")
        if len(polygon) < 8:
            raise ContractError(f"mask {mask_id} polygon must contain at least eight points")
        for point_index, point in enumerate(polygon):
            x, y = _xy(point, f"mask {mask_id} polygon[{point_index}]")
            if x >= source_size[0] or y >= source_size[1]:
                raise ContractError(f"mask {mask_id} polygon point exceeds source bounds")
        path = _checked_fixture_file(fixture_root, record["locator"], f"mask {mask_id} locator")
        mask_bytes = path.read_bytes()
        actual_file_hash = sha256(mask_bytes).hexdigest()
        if actual_file_hash != record["sha256"]:
            raise ContractError(
                f"mask {mask_id} sha256 mismatch: expected {record['sha256']}, got {actual_file_hash}"
            )
        actual = _load_image_bytes(mask_bytes, f"mask {mask_id}")
        if actual.mode != "L" or actual.size != source_size:
            raise ContractError(f"mask {mask_id} must be source-sized 8-bit grayscale")
        if _icc_state(actual)[0]:
            raise ContractError(f"mask {mask_id} must not contain an ICC profile")
        rebuilt = _rebuild_mask(record)
        if actual.tobytes() != rebuilt.tobytes():
            raise ContractError(f"mask {mask_id} pixels do not match its polygon and feather radius")
        paths[mask_id] = path
        images[mask_id] = actual
    if set(paths) != {"lemon-ginger-mask", "berry-oat-mask"}:
        raise ContractError("mask IDs must be lemon-ginger-mask and berry-oat-mask")
    return paths, images


def _validate_shadow(value: Any, context: str) -> None:
    if value is None:
        return
    shadow = _expect_keys(value, SHADOW_KEYS, context)
    _xy(shadow["offset"], f"{context}.offset")
    _expect_number(shadow["blur_radius"], f"{context}.blur_radius")
    opacity = _expect_int(shadow["opacity"], f"{context}.opacity", 0)
    if opacity > 255:
        raise ContractError(f"{context}.opacity must be at most 255")
    _color(shadow["color"], f"{context}.color")


def _validate_decorations(value: Any, canvas: tuple[int, int], context: str) -> None:
    for index, raw_decoration in enumerate(_expect_list(value, context)):
        decoration = _expect_mapping(raw_decoration, f"{context}[{index}]")
        decoration_type = decoration.get("type")
        if decoration_type == "rectangle":
            rectangle = _expect_keys(
                decoration, {"box", "fill", "type"}, f"{context}[{index}]"
            )
            _rect(rectangle["box"], canvas, f"{context}[{index}].box")
            _color(rectangle["fill"], f"{context}[{index}].fill")
        elif decoration_type == "line":
            line = _expect_keys(
                decoration, {"fill", "points", "type", "width"}, f"{context}[{index}]"
            )
            points = _expect_list(line["points"], f"{context}[{index}].points")
            if len(points) != 4:
                raise ContractError(f"{context}[{index}].points must contain four coordinates")
            x1, y1, x2, y2 = (
                _expect_int(item, f"{context}[{index}].points", 0) for item in points
            )
            if x1 > canvas[0] or x2 > canvas[0] or y1 > canvas[1] or y2 > canvas[1]:
                raise ContractError(f"{context}[{index}].points exceed canvas bounds")
            _color(line["fill"], f"{context}[{index}].fill")
            _expect_int(line["width"], f"{context}[{index}].width", 1)
        else:
            raise ContractError(f"{context}[{index}] has unsupported type {decoration_type!r}")


def _validate_graph(spec: dict[str, Any], source_size: tuple[int, int]) -> None:
    graph = _expect_list(spec["graph"], "graph")
    if [row.get("requested_artifact_id") for row in graph if isinstance(row, dict)] != GRAPH_ORDER:
        raise ContractError("graph must use the closed seven-role topological order")

    rows: dict[str, dict[str, Any]] = {}
    asset_dimensions: dict[str, tuple[int, int]] = {"compare-direction-a": source_size}
    for index, raw_row in enumerate(graph):
        row = _expect_keys(raw_row, GRAPH_KEYS, f"graph[{index}]")
        artifact_id = row["requested_artifact_id"]
        if artifact_id not in EXPECTED_GRAPH or artifact_id in rows:
            raise ContractError(f"graph[{index}] has unexpected requested_artifact_id {artifact_id!r}")
        expected = EXPECTED_GRAPH[artifact_id]
        checks = {
            "role": expected["role"],
            "parent_asset_brief_id": expected["parent"],
            "required_input_asset_ids": expected["inputs"],
            "preview_enabled": expected["preview"],
            "blocked_without": expected["blocked"],
            "operation": expected["operation"],
        }
        for field, expected_value in checks.items():
            if row[field] != expected_value:
                raise ContractError(
                    f"graph {artifact_id} {field} mismatch: expected {expected_value!r}"
                )
        if not isinstance(row["final_filename"], str) or Path(row["final_filename"]).name != row[
            "final_filename"
        ]:
            raise ContractError(f"graph {artifact_id} final_filename must be a basename")
        expected_filename = f"{artifact_id}-{RUN_DATE}.png"
        if row["final_filename"] != expected_filename:
            raise ContractError(
                f"graph {artifact_id} final_filename must be {expected_filename}"
            )
        canvas = _expect_keys(row["canvas"], CANVAS_KEYS, f"graph {artifact_id} canvas")
        dimensions = _dimensions(canvas["dimensions"], f"graph {artifact_id} canvas dimensions")
        if list(dimensions) != expected["dimensions"]:
            raise ContractError(f"graph {artifact_id} canvas dimensions mismatch")
        if canvas["mode"] != "RGB":
            raise ContractError(f"graph {artifact_id} canvas mode must be RGB")
        _color(canvas["background"], f"graph {artifact_id} canvas background")
        rows[artifact_id] = row
        asset_dimensions[artifact_id] = dimensions

    mask_ids = {record["id"] for record in spec["masks"]}
    for artifact_id in GRAPH_ORDER:
        row = rows[artifact_id]
        canvas_dimensions = asset_dimensions[artifact_id]
        crop_rect = row["crop_rect"]
        if row["operation"] == "direct_crop":
            parent = row["parent_asset_brief_id"]
            rect = _rect(crop_rect, asset_dimensions[parent], f"graph {artifact_id} crop_rect")
            if (rect[2] - rect[0], rect[3] - rect[1]) != canvas_dimensions:
                raise ContractError(f"graph {artifact_id} crop_rect must equal its canvas dimensions")
        elif crop_rect is not None:
            raise ContractError(f"graph {artifact_id} crop_rect must be null")

        face_masks = _expect_list(
            row["face_check_mask_ids"], f"graph {artifact_id} face_check_mask_ids"
        )
        if not face_masks or not set(face_masks).issubset(mask_ids):
            raise ContractError(f"graph {artifact_id} face_check_mask_ids are invalid")

        placements = _expect_list(row["placements"], f"graph {artifact_id} placements")
        for placement_index, raw_placement in enumerate(placements):
            context = f"graph {artifact_id} placements[{placement_index}]"
            placement = _expect_keys(raw_placement, PLACEMENT_KEYS, context)
            if not isinstance(placement["id"], str) or not placement["id"]:
                raise ContractError(f"{context}.id must be a non-empty string")
            source_asset_id = placement["source_asset_id"]
            if source_asset_id not in asset_dimensions:
                raise ContractError(f"{context}.source_asset_id is not in the input graph")
            if source_asset_id not in row["required_input_asset_ids"]:
                raise ContractError(f"{context}.source_asset_id is not a required input")
            source_rect = _rect(
                placement["source_crop_rect"], asset_dimensions[source_asset_id], f"{context}.source_crop_rect"
            )
            if placement["mask_id"] not in mask_ids:
                raise ContractError(f"{context}.mask_id is unknown")
            mask_rect = _rect(placement["mask_crop_rect"], source_size, f"{context}.mask_crop_rect")
            source_crop_size = (source_rect[2] - source_rect[0], source_rect[3] - source_rect[1])
            mask_crop_size = (mask_rect[2] - mask_rect[0], mask_rect[3] - mask_rect[1])
            if source_crop_size != mask_crop_size:
                raise ContractError(f"{context} source and mask crop sizes differ")
            destination = _xy(placement["destination_xy"], f"{context}.destination_xy")
            if destination[0] + source_crop_size[0] > canvas_dimensions[0] or destination[
                1
            ] + source_crop_size[1] > canvas_dimensions[1]:
                raise ContractError(f"{context} placement exceeds canvas bounds")
            if placement["affine_matrix"] != [1, 0, 0, 0, 1, 0]:
                raise ContractError(f"{context}.affine_matrix must be identity")
            if placement["resize_filter"] != "none":
                raise ContractError(f"{context}.resize_filter must be none")

        insets = _expect_list(row["derived_insets"], f"graph {artifact_id} derived_insets")
        for inset_index, raw_inset in enumerate(insets):
            context = f"graph {artifact_id} derived_insets[{inset_index}]"
            inset = _expect_keys(raw_inset, INSET_KEYS, context)
            source_asset_id = inset["source_asset_id"]
            if source_asset_id not in row["required_input_asset_ids"]:
                raise ContractError(f"{context}.source_asset_id is not a required input")
            _rect(inset["source_crop_rect"], asset_dimensions[source_asset_id], f"{context}.source_crop_rect")
            _rect(inset["destination_rect"], canvas_dimensions, f"{context}.destination_rect")
            if inset["resize_filter"] != "Pillow.Image.Resampling.LANCZOS":
                raise ContractError(f"{context}.resize_filter must be Pillow.Image.Resampling.LANCZOS")
            _color(inset["border_color"], f"{context}.border_color")
            _expect_int(inset["border_width"], f"{context}.border_width", 0)

        _validate_decorations(
            row["decorations"], canvas_dimensions, f"graph {artifact_id} decorations"
        )
        _validate_shadow(row["shadow"], f"graph {artifact_id} shadow")
        if not placements and row["shadow"] is not None:
            raise ContractError(f"graph {artifact_id} shadow must be null without placements")


def _load_contract_bundle(
    spec_path: Path, fixture_root: Path
) -> tuple[
    dict[str, Any],
    dict[str, Image.Image],
    dict[str, Image.Image],
    list[dict[str, Any]],
]:
    fixture_root = Path(fixture_root)
    _reject_symlink_chain(fixture_root, None, "fixture root")
    if not fixture_root.is_dir():
        raise ContractError(f"fixture root does not exist: {fixture_root}")
    spec_path = Path(spec_path)
    _reject_symlink_chain(spec_path, None, "transform spec")
    if not spec_path.is_file():
        raise ContractError(f"transform spec does not exist: {spec_path}")
    try:
        spec_bytes = spec_path.read_bytes()
        raw = json.loads(spec_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContractError(f"cannot read transform spec: {error}") from error
    spec = _expect_keys(raw, ROOT_KEYS, "transform spec")
    if spec["schema_version"] != 1:
        raise ContractError("transform spec schema_version must be 1")
    if spec["run_date"] != RUN_DATE:
        raise ContractError(f"transform spec run_date must be {RUN_DATE}")
    if not isinstance(spec["id"], str) or not spec["id"]:
        raise ContractError("transform spec id must be a non-empty string")
    if spec["final_output_root"] != f"generated/v0.2/{RUN_DATE}":
        raise ContractError("transform spec final_output_root is not the reserved v0.2 root")
    rendering = _expect_keys(spec["rendering"], RENDERING_KEYS, "rendering")
    if rendering["package_resize_filter"] != "none":
        raise ContractError("rendering.package_resize_filter must be none")
    if not isinstance(rendering["source_color_interpretation"], str) or not rendering[
        "source_color_interpretation"
    ]:
        raise ContractError("rendering.source_color_interpretation must be explicit")
    png = _expect_keys(rendering["png"], PNG_KEYS, "rendering.png")
    if png != {"format": "PNG", "optimize": False, "compress_level": 9}:
        raise ContractError("rendering.png must use the closed PNG encoder settings")
    source_path, source_image = _validate_source(spec, fixture_root)
    mask_paths, mask_images = _validate_masks(spec, fixture_root, source_image.size)
    _validate_graph(spec, source_image.size)
    snapshot = [
        {
            "label": "transform spec",
            "path": spec_path,
            "sha256": sha256(spec_bytes).hexdigest(),
        },
        {
            "label": "source",
            "path": source_path,
            "sha256": spec["source"]["sha256"],
        },
    ]
    snapshot.extend(
        {
            "label": f"mask {record['id']}",
            "path": mask_paths[record["id"]],
            "sha256": record["sha256"],
        }
        for record in spec["masks"]
    )
    return (
        spec,
        {"compare-direction-a": source_image},
        mask_images,
        snapshot,
    )


def load_contract(spec_path: Path, fixture_root: Path) -> dict[str, Any]:
    return _load_contract_bundle(spec_path, fixture_root)[0]


def _snapshot_hash(snapshot: list[dict[str, Any]], label: str) -> str:
    for record in snapshot:
        if record["label"] == label:
            return record["sha256"]
    raise ContractError(f"missing input snapshot for {label}")


def _assert_snapshot_unchanged(snapshot: list[dict[str, Any]], phase: str) -> None:
    for record in snapshot:
        label = record["label"]
        path = Path(record["path"])
        try:
            _reject_symlink_chain(path, None, label)
            current_hash = file_sha256(path)
        except (ContractError, OSError) as error:
            raise ContractError(f"{label} changed during {phase}: {error}") from error
        if current_hash != record["sha256"]:
            raise ContractError(
                f"{label} changed during {phase}: expected {record['sha256']}, got {current_hash}"
            )


def _draw_decorations(image: Image.Image, decorations: list[dict[str, Any]]) -> None:
    draw = ImageDraw.Draw(image)
    for decoration in decorations:
        if decoration["type"] == "rectangle":
            draw.rectangle(tuple(decoration["box"]), fill=tuple(decoration["fill"]))
        else:
            draw.line(
                tuple(decoration["points"]),
                fill=tuple(decoration["fill"]),
                width=decoration["width"],
            )


def _shadow_mask(
    canvas_size: tuple[int, int],
    alpha: Image.Image,
    destination: tuple[int, int],
    shadow: dict[str, Any],
) -> Image.Image:
    mask = Image.new("L", canvas_size, 0)
    offset = tuple(shadow["offset"])
    mask.paste(alpha, (destination[0] + offset[0], destination[1] + offset[1]))
    mask = mask.filter(ImageFilter.GaussianBlur(float(shadow["blur_radius"])))
    opacity = int(shadow["opacity"])
    return mask.point(lambda value: (value * opacity + 127) // 255)


def render_preview_asset(
    row: dict[str, Any],
    asset_images: dict[str, Image.Image],
    mask_images: dict[str, Image.Image],
) -> Image.Image:
    """Render one preview-enabled graph row using only recorded operations."""

    operation = row["operation"]
    if operation == "identity_copy":
        image = asset_images[row["required_input_asset_ids"][0]].copy()
    elif operation == "direct_crop":
        parent = asset_images[row["parent_asset_brief_id"]]
        image = parent.crop(tuple(row["crop_rect"]))
    elif operation == "composite":
        canvas = row["canvas"]
        image = Image.new("RGB", tuple(canvas["dimensions"]), tuple(canvas["background"]))
        _draw_decorations(image, row["decorations"])
        for placement in row["placements"]:
            source = asset_images[placement["source_asset_id"]]
            source_crop = source.crop(tuple(placement["source_crop_rect"]))
            alpha = mask_images[placement["mask_id"]].crop(tuple(placement["mask_crop_rect"]))
            destination = tuple(placement["destination_xy"])
            if row["shadow"] is not None:
                shadow = _shadow_mask(image.size, alpha, destination, row["shadow"])
                image.paste(tuple(row["shadow"]["color"]), (0, 0, *image.size), shadow)
            image.paste(source_crop, destination, alpha)
        draw = ImageDraw.Draw(image)
        for inset in row["derived_insets"]:
            source = asset_images[inset["source_asset_id"]]
            source_crop = source.crop(tuple(inset["source_crop_rect"]))
            destination = tuple(inset["destination_rect"])
            resized = source_crop.resize(
                (destination[2] - destination[0], destination[3] - destination[1]),
                Image.Resampling.LANCZOS,
            )
            image.paste(resized, destination[:2])
            if inset["border_width"]:
                draw.rectangle(
                    destination,
                    outline=tuple(inset["border_color"]),
                    width=inset["border_width"],
                )
    else:
        raise ContractError(f"cannot render operation {operation!r} as a deterministic preview")

    expected_size = tuple(row["canvas"]["dimensions"])
    if image.mode != "RGB" or image.size != expected_size:
        raise ContractError(
            f"rendered {row['requested_artifact_id']} as {image.mode} {image.size}, expected RGB {expected_size}"
        )
    return Image.frombytes("RGB", image.size, image.tobytes())


def render_final_asset(
    row: dict[str, Any],
    asset_images: dict[str, Image.Image],
    mask_images: dict[str, Image.Image],
) -> Image.Image:
    """Render one authorized final row without changing package pixels."""

    if row["operation"] != "blocked_composite":
        return render_preview_asset(row, asset_images, mask_images)
    supporting_ids = row["blocked_without"]
    if len(supporting_ids) != 1 or supporting_ids[0] not in asset_images:
        raise ContractError(
            f"{row['requested_artifact_id']} is missing its authorized background plate"
        )
    image = asset_images[supporting_ids[0]].copy()
    expected_size = tuple(row["canvas"]["dimensions"])
    if image.mode != "RGB" or image.size != expected_size:
        raise ContractError(
            f"background plate for {row['requested_artifact_id']} must be RGB {expected_size}"
        )
    _draw_decorations(image, row["decorations"])
    for placement in row["placements"]:
        source = asset_images[placement["source_asset_id"]]
        source_crop = source.crop(tuple(placement["source_crop_rect"]))
        alpha = mask_images[placement["mask_id"]].crop(tuple(placement["mask_crop_rect"]))
        destination = tuple(placement["destination_xy"])
        if row["shadow"] is not None:
            shadow = _shadow_mask(image.size, alpha, destination, row["shadow"])
            image.paste(tuple(row["shadow"]["color"]), (0, 0, *image.size), shadow)
        image.paste(source_crop, destination, alpha)
    draw = ImageDraw.Draw(image)
    for inset in row["derived_insets"]:
        source = asset_images[inset["source_asset_id"]]
        source_crop = source.crop(tuple(inset["source_crop_rect"]))
        destination = tuple(inset["destination_rect"])
        resized = source_crop.resize(
            (destination[2] - destination[0], destination[3] - destination[1]),
            Image.Resampling.LANCZOS,
        )
        image.paste(resized, destination[:2])
        if inset["border_width"]:
            draw.rectangle(
                destination,
                outline=tuple(inset["border_color"]),
                width=inset["border_width"],
            )
    return Image.frombytes("RGB", image.size, image.tobytes())


def _opaque_hash_pair(
    source: Image.Image, output: Image.Image, alpha: Image.Image
) -> tuple[str, str, int, tuple[int, int]]:
    if source.size != output.size or source.size != alpha.size:
        raise ContractError("package face comparison inputs have different dimensions")
    source_bytes = source.convert("RGB").tobytes()
    output_bytes = output.convert("RGB").tobytes()
    alpha_bytes = alpha.convert("L").tobytes()
    source_payload = bytearray()
    output_payload = bytearray()
    sample_index: int | None = None
    count = 0
    for index, value in enumerate(alpha_bytes):
        if value == 255:
            if sample_index is None:
                sample_index = index
            start = index * 3
            source_payload.extend(source_bytes[start : start + 3])
            output_payload.extend(output_bytes[start : start + 3])
            count += 1
    if sample_index is None:
        raise ContractError("package face mask has no fully opaque pixels")
    return (
        sha256(source_payload).hexdigest(),
        sha256(output_payload).hexdigest(),
        count,
        (sample_index % source.width, sample_index // source.width),
    )


def compute_package_face_checks(
    row: dict[str, Any],
    output: Image.Image,
    asset_images: dict[str, Image.Image],
    mask_images: dict[str, Image.Image],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    operation = row["operation"]
    comparisons: list[tuple[str, str, tuple[int, int, int, int], tuple[int, int, int, int], tuple[int, int]]] = []
    if operation == "identity_copy":
        source_id = row["required_input_asset_ids"][0]
        for mask_id in row["face_check_mask_ids"]:
            width, height = output.size
            comparisons.append((mask_id, source_id, (0, 0, width, height), (0, 0, width, height), (0, 0)))
    elif operation == "direct_crop":
        source_id = row["parent_asset_brief_id"]
        crop = tuple(row["crop_rect"])
        comparisons.append(
            (
                row["face_check_mask_ids"][0],
                source_id,
                crop,
                crop,
                (0, 0),
            )
        )
    elif operation in {"composite", "blocked_composite"}:
        for placement in row["placements"]:
            comparisons.append(
                (
                    placement["mask_id"],
                    placement["source_asset_id"],
                    tuple(placement["source_crop_rect"]),
                    tuple(placement["mask_crop_rect"]),
                    tuple(placement["destination_xy"]),
                )
            )

    for mask_id, source_id, source_rect, mask_rect, destination in comparisons:
        source_crop = asset_images[source_id].crop(source_rect)
        alpha = mask_images[mask_id].crop(mask_rect)
        output_rect = (
            destination[0],
            destination[1],
            destination[0] + source_crop.width,
            destination[1] + source_crop.height,
        )
        output_crop = output.crop(output_rect)
        source_hash, output_hash, count, local_sample = _opaque_hash_pair(
            source_crop, output_crop, alpha
        )
        checks.append(
            {
                "mask_id": mask_id,
                "source_asset_id": source_id,
                "source_rect": list(source_rect),
                "output_rect": list(output_rect),
                "source_opaque_sha256": source_hash,
                "output_opaque_sha256": output_hash,
                "opaque_pixel_count": count,
                "sample_output_point": [
                    destination[0] + local_sample[0],
                    destination[1] + local_sample[1],
                ],
            }
        )
    return checks


def _png_bytes(image: Image.Image, rendering: dict[str, Any]) -> bytes:
    clean = Image.frombytes("RGB", image.size, image.convert("RGB").tobytes())
    buffer = BytesIO()
    clean.save(
        buffer,
        format=rendering["png"]["format"],
        optimize=rendering["png"]["optimize"],
        compress_level=rendering["png"]["compress_level"],
    )
    return buffer.getvalue()


def _spec_and_inputs(
    spec_path: Path, fixture_root: Path
) -> tuple[
    dict[str, Any],
    dict[str, Image.Image],
    dict[str, Image.Image],
    list[dict[str, Any]],
]:
    return _load_contract_bundle(Path(spec_path), Path(fixture_root))


def _load_authorization_bundle(
    authorization_path: Path,
    fixture_root: Path,
    spec: dict[str, Any],
    input_snapshot: list[dict[str, Any]],
    trusted_authorization_sha256: str | None,
) -> tuple[
    dict[str, Any],
    dict[str, Image.Image],
    dict[str, bytes],
    list[dict[str, Any]],
]:
    authorization_path = Path(authorization_path)
    _reject_symlink_chain(authorization_path, None, "authorization record")
    if not authorization_path.is_file():
        raise ContractError(f"authorization record does not exist: {authorization_path}")
    try:
        authorization_bytes = authorization_path.read_bytes()
    except OSError as error:
        raise ContractError(f"cannot read authorization record: {error}") from error
    if trusted_authorization_sha256 is None:
        raise ContractError(
            "trusted authorization sha256 is not configured; current-user re-confirmation is required"
        )
    trusted_digest = _expect_sha256(
        trusted_authorization_sha256, "trusted authorization sha256"
    )
    authorization_digest = sha256(authorization_bytes).hexdigest()
    if authorization_digest != trusted_digest:
        raise ContractError(
            "authorization record sha256 mismatch: "
            f"trusted {trusted_digest}, got {authorization_digest}"
        )
    try:
        raw = yaml.safe_load(authorization_bytes.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as error:
        raise ContractError(f"cannot read authorization record: {error}") from error

    preliminary = _expect_mapping(raw, "authorization record")
    preliminary_binding = _expect_mapping(
        preliminary.get("transform_binding"), "authorization transform_binding"
    )
    current_transform_sha = _snapshot_hash(input_snapshot, "transform spec")
    if preliminary_binding.get("sha256") != current_transform_sha:
        raise ContractError(
            "transform binding sha256 mismatch: "
            f"current transform is {current_transform_sha}, authorization binds "
            f"{preliminary_binding.get('sha256')!r}"
        )

    authorization_record = _expect_keys(raw, AUTH_ROOT_KEYS, "authorization record")
    _expect_exact(authorization_record["schema_version"], 1, "authorization schema_version")
    _expect_exact(authorization_record["id"], FINAL_AUTHORIZATION_ID, "authorization id")
    _expect_exact(
        authorization_record["evidence_kind"],
        "current-user-generation-authorization",
        "authorization evidence_kind",
    )
    _expect_exact(authorization_record["status"], "passed", "authorization status")

    approval = _expect_keys(
        authorization_record["authorization"], AUTHORIZATION_KEYS, "authorization.authorization"
    )
    _expect_exact(approval["authority"], "current-user", "authorization.authority")
    _expect_string(approval["basis"], "authorization.basis")
    _expect_run_timestamp(approval["confirmed_at_utc"], "authorization.confirmed_at_utc")
    approval_message_sha256 = _expect_sha256(
        approval["approval_message_sha256"], "authorization.approval_message_sha256"
    )
    expected_message_sha256 = sha256(approval["basis"].encode("utf-8")).hexdigest()
    if approval_message_sha256 != expected_message_sha256:
        raise ContractError(
            "authorization.approval_message_sha256 mismatch: "
            f"expected {expected_message_sha256}, got {approval_message_sha256}"
        )

    scope = _expect_keys(
        authorization_record["approved_scope"], APPROVED_SCOPE_KEYS, "approved_scope"
    )
    expected_scope = {
        "selection_lock_id": SELECTION_LOCK_ID,
        "ecommerce_asset_plan_id": ECOMMERCE_ASSET_PLAN_ID,
        "selected_direction_id": SELECTED_DIRECTION_ID,
        "selected_sku_ids": SELECTED_SKU_IDS,
        "required_roles": REQUIRED_ROLES,
        "source_artifact_id": SOURCE_ARTIFACT_ID,
        "source_artifact_sha256": spec["source"]["sha256"],
        "package_identity_sha256": PACKAGE_IDENTITY_SHA256,
    }
    for field, expected in expected_scope.items():
        _expect_exact(scope[field], expected, f"approved_scope.{field}")

    binding = _expect_keys(
        authorization_record["transform_binding"],
        TRANSFORM_BINDING_KEYS,
        "transform_binding",
    )
    _expect_exact(binding["locator"], DEFAULT_SPEC.as_posix(), "transform_binding.locator")
    _expect_sha256(binding["sha256"], "transform_binding.sha256")

    transform_check = _expect_keys(
        authorization_record["current_transform_check"],
        CURRENT_TRANSFORM_CHECK_KEYS,
        "current_transform_check",
    )
    expected_transform_check = {
        "checked_on": RUN_DATE,
        "observed_sha256": current_transform_sha,
        "status": "match",
        "generation_authorized": True,
        "requires_new_current_user_confirmation": False,
    }
    for field, expected in expected_transform_check.items():
        _expect_exact(transform_check[field], expected, f"current_transform_check.{field}")

    scope_status = _expect_keys(
        authorization_record["current_scope_status"],
        CURRENT_SCOPE_STATUS_KEYS,
        "current_scope_status",
    )
    expected_scope_status = {
        "selection_lock": "passed",
        "ecommerce_asset_plan": "passed",
        "asset_briefs": "passed",
        "ecommerce_generation": "authorized",
        "qa_delivery": "not-run",
    }
    for field, expected in expected_scope_status.items():
        _expect_exact(scope_status[field], expected, f"current_scope_status.{field}")

    _expect_exact(
        authorization_record["usage_scene_constraint"],
        USAGE_SCENE_CONSTRAINT,
        "usage_scene_constraint",
    )
    _expect_exact(
        authorization_record["specification_constraint"],
        SPECIFICATION_CONSTRAINT,
        "specification_constraint",
    )

    qa_plan = _expect_keys(authorization_record["qa_plan"], QA_PLAN_KEYS, "qa_plan")
    expected_qa = {
        "required_gate_ids": REQUIRED_GATE_IDS,
        "cross_set_required_gate_ids": CROSS_SET_GATE_IDS,
        "required_profile_ids": PROFILE_IDS,
        "independent_review_required": True,
        "expected_gate_rows": EXPECTED_QA_ROWS,
    }
    for field, expected in expected_qa.items():
        _expect_exact(qa_plan[field], expected, f"qa_plan.{field}")
    computed_rows = len(GRAPH_ORDER) * len(REQUIRED_GATE_IDS) * len(PROFILE_IDS) + len(
        CROSS_SET_GATE_IDS
    )
    if computed_rows != EXPECTED_QA_ROWS:
        raise ContractError("internal QA row cardinality no longer equals 188")

    budget = _expect_keys(
        authorization_record["generation_budget"],
        GENERATION_BUDGET_KEYS,
        "generation_budget",
    )
    expected_budget = {
        "paid_calls_allowed": True,
        "maximum_total_calls": 4,
        "maximum_calls_per_background_plate": 2,
        "deterministic_roles": DETERMINISTIC_ROLES,
        "external_background_plate_roles": BACKGROUND_PLATE_ROLES,
    }
    for field, expected in expected_budget.items():
        _expect_exact(budget[field], expected, f"generation_budget.{field}")

    output = _expect_keys(authorization_record["output"], AUTH_OUTPUT_KEYS, "output")
    expected_output = {
        "root": spec["final_output_root"],
        "overwrite": False,
        "retention_policy": "preserve",
        "publication_authorized": False,
    }
    for field, expected in expected_output.items():
        _expect_exact(output[field], expected, f"output.{field}")
    publication = _expect_keys(
        authorization_record["publication"], PUBLICATION_KEYS, "publication"
    )
    _expect_bool(publication["authorized"], False, "publication.authorized")
    _expect_bool(
        publication["requires_new_current_user_confirmation"],
        True,
        "publication.requires_new_current_user_confirmation",
    )

    expected_plates = {
        "gallery-usage-background-plate": {
            "role": "usage",
            "dimensions": (1200, 1500),
            "retained_locator": "attempts/gallery-usage/background-attempt-01-2026-09-09.png",
        },
        "gallery-context-background-plate": {
            "role": "context",
            "dimensions": (1920, 1080),
            "retained_locator": "attempts/gallery-context/background-attempt-01-2026-09-09.png",
        },
    }
    raw_plates = _expect_list(authorization_record["background_plates"], "background_plates")
    if len(raw_plates) != len(expected_plates):
        raise ContractError("background_plates must contain exactly usage and context plates")
    plate_images: dict[str, Image.Image] = {}
    plate_bytes: dict[str, bytes] = {}
    snapshot = list(input_snapshot)
    snapshot.append(
        {
            "label": "authorization record",
            "path": authorization_path,
            "sha256": authorization_digest,
        }
    )
    total_calls = 0
    for index, raw_plate in enumerate(raw_plates):
        context = f"background_plates[{index}]"
        plate = _expect_keys(raw_plate, BACKGROUND_PLATE_KEYS, context)
        supporting_id = _expect_string(plate["supporting_asset_id"], f"{context}.supporting_asset_id")
        if supporting_id not in expected_plates or supporting_id in plate_images:
            raise ContractError(f"{context}.supporting_asset_id is unexpected or duplicated")
        expected_plate = expected_plates[supporting_id]
        _expect_exact(plate["role"], expected_plate["role"], f"{context}.role")
        _expect_exact(plate["locator_type"], "absolute_path", f"{context}.locator_type")
        locator = _expect_string(plate["locator"], f"{context}.locator")
        plate_path = Path(locator)
        if not plate_path.is_absolute():
            raise ContractError(f"{context}.locator must be an absolute external path")
        _reject_symlink_chain(plate_path, None, f"background plate {supporting_id}")
        if not plate_path.is_file():
            raise ContractError(f"background plate {supporting_id} does not exist: {plate_path}")
        resolved_repository = _repository_root(fixture_root)
        resolved_plate = plate_path.resolve(strict=True)
        if _contains_path(resolved_repository, resolved_plate):
            raise ContractError(f"background plate {supporting_id} must be repo-external")
        payload = plate_path.read_bytes()
        actual_hash = sha256(payload).hexdigest()
        expected_hash = _expect_sha256(plate["sha256"], f"{context}.sha256")
        if actual_hash != expected_hash:
            raise ContractError(
                f"background plate {supporting_id} sha256 mismatch: expected {expected_hash}, got {actual_hash}"
            )
        image = _load_image_bytes(payload, f"background plate {supporting_id}")
        expected_dimensions = expected_plate["dimensions"]
        _expect_exact(
            _dimensions(plate["dimensions"], f"{context}.dimensions"),
            expected_dimensions,
            f"{context}.dimensions",
        )
        if image.size != expected_dimensions:
            raise ContractError(
                f"background plate {supporting_id} dimensions mismatch: expected {expected_dimensions}, got {image.size}"
            )
        _expect_exact(plate["mode"], "RGB", f"{context}.mode")
        if image.mode != "RGB":
            raise ContractError(f"background plate {supporting_id} mode must be RGB")
        _expect_bool(plate["icc_profile_present"], False, f"{context}.icc_profile_present")
        if _icc_state(image)[0]:
            raise ContractError(f"background plate {supporting_id} must not contain an ICC profile")
        retained = _safe_locator(plate["retained_locator"], f"{context}.retained_locator")
        _expect_exact(
            retained.as_posix(),
            expected_plate["retained_locator"],
            f"{context}.retained_locator",
        )

        attempt = _expect_keys(plate["clean_attempt"], CLEAN_ATTEMPT_KEYS, f"{context}.clean_attempt")
        _expect_exact(
            attempt["attempt_id"],
            f"gallery-{expected_plate['role']}-background-attempt-01-{RUN_DATE}",
            f"{context}.clean_attempt.attempt_id",
        )
        _expect_exact(attempt["outcome"], "passed", f"{context}.clean_attempt.outcome")
        call_count = _expect_int(attempt["call_count"], f"{context}.clean_attempt.call_count", 1)
        if call_count > budget["maximum_calls_per_background_plate"]:
            raise ContractError(
                f"{context}.clean_attempt.call_count exceeds maximum_calls_per_background_plate"
            )
        total_calls += call_count
        if attempt["failure_class"] is not None:
            raise ContractError(f"{context}.clean_attempt.failure_class must be null")
        _expect_non_path_identifier(
            attempt["provider"], f"{context}.clean_attempt.provider"
        )
        _expect_non_path_identifier(attempt["model"], f"{context}.clean_attempt.model")
        _expect_run_timestamp(
            attempt["executed_at_utc"], f"{context}.clean_attempt.executed_at_utc"
        )
        _expect_sha256(
            attempt["prompt_sha256"], f"{context}.clean_attempt.prompt_sha256"
        )
        checks = _expect_keys(
            attempt["checks"], PLATE_CHECK_KEYS, f"{context}.clean_attempt.checks"
        )
        for check_name, result in checks.items():
            _expect_exact(result, "passed", f"{context}.clean_attempt.checks.{check_name}")

        provenance = _expect_keys(plate["provenance"], PROVENANCE_KEYS, f"{context}.provenance")
        expected_provenance = {
            "created_by": "external-image-generation",
            "source_material": "fictional text-only background prompt",
            "visible_trademarks": "none",
            "embedded_private_data": False,
            "redistribution_allowed": False,
            "publication_allowed": False,
            "documented_issue": "none",
        }
        for field, expected in expected_provenance.items():
            _expect_exact(provenance[field], expected, f"{context}.provenance.{field}")

        plate_images[supporting_id] = image
        plate_bytes[supporting_id] = payload
        snapshot.append(
            {
                "label": f"background plate {supporting_id}",
                "path": plate_path,
                "sha256": actual_hash,
            }
        )
    if set(plate_images) != set(expected_plates):
        raise ContractError("background_plates must bind usage and context supporting assets")
    if total_calls > budget["maximum_total_calls"]:
        raise ContractError("background plate call_count total exceeds maximum_total_calls")
    return authorization_record, plate_images, plate_bytes, snapshot


def _report_spec_locator(spec_path: Path, fixture_root: Path) -> str:
    resolved_root = Path(fixture_root).resolve(strict=True)
    resolved_spec = Path(spec_path).resolve(strict=True)
    if _contains_path(resolved_root, resolved_spec):
        return resolved_spec.relative_to(resolved_root).as_posix()
    return "external-transform-spec"


def _report_spec_reference(
    spec_path: Path, fixture_root: Path, snapshot: list[dict[str, Any]]
) -> dict[str, str]:
    return {
        "locator": _report_spec_locator(spec_path, fixture_root),
        "sha256": _snapshot_hash(snapshot, "transform spec"),
    }


def _report_source_reference(spec: dict[str, Any]) -> dict[str, str]:
    return {
        "locator": spec["source"]["locator"],
        "sha256": spec["source"]["sha256"],
    }


def _report_mask_references(spec: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"id": record["id"], "locator": record["locator"], "sha256": record["sha256"]}
        for record in spec["masks"]
    ]


def preflight(spec_path: Path, fixture_root: Path) -> dict[str, Any]:
    spec, _, _, snapshot = _spec_and_inputs(spec_path, fixture_root)
    final_root = Path(fixture_root) / _safe_locator(spec["final_output_root"], "final_output_root")
    ready = []
    blocked = []
    for row in spec["graph"]:
        summary = {
            "requested_artifact_id": row["requested_artifact_id"],
            "role": row["role"],
            "final_filename": row["final_filename"],
            "dimensions": row["canvas"]["dimensions"],
            "required_input_asset_ids": row["required_input_asset_ids"],
        }
        if row["preview_enabled"]:
            ready.append(summary)
        else:
            blocked.append(
                {
                    **summary,
                    "missing_input_asset_ids": row["blocked_without"],
                    "reason": BLOCKED_REASON,
                }
            )
    return {
        "schema_version": 1,
        "run_date": RUN_DATE,
        "mode": "preflight",
        "authorization": AUTHORIZATION,
        "transform_spec": _report_spec_reference(spec_path, fixture_root, snapshot),
        "source": _report_source_reference(spec),
        "masks": _report_mask_references(spec),
        "ready": ready,
        "blocked": blocked,
        "final_output_root": spec["final_output_root"],
        "final_output_root_exists": final_root.exists(),
    }


def _validate_preview_output(output: Path, fixture_root: Path, must_exist: bool) -> Path:
    output = Path(output)
    fixture_root = Path(fixture_root).resolve(strict=True)
    _reject_symlink_chain(output, None, "preview output")
    resolved = output.resolve(strict=False)
    if _contains_path(fixture_root, resolved):
        raise ContractError("unsafe preview output: previews must stay outside the fixture root")
    if must_exist:
        if not output.is_dir():
            raise ContractError(f"preview output does not exist: {output}")
    elif output.exists() or output.is_symlink():
        raise ContractError(f"existing output is not overwritten: {output}")
    parent = output.parent
    if not parent.is_dir():
        raise ContractError(f"preview output parent does not exist: {parent}")
    _reject_symlink_chain(parent, None, "preview output parent")
    return output


def _input_bindings(
    row: dict[str, Any], asset_hashes: dict[str, str]
) -> list[dict[str, Any]]:
    return [
        {
            "asset_id": asset_id,
            "status": "bound" if asset_id in asset_hashes else "missing",
            "sha256": asset_hashes.get(asset_id),
        }
        for asset_id in row["required_input_asset_ids"]
    ]


def build_preview(spec_path: Path, fixture_root: Path, output: Path) -> dict[str, Any]:
    fixture_root = Path(fixture_root)
    output = _validate_preview_output(Path(output), fixture_root, must_exist=False)
    spec, asset_images, mask_images, snapshot = _spec_and_inputs(Path(spec_path), fixture_root)
    staging = output.parent / f".{output.name}.staging-{uuid4().hex}"
    if staging.exists() or staging.is_symlink():
        raise ContractError(f"staging path already exists: {staging}")
    staging.mkdir(mode=0o700)
    artifacts: list[dict[str, Any]] = []
    asset_hashes = {"compare-direction-a": spec["source"]["sha256"]}
    try:
        for row in spec["graph"]:
            artifact_id = row["requested_artifact_id"]
            if not row["preview_enabled"]:
                artifacts.append(
                    {
                        "requested_artifact_id": artifact_id,
                        "role": row["role"],
                        "status": "blocked",
                        "reason": BLOCKED_REASON,
                        "missing_input_asset_ids": row["blocked_without"],
                        "input_bindings": _input_bindings(row, asset_hashes),
                        "locator": None,
                        "sha256": None,
                        "dimensions": row["canvas"]["dimensions"],
                        "mode": "RGB",
                        "package_face_checks": [],
                    }
                )
                continue
            image = render_preview_asset(row, asset_images, mask_images)
            checks = compute_package_face_checks(row, image, asset_images, mask_images)
            for check in checks:
                if check["source_opaque_sha256"] != check["output_opaque_sha256"]:
                    raise ContractError(f"{artifact_id} package face changed during rendering")
            encoded = _png_bytes(image, spec["rendering"])
            path = staging / row["final_filename"]
            path.write_bytes(encoded)
            artifact_hash = sha256(encoded).hexdigest()
            artifacts.append(
                {
                    "requested_artifact_id": artifact_id,
                    "role": row["role"],
                    "status": "preview",
                    "locator": row["final_filename"],
                    "sha256": artifact_hash,
                    "dimensions": list(image.size),
                    "mode": image.mode,
                    "icc_profile_present": False,
                    "input_bindings": _input_bindings(row, asset_hashes),
                    "package_face_checks": checks,
                }
            )
            asset_images[artifact_id] = image
            asset_hashes[artifact_id] = artifact_hash

        report = {
            "schema_version": 1,
            "run_date": RUN_DATE,
            "mode": "preview",
            "authorization": AUTHORIZATION,
            "transform_spec": _report_spec_reference(spec_path, fixture_root, snapshot),
            "source": _report_source_reference(spec),
            "masks": _report_mask_references(spec),
            "artifacts": artifacts,
            "final_output_root": spec["final_output_root"],
            "final_output_root_written": False,
        }
        (staging / "preview-report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        if output.exists() or output.is_symlink():
            raise ContractError(f"existing output appeared during build: {output}")
        _assert_snapshot_unchanged(snapshot, "preview build")
        os.rename(staging, output)
        return report
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _validate_final_output(
    spec: dict[str, Any], authorization: dict[str, Any], fixture_root: Path
) -> Path:
    fixture_root = Path(fixture_root)
    relative = _safe_locator(authorization["output"]["root"], "output.root")
    _expect_exact(relative.as_posix(), spec["final_output_root"], "output.root")
    output = fixture_root / relative
    _reject_symlink_chain(output, fixture_root, "final output")
    resolved_root = fixture_root.resolve(strict=True)
    resolved_output = output.resolve(strict=False)
    if not _contains_path(resolved_root, resolved_output):
        raise ContractError("final output escapes the fixture root")
    if output.exists() or output.is_symlink():
        raise ContractError(f"existing final output is not overwritten: {output}")
    return output


def _create_parent_chain(parent: Path, fixture_root: Path) -> list[Path]:
    fixture_root = Path(fixture_root)
    missing: list[Path] = []
    current = parent
    while not current.exists() and not current.is_symlink():
        missing.append(current)
        if current == fixture_root or current.parent == current:
            break
        current = current.parent
    _reject_symlink_chain(current, fixture_root, "final output parent")
    if not current.is_dir():
        raise ContractError(f"final output parent is not a directory: {current}")
    if not _contains_path(fixture_root.resolve(strict=True), parent.resolve(strict=False)):
        raise ContractError("final output parent escapes the fixture root")
    created: list[Path] = []
    try:
        for directory in reversed(missing):
            directory.mkdir(mode=0o700)
            created.append(directory)
    except BaseException:
        for directory in reversed(created):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise
    return created


def _remove_empty_directories(directories: list[Path]) -> None:
    for directory in reversed(directories):
        try:
            directory.rmdir()
        except OSError:
            pass


def _atomic_rename_no_replace(source: Path, destination: Path) -> None:
    if sys.platform == "win32":
        # Windows rename rejects existing destinations, including empty directories.
        try:
            os.rename(source, destination)
        except FileExistsError as error:
            raise ContractError(f"atomic final output already exists: {destination}") from error
        return
    source_bytes = os.fsencode(source)
    destination_bytes = os.fsencode(destination)
    libc = ctypes.CDLL(None, use_errno=True)
    ctypes.set_errno(0)
    if sys.platform == "darwin":
        try:
            rename = libc.renamex_np
        except AttributeError as error:
            raise ContractError("atomic no-replace rename is unavailable on this macOS host") from error
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(source_bytes, destination_bytes, 0x00000004)
    elif sys.platform.startswith("linux"):
        try:
            rename = libc.renameat2
        except AttributeError as error:
            raise ContractError("atomic no-replace rename is unavailable on this Linux host") from error
        rename.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename.restype = ctypes.c_int
        result = rename(-100, source_bytes, -100, destination_bytes, 0x00000001)
    else:
        raise ContractError(
            f"atomic no-replace rename is unsupported on platform {sys.platform!r}"
        )
    if result == 0:
        return
    error_code = ctypes.get_errno()
    if error_code in {errno.EEXIST, errno.ENOTEMPTY}:
        raise ContractError(f"atomic final output already exists: {destination}")
    raise OSError(error_code, os.strerror(error_code), str(destination))


def _build_plate_provenance(
    authorization: dict[str, Any], authorization_sha256: str
) -> dict[str, Any]:
    plates = []
    for plate in authorization["background_plates"]:
        plates.append(
            {
                "supporting_asset_id": plate["supporting_asset_id"],
                "role": plate["role"],
                "retained_locator": plate["retained_locator"],
                "sha256": plate["sha256"],
                "dimensions": plate["dimensions"],
                "mode": plate["mode"],
                "icc_profile_present": plate["icc_profile_present"],
                "clean_attempt": plate["clean_attempt"],
                "provenance": plate["provenance"],
            }
        )
    return {
        "schema_version": 1,
        "run_date": RUN_DATE,
        "status": FINAL_STATUS,
        "authorization": {
            "id": authorization["id"],
            "sha256": authorization_sha256,
        },
        "publication_authorized": False,
        "plates": plates,
    }


def _build_pending_qa_rows(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    artifact_by_id = {row["requested_artifact_id"]: row for row in artifacts}
    rows: list[dict[str, Any]] = []
    for requested_artifact_id in GRAPH_ORDER:
        artifact = artifact_by_id[requested_artifact_id]
        for gate_id in REQUIRED_GATE_IDS:
            for profile_id in PROFILE_IDS:
                rows.append(
                    {
                        "row_id": f"{requested_artifact_id}:{gate_id}:{profile_id}",
                        "scope": "artifact-profile",
                        "requested_artifact_id": requested_artifact_id,
                        "artifact_id": requested_artifact_id,
                        "role": artifact["role"],
                        "gate_id": gate_id,
                        "profile_id": profile_id,
                        "status": "unverified",
                        "evidence": None,
                        "reviewer_id": None,
                    }
                )
    for gate_id in CROSS_SET_GATE_IDS:
        rows.append(
            {
                "row_id": f"cross-set:{gate_id}",
                "scope": "cross-set",
                "requested_artifact_id": None,
                "artifact_id": None,
                "role": None,
                "gate_id": gate_id,
                "profile_id": None,
                "status": "unverified",
                "evidence": None,
                "reviewer_id": None,
            }
        )
    if len(rows) != EXPECTED_QA_ROWS or len({row["row_id"] for row in rows}) != len(rows):
        raise ContractError("final QA plan does not contain exactly 188 unique rows")
    return rows


def build_final(
    spec_path: Path,
    fixture_root: Path,
    authorization_path: Path,
    *,
    trusted_authorization_sha256: str | None = None,
) -> dict[str, Any]:
    fixture_root = Path(fixture_root)
    spec, asset_images, mask_images, snapshot = _spec_and_inputs(Path(spec_path), fixture_root)
    authorization, plate_images, plate_bytes, snapshot = _load_authorization_bundle(
        Path(authorization_path),
        fixture_root,
        spec,
        snapshot,
        trusted_authorization_sha256,
    )
    output = _validate_final_output(spec, authorization, fixture_root)
    created_directories: list[Path] = []
    staging: Path | None = None
    try:
        created_directories = _create_parent_chain(output.parent, fixture_root)
        staging = output.parent / f".{output.name}.staging-{uuid4().hex}"
        if staging.exists() or staging.is_symlink():
            raise ContractError(f"staging path already exists: {staging}")
        staging.mkdir(mode=0o700)

        asset_images.update(plate_images)
        asset_hashes = {SOURCE_ARTIFACT_ID: spec["source"]["sha256"]}
        asset_hashes.update(
            {plate["supporting_asset_id"]: plate["sha256"] for plate in authorization["background_plates"]}
        )
        artifacts: list[dict[str, Any]] = []
        for row in spec["graph"]:
            artifact_id = row["requested_artifact_id"]
            image = render_final_asset(row, asset_images, mask_images)
            checks = compute_package_face_checks(row, image, asset_images, mask_images)
            if not checks:
                raise ContractError(f"{artifact_id} has no package face identity receipt")
            for check in checks:
                if check["source_opaque_sha256"] != check["output_opaque_sha256"]:
                    raise ContractError(f"{artifact_id} package face changed during final rendering")
            encoded = _png_bytes(image, spec["rendering"])
            artifact_path = staging / row["final_filename"]
            artifact_path.write_bytes(encoded)
            artifact_hash = sha256(encoded).hexdigest()
            artifacts.append(
                {
                    "requested_artifact_id": artifact_id,
                    "role": row["role"],
                    "status": FINAL_STATUS,
                    "review_status": FINAL_REVIEW_STATUS,
                    "locator": row["final_filename"],
                    "sha256": artifact_hash,
                    "dimensions": list(image.size),
                    "mode": image.mode,
                    "icc_profile_present": False,
                    "input_bindings": _input_bindings(row, asset_hashes),
                    "package_face_checks": checks,
                }
            )
            asset_images[artifact_id] = image
            asset_hashes[artifact_id] = artifact_hash

        for plate in authorization["background_plates"]:
            supporting_id = plate["supporting_asset_id"]
            retained = staging / _safe_locator(
                plate["retained_locator"], f"background plate {supporting_id} retained_locator"
            )
            retained.parent.mkdir(parents=True, exist_ok=False)
            retained.write_bytes(plate_bytes[supporting_id])

        authorization_sha = _snapshot_hash(snapshot, "authorization record")
        provenance = _build_plate_provenance(authorization, authorization_sha)
        provenance_bytes = (
            json.dumps(provenance, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        (staging / "plate-provenance.json").write_bytes(provenance_bytes)
        qa_rows = _build_pending_qa_rows(artifacts)
        approval = authorization["authorization"]
        budget = authorization["generation_budget"]
        actual_calls = sum(
            plate["clean_attempt"]["call_count"] for plate in authorization["background_plates"]
        )
        report = {
            "schema_version": 1,
            "run_date": RUN_DATE,
            "mode": "authorized-final-build",
            "status": FINAL_STATUS,
            "authorization": {
                "id": authorization["id"],
                "sha256": authorization_sha,
                "authority": approval["authority"],
                "confirmed_at_utc": approval["confirmed_at_utc"],
                "approval_message_sha256": approval["approval_message_sha256"],
            },
            "transform_spec": _report_spec_reference(spec_path, fixture_root, snapshot),
            "source": _report_source_reference(spec),
            "masks": _report_mask_references(spec),
            "selected_direction_id": SELECTED_DIRECTION_ID,
            "selected_sku_ids": SELECTED_SKU_IDS,
            "package_identity_sha256": PACKAGE_IDENTITY_SHA256,
            "artifacts": artifacts,
            "plate_provenance": {
                "locator": "plate-provenance.json",
                "sha256": sha256(provenance_bytes).hexdigest(),
            },
            "call_budget": {
                "maximum_total_calls": budget["maximum_total_calls"],
                "maximum_calls_per_background_plate": budget[
                    "maximum_calls_per_background_plate"
                ],
                "actual_total_calls": actual_calls,
            },
            "qa": {
                "status": "pending-independent-review",
                "independent_review_required": True,
                "expected_gate_rows": EXPECTED_QA_ROWS,
                "actual_gate_rows": len(qa_rows),
                "rows": qa_rows,
            },
            "publication_authorized": False,
            "final_output_root": spec["final_output_root"],
            "final_output_root_written": True,
        }
        (staging / "final-build-report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        if output.exists() or output.is_symlink():
            raise ContractError(f"existing final output appeared during build: {output}")
        _assert_snapshot_unchanged(snapshot, "final build")
        _atomic_rename_no_replace(staging, output)
        staging = None
        return report
    except BaseException:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)
        _remove_empty_directories(created_directories)
        raise


def _validate_preview_directory(output: Path, spec: dict[str, Any]) -> None:
    expected = {"preview-report.json"}
    expected.update(
        row["final_filename"] for row in spec["graph"] if row["preview_enabled"]
    )
    entries = list(output.iterdir())
    actual = {entry.name for entry in entries}
    unexpected = sorted(actual - expected)
    if unexpected:
        raise ContractError(
            f"unexpected preview output entry: {', '.join(unexpected)}"
        )
    missing = sorted(expected - actual)
    if missing:
        raise ContractError(f"preview output is missing entry: {', '.join(missing)}")
    for entry in entries:
        _reject_symlink_chain(entry, output, f"preview output entry {entry.name}")
        if not entry.is_file():
            raise ContractError(f"preview output entry must be a regular file: {entry.name}")


def _validate_preview_report(
    raw_report: Any,
    spec: dict[str, Any],
    spec_path: Path,
    fixture_root: Path,
    snapshot: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    report = _expect_keys(raw_report, REPORT_ROOT_KEYS, "preview report")
    expected_root_values = {
        "schema_version": 1,
        "run_date": RUN_DATE,
        "mode": "preview",
        "authorization": AUTHORIZATION,
        "final_output_root": spec["final_output_root"],
        "final_output_root_written": False,
    }
    for field, expected in expected_root_values.items():
        if report[field] != expected:
            raise ContractError(
                f"preview report {field} mismatch: expected {expected!r}"
            )

    transform_spec = _expect_keys(
        report["transform_spec"], REPORT_TRANSFORM_SPEC_KEYS, "preview report transform_spec"
    )
    if transform_spec != _report_spec_reference(spec_path, fixture_root, snapshot):
        raise ContractError("preview report transform_spec binding mismatch")
    source = _expect_keys(report["source"], REPORT_SOURCE_KEYS, "preview report source")
    if source != _report_source_reference(spec):
        raise ContractError("preview report source binding mismatch")

    mask_records = _expect_list(report["masks"], "preview report masks")
    if len(mask_records) != len(spec["masks"]):
        raise ContractError("preview report masks cardinality mismatch")
    normalized_masks = []
    for index, record in enumerate(mask_records):
        normalized_masks.append(
            _expect_keys(record, REPORT_MASK_KEYS, f"preview report masks[{index}]")
        )
    if normalized_masks != _report_mask_references(spec):
        raise ContractError("preview report mask bindings mismatch")

    artifact_records = _expect_list(report["artifacts"], "preview report artifacts")
    if len(artifact_records) != len(GRAPH_ORDER):
        raise ContractError("preview report artifacts cardinality mismatch")
    normalized_artifacts = []
    artifact_ids = []
    for index, (record, graph_row) in enumerate(zip(artifact_records, spec["graph"])):
        expected_keys = (
            REPORT_PREVIEW_ARTIFACT_KEYS
            if graph_row["preview_enabled"]
            else REPORT_BLOCKED_ARTIFACT_KEYS
        )
        normalized = _expect_keys(
            record, expected_keys, f"preview report artifacts[{index}]"
        )
        bindings = _expect_list(
            normalized["input_bindings"],
            f"preview report artifacts[{index}].input_bindings",
        )
        for binding_index, binding in enumerate(bindings):
            _expect_keys(
                binding,
                REPORT_INPUT_BINDING_KEYS,
                f"preview report artifacts[{index}].input_bindings[{binding_index}]",
            )
        checks = _expect_list(
            normalized["package_face_checks"],
            f"preview report artifacts[{index}].package_face_checks",
        )
        for check_index, check in enumerate(checks):
            _expect_keys(
                check,
                REPORT_FACE_CHECK_KEYS,
                f"preview report artifacts[{index}].package_face_checks[{check_index}]",
            )
        artifact_ids.append(normalized["requested_artifact_id"])
        normalized_artifacts.append(normalized)
    if artifact_ids != GRAPH_ORDER:
        raise ContractError(
            "preview report artifact order, uniqueness, or requested IDs mismatch"
        )
    return normalized_artifacts


def _validate_preview_artifact_static_fields(
    recorded: dict[str, Any],
    row: dict[str, Any],
    asset_hashes: dict[str, str],
) -> None:
    artifact_id = row["requested_artifact_id"]
    expected_bindings = _input_bindings(row, asset_hashes)
    if row["preview_enabled"]:
        expected = {
            "requested_artifact_id": artifact_id,
            "role": row["role"],
            "status": "preview",
            "locator": row["final_filename"],
            "dimensions": row["canvas"]["dimensions"],
            "mode": "RGB",
            "icc_profile_present": False,
            "input_bindings": expected_bindings,
        }
    else:
        expected = {
            "requested_artifact_id": artifact_id,
            "role": row["role"],
            "status": "blocked",
            "reason": BLOCKED_REASON,
            "missing_input_asset_ids": row["blocked_without"],
            "input_bindings": expected_bindings,
            "locator": None,
            "sha256": None,
            "dimensions": row["canvas"]["dimensions"],
            "mode": "RGB",
            "package_face_checks": [],
        }
    for field, expected_value in expected.items():
        if recorded[field] != expected_value:
            raise ContractError(
                f"preview report artifact {artifact_id} {field} mismatch"
            )


def verify_preview(spec_path: Path, fixture_root: Path, output: Path) -> dict[str, Any]:
    fixture_root = Path(fixture_root)
    spec, expected_assets, mask_images, snapshot = _spec_and_inputs(
        Path(spec_path), fixture_root
    )
    output = _validate_preview_output(Path(output), fixture_root, must_exist=True)
    _validate_preview_directory(output, spec)
    report_path = output / "preview-report.json"
    _reject_symlink_chain(report_path, output, "preview report")
    if not report_path.is_file():
        raise ContractError("preview report is missing")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ContractError(f"cannot read preview report: {error}") from error
    report_rows = _validate_preview_report(
        report, spec, Path(spec_path), fixture_root, snapshot
    )

    actual_assets = {"compare-direction-a": expected_assets["compare-direction-a"].copy()}
    asset_hashes = {"compare-direction-a": spec["source"]["sha256"]}
    verified = []
    for row, recorded in zip(spec["graph"], report_rows):
        artifact_id = row["requested_artifact_id"]
        _validate_preview_artifact_static_fields(recorded, row, asset_hashes)
        if not row["preview_enabled"]:
            verified.append({"requested_artifact_id": artifact_id, "status": "blocked"})
            continue
        path = output / row["final_filename"]
        _reject_symlink_chain(path, output, f"preview artifact {artifact_id}")
        if not path.is_file():
            raise ContractError(f"preview artifact {artifact_id} is missing")
        actual = _load_image(path)
        if actual.mode != "RGB" or list(actual.size) != row["canvas"]["dimensions"]:
            raise ContractError(f"preview artifact {artifact_id} mode or dimensions mismatch")
        if _icc_state(actual)[0]:
            raise ContractError(f"preview artifact {artifact_id} unexpectedly contains an ICC profile")

        current_checks = compute_package_face_checks(row, actual, actual_assets, mask_images)
        for check in current_checks:
            if check["source_opaque_sha256"] != check["output_opaque_sha256"]:
                raise ContractError(
                    f"preview artifact {artifact_id} package face pixels do not match its bound input"
                )
        if current_checks != recorded.get("package_face_checks"):
            raise ContractError(f"preview artifact {artifact_id} package face receipt mismatch")

        expected = render_preview_asset(row, expected_assets, mask_images)
        expected_bytes = _png_bytes(expected, spec["rendering"])
        current_bytes = path.read_bytes()
        if sha256(current_bytes).hexdigest() != recorded.get("sha256"):
            raise ContractError(f"preview artifact {artifact_id} sha256 mismatch")
        if current_bytes != expected_bytes:
            raise ContractError(f"preview artifact {artifact_id} deterministic bytes mismatch")
        actual_assets[artifact_id] = actual
        expected_assets[artifact_id] = expected
        asset_hashes[artifact_id] = recorded["sha256"]
        verified.append({"requested_artifact_id": artifact_id, "status": "verified"})

    _assert_snapshot_unchanged(snapshot, "preview verification")
    return {
        "schema_version": 1,
        "run_date": RUN_DATE,
        "mode": "verification",
        "authorization": AUTHORIZATION,
        "status": "passed",
        "verified": verified,
        "final_output_root_written": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preflight or build temporary deterministic previews for the fictional v0.2 gallery."
    )
    parser.add_argument(
        "--fixture-root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Fictional fixture root (defaults to this script's directory).",
    )
    parser.add_argument(
        "--spec",
        type=Path,
        help="Closed transform spec (defaults inside the selected fixture root).",
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--build-preview", type=Path, metavar="OUTPUT")
    action.add_argument("--verify-preview", type=Path, metavar="OUTPUT")
    action.add_argument(
        "--build-final",
        action="store_true",
        help="Build the fixed local final root under an exact current-user authorization.",
    )
    parser.add_argument(
        "--authorization",
        type=Path,
        help="Exact current-user authorization record required by --build-final.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    fixture_root = args.fixture_root
    spec_path = args.spec if args.spec is not None else fixture_root / DEFAULT_SPEC
    try:
        if args.authorization is not None and not args.build_final:
            raise ContractError("--authorization is valid only with --build-final")
        if args.build_final:
            if args.authorization is None:
                raise ContractError("--authorization is required with --build-final")
            report = build_final(
                spec_path,
                fixture_root,
                args.authorization,
                trusted_authorization_sha256=TRUSTED_FINAL_AUTHORIZATION_SHA256,
            )
        elif args.build_preview is not None:
            report = build_preview(spec_path, fixture_root, args.build_preview)
        elif args.verify_preview is not None:
            report = verify_preview(spec_path, fixture_root, args.verify_preview)
        else:
            report = preflight(spec_path, fixture_root)
    except (ContractError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
