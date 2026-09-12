# Product And Research

Use this reference for `product-definition`, `research-options`, and `decision-freeze`. Contract shapes are normative in [contracts.md](contracts.md).

## Product Definition

Build `ProductBrief` from confirmed user input and trusted records. Capture category, product form, usage occasions, audience and buying task, requested variants, naming state, ID-bearing `ClaimItem` and `ExactCopyItem` records, verified facts with sources, commercial constraints, and permissions.

Also record the **package starting point** before research: the current construction candidate, target specification, whether each is confirmed or only working, practical constraints, and the questions that remain open. This is the user's first-pass product and packaging definition, not the final route. Do not turn category conventions or user aspirations into product facts. A source ID never substitutes for the exact approved claim or copy item.

The gate may accept unresolved items only as named hypotheses for research. A hypothesis cannot enter copy, image prompts, or selling-point communication as a verified claim.

## Evidence Model

Every `ResearchBoard` finding has a source, access date, access limitation, confidence, and exactly one evidence class:

- `sourced-evidence`: supported by the cited source within its stated scope;
- `visible-observation`: directly inspectable in a source image or artifact;
- `design-inference`: a bounded interpretation derived from evidence or observation;
- `hypothesis`: a proposition that needs testing or approval;
- `unknown`: not established.

Keep market signals, brand self-description, designer intent, platform engagement, and user approval distinct. None alone proves consumer preference, conversion, legal clearance, or a current trend.

## Research And Options

For a normal product-to-packaging run, research the open parts of these dimensions before visual directions:

- same-category packaging: common formats, front-of-pack hierarchy, series behavior, and useful anti-references;
- audience aesthetics: the target buyer's shopping task, recognition needs, tone, visual density, and evidence limits;
- typography: category conventions and overused fallbacks, Chinese-Latin relationships when applicable, reading distance, type-material and type-geometry relationships, distinctive opportunities, font-asset constraints, and a `TypographyResearchBoard` with real-copy specimens whenever typography remains open;
- package construction: viable forms, opening or dispensing action, storage, handling, and supplier questions;
- package specification: capacity or count range, footprint implications, variant fit, ecommerce communication, and production unknowns.

Add usage context and channel conventions when they affect the decision. A dimension may be skipped only when a current approved input already fixes it or it is genuinely irrelevant, and the reason must be recorded. Record search scope and material gaps; never claim exhaustive coverage.

Classify each reference by role, such as category convention, information architecture, typography convention, Chinese-Latin pairing, font source, font specimen, foundry reference, series system, ingredient depiction, material/structure cue, usage context, composition, or anti-reference. List permitted principles separately from prohibited identity, copy, claims, logos, protected composition, and trade dress.

Build `PackagingOptionMatrix` with the viable route and meaningful alternatives whenever alternatives exist. Compare product fit, user task, capacity/specification range, opening and dispensing action, storage, ecommerce communication, evidence confidence, concept risks, supplier questions, and production validation still required. A matrix with one preselected option is not a comparison unless the record explains why no other route is viable. Structure and specification research informs concept decisions only.

Present the research as a short visual decision board using the existing findings and option matrix, not another mandatory record. For each proposed route show the reference finding, the package/design choice it suggests, why it may fit the buying task, its tradeoff, and what remains unverified. Include construction/specification alternatives before choosing visual treatments. Explain what each proposed visual direction changes and why. A source list without a decision-use explanation is not the user-facing research deliverable.

Stop collecting sources when the remaining choice can be explained with credible alternatives and explicit gaps. Expand research when alternatives are indistinguishable, claims lack evidence, or a material question remains unanswered; do not fill a quota. Preserve already approved decisions and research only what a revision reopens.

If live research is unavailable, record the capability failure, create a query/source plan, and block only decisions that depend on missing evidence. Do not fabricate results or route the project away.

## Decision Freeze

For a normal workflow, create `DecisionLock` only after the option matrix and evidence gaps are visible. Record all three upstream contract IDs and hashes plus approval provenance for category, audience, use task, package construction, target specification range, variant system, approved claim/copy item IDs, exclusions, and prohibited claims.

Do not enter `packaging-directions` while audience task, usage task, package construction, target specification range, variant system, or copy boundary is still unknown or merely inferred. The user or a trusted record may approve a bounded concept decision despite incomplete market or production evidence, but the remaining uncertainty must stay visible and must not be described as consumer validation.

An already approved package may instead use `origin: imported-approved-package`. It still needs an inspectable permitted import source ID and SHA-256, user/trusted-record approval basis, source-bound claim/copy item IDs, and non-empty known frozen fields; it must not fabricate missing `ProductBrief`, `ResearchBoard`, or `PackagingOptionMatrix` records. Imported category, audience task, usage task, package construction, or target specification may remain `unknown` or unverified when the source cannot establish them. List those fields explicitly, never freeze them, and never use them as claims or verified prompt facts. Separate:

- `frozen_fields`: approved and stable for direction comparison;
- `open_fields`: deliberately unresolved but non-blocking for the next stage;
- `production_unknowns`: dieline, material, filling, sealing, barrier, transport, labeling, print, supplier, or other validation work.

For multiple SKUs, define `SeriesSystem`: fixed hierarchy and shared identity fields, variable fields, SKU order, differentiation rules, and comparison conditions. Leave typography open for direction comparison only when the intended roles, scripts, readability needs, existing brand assets, and prohibited treatments are known. Use [typography-system.md](typography-system.md) before a text-bearing direction is approved. A downstream request that changes a frozen field reopens `decision-freeze`.

Production validation is not performed by this workflow. Keep regulatory, trademark, dieline, material, barrier, filling, sealing, transport, color, supplier, and consumer-validation work in `remaining_work`.
