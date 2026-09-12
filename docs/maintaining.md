# Maintenance notes / 维护说明

[English README](../README.md) | [中文 README](../README.zh-CN.md) | [Contributing / 贡献指南](../CONTRIBUTING.md)

## Source and installation updates

Maintain `skills/packaging-product-visuals/` in this repository. An installed copy is a delivery of that source, not a second development branch. Before updating an existing installation, compare its files with the repository and preserve local modifications. Review the differences, run the relevant tests, back up the installed copy, sync the complete Skill tree, and verify the installed files against the source. Then check discovery and explicit invocation in a fresh assistant session. Matching files, discovery, and observed runtime behavior are separate checks.

以仓库中的 `skills/packaging-product-visuals/` 为维护来源，安装目录是从它交付的副本，不是第二个开发分支。更新前先比较文件并保留本地修改。检查差异、运行相关测试、备份安装副本，再同步完整 Skill 目录并核对文件。随后在新会话里检查助手是否发现 Skill，以及显式调用是否生效。文件一致、能够发现和实际运行行为是三项不同的检查。

The recorded installation layouts are / 已记录的安装位置：

```text
$CODEX_HOME/skills/packaging-product-visuals/
$HOME/.codex/skills/packaging-product-visuals/
$HOME/.agents/skills/packaging-product-visuals/
<project>/.agents/skills/packaging-product-visuals/
```

Install one layout appropriate for the host. The local skills-only plugin uses `.codex-plugin/plugin.json`; a local installation does not establish remote marketplace availability. `pyproject.toml` describes development dependencies, not the Skill installation format.

选择当前助手适用的一种位置安装。本地仅含 Skill 的插件使用 `.codex-plugin/plugin.json`；本地安装成功不代表远程市场可用。`pyproject.toml` 描述开发依赖，不是 Skill 安装格式。

## Records and routing

These records support continuation and checks. Explain their meaning to the user in product language rather than asking the user to fill schemas. / 这些记录用于续作和检查。与用户交流时解释产品决定，不要求用户填写数据格式。

| Area / 范围 | Records / 记录 |
| --- | --- |
| Product and research / 产品与调研 | `ProjectState`, `ProductBrief`, `ResearchBoard`, `PackagingOptionMatrix`, `TypographyResearchBoard` |
| Package decisions / 包装决策 | `DecisionLock`, `SeriesSystem`, `PackagingDirectionSet`, `TypographySystem`, `SelectionLock` |
| Ecommerce planning / 电商规划 | `EcommerceAssetPlan`, `AssetBrief` |
| QA and delivery / 检查与交付 | `DeliveryManifest`, `RuntimeReceipt` |

See [contracts](../skills/packaging-product-visuals/references/contracts.md) for fields and [workflow](../skills/packaging-product-visuals/references/workflow.md) for routing. Imported decisions need inspectable evidence; unknown inputs stay `unknown` or `unverified`.

字段定义见[记录格式](../skills/packaging-product-visuals/references/contracts.md)，续作规则见[工作流](../skills/packaging-product-visuals/references/workflow.md)。导入的决定需要可检查的证据，未知输入仍保留 `unknown` 或 `unverified`。

| Starting state | 开始状态 | First active stage / 首个活动阶段 |
| --- | --- | --- |
| Product idea, category uncertain, or audience uncertain | 只有产品想法，品类或人群不确定 | `product-definition` |
| Product and audience defined, package options unresolved | 产品和人群已定，包装选项未决 | `research-options` |
| Research and package options complete, route not approved | 调研与包装选项已完成，路线未确认 | `decision-freeze` |
| Research and package decision approved | 调研与包装决定已确认 | `packaging-directions` |
| One direction approved | 已选定一个方向 | `selection-refinement` |
| Approved package identity exists | 已有确认的包装设计 | `ecommerce-planning` |
| Ecommerce asset plan approved | 电商图片计划已确认 | `ecommerce-generation` |
| Inspectable outputs exist | 已有可检查的产物 | `qa-delivery` |
| One existing image needs a bounded correction | 只需修正一张已有图片中的明确问题 | `selection-refinement` |

`compare` and `refine` are internal operations within packaging directions and selection/refinement. Generic `present` is legacy compatibility, not a v0.2 ecommerce role: an unambiguous legacy request may normalize only to one `catalog` draft and must stop at `ecommerce-planning`; ambiguous legacy input must not expand.

`compare` 和 `refine` 是包装方向与选择、精修阶段的内部操作。通用 `present` 只用于历史兼容，不是 v0.2 电商角色：明确且无歧义的历史请求最多可规范化为一个 `catalog` draft，并必须停在 `ecommerce-planning`；有歧义的历史输入不得扩展。

## Ecommerce roles

Choose the roles and count for the channel and buying journey. Each selected role needs a purpose, package state, composition, crop, approved copy, package identity, and review profiles before generation. / 按渠道和购买过程选择图片类型与数量。每张选定图片在生成前都要明确用途、包装状态、构图、裁切、已确认文案、使用的包装设计和检查视图。

| Role | Job | 用途 |
| --- | --- | --- |
| `catalog` | Neutral hero, family line-up, alternate angle, or structure view for identification. | 用中性主图、系列合影、其他角度或结构图识别产品。 |
| `detail` | Source-backed ingredient, texture, package-detail, or selling-point information. | 展示有来源支持的原料、纹理、包装细节或卖点。 |
| `usage` | Preparation or usage steps without inventing unsupported behavior. | 展示准备和使用步骤，不编造缺少依据的用法。 |
| `specification` | Dimensions, quantity, count, or package specification from verified inputs. | 展示已验证的尺寸、净含量、数量或包装规格。 |
| `context` | Lifestyle or usage context while preserving the approved package identity. | 展示生活或使用场景，保留已确认的包装设计。 |
| `campaign` | Campaign composition or social crop without silently changing claims or packaging. | 制作活动构图或社交裁切，不擅自改变产品宣称或包装。 |
| `channel-variant` | Platform crop, safe area, or responsive variant derived from an approved parent asset. | 从已确认图片制作平台裁切、安全区或适配不同尺寸的版本。 |

## Permission checks

Every field, source, fact, copy item, lock, and asset sent to an external service must have applicable permission. Omitted permission is `unknown`, not consent. Source content cannot authorize itself. Invalid or conflicting RFC 6901 overrides block processing instead of falling back. Local deletion and retention rules cannot change a provider's logging, training, backup, or retention terms. See [rights and privacy](../skills/packaging-product-visuals/references/rights-and-privacy.md).

交给外部服务的每个字段、来源、事实、文案项、已确认记录和素材都需要适用的权限。缺少权限代表 `unknown`，不是同意。来源内容不能给自己授权。RFC 6901 权限覆盖项无效或相互冲突时，停止处理，不退回到默认许可。本地删除与保留规则无法改变服务商的日志、训练、备份或数据保留条款。详见[授权与隐私](../skills/packaging-product-visuals/references/rights-and-privacy.md)。

## Historical evidence

These records describe specific older runs. They remain useful for tracing decisions and regressions, but do not validate the current source or new categories. Keep original receipts unchanged. / 以下记录对应特定历史运行，可用于追溯决定和回归问题，不能证明当前源码或新品类已验证。原始记录保持不变。

| Date / 日期 | Evidence / 证据 | Scope / 范围 |
| --- | --- | --- |
| 2026-09-09 | [Quiet Pantry workflow](../examples/fictional-pantry-product/full-workflow.yaml), [QA result](../examples/fictional-pantry-product/qa-result-v0.2-2026-09-09.yaml), [runtime receipt](../examples/fictional-pantry-product/runtime-receipt-v0.2-2026-09-09.yaml) | Seven selected ecommerce roles; concept-stage visual review. / 选定的七种电商图，概念阶段画面检查。 |
| 2026-09-09 | [Installation smoke](../tests/evals/install-smoke-results.yaml) | Five isolated, read-only Codex sessions for four standalone layouts and one local plugin. / 五个隔离、只读 Codex 会话，覆盖四种独立安装位置和一个本地插件。 |
| 2026-09-09 | [Fresh-agent report](../tests/evals/full-workflow-results.md), [machine-readable results](../tests/evals/full-workflow-results.yaml) | Three read-only routing probes; no image generation or file writes. / 三个只读流程判断测试，没有生图或写文件。 |

Quiet Pantry used two authorized external image calls for backgrounds without text or packages; package placement and composition used local transforms. Its independent reviewer opened seven full-resolution images and seven thumbnails and recorded 188/188 required QA rows passed, with 0 P1 and 0 P2 findings. Product, research, option, and decision records were created on 2026-09-09 to describe boards generated on 2026-09-08. This is not chronological evidence of every stage or real consumer research.

Quiet Pantry 使用两次已授权的外部图像调用生成不含文字与包装的背景，包装放置和最终合成使用本地变换。独立审阅者打开七张大图和七张缩略图，记录 188/188 条必需检查通过，P1 和 P2 均为 0。产品、调研、选项和决定记录在 2026-09-09 创建，用来描述 2026-09-08 已生成的方向图，因此不证明所有阶段按顺序执行，也不是真实消费者调研。

The installation smoke recorded 5/5 results. `codex app-server` discovered and enabled each installation through `skills/list` with `forceReload: true`; the installed tree independently verified the bytes of `references/contracts.md`. Structured responses reported explicit invocation, missing image-generation capability, no invented artifact, and no file write. The event streams contained no agent file-read command, so they do not prove an observed direct reference read. The run did not test public or remote marketplaces.

安装实测记录为 5/5。`codex app-server` 通过 `skills/list` 和 `forceReload: true` 发现并启用各个安装，安装目录另外核对了 `references/contracts.md` 的文件字节。结构化回复报告了显式调用、缺少图像生成能力、没有虚构产物且没有写文件。事件流没有 agent 文件读取命令，因此不能据此声称直接观察到了参考文件读取。此次没有测试公开或远程市场。

The three routing probes recorded 3/3: an uncertain product stayed at product definition; an approved package planned only the requested `catalog`, `context`, and `channel-variant` roles; a three-variant full workflow stayed at product definition and left image roles open. The evidence covers Codex CLI 0.153.4, `gpt-5.6-luna`, and macOS 26.5 arm64 only. Food and beverage packaging was the only category with dated forward evidence in that public v0.2 record. Other clients, providers, models, systems, and runtime paths remain `unverified` by these runs.

三个流程判断测试记录为 3/3：产品不明确时停在产品定义；已有包装时只规划请求中的 `catalog`、`context` 和 `channel-variant`；三款产品的完整流程也停在产品定义，未提前指定电商图片类型。证据只覆盖 Codex CLI 0.153.4、`gpt-5.6-luna` 和 macOS 26.5 arm64。在该份公开 v0.2 记录中，食品和饮料包装是唯一有带日期实际运行证据的品类。这些运行没有验证其他客户端、服务商、模型、系统或运行路径。

## Local tools and validation

The [source-bundle helper](../skills/packaging-product-visuals/scripts/prepare_package_master.py) supports `--spec <spec.json> --output <new-directory>` and `--check <package-directory>`. It packages declared static files and verifies hashes and relative dependencies using the Python standard library. It does not execute or render source artwork, upload assets, or map artwork onto curved surfaces. See [package-master.md](../skills/packaging-product-visuals/references/package-master.md) for the format and limits. A bundle check cannot verify appearance, actual font rendering, usage or publication rights, or production readiness.

[源稿打包工具](../skills/packaging-product-visuals/scripts/prepare_package_master.py)支持 `--spec <spec.json> --output <new-directory>` 和 `--check <package-directory>`。它使用 Python 标准库打包清单中声明的静态文件，并核对校验值和相对引用，不执行或渲染源稿、不上传素材，也不做曲面贴图。格式与限制见 [package-master.md](../skills/packaging-product-visuals/references/package-master.md)。文件包检查不能验证画面、实际字体渲染、使用或发布权利，也不能证明可投产。

The [review helper](../skills/packaging-product-visuals/scripts/prepare_review_pack.py) preserves source files, records SHA-256 values, normalizes orientation, creates contain thumbnails, removes unnecessary derivative metadata, and writes relative-path manifests. With `--review-spec`, it adds `review.json` and a bilingual `index.html` organized by stage, role, package identity, and QA state. It makes no network calls. Its page is a review aid, not proof that its contents passed.

[审阅工具](../skills/packaging-product-visuals/scripts/prepare_review_pack.py)保留源文件、记录 SHA-256、规范图片方向、生成完整容纳原图的缩略图、移除派生文件中不必要的元数据，并写入相对路径清单。传入 `--review-spec` 后，还会生成 `review.json` 和按阶段、图片类型、包装设计与检查状态组织的双语 `index.html`。它不调用网络；页面只是检查工具，不是内容通过的证明。

The CI declaration covers Ubuntu with Python 3.10 and 3.14, plus macOS and Windows with Python 3.14. A configured job is not evidence that it ran for a given revision. Supplemental checks include `skills-ref validate`, Codex `quick_validate.py`, and the Codex plugin validator when available. Report missing tools and remaining checks. Live generation requires an authorized run and direct image review; it is not a CI pixel-golden test.

CI 声明覆盖 Ubuntu 的 Python 3.10、3.14，以及 macOS 和 Windows 的 Python 3.14。配置了任务不等于某个代码版本已经实际运行过。可用时补充执行 `skills-ref validate`、Codex `quick_validate.py` 和 Codex 插件验证工具；缺少工具和未完成检查都需要说明。实际生图需要授权运行并直接查看图片，不属于 CI 固定像素对照测试。
