#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.15"
# dependencies = []
# ///
"""Bundle static packaging source assets without rendering or changing permissions.

JSON spec v1: id, package_geometry {form, dimensions, unit}, approved_copy,
palette, surfaces [{id, kind, artwork_asset_ids}], counted_objects [{id, label}],
and assets [{id, role, source, sha256}]. A font also requires license_asset_id and
usage_status. Sources are relative to the spec and keep their layout in files/.

Only static HTML, CSS and SVG resource references are supported. Scripts,
remote/data URLs, system-font sources, CSS escapes and dynamic resource syntax
are rejected. The tool checks listed bytes and references, not browser rendering,
legal permission, visual quality, manufacturing readiness or approval provenance.
"""

from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
import math
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import stat
import sys
import unicodedata
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET


SPEC_FIELDS = {
    "schema_version", "id", "package_geometry", "approved_copy", "palette",
    "surfaces", "counted_objects", "assets",
}
ASSET_FIELDS = {"id", "role", "source", "sha256"}
FONT_FIELDS = {"license_asset_id", "usage_status"}
FONT_EXTENSIONS = {".otf", ".ttf", ".woff", ".woff2"}
ROLES = {"artwork", "style", "font", "license", "preview", "image"}
VALIDATION = {
    "file_integrity": "checked",
    "reference_completeness": "checked",
    "visual_qa": "unverified",
    "production_readiness": "unverified",
    "legal_review": "not-performed",
    "publication_allowed": False,
}
CSS_URL = re.compile(r'''url\s*\(\s*(?:"([^"\n]*)"|'([^'\n]*)'|([^()'"\s]*))\s*\)''', re.I)
CSS_IMPORT = re.compile(r'''@import\s+(?:"([^"\n]+)"|'([^'\n]+)'|(?=url\s*\())''', re.I)
ACTIVE_SVG_TAGS = {"script", "foreignobject", "animate", "animatetransform", "animatemotion", "set"}
CSS_PRESENTATION_ATTRIBUTES = {
    "alignment-baseline", "baseline-shift", "clip", "clip-path", "clip-rule",
    "color", "color-interpolation", "color-interpolation-filters", "color-profile",
    "color-rendering", "cursor", "direction", "display", "dominant-baseline",
    "enable-background", "fill", "fill-opacity", "fill-rule", "filter", "flood-color",
    "flood-opacity", "font-family", "font-size", "font-size-adjust", "font-stretch",
    "font-style", "font-variant", "font-weight", "glyph-orientation-horizontal",
    "glyph-orientation-vertical", "image-rendering", "kerning", "letter-spacing",
    "lighting-color", "marker", "marker-end", "marker-mid", "marker-start", "mask",
    "opacity", "overflow", "paint-order", "pointer-events", "shape-rendering",
    "stop-color", "stop-opacity", "stroke", "stroke-dasharray", "stroke-dashoffset",
    "stroke-linecap", "stroke-linejoin", "stroke-miterlimit", "stroke-opacity",
    "stroke-width", "style", "text-anchor", "text-decoration", "text-rendering",
    "transform", "unicode-bidi", "vector-effect", "visibility", "word-spacing",
    "writing-mode",
}
HTML_VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
HTML_RAW_TEXT_TAGS = {"style", "script", "title", "textarea", "xmp", "plaintext", "iframe", "noframes", "noscript"}


class MasterError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise MasterError(message)


def exact_keys(value, expected, context):
    require(isinstance(value, dict), f"{context} must be an object")
    require(set(value) == expected, f"{context} has missing or unknown fields")


def nonempty(value, context):
    require(isinstance(value, str) and bool(value.strip()), f"{context} must be nonempty text")
    return value


def identifier(value, context):
    require(
        isinstance(value, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]{0,127}", value),
        f"{context} must be a lowercase alphanumeric/hyphen id",
    )
    return value


def unique_text_list(value, context, allow_empty=False):
    require(isinstance(value, list) and (allow_empty or bool(value)), f"{context} must be a list")
    for item in value:
        nonempty(item, context)
    require(len(value) == len(set(value)), f"{context} contains duplicates")
    return value


def relative_path(value):
    message = "asset source must be an unambiguous portable relative path"
    require(isinstance(value, str) and bool(value), message)
    require(unicodedata.normalize("NFC", value) == value, message)
    parts = value.split("/")
    require(not PurePosixPath(value).is_absolute(), message)
    for part in parts:
        require(part not in {"", ".", ".."}, message)
        require(not any(ord(c) < 32 or c in '\\:<>"|?*%#' for c in part), message)
        require(not part.endswith((".", " ")), message)
        require(not re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", part), message)
    return value


def check_path_collisions(paths):
    spellings = {}
    file_keys = {path.casefold() for path in paths}
    require(len(file_keys) == len(paths), "duplicate or ambiguous asset paths")
    for path in paths:
        parts = path.split("/")
        for count in range(1, len(parts) + 1):
            prefix = "/".join(parts[:count])
            key = prefix.casefold()
            require(key not in spellings or spellings[key] == prefix, "ambiguous asset directory spelling")
            spellings[key] = prefix
            require(count == len(parts) or key not in file_keys, "asset path is both a file and a directory")


def no_symlinks(path):
    absolute = Path(os.path.abspath(path))
    for item in (*reversed(absolute.parents), absolute):
        require(not item.is_symlink(), "symlink paths are not supported")
    return absolute


def read_regular(path):
    path = no_symlinks(path)
    require(stat.S_ISREG(path.stat().st_mode), "asset must be a regular file")
    return path.read_bytes()


def json_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def read_json(path):
    def invalid_constant(_):
        raise MasterError("JSON must not contain non-finite numbers")

    return json.loads(
        read_regular(path).decode("utf-8"),
        object_pairs_hook=json_object,
        parse_constant=invalid_constant,
    )


def canonical_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def strip_css_comments(text):
    parts = []
    index = 0
    quote = None
    while index < len(text):
        character = text[index]
        if quote:
            parts.append(character)
            if character == quote:
                quote = None
            index += 1
        elif text.startswith("/*", index):
            end = text.find("*/", index + 2)
            require(end != -1, "unterminated CSS comment")
            index = end + 2
        else:
            if character in {"'", '"'}:
                quote = character
            parts.append(character)
            index += 1
    require(quote is None, "unterminated CSS string")
    return "".join(parts)


def css_references(text):
    require("\\" not in text, "CSS escapes are unsupported; use plain static resource URLs")
    text = strip_css_comments(text)
    require(
        not re.search(r"(?:local|(?:-webkit-)?image-set|image|src|attr)\s*\(", text, re.I),
        "system-font or dynamic CSS resource syntax is unsupported",
    )
    matches = list(CSS_URL.finditer(text))
    require(len(matches) == len(re.findall(r"url\s*\(", text, re.I)), "unsupported dynamic or malformed CSS URL")
    font_faces = list(re.finditer(r"@font-face\s*\{[^{}]*\}", text, re.I))
    require(len(font_faces) == len(re.findall(r"@font-face\b", text, re.I)), "unsupported font-face block")
    imports = list(CSS_IMPORT.finditer(text))
    require(len(imports) == len(re.findall(r"@import\b", text, re.I)), "unsupported CSS import")
    references = [
        (next(group for group in match.groups() if group is not None),
         "font" if any(face.start() < match.start() < face.end() for face in font_faces)
         else "style" if any(item.end() == match.start() for item in imports) else None)
        for match in matches
    ]
    references.extend((group, "style") for match in imports for group in match.groups() if group is not None)
    return references


class StaticHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.references = []
        self.style_parts = []
        self.in_style = False
        self.svg_depth = 0

    def handle_startendtag(self, tag, attrs):
        # HTMLParser closes <style/>, but HTML browsers keep its CSS body open.
        require(
            tag in HTML_VOID_TAGS or (tag not in HTML_RAW_TEXT_TAGS and (tag == "svg" or self.svg_depth > 0)),
            "self-closing non-void HTML tags are unsupported",
        )
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_starttag(self, tag, attrs):
        require(tag not in ACTIVE_SVG_TAGS | {"base", "iframe", "object", "embed", "form", "applet"}, f"unsupported active HTML tag: {tag}")
        names = [key for key, _ in attrs]
        require(len(names) == len(set(names)), "duplicate HTML attributes")
        attributes = dict(attrs)
        if tag == "link":
            rel = (attributes.get("rel") or "").lower().split()
            link_as = (attributes.get("as") or "").strip().lower()
            require("modulepreload" not in rel and link_as != "script", "script-loading HTML link hints are unsupported")
        for key, value in attrs:
            require(not key.startswith("on"), "HTML event handlers are unsupported")
            require(key not in {"srcset", "imagesrcset", "srcdoc", "http-equiv", "xml:base", "ping", "manifest", "lowsrc", "dynsrc"}, f"unsupported HTML attribute: {key}")
            if value is None:
                continue
            if key in {"href", "src", "poster", "background", "xlink:href"}:
                required_role = None
                if tag == "link":
                    if "stylesheet" in rel or link_as == "style":
                        required_role = "style"
                    elif link_as == "font":
                        required_role = "font"
                self.references.append((value, required_role))
            elif key in CSS_PRESENTATION_ATTRIBUTES or re.search(r"url\s*\(", value, re.I):
                self.references.extend(css_references(value))
        if tag == "svg":
            self.svg_depth += 1
        if tag == "style":
            require(not self.in_style, "nested HTML style blocks are unsupported")
            self.in_style = True
            self.style_parts = []

    def handle_endtag(self, tag):
        if tag == "svg":
            self.svg_depth = max(0, self.svg_depth - 1)
        if tag == "style" and self.in_style:
            self.references.extend(css_references("".join(self.style_parts)))
            self.in_style = False

    def handle_data(self, data):
        if self.in_style:
            self.style_parts.append(data)


def static_references(source, data):
    extension = PurePosixPath(source).suffix.lower()
    if extension not in {".html", ".htm", ".css", ".svg"}:
        return []
    text = data.decode("utf-8-sig")
    if extension == ".css":
        return css_references(text)
    if extension in {".html", ".htm"}:
        parser = StaticHTML()
        parser.feed(text)
        parser.close()
        require(not parser.in_style, "unclosed HTML style block")
        return parser.references
    require(not re.search(r"<!DOCTYPE|<!ENTITY|<\?xml-stylesheet", text, re.I), "SVG external declarations are unsupported")
    root = ET.fromstring(text)
    require(root.tag.split("}")[-1] == "svg", "SVG asset must have an svg root")
    references = []
    for element in root.iter():
        tag = element.tag.split("}")[-1].lower()
        require(tag not in ACTIVE_SVG_TAGS, "active SVG content is unsupported")
        for key, value in element.attrib.items():
            local_key = key.split("}")[-1].lower()
            require(not local_key.startswith("on") and local_key != "base", "active SVG attribute is unsupported")
            if local_key == "href":
                references.append((value, None))
            elif local_key in CSS_PRESENTATION_ATTRIBUTES or re.search(r"url\s*\(", value, re.I):
                references.extend(css_references(value))
        if tag == "style":
            references.extend(css_references("".join(element.itertext())))
    return references


def dependency_path(source, reference):
    require(reference == reference.strip() and bool(reference), "empty or ambiguous resource URL")
    uri = urlsplit(reference)
    require(not uri.scheme and not uri.netloc, "remote or data resource URLs are unsupported")
    if not uri.path:
        require(bool(uri.fragment) and not uri.query, "empty resource URL is unsupported")
        return None
    path = unquote(uri.path, errors="strict")
    require(not path.startswith("/"), "resource URL must be relative")
    target = posixpath.normpath(posixpath.join(posixpath.dirname(source), path))
    return relative_path(target)


def build_manifest(spec, source_root):
    exact_keys(spec, SPEC_FIELDS, "spec")
    require(type(spec["schema_version"]) is int and spec["schema_version"] == 1, "unsupported schema_version")
    identifier(spec["id"], "master id")
    geometry = spec["package_geometry"]
    exact_keys(geometry, {"form", "dimensions", "unit"}, "package_geometry")
    nonempty(geometry["form"], "package form")
    require(geometry["unit"] in {"mm", "cm", "in"}, "package unit must be mm, cm or in")
    require(isinstance(geometry["dimensions"], dict) and bool(geometry["dimensions"]), "dimensions must be a nonempty object")
    for name, value in geometry["dimensions"].items():
        identifier(name, "dimension name")
        require(type(value) in {float, int} and (type(value) is int or math.isfinite(value)) and value > 0, "dimensions must be finite positive numbers")
    unique_text_list(spec["approved_copy"], "approved_copy")
    unique_text_list(spec["palette"], "palette")
    require(all(re.fullmatch(r"#[0-9a-fA-F]{6}", color) for color in spec["palette"]), "palette entries must be #RRGGBB")
    objects = spec["counted_objects"]
    require(isinstance(objects, list) and bool(objects), "counted_objects must list visible instances")
    for obj in objects:
        exact_keys(obj, {"id", "label"}, "counted object")
        identifier(obj["id"], "object id")
        nonempty(obj["label"], "object label")
    unique_text_list([obj["id"] for obj in objects], "counted object ids")

    assets = spec["assets"]
    require(isinstance(assets, list) and bool(assets), "assets must be a nonempty list")
    for asset in assets:
        require(isinstance(asset, dict), "asset must be an object")
        exact_keys(asset, ASSET_FIELDS | (FONT_FIELDS if asset.get("role") == "font" else set()), "asset")
        identifier(asset["id"], "asset id")
        require(isinstance(asset["role"], str) and asset["role"] in ROLES, "unsupported asset role")
        relative_path(asset["source"])
        require(isinstance(asset["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", asset["sha256"]), "asset sha256 must be 64 lowercase hex characters")
        extension = PurePosixPath(asset["source"]).suffix.lower()
        require(extension not in FONT_EXTENSIONS or asset["role"] == "font", "font files must use the font role with license metadata")
        if asset["role"] == "font":
            require(extension in FONT_EXTENSIONS, "font role requires an OTF, TTF, WOFF or WOFF2 file")
            identifier(asset["license_asset_id"], "license asset id")
            require(asset["usage_status"] in {"unreviewed", "user-confirmed", "restricted"}, "unsupported font usage_status")
        if asset["role"] == "artwork":
            require(extension in {".html", ".htm", ".svg"}, "artwork must be static HTML or SVG; other formats require manual dependency review")
        if asset["role"] == "style":
            require(extension == ".css", "style role must be CSS")
    unique_text_list([asset["id"] for asset in assets], "asset ids")
    check_path_collisions([asset["source"] for asset in assets])
    by_id = {asset["id"]: asset for asset in assets}
    by_source = {asset["source"]: asset for asset in assets}
    for asset in assets:
        if asset["role"] == "font":
            license_asset = by_id.get(asset["license_asset_id"])
            require(license_asset is not None and license_asset["role"] == "license", "font needs a separate listed license asset")

    surfaces = spec["surfaces"]
    require(isinstance(surfaces, list) and bool(surfaces), "surfaces must be a nonempty list")
    linked_artwork = set()
    for surface in surfaces:
        exact_keys(surface, {"id", "kind", "artwork_asset_ids"}, "surface")
        identifier(surface["id"], "surface id")
        require(surface["kind"] in {"planar", "curved", "flexible"}, "unsupported surface kind")
        unique_text_list(surface["artwork_asset_ids"], "surface artwork_asset_ids")
        for asset_id in surface["artwork_asset_ids"]:
            require(asset_id in by_id and by_id[asset_id]["role"] == "artwork", "surface references an unknown or non-artwork asset")
            linked_artwork.add(asset_id)
    unique_text_list([surface["id"] for surface in surfaces], "surface ids")
    require(linked_artwork == {asset["id"] for asset in assets if asset["role"] == "artwork"}, "every artwork asset must identify its intended surface")

    contents = {}
    records = []
    for asset in sorted(assets, key=lambda item: item["id"]):
        source = asset["source"]
        data = read_regular(source_root / source)
        require(sha256(data) == asset["sha256"], f"sha256 mismatch for asset {asset['id']}")
        require(bool(data), f"empty asset {asset['id']}")
        dependencies = set()
        for reference, required_role in static_references(source, data):
            target = dependency_path(source, reference)
            if target is not None:
                require(target in by_source, f"resource referenced by {asset['id']} is not listed in assets")
                if required_role is not None:
                    require(by_source[target]["role"] == required_role, f"resource referenced by {asset['id']} requires the {required_role} role")
                dependencies.add(by_source[target]["id"])
        record = {key: value for key, value in asset.items() if key != "source"}
        record.update(path="files/" + source, size_bytes=len(data), dependencies=sorted(dependencies))
        records.append(record)
        contents[record["path"]] = data
    manifest = {key: value for key, value in spec.items() if key not in {"assets", "surfaces"}}
    manifest.update(
        kind="packaging-product-visuals-package-master",
        assets=records,
        surfaces=[dict(surface, mapping_status="not-performed" if surface["kind"] == "planar" else "unverified-nonplanar") for surface in surfaces],
        visible_instance_count=len(objects),
        validation=dict(VALIDATION),
    )
    return manifest, contents


def check_master(directory):
    directory = no_symlinks(directory)
    require(directory.is_dir(), "master must be a directory")
    manifest = read_json(directory / "manifest.json")
    exact_keys(manifest, SPEC_FIELDS | {"kind", "visible_instance_count", "validation"}, "manifest")
    require(isinstance(manifest["assets"], list) and isinstance(manifest["surfaces"], list), "manifest assets and surfaces must be lists")
    spec = {key: manifest[key] for key in SPEC_FIELDS}
    spec["assets"] = []
    for asset in manifest["assets"]:
        require(isinstance(asset, dict), "manifest asset must be an object")
        exact_keys(asset, (ASSET_FIELDS - {"source"}) | {"path", "size_bytes", "dependencies"} | (FONT_FIELDS if asset.get("role") == "font" else set()), "manifest asset")
        relative_path(asset["path"])
        require(asset["path"].startswith("files/"), "manifest asset paths must start with files/")
        spec["assets"].append({**{key: value for key, value in asset.items() if key not in {"path", "size_bytes", "dependencies"}}, "source": asset["path"][6:]})
    spec["surfaces"] = []
    for surface in manifest["surfaces"]:
        exact_keys(surface, {"id", "kind", "artwork_asset_ids", "mapping_status"}, "manifest surface")
        spec["surfaces"].append({key: value for key, value in surface.items() if key != "mapping_status"})
    rebuilt, contents = build_manifest(spec, directory / "files")
    require(manifest == rebuilt, "manifest does not match checked content or invariant validation boundaries")
    require(read_regular(directory / "manifest.json") == canonical_bytes(rebuilt), "manifest is not canonical JSON")
    expected_files = set(contents) | {"manifest.json"}
    actual_files = set()
    for root, directories, files in os.walk(directory, followlinks=False):
        for name in directories + files:
            child = Path(root) / name
            require(not child.is_symlink(), "master contains a symlink")
            if name in files:
                require(stat.S_ISREG(child.stat().st_mode), "master contains a non-regular file")
                actual_files.add(child.relative_to(directory).as_posix())
    require(actual_files == expected_files, "master contains missing or unexpected files")
    return rebuilt


def create_master(spec_path, output):
    spec_path = no_symlinks(spec_path)
    try:
        output = no_symlinks(output)
    except MasterError as error:
        raise MasterError("output must not use symlinks") from error
    require(not output.exists(), "output already exists; choose a new directory")
    require(output.parent.is_dir(), "output parent must already be a directory")
    manifest, contents = build_manifest(read_json(spec_path), spec_path.parent)

    # Reserve the destination with exclusive mkdir. Write the manifest last so an
    # interrupted copy is not mistaken for a complete package; never replace a tree.
    output.mkdir()
    created_files = []
    created_directories = [output]
    try:
        for relative, data in [*contents.items(), ("manifest.json", canonical_bytes(manifest))]:
            target = output / relative
            for parent in reversed(target.parents):
                if parent == output or output in parent.parents:
                    if not parent.exists():
                        parent.mkdir()
                        created_directories.append(parent)
            with target.open("xb") as stream:
                created_files.append(target)
                stream.write(data)
        return check_master(output)
    except BaseException:
        # Remove only paths created here, never a recursive user-owned directory.
        for path in reversed(created_files):
            path.unlink(missing_ok=True)
        for path in reversed(created_directories):
            try:
                path.rmdir()
            except OSError:
                pass
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--spec", type=Path, help="JSON spec to bundle; sources are relative to this file.")
    mode.add_argument("--check", type=Path, help="Verify an existing package without changing it.")
    parser.add_argument("--output", type=Path, help="New output directory; existing paths are never replaced.")
    args = parser.parse_args(argv)
    if (args.spec is None) == (args.output is not None):
        parser.error("--spec requires --output; --check must not use --output")
    try:
        manifest = check_master(args.check) if args.check else create_master(args.spec, args.output)
        print(json.dumps({
            "status": "checked",
            "id": manifest["id"],
            "manifest_sha256": sha256(canonical_bytes(manifest)),
            "visible_instance_count": manifest["visible_instance_count"],
            "validation": manifest["validation"],
        }, sort_keys=True))
        return 0
    except (MasterError, OSError, UnicodeError, ValueError, TypeError, ET.ParseError) as error:
        detail = str(error) if isinstance(error, MasterError) else type(error).__name__
        print(f"error: {detail}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
