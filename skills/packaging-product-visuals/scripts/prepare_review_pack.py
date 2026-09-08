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
        help="Also write a simple browser-text HTML review page.",
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
    index = output / "index.html"
    if index.exists():
        if not index.is_file() or index.is_symlink():
            raise ReviewPackError(
                EXIT_UNSAFE_OUTPUT,
                "existing output has an unsafe HTML review file",
            )
        allowed_top_level.add("index.html")
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


def write_html(staging: Path, records: list[dict[str, Any]]) -> None:
    entries = []
    for record in records:
        name = html.escape(record["source_path"])
        thumbnail = html.escape(record["thumbnail_path"])
        entries.append(
            "<article><img src=\"{}\" alt=\"{}\"><p>{}</p></article>".format(
                thumbnail, name, name
            )
        )
    page = "".join(
        [
            "<!doctype html><html lang=\"en\"><meta charset=\"utf-8\">",
            "<title>Review pack</title><main>",
            *entries,
            "</main></html>\n",
        ]
    )
    (staging / "index.html").write_text(page, encoding="utf-8")


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
        if args.html:
            write_html(staging, records)
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
    return EXIT_SUCCESS


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(parse_args(argv))
    except ReviewPackError as error:
        print(str(error), file=sys.stderr)
        return error.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
