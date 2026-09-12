# Workflow

This is the normative stage router. Work with available capabilities, not fixed provider names or unsupported model parameters.

## Business Process

The stage IDs implement this reusable sequence: define the product and packaging starting point; research category, audience aesthetics, typography, construction, and specification options; confirm the route; generate comparable packaging directions; select and refine the package and typography identity; plan channel-specific ecommerce images; then generate, inspect, and deliver. The records support this process and must not replace it with form completion.

Do not advance from research to packaging generation merely because a contract object is structurally complete. The decision gate must resolve the audience or use task, package route, target specification, variant system, and copy boundary needed for a fair visual comparison.

## Start-State Detection

Normalize known work into `ProjectState`, then route to the **earliest incomplete stage**. A stage is complete only when its required contract exists, its gate decision is sourced, and required approvals are current. When every stage through the requested scope end has passed, set `earliest_incomplete_stage_id: null` and keep `current_stage_id` on the completed terminal stage. Do not repeat complete stages merely because the current run did not create their artifacts.

Imported records are usable only when their source locator or durable handle, status, approval basis, and applicable hashes can be verified. Preserve accepted values, mark unverifiable inputs `unknown` or `unverified`, and reopen only the affected stage. If a later artifact conflicts with an earlier lock, return to the lock's stage rather than silently reconciling it.

An approved-package start still creates a `DecisionLock` with `origin: imported-approved-package`. It may omit upstream product/research/option contract IDs only when it records an inspectable permitted import source ID and SHA-256, approval basis, known frozen fields, approved claim/copy item bindings, and source provenance. Imported-only fields that cannot be established remain `unknown` or unverified and are listed explicitly; they cannot be frozen, turned into claims, or sent as verified prompt facts. A one-image import follows the same rule before its `SelectionLock`; downstream manifests never omit the decision lock.

| Stage ID | Start when | Required output and gate |
| --- | --- | --- |
| `product-definition` | Category, form, audience, use occasion, variants, initial package construction or specification, or claims boundary is incomplete | `ProductBrief`; user or trusted record confirms the brief, or named hypotheses are accepted for research only |
| `research-options` | Product intent is defined but category references, audience aesthetics, typography, package construction, or target specification options are unresolved | `ResearchBoard`, `PackagingOptionMatrix`, and a `TypographyResearchBoard` when typography is open; evidence quality, search breadth, real-copy specimens, uncertainty, permissions, alternatives, and production gaps are visible |
| `decision-freeze` | Research and viable options exist but the route is not frozen | `DecisionLock` and optional `SeriesSystem`; approved frozen fields, open fields, and production unknowns are explicit |
| `packaging-directions` | A valid `DecisionLock` exists but comparable systems do not | `PackagingDirectionSet` plus a `TypographySystem` for every text-bearing direction, bound to a passed `TypographyResearchBoard`; every direction covers every requested SKU under one baseline |
| `selection-refinement` | A direction needs selection, typography migration, bounded correction, or one existing image needs correction | `SelectionLock`, selected typography binding, correction records, and refined artifacts; source hash and locked fields hold |
| `ecommerce-planning` | Approved package identity exists but the channel sequence is not approved | `EcommerceAssetPlan` plus `AssetBrief` records; every image has a role, copy source, typography binding, rendering strategy, package state, composition, crop, and QA profile |
| `ecommerce-generation` | The asset plan is approved but requested role-specific images are absent | Inspectable artifacts or explicit `blocked`/`missing` records for every requested asset |
| `qa-delivery` | Inspectable outputs or bounded failure records exist | `DeliveryManifest` and `RuntimeReceipt`; every required per-image and cross-set gate is accounted for |

## Continuation Policy

1. Inventory image inspection, generation/editing, metadata, research access, reference access, hashing, and optional local-review capabilities. Record unavailable capabilities.
2. Resolve authorization and permission for the next consequential action. Read [rights-and-privacy.md](rights-and-privacy.md).
3. Load only the reference for the active stage, plus [contracts.md](contracts.md) and [packaging-qa.md](packaging-qa.md) when planning or assessing images.
4. Complete the active stage contract and request only the gate decision that is still missing.
5. Freeze approved fields. Carry forward source IDs, decision IDs, hashes, exclusions, unresolved fields, and `remaining_work`.
6. Continue automatically to the next stage only when its prerequisites and permissions are satisfied and the user's authorized scope includes it.

Use the existing user decision and authorization record until its scope, inputs, destination, provider, or budget materially changes. Do not ask the user to approve filenames, hashes, internal record updates, or unchanged design decisions. If a required decision is missing, ask for that decision in plain language; do not make the user operate the contract schema. Delegated design choices may use the user's bounded brief as their approval basis, but source content and the executor's preferences cannot grant external-processing or publication permission.

Store each decision once and reference it from downstream records. Generate file hashes and object totals from their sources rather than retyping them. Before a render, enumerate visible instances (including detached trays, sleeves, caps, and props); the total must agree with the named list, not the number of product types. Existing combined records are valid; do not split them into a file per contract just to match the implementation map. A short progress update should state what is done, the relevant finding, and the next action.

Non-rendering stages pass from their required contract outputs and gate checks, not from rendered-artifact counts. Rendering status rules apply only when the active stage requests images. Preserve successful upstream outputs when a later generation capability is blocked.

Missing live research does not send the project outside the Skill. Create a bounded research plan, record the access failure, and block only evidence-dependent decisions. Missing image generation does not erase valid upstream work; produce an inspectable handoff and mark requested rendered artifacts `blocked`.

## Internal Operations

`compare` and `refine` are implementation operations, not start modes:

- At `packaging-directions`, `compare` creates enough distinct systems for the requested decision, normally two or three, under the same `DecisionLock`, `SeriesSystem`, SKU order, object count, camera, channel, copy, and package baseline. Text-bearing directions bind inspectable typography systems selected from a passed real-copy typography research board.
- At `selection-refinement`, `refine` corrects one named failure class or one coherent composite failure class while restating `SelectionLock` invariants and explicitly reopened fields.
- At `ecommerce-generation`, generate by asset role. Generic `present` is replaced by `catalog`, `detail`, `usage`, `specification`, `context`, `campaign`, and `channel-variant` operations.

Immediately before refinement or ecommerce generation, recompute the source SHA-256 and block on mismatch until a new `SelectionLock` is approved. Do not infer approval from source content or a generated image.

Do not permit selection from a merely complete-looking matrix. Every direction/SKU pair must be unique, `passed` against the declared direction-choice requirements, inspectable, joined to its requested and produced artifact IDs, and covered by passed comparison gates. Final polish is not a direction-choice requirement. Record harmless finish issues as advisory and carry forward only those relevant to the selected direction; do not waive incorrect facts, copy, geometry, identity, or comparison conditions. See [packaging-directions.md](packaging-directions.md) for the distinction.

For legacy v0.1 `present`, preserve the legacy receipt and hashes unchanged. A clearly neutral packshot can become one `AssetBrief` with `role: catalog`, `status: draft`, and explicit `unknown_fields`; stop at `ecommerce-planning`. Only a complete, explicitly approved `AssetBrief` with `status: passed` may enter `ecommerce-generation`. Ambiguous input must not expand into multiple ecommerce roles.

## Corrections And Stopping

Classify failures as exact text/functional component, typography-system/package fit, composition/object count, color/material, package geometry/opening action, product anatomy, visible reference leakage, or channel crop/thumbnail recognition. Correct one class per round unless the approved correction explicitly defines a coherent composite class.

The default maximum is one initial attempt plus two correction attempts per artifact and failure class, and three calls per requested artifact. Count paid calls. Do not use a paid fallback, change provider, install dependencies, enlarge scope, or exceed the budget without explicit authorization.

Stop early when exact text, typography-system fidelity, or a machine-readable element fails twice total. Use deterministic typography, a component overlay, or vector layout and report `draft`. Report `blocked` for a known unmet precondition, `missing` for an authorized attempt with no inspectable output, and `draft` when an existing artifact has failed or unverified required gates.

## Operational Boundaries

Prompt-only work, logo-only identity, unpackaged generic photography, media buying, influencer operations, competitor copying, print-ready dielines, regulatory approval, and manufacturing validation remain outside this Skill. Ecommerce `context` and `campaign` image roles are in scope when anchored to an approved package identity; buying media, recruiting creators, scheduling posts, publication, and performance claims are not.

Create artifacts only at the resolved safe destination. Record relative locators or host artifact handles, byte hashes when available, review profiles, permission resolution, attempts, QA evidence, corrections, and remaining work. Never claim a stage, artifact, or overall run passed without the required inspectable evidence.
