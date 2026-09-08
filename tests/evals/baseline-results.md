# No-Skill Baseline Results

These RED observations use fictional packaging scenarios. The agents received
only the scenario prompts, without the approved design specification or a
candidate workflow Skill.

## Compare: Restricted Source Material

**Observed handling:** The response correctly avoided putting restricted
supplier/formula material into an external prompt and distinguished a visual
recommendation from print readiness.

**RED gaps:** It did not provide a machine-checkable receipt schema for locked
fields, approved prompt scope, actual paid-call count, or the status transition
from comparison to production development. Its stated comparison criteria were
useful but were not connected to evidence for each output.

## Refine: Local-Only Asset

**Observed handling:** The response promised a local-only edit and named the
fields it intended to preserve.

**RED gaps:** It asserted a local edit path without demonstrating that a
capable local editor was available. It also did not define a structured
before/after verification method that proves the change was limited to the
requested spacing, rather than relying on a visual assertion alone.

## Present: Publication-Gated Asset

**Observed handling:** The response identified the missing source asset and
withheld public posting pending explicit publication authorization, while
correctly recognizing that external image processing and local retention were
already authorized.

**RED gaps:** It did not create a formal `SelectionLock`, per-artifact status,
predeclared QA gates, output locator policy, or review-profile contract. The
prose response also did not distinguish `blocked` for the currently missing
source from a future local `draft` or `passed` result after generation.

## Baseline Conclusion

The baseline agents showed useful caution, but their safeguards were prose-only
and inconsistent across modes. The candidate Skill must turn permissions,
locked fields, capability checks, evidence, and status semantics into a common
receipt that can be evaluated rather than inferred.
