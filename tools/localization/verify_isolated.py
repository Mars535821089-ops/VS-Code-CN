#!/usr/bin/env python3
"""Verify local resources with isolated extension registration and the installed NLS resolver."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

from build_incremental import read_json


IDENTITIES = {"base": "local-vscode-cn-audit.official-baseline-fixture",
              "merged": "local-vscode-cn-audit.incremental-fixture"}


def snapshot(app, official):
    protected = [app / "out/cli.js", app / "out/nls.keys.json", app / "out/nls.messages.json",
                 app / "product.json", official / "package.json",
                 Path.home() / ".vscode/extensions/extensions.json",
                 Path.home() / "Library/Application Support/Code/languagepacks.json",
                 Path.home() / "Library/Application Support/Code/User/locale.json"]
    protected.extend(official.glob("translations/**/*.json"))
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
            for p in protected}


def fixture(path, kind, core, official):
    """Create an unsigned, local-only VSIX under a clearly independent identity."""
    manifest = read_json(official / "package.json")
    translations = manifest["contributes"]["localizations"][0]["translations"]
    publisher, name = IDENTITIES[kind].split(".")
    package = {
        "name": name, "publisher": publisher, "version": "0.0.1",
        "displayName": f"LOCAL AUDIT ONLY - {kind} Chinese fixture",
        "description": "Independent temporary verification fixture. Not a Microsoft product.",
        "engines": {"vscode": "^1.144.0"}, "categories": ["Language Packs"],
        "contributes": {"localizations": [{
            "languageId": "zh-cn", "languageName": "Chinese Simplified",
            "localizedLanguageName": "中文（本地测试）",
            "translations": [{"id": t["id"], "path": t["path"]} for t in translations]
            if kind == "base" else [{"id": "vscode", "path": "./translations/main.i18n.json"}],
        }]},
    }
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011">
<Metadata><Identity Language="en-US" Id="{name}" Version="0.0.1" Publisher="{publisher}"/>
<DisplayName>Independent local audit fixture</DisplayName>
<Description xml:space="preserve">Not Microsoft. Temporary verification only.</Description></Metadata>
<Installation><InstallationTarget Id="Microsoft.VisualStudio.Code"/></Installation>
<Dependencies/><Assets><Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true"/></Assets>
</PackageManifest>"""
    content_types = """<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="json" ContentType="application/json"/>
<Default Extension="vsixmanifest" ContentType="text/xml"/></Types>"""
    with zipfile.ZipFile(path, "x", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("extension/package.json", json.dumps(package, ensure_ascii=False))
        archive.writestr("extension.vsixmanifest", xml)
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("extension/translations/main.i18n.json", core.read_bytes())
        if kind == "base":
            for entry in translations:
                if entry["id"] == "vscode":
                    continue
                resource = (official / entry["path"]).resolve()
                if official.resolve() not in resource.parents:
                    raise ValueError(f"Translation outside official extension: {resource}")
                archive.writestr("extension/" + entry["path"].removeprefix("./"), resource.read_bytes())


def run(command, environment, log):
    result = subprocess.run(command, env=environment, text=True, capture_output=True, timeout=120)
    log.write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        raise ValueError(f"Command failed ({result.returncode}): {command!r}\n{result.stdout}{result.stderr}")
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--official-extension", type=Path, required=True)
    parser.add_argument("--generated", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New directory for report and logs")
    args = parser.parse_args()
    try:
        app = args.app.resolve()
        official = args.official_extension.resolve()
        generated = args.generated.resolve()
        output = args.output.resolve()
        for protected in [app, official, generated, Path.home() / ".vscode",
                          Path.home() / "Library/Application Support/Code"]:
            if output == protected or protected in output.parents:
                raise ValueError(f"Output cannot be inside protected resources: {protected}")
        report = read_json(generated / "audit.json")
        if report["build"] != {"version": read_json(app / "package.json")["version"],
                              "commit": read_json(app / "product.json")["commit"]}:
            raise ValueError("Audit and installed build mismatch")
        if hashlib.sha256((official / "translations/main.i18n.json").read_bytes()).hexdigest() != report["inputs_sha256"]["official"]:
            raise ValueError("Official extension and audit baseline mismatch")
        for name, metadata in [("keys", "nls.keys.json"), ("messages", "nls.messages.json")]:
            if hashlib.sha256((app / "out" / metadata).read_bytes()).hexdigest() != report["inputs_sha256"][name]:
                raise ValueError(f"Audit runtime input hash mismatch: {metadata}")
        baseline = read_json(official / "translations/main.i18n.json")["contents"]
        merged = read_json(generated / "merged-main.i18n.json")["contents"]
        for module, values in baseline.items():
            for key, value in values.items():
                if value.strip() and merged.get(module, {}).get(key) != value:
                    raise ValueError(f"Merged resource replaced official value: {module}/{key}")
        output.mkdir(parents=True, exist_ok=False)
        env = os.environ.copy()
        for key in list(env):
            if key.startswith(("VSCODE_", "ELECTRON_")) or key in {"NODE_OPTIONS", "NODE_REPL_EXTERNAL_MODULE"}:
                del env[key]
        results = []
        before = snapshot(app, official)
        # All generated VSIX files and installed fixtures are deleted after the test.
        with tempfile.TemporaryDirectory(prefix="vscode-cn-isolated-") as directory:
            root = Path(directory)
            for kind, core in [
                ("base", official / "translations/main.i18n.json"),
                ("merged", generated / "merged-main.i18n.json"),
            ]:
                fixture(root / f"{kind}.vsix", kind, core, official)
            for label, order in [("base-then-merged", ["base", "merged"]),
                                 ("merged-then-base", ["merged", "base"])]:
                user_data, extensions = root / label / "user-data", root / label / "extensions"
                for index, kind in enumerate(order):
                    run([str(app / "bin/code"), "--user-data-dir", str(user_data),
                         "--extensions-dir", str(extensions), "--install-extension",
                         str(root / f"{kind}.vsix"), "--force", "--do-not-sync"],
                        env, output / f"{label}-{index}.log")
                # The CLI accepted both manifests, but it does not necessarily
                # instantiate the cache service. Explicitly exercise that service.
                runner = Path(__file__).with_name("verify_runtime.cjs")
                raw = run(["node", str(runner), str(app), str(user_data), str(generated), str(extensions)],
                          env, output / f"{label}-runtime.log")
                runtime = json.loads(raw)
                registry = read_json(user_data / "languagepacks.json")
                pack = registry["zh-cn"]
                actual_ids = {item["extensionIdentifier"]["id"] for item in pack["extensions"]}
                if actual_ids != set(IDENTITIES.values()):
                    raise ValueError(f"Unexpected installed extensions: {actual_ids}")
                selected = Path(pack["translations"]["vscode"])
                if extensions.resolve() not in selected.resolve().parents:
                    raise ValueError("Core resource was not selected from isolated extensions")
                if len(pack["translations"]) != len(read_json(official / "package.json")["contributes"]["localizations"][0]["translations"]):
                    raise ValueError("Baseline extension resource IDs were lost")
                for resource in pack["translations"].values():
                    if extensions.resolve() not in Path(resource).resolve().parents:
                        raise ValueError("Registered resource is outside isolated extensions")
                    read_json(Path(resource))
                # The same installed resolver compiles the chosen resource and checks
                # every runtime occurrence, all additions and English fallback.
                selected_kind = next(kind for kind, identity in IDENTITIES.items()
                                     if identity.split(".")[1] in selected.parts[-3])
                if selected_kind == "merged" and runtime["applied_loaded"] != report["summary"]["applied"]:
                    raise ValueError("Merged fixture did not load every supplemental translation")
                results.append({"installation_order": order, "selected": selected_kind,
                                "registered_extension_ids": sorted(actual_ids),
                                "translation_resource_ids": len(pack["translations"]),
                                "runtime": runtime})
        if {item["selected"] for item in results} != {"base", "merged"}:
            raise ValueError("Could not demonstrate both same-locale selection outcomes")
        if snapshot(app, official) != before:
            raise ValueError("Protected application, official translation or current-user registration changed")
        summary = {
            "build": report["build"], "cases": results,
            "same_locale_rule": "Last scanned translation resource ID wins; not a per-key merge.",
            "installed_for_current_user": False, "gui_verified": False,
            "temporary_extensions_removed": True,
            "protected_file_hashes_unchanged": len(before),
            "runtime_validation": "Installed cache registration methods and NLS resolver, executed unmodified with explicit dependencies.",
        }
        (output / "verification.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        print(f"Isolated verification failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
