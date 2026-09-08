from pathlib import Path

import yaml


SCENARIO_PATH = Path(__file__).parent / "evals" / "baseline-scenarios.yaml"
REQUIRED_KEYS = {
    "id",
    "mode",
    "baseline",
    "permissions",
    "expected_locked_fields",
    "rights_or_capability_pressure",
    "expected_status_semantics",
}


def test_baseline_scenarios_define_all_required_evaluation_fields():
    scenarios = yaml.safe_load(SCENARIO_PATH.read_text(encoding="utf-8"))["scenarios"]

    assert [scenario["mode"] for scenario in scenarios] == [
        "compare",
        "refine",
        "present",
    ]
    assert len({scenario["id"] for scenario in scenarios}) == len(scenarios)

    for scenario in scenarios:
        assert REQUIRED_KEYS <= scenario.keys()
        assert scenario["permissions"]
        assert scenario["expected_locked_fields"]
        assert scenario["expected_status_semantics"]


def test_repository_license_is_apache_2(repo_root=None):
    root = repo_root or Path(__file__).parents[1]
    license_text = (root / "LICENSE").read_text(encoding="utf-8")
    pyproject_text = (root / "pyproject.toml").read_text(encoding="utf-8")

    assert "Apache License" in license_text
    assert "Version 2.0" in license_text
    assert 'license = "Apache-2.0"' in pyproject_text
