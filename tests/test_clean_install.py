import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parents[1]
SOURCE_SKILL = REPO_ROOT / "skills" / "packaging-product-visuals"
HELPER = SOURCE_SKILL / "scripts" / "prepare_review_pack.py"


def _tree_digest(root):
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
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
    shutil.copytree(SOURCE_SKILL, destination)
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
    assert _tree_digest(destination) == before
    assert not list(unrelated_cwd.iterdir())

