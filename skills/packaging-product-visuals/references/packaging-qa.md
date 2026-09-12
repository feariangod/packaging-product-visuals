# Packaging QA

Declare required gates before generation, hash the QA plan into the runtime receipt, and name the reviewer. Inspect every artifact at the highest available resolution, every required review profile, and the requested set as a whole. A visually appealing concept can still fail.

Use the declared review purpose from [packaging-directions.md](packaging-directions.md). Direction-choice review protects the comparison; delivery review also requires final finish. Choose advisory finish items before the run and never downgrade a failed critical gate after seeing the output. Preserve historical plans and results unchanged.

## Plan Binding And Review Identity

Use the canonical QA-plan hash defined in [contracts.md](contracts.md). Review-profile definitions have unique actual `profile_id` values and a discriminated scope: exactly one required `full-resolution` profile uses `profile_id: full-resolution`; each derived profile uses `profile_scope: named-profile` and its configured ID. Cross-set gates use `profile_scope: cross-set` and `profile_id: cross-set`.

For every requested artifact, record each required per-image gate exactly once at full resolution and exactly once at every required named profile. Record each required cross-set gate exactly once total. Omission, duplication, failure, or `unverified` status prevents `passed`.

Separate file evidence from visual judgment. Reuse a verified source/license or file-check record by reference across profiles; do not call repeated references separate visual inspections. Automated checks can establish dimensions, hashes, explicit resource dependencies, or arithmetic. Typography fit, physical plausibility, and hierarchy require looking at the image. Report material findings and the reviewer's identity, not a large check count as an aesthetic score. User preference, self-review, independent review, and production acceptance are different evidence.

When `independent_review_required: true`, record `reviewed_by: independent-agent`, a non-empty `reviewer_id`, and an identity different from the generation executor. A generating agent may gather evidence but cannot satisfy an independent-review requirement.

## Required Per-Image Gates

Retain these stable gate IDs for every generated or edited artifact:

- `artifact-type`: requested role, product, variant, and state are correct.
- `object-count`: requested objects and package silhouettes are complete.
- `package-geometry`: form, geometry, closure, material cues, and opening action are preserved.
- `exact-copy`: required visible brand, product, variant, quantity, and other exact copy are accurate; explicit no-readable-copy states remain text-free.
- `invented-claims`: no unsupported claims, certifications, marks, legal text, ingredients, prices, offers, instructions, or specifications appear.
- `reference-role`: output uses only permitted principles and has no visible prohibited-element leakage.
- `visual-hierarchy-identity`: hierarchy, defining graphic identity, palette, color differentiation, and single-image SKU recognition match the active locks.
- `typography-system`: when readable type contributes to identity, visible type roles, form rules, Chinese-Latin relationship, distinctive features, and series behavior match the approved `TypographySystem`.
- `typography-package-fit`: typography visibly belongs with the package geometry, material, graphics, product, and intended character rather than appearing as a generic fallback or unrelated overlay.
- `typography-legibility`: required type hierarchy survives full resolution and every named channel profile without clipping, crowding, substitution, or optical collapse.
- `product-anatomy`: when a product, ingredient, texture, cutaway, or prepared state is requested or depicted, its visible anatomy is plausible and consistent with verified inputs. Omit this gate only when the QA plan records why anatomy is not applicable.
- `channel-fit`: role, composition, camera, crop, safe area, background, lighting, and thumbnail recognition fit the approved brief.
- `artifact-integrity`: file or handle exists, is inspectable, has supported format/dimensions, a safe locator, hash when bytes are available, and a manifest entry.

Add stage-specific gates:

- `research-options` or reopened `selection-refinement`: `font-character-coverage` verifies that the actual candidate font contains every approved character assigned to it; `font-render-substitution` verifies that the declared font loaded without a hidden system fallback; `typography-research-adequacy` verifies inspectable external sources, meaningful candidate breadth, exact-copy specimens, required-character coverage, explicit license and redistribution state, named mismatch risks, and an evidence-backed shortlist.
- `packaging-directions`: `direction-comparability` verifies the same `DecisionLock`, `SeriesSystem`, SKU order, object count, package baseline, camera, channel, copy, and review profiles; only declared variables differ. A typography comparison also requires one inspectable `TypographySystem` per direction and a passed `typography-research-adequacy` result for the bound research board.
- `selection-refinement`: `selection-lock` and `named-failure-correction` verify the source hash, identity invariants, explicitly reopened fields, and evidenced correction.
- `ecommerce-generation`: `selection-lock`, `asset-role`, and `package-identity` verify the source hash, role job, and approved package identity.
- When actual font assets are named, handed off, or redistributed: `font-asset-provenance` verifies source, license, redistribution status, and whether the render substituted another font. It is advisory for unnamed exploratory type and required for a font-asset handoff.

Evaluate exact copy, type-system fidelity, claims, functional components, and geometry at full resolution. Review profiles are contract-defined; do not assume one fixed thumbnail size. Small supporting copy need not become readable in every thumbnail unless the brief requires it, but the intended brand and SKU hierarchy must survive. Record `pass`, `fail`, or `unverified` with concise visible evidence.

Before generation, derive the expected count from a named visible-instance list and check face proportions, label/sleeve boundaries, opening state, approved text (including decorative numerals), and reference roles. An old packaging photo can guide structure while a new artwork master controls graphics; state which source owns each property so obsolete lettering or sleeve lines do not return. After generation, count the visible instances and inspect the actual geometry rather than accepting a matching brief or hash as image evidence.

## Role Checks

- `catalog`: neutral or approved staging, correct line-up/order, usable silhouette, and no unintended identity change.
- `detail`: depicted ingredient, texture, package detail, or selling point is source-backed and matches the intended scope.
- `usage`: each step and package state follows verified instructions; no unsafe or invented action appears.
- `specification`: every dimension, quantity, count, and diagram label is verified and readable.
- `context`: setting and props support the intended use without implying unsupported audience, benefit, endorsement, or claim.
- `campaign`: composition and copy stay within the approved asset brief; no invented promotion, price, offer, performance claim, or publication status.
- `channel-variant`: parent asset binding, content identity, crop, and safe areas are preserved.

## Required Cross-Set Gates

Use these stable set-level gate IDs whenever more than one asset is requested:

- `set-completeness`: every requested `AssetBrief` has one artifact record with a bounded status.
- `cross-asset-package-identity`: geometry, closure, logo/brand state, product/variant names, material cues, palette, defining graphic system, and exact copy remain consistent across assets.
- `cross-asset-typography-system`: typography roles, Chinese-Latin relationship, distinctive features, and intended substitutions remain consistent across every text-bearing asset.
- `cross-asset-sku-consistency`: SKU identity, differentiation, and required order follow `SeriesSystem`.
- `cross-asset-claims-consistency`: claims and specifications are source-backed and do not conflict across the set.
- `sequence-role-coverage`: the approved ecommerce sequence and requested role jobs are fulfilled without redundant substitutions.
- `cross-asset-channel-fit`: aspect ratios, safe areas, crops, and review-profile recognition are coherent for the target channel.

For a typography candidate or direction set, add `typography-research-adequacy` exactly once as a cross-set gate. It fails when the set is composed mainly of one base family with cosmetic changes, when actual approved copy was not rendered, when hidden fallback cannot be ruled out, when source or license state is missing, or when the shortlist rationale relies only on the generating agent's unsupported taste.

A set cannot pass because its best image passes. Any requested `blocked` or `missing` artifact, failed or unverified per-image gate, or failed or unverified cross-set gate makes the overall result `draft` when at least one artifact exists.

## Corrections

Classify evidence by failure class before another call. Correct one failure class per round unless the approved request defines one coherent composite class. Restate all locks and prohibited changes. Stop after two total exact-text, typography-system, or machine-readable-element failures and use deterministic typography, a component overlay, or vector layout. Respect the call budget and preserve every attempt allowed by the retention policy.

## Advisory Production Boundaries

Keep editable final layout, dieline, bleed, legal labeling, print separations, material specification, filling, sealing, barrier performance, transport, color matching, samples, supplier manufacturability, and specialist review advisory for concept work. Font licensing may remain advisory only while no named font asset is included or redistributed; once a font asset enters the handoff, its provenance gate is required. Structure and target-specification research does not convert these into validated facts.

Do not report a concept or ecommerce image as print-ready, compliant, legally cleared, manufacturable, production-ready, consumer-validated, conversion-proven, or platform-approved. Visible reference-leakage review means only that the inspected output does not visibly reproduce the prohibited elements named in the reference record.
