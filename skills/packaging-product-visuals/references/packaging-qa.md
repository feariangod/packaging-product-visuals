# Packaging QA

Define required gates before generation, hash that QA plan into the receipt, and identify the reviewer. Inspect every artifact at the highest available resolution and each requested review profile. Every predeclared required gate must be reported exactly once per artifact and required profile; omission or duplication is a failure. A concept can be visually appealing and still fail.

## Required Concept Gates

Use these stable gate IDs. Every mode requires `artifact-type`, `object-count`, `package-geometry`, `exact-copy`, `invented-claims`, `reference-role`, `channel-fit`, and `artifact-integrity`. `compare` additionally requires `direction-comparability`; `refine` additionally requires `selection-lock` and `named-failure-correction`; `present` additionally requires `selection-lock` and `presentation-lock`. A brief may add stricter gates, but it must not omit its mode's minimum set.

Record a `pass`, `fail`, or `unverified` result plus concise visual evidence for each applicable gate:

- Correct artifact type, product, variant count, and requested state.
- Complete object count and package silhouettes.
- Package form, geometry, material, closure, and opening cues.
- Required brand, product name, variant name, and exact copy.
- No invented claims, certifications, marks, legal text, ingredients, prices, or specifications.
- Product or ingredient anatomy when the visual request requires it.
- Hierarchy, series consistency, defining graphic identity, and color differentiation.
- Reference-role compliance and visible reference-leakage checks.
- Requested background, camera, crop, lighting, and channel fit.
- Full-resolution readability and recognition at every review profile.
- File existence, dimensions, supported format, relative locator, hash, and manifest entry.

Evaluate exact copy and functional components at full resolution. Review profiles are configured by the input contract; do not assume a fixed thumbnail size. A required `fail` or `unverified` result prevents `passed` and makes an existing artifact `draft`. When independent review is predeclared, record an independent reviewer ID distinct from the executor ID.

## Mode Checks

For `compare`, verify that product baseline, package structure, exact copy, SKU order, object count, camera, and channel remain comparable; only declared direction variables may differ.

For `refine`, verify the named failure class changed while every selection-lock invariant remains intact. A changed locked field is a required failure unless it was explicitly reopened.

For `present`, verify package geometry, closure, logo, product name, net weight, material, palette, and defining graphic system remain locked. Only declared presentation changes may vary.

## Advisory Production Boundaries

Keep these findings advisory for concept work: font licensing, editable layout, dieline, bleed, legal labeling, print separations, material specification, filling, sealing, barrier performance, transport, color matching, samples, and specialist review. Do not report a concept as print-ready, compliant, or production-ready.

Visible reference-leakage review means only that the inspected output does not visibly reproduce prohibited elements named in the reference manifest. It does not provide legal clearance or validate consumer preference, conversion, sales, shareability, or manufacturing performance.
