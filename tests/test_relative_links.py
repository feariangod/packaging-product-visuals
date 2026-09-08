from pathlib import Path

import yaml
from PIL import Image


REPO_ROOT = Path(__file__).parents[1]
FIXTURE_ROOT = REPO_ROOT / "examples" / "fictional-pantry-product"


def _relative_path_values(value, key=""):
    if isinstance(value, dict):
        for child_key, child in value.items():
            yield from _relative_path_values(child, str(child_key))
    elif isinstance(value, list):
        for child in value:
            yield from _relative_path_values(child, key)
    elif isinstance(value, str) and key.lower() in {"locator", "root", "path", "source_path"}:
        yield key, value


def test_fixture_locators_are_relative_and_resolve_inside_fixture():
    for path in FIXTURE_ROOT.glob("*.yaml"):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        for key, locator in _relative_path_values(document):
            assert not Path(locator).is_absolute(), (path.name, key, locator)
            assert not locator.startswith("~"), (path.name, key, locator)
            if locator.startswith("assets/"):
                resolved = (FIXTURE_ROOT / locator).resolve()
                assert FIXTURE_ROOT.resolve() in resolved.parents
                assert resolved.is_file(), (path.name, locator)


def test_owned_fixture_images_have_stable_semantic_markers():
    expected = {
        "refine-source.png": ((640, 800), (226, 54, 54)),
        "present-source.png": ((640, 800), (226, 54, 54)),
        "角标.png": ((64, 64), (226, 54, 54)),
    }
    for name, (size, marker) in expected.items():
        with Image.open(FIXTURE_ROOT / "assets" / name) as image:
            assert image.size == size
            assert image.mode == "RGB"
            assert image.getpixel((0, 0)) == marker
            assert image.getpixel((size[0] - 1, 0)) == (54, 156, 92)
            assert image.getpixel((0, size[1] - 1)) == (54, 108, 188)
            assert image.getpixel((size[0] - 1, size[1] - 1)) == (218, 166, 54)

