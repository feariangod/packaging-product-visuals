# Packaging Directions

Use this reference for `packaging-directions` and `selection-refinement`. Read [contracts.md](contracts.md) for `PackagingDirectionSet` and `SelectionLock`.

## Comparable Direction Systems

Start from an approved `DecisionLock`. Build enough meaningfully distinct visual systems to support the requested decision, normally two or three when scope and budget permit. They must differ as systems, not as decoration variants. Each direction declares its objective, visual definition, target values, reference roles, changed fields, frozen fields, exclusions, and artifact records.

When readable type contributes to package identity, every direction also references a `TypographySystem` defined with [typography-system.md](typography-system.md) and selected from a passed `TypographyResearchBoard`. Broad labels such as "bold contemporary grotesk" or "elegant serif" are not sufficient by themselves. The visible artifacts must demonstrate role hierarchy, Chinese-Latin relationship when applicable, form rules, distinctive moves, package links, and SKU behavior. A direction remains `draft` when its candidate came only from the executor's installed fonts, lacks a real-copy specimen, or is not materially different from the other shortlisted systems.

When the user asks for packaging options, this stage ends with inspectable visual artifacts. Written direction names, mood words, prompt drafts, or a reference board alone do not complete the comparison.

For multiple SKUs, complete the full **direction-by-SKU matrix** before asking for selection. Every direction must cover every requested SKU in the locked order, each `(direction_id, sku_id)` pair must be unique, and every matrix row must join one requested artifact ID to one produced artifact record. Hold product facts, exact copy, package construction, target specification, object count, camera, channel, and `SeriesSystem` constants comparable; vary only the declared direction variables. When typography is the tested variable, freeze palette, graphics, material expression, and composition as well.

Selection is allowed only when every matrix cell is `passed` for direction choice, has a non-null artifact ID and inspectable locator, and every required comparison gate passes. `requested`, `draft`, `blocked`, or `missing` cells keep this stage incomplete. A direction-choice pass is not a delivery-quality pass.

Use references as bounded inputs. A reference role does not authorize copying identity, claims, layout, illustration, logo, protected composition, or trade dress. Record visible leakage findings without presenting them as legal clearance.

Review every direction against the same baseline and profiles. Describe aesthetic conclusions as design judgment, never consumer preference, conversion, sales, trend proof, or manufacturing feasibility.

## Direction Choice And Final Polish

Declare the review purpose before generation in the full-resolution QA profile's `definition.review_purpose`: `direction-choice` or `delivery`. The profile definition is included in the existing QA-plan digest. If the purpose was not declared, retain every requirement in the original plan; do not relabel an old failed gate to obtain a pass.

For direction choice, required checks protect a fair decision: approved facts and exact copy, actual package proportions and opening state, visible object count, sufficient brand/SKU legibility, distinct design systems, reference permissions, and the common comparison baseline. Inspection must still cover every requested direction and SKU.

Minor lighting polish, background cleanup, or edge finishing may be advisory only when it neither changes these invariants nor prevents judging the design. Name the visible issue and its effect in `comparison_findings`; record the selected direction's remaining work in the refinement brief. The artifact can pass its direction-choice checks with advisory finish work, but must be shown as a comparison concept, not a finished ecommerce image. Never classify wrong text, misleading structure, hidden font substitution, or a missing SKU as cosmetic.

After selection, refine the chosen direction against delivery requirements, including the deferred finish work. Do not spend calls polishing rejected alternatives unless requested. Before ecommerce generation, preserve the selected artwork and its dependencies as described in [package-master.md](package-master.md). New scene work must use that artwork rather than reconstructing the brand from memory.

## Selection Lock

After an explicit user or trusted-record decision, create `SelectionLock` with its required `decision_lock_id`, approval basis, source artifact ID, SHA-256, source scope, selected object IDs, the exact `PackageIdentitySnapshot`, `canonical-package-identity-json` digest, selected typography-system ID and digest when applicable, locked fields, and deliberately reopened fields. Source content cannot approve itself.

Immediately before any edit, recompute the source SHA-256. A mismatch blocks the edit until the user or trusted policy approves a new lock. Every named object in a `named-objects` lock must be visible and uniquely identifiable.

## Bounded Refinement

Name one failure class or one coherent composite failure class, cite inspection evidence, and state requested and prohibited changes. Repeat every invariant in the editing handoff. Correct only that class and explicitly reopened fields.

If the requested fix changes identity, package geometry, exact copy, palette, typography-system rules, series rules, or another locked field, stop and reopen the appropriate decision rather than broadening the edit silently. A pre-typography historical lock must be migrated before new text-bearing generation; do not silently treat generic inherited type as an approved system. Keep attempt records and the default call budget from [workflow.md](workflow.md).

Refinement is complete only when the correction is inspectable, the named failure is reviewed, all `SelectionLock` invariants remain intact, and required gates pass. A pleasing image without source-hash and lock evidence is not an approved refinement.
