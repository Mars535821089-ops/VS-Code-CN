#!/usr/bin/env python3
"""Audit an installed VS Code build and generate a non-installing supplement."""

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[2]
CJK = re.compile(r"[\u3400-\u9fff]")
TOKENS = re.compile(
    r"\{\d+(?::[^{}]+)?\}|\$\{[^}]+\}|\$\([^)]+\)|`[^`]+`|"
    r"https?://[^\s)>\"]+|<[/!]?[A-Za-z][^>]*>|"
    r"\]\([^)]*\)|#[A-Za-z][\w.]*#|%(?:\d+\$)?[sdif]"
)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def signature(text):
    return Counter(TOKENS.findall(text)), text.count("\n"), text.count("&&")


def validate_translation(source, translation):
    if not isinstance(translation, str) or not translation.strip():
        raise ValueError("Translation must be a non-empty string")
    if signature(source) != signature(translation):
        raise ValueError(f"Translation changes formatting tokens: {source!r}")


def flatten(keys, messages):
    entries = []
    for module, module_keys in keys:
        if not isinstance(module, str) or not isinstance(module_keys, list):
            raise ValueError("Invalid nls.keys.json module")
        for key in module_keys:
            if not isinstance(key, str):
                raise ValueError(f"Invalid localization key: {module}/{key}")
            entries.append((module, key))
    if len(entries) != len(messages) or any(not isinstance(x, str) for x in messages):
        raise ValueError("NLS keys/messages length or type mismatch")
    result = []
    seen = {}
    for (module, key), message in zip(entries, messages):
        if (module, key) in seen and seen[module, key] != message:
            raise ValueError(f"Conflicting source strings for {module}/{key}")
        seen[module, key] = message
        result.append((module, key, message))
    return result


def audit(entries, official, dictionary):
    runtime_occurrences = len(entries)
    entries = list(dict.fromkeys(entries))
    contents = official["contents"]
    if not isinstance(contents, dict) or any(
        not isinstance(values, dict)
        or any(not isinstance(value, str) for value in values.values())
        for values in contents.values()
    ):
        raise ValueError("Official contents must map modules and keys to strings")
    if set(dictionary) != {"entries", "keep"}:
        raise ValueError("Dictionary must contain entries and keep")
    reviewed = {}
    for item in dictionary["entries"]:
        if set(item) != {"source", "translation"}:
            raise ValueError("Dictionary entries require source and translation")
        source = item["source"]
        if not isinstance(source, str) or not source or source in reviewed:
            raise ValueError(f"Invalid or duplicate dictionary source: {source!r}")
        validate_translation(source, item["translation"])
        reviewed[source] = item["translation"]
    keep = dictionary["keep"]
    if not isinstance(keep, list) or any(not isinstance(x, str) for x in keep):
        raise ValueError("keep must be a list of exact source strings")
    if len(set(keep)) != len(keep) or set(keep) & reviewed.keys():
        raise ValueError("Duplicate or translated keep entry")
    keep = set(keep)

    # Reuse only the same semantic key AND exact current English source.
    # Different Chinese values for that pair make reuse ambiguous and disallowed.
    donors = defaultdict(list)
    for module, key, source in entries:
        value = contents.get(module, {}).get(key)
        if value and CJK.search(value) and signature(source) == signature(value):
            donors[(key, source)].append((module, value))

    merged = deepcopy(official)
    delta = {"version": official.get("version", ""), "contents": {}}
    pending, applied, kept = [], [], []
    counts = Counter()
    for module, key, source in entries:
        values = contents.get(module, {})
        value = values.get(key)
        if module not in contents:
            reason = "missing_module"
        elif key not in values:
            reason = "missing_key"
        elif not value.strip():
            reason = "empty_value"
        elif value == source and re.search(r"[A-Za-z]", source) and not CJK.search(source):
            reason = "official_unchanged"
        else:
            continue
        counts[reason] += 1
        item = {"module": module, "key": key, "source": source, "reason": reason}
        if source in keep or not re.search(r"[A-Za-z\u3400-\u9fff]", TOKENS.sub("", source)):
            kept.append(item)
            continue
        # Preserve every existing non-empty official value, including English.
        if reason == "official_unchanged":
            pending.append(item)
            continue
        translation = reviewed.get(source)
        provenance = {"kind": "reviewed"}
        if translation is None:
            matches = donors[(key, source)]
            unique = {text for _, text in matches}
            if len(unique) == 1:
                translation = next(iter(unique))
                provenance = {"kind": "official_same_key_source", "modules": sorted(m for m, _ in matches)}
        if translation is None:
            pending.append(item)
            continue
        validate_translation(source, translation)
        delta["contents"].setdefault(module, {})[key] = translation
        merged["contents"].setdefault(module, {})[key] = translation
        applied.append({**item, "translation": translation, "provenance": provenance})
    summary = {
        "runtime_occurrences": runtime_occurrences,
        "unique_build_keys": len(entries),
        "candidates": dict(sorted(counts.items())),
        "applied": len(applied),
        "applied_by_provenance": dict(sorted(Counter(x["provenance"]["kind"] for x in applied).items())),
        "kept_nontranslatable": len(kept),
        "pending": len(pending),
        "pending_by_reason": dict(sorted(Counter(x["reason"] for x in pending).items())),
        "installed": False,
    }
    return delta, merged, {"summary": summary, "applied": applied, "kept": kept, "pending": pending}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, required=True, help="VS Code Contents/Resources/app directory")
    parser.add_argument("--official", type=Path, default=ROOT / "i18n/vscode-language-pack-zh-hans/translations/main.i18n.json")
    parser.add_argument("--dictionary", type=Path, default=Path(__file__).with_name("reviewed-zh-cn.json"))
    parser.add_argument("--output", type=Path, required=True, help="New directory for generated resources and audit")
    args = parser.parse_args()
    try:
        keys_path = args.app / "out/nls.keys.json"
        messages_path = args.app / "out/nls.messages.json"
        package = read_json(args.app / "package.json")
        product = read_json(args.app / "product.json")
        entries = flatten(read_json(keys_path), read_json(messages_path))
        delta, merged, report = audit(entries, read_json(args.official), read_json(args.dictionary))
        report["build"] = {"version": package["version"], "commit": product["commit"]}
        report["inputs_sha256"] = {
            "keys": sha256(keys_path), "messages": sha256(messages_path),
            "official": sha256(args.official), "dictionary": sha256(args.dictionary),
        }
        # Never overwrite existing output, installed extensions, or application files.
        output = args.output.resolve()
        for protected in [args.app.resolve(), args.official.resolve().parent]:
            if output == protected or protected in output.parents:
                raise ValueError(f"Output must not be inside protected resources: {protected}")
        args.output.mkdir(parents=True, exist_ok=False)
        for name, value in [("delta.json", delta), ("merged-main.i18n.json", merged), ("audit.json", report)]:
            (args.output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"build": report["build"], **report["summary"]}, ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Incremental localization failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
