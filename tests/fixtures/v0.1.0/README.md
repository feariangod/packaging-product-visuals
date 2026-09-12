# Frozen v0.1.0 compatibility fixture

`prepare_review_pack.py` is an unchanged copy of the helper published at commit
[`5d5fcaaa289da5bf6fbb09ec051a1d9d74c5adcb`](https://github.com/feariangod/packaging-product-visuals/blob/5d5fcaaa289da5bf6fbb09ec051a1d9d74c5adcb/skills/packaging-product-visuals/scripts/prepare_review_pack.py).
Its SHA-256 is `004d8515e981adb6d2eac651c23ff7051f50a26322cc8f6883ee99c273515d6b`.

The migration tests check this hash and use the old helper to create authentic
review packs in temporary directories. The snapshot removes the test dependency
on Git history, including in shallow clones. It uses this repository's Apache-2.0
license and is not part of the installed Skill. Do not update it with the current
helper or use it for new work.

这是已发布 v0.1.0 工具的原始快照，供迁移测试在临时目录创建真实旧版审阅包。
测试会检查校验值，不再依赖完整 Git 历史。它沿用仓库的 Apache-2.0 许可，不随
Skill 安装；不要用当前工具覆盖它，也不要用它处理新项目。
