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
V01_HELPER = REPO_ROOT / "tests" / "fixtures" / "v0.1.0" / "prepare_review_pack.py"
V01_HELPER_SHA256 = "004d8515e981adb6d2eac651c23ff7051f50a26322cc8f6883ee99c273515d6b"


def _run(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)],
        cwd=cwd or REPO_ROOT,
        capture_output=True,
        text=True,
    )


def _run_v01_helper(*args, cwd=None):
    legacy_bytes = V01_HELPER.read_bytes()
    assert hashlib.sha256(legacy_bytes).hexdigest() == V01_HELPER_SHA256
    return subprocess.run(
        [sys.executable, "-", *map(str, args)],
        cwd=cwd or REPO_ROOT,
        input=legacy_bytes.decode("utf-8"),
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


def _write_review_spec(path, sources):
    source_names = [Path(source).name for source in sources]
    payload = {
        "schema_version": 1,
        "title": {"en": "Pantry packaging review", "zh": "食品包装审阅"},
        "product": {
            "name": {"en": "Citrus Pantry Mix", "zh": "柑橘谷物冲调粉"},
            "summary": {
                "en": "Two-SKU fictional pouch system for review.",
                "zh": "用于审阅的双 SKU 虚构袋装系统。",
            },
        },
        "direction": {"en": "Quiet Pantry", "zh": "静谧食柜"},
        "delivery_status": "draft",
        "stages": [
            {"id": "qa-delivery", "status": "draft"},
            {"id": "packaging-directions", "status": "passed"},
            {"id": "ecommerce-planning", "status": "draft"},
        ],
        "assets": [
            {
                "source": source_names[1],
                "stage": "ecommerce-planning",
                "role": "catalog",
                "status": "draft",
                "title": {"en": "Catalog packshot", "zh": "目录主图"},
                "summary": {
                    "en": "Neutral family lineup for channel review.",
                    "zh": "用于渠道审阅的中性系列陈列。",
                },
                "identity": {
                    "en": "Keep pouch geometry and exact copy.",
                    "zh": "保持袋型与准确文案。",
                },
                "qa": {
                    "en": "Generation is not authorized.",
                    "zh": "尚未授权生成。",
                },
            },
            {
                "source": source_names[0],
                "stage": "packaging-directions",
                "role": "comparison",
                "status": "passed",
                "title": {"en": "Direction board", "zh": "方向对比板"},
                "summary": {
                    "en": "Compare both SKUs under one system.",
                    "zh": "在同一系统下比较两个 SKU。",
                },
                "identity": {
                    "en": "Brand, product name, variants, quantity.",
                    "zh": "品牌、产品名、口味与净含量。",
                },
                "qa": {
                    "en": "Comparison gates passed.",
                    "zh": "对比检查已通过。",
                },
            },
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


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
    assert "Review pack" in html
    assert "审阅包" in html
    assert "80 × 120" in html
    assert source_hash in html
    assert not (destination / "review.json").exists()


def test_overwrite_migrates_authentic_v01_html_pack_without_weakening_validation(
    tmp_path,
):
    source = tmp_path / "legacy tea.png"
    _save_corners(source, size=(80, 120))
    destination = tmp_path / "legacy-review"

    legacy_result = _run_v01_helper("--output", destination, "--html", source)
    assert legacy_result.returncode == 0, legacy_result.stderr
    legacy_page = (destination / "index.html").read_text(encoding="utf-8")
    assert legacy_page.startswith('<!doctype html><html lang="en">')
    assert "Review pack" in legacy_page

    result = _run("--output", destination, "--overwrite", "--html", source)

    assert result.returncode == 0, result.stderr
    migrated_page = (destination / "index.html").read_text(encoding="utf-8")
    assert migrated_page != legacy_page
    assert "Review pack" in migrated_page
    assert "审阅包" in migrated_page


@pytest.mark.parametrize(
    "tampering",
    [
        '<script>fetch("https://example.invalid/private")</script>',
        "<!-- altered -->",
    ],
)
def test_overwrite_rejects_tampered_authentic_v01_html_pack(tmp_path, tampering):
    source = tmp_path / "legacy tea.png"
    _save_corners(source, size=(80, 120))
    destination = tmp_path / "legacy-review"

    legacy_result = _run_v01_helper("--output", destination, "--html", source)
    assert legacy_result.returncode == 0, legacy_result.stderr
    index = destination / "index.html"
    index.write_text(
        index.read_text(encoding="utf-8").replace("</main>", f"{tampering}</main>"),
        encoding="utf-8",
    )
    before = _tree_snapshot(destination)

    result = _run("--output", destination, "--overwrite", "--html", source)

    assert result.returncode == 5
    assert "invalid HTML review file" in result.stderr
    assert _tree_snapshot(destination) == before


def test_review_spec_writes_normalized_semantic_projection_and_bilingual_page(tmp_path):
    direction = tmp_path / "direction.png"
    catalog = tmp_path / "catalog.png"
    _save_corners(direction, size=(120, 80))
    _save_corners(catalog, size=(80, 120))
    spec_path = tmp_path / "review-spec.json"
    _write_review_spec(spec_path, [direction, catalog])
    destination = tmp_path / "workflow-review"

    result = _run(
        "--output",
        destination,
        "--review-spec",
        spec_path,
        catalog,
        direction,
    )

    assert result.returncode == 0, result.stderr
    review = json.loads((destination / "review.json").read_text(encoding="utf-8"))
    assert list(review) == [
        "assets",
        "delivery_status",
        "direction",
        "product",
        "schema_version",
        "stages",
        "title",
    ]
    assert review["schema_version"] == 1
    assert [stage["id"] for stage in review["stages"]] == [
        "packaging-directions",
        "ecommerce-planning",
        "qa-delivery",
    ]
    assert [asset["source_path"] for asset in review["assets"]] == [
        "direction.png",
        "catalog.png",
    ]
    assert review["assets"][0]["thumbnail_path"] == "thumbnails/direction.png"
    assert review["assets"][0]["sha256"] == _sha256(direction)
    assert review["assets"][1]["role"] == "catalog"
    assert review["product"]["name"]["zh"] == "柑橘谷物冲调粉"

    page = (destination / "index.html").read_text(encoding="utf-8")
    assert '<html lang="en" data-language="all">' in page
    assert 'aria-label="Language / 语言"' in page
    assert 'data-language-option="en"' in page
    assert 'data-language-option="zh"' in page
    assert 'data-stage="packaging-directions"' in page
    assert 'data-role="catalog"' in page
    assert 'alt="Direction board / 方向对比板"' in page
    assert "Pantry packaging review" in page
    assert "食品包装审阅" in page
    assert "Keep pouch geometry and exact copy." in page
    assert "保持袋型与准确文案。" in page
    assert page.index("Direction board") < page.index("Catalog packshot")


def test_review_page_is_offline_static_accessible_and_responsive(tmp_path):
    direction = tmp_path / "direction.png"
    catalog = tmp_path / "catalog.png"
    _save_corners(direction)
    _save_corners(catalog)
    spec_path = tmp_path / "review-spec.json"
    _write_review_spec(spec_path, [direction, catalog])
    destination = tmp_path / "workflow-review"

    result = _run(
        "--output", destination, "--review-spec", spec_path, direction, catalog
    )

    assert result.returncode == 0, result.stderr
    page = (destination / "index.html").read_text(encoding="utf-8")
    lowered = page.lower()
    assert "http://" not in lowered
    assert "https://" not in lowered
    assert "cdn" not in lowered
    assert "@import" not in lowered
    assert "innerhtml" not in lowered
    assert "<style>" in page and "<script>" in page
    assert "Avenir Next" in page
    assert "#F3F5F7" in page
    assert "#FFFFFF" in page
    assert "#17212B" in page
    assert "#5D6975" in page
    assert "#D9A928" in page
    assert "#A63A5B" in page
    assert "#287A55" in page
    assert "#B54343" in page
    assert "position: sticky" in page
    assert "@media (max-width: 760px)" in page
    assert "overflow-x: auto" in page
    assert ":focus-visible" in page
    assert "prefers-reduced-motion: reduce" in page
    assert "object-fit: contain" in page
    assert "border-radius: 8px" in page
    assert 'aria-controls="review-assets"' in page
    assert "<noscript>" not in page
    assert "overflow-wrap: anywhere" in page
    assert "word-break: break-word" in page
    assert "3vw" not in page
    assert "clamp(" not in page
    assert 'data-enhanced="true"' in page
    assert page.count("<img ") == 2


def test_review_spec_escapes_all_user_visible_html(tmp_path):
    source = tmp_path / "unsafe&'.png"
    _save_corners(source)
    spec_path = tmp_path / "review-spec.json"
    payload = _write_review_spec(spec_path, [source, source])
    payload["assets"] = [payload["assets"][0]]
    payload["assets"][0]["source"] = source.name
    payload["assets"][0]["title"] = {
        "en": '<script>alert("x")</script>',
        "zh": "<b>不可信</b>",
    }
    spec_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    destination = tmp_path / "escaped"

    result = _run("--output", destination, "--review-spec", spec_path, source)

    assert result.returncode == 0, result.stderr
    page = (destination / "index.html").read_text(encoding="utf-8")
    assert '<script>alert("x")</script>' not in page
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;" in page
    assert "&lt;b&gt;不可信&lt;/b&gt;" in page
    assert 'src="thumbnails/unsafe&amp;&#x27;.png"' in page


@pytest.mark.parametrize(
    ("mutation", "error_text"),
    [
        (lambda spec: spec.update({"unknown": True}), "unknown"),
        (lambda spec: spec["title"].pop("zh"), "bilingual"),
        (lambda spec: spec["stages"].append(spec["stages"][0]), "duplicate stage"),
        (lambda spec: spec["assets"].append(spec["assets"][0]), "duplicate source"),
        (lambda spec: spec["stages"][0].update({"status": "done"}), "status"),
        (lambda spec: spec["assets"][0].update({"role": "hero"}), "role"),
        (lambda spec: spec["assets"][0].update({"stage": "render"}), "stage"),
    ],
)
def test_review_spec_rejects_invalid_schema_without_creating_output(
    tmp_path, mutation, error_text
):
    direction = tmp_path / "direction.png"
    catalog = tmp_path / "catalog.png"
    _save_corners(direction)
    _save_corners(catalog)
    spec_path = tmp_path / "review-spec.json"
    payload = _write_review_spec(spec_path, [direction, catalog])
    mutation(payload)
    spec_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    destination = tmp_path / "invalid-review"

    result = _run(
        "--output", destination, "--review-spec", spec_path, direction, catalog
    )

    assert result.returncode == 2
    assert error_text in result.stderr.lower()
    assert not destination.exists()
    diagnostics = list(tmp_path.glob(".invalid-review.staging-*/diagnostic.json"))
    assert len(diagnostics) == 1
    assert sorted(path.name for path in diagnostics[0].parent.iterdir()) == [
        "diagnostic.json"
    ]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda spec: spec["stages"][0].update({"id": []}),
        lambda spec: spec["assets"][0].update({"stage": {}}),
        lambda spec: spec["assets"][0].update({"role": []}),
        lambda spec: spec.update({"delivery_status": []}),
    ],
)
def test_review_spec_wrong_scalar_types_fail_closed_and_clean_staging(tmp_path, mutate):
    direction = tmp_path / "private-direction.png"
    catalog = tmp_path / "private-catalog.png"
    _save_corners(direction)
    _save_corners(catalog)
    spec_path = tmp_path / "review-spec.json"
    payload = _write_review_spec(spec_path, [direction, catalog])
    mutate(payload)
    spec_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    destination = tmp_path / "wrong-type"

    result = _run(
        "--output", destination, "--review-spec", spec_path, direction, catalog
    )

    assert result.returncode == 2
    assert "traceback" not in result.stderr.lower()
    assert str(tmp_path) not in result.stderr
    assert direction.name not in result.stderr
    assert catalog.name not in result.stderr
    assert not destination.exists()
    diagnostic_path = next(tmp_path.glob(".wrong-type.staging-*/diagnostic.json"))
    assert sorted(path.name for path in diagnostic_path.parent.iterdir()) == [
        "diagnostic.json"
    ]
    diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    assert diagnostic["exit_code"] == 2
    assert str(tmp_path) not in diagnostic["error"]
    assert direction.name not in diagnostic["error"]
    assert catalog.name not in diagnostic["error"]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda spec: spec["assets"][0].update({"status": "blocked"}),
        lambda spec: spec["assets"][0].update({"status": "missing"}),
        lambda spec: spec.update({"delivery_status": "missing"}),
        lambda spec: (
            spec.update({"delivery_status": "passed"}),
            [stage.update({"status": "passed"}) for stage in spec["stages"]],
        ),
        lambda spec: spec["stages"][2].update({"status": "passed"}),
        lambda spec: spec["stages"][2].update({"status": "missing"}),
    ],
)
def test_review_spec_rejects_inconsistent_image_delivery_and_stage_statuses(
    tmp_path, mutate
):
    direction = tmp_path / "direction.png"
    catalog = tmp_path / "catalog.png"
    _save_corners(direction)
    _save_corners(catalog)
    spec_path = tmp_path / "review-spec.json"
    payload = _write_review_spec(spec_path, [direction, catalog])
    mutate(payload)
    spec_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    result = _run(
        "--output",
        tmp_path / "invalid-status",
        "--review-spec",
        spec_path,
        direction,
        catalog,
    )

    assert result.returncode == 2
    assert "status" in result.stderr.lower()


def test_review_spec_accepts_passed_delivery_only_when_all_covered_items_pass(tmp_path):
    direction = tmp_path / "direction.png"
    catalog = tmp_path / "catalog.png"
    _save_corners(direction)
    _save_corners(catalog)
    spec_path = tmp_path / "review-spec.json"
    payload = _write_review_spec(spec_path, [direction, catalog])
    payload["delivery_status"] = "passed"
    for stage in payload["stages"]:
        stage["status"] = "passed"
    for asset in payload["assets"]:
        asset["status"] = "passed"
    spec_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    result = _run(
        "--output",
        tmp_path / "passed-review",
        "--review-spec",
        spec_path,
        direction,
        catalog,
    )

    assert result.returncode == 0, result.stderr
    review = json.loads(
        (tmp_path / "passed-review" / "review.json").read_text(encoding="utf-8")
    )
    assert review["delivery_status"] == "passed"
    assert all(stage["status"] == "passed" for stage in review["stages"])
    assert all(asset["status"] == "passed" for asset in review["assets"])


@pytest.mark.parametrize(
    "unsafe_source",
    ["/tmp/direction.png", "../direction.png", "nested/direction.png", "other.png"],
)
def test_review_spec_rejects_unsafe_or_unmatched_source_refs(tmp_path, unsafe_source):
    direction = tmp_path / "direction.png"
    catalog = tmp_path / "catalog.png"
    _save_corners(direction)
    _save_corners(catalog)
    spec_path = tmp_path / "review-spec.json"
    payload = _write_review_spec(spec_path, [direction, catalog])
    payload["assets"][1]["source"] = unsafe_source
    spec_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    destination = tmp_path / "unsafe-review"

    result = _run(
        "--output", destination, "--review-spec", spec_path, direction, catalog
    )

    assert result.returncode == 2
    assert "source" in result.stderr.lower()
    assert not destination.exists()


def test_review_spec_requires_exactly_one_record_for_every_input_image(tmp_path):
    direction = tmp_path / "direction.png"
    catalog = tmp_path / "catalog.png"
    extra = tmp_path / "extra.png"
    for source in (direction, catalog, extra):
        _save_corners(source)
    spec_path = tmp_path / "review-spec.json"
    _write_review_spec(spec_path, [direction, catalog])

    result = _run(
        "--output",
        tmp_path / "incomplete-review",
        "--review-spec",
        spec_path,
        direction,
        catalog,
        extra,
    )

    assert result.returncode == 2
    assert "match" in result.stderr.lower()


def test_review_spec_failure_diagnostic_does_not_expose_source_names(tmp_path):
    direction = tmp_path / "private-direction.png"
    catalog = tmp_path / "private-catalog.png"
    _save_corners(direction)
    _save_corners(catalog)
    spec_path = tmp_path / "review-spec.json"
    payload = _write_review_spec(spec_path, [direction, catalog])
    payload["assets"][0]["title"].pop("zh")
    spec_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    destination = tmp_path / "private-failure"

    result = _run(
        "--output", destination, "--review-spec", spec_path, direction, catalog
    )

    assert result.returncode == 2
    diagnostic_path = next(tmp_path.glob(".private-failure.staging-*/diagnostic.json"))
    diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    assert direction.name not in diagnostic["error"]
    assert catalog.name not in diagnostic["error"]
    assert str(tmp_path) not in diagnostic["error"]


def test_review_spec_unknown_field_diagnostic_does_not_echo_untrusted_key(tmp_path):
    direction = tmp_path / "direction.png"
    catalog = tmp_path / "catalog.png"
    _save_corners(direction)
    _save_corners(catalog)
    spec_path = tmp_path / "review-spec.json"
    payload = _write_review_spec(spec_path, [direction, catalog])
    private_key = "/" + "Users/customer/秘密项目/private-source.png"
    payload["assets"][0][private_key] = True
    spec_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    destination = tmp_path / "unknown-field"

    result = _run(
        "--output", destination, "--review-spec", spec_path, direction, catalog
    )

    assert result.returncode == 2
    assert "unknown" in result.stderr.lower()
    assert private_key not in result.stderr
    diagnostic_path = next(tmp_path.glob(".unknown-field.staging-*/diagnostic.json"))
    diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    assert private_key not in diagnostic["error"]


def test_review_page_contains_long_user_tokens_without_unbounded_layout_rules(tmp_path):
    direction = tmp_path / "direction.png"
    catalog = tmp_path / "catalog.png"
    _save_corners(direction)
    _save_corners(catalog)
    spec_path = tmp_path / "review-spec.json"
    payload = _write_review_spec(spec_path, [direction, catalog])
    long_token = "LONGTOKEN" * 80
    payload["title"] = {"en": long_token, "zh": long_token}
    payload["product"]["name"] = {"en": long_token, "zh": long_token}
    payload["direction"] = {"en": long_token, "zh": long_token}
    payload["assets"][0]["title"] = {"en": long_token, "zh": long_token}
    payload["assets"][0]["identity"] = {"en": long_token, "zh": long_token}
    spec_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    destination = tmp_path / "long-token-review"

    result = _run(
        "--output", destination, "--review-spec", spec_path, direction, catalog
    )

    assert result.returncode == 0, result.stderr
    page = (destination / "index.html").read_text(encoding="utf-8")
    assert long_token in page
    assert "overflow-wrap: anywhere" in page
    assert "word-break: break-word" in page
    assert "min-width: 0" in page


@pytest.mark.parametrize(
    "corruption", ["review-json", "index-structure", "executable-index"]
)
def test_overwrite_rejects_corrupted_review_projection_or_index(tmp_path, corruption):
    direction = tmp_path / "direction.png"
    catalog = tmp_path / "catalog.png"
    _save_corners(direction)
    _save_corners(catalog)
    spec_path = tmp_path / "review-spec.json"
    _write_review_spec(spec_path, [direction, catalog])
    destination = tmp_path / f"owned-{corruption}"
    initial = _run(
        "--output", destination, "--review-spec", spec_path, direction, catalog
    )
    assert initial.returncode == 0, initial.stderr

    target = destination / ("review.json" if corruption == "review-json" else "index.html")
    if corruption == "review-json":
        target.write_text("{}\n")
    elif corruption == "index-structure":
        target.write_text("<html></html>\n")
    else:
        page = target.read_text(encoding="utf-8")
        target.write_text(
            page.replace(
                "</body>",
                '<script>fetch("https://example.invalid/private?x=1")</script></body>',
            ),
            encoding="utf-8",
        )
    before = _tree_snapshot(destination)

    result = _run(
        "--output",
        destination,
        "--overwrite",
        "--review-spec",
        spec_path,
        direction,
        catalog,
    )

    assert result.returncode == 5
    assert _tree_snapshot(destination) == before
    assert not list(tmp_path.glob(f".{destination.name}.staging-*"))
    assert not list(tmp_path.glob(f".{destination.name}.rollback-*"))


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
