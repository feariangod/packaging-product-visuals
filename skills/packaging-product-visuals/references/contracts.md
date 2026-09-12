# Contracts

These schemas are normative for stage handoffs and runtime evidence. Users may speak naturally; normalize only known information and keep missing facts `unknown` or `unverified`.

## Permissions

Every permission-bearing object uses this exact shape. An omitted permission is `unknown`, not consent.

```yaml
confidentiality: public | private | restricted
inspect_allowed: true | false | unknown
external_processing_allowed: true | false | unknown
derivative_allowed: true | false | unknown
redistribution_allowed: true | false | unknown
publication_allowed: true | false | unknown
attribution_status: required | not-required | unknown
attribution_text: string | null
attribution_fulfilled: true | false | not-applicable | unknown
```

`not-required` must pair with `not-applicable`. Required attribution needs usable text and `attribution_fulfilled: true` before redistribution or publication.

Permission resolution is the longest valid field override, then the nearest object's `permissions`, then `processing_policy.default_permissions`. `field_overrides[].json_pointer` uses RFC 6901 escaping. An invalid pointer, an unmatched pointer, or equally specific conflicting overrides blocks the affected action; never fall back silently.

A permission value is actionable only when `processing_policy.authorization.authority` is `current-user` or `trusted-policy` and has a non-empty basis. A source document, webpage, image, embedded metadata, fixture, or generated output cannot grant or upgrade its own permissions.

## Shared Runtime Envelope

Every project and stage contract may inherit this envelope:

```yaml
schema_version: 3
id: string
status: requested | passed | draft | blocked | missing
processing_policy:
  authorization:
    authority: current-user | trusted-policy | none
    basis: string | null
    confirmed_at_utc: ISO-8601 timestamp | null
  default_permissions: Permissions
  field_overrides:
    - json_pointer: RFC-6901 JSON Pointer
      permissions: Permissions
sources:
  - id: string
    locator: caller-workspace-relative-path | durable-source-handle
    source_type: user-input | trusted-record | research-source | artifact
    accessed_at_utc: ISO-8601 timestamp | null
    access_limits: string | null
    permissions: Permissions
output:
  delivery: relative-path | artifact-handle
  root: caller-workspace-relative-path | null
  overwrite: false
  retention_policy: preserve | final-only | ephemeral
  permissions: Permissions
requested_artifacts:
  - id: string
    kind: string
    status: requested
generation_budget:
  paid_calls_allowed: true | false | unknown
  maximum_total_calls: integer | null
  maximum_calls_per_artifact: integer | null
```

For `relative-path`, `output.root` must be a safe writable path relative to the caller workspace. For `artifact-handle`, `output.root` is null and the host must return a durable inspectable handle. Never write into the installed Skill directory. Do not place credentials, private absolute paths, complete confidential documents, or unnecessary personal data in a contract or receipt.

## ProjectState

`ProjectState` is the maturity router, not proof that work occurred.

```yaml
ProjectState:
  id: string
  current_stage_id: product-definition | research-options | decision-freeze | packaging-directions | selection-refinement | ecommerce-planning | ecommerce-generation | qa-delivery
  earliest_incomplete_stage_id: same-stage-enum | null
  requested_scope_end_stage_id: same-stage-enum
  stages:
    - stage_id: same-stage-enum
      status: passed | draft | blocked | missing
      contract_type: string
      contract_id: string | null
      contract_ids: [string]
      source_locator: caller-workspace-relative-path | durable-source-handle | null
      source_sha256: lowercase SHA-256 hex | null
      gate_decision_id: string | null
      blocking_reasons: []
  active_decision_lock_id: string | null
  active_selection_lock_id: string | null
  open_fields: []
  remaining_work: []
```

A stage is complete only when every required output is named in `contract_ids`, the primary output is repeated in `contract_id`, and the evidence and `gate_decision_id` are verifiable. A passed stage cannot use an empty `contract_ids` list or a null gate decision. Route to the earliest incomplete stage. Set `earliest_incomplete_stage_id: null` only when every stage through `requested_scope_end_stage_id` has passed; `current_stage_id` then records the terminal stage that was completed. A conflict with a lock reopens the stage that owns the lock, not unrelated accepted stages.

## ClaimItem

```yaml
ClaimItem:
  id: string
  value: string
  source_id: string | null
  approval_state: approved | working | prohibited | unknown
  approved_by: current-user | trusted-record | null
  approval_basis: string | null
  approval_source_id: string | null
  approval_record_id: string | null
  permissions: Permissions
```

An approved claim needs a non-null source, approver, approval basis, and actionable permissions. A `trusted-record` approval also needs `approval_source_id` and `approval_record_id` that resolve to an independent inspectable source and record; source content cannot approve itself. `working`, `prohibited`, and `unknown` claims cannot enter rendered copy as approved claims.

## ExactCopyItem

```yaml
ExactCopyItem:
  id: string
  value: string
  source_id: string | null
  copy_role: brand | product-name | variant-name | quantity | instruction | legal | other
  approval_state: approved | working | prohibited | unknown
  approved_by: current-user | trusted-record | null
  approval_basis: string | null
  approval_source_id: string | null
  approval_record_id: string | null
  permissions: Permissions
```

Every visible exact-copy value is referenced by `ExactCopyItem.id`; a source document ID alone is insufficient. A `trusted-record` approval also needs `approval_source_id` and `approval_record_id` that resolve to an independent inspectable source and record; source content cannot approve itself. Unknown or working copy remains blocked from exact-copy generation unless the brief explicitly requires no readable copy.

## ProductBrief

```yaml
ProductBrief:
  id: string
  product:
    category: string | unknown
    product_name: string | unknown
    form: string | unknown
    usage_occasions: []
    audience:
      description: string | unknown
      evidence_ids: []
    variants:
      - id: string
        name: string | unknown
        sku_order: integer
    naming_state: approved | working | unknown
    verified_facts:
      - id: string
        value: string
        source_id: string | null
        permissions: Permissions
    claim_items:
      - ClaimItem
    prohibited_claim_item_ids: []
  exact_copy:
    readable_copy_required: true | false
    exact_copy_items:
      - ExactCopyItem
    required_item_ids: []
    forbidden_item_ids: []
    permissions: Permissions
  package_starting_point:
    construction: string | unknown
    target_specification: string | unknown
    status: confirmed | working | unknown
    constraints: []
    open_questions: []
  typography_starting_point:
    state: existing-approved | working | open | no-readable-copy
    required_scripts: []
    existing_asset_ids: []
    constraints: []
    open_questions: []
  commercial_constraints: []
  package_unknowns: []
  research_hypotheses: []
  approved_by: current-user | trusted-record | null
  approval_basis: string | null
  approval_source_id: string | null
  approval_record_id: string | null
  frozen_fields: []
  open_fields: []
```

The package starting point captures the first-pass construction and specification before alternatives are researched; `working` does not freeze either field. Unresolved facts may be approved only as research hypotheses. They cannot be used as verified claims or exact copy. A `trusted-record` ProductBrief approval also needs `approval_source_id` and `approval_record_id` that resolve to an independent inspectable source and record; source content cannot approve itself. `prohibited_claim_item_ids`, `required_item_ids`, and `forbidden_item_ids` must resolve uniquely to items in the same `ProductBrief`.

## ResearchBoard

```yaml
ResearchBoard:
  id: string
  product_brief_id: string
  scope:
    questions: []
    dimensions: [same-category-packaging, audience-aesthetics, typography, package-construction, package-specification]
    searched_sources: []
    date_range: string | null
    coverage_limits: []
  findings:
    - id: string
      statement: string
      evidence_class: sourced-evidence | visible-observation | design-inference | hypothesis | unknown
      source_ids: []
      observed_or_published_at: ISO-8601 date | null
      accessed_at_utc: ISO-8601 timestamp | null
      confidence: high | medium | low | unknown
      access_limits: string | null
      decision_use: string
  references:
    - source_id: string
      role: category-convention | audience-aesthetic | information-architecture | typography-convention | cjk-latin-pairing | type-package-integration | font-source | font-specimen | foundry-reference | series-system | ingredient-depiction | material-structure | package-specification | usage-context | composition | anti-reference
      permitted_elements: []
      prohibited_elements: []
  evidence_gaps: []
  research_plan_if_blocked: []
```

Evidence classes must not be collapsed. A normal product-to-packaging run covers all five named dimensions unless an approved input already fixes one or the record explains why it is irrelevant. Research records access limits and cannot claim exhaustive coverage, consumer validation, current platform compliance, or legal clearance without appropriate evidence.

## TypographyResearchBoard

```yaml
TypographyResearchBoard:
  id: string
  status: passed | draft | blocked
  product_brief_id: string | null
  research_board_id: string | null
  decision_lock_id: string | null
  reopened_selection_lock_id: string | null
  scope:
    category: string | unknown
    audience_task: string | unknown
    required_scripts: []
    exact_copy_item_ids: []
    named_profile_ids: []
    candidate_target: integer | null
    coverage_basis: string
    source_classes_required: []
    coverage_limits: []
  sources:
    - source_id: string
      source_class: category-reference | foundry | official-repository | font-distributor | user-licensed-asset | other
      locator: caller-workspace-relative-path | durable-source-handle
      accessed_at_utc: ISO-8601 timestamp
      upstream_revision_or_release: string | null
      license_id: string | unknown
      redistribution_allowed: true | false | unknown
      access_limits: string | null
  candidates:
    - id: string
      family_name: string
      classification: string
      source_ids: []
      intended_roles: []
      observed_character: []
      cjk_latin_strategy: string | not-applicable
      required_copy_coverage: pass | fail | unverified
      missing_characters: []
      fallback_substitution: none-observed | observed | unverified
      category_fit_hypothesis: string
      package_fit_hypothesis: string
      overuse_risk: string
      mismatch_risks: []
      specimen_artifact_id: string | null
      full_resolution_status: pass | fail | unverified
      named_profile_statuses: {}
      disposition: shortlisted | retained-alternative | rejected | blocked
      disposition_basis: string
  specimen_set:
    exact_copy_item_ids: []
    frozen_fields: []
    allowed_variables: []
    artifact_ids: []
    comparison_sha256: lowercase SHA-256 hex | null
  shortlist_candidate_ids: []
  shortlist_basis: string
  adequacy_exception:
    used: true | false
    basis: string | null
    approved_by: current-user | trusted-record | null
  evidence_gaps: []
  approved_by: current-user | trusted-record | null
  approval_basis: string | null
  approved_at_utc: ISO-8601 timestamp | null
  sha256: lowercase SHA-256 hex
  hash_basis: canonical-typography-research-json
```

Compute `sha256` from canonical UTF-8 JSON containing only `scope`, the complete ordered `sources`, `candidates`, `specimen_set`, `shortlist_candidate_ids`, `shortlist_basis`, `adequacy_exception`, and `evidence_gaps`. Sort object keys lexicographically, use compact separators, preserve array order, and encode UTF-8.

A passed board records why its search coverage is sufficient for the open decision. `candidate_target` is optional planning context, not a pass threshold. External evidence, meaningful alternatives, and an explained shortlist are required; no universal font-count or class quota applies. Every shortlisted candidate needs an inspectable real-copy specimen, `required_copy_coverage: pass`, `fallback_substitution: none-observed`, explicit source/license/redistribution state, named mismatch risks, and passed full-resolution plus required named-profile review. Rejected discovery leads may omit specimens and retain their observed gaps. Cosmetic variants of one base family do not establish a broad search. Historical `normal_candidate_target`, `minimum_distinct_classes`, and `adequacy_exception` records remain readable with their original hashes; new research does not require an exception approval merely because it uses fewer candidates.

## PackagingOptionMatrix

```yaml
PackagingOptionMatrix:
  id: string
  research_board_id: string
  product_brief_id: string
  criteria:
    - id: string
      requirement: string
      evidence_ids: []
  options:
    - id: string
      construction: string
      target_specification_range: string | unknown
      opening_and_dispensing: string | unknown
      product_fit: string
      audience_task_fit: string
      storage_and_usage: string
      ecommerce_communication: string
      evidence_ids: []
      evidence_confidence: high | medium | low | unknown
      concept_risks: []
      supplier_questions: []
      production_validation_required: []
  preferred_option_id: string | null
  alternatives_retained: []
  recommendation_basis: string | null
```

Option comparison is concept-stage advice. It does not validate dielines, materials, filling, sealing, barrier performance, transport, labeling, or manufacturability.

## DecisionLock

```yaml
DecisionLock:
  id: string
  origin: workflow | imported-approved-package
  product_brief_id: string | null
  research_board_id: string | null
  packaging_option_matrix_id: string | null
  import_source_id: string | null
  import_source_sha256: lowercase SHA-256 hex | null
  approved_by: current-user | trusted-record
  approval_basis: string
  approval_source_id: string | null
  approval_record_id: string | null
  approved_at_utc: ISO-8601 timestamp
  category: string | unknown
  audience_task: string | unknown
  usage_task: string | unknown
  package_construction: string | unknown
  target_specification_range: string | unknown
  variant_ids: []
  exact_copy_state: approved | working | no-readable-copy
  claim_items:
    - ClaimItem
  exact_copy_items:
    - ExactCopyItem
  claim_item_ids: []
  exact_copy_item_ids: []
  prohibited_claim_item_ids: []
  exclusions: []
  unknown_fields: []
  unverified_fields: []
  frozen_fields: []
  open_fields: []
  verified_prompt_fact_fields: []
  production_unknowns: []
  source_contract_hashes:
    hash_basis: canonical-sorted-compact-utf8-json
    product_brief_sha256: lowercase SHA-256 hex | null
    research_board_sha256: lowercase SHA-256 hex | null
    packaging_option_matrix_sha256: lowercase SHA-256 hex | null
```

For a **workflow-origin** lock, `product_brief_id`, `research_board_id`, `packaging_option_matrix_id`, and all three source-contract hashes are required; import fields are null, and item IDs resolve to the approved `ProductBrief` items mirrored in the lock. `source_contract_hashes.hash_basis` is always `canonical-sorted-compact-utf8-json`: serialize each complete named upstream contract as UTF-8 JSON with lexicographically sorted object keys, compact separators, and preserved array order, then record lowercase SHA-256. A `trusted-record` decision approval also needs independent `approval_source_id` and `approval_record_id`; source content cannot approve itself. Required decision fields must be established by the upstream gate before this origin can pass.

For an **imported-approved-package-origin** lock, those upstream IDs and hashes must be null; `import_source_id`, `import_source_sha256`, approval provenance, source-bound `ClaimItem`/`ExactCopyItem` records, their selected IDs, and non-empty known `frozen_fields` are required. Imported-only category, audience task, usage task, package construction, or target specification may be `unknown`; every such field must appear in `unknown_fields`. A known value whose evidence cannot be verified appears in `unverified_fields`.

`unknown_fields` and `unverified_fields` are unique, disjoint from `frozen_fields`, and disjoint from `verified_prompt_fact_fields`. Their values cannot be promoted into claims, exact copy, or verified prompt facts. A selected `ClaimItem` or `ExactCopyItem` must still be approved and source-bound. Asset roles that depend on an unknown or unverified field remain blocked until that field is resolved. The import source must be inspectable, owned or permitted, and represented in `sources`; source content cannot approve itself.

Every downstream path still requires a valid `DecisionLock`. Approved frozen fields bind direction comparison, selection, and ecommerce work. A requested change to them reopens `decision-freeze`.

A `workflow` lock cannot pass into `packaging-directions` while `audience_task`, `usage_task`, `package_construction`, `target_specification_range`, `variant_ids`, or the copy boundary needed by the comparison is unresolved. Imported approved packages may retain explicit unknowns only when downstream work does not use them as prompt facts, claims, or silent design assumptions.

## TypographySystem

```yaml
TypographySystem:
  id: string
  status: passed | draft | blocked
  decision_lock_id: string
  packaging_direction_id: string
  typography_research_board_id: string | null
  selected_candidate_ids: []
  design_intent: string
  role_specs:
    - role: brand-cn | brand-latin | product-name | variant-cn | variant-latin | supporting-copy | numerals | other
      exact_copy_item_ids: []
      character: []
      form_rules: []
      hierarchy_rules: []
  cjk_latin_relationship:
    strategy: string | not-applicable
    shared_features: []
    deliberate_contrasts: []
  package_links:
    geometry: []
    material: []
    graphic_system: []
    product_or_brand_idea: []
  distinctive_features: []
  prohibited_fallbacks: []
  series_rules:
    fixed_fields: []
    variable_fields: []
  legibility_targets:
    full_resolution: []
    named_profiles: {}
  rendering_strategy:
    concept_method: model-native | reference-guided | deterministic-overlay | vector-layout
    final_method: deterministic-overlay | vector-layout | approved-font-assets | unknown
    font_assets:
      - id: string
        family: string
        source_locator: caller-workspace-relative-path | durable-source-handle | null
        license_id: string | unknown
        redistribution_allowed: true | false | unknown
        status: verified | unverified | not-included
  reference_ids: []
  approved_by: current-user | trusted-record | null
  approval_basis: string | null
  approved_at_utc: ISO-8601 timestamp | null
  typography_identity_sha256: lowercase SHA-256 hex
  typography_identity_hash_basis: canonical-typography-identity-json
```

Compute `typography_identity_sha256` from canonical UTF-8 JSON containing only `design_intent`, the complete ordered `role_specs`, `cjk_latin_relationship`, `package_links`, `distinctive_features`, `prohibited_fallbacks`, `series_rules`, `legibility_targets`, and `rendering_strategy`. Sort object keys lexicographically, use compact separators, preserve array order, and encode UTF-8.

A newly researched or reopened text-bearing direction cannot use `status: passed` when `typography_research_board_id` is null, its selected candidates are absent from that board's passed shortlist, or `typography-research-adequacy` did not pass. Historical typography systems without these fields remain readable evidence, but they cannot authorize a new text-bearing generation run after typography is reopened. The direction also cannot pass when role specs are empty, the Chinese-Latin relationship is missing when both scripts are present, package links are empty, no prohibited fallback is named, a required legibility profile is absent, or approval provenance is null. Broad labels such as "bold sans" do not satisfy `form_rules` or `distinctive_features`. `font_assets` may use `status: not-included` during concept work; a named or distributed font file requires inspectable source and license evidence.

## SeriesSystem

```yaml
SeriesSystem:
  id: string
  decision_lock_id: string
  sku_order: []
  shared_identity_fields: []
  fixed_hierarchy: []
  variable_fields: []
  differentiation_rules: []
  typography_comparison_baseline:
    required_scripts: []
    fixed_role_ids: []
    allowed_direction_variables: []
    prohibited_treatments: []
  comparison_conditions:
    package_snapshot: {}
    exact_copy_snapshot: {}
    counted_objects: [{id: string, label: string}]
    object_count: integer
    camera_baseline: {}
    channel_snapshot: {}
    exclusions: []
```

## PackagingDirectionSet

```yaml
PackagingDirectionSet:
  id: string
  decision_lock_id: string
  series_system_id: string | null
  internal_operation: compare
  directions:
    - id: string
      name: string
      objective: string
      typography_system_id: string | null
      visual_definition: {}
      target_values: {}
      reference_roles:
        - source_or_asset_id: string
          role: string
          permitted_elements: []
          prohibited_elements: []
      changed_fields: []
      frozen_fields: []
      exclusions: []
  requested_artifacts:
    - id: string
      direction_id: string
      sku_id: string
      status: requested
  artifacts:
    - requested_artifact_id: string
      artifact_id: string | null
      locator: caller-workspace-relative-path | artifact-handle | null
      locator_type: relative_path | artifact_handle | null
      sha256: lowercase SHA-256 hex | null
      status: passed | draft | blocked | missing
      source_asset_id: string | null
      source_object_id: string | null
      source_receipt:
        source_id: string
        receipt_id: string
        receipt_sha256: lowercase SHA-256 hex
        requested_artifact_id: string
  direction_by_sku_matrix:
    - direction_id: string
      sku_id: string
      requested_artifact_id: string
      artifact_id: string | null
      status: requested | passed | draft | blocked | missing
  comparison_profiles: []
  comparison_findings: []
```

The `direction_by_sku_matrix` is the normative **direction-by-SKU matrix**. It contains exactly one unique `(direction_id, sku_id)` pair for every direction/required-SKU combination. Its `requested_artifact_id` values must equal the exact requested-ID set in `requested_artifacts`, and each row must join to exactly one `artifacts` record.

Every text-bearing direction has one unique `typography_system_id` resolving to a `passed` `TypographySystem` with the same `decision_lock_id` and direction ID. A no-readable-copy direction uses null and records that state in the decision chain. A generic prose `visual_definition.typography` does not replace this binding.

For an artifact that maps a multi-object board into matrix cells, `source_asset_id` identifies the owned board, `source_object_id` identifies the visible named object, and `source_receipt` binds that board to an inspectable receipt, receipt-file hash, and receipt requested-artifact ID. The receipt artifact's locator/hash and all required recorded QA gates must match the matrix artifact before it may be `passed`. Every matrix cell must be `passed` against the declared direction-choice requirements, have a non-null `artifact_id` and inspectable locator, and pass every required comparison gate before any `SelectionLock` can be approved. `requested`, `draft`, `blocked`, or `missing` cells keep `packaging-directions` incomplete. Only declared direction variables may change; baseline and series fields remain comparable.

Declare `definition.review_purpose: direction-choice` or `delivery` in the full-resolution QA profile before generation. Non-critical finish issues may be advisory in `comparison_findings` for direction choice, but false facts, wrong copy, package geometry, missing objects/SKUs, or unfair comparison conditions are always required failures. Carry selected-direction finish work into refinement; a direction-choice pass cannot be reused as final delivery acceptance. Plans without an explicit purpose retain their original required gates.

## PackageIdentitySnapshot

Use exactly this field set wherever package identity is frozen:

```yaml
PackageIdentitySnapshot:
  decision_lock_id: string
  source_artifact_id: string
  source_artifact_sha256: lowercase SHA-256 hex
  package_form: string | unknown
  geometry: string | unknown
  closure_and_opening: string | unknown
  material_cues: string | unknown
  brand_mark_state: string | unknown
  product_name: string | unknown
  variant_identity_by_sku: {}
  exact_copy_item_ids: []
  palette: []
  defining_graphic_system: string | unknown
  typography_system_id: string | null
  typography_identity_sha256: lowercase SHA-256 hex | null
  series_system_id: string | null
  sku_order: []
```

Compute its digest from canonical UTF-8 JSON of the complete `PackageIdentitySnapshot` object: use this exact field set, retain explicit `unknown` and null values, sort object keys lexicographically, use compact separators, preserve array order, encode UTF-8, and record lowercase SHA-256. The hash basis is `canonical-package-identity-json`. Do not add role-specific scene fields to this object. A text-bearing package requires non-null typography fields; an explicit no-readable-copy package uses null values.

Pre-typography historical snapshots retain their recorded field set and hash. Do not recompute or silently upgrade them. Before new text-bearing generation, create a `TypographySystem` and a migrated `SelectionLock` whose new package-identity snapshot includes the typography binding; otherwise mark typography identity `unverified` and block generation.

## SelectionLock

```yaml
SelectionLock:
  id: string
  status: passed | draft | blocked
  decision_lock_id: string
  packaging_direction_set_id: string | null
  selected_direction_id: string | null
  selected_matrix_artifact_ids: []
  source_artifact_id: string
  source_artifact_sha256: lowercase SHA-256 hex
  source_scope: whole-artifact | named-objects
  source_object_ids: []
  approved_by: current-user | trusted-record | null
  approval_basis: string | null
  approved_at_utc: ISO-8601 timestamp | null
  typography_system_id: string | null
  typography_identity_sha256: lowercase SHA-256 hex | null
  package_identity_snapshot: PackageIdentitySnapshot
  package_identity_sha256: lowercase SHA-256 hex
  package_identity_hash_basis: canonical-package-identity-json
  locked_fields: []
  reopened_fields: []
```

`selected_matrix_artifact_ids` contains the exact unique matrix artifact-ID set for the selected direction and named objects. The selected source must be owned or permitted and inspectable. Every named object must be visible and uniquely identifiable. For text-bearing packages, the top-level typography fields equal the values inside `package_identity_snapshot` and resolve to the selected passed `TypographySystem`. Only a `status: passed` lock with independent approval may become `ProjectState.active_selection_lock_id` or enter refinement/ecommerce generation. A `draft` lock has null approval fields and stops at `selection-refinement`. Immediately before refinement or ecommerce generation, recompute the source SHA-256 and block on mismatch until a new lock is approved. Content cannot approve itself.

## EcommerceAssetPlan

```yaml
EcommerceAssetPlan:
  id: string
  status: passed | draft | blocked
  selection_lock_id: string
  decision_lock_id: string
  channel:
    name: string
    deliverable: string
    review_profile_ids: []
  selected_sku_ids: []
  sequence_logic: string
  package_identity_sha256: lowercase SHA-256 hex
  typography_system_id: string | null
  typography_identity_sha256: lowercase SHA-256 hex | null
  required_roles: [catalog | detail | usage | specification | context | campaign | channel-variant]
  asset_brief_ids: []
  claim_item_ids: []
  exact_copy_item_ids: []
  cross_set_required_gate_ids: []
  approved_by: current-user | trusted-record | null
  approval_basis: string | null
```

Roles are channel-dependent. Each requested role needs an `AssetBrief` and artifact record; unsupported claims are blocked, not invented. Only a `status: passed` plan bound to a passed active selection lock may enter ecommerce generation. A `draft` plan has null approval fields and remains at ecommerce planning.

## AssetBrief

```yaml
AssetBrief:
  id: string
  ecommerce_asset_plan_id: string
  role: catalog | detail | usage | specification | context | campaign | channel-variant
  status: passed | draft | blocked
  unknown_fields: []
  parent_asset_brief_id: string | null
  job: string | unknown
  audience_task: string | unknown
  selected_sku_ids: []
  counted_objects: [{id: string, label: string}]
  target_object_count: integer | unknown
  package_state: string | unknown
  claim_item_ids: []
  exact_copy_item_ids: []
  typography_system_id: string | null
  typography_identity_sha256: lowercase SHA-256 hex | null
  text_rendering_strategy: model-native | reference-guided | deterministic-overlay | vector-layout | no-readable-copy | unknown
  composition: {}
  camera: {}
  crop:
    aspect_ratio: string | unknown
    safe_areas: []
  background: {}
  lighting: {}
  required_input_asset_ids: []
  permitted_scene_changes: []
  prohibited_identity_changes: []
  package_identity_sha256: lowercase SHA-256 hex | null
  review_profile_ids: []
  approved_by: current-user | trusted-record | null
  approval_basis: string | null
  permissions: Permissions
```

For a `passed` plan, `EcommerceAssetPlan.package_identity_sha256` and every `AssetBrief.package_identity_sha256` must equal the active passed `SelectionLock.package_identity_sha256`. Text-bearing plans and briefs also carry the same non-null selected typography-system ID and digest; no-readable-copy assets use null typography bindings and the explicit `no-readable-copy` strategy. A draft plan may bind a candidate draft selection lock solely for planning readback; it cannot enter generation. Every referenced claim/copy ID must resolve uniquely to an approved, permission-resolved `ClaimItem` or `ExactCopyItem` carried by the active decision chain.

An `AssetBrief` is generation-eligible only with `status: passed`, no `unknown_fields`, non-empty job and audience task, known object count and package state, complete composition/camera/crop requirements, the active package-identity digest, a resolved typography binding and rendering strategy when readable type is visible, actual required profile IDs, resolved approved item references, and explicit user or trusted-record approval basis. A complete brief cannot self-approve.

`status: draft` permits necessary imported fields to be explicit `unknown`, null, or empty only when every gap is named in `unknown_fields`. A draft is not approved and must stop at `ecommerce-planning`; it cannot enter `ecommerce-generation`. `status: blocked` records a known planning precondition and its reason. Any role that depends on an unknown or unverified `DecisionLock` field remains draft or blocked.

Every handoff restates the approved package identity. Scene changes must not silently redesign geometry, closure, logo/brand state, product or variant names, material cues, palette, defining graphics, or exact copy.

For new render briefs and series baselines, `counted_objects` names each expected visible instance with a unique ID, including detached components and props. Derive the total from the list; do not count object types or infer totals from prose. A scene-specific list belongs to the brief, not to permanent product identity. Preserve historical records without this field, and derive a fresh list in the next run's preflight rather than rewriting old hashes.

## Editable Artwork Master

After selection, retain the editable artwork, declared font assets and license evidence, exact copy, palette, geometry, and surface-specific applicability. Reference its manifest path and file SHA-256 from the run's source bindings or `AssetBrief.required_input_asset_ids`. Scene-specific counts and lighting never change the locked package identity.

The optional local `PackageMaster` format and commands are documented in [package-master.md](package-master.md). Its version is independent of the workflow schema. A successful bundle check establishes file/dependency integrity only; it does not create a `SelectionLock`, approve fonts for redistribution, validate surface mapping, or pass visual/production QA. Use existing permitted design source formats when the helper cannot package them; record the limitation rather than treating an unsupported format as a failed design.

## DeliveryManifest

```yaml
DeliveryManifest:
  id: string
  project_state_id: string
  decision_lock_id: string
  selection_lock_id: string
  ecommerce_asset_plan_id: string | null
  source_bindings:
    decision_lock_sha256: lowercase SHA-256 hex
    decision_lock_hash_basis: canonical-sorted-compact-utf8-json
  requested_artifact_ids: []
  artifacts:
    - requested_artifact_id: string
      artifact_id: string | null
      asset_brief_id: string | null
      role: string
      locator: caller-workspace-relative-path | artifact-handle | null
      locator_type: relative_path | artifact_handle | null
      sha256: lowercase SHA-256 hex | null
      status: passed | draft | blocked | missing
      blocking_reason: string | null
      expected_package_identity_sha256: lowercase SHA-256 hex
      expected_typography_identity_sha256: lowercase SHA-256 hex | null
      review_profile_ids: []
  per_image_qa_status: pass | fail | unverified
  cross_set_qa_status: pass | fail | unverified
  completeness_status: passed | draft | blocked
  remaining_work: []
```

`DeliveryManifest.decision_lock_id` is always non-null, including approved-package imports. `source_bindings.decision_lock_hash_basis` is always `canonical-sorted-compact-utf8-json`: serialize the complete referenced `DecisionLock` as UTF-8 JSON with lexicographically sorted object keys, compact separators, and preserved array order, then record lowercase SHA-256. `requested_artifact_ids` contains no duplicates and must equal the exact requested-ID set in `artifacts[].requested_artifact_id`; each requested ID appears exactly once. `artifact_id` values are unique among non-null values.

`passed` or `draft` records require non-null `artifact_id`, an inspectable locator and locator type, and a SHA-256 when bytes are available. `blocked` or `missing` records require null `artifact_id`, locator, locator type, and SHA-256. Every `expected_package_identity_sha256` equals the referenced `SelectionLock.package_identity_sha256`; text-bearing artifacts also carry its typography digest. A passed delivery requires that lock to be the active passed lock. This canonical binding preserves package and typography identity across assets, while visual cross-set QA checks the rendered pixels. Every requested artifact must appear even if blocked or missing.

## QA Support Records

```yaml
GenerationReceipt:
  executor_id: string
  capability_used: string
  runtime:
    client: string
    client_version: string | null
    tool_or_provider: string | null
    model_or_version: string | null
    exposed_parameters: {}
    executed_at_utc: ISO-8601 timestamp
  input_asset_ids: []
  frozen_fields: []
  changed_fields: []
  attempts:
    - attempt_id: string
      requested_artifact_ids: []
      artifact_ids: []
      outputs:
        - locator: caller-workspace-relative-path | artifact-handle
          locator_type: relative_path | artifact_handle
          sha256: lowercase SHA-256 hex | null
      failure_class: string | null
      requested_changes: []
      preserved_fields: []
      outcome: passed | failed | blocked | missing
      executed_at_utc: ISO-8601 timestamp

ImageQAPlan:
  required_gate_ids: []
  cross_set_required_gate_ids: []
  review_profiles:
    - profile_id: string
      profile_scope: full-resolution | named-profile
      required: true | false
      definition: {}
  independent_review_required: true | false
  sha256: lowercase SHA-256 hex

ImageQAResult:
  plan_sha256: lowercase SHA-256 hex
  reviewed_by: current-user | independent-agent | generating-agent
  reviewer_id: string
  reviewed_at_utc: ISO-8601 timestamp
  gates:
    - gate_id: string
      scope: per-image | cross-set
      level: required | advisory
      requirement: string
      requested_artifact_id: string | null
      artifact_id: string | null
      profile_scope: full-resolution | named-profile | cross-set
      profile_id: string
      status: pass | fail | unverified
      evidence: string
  required_failures: []
  advisory_findings: []
```

`review_profiles` has unique `profile_id` values and exactly one required `full-resolution` entry with `profile_id: full-resolution`. Named profiles use their actual configured IDs; `review-profile-id` is not a literal value. Cross-set gates use `profile_scope: cross-set` and `profile_id: cross-set`.

## RuntimeReceipt

Every consequential run produces a stage-aware `RuntimeReceipt`:

```yaml
RuntimeReceipt:
  schema_version: 3
  id: string
  project_state_id: string
  stage_id: product-definition | research-options | decision-freeze | packaging-directions | selection-refinement | ecommerce-planning | ecommerce-generation | qa-delivery
  internal_operation: compare | refine | catalog | detail | usage | specification | context | campaign | channel-variant | inspect | none
  status: passed | draft | blocked
  source_brief:
    locator: caller-workspace-relative-path | durable-source-handle
    sha256: lowercase SHA-256 hex
  input_contract_ids: []
  output_contract_ids: []
  stage_outputs:
    - contract_type: string
      contract_id: string | null
      status: passed | draft | blocked | missing
      locator: caller-workspace-relative-path | durable-source-handle | null
      sha256: lowercase SHA-256 hex | null
      blocking_reason: string | null
  stage_checks:
    - check_id: string
      required: true | false
      status: pass | fail | unverified
      evidence: string
  requested_artifact_ids: []
  contract_snapshot:
    snapshot_level: full | redacted | digest-only
    normalized_contract: {}
    resolved_permissions:
      - subject_type: field | source | fact | copy | asset | font-asset | lock | output
        subject_id_or_path: string
        permissions: Permissions
        resolution_source: field-override | object | run-default
        authorization_source: current-user | trusted-policy
    sha256: lowercase SHA-256 hex
    hash_basis: canonical-runtime-contract-json
    omissions: []
  artifacts:
    - requested_artifact_id: string
      artifact_id: string | null
      locator: caller-workspace-relative-path | artifact-handle | null
      locator_type: relative_path | artifact_handle | null
      role: string
      status: passed | draft | blocked | missing
      sha256: lowercase SHA-256 hex | null
      blocking_reason: string | null
      expected_package_identity_sha256: lowercase SHA-256 hex | null
      expected_typography_identity_sha256: lowercase SHA-256 hex | null
  generation_receipt: GenerationReceipt | null
  qa_plan: ImageQAPlan | null
  qa: ImageQAResult | null
  remaining_work: []
```

The snapshot stores the complete runtime-normalized contract, including runtime authorization and any runtime-approved `DecisionLock` or `SelectionLock`, only when confidentiality and retention permit it. The static source brief remains non-authorizing and is bound separately by `source_brief.sha256`.

Compute `contract_snapshot.sha256` from canonical UTF-8 JSON of `contract_snapshot.normalized_contract`: sort object keys lexicographically, use compact separators, preserve array order, and record lowercase SHA-256. Otherwise retain a stable digest or explicit redaction marker, list every omission, and lower `snapshot_level`.

Every value sent to generation or editing must be covered by `resolved_permissions`. A `field` entry whose subject is an RFC 6901 pointer covers descendants; the longest matching recorded ancestor wins. Record separate subjects whenever sources, facts, copy, assets, locks, or output enter the request.

Compute `qa_plan.sha256` and `qa.plan_sha256` from the same canonical UTF-8 JSON object containing only `required_gate_ids`, `cross_set_required_gate_ids`, the complete ordered `review_profiles` objects with actual `profile_id` values, and `independent_review_required`. Sort object keys, use compact separators, preserve array order, encode UTF-8, and record lowercase SHA-256.

For each requested artifact, every predeclared per-image gate appears exactly once at `profile_scope: full-resolution` with `profile_id: full-resolution`, and exactly once for every required named profile using that profile's actual ID. Every predeclared cross-set gate appears exactly once total with `profile_scope: cross-set`, `profile_id: cross-set`, and null requested/artifact IDs. Omitted, duplicate, failed, or unverified required gates prevent `passed`. When independent review is required, `reviewer_id` must be non-empty and must differ from `generation_receipt.executor_id`.

`RuntimeReceipt.requested_artifact_ids` contains no duplicates and must equal the exact requested-ID set in `artifacts[].requested_artifact_id`. `passed` and `draft` artifact rows require a non-null unique `artifact_id` and inspectable locator. `blocked` or `missing` records require null `artifact_id`, locator, locator type, and SHA-256. For identity-bound rendering, `expected_package_identity_sha256` equals the active `SelectionLock.package_identity_sha256`; text-bearing artifacts also carry the active typography digest.

## Bounded Status Semantics

**Non-rendering stage status** applies to `product-definition`, `research-options`, `decision-freeze`, and `ecommerce-planning`, plus any stage run that requests only contracts. `passed` requires every required `stage_output` to exist with `status: passed` and every required `stage_check` to pass. `draft` means at least one inspectable stage output exists but a required output or check is draft, missing, failed, or unverified. `blocked` means a known precondition prevents every required stage output. `generation_receipt`, image `qa_plan`, image `qa`, `requested_artifact_ids`, and `artifacts` may be null or empty as defined by the schema; a successful `ProductBrief`, `ResearchBoard`, `PackagingOptionMatrix`, `DecisionLock`, or `EcommerceAssetPlan` is not blocked merely because no image was requested.

**Rendered-artifact status** applies only when the stage requests rendered artifacts. Artifact `blocked` means a known precondition prevents an attempt; `missing` means an authorized attempt yields no inspectable artifact; `draft` means an inspectable artifact exists but a required gate fails or is unverified; `passed` means an inspectable artifact exists and every applicable required gate passes. Overall `blocked` means no requested rendered artifact exists, overall `draft` means at least one exists but the exact requested set is not passed, and overall `passed` requires every requested artifact plus all per-image and cross-set required gates to pass.

`passed` is concept-stage completion only. Production, regulatory, legal, supplier, consumer, conversion, and platform approval remain advisory or unresolved work.

## Legacy v0.2 Typography Migration

Schema-version-2 records created before `TypographySystem` remain readable historical evidence. Preserve their bytes, hashes, statuses, and original package-identity field set. Do not mark them failed solely because typography fields are absent.

Before a new text-bearing packaging refinement or ecommerce generation uses one of those records, route to `selection-refinement`. Create an inspectable typography comparison or approved imported type specimen, a schema-version-3 `TypographySystem`, and a new `SelectionLock` whose package-identity snapshot includes the typography ID and digest. Until that migration is approved, typography identity is `unverified` and the new text-bearing handoff remains `draft` or `blocked`.

## Legacy v0.1 Import

Existing v0.1 fixtures may contain `mode: compare | refine | present`, `product_baseline`, `comparison_directions`, `correction:`, or `presentation:`. Preserve them as historical source inputs. Map `compare` to `packaging-directions` and `refine` to `selection-refinement` without rewriting old receipts.

A neutral legacy `present` may map only to exactly one `catalog` draft. Populate only fields directly supported by the legacy brief; keep missing role job, audience task, approved item IDs, package state, crop, parent, identity digest, typography binding, and profile definitions `unknown` or incomplete, then stop at `ecommerce-planning` for approval. Ambiguous legacy `present` input must not infer or expand additional roles. Always preserve the old receipt and hash bytes unchanged, including its historical three-field QA-plan hash basis and legacy gate `profile` field. Current requests do not use a top-level mode, and generic `present` is never an ecommerce role.

Legacy v0.1 receipts retain `profile` exactly as recorded. Validators may read it for historical verification but must not rewrite it into `profile_id`, alter its contract snapshot, or recompute its hashes under current rules.
