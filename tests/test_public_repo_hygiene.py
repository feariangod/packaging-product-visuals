import re
import subprocess
from pathlib import Path

from PIL import Image


REPO_ROOT = Path(__file__).parents[1]
IGNORED_PARTS = {".git", ".venv", ".pytest_cache", "__pycache__", ".superpowers", ".worktrees"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def _candidate_files():
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        yield REPO_ROOT / raw_path.decode()


def _candidate_text_files():
    for path in _candidate_files():
        data = path.read_bytes()
        if b"\0" in data:
            continue
        try:
            yield path, data.decode("utf-8")
        except UnicodeDecodeError:
            continue


def _private_identifier_sentinels():
    return (
        "Yi" + "shi",
        chr(0x76CA) + chr(0x5F0F),
        chr(0x76CA) + chr(0x6C0F),
        "jin" + "tiao",
    )


def _suspicious_patterns():
    absolute_roots = ["/" + part for part in ("Users/", "Volumes/", "home/")]
    private_key_marker = "-" * 5 + "BEGIN " + ".*PRIVATE KEY" + "-" * 5
    placeholder_terms = ("to" + "do", "fix" + "me", "tb" + "d", "lorem" + " ipsum")
    private_identifiers = [
        rf"(?i){re.escape(value)}" for value in _private_identifier_sentinels()
    ]
    return [
        *absolute_roots,
        *private_identifiers,
        "/" + "private/var/",
        private_key_marker,
        r"(?:sk|ghp|xoxb)-[A-Za-z0-9_-]{12,}",
        r"(?i)password\s*[=:]",
        r"(?i)\b(?:" + "|".join(placeholder_terms) + r")\b",
        r"<your[-_][^>]+>",
    ]


def _find_hygiene_issues(text):
    return [pattern for pattern in _suspicious_patterns() if re.search(pattern, text)]


def test_tracked_public_tree_has_no_private_paths_credentials_or_placeholders():
    issues = {}
    for path, text in _candidate_text_files():
        found = _find_hygiene_issues(text) + _find_hygiene_issues(
            path.relative_to(REPO_ROOT).as_posix()
        )
        if found:
            issues[str(path.relative_to(REPO_ROOT))] = found
    assert not issues, issues


def test_every_tracked_non_image_file_is_utf8_text_without_nul_bytes():
    issues = {}
    for path in _candidate_files():
        if path.suffix.lower() in IMAGE_SUFFIXES:
            continue
        data = path.read_bytes()
        if b"\0" in data:
            issues[str(path.relative_to(REPO_ROOT))] = "contains NUL byte"
            continue
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as error:
            issues[str(path.relative_to(REPO_ROOT))] = str(error)
    assert not issues, issues


def test_tracked_images_have_no_exif_or_suspicious_text_metadata():
    issues = {}
    for path in _candidate_files():
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        with Image.open(path) as image:
            found = []
            if image.getexif():
                found.append("EXIF")
            for key, value in image.info.items():
                metadata = value if isinstance(value, str) else repr(value)
                if _find_hygiene_issues(metadata):
                    found.append(str(key))
            if found:
                issues[str(path.relative_to(REPO_ROOT))] = found
    assert not issues, issues


def test_hygiene_scanner_self_test_uses_only_tmp_path(tmp_path):
    sentinel = tmp_path / "sentinel.md"
    sentinel.write_text("/" + "Users/private-user and " + "TO" + "DO")
    assert _find_hygiene_issues(sentinel.read_text(encoding="utf-8"))
    for value in _private_identifier_sentinels():
        assert _find_hygiene_issues(value)
    for value in ("/" + "Users/private-user", "/" + "Volumes/private-drive", "/" + "home/private-user"):
        assert _find_hygiene_issues(value)
    assert not (REPO_ROOT / "sentinel.md").exists()


def test_hygiene_candidate_scan_includes_unignored_public_plan():
    relative_candidates = {
        path.relative_to(REPO_ROOT) for path in _candidate_files()
    }
    assert Path("docs/superpowers/plans/2026-09-08-product-to-ecommerce-workflow.md") in relative_candidates
