#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.15"
# dependencies = [
#   "Pillow>=10,<13",
# ]
# ///
"""Build a local, inspectable thumbnail review pack without changing sources."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import shutil
import stat
import sys
import unicodedata
import uuid
from pathlib import Path
from typing import Any, Sequence

try:
    from PIL import Image, ImageOps, UnidentifiedImageError
except ImportError:
    Image = None
    ImageOps = None
    UnidentifiedImageError = OSError


EXIT_SUCCESS = 0
EXIT_INVALID_INPUT = 2
EXIT_MISSING_DEPENDENCY = 3
EXIT_UNREADABLE_IMAGE = 4
EXIT_UNSAFE_OUTPUT = 5
DEFAULT_THUMBNAIL_EDGE = 320
MANIFEST_SCHEMA_VERSION = 1
REVIEW_SCHEMA_VERSION = 1
OWNER_MARKER_NAME = ".packaging-product-visuals-review-pack.json"
OWNER_MARKER = {
    "kind": "packaging-product-visuals-review-pack",
    "schema_version": 1,
}
MANIFEST_RECORD_FIELDS = {
    "height",
    "mode",
    "orientation",
    "sha256",
    "source_orientation",
    "source_path",
    "thumbnail_height",
    "thumbnail_path",
    "thumbnail_width",
    "width",
}
REVIEW_FIELDS = {
    "assets",
    "delivery_status",
    "direction",
    "product",
    "schema_version",
    "stages",
    "title",
}
REVIEW_ASSET_FIELDS = {
    "height",
    "identity",
    "mode",
    "qa",
    "role",
    "sha256",
    "source_path",
    "stage",
    "status",
    "summary",
    "thumbnail_path",
    "title",
    "width",
}
DELIVERY_STATUSES = ("passed", "draft", "blocked")
STAGE_STATUSES = ("passed", "draft", "blocked", "missing")
IMAGE_ASSET_STATUSES = ("passed", "draft")
STAGES = (
    ("product-definition", "Product definition", "产品定义"),
    ("research-options", "Research and options", "研究与方案比较"),
    ("decision-freeze", "Decision freeze", "决策冻结"),
    ("packaging-directions", "Packaging directions", "包装方向"),
    ("selection-refinement", "Selection and refinement", "选择与精修"),
    ("ecommerce-planning", "Ecommerce planning", "电商资产规划"),
    ("ecommerce-generation", "Ecommerce generation", "电商套图生成"),
    ("qa-delivery", "QA and delivery", "质检与交付"),
)
ROLES = (
    ("comparison", "Comparison", "方向对比"),
    ("refinement", "Refinement", "精修"),
    ("catalog", "Catalog", "目录主图"),
    ("detail", "Detail", "细节"),
    ("usage", "Usage", "使用步骤"),
    ("specification", "Specification", "规格信息"),
    ("context", "Context", "场景"),
    ("campaign", "Campaign", "活动素材"),
    ("channel-variant", "Channel variant", "渠道变体"),
    ("technical-review", "Technical review", "技术审阅"),
)
STAGE_LABELS = {stage_id: {"en": en, "zh": zh} for stage_id, en, zh in STAGES}
ROLE_LABELS = {role_id: {"en": en, "zh": zh} for role_id, en, zh in ROLES}
STAGE_ORDER = {stage_id: index for index, (stage_id, _, _) in enumerate(STAGES)}
ROLE_ORDER = {role_id: index for index, (role_id, _, _) in enumerate(ROLES)}


class ReviewPackError(Exception):
    def __init__(self, exit_code: int, message: str) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def error_kind(error: BaseException) -> str:
    """Describe an operating failure without copying private paths into diagnostics."""
    if isinstance(error, OSError) and error.strerror:
        return error.strerror
    return type(error).__name__


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create local contain thumbnails and a relative review manifest."
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Destination directory for the completed review pack.",
    )
    parser.add_argument(
        "--thumbnail-edge",
        type=int,
        default=DEFAULT_THUMBNAIL_EDGE,
        help="Longest edge of each contain thumbnail (default: 320).",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Also write a bilingual offline HTML review page.",
    )
    parser.add_argument(
        "--review-spec",
        type=Path,
        help=(
            "Optional JSON metadata for a staged bilingual review; also writes "
            "review.json and index.html."
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing tool-owned review pack after a new pack is ready.",
    )
    parser.add_argument(
        "source_images",
        nargs="*",
        type=Path,
        help="One or more readable source image files.",
    )
    args = parser.parse_args(argv)
    if not args.source_images:
        parser.error("at least one source image is required")
    if args.thumbnail_edge < 1:
        parser.error("--thumbnail-edge must be a positive integer")
    return args


def _require_object(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReviewPackError(EXIT_INVALID_INPUT, f"review spec {context} must be an object")
    return value


def _require_exact_keys(
    value: Any, expected: set[str], context: str
) -> dict[str, Any]:
    item = _require_object(value, context)
    unknown = sorted(set(item) - expected)
    if unknown:
        raise ReviewPackError(
            EXIT_INVALID_INPUT,
            f"review spec {context} has unknown fields",
        )
    missing = sorted(expected - set(item))
    if missing:
        raise ReviewPackError(
            EXIT_INVALID_INPUT,
            f"review spec {context} is missing field: {missing[0]}",
        )
    return item


def _bilingual(value: Any, context: str) -> dict[str, str]:
    item = _require_object(value, context)
    unknown = sorted(set(item) - {"en", "zh"})
    if unknown:
        raise ReviewPackError(
            EXIT_INVALID_INPUT,
            f"review spec {context} has unknown fields",
        )
    if set(item) != {"en", "zh"}:
        raise ReviewPackError(
            EXIT_INVALID_INPUT,
            f"review spec {context} must contain bilingual en and zh text",
        )
    if any(not isinstance(item[language], str) or not item[language].strip() for language in ("en", "zh")):
        raise ReviewPackError(
            EXIT_INVALID_INPUT,
            f"review spec {context} must contain non-empty bilingual text",
        )
    return {"en": item["en"].strip(), "zh": item["zh"].strip()}


def _status(value: Any, allowed: tuple[str, ...], context: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ReviewPackError(
            EXIT_INVALID_INPUT,
            f"review spec {context} has invalid status",
        )
    return value


def _validate_status_consistency(
    delivery_status: str,
    stages: list[dict[str, Any]],
    assets: list[dict[str, Any]],
    exit_code: int,
    message_prefix: str,
) -> None:
    assets_by_stage: dict[str, list[dict[str, Any]]] = {
        stage["id"]: [] for stage in stages
    }
    for asset in assets:
        assets_by_stage[asset["stage"]].append(asset)

    for stage in stages:
        covered_assets = assets_by_stage[stage["id"]]
        if stage["status"] == "passed" and any(
            asset["status"] != "passed" for asset in covered_assets
        ):
            raise ReviewPackError(
                exit_code, f"{message_prefix} has inconsistent passed stage status"
            )
        if stage["status"] == "missing" and covered_assets:
            raise ReviewPackError(
                exit_code, f"{message_prefix} has inconsistent missing stage status"
            )

    if delivery_status == "passed" and (
        any(stage["status"] != "passed" for stage in stages)
        or any(asset["status"] != "passed" for asset in assets)
    ):
        raise ReviewPackError(
            exit_code, f"{message_prefix} has inconsistent passed delivery status"
        )


def _load_review_spec(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise ReviewPackError(EXIT_INVALID_INPUT, "review spec must be a readable JSON file")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReviewPackError(
            EXIT_INVALID_INPUT, "review spec must be valid UTF-8 JSON"
        ) from error
    return _require_exact_keys(
        payload,
        {
            "assets",
            "delivery_status",
            "direction",
            "product",
            "schema_version",
            "stages",
            "title",
        },
        "root",
    )


def normalize_review_spec(
    path: Path, sources: Sequence[Path], records: list[dict[str, Any]]
) -> dict[str, Any]:
    spec = _load_review_spec(path.expanduser())
    if (
        not isinstance(spec["schema_version"], int)
        or isinstance(spec["schema_version"], bool)
        or spec["schema_version"] != REVIEW_SCHEMA_VERSION
    ):
        raise ReviewPackError(EXIT_INVALID_INPUT, "review spec has unsupported schema version")

    title = _bilingual(spec["title"], "title")
    product = _require_exact_keys(spec["product"], {"name", "summary"}, "product")
    normalized_product = {
        "name": _bilingual(product["name"], "product.name"),
        "summary": _bilingual(product["summary"], "product.summary"),
    }
    direction = _bilingual(spec["direction"], "direction")
    delivery_status = _status(
        spec["delivery_status"], DELIVERY_STATUSES, "delivery_status"
    )

    if not isinstance(spec["stages"], list) or not spec["stages"]:
        raise ReviewPackError(EXIT_INVALID_INPUT, "review spec stages must be a non-empty list")
    normalized_stages = []
    seen_stages: set[str] = set()
    for index, value in enumerate(spec["stages"]):
        stage = _require_exact_keys(value, {"id", "status"}, f"stages[{index}]")
        stage_id = stage["id"]
        if not isinstance(stage_id, str) or stage_id not in STAGE_LABELS:
            raise ReviewPackError(EXIT_INVALID_INPUT, "review spec has invalid stage")
        if stage_id in seen_stages:
            raise ReviewPackError(EXIT_INVALID_INPUT, "review spec has duplicate stage")
        seen_stages.add(stage_id)
        normalized_stages.append(
            {
                "id": stage_id,
                "label": STAGE_LABELS[stage_id],
                "status": _status(
                    stage["status"], STAGE_STATUSES, f"stages[{index}].status"
                ),
            }
        )
    normalized_stages.sort(key=lambda stage: STAGE_ORDER[stage["id"]])

    if not isinstance(spec["assets"], list) or not spec["assets"]:
        raise ReviewPackError(EXIT_INVALID_INPUT, "review spec assets must be a non-empty list")
    records_by_source = {record["source_path"]: record for record in records}
    source_names = {source.name for source in sources}
    normalized_assets = []
    seen_sources: set[str] = set()
    asset_fields = {
        "identity",
        "qa",
        "role",
        "source",
        "stage",
        "status",
        "summary",
        "title",
    }
    for index, value in enumerate(spec["assets"]):
        asset = _require_exact_keys(value, asset_fields, f"assets[{index}]")
        source_ref = asset["source"]
        if (
            not isinstance(source_ref, str)
            or not source_ref
            or Path(source_ref).is_absolute()
            or Path(source_ref).name != source_ref
            or ".." in Path(source_ref).parts
            or "/" in source_ref
            or "\\" in source_ref
            or source_ref not in source_names
        ):
            raise ReviewPackError(
                EXIT_INVALID_INPUT,
                "review spec source must match a current input filename",
            )
        if source_ref in seen_sources:
            raise ReviewPackError(EXIT_INVALID_INPUT, "review spec has duplicate source")
        seen_sources.add(source_ref)

        stage_id = asset["stage"]
        if (
            not isinstance(stage_id, str)
            or stage_id not in STAGE_LABELS
            or stage_id not in seen_stages
        ):
            raise ReviewPackError(EXIT_INVALID_INPUT, "review spec asset has invalid stage")
        role = asset["role"]
        if (
            not isinstance(role, str)
            or role not in ROLE_LABELS
            or role == "technical-review"
        ):
            raise ReviewPackError(EXIT_INVALID_INPUT, "review spec asset has invalid role")
        record = records_by_source[source_ref]
        normalized_assets.append(
            {
                "height": record["height"],
                "identity": _bilingual(asset["identity"], f"assets[{index}].identity"),
                "mode": record["mode"],
                "qa": _bilingual(asset["qa"], f"assets[{index}].qa"),
                "role": role,
                "sha256": record["sha256"],
                "source_path": source_ref,
                "stage": stage_id,
                "status": _status(
                    asset["status"],
                    IMAGE_ASSET_STATUSES,
                    f"assets[{index}].status",
                ),
                "summary": _bilingual(asset["summary"], f"assets[{index}].summary"),
                "thumbnail_path": record["thumbnail_path"],
                "title": _bilingual(asset["title"], f"assets[{index}].title"),
                "width": record["width"],
            }
        )
    if seen_sources != source_names:
        raise ReviewPackError(
            EXIT_INVALID_INPUT,
            "review spec assets must match every current input image exactly once",
        )
    normalized_assets.sort(
        key=lambda asset: (
            STAGE_ORDER[asset["stage"]],
            ROLE_ORDER[asset["role"]],
            asset["source_path"].casefold(),
            asset["source_path"],
        )
    )
    _validate_status_consistency(
        delivery_status,
        normalized_stages,
        normalized_assets,
        EXIT_INVALID_INPUT,
        "review spec",
    )
    return {
        "assets": normalized_assets,
        "delivery_status": delivery_status,
        "direction": direction,
        "product": normalized_product,
        "schema_version": REVIEW_SCHEMA_VERSION,
        "stages": normalized_stages,
        "title": title,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_runtime() -> None:
    if not (3, 10) <= sys.version_info[:2] < (3, 15):
        raise ReviewPackError(
            EXIT_INVALID_INPUT,
            "prepare_review_pack.py requires Python >=3.10,<3.15",
        )
    if Image is None or ImageOps is None:
        raise ReviewPackError(
            EXIT_MISSING_DEPENDENCY,
            "Pillow>=10,<13 is required; install it in the active environment.",
        )


def normalized_sources(paths: Sequence[Path]) -> list[Path]:
    sources = [path.expanduser() for path in paths]
    duplicate_stems: dict[str, Path] = {}
    for source in sources:
        key = unicodedata.normalize("NFC", source.stem).casefold()
        previous = duplicate_stems.get(key)
        if previous is not None:
            raise ReviewPackError(
                EXIT_INVALID_INPUT,
                f"duplicate source stem: {previous.name!r} and {source.name!r}",
            )
        duplicate_stems[key] = source
    return sorted(sources, key=lambda path: (path.name.casefold(), path.name))


def _is_same_or_ancestor(candidate: Path, protected: Path) -> bool:
    try:
        protected.relative_to(candidate)
    except ValueError:
        return False
    return True


def _repository_root(path: Path) -> Path | None:
    current = path if path.is_dir() else path.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate.resolve()
    return None


def is_high_risk_destination(output: Path) -> bool:
    resolved = output.resolve()
    if (resolved / ".git").exists():
        return True
    filesystem_root = Path(resolved.anchor).resolve()
    home = Path.home().resolve()
    cwd = Path.cwd().resolve()
    skill_root = Path(__file__).resolve().parents[1]
    repo_root = _repository_root(cwd) or _repository_root(Path(__file__).resolve())
    protected = [filesystem_root, home, cwd, skill_root]
    if repo_root is not None:
        protected.append(repo_root)
    return any(_is_same_or_ancestor(resolved, path) for path in protected)


def _load_json_object(path: Path, description: str) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise ReviewPackError(
            EXIT_UNSAFE_OUTPUT,
            f"existing output has no valid {description}",
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReviewPackError(
            EXIT_UNSAFE_OUTPUT,
            f"existing output has no valid {description}",
        ) from error
    if not isinstance(payload, dict):
        raise ReviewPackError(
            EXIT_UNSAFE_OUTPUT,
            f"existing output has no valid {description}",
        )
    return payload


def _validate_projection_bilingual(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"en", "zh"}
        and all(isinstance(value[key], str) and value[key] for key in ("en", "zh"))
    )


def validate_review_projection(
    review: dict[str, Any], manifest_records: list[dict[str, Any]]
) -> None:
    invalid = ReviewPackError(
        EXIT_UNSAFE_OUTPUT, "existing output has an invalid review projection"
    )
    if set(review) != REVIEW_FIELDS or review.get("schema_version") != REVIEW_SCHEMA_VERSION:
        raise invalid
    product = review.get("product")
    if (
        not _validate_projection_bilingual(review.get("title"))
        or not _validate_projection_bilingual(review.get("direction"))
        or not isinstance(review.get("delivery_status"), str)
        or review.get("delivery_status") not in DELIVERY_STATUSES
        or not isinstance(product, dict)
        or set(product) != {"name", "summary"}
        or not _validate_projection_bilingual(product.get("name"))
        or not _validate_projection_bilingual(product.get("summary"))
    ):
        raise invalid

    stages = review.get("stages")
    if not isinstance(stages, list) or not stages:
        raise invalid
    seen_stages: set[str] = set()
    last_stage_order = -1
    for stage in stages:
        if not isinstance(stage, dict) or set(stage) != {"id", "label", "status"}:
            raise invalid
        stage_id = stage.get("id")
        if (
            not isinstance(stage_id, str)
            or stage_id not in STAGE_LABELS
            or stage_id in seen_stages
            or stage.get("label") != STAGE_LABELS[stage_id]
            or not isinstance(stage.get("status"), str)
            or stage.get("status") not in STAGE_STATUSES
            or STAGE_ORDER[stage_id] <= last_stage_order
        ):
            raise invalid
        seen_stages.add(stage_id)
        last_stage_order = STAGE_ORDER[stage_id]

    records_by_source = {record["source_path"]: record for record in manifest_records}
    assets = review.get("assets")
    if not isinstance(assets, list) or len(assets) != len(records_by_source):
        raise invalid
    seen_sources: set[str] = set()
    previous_order: tuple[int, int, str, str] | None = None
    for asset in assets:
        if not isinstance(asset, dict) or set(asset) != REVIEW_ASSET_FIELDS:
            raise invalid
        source_path = asset.get("source_path")
        stage_id = asset.get("stage")
        role = asset.get("role")
        if (
            not isinstance(source_path, str)
            or source_path not in records_by_source
            or source_path in seen_sources
            or not isinstance(stage_id, str)
            or stage_id not in seen_stages
            or not isinstance(role, str)
            or role not in ROLE_LABELS
            or role == "technical-review"
            or not isinstance(asset.get("status"), str)
            or asset.get("status") not in IMAGE_ASSET_STATUSES
            or not all(
                _validate_projection_bilingual(asset.get(field))
                for field in ("identity", "qa", "summary", "title")
            )
        ):
            raise invalid
        record = records_by_source[source_path]
        if any(
            asset.get(field) != record[field]
            for field in (
                "height",
                "mode",
                "sha256",
                "source_path",
                "thumbnail_path",
                "width",
            )
        ):
            raise invalid
        order = (
            STAGE_ORDER[stage_id],
            ROLE_ORDER[role],
            source_path.casefold(),
            source_path,
        )
        if previous_order is not None and order <= previous_order:
            raise invalid
        previous_order = order
        seen_sources.add(source_path)
    if seen_sources != set(records_by_source):
        raise invalid
    _validate_status_consistency(
        review["delivery_status"],
        stages,
        assets,
        EXIT_UNSAFE_OUTPUT,
        "existing review projection",
    )


def render_v01_legacy_html(records: list[dict[str, Any]]) -> str:
    entries = []
    for record in records:
        name = html.escape(record["source_path"])
        thumbnail = html.escape(record["thumbnail_path"])
        entries.append(
            '<article><img src="{}" alt="{}"><p>{}</p></article>'.format(
                thumbnail, name, name
            )
        )
    return "".join(
        [
            '<!doctype html><html lang="en"><meta charset="utf-8">',
            "<title>Review pack</title><main>",
            *entries,
            "</main></html>\n",
        ]
    )


def validate_review_html(path: Path, expected_pages: tuple[str, ...]) -> None:
    if not path.is_file() or path.is_symlink():
        raise ReviewPackError(
            EXIT_UNSAFE_OUTPUT, "existing output has an unsafe HTML review file"
        )
    try:
        page = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ReviewPackError(
            EXIT_UNSAFE_OUTPUT, "existing output has an invalid HTML review file"
        ) from error
    if page not in expected_pages:
        raise ReviewPackError(
            EXIT_UNSAFE_OUTPUT, "existing output has an invalid HTML review file"
        )


def validate_owned_review_pack(output: Path) -> None:
    marker = _load_json_object(output / OWNER_MARKER_NAME, "ownership marker")
    if marker != OWNER_MARKER:
        raise ReviewPackError(
            EXIT_UNSAFE_OUTPUT,
            "existing output has no valid ownership marker",
        )

    manifest = _load_json_object(output / "manifest.json", "review manifest")
    if set(manifest) != {"images", "schema_version"}:
        raise ReviewPackError(
            EXIT_UNSAFE_OUTPUT,
            "existing output has an invalid review manifest",
        )
    if (
        manifest["schema_version"] != MANIFEST_SCHEMA_VERSION
        or not isinstance(manifest["images"], list)
        or not manifest["images"]
    ):
        raise ReviewPackError(
            EXIT_UNSAFE_OUTPUT,
            "existing output has an invalid review manifest",
        )

    thumbnail_root = output / "thumbnails"
    if not thumbnail_root.is_dir() or thumbnail_root.is_symlink():
        raise ReviewPackError(
            EXIT_UNSAFE_OUTPUT,
            "existing output has an invalid thumbnail directory",
        )

    expected_thumbnails: set[Path] = set()
    for record in manifest["images"]:
        if not isinstance(record, dict) or set(record) != MANIFEST_RECORD_FIELDS:
            raise ReviewPackError(
                EXIT_UNSAFE_OUTPUT,
                "existing output has an invalid review manifest",
            )
        source_path = record["source_path"]
        dimensions = (
            record["width"],
            record["height"],
            record["thumbnail_width"],
            record["thumbnail_height"],
        )
        if (
            not isinstance(source_path, str)
            or not source_path
            or Path(source_path).name != source_path
            or not isinstance(record["mode"], str)
            or not record["mode"]
            or record["orientation"] != 1
            or not isinstance(record["source_orientation"], int)
            or any(not isinstance(value, int) or value < 1 for value in dimensions)
            or not isinstance(record["sha256"], str)
            or len(record["sha256"]) != 64
            or any(character not in "0123456789abcdef" for character in record["sha256"])
        ):
            raise ReviewPackError(
                EXIT_UNSAFE_OUTPUT,
                "existing output has an invalid review manifest",
            )
        relative = record.get("thumbnail_path")
        if not isinstance(relative, str):
            raise ReviewPackError(
                EXIT_UNSAFE_OUTPUT,
                "existing output has an invalid review manifest",
            )
        relative_path = Path(relative)
        if (
            relative_path.is_absolute()
            or ".." in relative_path.parts
            or not relative_path.parts
            or relative_path.parts[0] != "thumbnails"
        ):
            raise ReviewPackError(
                EXIT_UNSAFE_OUTPUT,
                "existing output has an unsafe thumbnail path",
            )
        thumbnail = output / relative_path
        if not thumbnail.is_file() or thumbnail.is_symlink():
            raise ReviewPackError(
                EXIT_UNSAFE_OUTPUT,
                "existing output has a missing or unsafe thumbnail",
            )
        try:
            with Image.open(thumbnail) as opened:
                opened.load()
                if opened.format != "PNG" or opened.size != dimensions[2:]:
                    raise ReviewPackError(
                        EXIT_UNSAFE_OUTPUT,
                        "existing output has an invalid thumbnail",
                    )
        except (OSError, UnidentifiedImageError, ValueError) as error:
            raise ReviewPackError(
                EXIT_UNSAFE_OUTPUT,
                "existing output has an invalid thumbnail",
            ) from error
        if relative_path in expected_thumbnails:
            raise ReviewPackError(
                EXIT_UNSAFE_OUTPUT,
                "existing output has duplicate thumbnail paths",
            )
        expected_thumbnails.add(relative_path)

    thumbnail_entries = list(thumbnail_root.iterdir())
    actual_thumbnails = {path.relative_to(output) for path in thumbnail_entries}
    if actual_thumbnails != expected_thumbnails or any(
        not path.is_file() or path.is_symlink() for path in thumbnail_entries
    ):
        raise ReviewPackError(
            EXIT_UNSAFE_OUTPUT,
            "existing output has unexpected thumbnail contents",
        )

    allowed_top_level = {OWNER_MARKER_NAME, "manifest.json", "thumbnails"}
    review_path = output / "review.json"
    review = None
    if review_path.exists():
        review = _load_json_object(review_path, "review projection")
        validate_review_projection(review, manifest["images"])
        allowed_top_level.add("review.json")
    index = output / "index.html"
    if index.exists():
        if review is not None:
            expected_pages = (render_html(review),)
        else:
            expected_pages = (
                render_html(build_legacy_review(manifest["images"])),
                render_v01_legacy_html(manifest["images"]),
            )
        validate_review_html(index, expected_pages)
        allowed_top_level.add("index.html")
    if review_path.exists() and not index.exists():
        raise ReviewPackError(
            EXIT_UNSAFE_OUTPUT,
            "existing output has a review projection without an HTML review file",
        )
    if {path.name for path in output.iterdir()} != allowed_top_level:
        raise ReviewPackError(
            EXIT_UNSAFE_OUTPUT,
            "existing output contains files not owned by this review pack",
        )


def prepare_output(
    destination: Path, sources: Sequence[Path], overwrite: bool
) -> tuple[Path, Path]:
    expanded = destination.expanduser()
    if expanded.is_symlink():
        raise ReviewPackError(
            EXIT_UNSAFE_OUTPUT,
            "output cannot be a symbolic link",
        )
    output = expanded.resolve()
    if is_high_risk_destination(output):
        raise ReviewPackError(
            EXIT_UNSAFE_OUTPUT,
            "output is a protected high-risk destination",
        )
    for source in sources:
        try:
            source.resolve().relative_to(output)
        except ValueError:
            continue
        raise ReviewPackError(
            EXIT_UNSAFE_OUTPUT,
            f"output cannot contain source image: {source.name!r}",
        )
    if output.exists() and not overwrite:
        raise ReviewPackError(
            EXIT_UNSAFE_OUTPUT,
            f"output already exists: {output.name!r}; pass --overwrite to replace it",
        )
    if output.exists() and not output.is_dir():
        raise ReviewPackError(
            EXIT_UNSAFE_OUTPUT,
            f"output exists and is not a directory: {output.name!r}",
        )
    if output.exists() and overwrite:
        validate_owned_review_pack(output)
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        staging = output.parent / f".{output.name}.staging-{uuid.uuid4().hex}"
        staging.mkdir()
    except OSError as error:
        raise ReviewPackError(
            EXIT_UNSAFE_OUTPUT,
            f"cannot prepare output: {error_kind(error)}",
        ) from error
    return output, staging


def render_thumbnail(
    source: Path,
    thumbnail_path: Path,
    thumbnail_relative: Path,
    edge: int,
) -> dict[str, Any]:
    try:
        source_hash = sha256_file(source)
        with Image.open(source) as opened:
            source_orientation = opened.getexif().get(274, 1)
            normalized = ImageOps.exif_transpose(opened)
            normalized.load()
            width, height = normalized.size
            mode = normalized.mode
            if max(normalized.size) <= edge:
                thumbnail = normalized.copy()
            else:
                thumbnail = ImageOps.contain(
                    normalized, (edge, edge), method=Image.Resampling.LANCZOS
                )
            thumbnail.save(thumbnail_path, format="PNG")
    except (OSError, UnidentifiedImageError, ValueError) as error:
        raise ReviewPackError(
            EXIT_UNREADABLE_IMAGE,
            f"cannot read a supported image: {error_kind(error)}",
        ) from error

    return {
        "height": height,
        "mode": mode,
        "orientation": 1,
        "sha256": source_hash,
        "source_orientation": source_orientation,
        "source_path": source.name,
        "thumbnail_height": thumbnail.height,
        "thumbnail_path": thumbnail_relative.as_posix(),
        "thumbnail_width": thumbnail.width,
        "width": width,
    }


def write_manifest(staging: Path, records: list[dict[str, Any]]) -> None:
    manifest = {"images": records, "schema_version": MANIFEST_SCHEMA_VERSION}
    payload = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    (staging / "manifest.json").write_text(payload, encoding="utf-8")


def write_owner_marker(staging: Path) -> None:
    payload = json.dumps(OWNER_MARKER, indent=2, sort_keys=True) + "\n"
    (staging / OWNER_MARKER_NAME).write_text(payload, encoding="utf-8")


def write_review_json(staging: Path, review: dict[str, Any]) -> None:
    payload = json.dumps(review, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    (staging / "review.json").write_text(payload, encoding="utf-8")


def build_legacy_review(records: list[dict[str, Any]]) -> dict[str, Any]:
    assets = []
    for record in records:
        assets.append(
            {
                "height": record["height"],
                "identity": {
                    "en": "No structured identity lock supplied.",
                    "zh": "未提供结构化身份锁定信息。",
                },
                "mode": record["mode"],
                "qa": {
                    "en": "Technical thumbnail only; no QA claim.",
                    "zh": "仅供技术缩略图审阅，不代表质检结论。",
                },
                "role": "technical-review",
                "sha256": record["sha256"],
                "source_path": record["source_path"],
                "stage": "qa-delivery",
                "status": "draft",
                "summary": {
                    "en": "Inspect the contained thumbnail and source metadata.",
                    "zh": "检查完整显示的缩略图与源文件技术信息。",
                },
                "thumbnail_path": record["thumbnail_path"],
                "title": {"en": record["source_path"], "zh": record["source_path"]},
                "width": record["width"],
            }
        )
    return {
        "assets": assets,
        "delivery_status": "draft",
        "direction": {"en": "Not specified", "zh": "未指定"},
        "product": {
            "name": {"en": "Local image set", "zh": "本地图像集"},
            "summary": {
                "en": f"{len(records)} source image(s) prepared for offline review.",
                "zh": f"已准备 {len(records)} 张源图像供离线审阅。",
            },
        },
        "schema_version": REVIEW_SCHEMA_VERSION,
        "stages": [
            {
                "id": "qa-delivery",
                "label": STAGE_LABELS["qa-delivery"],
                "status": "draft",
            }
        ],
        "title": {"en": "Review pack", "zh": "审阅包"},
    }


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _bilingual_html(value: dict[str, str], class_name: str = "") -> str:
    class_attribute = f' class="{_escape(class_name)}"' if class_name else ""
    return (
        f'<span{class_attribute} data-lang="en">{_escape(value["en"])}</span>'
        f'<span{class_attribute} data-lang="zh" lang="zh-CN">{_escape(value["zh"])}</span>'
    )


def _status_html(status: str) -> str:
    labels = {
        "passed": {"en": "Passed", "zh": "已通过"},
        "draft": {"en": "Draft", "zh": "草稿"},
        "blocked": {"en": "Blocked", "zh": "受阻"},
        "missing": {"en": "Missing", "zh": "缺失"},
    }
    return (
        f'<span class="status status-{_escape(status)}">'
        f'{_bilingual_html(labels[status])}</span>'
    )


def render_html(review: dict[str, Any]) -> str:
    stage_buttons = [
        (
            '<button type="button" class="stage-button is-active" '
            'data-filter-stage="all" aria-pressed="true" '
            'aria-controls="review-assets">'
            f'{_bilingual_html({"en": "All stages", "zh": "全部阶段"})}'
            "</button>"
        )
    ]
    for stage in review["stages"]:
        stage_buttons.append(
            (
                '<button type="button" class="stage-button" '
                f'data-filter-stage="{_escape(stage["id"])}" aria-pressed="false" '
                'aria-controls="review-assets">'
                f'<span class="stage-name">{_bilingual_html(stage["label"])}</span>'
                f'{_status_html(stage["status"])}'
                "</button>"
            )
        )

    present_roles = sorted(
        {asset["role"] for asset in review["assets"]}, key=lambda role: ROLE_ORDER[role]
    )
    role_buttons = [
        (
            '<button type="button" class="role-button is-active" data-filter-role="all" '
            'aria-pressed="true" aria-controls="review-assets">'
            f'{_bilingual_html({"en": "All roles", "zh": "全部角色"})}</button>'
        )
    ]
    for role in present_roles:
        role_buttons.append(
            (
                '<button type="button" class="role-button" '
                f'data-filter-role="{_escape(role)}" aria-pressed="false" '
                'aria-controls="review-assets">'
                f'{_bilingual_html(ROLE_LABELS[role])}</button>'
            )
        )

    asset_entries = []
    for asset in review["assets"]:
        alt = f'{asset["title"]["en"]} / {asset["title"]["zh"]}'
        stage_label = STAGE_LABELS[asset["stage"]]
        role_label = ROLE_LABELS[asset["role"]]
        asset_entries.append(
            "".join(
                [
                    '<article class="asset-card" ',
                    f'data-stage="{_escape(asset["stage"])}" ',
                    f'data-role="{_escape(asset["role"])}">',
                    '<figure class="image-frame">',
                    f'<img src="{_escape(asset["thumbnail_path"])}" alt="{_escape(alt)}" ',
                    f'width="{asset["width"]}" height="{asset["height"]}">',
                    "</figure>",
                    '<div class="asset-content">',
                    '<div class="asset-heading"><div>',
                    f'<p class="asset-context">{_bilingual_html(stage_label)} · '
                    f'{_bilingual_html(role_label)}</p>',
                    f'<h2>{_bilingual_html(asset["title"])}</h2>',
                    f'</div>{_status_html(asset["status"])}</div>',
                    f'<p class="asset-summary">{_bilingual_html(asset["summary"])}</p>',
                    '<dl class="review-notes">',
                    f'<div><dt>{_bilingual_html({"en": "Identity", "zh": "身份"})}</dt>',
                    f'<dd>{_bilingual_html(asset["identity"])}</dd></div>',
                    f'<div><dt>{_bilingual_html({"en": "QA", "zh": "质检"})}</dt>',
                    f'<dd>{_bilingual_html(asset["qa"])}</dd></div>',
                    "</dl>",
                    '<dl class="technical-data">',
                    f'<div><dt>File / 文件</dt><dd>{_escape(asset["source_path"])}</dd></div>',
                    f'<div><dt>Size / 尺寸</dt><dd>{asset["width"]} × {asset["height"]}</dd></div>',
                    f'<div><dt>Mode / 模式</dt><dd>{_escape(asset["mode"])}</dd></div>',
                    f'<div class="hash-row"><dt>SHA-256</dt><dd>{_escape(asset["sha256"])}</dd></div>',
                    "</dl></div></article>",
                ]
            )
        )

    css = """
:root {
  color-scheme: light;
  --canvas: #F3F5F7;
  --surface: #FFFFFF;
  --ink: #17212B;
  --muted: #5D6975;
  --lemon: #D9A928;
  --berry: #A63A5B;
  --success: #287A55;
  --danger: #B54343;
  --line: #D9DEE3;
  font-family: "Avenir Next", "Helvetica Neue", "Noto Sans SC", sans-serif;
}
* { box-sizing: border-box; }
body { margin: 0; color: var(--ink); background: var(--canvas); line-height: 1.5; }
button { font: inherit; color: inherit; }
button:focus-visible { outline: 3px solid var(--lemon); outline-offset: 2px; }
[data-lang], .technical-data dd { overflow-wrap: anywhere; word-break: break-word; }
[hidden] { display: none !important; }
html[data-enhanced="true"][data-language="en"] [data-lang="zh"],
html[data-enhanced="true"][data-language="zh"] [data-lang="en"] { display: none; }
html:not([data-enhanced="true"]) [data-lang="zh"]::before,
html[data-language="all"] [data-lang="zh"]::before { content: " / "; color: var(--muted); }
.topbar { min-height: 68px; padding: 12px 24px; display: flex; align-items: center; justify-content: space-between; gap: 20px; background: var(--surface); border-bottom: 1px solid var(--line); }
.brand-title { margin: 0; font-size: 16px; font-weight: 700; }
.brand-subtitle { margin: 2px 0 0; color: var(--muted); font-size: 12px; }
.language-control { display: inline-flex; padding: 3px; border: 1px solid var(--line); border-radius: 8px; background: var(--canvas); }
.language-control button { min-width: 52px; min-height: 32px; padding: 4px 10px; border: 0; border-radius: 5px; background: transparent; cursor: pointer; }
.language-control button[aria-pressed="true"] { color: var(--surface); background: var(--ink); }
.review-shell { display: grid; grid-template-columns: 232px minmax(0, 1fr); max-width: 1440px; margin: 0 auto; }
.stage-rail { position: sticky; top: 0; align-self: start; height: 100vh; padding: 22px 16px; overflow-y: auto; background: var(--surface); border-right: 1px solid var(--line); }
.rail-heading, .filter-heading { margin: 0 0 10px; color: var(--muted); font-size: 12px; font-weight: 700; }
.stage-list { display: grid; gap: 6px; }
.stage-button { width: 100%; min-height: 48px; padding: 8px 10px; display: flex; align-items: center; justify-content: space-between; gap: 8px; text-align: left; border: 1px solid transparent; border-radius: 6px; background: transparent; cursor: pointer; }
.stage-button:hover { background: var(--canvas); }
.stage-button.is-active { border-color: var(--ink); background: var(--canvas); }
.stage-name { min-width: 0; font-size: 13px; font-weight: 600; }
.status { display: inline-flex; min-height: 24px; align-items: center; flex: 0 0 auto; padding: 2px 7px; border: 1px solid currentColor; border-radius: 4px; font-size: 11px; font-weight: 700; }
.status-passed { color: var(--success); }
.status-draft { color: #745B14; background: #FFF9E8; }
.status-blocked, .status-missing { color: var(--danger); }
.review-main { min-width: 0; padding: 22px 28px 48px; }
.summary-band { display: grid; grid-template-columns: minmax(0, 1fr) minmax(220px, 0.42fr); gap: 28px; padding: 4px 0 22px; border-bottom: 1px solid var(--line); }
.summary-band > *, .asset-heading > *, .review-notes dd { min-width: 0; }
.summary-band h1 { margin: 0; font-size: 32px; line-height: 1.15; letter-spacing: 0; }
.product-name { margin: 12px 0 4px; font-size: 18px; font-weight: 700; }
.product-summary { max-width: 68ch; margin: 0; color: var(--muted); }
.delivery-block { padding-left: 18px; border-left: 4px solid var(--berry); align-self: center; }
.delivery-label { margin: 0 0 6px; color: var(--muted); font-size: 12px; font-weight: 700; }
.direction-value { margin: 10px 0 0; font-size: 14px; }
.role-filter { padding: 18px 0 14px; }
.role-list { display: flex; gap: 7px; overflow-x: auto; padding: 2px 2px 6px; scrollbar-width: thin; }
.role-button { min-width: max-content; min-height: 36px; padding: 6px 11px; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); cursor: pointer; }
.role-button.is-active { color: var(--surface); border-color: var(--ink); background: var(--ink); }
.asset-list { display: grid; gap: 14px; }
.asset-card { display: grid; grid-template-columns: minmax(260px, 38%) minmax(0, 1fr); min-height: 300px; overflow: hidden; background: var(--surface); border: 1px solid var(--line); border-radius: 8px; }
.image-frame { min-width: 0; min-height: 300px; margin: 0; display: grid; place-items: center; padding: 18px; background: #E9EDF0; border-right: 1px solid var(--line); }
.image-frame img { display: block; width: 100%; height: 100%; max-height: 420px; object-fit: contain; }
.asset-content { min-width: 0; padding: 20px; }
.asset-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.asset-context { margin: 0 0 5px; color: var(--berry); font-size: 12px; font-weight: 700; }
.asset-card h2 { margin: 0; font-size: 20px; line-height: 1.25; letter-spacing: 0; }
.asset-summary { margin: 10px 0 16px; color: var(--muted); }
.review-notes, .technical-data { margin: 0; }
.review-notes > div { display: grid; grid-template-columns: 76px minmax(0, 1fr); gap: 10px; padding: 8px 0; border-top: 1px solid var(--line); }
dt { color: var(--muted); font-size: 12px; font-weight: 700; }
dd { min-width: 0; margin: 0; }
.technical-data { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px 14px; margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--line); }
.technical-data dd { font-size: 12px; }
.hash-row { grid-column: 1 / -1; }
.hash-row dd { color: var(--muted); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
@media (max-width: 760px) {
  .topbar { padding: 10px 14px; align-items: flex-start; }
  .brand-subtitle { display: none; }
  .review-shell { display: block; }
  .stage-rail { position: static; width: 100%; height: auto; padding: 12px 14px; overflow: visible; border-right: 0; border-bottom: 1px solid var(--line); }
  .rail-heading { margin-bottom: 7px; }
  .stage-list { display: flex; gap: 7px; overflow-x: auto; padding: 2px 2px 7px; scrollbar-width: thin; }
  .stage-button { width: auto; min-width: 178px; min-height: 44px; }
  .review-main { padding: 18px 14px 36px; }
  .summary-band { grid-template-columns: 1fr; gap: 15px; }
  .summary-band h1 { font-size: 26px; }
  .delivery-block { padding: 12px 0 0; border-left: 0; border-top: 4px solid var(--berry); }
  .asset-card { grid-template-columns: 1fr; min-height: 0; }
  .image-frame { min-height: 260px; border-right: 0; border-bottom: 1px solid var(--line); }
  .asset-content { padding: 16px; }
  .asset-heading { gap: 10px; }
  .technical-data { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { scroll-behavior: auto !important; transition-duration: 0.01ms !important; }
}
"""
    script = """
(() => {
  const root = document.documentElement;
  const assets = Array.from(document.querySelectorAll(".asset-card"));
  let activeStage = "all";
  let activeRole = "all";

  const setPressed = (selector, attribute, value) => {
    document.querySelectorAll(selector).forEach((button) => {
      const selected = button.dataset[attribute] === value;
      button.setAttribute("aria-pressed", String(selected));
      button.classList.toggle("is-active", selected);
    });
  };

  const updateAssets = () => {
    assets.forEach((asset) => {
      const stageMatches = activeStage === "all" || asset.dataset.stage === activeStage;
      const roleMatches = activeRole === "all" || asset.dataset.role === activeRole;
      asset.hidden = !(stageMatches && roleMatches);
    });
  };

  document.querySelectorAll("[data-language-option]").forEach((button) => {
    button.addEventListener("click", () => {
      const language = button.dataset.languageOption;
      root.dataset.language = language;
      root.lang = language === "zh" ? "zh-CN" : "en";
      setPressed("[data-language-option]", "languageOption", language);
    });
  });
  document.querySelectorAll("[data-filter-stage]").forEach((button) => {
    button.addEventListener("click", () => {
      activeStage = button.dataset.filterStage;
      setPressed("[data-filter-stage]", "filterStage", activeStage);
      updateAssets();
    });
  });
  document.querySelectorAll("[data-filter-role]").forEach((button) => {
    button.addEventListener("click", () => {
      activeRole = button.dataset.filterRole;
      setPressed("[data-filter-role]", "filterRole", activeRole);
      updateAssets();
    });
  });

  root.setAttribute("data-enhanced", "true");
  root.dataset.language = "en";
  setPressed("[data-language-option]", "languageOption", "en");
})();
"""
    page = "".join(
        [
            '<!doctype html><html lang="en" data-language="all"><head>',
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            '<meta name="review-pack-kind" content="packaging-product-visuals-review-pack">',
            '<link rel="icon" href="data:,">',
            f'<title>{_escape(review["title"]["en"])} / {_escape(review["title"]["zh"])}</title>',
            f"<style>{css}</style></head><body>",
            '<header class="topbar"><div><p class="brand-title">',
            _bilingual_html({"en": "Packaging workflow review", "zh": "包装工作流审阅"}),
            '</p><p class="brand-subtitle">',
            _bilingual_html({"en": "Stage, role, identity, and QA", "zh": "阶段、角色、身份与质检"}),
            '</p></div><div class="language-control" role="group" aria-label="Language / 语言">',
            '<button type="button" data-language-option="en" aria-pressed="false">EN</button>',
            '<button type="button" data-language-option="zh" aria-pressed="false">中文</button>',
            "</div></header>",
            '<div class="review-shell"><aside class="stage-rail" aria-label="Workflow stages / 工作流阶段">',
            f'<p class="rail-heading">{_bilingual_html({"en": "Workflow stages", "zh": "工作流阶段"})}</p>',
            f'<nav class="stage-list">{"".join(stage_buttons)}</nav></aside>',
            '<main class="review-main"><section class="summary-band" aria-labelledby="review-title">',
            '<div><h1 id="review-title">',
            _bilingual_html(review["title"]),
            '</h1><p class="product-name">',
            _bilingual_html(review["product"]["name"]),
            '</p><p class="product-summary">',
            _bilingual_html(review["product"]["summary"]),
            '</p></div><div class="delivery-block"><p class="delivery-label">',
            _bilingual_html({"en": "Delivery status", "zh": "交付状态"}),
            "</p>",
            _status_html(review["delivery_status"]),
            '<p class="direction-value">',
            _bilingual_html({"en": "Direction", "zh": "方向"}),
            ": ",
            _bilingual_html(review["direction"]),
            "</p></div></section>",
            '<section class="role-filter" aria-label="Asset roles / 资产角色"><p class="filter-heading">',
            _bilingual_html({"en": "Filter by asset role", "zh": "按资产角色筛选"}),
            f'</p><div class="role-list">{"".join(role_buttons)}</div></section>',
            f'<section id="review-assets" class="asset-list" aria-live="polite">{"".join(asset_entries)}</section>',
            f"</main></div><script>{script}</script></body></html>\n",
        ]
    )
    return page


def write_html(staging: Path, review: dict[str, Any]) -> None:
    (staging / "index.html").write_text(render_html(review), encoding="utf-8")


def write_diagnostic(staging: Path, error: ReviewPackError) -> None:
    payload = {
        "error": str(error),
        "exit_code": error.exit_code,
        "schema_version": 1,
    }
    try:
        (staging / "diagnostic.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except OSError:
        pass


def replace_staging_with_diagnostic(staging: Path, error: ReviewPackError) -> None:
    """Remove partial derivatives before retaining a minimal failure record."""
    try:
        if staging.exists() or staging.is_symlink():
            if staging.is_symlink():
                staging.unlink()
            else:
                shutil.rmtree(staging)
        staging.mkdir()
    except OSError:
        return
    write_diagnostic(staging, error)


def copy_owned_tree(source: Path, destination: Path) -> None:
    destination.mkdir()
    for entry in source.iterdir():
        target = destination / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target, copy_function=shutil.copyfile)
        else:
            shutil.copyfile(entry, target)


def remove_owned_tree(path: Path) -> None:
    for entry in (path, *path.rglob("*")):
        mode = entry.stat(follow_symlinks=False).st_mode
        if entry.is_dir():
            entry.chmod(mode | stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        else:
            entry.chmod(mode | stat.S_IRUSR | stat.S_IWUSR)
    shutil.rmtree(path)


def restore_owned_tree(rollback: Path, output: Path) -> None:
    if output.exists():
        remove_owned_tree(output)
    os.replace(rollback, output)


def replace_output(staging: Path, output: Path, overwrite: bool) -> None:
    if not output.exists():
        try:
            os.replace(staging, output)
        except OSError as error:
            raise ReviewPackError(
                EXIT_UNSAFE_OUTPUT,
                f"cannot finalize output: {error_kind(error)}",
            ) from error
        return

    if not overwrite:
        raise ReviewPackError(
            EXIT_UNSAFE_OUTPUT,
            f"output already exists: {output.name!r}; pass --overwrite to replace it",
        )

    rollback = output.parent / f".{output.name}.rollback-{uuid.uuid4().hex}"
    rollback_validated = False
    replacement_started = False
    try:
        copy_owned_tree(output, rollback)
        validate_owned_review_pack(rollback)
        rollback_validated = True
        replacement_started = True
        remove_owned_tree(output)
        os.replace(staging, output)
    except (OSError, ReviewPackError) as error:
        try:
            if rollback_validated and replacement_started:
                restore_owned_tree(rollback, output)
            elif rollback.exists():
                remove_owned_tree(rollback)
        except OSError as rollback_error:
            raise ReviewPackError(
                EXIT_UNSAFE_OUTPUT,
                "cannot clean or restore the validated rollback copy: "
                f"{error_kind(rollback_error)}",
            ) from rollback_error
        if isinstance(error, ReviewPackError):
            raise
        raise ReviewPackError(
            EXIT_UNSAFE_OUTPUT,
            f"cannot replace output: {error_kind(error)}",
        ) from error

    try:
        remove_owned_tree(rollback)
    except OSError as error:
        failed_new = output.parent / f".{output.name}.failed-new-{uuid.uuid4().hex}"
        try:
            os.replace(output, failed_new)
            os.replace(rollback, output)
            remove_owned_tree(failed_new)
        except OSError as rollback_error:
            raise ReviewPackError(
                EXIT_UNSAFE_OUTPUT,
                "cannot clean the rollback copy or restore the prior output: "
                f"{error_kind(rollback_error)}",
            ) from rollback_error
        raise ReviewPackError(
            EXIT_UNSAFE_OUTPUT,
            f"cannot clean the rollback copy: {error_kind(error)}",
        ) from error


def run(args: argparse.Namespace) -> int:
    validate_runtime()
    sources = normalized_sources(args.source_images)
    output, staging = prepare_output(args.output, sources, args.overwrite)
    try:
        thumbnail_root = staging / "thumbnails"
        thumbnail_root.mkdir()
        records = []
        for source in sources:
            thumbnail_relative = Path("thumbnails") / f"{source.stem}.png"
            records.append(
                render_thumbnail(
                    source,
                    staging / thumbnail_relative,
                    thumbnail_relative,
                    args.thumbnail_edge,
                )
            )
        records.sort(key=lambda record: record["source_path"].casefold())
        write_owner_marker(staging)
        write_manifest(staging, records)
        if args.review_spec is not None:
            review = normalize_review_spec(args.review_spec, sources, records)
            write_review_json(staging, review)
            write_html(staging, review)
        elif args.html:
            write_html(staging, build_legacy_review(records))
        replace_output(staging, output, args.overwrite)
    except ReviewPackError as error:
        replace_staging_with_diagnostic(staging, error)
        raise
    except OSError as error:
        wrapped = ReviewPackError(
            EXIT_UNSAFE_OUTPUT,
            f"cannot write review pack: {error_kind(error)}",
        )
        replace_staging_with_diagnostic(staging, wrapped)
        raise wrapped from error
    except Exception as error:
        wrapped = ReviewPackError(
            EXIT_UNSAFE_OUTPUT,
            "cannot build review pack: unexpected error",
        )
        replace_staging_with_diagnostic(staging, wrapped)
        raise wrapped from error
    return EXIT_SUCCESS


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(parse_args(argv))
    except ReviewPackError as error:
        print(str(error), file=sys.stderr)
        return error.exit_code
    except Exception:
        print("cannot build review pack: unexpected error", file=sys.stderr)
        return EXIT_UNSAFE_OUTPUT


if __name__ == "__main__":
    raise SystemExit(main())
