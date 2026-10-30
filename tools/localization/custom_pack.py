#!/usr/bin/env python3
"""Generate an independent full language pack with a non-conflicting locale."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

from build_incremental import read_json
from verify_isolated import fixture, IDENTITIES


LOCALE = "zh-cn-mars"
PUBLISHER = "mars-localization"
NAME = "vscode-language-pack-zh-cn-mars"
IDENTITY = f"{PUBLISHER}.{NAME}"


def build(app, official, generated, output):
    product = read_json(app / "product.json")
    audit = read_json(generated / "audit.json")
    if audit["build"] != {"version": read_json(app / "package.json")["version"],
                          "commit": product["commit"]}:
        raise ValueError("Audit and installed VS Code build do not match")
    for label, file in [("keys", app / "out/nls.keys.json"),
                        ("messages", app / "out/nls.messages.json"),
                        ("official", official / "translations/main.i18n.json")]:
        if hashlib.sha256(file.read_bytes()).hexdigest() != audit["inputs_sha256"][label]:
            raise ValueError(f"Audit input hash mismatch: {label}")
    base = read_json(official / "translations/main.i18n.json")
    merged = read_json(generated / "merged-main.i18n.json")
    expected = json.loads(json.dumps(base))
    for item in audit["applied"]:
        values = expected["contents"].setdefault(item["module"], {})
        if values.get(item["key"], "").strip():
            raise ValueError("Incremental translation would replace an official value")
        values[item["key"]] = item["translation"]
    if merged != expected:
        raise ValueError("Merged resource differs from official baseline plus audited additions")
    output.mkdir(parents=True, exist_ok=False)
    # Reuse the local VSIX container construction, then replace only our fixture
    # manifest/identity and full core resource; official source files remain read-only.
    temporary = output / "baseline-fixture.vsix"
    fixture(temporary, "base", official / "translations/main.i18n.json", official)
    with zipfile.ZipFile(temporary) as source:
        package = json.loads(source.read("extension/package.json"))
        package.update({
            "publisher": PUBLISHER, "name": NAME, "version": "0.1.0",
            "displayName": "Chinese Simplified - Mars reviewed supplement",
            "description": "Independent Chinese supplement. Not published or supported by Microsoft.",
            "license": "MIT",
            "engines": {"vscode": audit["build"]["version"]},
        })
        localization = package["contributes"]["localizations"][0]
        localization.update({"languageId": LOCALE, "languageName": "Chinese Simplified (Mars)",
                             "localizedLanguageName": "简体中文（Mars 增量）"})
        manifest = source.read("extension.vsixmanifest").decode()
        manifest = manifest.replace(IDENTITIES["base"].split(".")[0], PUBLISHER)
        manifest = manifest.replace(IDENTITIES["base"].split(".")[1], NAME).replace('Version="0.0.1"', 'Version="0.1.0"')
        target = output / f"{IDENTITY}-0.1.0.vsix"
        with zipfile.ZipFile(target, "x", zipfile.ZIP_DEFLATED) as archive:
            def write(name, data):
                entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(entry, data)
            for name in source.namelist():
                if name in {"extension/package.json", "extension.vsixmanifest",
                            "extension/translations/main.i18n.json"}:
                    continue
                write(name, source.read(name))
            write("extension/package.json", json.dumps(package, ensure_ascii=False, indent=2))
            write("extension.vsixmanifest", manifest)
            write("extension/translations/main.i18n.json", json.dumps(merged, ensure_ascii=False, indent=2))
            write("extension/LICENSE.md", (Path(__file__).resolve().parents[2] / "LICENSE.md").read_bytes())
    temporary.unlink()
    result = {
        "extension": IDENTITY, "locale": LOCALE, "version": "0.1.0",
        "build": audit["build"], "additions": audit["summary"]["applied"],
        "translation_resources": len(localization["translations"]),
        "vsix": str(target), "vsix_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "installed": False,
    }
    (output / "package-report.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ["app", "official-extension", "generated", "output"]:
        parser.add_argument(f"--{argument}", type=Path, required=True)
    args = parser.parse_args()
    try:
        output = args.output.resolve()
        protected = [args.app.resolve(), args.official_extension.resolve(), args.generated.resolve(),
                     Path.home() / ".vscode", Path.home() / "Library/Application Support/Code"]
        if any(output == p or p in output.parents for p in protected):
            raise ValueError("Package output must not be within application or extension resources")
        print(json.dumps(build(args.app, args.official_extension, args.generated, output), indent=2))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Custom language pack generation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
