# v0.1 Full-Workflow Baseline Results

Recorded 2026-09-08 against base revision
`5d5fcaaa289da5bf6fbb09ec051a1d9d74c5adcb`. These are read-only probes of the
published v0.1 Skill routing, workflow, and contract references. They did not
invoke image generation, modify files, or claim runtime output.

## Source Receipt

Read from the pinned revision:

- `skills/packaging-product-visuals/SKILL.md`
  - Lines 3 and 9 describe the v0.1 scope and route research/campaign work
    away; lines 11-17 expose the `compare`/`refine`/`present` mode-first
    interface.
- `skills/packaging-product-visuals/references/workflow.md`
  - Lines 5-14 start with mode classification; lines 28-32 constrain
    `present` to neutral presentation and route campaign/lifestyle expansion
    away.
- `skills/packaging-product-visuals/references/contracts.md`
  - Lines 25-30 define the v0.1 normalized input around
    `mode: compare | refine | present`.

Probe commands used for the line-numbered readback:

```sh
git show 5d5fcaaa289da5bf6fbb09ec051a1d9d74c5adcb:skills/packaging-product-visuals/SKILL.md | nl -ba
git show 5d5fcaaa289da5bf6fbb09ec051a1d9d74c5adcb:skills/packaging-product-visuals/references/workflow.md | nl -ba
git show 5d5fcaaa289da5bf6fbb09ec051a1d9d74c5adcb:skills/packaging-product-visuals/references/contracts.md | nl -ba
```

## Uncertain Product Start

**Probe:** Start with a fictional pantry product idea whose category, audience,
package construction, and variant system are unresolved.

**v0.1 result:** The Skill routes research-only work away and begins only after
the packaging baseline is established for `compare`, `refine`, or `present`.
It has no `ProductBrief`, `ResearchBoard`, `PackagingOptionMatrix`, or
`DecisionLock` path for resolving upstream uncertainty.

**Failure to carry forward:** A product-origin request is out of the primary
workflow instead of receiving a bounded research and decision path.

## Approved-Package Gallery

**Probe:** Start from an approved fictional package identity and request a
complete ecommerce gallery, including information, usage, context, campaign,
and channel-specific variants.

**v0.1 result:** `present` supports a neutral ecommerce presentation with a
`SelectionLock`. The v0.1 routing and workflow explicitly route campaign and
generic photography work away, and define no `EcommerceAssetPlan` or
per-image `AssetBrief` roles.

**Failure to carry forward:** The downstream gallery is reduced to a neutral
packshot; detail, usage, specification, context, campaign, and
`channel-variant` roles have no in-scope workflow.

## Three-SKU Full Chain

**Probe:** Start from a fictional three-SKU product idea and request research,
package-option selection, comparable directions across all SKUs, selection,
and a complete ecommerce set.

**v0.1 result:** `compare` can preserve a fixed SKU order once a
`ProductBaseline` exists, but it cannot create the research or package-option
decision that precedes it. `present` does not expand the selected identity
into an ecommerce role sequence or bind identity across assets.

**Failure to carry forward:** v0.1 blocks or routes away both the upstream
research/decision roles and the downstream gallery roles, so it cannot deliver
the complete three-SKU chain.

## Baseline Conclusion

v0.1 retains bounded operations for comparison, correction, and
neutral presentation. It is not a product-to-ecommerce workflow: its public
contracts do not define maturity routing, a direction-by-SKU matrix,
cross-asset package identity, or a complete ecommerce asset plan. The v0.2
tests therefore begin RED until those structures exist.
