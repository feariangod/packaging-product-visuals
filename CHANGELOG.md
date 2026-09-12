# Changelog

## Unreleased

- Replaced the featured Quiet Pantry example with CORNER NOTE, a fictional ceramic scent tile set. Added an English and Chinese case study covering product and packaging decisions, three typography alternatives, the selected Sensory Serif design, and one Rain Cedar ecommerce hero.
- Included four unchanged, specifically authorized PNGs with asset hashes and font-source notes. The full gallery remains incomplete. Private working records and font files are not included; Quiet Pantry remains a historical test fixture.
- This documentation update does not change the installable Skill or the existing v0.2.0 tag and release archives.

## 0.2.0 - 2026-09-12

### Added

- Added maturity routing from `ProjectState` through product definition, research, package decisions, packaging directions, ecommerce planning/generation, and QA delivery.
- Added `ProductBrief`, `ResearchBoard`, `PackagingOptionMatrix`, `DecisionLock`, `SeriesSystem`, `PackagingDirectionSet`, `SelectionLock`, `EcommerceAssetPlan`, `AssetBrief`, `DeliveryManifest`, and stage-aware `RuntimeReceipt` contracts.
- Added direction-by-SKU comparison, cross-asset package identity, channel-selected ecommerce roles, focused workflow references, a bilingual local review page, and a public contract-chain fixture with explicit chronology limits.
- Added a Quiet Pantry fixture that retrospectively maps authored product/research records to two historical packaging-direction boards, then provides dated forward evidence from selection through a seven-role example gallery and 188-row independent QA.

### Changed

- Replaced the public mode-first interface with continuation from the earliest incomplete stage.
- Reordered the public Skill around the product-to-delivery process so contracts and release evidence support the work instead of replacing product, research, and confirmation decisions.
- Kept `compare` and `refine` as bounded internal operations and replaced generic `present` with role-specific ecommerce asset briefs.
- Expanded QA from individual operation checks to per-image, named-profile, and cross-set delivery gates.

### Workflow Update - 2026-09-12

- Merged the locally tested typography guidance into the repository source. Typography research now follows the open decision rather than a fixed candidate quota, and shortlisted systems are shown with actual copy at package proportions before photographic directions.
- Separated direction-choice checks from final polish while retaining critical copy, geometry, identity, permission, and comparison requirements. Deferred finish work belongs to the selected direction, not every rejected alternative.
- Added a local editable-artwork bundle helper and surface-specific reuse guidance. Bundle integrity is separate from visual review, font rendering, redistribution permission, and production validation.
- Clarified continuation within an existing authorization, visible-instance counting, and shared source records. Simplified the English and Chinese entrypoints while retaining links to dated evidence.
- Removed the migration tests' dependency on full Git history by retaining the original v0.1.0 helper with a fixed hash. Corrected Windows gallery finalization and test filenames, and made the private runtime harness explicitly POSIX-only without weakening credential checks.

The earlier test, installation, and visual-review counts describe their recorded runs. They do not certify this update. The maintainer's separate authorization for this release is recorded in [the publication record](docs/releases/v0.2.0-publication.json); original generation and audit records remain unchanged.

### Migration

- Preserve v0.1 receipts byte-for-byte as historical evidence; do not recompute them under v0.2 hash or profile rules.
- Bind imported decisions to inspectable source records and hashes. Unverifiable values remain `unknown` or `unverified`.
- Map an unambiguous legacy `present` request only to one `catalog` draft at `ecommerce-planning`; ambiguous input fails closed and must not expand.

### Boundaries

- Dated local evidence covers Quiet Pantry from selection through its seven-role gallery and 188/188 concept QA rows, plus five install layouts and three read-only workflow probes. The historical direction boards do not prove post-lock packaging generation. GitHub publication is a separate release action, not evidence of marketplace listing, production approval, consumer preference, or model compatibility.

## 0.1.0 - 2026-09-08

Initial public contract for controlled packaging product visuals.

- Added `compare`, `refine`, and `present` modes.
- Added product baseline, exact-copy, selection-lock, permission, output-status, reference, and visual-QA contracts.
- Added a fictional pantry-product fixture set with asset provenance and redistribution records.
- Added four final public fictional visual artifacts, two retained failed attempts, and full-resolution plus 320-pixel independent QA receipts.
- Added fresh-session routing and contract-behavior evidence for authorization, RFC 6901 overrides, artifact handles, and reviewer independence.
- Added standalone Skill and skills-only plugin layouts.
- Hardened review-pack overwrite so only a validated tool-owned pack can be replaced; ordinary and protected directories remain untouched.
- Removed partial image derivatives on review-pack failure before retaining a minimal non-image diagnostic.
- Fixed Windows validation by declaring canonical LF text checkouts and explicit UTF-8 test reads.
- Added release documentation and a cross-platform validation workflow.
- Validation scope is food and beverage packaging on the named tested matrix; other clients, providers, models, and consumer packaged goods remain `unverified` or experimental until independent forward tests exist.
- Concept completion does not imply print, regulatory, food-safety, or manufacturing approval.
