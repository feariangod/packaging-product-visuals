# Contributing / 贡献指南

[English](#english) | [简体中文](#简体中文)

## English

### Scope

Keep a contribution focused on a behavior that a user can observe. Read [SKILL.md](skills/packaging-product-visuals/SKILL.md) and the relevant reference before editing. This repository's `skills/packaging-product-visuals/` is the maintenance source; installed copies are updated from it, not developed independently. The [maintenance guide](docs/maintaining.md) covers updates and internal records.

Preserve the workflow: define the product and initial packaging, research alternatives, confirm the shared basis, compare complete packaging directions, refine the selection, then plan and deliver ecommerce images. A typography improvement must still work as part of that workflow.

Do not add a marketplace repository, telemetry, hosted documentation, automatic uploads, or a paid integration without separately approved scope. Never commit customer material, private project documents or prompts, credentials, source EXIF, unlicensed references, or outputs derived from private inputs.

### Tests

Use Python `>=3.10,<3.15` with the repository's development dependencies:

```bash
uv sync --extra dev --frozen
uv run python -m pytest -v
uv lock --check
git diff --check
```

This environment runs tests and local tools; it does not install the Skill. Add tests for the changed behavior and meaningful failure cases. Documentation tests should check facts, working links, and bilingual agreement without forcing one exact sentence.

CI is configured for Ubuntu with Python 3.10 and 3.14, plus macOS and Windows with Python 3.14. Do not compare encoded PNG/JPEG bytes across systems. Check dimensions, mode, orientation, semantic markers, decoded hashes where pinned, canonical text, path ordering, and exit codes instead.

The credential-bearing runtime harness requires POSIX permissions. Windows runs the offline and contract tests plus explicit unsupported-platform rejection tests; POSIX-only private-runtime fixtures are reported as skipped. Live Codex evidence remains limited to the recorded macOS runs. See [maintenance notes](docs/maintaining.md).

Use available official validators as supplemental checks:

```bash
skills-ref validate skills/packaging-product-visuals
python quick_validate.py skills/packaging-product-visuals
```

Locate the installed validator rather than assuming a machine-specific path. Report a missing validator; do not fabricate a pass or copy a replacement into the repository. Record the revision, date, environment, results, and gaps for each run. Historical test counts do not validate new changes.

### Examples and visual review

Public examples must be fictional and redistributable. Every image needs a provenance entry beside its example and an entry in [ASSET_LICENSES.md](ASSET_LICENSES.md). Record creation method, sources, redistribution terms, visible trademarks, private-data checks, dimensions, mode, and source hash. Keep programmatic examples deterministic. List which reference elements may and may not be reused; record font licenses separately.

For direction comparisons, preserve product facts, package structure and proportions, required copy, variant order, and viewing conditions. Declare the comparison checks before the run. Cosmetic finish can be advisory only when it cannot affect the choice; do not downgrade a failed required check afterward. Missing permission and incorrect facts are never exceptions. Refinement cases must name the correction and selected design. Ecommerce cases must identify that design and the staging changes allowed.

Open full-size images and thumbnails. Check each image and consistency across the set. Keep self-review, independent review, and user preference separate in the report. New-category and clean-session trials must state which stages actually ran; planning-only trials are not image-generation evidence. Do not retry live generation until a run happens to pass.

### Documentation and release

Keep both READMEs, this guide, `CHANGELOG.md`, `SKILL.md`, plugin metadata, and license declarations consistent. Explain the user's workflow on the homepage; put schemas and dated evidence in the maintenance guide. Avoid claims of exact generated text, universal compatibility, marketplace availability, consumer preference, regulatory approval, food safety, or manufacturing validation. An acceptable concept does not establish any of these.

Describe the requested behavior, fixed decisions, permissions, asset provenance, tests run, unavailable validators, and remaining checks in a pull request. Keep unrelated changes out. Before publication, obtain an independent agent review and review the public prose for generic AI-style wording without removing factual caveats. Tags, GitHub Releases, marketplace submissions, external pushes, and publication require explicit approval after release checks pass. Preserve old receipts rather than rewriting them as evidence for a newer version.

## 简体中文

### 修改范围

一次贡献聚焦于使用者能观察到的行为。修改前先阅读 [SKILL.md](skills/packaging-product-visuals/SKILL.md) 和相关参考文件。仓库中的 `skills/packaging-product-visuals/` 是统一维护来源，安装目录从这里更新，不单独开发。[维护说明](docs/maintaining.md)记录了更新方法和内部记录。

保留完整流程：确定产品与初始包装，调研备选，确认共同条件，比较完整包装方向，精修选中方案，再规划和交付电商图。字体方面的改进也需要服务于这个流程。

新增市场仓库、遥测、托管文档、自动上传或付费集成，需要另行批准范围。不要提交客户资料、私有项目文件或提示词、凭据、源图 EXIF、无授权参考资料，或由私有输入生成的产物。

### 测试

使用 Python `>=3.10,<3.15` 和仓库的开发依赖：

```bash
uv sync --extra dev --frozen
uv run python -m pytest -v
uv lock --check
git diff --check
```

此环境用于测试和本地工具，不用于安装 Skill。为改动的行为和有意义的失败情况补充测试。文档测试应检查事实、链接和中英一致性，不应强制某一句固定措辞。

CI 配置覆盖 Ubuntu 的 Python 3.10、3.14，以及 macOS 和 Windows 的 Python 3.14。不要跨系统比较 PNG/JPEG 编码后的文件字节；应检查尺寸、模式、方向、可识别内容、明确固定的解码后校验值、标准化文字、路径顺序和退出码。

需要凭据的运行探针依赖 POSIX 权限。Windows 执行离线工具、数据规则和不支持平台的提前拒绝测试，POSIX 私有运行样例会明确报告为跳过。真实 Codex 会话证据仍限于已记录的 macOS 运行。详见[维护说明](docs/maintaining.md)。

可用时，用官方验证工具补充检查：

```bash
skills-ref validate skills/packaging-product-visuals
python quick_validate.py skills/packaging-product-visuals
```

先找到已安装的验证工具，不假设某个本机路径一定存在。缺少工具就记录缺口，不伪造通过，也不往仓库复制替代品。每次运行记录代码版本、日期、环境、结果和未验证项。旧测试数量不能证明新修改已通过。

### 示例与画面检查

公开示例必须虚构且可再分发。每张图片都要在对应示例的来源记录和 [ASSET_LICENSES.md](ASSET_LICENSES.md) 中登记，包括生成方法、来源、再分发条款、可见商标、隐私检查、尺寸、模式和源文件校验值。程序生成的示例应可重复生成。参考资料需要写清可用和禁用的元素，字体许可另行记录。

比较方向时，保持产品事实、包装构造与比例、必需文案、款式顺序和查看条件一致。运行前先确定比较检查；只有不影响选择的外观精修才可以作为建议项，不能事后降低某项必需检查的失败等级。缺少权限和事实错误不在例外之列。精修案例要明确修正问题和选中设计；电商案例要明确使用哪个设计，以及允许改变哪些场景内容。

打开大图和缩略图，逐张检查并核对整套一致性。报告中分开记录自查、独立审查和用户偏好。新品类和新会话测试需要说明实际完成了哪些阶段；只做规划不能算生图证据。不要反复生成，直到偶然出现一次通过。

### 文档与发布

保持两份 README、本指南、`CHANGELOG.md`、`SKILL.md`、插件信息和许可声明一致。首页解释使用流程，数据格式和带日期的证据放进维护说明。不承诺生成文字完全准确、兼容所有环境、已进入市场，也不声称消费者偏好、法规批准、食品安全或投产验证。概念图检查通过不能证明这些结果。

Pull request 说明预期行为、已固定的决定、权限、素材来源、运行过的测试、缺少的验证工具和剩余检查。不要混入无关修改。发布前进行独立子 agent 审查，并检查公开文字中的套话和 AI 式表达，同时保留事实限制。创建标签、GitHub Release、提交市场、向外部推送或发布，都需要先通过发布检查，再取得明确批准。保留旧运行记录，不把它们改写为新版本证据。
