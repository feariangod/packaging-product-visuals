# Workflow

Use this reference after reading the contract. Work with capabilities, not fixed provider names or unsupported model parameters.

## Shared Steps

1. Classify the request as `compare`, `refine`, or `present`. Route research-only, prompt-only, campaign, prepress, regulatory, manufacturing, logo, generic photography, and competitor-copy work outside this Skill.
2. Inventory image inspection, generation, editing, metadata reading, permitted-reference access, and optional local-review capability. Record unavailable capabilities.
3. Establish product truth. Keep confirmed facts, source-stated facts, visible observations, design inference, hypotheses, and unknowns distinct.
4. Resolve prompt-bound permissions before external processing. Read [rights-and-privacy.md](rights-and-privacy.md).
5. Build the `ProductBaseline`, set a safe relative-path or host-artifact destination, name artifacts, establish required QA gates, and declare a review profile before generation.
6. Compile a generation or editing handoff with subject, artifact, package geometry and material, composition, channel, exact-copy priority, permitted asset roles, frozen and open fields, exclusions, and output expectations.
7. Run only authorized attempts. Do not overwrite by default. Preserve attempts only as allowed by `retention_policy`.
8. Inspect high resolution and each requested profile. Read [packaging-qa.md](packaging-qa.md), then write the contract receipt.

## Compare

Create two or three directions that differ in declared visual-system variables only. Each direction restates its frozen fields and exclusions. Keep product facts, package structure, exact copy, SKU order, object count, camera baseline, and channel comparable. Do not turn a reference role into permission to copy identity, claims, or protected composition.

For each direction, compare against the same baseline before discussing preference. Mark aesthetic assessments as design judgment, not consumer validation. A visual comparison does not establish claims, preference, conversion, sales, or manufacturing feasibility.

## Refine

Start only from an inspectable selected direction or owned/permitted source artifact. Create a `SelectionLock` before editing, including source hash, approval basis, identity snapshot, locked fields, and reopened fields. Immediately before editing, recompute the source SHA-256 and block if it differs from the lock. Name one `failure_class` such as exact text, composition, color or material, package geometry, anatomy, reference leakage, or channel crop.

Repeat every invariant in the handoff. Change only that failure class and explicitly reopened fields. If a requested change would reopen identity, package geometry, copy, palette, or other lock fields, stop and request a new selection decision rather than silently broadening the change.

## Present

Start only from an inspectable approved package with a selection lock. Immediately before presentation work, recompute the source SHA-256 and block if it differs from the lock. Keep brand, package geometry, exact copy, material, palette, and defining graphic system locked. Permit only explicitly named camera, crop, background, lighting, and neutral-staging changes.

Do not convert a neutral product presentation into a campaign, lifestyle scene, or a new visual identity. Publication is a separate permission from local generation and reviewer access.

## Corrections And Stopping

Inspect failures by class:

- exact text or functional components;
- composition or object count;
- color or material;
- package geometry or opening action;
- product or ingredient anatomy;
- visible reference leakage or similarity concern;
- channel crop or thumbnail recognition.

Correct one class per round. The default maximum is one initial attempt plus two correction attempts per artifact and failure class, and three calls per requested artifact. Count paid calls and do not use a paid fallback, change provider, install dependencies, or exceed the budget without explicit authorization.

Stop before the maximum when exact text or a machine-readable element fails twice total. Report `draft` and recommend deterministic typography or a component overlay. When required input, permission, authorization, or capability is missing, report `blocked`; when required gates remain failed or unverified on an inspectable artifact, report `draft`.

## Review Artifacts

Create artifacts only at the resolved safe destination. When an optional deterministic local review helper is available, it may prepare review files, but the workflow remains usable without it. Record relative locators or host artifact handles, hashes when bytes are available, review profiles, QA evidence, correction history, and remaining work in the receipt. Never claim a generated artifact passed without recorded inspection evidence.
