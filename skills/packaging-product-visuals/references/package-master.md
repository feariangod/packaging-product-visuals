# Editable Package Master

Use this after a packaging direction is selected and whenever later images need the same package design. Keep the approved editable artwork, actual fonts and license evidence, copy, palette, package proportions, and source previews together. Reuse those sources across the ecommerce set instead of reconstructing the package from a prompt or a screenshot.

## What Belongs Together

- The editable design source and its explicit dependencies. Static HTML/CSS/SVG is one option; a permitted native design file is also valid.
- Exact brand, product, variant, and quantity strings. Keep bilingual words separate from flexible layout separators.
- Geometry and the surface each artwork applies to. Distinguish a flat carton face, a curved label, and a flexible pouch.
- Actual font files when their local use permits inclusion, with source/license evidence and substitution status. Do not call a font verified because its filename or CSS family matches.
- A preview plus the selected design and typography references. The preview helps inspection; it is not the editable source.

Keep scene lighting, camera, props, and visible-instance counts in the image brief. A source-package inventory is not automatically the object count for every scene.

## Local Bundle Helper

`scripts/prepare_package_master.py` packages declared local assets without executing, rendering, editing, or uploading them. It uses the Python standard library:

```bash
python3 scripts/prepare_package_master.py --spec master-spec.json --output package-master
python3 scripts/prepare_package_master.py --check package-master
```

Paths above are relative to the Skill directory. The spec is JSON with `schema_version: 1`, an `id`, `package_geometry` (`form`, `dimensions`, `unit`), `approved_copy` strings, `palette` colors, `surfaces`, `counted_objects`, and `assets`. Each surface names its `id`, `kind` (`planar`, `curved`, or `flexible`), and `artwork_asset_ids`. Each counted object names one visible instance with an `id` and `label`; the helper derives the total.

Each asset has an `id`, `role` (`artwork`, `style`, `font`, `license`, `preview`, or `image`), `source` relative to the spec directory, and its actual file `sha256`. Font assets also identify a separate `license_asset_id` and a `usage_status` (`unreviewed`, `user-confirmed`, or `restricted`). Those are recorded states, not a legal conclusion. Never invent a font file or license to satisfy the format.

The helper preserves relative resource paths in the bundle. It rejects missing or undeclared dependencies, unsafe paths, unsupported dynamic references, and existing output directories. It does not run JavaScript or fetch remote resources. If the chosen source format cannot be safely packaged, keep the original source and its dependency inventory; do not strip its functionality merely to pass the helper.

Use lowercase letters, numbers, and hyphens for IDs, positive dimensions, and units `mm`, `cm`, or `in`. Supported artwork is static `.html`, `.htm`, or `.svg`; styles use `.css`, and fonts use `.otf`, `.ttf`, `.woff`, or `.woff2`. Create the output's parent directory first. The helper rejects scripts, data URLs, `srcset`, CSS escapes, and `local()` fonts rather than guessing their dependencies. Font binary validity and actual rendering are outside this file-bundling check.

Retain the manifest file hash in the run's source bindings. Before reuse, run the bundle check and compare that hash with the recorded one. A changed approved source requires a new version; keep previous source files and receipts unchanged.

## Apply And Inspect

Choose the image-production method before generation. A real-font artwork can control exact lettering while the image tool supplies the package, material, scene, and lighting. Explicitly assign source roles when an older photograph supplies geometry but newer artwork supplies graphics. Do not let obsolete lettering, color blocks, or sleeve boundaries reappear.

Use a plane-based mapping only on a verified planar surface. Curved bottles and flexible pouches need their own wrapping/deformation method and visual inspection. A successful planar case is not proof that those other surfaces work. The bundle helper does not perform any mapping.

Inspect the result at full resolution and the channel's review size: proportions, sleeve/label transitions, type fit, exact copy, perspective, lighting, occlusion, and edge artifacts. Recheck the complete requested set for package consistency.

A bundle check proves file integrity and explicit static dependencies. Visual QA, font rendering, permission to publish, and production readiness remain separate. Source masters and font files are local by default; include them in an open-source example only with the required redistribution rights and publication authorization.
