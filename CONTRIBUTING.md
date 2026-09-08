# Contributing

Thank you for improving Packaging Product Visuals. Keep contributions small, inspectable, and compatible with the public contract.

## Before opening a change

- Read `SKILL.md` and the relevant reference contract.
- Keep examples fictional, low-risk, and redistributable.
- Do not commit customer material, private project documents, private prompts, credentials, source EXIF, unlicensed reference images, or generated outputs derived from private inputs.
- Do not add a marketplace repository, telemetry, hosted documentation site, automatic upload, or paid provider integration without a separately approved scope.

## Tests

Use Python `>=3.10,<3.15` and the development dependencies from `pyproject.toml`:

```bash
uv sync --extra dev
uv run python -m pytest -v
```

The Python environment is for repository tests and the deterministic review helper; it is not the Skill installation mechanism.

The release matrix is Ubuntu 3.10/3.14, macOS 3.14, and Windows 3.14. Do not compare encoded PNG/JPEG bytes across operating systems. Prefer dimensions, mode, orientation, preserved semantic markers, decoded hashes where pinned, canonical text, path ordering, and exit codes.

When available, run the official local validators as supplemental checks:

```bash
skills-ref validate skills/packaging-product-visuals
python quick_validate.py skills/packaging-product-visuals
```

The repository does not depend on one absolute validator path. A missing local validator is a capability gap to report, not a reason to copy a replacement into the repository.

## Fixtures and assets

Every public image needs an entry in `examples/fictional-pantry-product/asset-provenance.yaml` and `ASSET_LICENSES.md`. Record how it was created, its source material, redistribution terms, visible trademarks, private-data check, dimensions, mode, and a source hash. Programmatic fixtures must remain fictional and deterministic. Reference manifests must name permitted and prohibited elements.

Forward tests must preserve the same product facts, package structure, exact copy, and SKU order when comparing directions. A refine fixture must name one correction class and a selection lock. A present fixture must identify the approved package identity and permitted staging changes.

## Documentation and release language

Do not call a concept result production-ready. Do not claim guaranteed exact generated text, universal client compatibility, marketplace availability, consumer preference, regulatory approval, food safety, or manufacturing validation. State the tested client, provider, model, operating system, version, and date when making a stability claim; all other runtimes remain `unverified`.

Keep `README.md`, `README.zh-CN.md`, `CHANGELOG.md`, `SKILL.md`, plugin metadata, and license declarations aligned. Run `git diff --check` and the full pytest command before requesting review.

## Pull requests

Describe the requested behavior, frozen fields, permissions, fixture provenance, tests run, validator availability, and any remaining production checks. Avoid bundling unrelated formatting or generated files. Public publication, release tags, marketplace submissions, and external pushes require explicit approval.
