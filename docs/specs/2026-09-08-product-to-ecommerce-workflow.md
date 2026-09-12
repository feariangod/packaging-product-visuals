# Product-to-Ecommerce Packaging Workflow Specification

**Status:** Approved on 2026-09-08

## Problem

Version 0.1 models packaging work as three separate operations: `compare`, `refine`, and `present`. That is useful once a product and package are already defined, but it excludes the decisions that determine whether the generated work is relevant: product category, audience, package construction, package specification, reference interpretation, and ecommerce asset planning.

Version 0.2 must make the complete decision and delivery chain the primary workflow. The three existing operations remain useful, but only inside the stages where they belong.

## Product Goal

Provide an open-source, provider-agnostic Agent Skill that can take a consumer product from an early idea or any later verified state through packaging concepts and a consistent ecommerce image set. Every stage must preserve evidence, permissions, decisions, visual identity, QA, and unresolved production work.

## Design Principles

1. **Route by maturity, not by mode.** Determine the earliest incomplete stage and continue from there.
2. **Research before rendering.** Do not generate packaging directions until product, audience, structure, and specification decisions are explicit enough to compare.
3. **Separate evidence from judgment.** Record sourced evidence, visible observations, design inference, hypotheses, and unknowns separately.
4. **Freeze decisions at gates.** Use `DecisionLock` before packaging exploration and `SelectionLock` before refinement or ecommerce expansion.
5. **Compare systems, not isolated decoration.** A direction is a coherent visual system applied across the full requested SKU set.
6. **Plan the gallery before generating it.** Every ecommerce image has a role, claim source, package state, composition, crop, and QA profile.
7. **Keep package identity consistent across assets.** Ecommerce scenes may change context, but not silently redesign the approved package.
8. **Treat outputs as inspectable evidence.** Never invent files, inspections, permissions, research, or generation results.
9. **Keep concept approval separate from production approval.** Structure research can inform concepts but does not validate dielines, materials, filling, sealing, transport, labeling, or manufacturing.

## Stage Router

The Skill accepts natural-language requests and identifies the earliest incomplete stage:

| Start state | First active stage |
| --- | --- |
| Product idea, category uncertain, or audience uncertain | Product definition |
| Product and audience defined, package options unresolved | Research and option comparison |
| Research and viable package options exist, route not confirmed | Decision freeze |
| Research and package decision approved | Packaging direction generation |
| One direction approved | Selection and refinement |
| Approved package identity exists | Ecommerce asset planning |
| Asset plan approved | Ecommerce set generation |
| Inspectable outputs exist | QA and delivery |
| One existing image needs a bounded correction | Selection and refinement |

Do not repeat accepted work. Bind imported decisions to their sources and mark unverifiable inputs `unknown` or `unverified`.

## Workflow And Gates

### 1. Product Definition

Determine category, product form, usage occasion, audience, variants, naming state, verified facts, prohibited claims, known commercial constraints, and the initial package construction/specification starting point. Produce a `ProductBrief`.

Gate: the user or trusted record confirms the brief, or unresolved fields are explicitly accepted as hypotheses for research only.

### 2. Research And Option Comparison

Research same-category packaging, audience aesthetics and usage expectations, and viable package construction/specification options. Classify references by role instead of treating every image as a style target. Produce a `ResearchBoard` and `PackagingOptionMatrix`.

Gate: evidence quality, uncertainty, permission, and production-validation gaps are visible. A preferred package route and alternatives are ready for decision.

### 3. Decision Freeze

Confirm the category, audience, usage task, package construction, target specification range, variant system, exact-copy state, and exclusions. Produce a `DecisionLock` and a `SeriesSystem` when multiple SKUs are requested.

Gate: approved fields are frozen; deliberately open fields and production unknowns are listed.

### 4. Packaging Direction Generation

Create enough meaningfully distinct packaging systems to support the requested decision, normally two or three when scope and budget permit. Keep the same locked facts and comparison conditions, apply every direction across every requested SKU, and produce inspectable visuals rather than stopping at written direction descriptions. Produce a `PackagingDirectionSet` with a direction-by-SKU matrix.

`compare` is the internal operation for this stage.

Gate: each direction is inspectable, comparable, distinct, permission-safe, and reviewed against the same baseline.

### 5. Selection And Refinement

Record the approved direction and source hashes in a `SelectionLock`. Correct a named failure class or coherent composite failure class without silently reopening identity. Produce refined packaging artifacts and correction records.

`refine` is the internal operation for this stage.

Gate: the requested correction is evidenced, locked fields remain intact, and any reopened field is explicit.

### 6. Ecommerce Asset Planning

Translate the approved package into a channel-specific sequence. Produce an `EcommerceAssetPlan` and one `AssetBrief` per requested image.

Supported asset roles, when the channel requires them:

- `catalog`: white or neutral hero, family line-up, alternate angles, structure views
- `detail`: ingredients, product texture, package details, verified selling-point information
- `usage`: preparation or usage steps
- `specification`: dimensions, quantity, count, or package specification
- `context`: lifestyle and usage context
- `campaign`: social cover, campaign crop, promotional composition
- `channel-variant`: platform crops, safe areas, and responsive variants

Gate: every asset has a job, source-backed copy, package state, composition, crop, and review profile. Unsupported claims are blocked rather than invented.

### 7. Ecommerce Set Generation

Generate or edit the approved sequence within resolved permissions and call budgets. Every asset handoff restates the package identity lock and only opens role-specific scene variables.

`present` is replaced by role-specific generation operations such as `catalog`, `detail`, `usage`, `context`, and `campaign`.

Gate: each requested asset is inspectable or has an explicit `blocked` or `missing` record.

### 8. QA And Delivery

Inspect full-resolution artifacts and every requested review profile. Review both per-image correctness and cross-set consistency. Produce a `DeliveryManifest` and runtime receipt.

Gate: `passed` requires every requested artifact and every predeclared required gate to pass. `draft` and `blocked` retain their bounded meanings.

## Core Contracts

Version 0.2 defines these named contracts:

- `ProjectState`
- `ProductBrief`
- `ResearchBoard`
- `PackagingOptionMatrix`
- `DecisionLock`
- `SeriesSystem`
- `PackagingDirectionSet`
- `SelectionLock`
- `EcommerceAssetPlan`
- `AssetBrief`
- `DeliveryManifest`
- `RuntimeReceipt`

The existing permission schema, RFC 6901 override rules, source authorization rules, hash binding, safe output rules, generation budgets, QA-plan hashes, independent-review identity, and `passed | draft | blocked` semantics remain normative.

## Research Boundary

Research is in scope when it supports product, audience, package, or ecommerce decisions. The Skill may use available research capabilities and must record source, date, access limits, confidence, and whether a statement is evidence, inference, hypothesis, or unknown. It must not claim exhaustive market coverage, consumer validation, legal clearance, or current platform compliance without appropriate evidence.

When live research is unavailable, the Skill creates a research plan and blocks evidence-dependent decisions. It does not route the whole project elsewhere.

## Production Boundary

The workflow can compare package structures and target specifications at concept stage. It cannot approve regulatory copy, trademarks, print artwork, dielines, materials, barrier performance, filling, sealing, transport, color matching, supplier manufacturability, or consumer preference. These remain explicit advisory findings and `remaining_work`.

## Open-Source Boundary

- Public examples use fictional products and self-created or documented-redistributable assets.
- Public files contain no private product names, private source images, private absolute paths, credentials, or proprietary project evidence.
- Runtime tools and providers are capabilities, not hard-coded dependencies.
- Paid calls, external processing, publication, and material scope expansion require explicit authorization.

## Public Example And Review Interface

The fictional pantry example must document the full contract chain from an initial product/package starting point through four-dimension research, multiple structure/specification options, decision freeze, comparable visual directions, and `DeliveryManifest`. If it maps historical artifacts into a newer contract chain, it must state the chronology and must not call that reconstruction proof of post-lock generation. Historical artifacts cannot replace the upstream product and research records. The optional offline review page must be bilingual and organize outputs by workflow stage and ecommerce role. It remains a local review aid, not proof of QA or publication.

## Acceptance Criteria

1. A request starting from an uncertain product idea stays in scope and receives a staged research-and-decision path.
2. A request starting from approved packaging produces only the channel roles that are requested or justified; context and campaign remain available but are not mandatory.
3. A multi-SKU request produces a full direction-by-SKU comparison matrix before selection.
4. A one-image correction still benefits from source hashing, a selection lock, and bounded change control.
5. Existing permission, privacy, receipt, QA, and production-boundary guarantees remain test-covered.
6. English and Chinese README files describe the same workflow, outputs, start states, and boundaries.
7. Public fixtures, tests, validators, a clean install, dated forward evidence for the stages actually rerun, a private local product-image trial, a deep humanizer review, and an independent final audit all pass before release.
