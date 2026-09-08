import hashlib
import json
import runpy
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image


REPO_ROOT = Path(__file__).parents[1]
SCRIPT = REPO_ROOT / "skills" / "packaging-product-visuals" / "scripts" / "prepare_review_pack.py"
OWNER_MARKER_NAME = ".packaging-product-visuals-review-pack.json"


def _run(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)],
        cwd=cwd or REPO_ROOT,
        capture_output=True,
        text=True,
    )


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_snapshot(root):
    directories = sorted(
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_dir()
    )
    files = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }
    return directories, files


def _save_corners(path, mode="RGB", size=(80, 120), exif_orientation=None):
    image = Image.new(mode, size)
    colors = {
        "top_left": (226, 54, 54),
        "top_right": (54, 156, 92),
        "bottom_left": (54, 108, 188),
        "bottom_right": (218, 166, 54),
    }
    if mode == "L":
        colors = {name: index * 60 for index, name in enumerate(colors)}
    image.putpixel((0, 0), colors["top_left"])
    image.putpixel((size[0] - 1, 0), colors["top_right"])
    image.putpixel((0, size[1] - 1), colors["bottom_left"])
    image.putpixel((size[0] - 1, size[1] - 1), colors["bottom_right"])
    if exif_orientation is None:
        image.save(path)
        return
    exif = Image.Exif()
    exif[274] = exif_orientation
    image.save(path, format="JPEG", exif=exif, quality=100, subsampling=0)


def _manifest(destination):
    return json.loads((destination / "manifest.json").read_text(encoding="utf-8"))


def test_help_and_pep_723_dependency_declaration():
    result = _run("--help")

    assert result.returncode == 0
    assert "--output" in result.stdout
    text = SCRIPT.read_text(encoding="utf-8")
    assert "# /// script" in text
    assert 'requires-python = ">=3.10,<3.15"' in text
    assert '"Pillow>=10,<13"' in text


def test_reports_missing_pillow_without_installing(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-S",
            str(SCRIPT),
            "--output",
            str(tmp_path / "out"),
            "source.png",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 3
    assert "Pillow" in result.stderr


def test_creates_canonical_relative_manifest_thumbnails_and_optional_html(tmp_path):
    source = tmp_path / "input folder" / "tea blend.png"
    source.parent.mkdir()
    _save_corners(source, size=(80, 120))
    source_hash = _sha256(source)
    destination = tmp_path / "review pack"

    result = _run(
        "--output",
        destination,
        "--thumbnail-edge",
        "40",
        "--html",
        source,
    )

    assert result.returncode == 0, result.stderr
    assert _sha256(source) == source_hash
    manifest = _manifest(destination)
    assert list(manifest) == ["images", "schema_version"]
    assert manifest["schema_version"] == 1
    marker = json.loads((destination / OWNER_MARKER_NAME).read_text(encoding="utf-8"))
    assert marker == {
        "kind": "packaging-product-visuals-review-pack",
        "schema_version": 1,
    }
    assert len(manifest["images"]) == 1
    record = manifest["images"][0]
    assert record["source_path"] == "tea blend.png"
    assert record["thumbnail_path"] == "thumbnails/tea blend.png"
    assert not Path(record["source_path"]).is_absolute()
    assert not Path(record["thumbnail_path"]).is_absolute()
    assert record["sha256"] == source_hash
    assert record["width"] == 80
    assert record["height"] == 120
    assert record["mode"] == "RGB"
    assert record["orientation"] == 1
    thumbnail = destination / record["thumbnail_path"]
    with Image.open(thumbnail) as image:
        assert image.size == (27, 40)
        assert image.getexif() == {}
    html = (destination / "index.html").read_text(encoding="utf-8")
    assert "tea blend.png" in html
    assert "thumbnails/tea blend.png" in html


@pytest.mark.parametrize("mode", ["RGB", "RGBA", "L"])
def test_supports_common_image_modes_without_mutating_source(tmp_path, mode):
    source = tmp_path / f"{mode}.png"
    _save_corners(source, mode=mode, size=(32, 64))
    source_hash = _sha256(source)
    destination = tmp_path / f"out-{mode}"

    result = _run("--output", destination, source)

    assert result.returncode == 0, result.stderr
    assert _sha256(source) == source_hash
    record = _manifest(destination)["images"][0]
    assert record["mode"] == mode
    with Image.open(destination / record["thumbnail_path"]) as thumbnail:
        assert thumbnail.size == (32, 64)
        assert max(thumbnail.size) <= 320
        assert thumbnail.getexif() == {}


def test_transposes_orientation_before_contain_thumbnail_and_strips_exif(tmp_path):
    source = tmp_path / "rotated.jpg"
    _save_corners(source, size=(60, 100), exif_orientation=6)
    destination = tmp_path / "out"

    result = _run("--output", destination, "--thumbnail-edge", "50", source)

    assert result.returncode == 0, result.stderr
    record = _manifest(destination)["images"][0]
    assert record["width"] == 100
    assert record["height"] == 60
    assert record["orientation"] == 1
    with Image.open(destination / record["thumbnail_path"]) as thumbnail:
        assert thumbnail.size == (50, 30)
        assert thumbnail.getexif() == {}
        blue = thumbnail.getpixel((0, 0))
        assert blue[2] > blue[0]
        assert blue[2] > blue[1]


def test_rejects_empty_input_and_duplicate_stems(tmp_path):
    empty = _run("--output", tmp_path / "empty")
    assert empty.returncode == 2
    assert "source image" in empty.stderr.lower()

    first = tmp_path / "one" / "same.png"
    second = tmp_path / "two" / "same.jpg"
    first.parent.mkdir()
    second.parent.mkdir()
    _save_corners(first)
    _save_corners(second)
    duplicate = _run("--output", tmp_path / "duplicate", first, second)
    assert duplicate.returncode == 2
    assert "duplicate" in duplicate.stderr.lower()


def test_rejects_existing_output_without_overwrite_and_preserves_it(tmp_path):
    source = tmp_path / "source.png"
    _save_corners(source)
    destination = tmp_path / "existing"
    destination.mkdir()
    sentinel = destination / "keep.txt"
    sentinel.write_text("keep")

    result = _run("--output", destination, source)

    assert result.returncode == 5
    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert "exists" in result.stderr.lower()


def test_failure_keeps_source_and_leaves_only_staging_diagnostic(tmp_path):
    source = tmp_path / "a-valid.png"
    _save_corners(source)
    source_hash = _sha256(source)
    damaged = tmp_path / "z-damaged.png"
    damaged.write_bytes(b"not an image")
    destination = tmp_path / "failed-output"

    result = _run("--output", destination, source, damaged)

    assert result.returncode == 4
    assert not destination.exists()
    assert _sha256(source) == source_hash
    diagnostics = list(tmp_path.glob(".failed-output.staging-*/diagnostic.json"))
    assert len(diagnostics) == 1
    staging = diagnostics[0].parent
    assert sorted(path.name for path in staging.iterdir()) == ["diagnostic.json"]
    diagnostic = json.loads(diagnostics[0].read_text(encoding="utf-8"))
    assert diagnostic["exit_code"] == 4
    assert diagnostic["error"]
    assert "source_images" not in diagnostic
    assert source.name not in diagnostic["error"]
    assert damaged.name not in diagnostic["error"]
    assert str(tmp_path) not in diagnostic["error"]


def test_unicode_paths_and_overwrite_produce_deterministic_manifest(tmp_path):
    source = tmp_path / "输入" / "cafe-\u00e9.png"
    source.parent.mkdir()
    _save_corners(source, size=(48, 48))
    first_destination = tmp_path / "first"
    second_destination = tmp_path / "second"

    first = _run("--output", first_destination, source)
    second = _run("--output", second_destination, source)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert (first_destination / "manifest.json").read_bytes() == (
        second_destination / "manifest.json"
    ).read_bytes()
    assert _manifest(first_destination)["images"][0]["source_path"] == "cafe-\u00e9.png"


def test_overwrite_replaces_output_atomically_after_a_complete_build(tmp_path):
    source = tmp_path / "source.png"
    _save_corners(source, size=(80, 120))
    destination = tmp_path / "out"

    initial = _run("--output", destination, source)
    assert initial.returncode == 0, initial.stderr
    initial_hash = _manifest(destination)["images"][0]["sha256"]
    _save_corners(source, size=(120, 80))

    result = _run("--output", destination, "--overwrite", source)

    assert result.returncode == 0, result.stderr
    assert (destination / "manifest.json").is_file()
    assert (destination / OWNER_MARKER_NAME).is_file()
    manifest = _manifest(destination)
    assert manifest["images"][0]["sha256"] != initial_hash
    assert manifest["images"][0]["width"] == 120
    assert manifest["images"][0]["height"] == 80
    assert not list(tmp_path.glob(".out.staging-*"))
    assert not list(tmp_path.glob(".out.rollback-*"))


def test_overwrite_handles_read_only_owned_subdirectory_without_residue(tmp_path):
    source = tmp_path / "source.png"
    _save_corners(source, size=(80, 120))
    destination = tmp_path / "out"
    initial = _run("--output", destination, source)
    assert initial.returncode == 0, initial.stderr

    (destination / "thumbnails").chmod(0o555)
    _save_corners(source, size=(120, 80))
    result = _run("--output", destination, "--overwrite", source)

    assert result.returncode == 0, result.stderr
    assert _manifest(destination)["images"][0]["width"] == 120
    assert not list(tmp_path.glob(".out.rollback-*"))
    assert not list(tmp_path.glob(".out.failed-new-*"))
    assert not list(tmp_path.glob(".out.staging-*"))


def test_overwrite_rolls_back_if_validated_copy_cleanup_fails(tmp_path):
    source = tmp_path / "source.png"
    _save_corners(source, size=(80, 120))
    destination = tmp_path / "out"
    assert _run("--output", destination, source).returncode == 0
    before = _tree_snapshot(destination)

    _save_corners(source, size=(120, 80))
    staging_parent = tmp_path / "new"
    assert _run("--output", staging_parent, source).returncode == 0

    namespace = runpy.run_path(str(SCRIPT))
    replace_output = namespace["replace_output"]
    real_remove = namespace["remove_owned_tree"]
    calls = 0

    def fail_rollback_cleanup(path):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated rollback cleanup failure")
        real_remove(path)

    replace_output.__globals__["remove_owned_tree"] = fail_rollback_cleanup
    with pytest.raises(namespace["ReviewPackError"]):
        replace_output(staging_parent, destination, True)

    assert _tree_snapshot(destination) == before
    assert not list(tmp_path.glob(".out.rollback-*"))
    assert not list(tmp_path.glob(".out.failed-new-*"))


def test_overwrite_copy_failure_never_replaces_original_with_partial_rollback(
    tmp_path, monkeypatch
):
    source = tmp_path / "source.png"
    _save_corners(source, size=(80, 120))
    destination = tmp_path / "out"
    assert _run("--output", destination, source).returncode == 0
    before = _tree_snapshot(destination)

    _save_corners(source, size=(120, 80))
    staging_parent = tmp_path / "new"
    assert _run("--output", staging_parent, source).returncode == 0

    namespace = runpy.run_path(str(SCRIPT))
    replace_output = namespace["replace_output"]
    real_copyfile = namespace["shutil"].copyfile
    calls = 0

    def fail_second_copy(source_path, destination_path):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated copy failure")
        return real_copyfile(source_path, destination_path)

    monkeypatch.setattr(namespace["shutil"], "copyfile", fail_second_copy)
    with pytest.raises(namespace["ReviewPackError"]):
        replace_output(staging_parent, destination, True)

    assert _tree_snapshot(destination) == before
    assert not list(tmp_path.glob(".out.rollback-*"))
    assert staging_parent.is_dir()


def test_overwrite_rollback_validation_failure_leaves_original_untouched(
    tmp_path, monkeypatch
):
    source = tmp_path / "source.png"
    _save_corners(source, size=(80, 120))
    destination = tmp_path / "out"
    assert _run("--output", destination, source).returncode == 0
    before = _tree_snapshot(destination)

    _save_corners(source, size=(120, 80))
    staging_parent = tmp_path / "new"
    assert _run("--output", staging_parent, source).returncode == 0

    namespace = runpy.run_path(str(SCRIPT))
    replace_output = namespace["replace_output"]

    def reject_rollback(_path):
        raise namespace["ReviewPackError"](5, "simulated invalid rollback")

    monkeypatch.setitem(
        replace_output.__globals__, "validate_owned_review_pack", reject_rollback
    )
    with pytest.raises(namespace["ReviewPackError"]):
        replace_output(staging_parent, destination, True)

    assert _tree_snapshot(destination) == before
    assert not list(tmp_path.glob(".out.rollback-*"))
    assert staging_parent.is_dir()


def test_overwrite_rejects_ordinary_directory_and_preserves_every_byte(tmp_path):
    source = tmp_path / "source.png"
    _save_corners(source)
    destination = tmp_path / "ordinary"
    nested = destination / "nested"
    nested.mkdir(parents=True)
    (destination / "keep.bin").write_bytes(b"\x00keep\xff")
    (nested / "also-keep.txt").write_text("keep", encoding="utf-8")
    before = _tree_snapshot(destination)

    result = _run("--output", destination, "--overwrite", source)

    assert result.returncode == 5
    assert "ownership marker" in result.stderr.lower()
    assert _tree_snapshot(destination) == before
    assert not list(tmp_path.glob(".ordinary.staging-*"))
    assert not list(tmp_path.glob(".ordinary.rollback-*"))


@pytest.mark.parametrize("corruption", ["marker", "manifest", "extra-file"])
def test_overwrite_rejects_corrupted_or_mixed_review_pack(tmp_path, corruption):
    source = tmp_path / "source.png"
    _save_corners(source)
    destination = tmp_path / f"pack-{corruption}"
    initial = _run("--output", destination, source)
    assert initial.returncode == 0, initial.stderr

    if corruption == "marker":
        (destination / OWNER_MARKER_NAME).write_text("{}\n", encoding="utf-8")
    elif corruption == "manifest":
        manifest = _manifest(destination)
        manifest["schema_version"] = 999
        (destination / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    else:
        (destination / "unowned.txt").write_text("keep", encoding="utf-8")
    before = _tree_snapshot(destination)

    result = _run("--output", destination, "--overwrite", source)

    assert result.returncode == 5
    assert _tree_snapshot(destination) == before
    assert not list(tmp_path.glob(f".{destination.name}.staging-*"))
    assert not list(tmp_path.glob(f".{destination.name}.rollback-*"))


def test_high_risk_destination_guard_covers_root_home_cwd_repo_and_skill(tmp_path):
    namespace = runpy.run_path(str(SCRIPT))
    is_high_risk_destination = namespace["is_high_risk_destination"]

    assert is_high_risk_destination(Path(Path.cwd().anchor))
    assert is_high_risk_destination(Path.home())
    assert is_high_risk_destination(Path.cwd())
    assert is_high_risk_destination(REPO_ROOT)
    assert is_high_risk_destination(SCRIPT.parents[1])

    simulated_repo = tmp_path / "simulated-repo"
    simulated_repo.mkdir()
    (simulated_repo / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
    assert is_high_risk_destination(simulated_repo)


def test_overwrite_refuses_output_directory_that_contains_a_source(tmp_path):
    destination = tmp_path / "source-tree"
    destination.mkdir()
    source = destination / "source.png"
    _save_corners(source)
    source_hash = _sha256(source)

    result = _run("--output", destination, "--overwrite", source)

    assert result.returncode == 5
    assert "contain source" in result.stderr.lower()
    assert source.is_file()
    assert _sha256(source) == source_hash
