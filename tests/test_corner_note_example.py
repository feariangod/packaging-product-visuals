import hashlib
import json
import re
from pathlib import Path

import pytest
from PIL import Image


REPO_ROOT = Path(__file__).parents[1]
CASE_ROOT = REPO_ROOT / "examples/corner-note"
ASSETS = {
    "typography-comparison.png": (
        "32eb80ef4dae8fb84ae162405ee5fe1a748f26923a92845677ea9ca333db1a5f",
        (2400, 1200),
    ),
    "selected-packaging-b.png": (
        "06dece7d22027f6c388ccc1b559184dbd8916a611ec736226c8c3d0bb081d646",
        (1400, 1000),
    ),
    "rain-cedar-hero.png": (
        "b64bf6a60977f3c9287318cf0cdf9de78e44140a00182bf979ce50f69a520a35",
        (1280, 1280),
    ),
    "rain-cedar-hero-thumb-240.png": (
        "09e031b6cf9f60dfeb0d33766054b44a32da4e8b5ca941f6c5b6266c7f008d08",
        (240, 240),
    ),
}


@pytest.mark.parametrize("name", ASSETS)
def test_selected_assets_match_reviewed_originals_without_private_metadata(name):
    path = CASE_ROOT / "assets" / name
    expected_hash, expected_size = ASSETS[name]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash
    with Image.open(path) as image:
        assert image.format == "PNG"
        assert image.mode == "RGB"
        assert image.size == expected_size
        assert not image.getexif()
        assert set(image.info) <= {"dpi"}


def test_case_publication_is_limited_to_selected_assets_and_summary():
    provenance = json.loads((CASE_ROOT / "provenance.json").read_text(encoding="utf-8"))
    expected = {"assets/" + name for name in ASSETS}
    assert {row["path"] for row in provenance["assets"]} == expected
    assert len(provenance["assets"]) == 4
    for row in provenance["assets"]:
        expected_hash, expected_size = ASSETS[Path(row["path"]).name]
        assert row["sha256"] == expected_hash
        assert tuple(row["dimensions_px"]) == expected_size
    assert {p.name for p in (CASE_ROOT / "assets").iterdir()} == set(ASSETS)
    assert {p.relative_to(CASE_ROOT).as_posix() for p in CASE_ROOT.rglob("*") if p.is_file()} == (
        expected | {"README.md", "README.zh-CN.md", "provenance.json"}
    )
    publication = provenance["publication"]
    assert publication["authority"] == "current-user"
    assert publication["date"] == "2026-09-12"
    assert publication["destination"] == "https://github.com/feariangod/packaging-product-visuals"
    assert publication["branch"] == "main"
    assert publication["selected_asset_publication"] is True
    assert publication["historical_generation_publication_allowed"] is False
    assert publication["original_records_modified"] is False
    assert publication["new_generation_authorized"] is False
    assert publication["font_binary_publication"] is False
    assert publication["private_record_publication"] is False
    assert publication["future_asset_publication"] is False


def test_case_does_not_turn_one_hero_or_self_review_into_full_delivery():
    provenance = json.loads((CASE_ROOT / "provenance.json").read_text(encoding="utf-8"))
    delivery = provenance["delivery"]
    assert delivery["completed_hero_skus"] == ["rain-cedar"]
    assert delivery["ecommerce_gallery_complete"] is False
    assert delivery["production_validation"] == "unverified"
    assert delivery["consumer_preference_validation"] == "unverified"
    assert provenance["historical_hero_review"] == {
        "reviewer": "generating-agent",
        "checks_per_profile": 17,
        "profiles": ["full-resolution", "thumbnail-240"],
        "pass_count": 34,
        "independent_review": False,
    }
    thumbnail = next(row for row in provenance["assets"] if row["kind"] == "thumbnail")
    assert thumbnail["derived_from"] == "assets/rain-cedar-hero.png"
    assert set(provenance["fonts"]) == {
        "Zhuque Fangsong", "ZCOOL XiaoWei", "Fraunces", "Ma Shan Zheng",
        "Instrument Serif", "Noto Sans SC", "Barlow Condensed",
    }


def test_bilingual_entrypoints_feature_corner_note_and_case_links_resolve():
    inventory = (REPO_ROOT / "ASSET_LICENSES.md").read_text(encoding="utf-8")
    for name in ASSETS:
        assert "examples/corner-note/assets/" + name in inventory
    for filename, heading in (("README.md", "Public example"), ("README.zh-CN.md", "公开虚构示例")):
        readme = (REPO_ROOT / filename).read_text(encoding="utf-8")
        section = readme.split("## " + heading + "\n", 1)[1].split("\n## ", 1)[0]
        assert "CORNER NOTE" in section
        assert "examples/corner-note/assets/rain-cedar-hero.png" in section
        assert "fictional-pantry-product/generated/" not in section
        assert "examples/corner-note/" + filename in section
    suspicious = re.compile(r"/(?:Users|Volumes|home)/|(?:sk|ghp|xoxb)-[A-Za-z0-9_-]{12,}")
    for path in CASE_ROOT.rglob("*"):
        if path.is_file() and path.suffix in {".md", ".json"}:
            text = path.read_text(encoding="utf-8")
            assert not suspicious.search(text), path
            if path.suffix == ".md":
                for target in re.findall(r"\]\(([^)]+)\)", text):
                    if not target.startswith(("https://", "#")):
                        assert (path.parent / target.split("#", 1)[0]).is_file(), target
