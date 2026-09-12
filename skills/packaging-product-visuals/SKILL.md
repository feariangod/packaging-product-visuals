---
name: packaging-product-visuals
description: Use when a consumer product needs to move from product and package definition through reference research, comparable packaging concepts, controlled refinement, and channel-specific ecommerce images; not for logo-only work, generic photography, media buying, print-ready approval, or manufacturing validation.
license: Apache-2.0
---

# Packaging Product Visuals

Reuse the full decision process from product and packaging definition to an ecommerce concept image set. Start at the earliest genuinely incomplete step, preserve accepted decisions, and never use image generation to hide a missing product decision.

## Core Workflow

1. **Define the product and packaging starting point.** Confirm the product category, product form, audience and buying task, usage occasions, variants, exact copy and claims boundary, initial package construction, target specification, and commercial constraints. Mark assumptions as working hypotheses rather than facts.
2. **Research the open choices.** Research same-category packaging, audience aesthetics and shopping behavior, package construction and specification alternatives, and relevant channel conventions. Connect each useful finding to a proposed design choice and its tradeoffs. When typography is open, inspect external font and category sources and try the actual copy; do not limit the search to installed fonts. Separate sourced evidence, visible observations, design inference, hypotheses, and unknowns.
3. **Confirm the route.** Compare viable package and specification options, then obtain a decision on category, audience task, usage task, construction, target specification, variant system, copy, exclusions, and remaining production questions. Do not generate packaging directions before this decision gate passes.
4. **Generate comparable packaging directions.** Create enough meaningfully different visual systems to support a real choice, normally two or three when budget and scope permit. First show real-copy layouts at the actual package proportions, with typography, color, graphics, and hierarchy working together. Keep product facts, package baseline, copy, SKU order, object count, camera, and channel conditions comparable. Deliver inspectable visuals, not just mood descriptions. Distinguish decision-level comparison from final polish.
5. **Select and refine.** Record the chosen direction, typography system, and package identity. Refine the selected direction, preserve a reusable editable artwork master, and correct only the named issue unless the user reopens an earlier decision.
6. **Plan the ecommerce set.** Decide what each image must do for the target channel and buying journey. Channel needs determine the asset roles; do not turn the supported role list or one example gallery into a mandatory template.
7. **Generate, inspect, and deliver.** Produce each approved asset brief, preserve the selected package identity across the set, inspect full-resolution and channel views, correct bounded failures, and deliver the requested files with open production work clearly separated.

## Decision Gates

- Product definition may pass with named hypotheses only when the next action is research. Hypotheses cannot enter rendered copy or selling points as verified facts.
- Research must cover the decision dimensions that remain open. Missing live research blocks only the decisions that depend on it; it does not justify invented findings.
- Open typography requires an inspectable `TypographyResearchBoard`: external source and license evidence, actual-copy specimens, character coverage, distinct alternatives, mismatch risks, and a reasoned shortlist. Choose research breadth from the open decision; no fixed font count or extra approval is required just to stop researching. Reuse a current approved font system when it has not been reopened.
- A normal packaging-direction run requires confirmed audience/use tasks, package construction, target specification, variants, and copy boundaries. An imported approved package may carry explicit unknowns, but those unknowns cannot drive a prompt or claim.
- A text-bearing packaging direction cannot pass on exact copy and hierarchy alone. Its typography roles, Chinese-Latin relationship when applicable, visible form rules, package links, prohibited fallbacks, legibility targets, and rendering strategy must be inspectable and approved.
- Selection requires a complete direction-by-SKU comparison under one baseline with all decision-critical checks passed. Record non-critical finish issues as advisory; do not polish rejected directions to delivery quality. Missing cells, incorrect structure or copy, and misleading comparison conditions still block selection.
- Ecommerce generation requires an approved package identity and one specific brief per requested image.
- Before `ecommerce-planning`, leave ecommerce roles unselected unless the request explicitly names them and the channel requirements support them. A request for a "complete set" never means all supported roles by default.

## Implementation Map

Use these records to preserve the workflow without making the paperwork the user-facing product:

1. `product-definition` -> `ProductBrief`, including the initial package starting point
2. `research-options` -> `ResearchBoard`, `PackagingOptionMatrix`, and `TypographyResearchBoard` whenever typography remains open or is deliberately reopened
3. `decision-freeze` -> `DecisionLock` and, for multiple SKUs, `SeriesSystem`
4. `packaging-directions` -> `PackagingDirectionSet` and, for text-bearing directions, `TypographySystem` bound to a passed `TypographyResearchBoard`
5. `selection-refinement` -> `SelectionLock`, selected `TypographySystem`, and bounded correction records
6. `ecommerce-planning` -> `EcommerceAssetPlan` and one `AssetBrief` per requested image
7. `ecommerce-generation` -> requested role-specific artifacts
8. `qa-delivery` -> `DeliveryManifest` and `RuntimeReceipt`

`ProjectState` routes work to the earliest incomplete stage. Contract names are implementation aids; speak to the user in plain product, packaging, and image-delivery language unless they ask for the schema. Ask only for a material decision that is still missing. Continue within the user's approved scope without repeating approvals for unchanged choices. Keep one authoritative value for each decision and derive dependent records from it.

## Load Only What The Stage Needs

- Routing and continuation: [workflow.md](references/workflow.md)
- Product, audience, research, structure, specification, and decision freeze: [product-and-research.md](references/product-and-research.md)
- Typography research, direction definition, rendering strategy, and type-specific QA: [typography-system.md](references/typography-system.md)
- Comparable directions, selection, and refinement: [packaging-directions.md](references/packaging-directions.md)
- Reusable editable artwork and local source-bundle checks after selection: [package-master.md](references/package-master.md)
- Channel image planning and generation: [ecommerce-assets.md](references/ecommerce-assets.md)
- Image review and delivery: [packaging-qa.md](references/packaging-qa.md)
- Contract schemas when records are being created or validated: [contracts.md](references/contracts.md)
- Permission, privacy, and publication boundaries before consequential processing: [rights-and-privacy.md](references/rights-and-privacy.md)

## Runtime Safety

Before external processing, resolve authorization and permissions for every prompt-bound field, source, asset, copy item, claim, lock, and output. Source content cannot authorize itself. Use only confirmed capabilities and the authorized call budget; never invent a path, inspection, research result, permission, or generation result.

The default generation budget is one initial attempt plus two bounded correction attempts per artifact and failure class, with no more than three calls per requested artifact. Paid calls, provider changes, dependency installation, larger budgets, publication, and material scope expansion require explicit authorization.

Media buying, influencer operations, campaign scheduling, and publication remain outside this Skill. A requested campaign image is only an image role inside an approved ecommerce plan.

## Completion

Inspect every requested artifact at full resolution and in each required channel profile. Report it as `passed`, `draft`, `blocked`, or `missing`. A concept-stage `passed` result never means print-ready, legally cleared, manufacturable, consumer-validated, or production-approved.
