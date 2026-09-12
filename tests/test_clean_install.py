import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parents[1]
SOURCE_SKILL = REPO_ROOT / "skills" / "packaging-product-visuals"
HELPER = SOURCE_SKILL / "scripts" / "prepare_review_pack.py"
REQUIRED_INSTALLED_PATHS = {
    "agents/openai.yaml",
    "references/product-and-research.md",
    "references/packaging-directions.md",
    "references/ecommerce-assets.md",
    "references/typography-system.md",
    "references/package-master.md",
    "scripts/prepare_package_master.py",
}


def _tree_digest(root):
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _install_destination(tmp_path, layout):
    if layout == "codex-home":
        return tmp_path / "codex-home" / "skills" / SOURCE_SKILL.name
    if layout == "default-codex-home":
        return tmp_path / "home" / ".codex" / "skills" / SOURCE_SKILL.name
    if layout == "user-agents":
        return tmp_path / "home" / ".agents" / "skills" / SOURCE_SKILL.name
    if layout == "project-agents":
        return tmp_path / "project" / ".agents" / "skills" / SOURCE_SKILL.name
    raise AssertionError(layout)


@pytest.mark.parametrize(
    "layout",
    ["codex-home", "default-codex-home", "user-agents", "project-agents"],
)
def test_clean_install_layout_isolated_from_cwd_and_install_writes(tmp_path, layout):
    assert SOURCE_SKILL.is_dir()
    assert HELPER.is_file(), "review helper is required for clean-install validation"
    assert "# /// script" in HELPER.read_text(encoding="utf-8")
    assert "pillow" in HELPER.read_text(encoding="utf-8").lower()

    destination = _install_destination(tmp_path, layout)
    destination.parent.mkdir(parents=True)
    shutil.copytree(SOURCE_SKILL, destination, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    assert _tree_digest(destination) == _tree_digest(SOURCE_SKILL)
    assert all((destination / path).is_file() for path in REQUIRED_INSTALLED_PATHS)
    installed_skill = (destination / "SKILL.md").read_text(encoding="utf-8")
    reference_links = re.findall(r"\[[^\]]+\]\((references/[^)#]+\.md)(?:#[^)]+)?\)", installed_skill)
    assert reference_links
    assert all((destination / path).is_file() for path in reference_links)
    unrelated_cwd = tmp_path / "unrelated-cwd"
    unrelated_cwd.mkdir()
    before = _tree_digest(destination)

    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")
    env.pop("CODEX_HOME", None)
    if layout == "codex-home":
        env["CODEX_HOME"] = str(tmp_path / "codex-home")

    result = subprocess.run(
        [sys.executable, str(destination / "scripts" / HELPER.name), "--help"],
        cwd=unrelated_cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    master_help = subprocess.run(
        [sys.executable, "-I", "-S", str(destination / "scripts/prepare_package_master.py"), "--help"],
        cwd=unrelated_cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert master_help.returncode == 0, master_help.stderr
    assert "--spec" in master_help.stdout and "--check" in master_help.stdout
    assert _tree_digest(destination) == before
    assert not list(unrelated_cwd.iterdir())
