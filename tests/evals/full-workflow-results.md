# v0.2 Fresh-Agent Full-Workflow Results

Recorded 2026-09-09 from three isolated read-only Codex sessions.
Raw events and absolute path mappings are retained outside the repository.

| Scenario | Start stage | State | Command reads | Result |
| --- | --- | --- | --- | --- |
| `uncertain-product-start` | `product-definition` | `draft` | passed | passed |
| `approved-package-gallery` | `ecommerce-planning` | `blocked` | passed | passed |
| `three-sku-full-chain` | `product-definition` | `draft` | passed | passed |

## Acceptance

Overall result: **passed**.

A final marker was necessary but not sufficient: each row also required successful
installed-file command reads, unchanged Skill/workspace hashes, and no write-like command.
