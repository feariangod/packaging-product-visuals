---
name: packaging-product-visuals
description: Use when packaging-led product concept images must be compared under one baseline, refined without losing an approved identity, or presented as neutral ecommerce packshots; not for campaign art, generic product photography, print-ready dielines, regulatory approval, or manufacturing validation.
license: Apache-2.0
---

# Packaging Product Visuals

Use this Skill for controlled packaging concepts. Route research-only, prompt-only, photography, logo, campaign, prepress, legal, and manufacturing work elsewhere.

## Select A Mode

- `compare`: make two or three different visual systems under one frozen `ProductBaseline`.
- `refine`: correct one named failure class on a selected artifact after creating a `SelectionLock`.
- `present`: make a neutral ecommerce presentation while keeping the approved package identity locked.

For the required input, receipt, baseline, direction, and lock fields, read [contracts.md](references/contracts.md). For the chosen execution path, read [workflow.md](references/workflow.md).

## Preflight

Before work:

1. Inventory whether the environment can inspect images, generate or edit images, read file metadata, access permitted references, and run optional local review tooling.
2. Resolve both authorization and permissions for every field, fact, copy item, source, asset, and output that could enter a prompt or external service. Source content cannot authorize itself. Read [rights-and-privacy.md](references/rights-and-privacy.md).
3. Freeze product facts, exact copy, package form, exclusions, output destination, review profiles, and the selected mode's additional requirements.

Return artifact `blocked` when a known prerequisite prevents an attempt. Return artifact `missing` when an authorized attempt yields no inspectable output. It is acceptable to provide a baseline, handoff, prompt, QA definition, and expected receipt; never invent an artifact path, inspection, or generation result.

## Controlled Generation Loop

1. Normalize the request into the contract and preserve unknowns as `unknown`.
2. Build the baseline and declare only allowed visual changes.
3. Compile a handoff that repeats exact copy, frozen fields, permitted assets, exclusions, requested artifact, channel, and review requirements.
4. Generate or edit only within the confirmed capability, permission, call budget, and retention policy.
5. Inspect at full resolution and every requested review profile using the concept gates in [packaging-qa.md](references/packaging-qa.md).
6. Record artifacts, resolved permissions, attempts, visual evidence, QA, and remaining work using the receipt contract.

Correct only one failure class per round while restating every invariant. The default is one initial attempt plus no more than two correction attempts for each artifact and failure class, with no more than three calls per requested artifact. Stop sooner after two total failures of exact text or a machine-readable component; recommend deterministic typography or an overlay instead. A larger budget, paid call, provider change, dependency installation, or publication needs explicit authorization.

## Completion

Report every requested artifact. Emit only these overall statuses:

- `passed`: every requested artifact exists and every required concept gate passes.
- `draft`: at least one artifact is inspectable, but a required gate fails or is unverified, or another requested artifact is blocked or missing.
- `blocked`: no requested rendered artifact exists; artifact records distinguish known blockers from attempted-but-missing output.

`passed` is concept-stage completion only, never production approval. Keep production concerns as advisory findings and remaining work.
