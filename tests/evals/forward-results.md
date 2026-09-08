# Forward Test Results

Recorded on 2026-09-08. The public fixture is fictional and uses the explicit sample label `PPV FIXTURE`.

## Result

| Mode | Requested artifacts | Status |
| --- | --- | --- |
| `compare` | `compare-direction-a`, `compare-direction-b` | `passed` |
| `refine` | `refined-package` | `passed` |
| `present` | `ecommerce-packshot` | `passed` |

`passed` means that every requested concept artifact exists and every predeclared gate passed at full resolution and in the 320-pixel contain profile. It does not mean print-ready, legally cleared, manufacturing-validated, or production-approved.

Machine-readable run receipts and the complete artifact-by-gate-by-profile matrix are in [forward-receipts.yaml](forward-receipts.yaml). Candidate Skill classification evidence is in [routing-results.yaml](routing-results.yaml), permission and lock behavior evidence is in [contract-probe-results.yaml](contract-probe-results.yaml), and clean-install behavior is in [install-smoke-results.yaml](install-smoke-results.yaml).

## Runtime And Authorization

- Image workflow host: Codex desktop environment reporting `codex-cli 0.153.4` on macOS 26.5 arm64.
- Image capability: OpenAI-hosted image generation and editing.
- Provider model/version, seed, and lower-level generation parameters: not exposed by the host.
- Provider switch, fallback provider, or automatic dependency installation: none.
- Billing detail: not exposed by the host.
- Static briefs: `processing_policy.authorization.authority: none`; a fixture cannot authorize itself.
- Runtime authority: the current user explicitly authorized external image generation, derivative creation, retention of public test artifacts, and public GitHub publication on 2026-09-08.
- Inputs: self-authored fictional copy and repository-owned fixtures; no customer source, private path, or third-party reference image entered the public evidence.

The workflow retention setting governs repository-controlled artifacts only. It does not alter an external provider's own logging, safety, backup, training, or retention terms.

## Artifact Evidence

| Artifact | Dimensions | SHA-256 | Independent QA |
| --- | --- | --- | --- |
| `generated/compare-direction-a.png` | 1448 x 1086 RGB | `a2c1d38551febace8a1bfec48011e7e36528695e244ec892d2c4fa4ad3d4f4fb` | passed |
| `generated/compare-direction-b.png` | 1448 x 1086 RGB | `066cc63a2d2aa54a1b02e67104bab5b1a1e677c16d96e5ec641213f176c74aae` | passed |
| `generated/refined-package.png` | 1122 x 1402 RGB | `b2dce882f3c948b91ee8e0dca490a85727e8874e9bad305bfde742ead65cb059` | passed |
| `generated/ecommerce-packshot.png` | 1448 x 1086 RGB | `0458444242f134aaf4865366f0e69e9170edaed7fb9c43e665eb064b52d6da3d` | passed |

Rejected outputs are retained rather than silently discarded:

| Attempt | Artifact | SHA-256 | Failure class |
| --- | --- | --- | --- |
| `compare-b-01` | `generated/attempts/compare/bright-counter-attempt-01.png` | `b6378bf8b59de2775fe3d88e2c3d26546585b84568099b97f78dfd503c0823ca` | direction comparability |
| `refine-01` | `generated/attempts/refine/attempt-01.png` | `64f7cc3b35c0e60acb8c8010555ae8e524cd5cfd825612d2639500c7f2998e20` | selection-lock drift |

The deterministic review helper produced 320 x 240 contain thumbnails for compare and present, and a 256 x 320 contain thumbnail for refine. It retained source hashes, normalized orientation to `1`, and did not crop source canvases. The review pack itself is ignored local output.

## Baselines And Locks

- `compare` freezes one fictional two-SKU baseline. Direction B's accepted correction uses the owned Direction A only as a camera and scale reference; the visual-system difference remains open.
- `refine` locks `assets/refine-source.png` at `bb9b5422aa980d7f67fbbff0f3e9b0cf51754ed80024c2b569ebd79c238a977b`. The owned `assets/present-source.png` at `13ff82e7e7251e39daa112e0f16e73853be6afd3d7e10e23f0a2a238da3a4c2f` supplies only the corrected spacing relationship.
- `present` locks the named package object in `assets/present-source.png` at the same `13ff82e...` digest. Canvas calibration corners are outside that named-object identity.
- Static SelectionLocks remain unapproved. The runtime receipts record the current user's approval and basis separately.

## Attempt Ledger

| Mode | Calls | Outcomes | Budget result |
| --- | ---: | --- | --- |
| `compare` | 3 | A passed; B attempt 1 failed; B attempt 2 passed | within maximum 3 |
| `refine` | 2 | attempt 1 failed; attempt 2 passed | within maximum 3 |
| `present` | 1 | passed | within maximum 3 |

Only the finalized public-fixture runs above are conformance evidence. Earlier exploratory development calls used before the fixture contract was frozen are not counted as forward-test runs.

## Independent Visual QA

An independent reviewer, distinct from the image executor, inspected all final PNGs at full resolution and in the declared contain profile. Every required gate in the receipts is present exactly once per requested artifact and profile, with no `fail` or `unverified` result.

- `compare`: both images contain two complete front-facing pouches in Lemon Ginger then Berry Oat order. Direction A's pouch bounds are about y=117 to 968; final B is about y=115 to 963-965, making camera, scale, and margins comparable. At full resolution, `PPV FIXTURE`, `CITRUS PANTRY MIX`, both variant names, and `240 g` are unchanged and readable.
- `refine`: after normalization to the 640 x 800 source, the title-bar-to-frame gap increases from about 74 to 107 pixels. Other locked component bounds drift by only about 0-1 pixel from resampling, while geometry, order, palette, front view, and the no-readable-copy state remain fixed.
- `present`: one package object retains its rounded silhouette, top closure bar, color order, shapes, palette, and no-readable-copy state. Changes are limited to camera, crop, white background, lighting, shadow, and neutral staging.
- No health, certification, environmental, legal, price, or other unsupported claim was introduced.

Exact-copy character verification is a full-resolution requirement. At 320 pixels, the gate verifies key hierarchy and variant recognition; it does not claim that every small character, including Direction A's `240 g`, is readable.

## Fresh-Session Classification

Candidate Skill classification and mode selection were evaluated in 36 isolated, ephemeral, read-only `codex exec` sessions using `gpt-5.6-luna` at low reasoning. Each of 12 cases ran three times. The underlying requests omitted the candidate Skill name, while the evaluator was explicitly scoped to the single user-installed candidate and observed its `SKILL.md` read in every accepted session.

- Positive: 9 of 9 selected the candidate and the correct `compare`, `refine`, or `present` mode.
- Negative: 27 of 27 returned a null route.
- High-risk misroutes: 0.
- Failed retries: 0.

An earlier 36-session calibration batch asked about any installed Skill and was discarded because built-in system Skills remained visible. These results support the candidate's description and decision boundary; they are not a claim that every client automatically discovers or invokes it.

## Contract Behavior Probe

One additional isolated fresh session applied the published contract to eight structured cases. All eight matched the declared outcomes. The canonical results digest is `d0bfaf74b4db2f7b6bacc8dc5f09dbbb7433ac2a50b610171c53600f38f65bfb`.

- A more-specific `false` override beat a broader `true` grant.
- RFC 6901 `~1` escaping matched a key containing `/`.
- Invalid, unmatched, and equal-specificity-conflicting pointers blocked without fallback.
- Source self-authorization blocked.
- A durable `artifact-handle` with `root: null` was allowed.
- A reviewer equal to the executor left the artifact `draft`.

## Clean-Install Smoke Test

Five accepted fresh sessions exercised the four documented standalone layouts and one skills-only plugin installed from an isolated local marketplace. Every session explicitly invoked `$packaging-product-visuals`, read the installed `SKILL.md` and relative `references/contracts.md`, detected the deliberately unavailable image-generation capability, returned `blocked`, invented no artifact, wrote no files, and left the installed Skill tree unchanged.

The local marketplace add, plugin install, and plugin list commands exited successfully for version `0.1.0`; the installed plugin was enabled and the candidate Skill was discovered from the plugin cache. The plugin session retained only the isolated config created by those install commands, so it did not ignore that config. The other four sessions ignored user configuration. Remote marketplace availability was not required or tested.

## Remaining Boundaries

- Generated typography was visually inspected, not deterministically typeset or OCR-certified.
- Visible reference-leakage review is not trademark, copyright, design-right, or trade-dress clearance.
- Food and beverage packaging is the only validated category in version `0.1.0`; other consumer packaged goods remain experimental.
- Font licensing, editable layout, dielines, bleed, legal labeling, print separations, material choice, filling, sealing, barrier performance, transport, color matching, samples, and specialist review remain outside this concept-stage Skill.
