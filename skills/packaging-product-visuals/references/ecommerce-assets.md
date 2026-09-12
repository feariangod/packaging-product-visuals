# Ecommerce Assets

Use this reference for `ecommerce-planning` and `ecommerce-generation`. Ecommerce scenes may change context, but must preserve the approved **package identity** across assets.

## Plan The Set First

Create `EcommerceAssetPlan` before generation. Start from the target channel, buying journey, and information jobs; channel needs determine the asset roles. Record channel, sequence logic, selected SKUs, the active `DecisionLock` and `SelectionLock`, their canonical package-identity digest, the selected typography-system ID and digest when readable type is visible, required roles, crop variants, approved `exact_copy_item_ids`, approved `claim_item_ids`, review-profile IDs, and set-level QA gates. Create one `AssetBrief` for every requested image; do not use one generic prompt for the gallery.

Supported roles are channel-dependent:

- `catalog`: neutral hero, family line-up, alternate angles, or structure views;
- `detail`: ingredients, product texture, package details, or verified selling-point information;
- `usage`: preparation or usage steps grounded in verified instructions;
- `specification`: verified dimensions, quantity, count, or package specification;
- `context`: lifestyle or usage context anchored to the approved package;
- `campaign`: social cover, campaign crop, or promotional composition without media operations or invented offers;
- `channel-variant`: platform crop, safe-area, or responsive variant of another approved asset.

Not every channel needs every role, and no fixed image count is implied. Include only requested or justified roles, but every requested role needs at least one asset record or an explicit `blocked` record.

Do not prefill the role list during product definition, research, package decisions, or packaging generation. If the user asks for a "complete ecommerce set" without naming a channel or image jobs, keep roles open until `ecommerce-planning`; the supported-role list is not a checklist.

## Asset Brief

Each `AssetBrief` names its `status`, `unknown_fields`, role, job, audience task, SKU/object count, approved copy and claim item IDs, package state, selected typography-system binding, text rendering strategy, permitted scene variables, prohibited identity changes, composition, camera, crop/aspect ratio, background, lighting, required inputs, permissions, actual QA profile IDs, and approval provenance. Unsupported, unverified, working, or prohibited items are blocked rather than invented.

Only a complete, explicitly approved `AssetBrief` with `status: passed` is generation-eligible. A legacy or partial brief uses `status: draft`, records every missing field in `unknown_fields`, and stops at `ecommerce-planning`; it cannot be handed to an image tool. A role that depends on an unknown or unverified decision field remains draft or blocked.

Bind the plan and every brief to the same `SelectionLock.package_identity_sha256` and, when applicable, the same selected typography-system digest. Restate locked geometry, closure, logo/brand state, product and variant names, material cues, palette, defining graphic system, typography roles and distinctive features, and exact copy whenever they are visible.

Reference the selected editable artwork master and its manifest digest when available; see [package-master.md](package-master.md). Share those design inputs across briefs, but derive each scene's `target_object_count` from its own named visible instances. A closed pack, an opened pack, and a lifestyle scene do not necessarily have the same count. Package proportions and label/sleeve boundaries come from the approved source, not from a font specimen's display size.

## Role-Specific Generation

Immediately before generation or editing, recompute the selected package source SHA-256. Resolve permissions for every prompt-bound field, source, asset, copy item, claim, font asset, and output. Generate only the approved sequence and scene variables within the authorized call budget.

Use the approved typography rendering strategy. `model-native` typography is exploratory and cannot stand in for a locked distinctive type system when substitution would change identity. Use an approved reference, deterministic text overlay, or vector layout when exact type behavior matters. A model-generated package that keeps the words but falls back to generic type fails typography QA.

Complete selected-direction finish work before treating any ecommerce output as delivered. A direction-choice pass only establishes that the comparison was usable; it cannot replace delivery QA. Once a sequence and its budget are approved, continue through that scope without asking again for unchanged briefs. New publication, fees outside the approved budget, or material design changes remain separate decisions.

Role-specific context cannot silently redesign the package. A `context` or `campaign` asset may change scene, crop, props, lighting, or composition only as allowed by its brief. A `channel-variant` must retain its parent asset ID and package identity binding.

Create exactly one artifact record for every unique requested asset ID even when no image exists. `passed` and `draft` records need a produced artifact ID and inspectable locator. `blocked` and `missing` records keep produced artifact ID, locator, and hash null. Do not infer a file path or substitute an unrequested asset. Every record carries the expected package-identity digest; visual QA still verifies the pixels.

## Set Consistency

Inspect each image and the set as a whole. Check package identity, typography-system fidelity, SKU identity and order, exact copy, color/material behavior, claims, object count, role fulfillment, sequence coverage, crop/safe area, and visible reference leakage. Pass the set only when every requested artifact and every required per-image and cross-set gate passes.

Publication, paid media, influencer operations, platform compliance, consumer preference, conversion, and production approval remain separate from local concept-stage asset generation.
