# Typography System

Use this reference whenever readable typography contributes to package identity. Exact copy answers **what the package says**; the typography system answers **why the words belong to this brand and package**.

## When It Is Required

A text-bearing packaging direction, selected package, or ecommerce image cannot pass on exact copy and hierarchy alone. It also needs a `TypographySystem` when type affects recognition, brand character, SKU differentiation, or the relationship between graphics and structure.

Typography may remain open during early research. It must be resolved before a text-bearing `PackagingDirectionSet`, migrated `SelectionLock`, or generation-ready `AssetBrief` is marked `passed`. A package explicitly designed with no readable copy records that exception instead.

## Research The Type Decision

Do not begin from the executor's installed fonts, one convenient host library, or a previously used neutral family. Create an inspectable `TypographyResearchBoard` before approving a new or reopened type direction. Research only what the decision needs, but make the search broad enough to reveal real alternatives:

- same-category type conventions and overused fallback patterns;
- audience recognition needs, reading distance, tone, and density without claiming unsupported preference;
- Chinese and Latin script relationships used by relevant packages;
- how type interacts with package geometry, opening, material, graphics, and SKU architecture;
- thumbnail behavior and the smallest information that must remain recognizable;
- available open-source, user-licensed commercial, and custom-lettering routes without treating them as equally redistributable;
- font source, upstream revision or release when available, license, redistribution, editable-layout constraints, required-character coverage, and substitution risk when actual fonts are named.

Choose breadth according to the unresolved decision. Compare materially different letterform and brand approaches, not just weights of one family. An unfamiliar category may need a broad scan; an approved identity with one missing script may need a focused search. State the coverage basis and gaps. There is no universal candidate count, class quota, or approval gate for using fewer fonts. Stop when the viable alternatives explain the choice; expand when the shortlist remains generic or poorly supported.

Render every shortlisted system with the approved brand, product, variant, quantity, and bilingual strings. Rejected discovery leads can remain source notes; they do not need a complete specimen. Inspect each finalist at full resolution and at every required named profile. Record missing characters, fallback substitution, the intended role, Chinese-Latin strategy, package-fit hypothesis, overuse risk, and mismatch risk. A font website sample, family name, or mood adjective is not a substitute for rendering the actual copy.

Shortlist systems only after comparing the same copy and review profiles. The finalists must differ in underlying letterform character and brand logic, not merely weight, tracking, rules, or decorative masks applied to one neutral base. Preserve rejected candidates and the reason for rejection so a narrow search cannot be disguised as a broad one.

Classify observations and design inference separately. A popular typeface, a designer statement, or a visual reference does not prove target-audience preference.

`typography-research-adequacy` passes only when the sources are inspectable, the candidate set is meaningfully broad, exact-copy specimens exist, required characters render without hidden fallback, license and redistribution states are explicit, category and anti-reference evidence are visible, and the shortlist rationale can be reviewed independently. A structurally complete board with self-authored claims but no external evidence remains `draft`.

## Define A Real System

Do not accept a direction described only as "bold sans", "modern serif", "clean type", or similar broad labels. Define enough visible rules that another agent or designer can distinguish a deliberate result from a generic fallback:

- roles for brand Chinese, brand Latin, product name, variant Chinese, variant Latin, supporting copy, and numerals when present;
- intended character for each role and the hierarchy between roles;
- form rules such as width, weight, contrast, terminals, corners, counters, rhythm, case, tracking, line spacing, and alignment;
- the intended Chinese-Latin relationship, including shared features and deliberate contrasts;
- one or more restrained distinctive moves tied to the package, product, or brand idea;
- explicit links to package geometry, material, graphic devices, and series behavior;
- prohibited fallbacks, substitutions, novelty effects, or decorative treatments;
- full-resolution and channel-profile legibility targets;
- a concept and final rendering strategy.

Distinctive does not mean every glyph is customized. A small repeatable move, applied to the right role, is usually stronger than unrelated display effects.

## Compare Directions Fairly

When typography is the variable under review, freeze product facts, exact copy, package construction, dimensions, material, palette, graphic blocks, SKU order, camera, and comparison profile. Change only the declared typography fields.

Show inspectable applications rather than mood words alone. Include every required SKU and enough scale to inspect the brand, product name, variant names, supporting copy, and numerals. A direction stays `draft` when its typography is merely named but not visibly demonstrated.

Before spending calls on photographic packaging directions, apply each finalist to a simple package-proportion layout. Derive the face ratio and any sleeve, label, or opening boundaries from the approved geometry; do not approximate them from a narrow font specimen. Show type with the intended palette, graphics, material context, and hierarchy. This is part of the packaging comparison, not a separate user approval ceremony. An explicitly typography-only revision freezes those other variables.

Do not force every shortlisted family into one rigid lockup. Freeze package construction, copy, palette, material intent, SKU order, and comparison profiles, while allowing each type system to use the spacing, line breaks, alignment, proportion, and restrained custom lettering required to demonstrate its real character. Record those changes as typography variables.

## Selection And Migration

The selected `TypographySystem` becomes part of package identity and is bound by ID and digest. A later request to change its role rules, Chinese-Latin relationship, distinctive features, or rendering strategy reopens `selection-refinement` or the earlier decision that owns the change.

Historical selected packages that predate the typography fields remain readable evidence. Do not recompute their old identity hashes. Before new text-bearing generation, either create and approve a migrated `TypographySystem` plus a new `SelectionLock`, or mark typography identity `unverified` and block the handoff.

## Rendering Strategy

Choose the least fragile method that meets the required fidelity:

- `model-native`: exploratory only, when broad type character is sufficient and substitution is acceptable;
- `reference-guided`: concept work anchored to an inspectable approved package or type specimen;
- `deterministic-overlay`: use real text layers over a generated or photographed package when exact words and type behavior matter;
- `vector-layout`: use real font assets or outlined lettering for controlled packaging artwork and high-fidelity mockups.

Choose the method before generation. When exact brand lettering or a named font must survive into the ecommerce set, prepare real-font artwork up front rather than waiting for text failures. Preserve the approved source artwork using [package-master.md](package-master.md). Planar mapping is not evidence that the same artwork wraps a curved bottle or flexible pouch correctly; inspect or adapt that surface separately.

Do not keep spending image-generation calls on exact typography failures. After two failed text or typography attempts, stop and use deterministic overlay or vector layout.

If an actual font family is named, record the asset and license status. Do not bundle or redistribute proprietary font files in a public Skill or example. Open-source status must be supported by inspectable license evidence; a familiar font name is not proof.

## Typography QA

Keep these checks separate from `exact-copy`:

- `typography-system`: the visible roles, form rules, Chinese-Latin relationship, distinctive features, and series rules match the approved system;
- `typography-research-adequacy`: the approved system comes from an inspectable, sufficiently broad, real-copy research board rather than an arbitrary local font choice or cosmetic variation of one base family;
- `font-character-coverage`: every shortlisted font asset contains the required approved characters for its assigned script and role, verified from the font rather than inferred from a browser screenshot;
- `font-render-substitution`: the specimen and downstream render use the declared font files without silent system fallback or an undeclared substitute;
- `typography-package-fit`: type visibly belongs with the package geometry, material, graphics, product, and intended character rather than appearing as a generic overlay;
- `typography-legibility`: the required hierarchy survives full-resolution and named channel profiles without clipping, crowding, or optical collapse;
- `font-asset-provenance`: when actual font assets are named or distributed, their source, license, redistribution status, and substitution state are recorded.

A concept may pass the first three checks while production font licensing and editable artwork remain open. `font-asset-provenance` becomes required when a named font file is included, handed off, or redistributed.
