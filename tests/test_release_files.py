import hashlib
import json
import re
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).parents[1]
ENGLISH_HEADINGS = [
    "Workflow",
    "Use the Skill",
    "Design and review",
    "Public example",
    "Installation",
    "Local tools",
    "Safety boundaries",
    "Development",
    "License",
]
CHINESE_HEADINGS = [
    "工作流",
    "使用 Skill",
    "设计与检查",
    "公开虚构示例",
    "安装",
    "本地工具",
    "安全边界",
    "开发",
    "许可",
]
CONTRACT_NAMES = {
    "ProjectState",
    "ProductBrief",
    "ResearchBoard",
    "PackagingOptionMatrix",
    "DecisionLock",
    "SeriesSystem",
    "PackagingDirectionSet",
    "SelectionLock",
    "EcommerceAssetPlan",
    "AssetBrief",
    "DeliveryManifest",
    "RuntimeReceipt",
    "TypographyResearchBoard",
    "TypographySystem",
}
STAGE_IDS = {
    "product-definition",
    "research-options",
    "decision-freeze",
    "packaging-directions",
    "selection-refinement",
    "ecommerce-planning",
    "ecommerce-generation",
    "qa-delivery",
}
ECOMMERCE_ROLES = {
    "catalog",
    "detail",
    "usage",
    "specification",
    "context",
    "campaign",
    "channel-variant",
}
START_STAGE_SEQUENCE = [
    "product-definition",
    "research-options",
    "decision-freeze",
    "packaging-directions",
    "selection-refinement",
    "ecommerce-planning",
    "ecommerce-generation",
    "qa-delivery",
    "selection-refinement",
]
EXPECTED_ROLE_RELATIONS = {
    "catalog": {
        "en": {"Neutral", "identification"},
        "zh": {"中性", "识别"},
    },
    "detail": {
        "en": {"Source-backed", "ingredient", "package-detail"},
        "zh": {"有来源", "原料", "包装细节"},
    },
    "usage": {
        "en": {"Preparation", "unsupported behavior"},
        "zh": {"准备", "不编造", "用法"},
    },
    "specification": {
        "en": {"Dimensions", "quantity", "verified inputs"},
        "zh": {"尺寸", "净含量", "已验证"},
    },
    "context": {
        "en": {"Lifestyle", "approved package identity"},
        "zh": {"生活", "已确认的包装"},
    },
    "campaign": {
        "en": {"Campaign composition", "claims", "packaging"},
        "zh": {"活动构图", "宣称", "包装"},
    },
    "channel-variant": {
        "en": {"Platform crop", "safe area", "approved parent asset"},
        "zh": {"平台裁切", "安全区", "已确认图片"},
    },
}
EXPECTED_ASSET_BRIEF_ROLES = {
    "gallery-catalog": "catalog",
    "gallery-detail": "detail",
    "gallery-usage": "usage",
    "gallery-specification": "specification",
    "gallery-context": "context",
    "gallery-campaign": "campaign",
    "gallery-channel-variant": "channel-variant",
}
LEGACY_PRESENT_RULE_EN = (
    "Generic `present` is legacy compatibility, not a v0.2 ecommerce role: an "
    "unambiguous legacy request may normalize only to one `catalog` draft and must "
    "stop at `ecommerce-planning`; ambiguous legacy input must not expand."
)
LEGACY_PRESENT_RULE_ZH = (
    "通用 `present` 只用于历史兼容，不是 v0.2 电商角色：明确且无歧义的历史请求"
    "最多可规范化为一个 `catalog` draft，并必须停在 `ecommerce-planning`；有歧义的历史输入"
    "不得扩展。"
)
V01_CHANGELOG_SUFFIX_SHA256 = "7fb4819977b803a025bbfeb6fe1b530a271253a9a373cf53839f43a00d1bcb36"


def _h2_headings(text):
    return re.findall(r"^## (.+)$", text, flags=re.MULTILINE)


def _version_after(text, marker):
    match = re.search(rf"{re.escape(marker)}.*?^version = \"([^\"]+)\"", text, re.MULTILINE | re.DOTALL)
    assert match, marker
    return match.group(1)


def _section(text, heading):
    match = re.search(
        rf"^## {re.escape(heading)}\n(?P<body>.*?)(?=^## |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match, heading
    return match.group("body")


def _markdown_table_rows(text, heading, table_index=0):
    lines = _section(text, heading).splitlines()
    tables = []
    current = []
    for line in lines:
        if line.startswith("|"):
            current.append(line)
        elif current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    assert len(tables) > table_index, heading
    table_lines = tables[table_index]
    assert len(table_lines) >= 3, heading

    def cells(line):
        return [cell.strip() for cell in line.strip().strip("|").split("|")]

    headers = cells(table_lines[0])
    rows = [cells(line) for line in table_lines[2:]]
    assert all(len(row) == len(headers) for row in rows), heading
    return headers, rows


def _markdown_table_map(text, heading):
    _, rows = _markdown_table_rows(text, heading)
    return {
        row[0].strip("`"): row[1].strip("`")
        for row in rows
    }


def _deliverables_contract_map(text, heading):
    _, rows = _markdown_table_rows(text, heading)
    return {
        row[0]: set(re.findall(r"`([A-Za-z][A-Za-z0-9]+)`", row[1]))
        for row in rows
    }


def _legacy_present_rule_is_valid(english, chinese):
    return LEGACY_PRESENT_RULE_EN in english and LEGACY_PRESENT_RULE_ZH in chinese


def test_release_documentation_and_license_inventory_exist():
    required = {
        "README.md",
        "README.zh-CN.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "CHANGELOG.md",
        "ASSET_LICENSES.md",
        "docs/maintaining.md",
        "tests/evals/v0.2-humanizer-audit.md",
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
        "permission",
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
        "quiet pantry",
        "fictional",
    ]
    lowered = readme.lower()
    assert all(phrase in lowered for phrase in required_phrases)
    assert "marketplace installation is available" not in lowered
    assert "guaranteed exact text" not in lowered
    assert "production-ready" not in lowered
    assert "all clients are supported" not in lowered
    assert "## supported modes" not in lowered


def test_chinese_readme_covers_the_same_release_boundaries():
    readme = (REPO_ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    for phrase in ("blocked", "draft", "passed", "食品", "投产", "授权", "本地"):
        assert phrase.lower() in readme.lower()
    assert "marketplace 安装已提供" not in readme
    assert "## 三种模式" not in readme


def test_bilingual_readmes_share_the_v02_information_architecture_and_contracts():
    english = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    chinese = (REPO_ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    shared_terms = CONTRACT_NAMES | STAGE_IDS | ECOMMERCE_ROLES
    maintenance = (REPO_ROOT / "docs/maintaining.md").read_text(encoding="utf-8")

    assert _h2_headings(english) == ENGLISH_HEADINGS
    assert _h2_headings(chinese) == CHINESE_HEADINGS
    assert all(term in maintenance for term in shared_terms)
    assert "docs/maintaining.md" in english and "docs/maintaining.md" in chinese
    assert "[简体中文](README.zh-CN.md)" in english
    assert "[English](README.md)" in chinese
    assert "examples/fictional-pantry-product/full-workflow.yaml" in english
    assert "examples/fictional-pantry-product/delivery-manifest.yaml" in english
    assert "examples/fictional-pantry-product/full-workflow.yaml" in chinese
    assert "examples/fictional-pantry-product/delivery-manifest.yaml" in chinese
    assert "Version `0.2.0`" in english
    assert "`0.2.0`" in chinese
    assert "legacy" in maintenance.lower() and "`catalog` draft" in maintenance
    assert "历史" in maintenance
    assert "research" in english.lower()
    assert "ecommerce" in english.lower()
    assert "production" in english.lower()
    assert "调研" in chinese
    assert "电商" in chinese
    assert "投产" in chinese


def test_bilingual_docs_keep_workflow_routing_and_role_coverage():
    english = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    chinese = (REPO_ROOT / "README.zh-CN.md").read_text(encoding="utf-8")

    maintenance = (REPO_ROOT / "docs/maintaining.md").read_text(encoding="utf-8")
    _, start_rows = _markdown_table_rows(maintenance, "Records and routing", table_index=1)
    assert len(start_rows) == 9
    assert all(len(row) == 3 and row[0] and row[1] for row in start_rows)
    assert [row[2].strip("`") for row in start_rows] == START_STAGE_SEQUENCE

    en_workflow = _markdown_table_map(english, "Workflow")
    zh_workflow = _markdown_table_map(chinese, "工作流")
    assert len(en_workflow) == len(zh_workflow) == 7
    assert [step.split(".")[0] for step in en_workflow] == list("1234567")
    assert [step.split(".")[0] for step in zh_workflow] == list("1234567")
    assert "construction" in list(en_workflow.values())[0]
    assert "规格" in list(zh_workflow.values())[0]
    assert "approved" in list(en_workflow.values())[2]
    assert "确认" in list(zh_workflow.values())[2]

    _, role_rows = _markdown_table_rows(maintenance, "Ecommerce roles")
    en_roles = {row[0].strip("`"): row[1] for row in role_rows}
    zh_roles = {row[0].strip("`"): row[2] for row in role_rows}
    assert len(en_roles) == len(zh_roles) == 7
    assert set(en_roles) == set(zh_roles) == ECOMMERCE_ROLES
    assert len(set(en_roles.values())) == len(set(zh_roles.values())) == 7
    for role, expected in EXPECTED_ROLE_RELATIONS.items():
        assert all(token in en_roles[role] for token in expected["en"]), role
        assert all(token in zh_roles[role] for token in expected["zh"]), role


def test_bilingual_maintenance_groups_bind_to_contract_sets_and_reject_swap():
    maintenance = (REPO_ROOT / "docs/maintaining.md").read_text(encoding="utf-8")
    expected_english = {
        "Product and research / 产品与调研": {
            "ProjectState",
            "ProductBrief",
            "ResearchBoard",
            "PackagingOptionMatrix",
            "TypographyResearchBoard",
        },
        "Package decisions / 包装决策": {
            "DecisionLock",
            "SeriesSystem",
            "PackagingDirectionSet",
            "SelectionLock",
            "TypographySystem",
        },
        "Ecommerce planning / 电商规划": {"EcommerceAssetPlan", "AssetBrief"},
        "QA and delivery / 检查与交付": {"DeliveryManifest", "RuntimeReceipt"},
    }
    assert _deliverables_contract_map(maintenance, "Records and routing") == expected_english

    mutated = maintenance.replace(
        "| Product and research / 产品与调研 | `ProjectState`,",
        "| Product and research / 产品与调研 | `DeliveryManifest`,",
        1,
    )
    assert _deliverables_contract_map(mutated, "Records and routing") != expected_english


def test_legacy_present_rule_is_exact_and_rejects_continue_or_expand_mutation():
    english = (REPO_ROOT / "docs/maintaining.md").read_text(encoding="utf-8")
    chinese = english
    assert _legacy_present_rule_is_valid(english, chinese)

    mutated_english = english.replace(
        "must stop at `ecommerce-planning`; ambiguous legacy input must not expand.",
        "may continue after `ecommerce-planning`; ambiguous legacy input may expand.",
    )
    mutated_chinese = chinese.replace(
        "并必须停在 `ecommerce-planning`；有歧义的历史输入不得扩展。",
        "并可继续超过 `ecommerce-planning`；有歧义的历史输入也可扩展。",
    )
    assert not _legacy_present_rule_is_valid(mutated_english, mutated_chinese)


def test_public_example_binds_completed_role_gallery_and_independent_qa():
    example_root = REPO_ROOT / "examples" / "fictional-pantry-product"
    english = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    chinese = (REPO_ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    workflow = yaml.safe_load((example_root / "full-workflow.yaml").read_text(encoding="utf-8"))
    manifest = yaml.safe_load((example_root / "delivery-manifest.yaml").read_text(encoding="utf-8"))
    generation = yaml.safe_load(
        (example_root / "generation-receipt-v0.2-2026-09-09.yaml").read_text(encoding="utf-8")
    )
    qa_result = yaml.safe_load(
        (example_root / "qa-result-v0.2-2026-09-09.yaml").read_text(encoding="utf-8")
    )
    runtime = yaml.safe_load(
        (example_root / "runtime-receipt-v0.2-2026-09-09.yaml").read_text(encoding="utf-8")
    )
    contracts = workflow["contracts"]

    english_example = _section(english, "Public example")
    chinese_example = _section(chinese, "公开虚构示例")
    assert "retrospectively" in english_example and "not real market research" in english_example
    assert "not a default requirement" in english_example
    assert "事后补充" in chinese_example and "不是真实市场调研" in chinese_example
    assert "不是默认要求" in chinese_example
    historical = _section((REPO_ROOT / "docs/maintaining.md").read_text(encoding="utf-8"), "Historical evidence")
    assert "188/188" in historical and "2026-09-09" in historical
    for locator in (
        "qa-result-v0.2-2026-09-09.yaml",
        "runtime-receipt-v0.2-2026-09-09.yaml",
        "review/v0.2/2026-09-09/index.html",
    ):
        assert locator in english_example
        assert locator in chinese_example

    for name in ("selection_lock", "ecommerce_asset_plan"):
        assert contracts[name]["status"] == "passed"
        assert contracts[name]["approved_by"] == "current-user"

    briefs = {brief["id"]: brief for brief in contracts["asset_briefs"]}
    deliveries = {row["requested_artifact_id"]: row for row in manifest["artifacts"]}
    assert len(briefs) == len(deliveries) == 7
    assert set(briefs) == set(deliveries) == set(EXPECTED_ASSET_BRIEF_ROLES)
    assert manifest["requested_artifact_ids"] == list(EXPECTED_ASSET_BRIEF_ROLES)
    assert contracts["ecommerce_asset_plan"]["asset_brief_ids"] == list(EXPECTED_ASSET_BRIEF_ROLES)

    for request_id, role in EXPECTED_ASSET_BRIEF_ROLES.items():
        brief = briefs[request_id]
        delivery = deliveries[request_id]
        assert brief["role"] == delivery["role"] == role
        assert brief["status"] == "passed"
        assert delivery["status"] == "passed"
        assert delivery["asset_brief_id"] == request_id
        for field in ("artifact_id", "locator", "locator_type", "sha256"):
            assert delivery[field]

        artifact_path = REPO_ROOT / delivery["locator"]
        assert artifact_path.is_file()
        assert hashlib.sha256(artifact_path.read_bytes()).hexdigest() == delivery["sha256"]

    assert manifest["per_image_qa_status"] == "pass"
    assert manifest["cross_set_qa_status"] == "pass"
    assert manifest["completeness_status"] == "passed"
    assert qa_result["status"] == "passed"
    assert len(qa_result["gates"]) == 188
    assert all(row["status"] == "pass" for row in qa_result["gates"])
    assert qa_result["severity_summary"] == {"p1": 0, "p2": 0}
    assert qa_result["reviewer_id"] != generation["executor_id"]
    assert runtime["status"] == "passed"
    assert runtime["stage_id"] == "qa-delivery"
    assert runtime["internal_operation"] == "inspect"


def test_humanizer_audit_records_bilingual_review_and_semantic_guardrails():
    audit = (REPO_ROOT / "tests" / "evals" / "v0.2-humanizer-audit.md").read_text(
        encoding="utf-8"
    )
    required_phrases = (
        "2026-09-09",
        "humanizer",
        "humanizer-zh",
        "README.md",
        "README.zh-CN.md",
        "SKILL.md",
        "Contract identifiers were preserved",
        "No release, production, legal, or platform claim was widened",
    )
    assert all(phrase in audit for phrase in required_phrases)


def test_source_release_versions_and_changelog_are_consistent():
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    lock = (REPO_ROOT / "uv.lock").read_text(encoding="utf-8")
    plugin = json.loads(
        (REPO_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    project_version = _version_after(pyproject, "[project]")
    lock_version = _version_after(lock, 'name = "packaging-product-visuals"')
    assert project_version == lock_version == plugin["version"] == "0.2.0"
    assert "## 0.2.0 - 2026-09-12" in changelog
    assert "## 0.1.0 - 2026-09-08" in changelog
    assert changelog.index("## 0.2.0 - 2026-09-12") < changelog.index(
        "## 0.1.0 - 2026-09-08"
    )
    v01_suffix = changelog[changelog.index("## 0.1.0 - 2026-09-08") :]
    assert hashlib.sha256(v01_suffix.encode("utf-8")).hexdigest() == V01_CHANGELOG_SUFFIX_SHA256


def test_release_publication_scope_preserves_original_generation_records():
    publication = json.loads(
        (REPO_ROOT / "docs/releases/v0.2.0-publication.json").read_text(encoding="utf-8")
    )
    assert publication["authorization"]["authority"] == "current-user"
    assert publication["authorization"]["date"] == "2026-09-12"
    assert publication["destination"] == {
        "repository": "https://github.com/feariangod/packaging-product-visuals",
        "branch": "main",
        "tag": "v0.2.0",
    }
    assert publication["permissions"] == {
        "repository_publication": True,
        "listed_fixture_redistribution": True,
        "marketplace_submission": False,
        "private_material_publication": False,
        "font_binary_publication": False,
        "future_asset_publication": False,
    }
    inventory = publication["asset_inventory"]
    assert inventory["path"] == "examples/fictional-pantry-product/asset-provenance.yaml"
    assert hashlib.sha256((REPO_ROOT / inventory["path"]).read_bytes()).hexdigest() == inventory["sha256"]
    assets = yaml.safe_load((REPO_ROOT / inventory["path"]).read_text(encoding="utf-8"))["assets"]
    assert len(assets) == inventory["asset_count"] == 27
    for asset in assets:
        image = REPO_ROOT / "examples/fictional-pantry-product" / asset["locator"]
        assert hashlib.sha256(image.read_bytes()).hexdigest() == asset["sha256"]
    for record in publication["preserved_historical_records"]:
        assert hashlib.sha256((REPO_ROOT / record["path"]).read_bytes()).hexdigest() == record["sha256"]


def test_asset_license_inventory_names_only_owned_fixture_assets():
    text = (REPO_ROOT / "ASSET_LICENSES.md").read_text(encoding="utf-8")
    provenance = yaml.safe_load(
        (REPO_ROOT / "examples/fictional-pantry-product/asset-provenance.yaml").read_text(
            encoding="utf-8"
        )
    )["assets"]
    for asset in provenance:
        assert f"examples/fictional-pantry-product/{asset['locator']}" in text
    assert "Apache-2.0" in text
    assert "third-party" in text.lower()
    assert "private" in text.lower()
    assert "separate publication authorization" in text
    assert "`redistribution_allowed`" in text
    assert "`publication_allowed`" in text


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
