import json
import re
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).parents[1]


def test_release_documentation_and_license_inventory_exist():
    required = {
        "README.md",
        "README.zh-CN.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "CHANGELOG.md",
        "ASSET_LICENSES.md",
        ".github/workflows/validate.yml",
    }
    missing = sorted(path for path in required if not (REPO_ROOT / path).is_file())
    assert not missing, f"missing release files: {missing}"


def test_repository_normalizes_text_line_endings_and_png_binary():
    attributes = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "* text=auto eol=lf" in attributes.splitlines()
    assert "*.png binary" in attributes.splitlines()


def test_security_policy_has_a_private_reporting_route():
    security = (REPO_ROOT / "SECURITY.md").read_text(encoding="utf-8")
    assert "Report a vulnerability" in security
    assert "private vulnerability reporting" in security


def test_readme_states_supported_scope_and_honest_boundaries():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    required_phrases = [
        "compare",
        "refine",
        "present",
        "permissions",
        "external processing",
        "paid",
        "privacy",
        "blocked",
        "draft",
        "passed",
        "concept",
        "production",
        "food and beverage",
        "unverified",
        "fictional pantry",
    ]
    lowered = readme.lower()
    assert all(phrase in lowered for phrase in required_phrases)
    assert "marketplace installation is available" not in lowered
    assert "guaranteed exact text" not in lowered
    assert "production-ready" not in lowered
    assert "all clients are supported" not in lowered


def test_chinese_readme_covers_the_same_release_boundaries():
    readme = (REPO_ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    for phrase in ("compare", "refine", "present", "blocked", "draft", "passed", "食品", "投产"):
        assert phrase.lower() in readme.lower()
    assert "marketplace 安装已提供" not in readme


def test_asset_license_inventory_names_only_owned_fixture_assets():
    text = (REPO_ROOT / "ASSET_LICENSES.md").read_text(encoding="utf-8")
    for asset in ("refine-source.png", "present-source.png", "角标.png"):
        assert asset in text
    assert "Apache-2.0" in text
    assert "third-party" in text.lower()
    assert "private" in text.lower()


def test_ci_has_required_matrix_and_two_validator_steps():
    ci_path = REPO_ROOT / ".github" / "workflows" / "validate.yml"
    assert ci_path.is_file()
    ci = yaml.safe_load(ci_path.read_text(encoding="utf-8"))
    assert ci["jobs"]
    matrix_text = ci_path.read_text(encoding="utf-8")
    assert "ubuntu-latest" in matrix_text
    assert "macos-latest" in matrix_text
    assert "windows-latest" in matrix_text
    assert "3.10" in matrix_text
    assert "3.14" in matrix_text
    assert "pytest" in matrix_text
    assert "skills-ref validate" in matrix_text
    assert "quick_validate.py" in matrix_text
    assert 'python "$CODEX_PLUGIN_VALIDATE" .' in matrix_text


def test_release_files_do_not_embed_absolute_user_paths_or_credentials():
    paths = [REPO_ROOT / name for name in ("README.md", "README.zh-CN.md", "CONTRIBUTING.md", "SECURITY.md", "CHANGELOG.md", "ASSET_LICENSES.md")]
    paths.append(REPO_ROOT / ".github" / "workflows" / "validate.yml")
    suspicious = re.compile(r"/(?:Users|Volumes|home)/|(?:sk|ghp|xoxb)-[A-Za-z0-9_-]{12,}")
    for path in paths:
        if path.is_file():
            assert not suspicious.search(path.read_text(encoding="utf-8")), path
