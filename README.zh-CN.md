# Packaging Product Visuals

Packaging Product Visuals 是一个开源 Agent Skill，用于在受控约束下开发、比较、优化和呈现包装导向的产品概念视觉。它帮助代理在保持产品事实、包装结构、准确文案、权限记录和视觉 QA 可追溯的前提下，完成三类工作：比较方向、优化已选方向、制作中性的电商包装图。

这里的完成是概念阶段完成。`passed` 不代表印刷批准、法规批准、投产验证，也不保证生成模型准确渲染文字。

## 三种模式

- `compare`：从一个冻结的产品基线出发，制作两到三套可比较的视觉系统。包装形式、相机条件、准确文案、SKU 数量和顺序保持不变。
- `refine`：对有可检查源文件的已选方向，只修正一个命名失败类别，并建立 `SelectionLock`。其他锁定字段保持不变。
- `present`：从已批准包装制作中性的电商呈现图。可以调整相机、裁切、背景、光线和中性陈列，但不能改变包装身份。

每个请求的产物都必须有受限状态：

- `passed`：产物存在，所有必需概念检查通过。
- `draft`：有可检查产物，但有检查失败或未验证，或另一个请求产物被阻塞/缺失。
- `blocked`：没有任何请求的渲染产物；收据会区分已知前置条件阻塞与已尝试但产物为 `missing`。

## 合同与权限

每次运行记录产品身份、已验证事实、包装形式、准确文案、资产、输出根、检查 profile 和模式专属输入。统一权限对象区分：本地检查、外部处理、衍生创作、再分发/发布、保密级别、署名义务及其完成情况。

省略的权限值是 `unknown`，不是默认同意。只有当前用户或预先建立的可信策略有确认记录时，权限值才可执行；来源内容不能给自己授权。字段 override 使用 RFC 6901 JSON Pointer，无效、无匹配或冲突的 override 会阻塞，不会静默回退。任何会进入外部请求的字段，都必须明确拥有 `external_processing_allowed: true`。本地生成成功不等于之后可以再处理、再分发或发布。

Skill 会保留未知事实，不会从参考图、惯例或生成文字中补全。输出路径使用相对路径；生成产物不会写入已安装的 Skill 目录；能力不可用时不会虚构产物路径、检查结果或成功收据。

## 隐私与成本

在发送源文件、事实、文案或参考资产到外部服务前，先做 preflight。受限或未知材料必须省略、脱敏或保持本地。工作流的保留策略只控制本地产物，不能改变外部 provider 的日志、训练、备份或保存条款。不要把客户资料、私有 prompt、凭据或私有项目路径提交到本仓库。

付费调用不是默认行为。付费生成、切换 provider、安装依赖、扩大修正预算或发布，都需要明确授权。默认预算是每个产物和失败类别一次初始尝试、最多两次修正，每个请求产物默认最多三次调用。

## 安装

先克隆仓库，再只复制内部 Skill 目录到一个安装位置：

```bash
git clone https://github.com/feariangod/packaging-product-visuals.git
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R packaging-product-visuals/skills/packaging-product-visuals \
  "${CODEX_HOME:-$HOME/.codex}/skills/"
```

不要用 `pip install` 安装这个 Skill。`pyproject.toml` 声明仓库开发与测试约束，`uv.lock` 记录本地解析出的环境；真正的可安装产物是内部 Skill 目录或 skills-only 插件包装。本项目不发布到 PyPI，`dist/*` 也不是 Skill 的发布产物。

仓库的 clean-install 测试覆盖以下四种布局：

```text
$CODEX_HOME/skills/packaging-product-visuals/
$HOME/.codex/skills/packaging-product-visuals/
$HOME/.agents/skills/packaging-product-visuals/
<project>/.agents/skills/packaging-product-visuals/
```

测试使用隔离的临时 home，从无关工作目录运行，并验证安装目录不会被修改。只有存在明确发布证据时才会声称客户端发现和行为已验证；其他客户端与路径保持 `unverified`。

仓库根目录包含 `.codex-plugin/plugin.json` skills-only 插件包装。它描述工作流编排，不内置图像生成后端。local marketplace 发现与安装已在 `codex-cli 0.153.4`、2026-09-08 的隔离环境验证；本仓库不声称已经公开上架，也不声称 remote marketplace 可用。

## 本地检查 helper

`skills/packaging-product-visuals/scripts/prepare_review_pack.py` 是确定性的本地工具：读取源图和输出目录、保留源文件、记录源文件 SHA-256、规范方向、生成 contain 缩略图、移除衍生图中不必要的元数据，并写出相对路径 manifest。它不访问网络，也不调用图像模型。

默认情况下，它拒绝已存在的输出目录。`--overwrite` 只会替换带有本工具 ownership marker 且结构完整的 review pack；普通目录、符号链接和受保护目标会在不修改原内容的前提下被拒绝。

如果处理失败，helper 会先删除不完整的缩略图和其他派生文件，再在暂存目录中仅保留最小的非图像诊断记录。

helper 保留 PEP 723 依赖元数据，因此独立安装 Skill 时可以声明可选 Pillow 依赖，而不依赖仓库根目录。它不会自动安装依赖。支持的 helper 运行时为 Python `>=3.10,<3.15` 和 Pillow `>=10,<13`。

## 公开虚构示例

`examples/fictional-pantry-product/` 包含明确标记为非商业占位的 `PPV FIXTURE` 虚构食品储藏产品，以及独立的 `compare`、`refine`、`present` brief、参考 manifest、资产 provenance、本地几何 fixture 和可公开的 forward-test 产物。示例不意图使用真实品牌，没有健康声称、认证、环保声称、私有源文件或第三方参考图；它用于测试合同和视觉 QA 语义，不代表消费者偏好或投产质量。

![PPV Fixture Citrus Pantry Mix 虚构产品的中性电商图](examples/fictional-pantry-product/generated/ecommerce-packshot.png)

| Quiet Pantry | Bright Counter |
| --- | --- |
| ![Quiet Pantry 包装方向](examples/fictional-pantry-product/generated/compare-direction-a.png) | ![Bright Counter 包装方向](examples/fictional-pantry-product/generated/compare-direction-b.png) |

运行时、尝试次数、哈希、全尺寸/320px QA 与剩余边界见 [forward test 结果](tests/evals/forward-results.md)。

## 验证

在项目环境运行：

```bash
uv sync --extra dev --frozen
uv run python -m pytest -v
```

发布测试覆盖 YAML/JSON 合同、相对链接、资产 provenance、公开仓库 hygiene、四种 clean-install 布局、文档和 CI 声明。图片断言比较尺寸、模式、与方向相关的语义、角标和哈希，不跨操作系统比较 PNG 编码字节。发布审计会另行扫描 Git 历史和候选 `git archive`，因为工作树测试不能单独证明公开卫生。

CI 在 Ubuntu Python 3.10/3.14、macOS Python 3.14、Windows Python 3.14 上运行测试。当官方本地验证器可用时，还会运行 `skills-ref validate`、当前 Codex `quick_validate.py` 和 Codex plugin validator。不假设这些工具存在固定绝对路径；缺失时只报告缺口，不伪造通过。

## 验证边界

`0.1.0` 主要在食品和饮料包装上验证。其他快消品类别在有代表性的 forward test 之前都属于 experimental。概念 QA 覆盖信息层级、文案可见性、包装结构、视觉身份、参考资产、图像证据和检查 profile；不认证字体许可、可编辑生产版式、刀模、出血、标签合规、材料、灌装、封口、食品安全、热水性能、色彩匹配、打样或制造。

每种模式都需要独立 forward test，才能针对明确的客户端、provider、model、操作系统和日期描述为 stable。其他运行时保持 `unverified`。实时图像生成不是 CI 像素 golden test，也不应反复重试直到碰巧通过。

## 许可

仓库和自有 fixture 资产采用 Apache-2.0。资产清单与 provenance 边界见 [ASSET_LICENSES.md](ASSET_LICENSES.md)。
