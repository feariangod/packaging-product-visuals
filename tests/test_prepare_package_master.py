import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parents[1]
SCRIPT = REPO_ROOT / "skills/packaging-product-visuals/scripts/prepare_package_master.py"


def _run(*args):
    return subprocess.run(
        [sys.executable, "-S", str(SCRIPT), *map(str, args)],
        capture_output=True,
        text=True,
    )


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _write_spec(path, spec):
    path.write_text(json.dumps(spec), encoding="utf-8")


def _fixture(tmp_path):
    root = tmp_path / "input"
    root.mkdir()
    files = {
        "artwork/front.html": (
            b'<html><head><link rel="stylesheet" href="../styles/label.css">'
            b'</head><body><img src="../images/mark.svg"><p>Test label</p></body></html>'
        ),
        "styles/label.css": (
            b'@import "shared.css"; @font-face {font-family: Fixture; '
            b'src: url("../fonts/fixture.woff2");} p {font-family: Fixture;}'
        ),
        "styles/shared.css": b"p {color: #123456;}",
        "fonts/fixture.woff2": b"Self-authored opaque font placeholder; not a renderable font.",
        "licenses/fixture.txt": b"Self-authored test fixture. No third-party font is included.",
        "images/mark.svg": b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="1"/></svg>',
        "preview.svg": b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>',
    }
    for name, data in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    roles = ["artwork", "style", "style", "font", "license", "image", "preview"]
    ids = ["front", "label-style", "shared-style", "display-font", "font-license", "mark", "preview"]
    assets = [
        {"id": asset_id, "role": role, "source": name, "sha256": _sha(data)}
        for (name, data), role, asset_id in zip(files.items(), roles, ids)
    ]
    assets[3].update(license_asset_id="font-license", usage_status="unreviewed")
    spec = {
        "schema_version": 1,
        "id": "fictional-master-v1",
        "package_geometry": {
            "form": "folding-carton",
            "dimensions": {"width": 95, "height": 120, "depth": 38},
            "unit": "mm",
        },
        "approved_copy": ["Test label", "50 ml"],
        "palette": ["#123456", "#FAFAFA"],
        "surfaces": [{"id": "front-face", "kind": "planar", "artwork_asset_ids": ["front"]}],
        "counted_objects": [
            {"id": "carton", "label": "carton"},
            {"id": "bottle-left", "label": "bottle"},
            {"id": "bottle-right", "label": "bottle"},
        ],
        "assets": assets,
    }
    path = root / "spec.json"
    _write_spec(path, spec)
    return path, spec, files


def _change_file(path, spec, source, data):
    (path.parent / source).write_bytes(data)
    next(asset for asset in spec["assets"] if asset["source"] == source)["sha256"] = _sha(data)
    _write_spec(path, spec)


def _replace_bundled_asset(output, source, data, dependencies=()):
    (output / "files" / source).write_bytes(data)
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    asset = next(row for row in manifest["assets"] if row["path"] == "files/" + source)
    asset.update(sha256=_sha(data), size_bytes=len(data), dependencies=list(dependencies))
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def test_builds_relocatable_byte_preserving_package_and_checks_without_dependencies(tmp_path):
    path, spec, files = _fixture(tmp_path)
    output = tmp_path / "master"
    result = _run("--spec", path, "--output", output)

    assert result.returncode == 0, result.stderr
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["id"] == spec["id"]
    assert manifest["visible_instance_count"] == 3
    assert manifest["package_geometry"] == spec["package_geometry"]
    assert manifest["validation"] == {
        "file_integrity": "checked",
        "reference_completeness": "checked",
        "visual_qa": "unverified",
        "production_readiness": "unverified",
        "legal_review": "not-performed",
        "publication_allowed": False,
    }
    assert str(tmp_path) not in (output / "manifest.json").read_text()
    by_id = {asset["id"]: asset for asset in manifest["assets"]}
    assert by_id["front"]["dependencies"] == ["label-style", "mark"]
    assert by_id["label-style"]["dependencies"] == ["display-font", "shared-style"]
    assert by_id["display-font"]["license_asset_id"] == "font-license"
    for name, data in files.items():
        assert (output / "files" / name).read_bytes() == data
        assert (path.parent / name).read_bytes() == data

    relocated = tmp_path / "elsewhere"
    output.rename(relocated)
    checked = _run("--check", relocated)
    assert checked.returncode == 0, checked.stderr
    assert json.loads(checked.stdout)["manifest_sha256"] == _sha((relocated / "manifest.json").read_bytes())


def test_same_inputs_produce_identical_manifest_bytes(tmp_path):
    path, _, _ = _fixture(tmp_path)
    for name in ("one", "two"):
        result = _run("--spec", path, "--output", tmp_path / name)
        assert result.returncode == 0, result.stderr
    assert (tmp_path / "one/manifest.json").read_bytes() == (tmp_path / "two/manifest.json").read_bytes()


@pytest.mark.parametrize("kind", ["curved", "flexible"])
def test_nonplanar_surface_mapping_and_user_confirmed_license_remain_unverified(tmp_path, kind):
    path, spec, _ = _fixture(tmp_path)
    spec["surfaces"][0]["kind"] = kind
    spec["assets"][3]["usage_status"] = "user-confirmed"
    _write_spec(path, spec)
    output = tmp_path / "master"
    result = _run("--spec", path, "--output", output)
    assert result.returncode == 0, result.stderr
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["surfaces"][0]["mapping_status"] == "unverified-nonplanar"
    assert manifest["validation"]["legal_review"] == "not-performed"
    assert manifest["validation"]["publication_allowed"] is False


@pytest.mark.parametrize("source", ["/etc/passwd", "../outside.txt", "a/../b.txt", "C:/secrets.txt", "a\\b.txt"])
def test_rejects_unsafe_source_paths_before_creating_output(tmp_path, source):
    path, spec, _ = _fixture(tmp_path)
    spec["assets"][0]["source"] = source
    _write_spec(path, spec)
    output = tmp_path / "master"
    result = _run("--spec", path, "--output", output)
    assert result.returncode == 2
    assert "relative path" in result.stderr
    assert not output.exists()


def test_rejects_source_symlink_escape(tmp_path):
    path, _, _ = _fixture(tmp_path)
    font = path.parent / "fonts/fixture.woff2"
    outside = tmp_path / "outside-font.woff2"
    font.rename(outside)
    font.symlink_to(outside)
    result = _run("--spec", path, "--output", tmp_path / "master")
    assert result.returncode == 2
    assert "symlink" in result.stderr
    assert not (tmp_path / "master").exists()


def test_rejects_output_symlink_and_existing_empty_or_nonempty_directory(tmp_path):
    path, _, _ = _fixture(tmp_path)
    for name in ("empty", "nonempty", "link"):
        target = tmp_path / name
        if name == "link":
            target.symlink_to(tmp_path / "empty", target_is_directory=True)
        else:
            target.mkdir()
        if name == "nonempty":
            (target / "keep.txt").write_text("user data")
        result = _run("--spec", path, "--output", target)
        assert result.returncode == 2
        assert "output" in result.stderr
    assert (tmp_path / "nonempty/keep.txt").read_text() == "user data"
    assert list((tmp_path / "empty").iterdir()) == []


@pytest.mark.parametrize("change", ["hash", "license-link", "license-role", "duplicate-id", "duplicate-path", "case-collision", "surface-link", "duplicate-object"])
def test_rejects_invalid_asset_and_identity_contracts(tmp_path, change):
    path, spec, _ = _fixture(tmp_path)
    if change == "hash":
        spec["assets"][0]["sha256"] = "0" * 64
    elif change == "license-link":
        del spec["assets"][3]["license_asset_id"]
    elif change == "license-role":
        spec["assets"][3]["license_asset_id"] = "mark"
    elif change == "duplicate-id":
        spec["assets"][1]["id"] = "front"
    elif change == "duplicate-path":
        spec["assets"][1]["source"] = "artwork/front.html"
    elif change == "case-collision":
        spec["assets"][1]["source"] = "ARTWORK/front.HTML"
    elif change == "surface-link":
        spec["surfaces"][0]["artwork_asset_ids"] = ["not-present"]
    else:
        spec["counted_objects"][2]["id"] = "bottle-left"
    _write_spec(path, spec)
    result = _run("--spec", path, "--output", tmp_path / "master")
    assert result.returncode == 2
    assert result.stderr.startswith("error:")
    assert not (tmp_path / "master").exists()


def test_missing_referenced_font_fails_even_when_font_exists_but_is_not_listed(tmp_path):
    path, spec, _ = _fixture(tmp_path)
    spec["assets"] = [asset for asset in spec["assets"] if asset["id"] != "display-font"]
    _write_spec(path, spec)
    result = _run("--spec", path, "--output", tmp_path / "master")
    assert result.returncode == 2
    assert "not listed" in result.stderr
    assert not (tmp_path / "master").exists()


@pytest.mark.parametrize("css", [
    b'@font-face {src: url("https://example.invalid/font.woff2")}',
    b'@import "https://example.invalid/style.css";',
    b'@font-face {src: local("Installed font")}',
    b'p {background: url(var(--path))}',
    b'p {background: image-set("picture.png" 1x)}',
    b'p {background: u\\72l("picture.png")}',
    b'p {background: url("../../../outside.png")}',
])
def test_rejects_remote_system_or_unsupported_dynamic_css_dependencies(tmp_path, css):
    path, spec, _ = _fixture(tmp_path)
    _change_file(path, spec, "styles/label.css", css)
    result = _run("--spec", path, "--output", tmp_path / "master")
    assert result.returncode == 2
    assert not (tmp_path / "master").exists()


@pytest.mark.parametrize("html", [
    b'<script>fetch("https://example.invalid")</script>',
    b'<img src="../images/mark.svg" onload="alert(1)">',
    b'<base href="https://example.invalid/"><p>Test</p>',
    b'<img srcset="../images/mark.svg 1x">',
    b'<svg><set attributeName="href" to="https://example.invalid/image.svg"/></svg>',
    b'<applet archive="remote.jar"></applet>',
])
def test_rejects_html_that_cannot_be_statically_bundled(tmp_path, html):
    path, spec, _ = _fixture(tmp_path)
    _change_file(path, spec, "artwork/front.html", html)
    result = _run("--spec", path, "--output", tmp_path / "master")
    assert result.returncode == 2
    assert not (tmp_path / "master").exists()


def test_svg_href_and_paint_server_references_are_checked(tmp_path):
    path, spec, _ = _fixture(tmp_path)
    _change_file(
        path, spec, "images/mark.svg",
        b'<svg xmlns="http://www.w3.org/2000/svg"><image href="missing.svg"/><rect fill="url(#fill)"/></svg>',
    )
    result = _run("--spec", path, "--output", tmp_path / "master")
    assert result.returncode == 2
    assert "not listed" in result.stderr


def test_checks_spaced_inline_svg_resource_urls_inside_html(tmp_path):
    path, spec, _ = _fixture(tmp_path)
    _change_file(path, spec, "artwork/front.html", b'<svg><rect fill="url  (missing.svg#paint)"/></svg>')
    result = _run("--spec", path, "--output", tmp_path / "master")
    assert result.returncode == 2
    assert "not listed" in result.stderr


@pytest.mark.parametrize("mode", ["create", "check"])
@pytest.mark.parametrize("source", ["artwork/front.html", "images/mark.svg"])
@pytest.mark.parametrize("attribute,target", [
    ("fill", "missing.svg#paint"),
    ("filter", "https://example.invalid/filter.svg#filter"),
    ("stroke", "missing.svg#paint"),
    ("clip-path", "missing.svg#clip"),
    ("mask", "missing.svg#mask"),
    ("marker-start", "missing.svg#marker"),
])
def test_rejects_escaped_svg_presentation_urls_during_create_and_check(tmp_path, mode, source, attribute, target):
    path, spec, _ = _fixture(tmp_path)
    output = tmp_path / "master"
    data = (
        '<svg xmlns="http://www.w3.org/2000/svg"><rect '
        + attribute + '="u\\72l(' + target + ')"/></svg>'
    ).encode("utf-8")
    if mode == "check":
        created = _run("--spec", path, "--output", output)
        assert created.returncode == 0, created.stderr
        _replace_bundled_asset(output, source, data)
        result = _run("--check", output)
    else:
        _change_file(path, spec, source, data)
        result = _run("--spec", path, "--output", output)
        assert not output.exists()
    assert result.returncode == 2
    assert "CSS escapes are unsupported" in result.stderr


@pytest.mark.parametrize("mode", ["create", "check"])
@pytest.mark.parametrize("target", ["missing.css", "https://example.invalid/style.css"])
def test_rejects_self_closing_html_style_before_import_during_create_and_check(tmp_path, mode, target):
    path, spec, _ = _fixture(tmp_path)
    output = tmp_path / "master"
    data = ('<html><head><style/>@import "' + target + '";</style></head></html>').encode("utf-8")
    if mode == "check":
        created = _run("--spec", path, "--output", output)
        assert created.returncode == 0, created.stderr
        _replace_bundled_asset(output, "artwork/front.html", data)
        result = _run("--check", output)
    else:
        _change_file(path, spec, "artwork/front.html", data)
        result = _run("--spec", path, "--output", output)
        assert not output.exists()
    assert result.returncode == 2
    assert "self-closing" in result.stderr


def test_keeps_valid_html_void_elements_and_inline_svg_self_closing_graphics(tmp_path):
    path, spec, _ = _fixture(tmp_path)
    _change_file(
        path, spec, "artwork/front.html",
        b'<html><head><link rel="stylesheet" href="../styles/label.css"/></head>'
        b'<body><img src="../images/mark.svg"/><br/><svg><rect fill="#123456"/></svg></body></html>',
    )
    output = tmp_path / "master"
    result = _run("--spec", path, "--output", output)
    assert result.returncode == 0, result.stderr
    checked = _run("--check", output)
    assert checked.returncode == 0, checked.stderr


@pytest.mark.parametrize("mode", ["create", "check"])
@pytest.mark.parametrize("attributes", [
    'rel="modulepreload"',
    'rel="MoDuLePrElOaD"',
    'rel="preload" as="script"',
    'rel="preload" as="ScRiPt"',
])
def test_rejects_script_loading_links_with_a_listed_local_module(tmp_path, mode, attributes):
    path, spec, _ = _fixture(tmp_path)
    module_data = b"export const fixture = true;"
    module_path = path.parent / "scripts/module.js"
    module_path.parent.mkdir()
    module_path.write_bytes(module_data)
    spec["assets"].append({
        "id": "module-script", "role": "image", "source": "scripts/module.js",
        "sha256": _sha(module_data),
    })
    _write_spec(path, spec)
    data = ('<link ' + attributes + ' href="../scripts/module.js">').encode("utf-8")
    output = tmp_path / "master"
    if mode == "check":
        created = _run("--spec", path, "--output", output)
        assert created.returncode == 0, created.stderr
        _replace_bundled_asset(output, "artwork/front.html", data, ["module-script"])
        result = _run("--check", output)
    else:
        _change_file(path, spec, "artwork/front.html", data)
        result = _run("--spec", path, "--output", output)
        assert not output.exists()
    assert result.returncode == 2
    assert "script-loading" in result.stderr


def test_font_face_cannot_hide_an_unlicensed_font_behind_an_image_role(tmp_path):
    path, spec, _ = _fixture(tmp_path)
    _change_file(path, spec, "styles/label.css", b'@font-face {font-family: Hidden; src: url("../images/mark.svg")}')
    result = _run("--spec", path, "--output", tmp_path / "master")
    assert result.returncode == 2
    assert "font role" in result.stderr


@pytest.mark.parametrize("form", ["css-import", "html-stylesheet", "html-font-preload"])
def test_typed_resource_dependencies_require_the_correct_asset_role(tmp_path, form):
    path, spec, _ = _fixture(tmp_path)
    if form == "css-import":
        _change_file(path, spec, "styles/label.css", b'@import url("../images/mark.svg");')
    elif form == "html-stylesheet":
        _change_file(path, spec, "artwork/front.html", b'<link rel="stylesheet" href="../images/mark.svg">')
    else:
        _change_file(path, spec, "artwork/front.html", b'<link rel="preload" as="font" href="../images/mark.svg">')
    result = _run("--spec", path, "--output", tmp_path / "master")
    assert result.returncode == 2
    assert "role" in result.stderr


def test_css_comments_are_not_removed_from_quoted_resource_names(tmp_path):
    path, spec, _ = _fixture(tmp_path)
    _change_file(path, spec, "styles/label.css", b'p {background: url("../images/ma/*ignored*/rk.svg")}')
    result = _run("--spec", path, "--output", tmp_path / "master")
    assert result.returncode == 2


def test_accepts_css_comments_and_percent_encoded_local_spaces(tmp_path):
    path, spec, _ = _fixture(tmp_path)
    old = path.parent / "images/mark.svg"
    old.rename(path.parent / "images/my mark.svg")
    spec["assets"][5]["source"] = "images/my mark.svg"
    _change_file(path, spec, "artwork/front.html", b'<link rel="stylesheet" href="../styles/label.css"><img src="../images/my%20mark.svg">')
    _change_file(path, spec, "styles/shared.css", b'/* url(missing.png) */ p {color: #123456;}')
    result = _run("--spec", path, "--output", tmp_path / "master")
    assert result.returncode == 0, result.stderr


def test_rejects_case_ambiguous_parent_directories_and_source_parent_symlinks(tmp_path):
    path, spec, _ = _fixture(tmp_path)
    spec["assets"][2]["source"] = "STYLES/shared.css"
    _write_spec(path, spec)
    result = _run("--spec", path, "--output", tmp_path / "master")
    assert result.returncode == 2
    assert "ambiguous" in result.stderr
    spec["assets"][2]["source"] = "styles/shared.css"
    _write_spec(path, spec)
    (path.parent / "styles").rename(tmp_path / "styles-outside")
    (path.parent / "styles").symlink_to(tmp_path / "styles-outside", target_is_directory=True)
    result = _run("--spec", path, "--output", tmp_path / "master")
    assert result.returncode == 2
    assert "symlink" in result.stderr


def test_existing_output_parent_symlink_is_not_followed(tmp_path):
    path, _, _ = _fixture(tmp_path)
    real = tmp_path / "real-parent"
    real.mkdir()
    (tmp_path / "alias-parent").symlink_to(real, target_is_directory=True)
    result = _run("--spec", path, "--output", tmp_path / "alias-parent/master")
    assert result.returncode == 2
    assert "output" in result.stderr
    assert list(real.iterdir()) == []


@pytest.mark.parametrize("change", ["content", "missing", "extra", "symlink", "count", "permission", "legal", "unknown-field"])
def test_check_rejects_tampering_and_unexpected_files(tmp_path, change):
    path, _, _ = _fixture(tmp_path)
    output = tmp_path / "master"
    created = _run("--spec", path, "--output", output)
    assert created.returncode == 0, created.stderr
    if change == "content":
        (output / "files/styles/label.css").write_text("modified")
    elif change == "missing":
        (output / "files/fonts/fixture.woff2").unlink()
    elif change == "extra":
        (output / "credentials.txt").write_text("must not be in the package")
    elif change == "symlink":
        (output / "files/escape").symlink_to(tmp_path, target_is_directory=True)
    else:
        manifest_path = output / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        if change == "count":
            manifest["visible_instance_count"] = 2
        elif change == "permission":
            manifest["validation"]["publication_allowed"] = True
        elif change == "legal":
            manifest["validation"]["legal_review"] = "passed"
        else:
            manifest["unknown"] = "not supported"
        _write_spec(manifest_path, manifest)
    result = _run("--check", output)
    assert result.returncode == 2
    assert result.stderr.startswith("error:")


def test_rejects_duplicate_json_keys(tmp_path):
    path, _, _ = _fixture(tmp_path)
    path.write_text(path.read_text().replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1'))
    result = _run("--spec", path, "--output", tmp_path / "master")
    assert result.returncode == 2
    assert "duplicate JSON key" in result.stderr
