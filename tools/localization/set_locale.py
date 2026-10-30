#!/usr/bin/env python3
"""Change only VS Code's startup locale, preserving comments and unrelated settings."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile


TOKEN = re.compile(r'\s+|//[^\r\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|[{}\[\]:,]|[^{}\[\]:,\s]+')
LOCALE = "zh-cn-mars"


def parse(text):
    tokens = [(match.group(), match.start(), match.end()) for match in TOKEN.finditer(text)
              if not match.group().isspace() and not match.group().startswith(("//", "/*"))]
    normalized = "".join(token for index, (token, _, _) in enumerate(tokens)
                         if not (token == "," and index + 1 < len(tokens)
                                 and tokens[index + 1][0] in {"}", "]"}))
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate startup setting: {key}")
            result[key] = value
        return result
    data = json.loads(normalized, object_pairs_hook=unique)
    if not isinstance(data, dict):
        raise ValueError("argv.json must contain an object")
    if not tokens or tokens[0][0] != "{" or tokens[-1][0] != "}":
        raise ValueError("Invalid argv.json token structure")
    return data, tokens


def patch(text, present, value):
    data, tokens = parse(text)
    if present and not isinstance(value, str):
        raise ValueError("Locale must be a string")
    depth = 0
    for index, (token, start, end) in enumerate(tokens):
        if token in {"{", "["}:
            depth += 1
        elif token in {"}", "]"}:
            depth -= 1
        elif (depth == 1 and token.startswith('"') and json.loads(token) == "locale"
              and index + 1 < len(tokens) and tokens[index + 1][0] == ":"):
            if tokens[index + 1][0] != ":" or not tokens[index + 2][0].startswith('"'):
                raise ValueError("Existing locale must be a string")
            value_token = tokens[index + 2]
            if present:
                result = text[:value_token[1]] + json.dumps(value) + text[value_token[2]:]
            else:
                after = tokens[index + 3]
                if after[0] == ",":
                    result = text[:start] + text[after[2]:]
                else:
                    before = tokens[index - 1]
                    cut = before[1] if before[0] == "," else start
                    result = text[:cut] + text[value_token[2]:]
            break
    else:
        if not present:
            return text
        insertion = tokens[0][2]
        result = text[:insertion] + '\n\t"locale": ' + json.dumps(value) + ("," if data else "") + text[insertion:]
    expected = dict(data)
    if present:
        expected["locale"] = value
    else:
        expected.pop("locale", None)
    if parse(result)[0] != expected:
        raise ValueError("Locale edit changed unrelated configuration")
    return result


def atomic_write(path, text, original):
    if path.read_text() != original:
        raise ValueError("Configuration changed concurrently; refusing overwrite")
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(text)
    try:
        temporary.chmod(path.stat().st_mode & 0o777)
        if path.read_text() != original:
            raise ValueError("Configuration changed concurrently; refusing overwrite")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["activate", "restore"])
    parser.add_argument("--argv", type=Path, default=Path.home() / ".vscode/argv.json")
    parser.add_argument("--backup", type=Path, required=True, help="Locale-only backup, never the full argv file")
    args = parser.parse_args()
    try:
        text = args.argv.read_text()
        data, _ = parse(text)
        if args.action == "activate":
            if data.get("locale") == LOCALE:
                raise ValueError("Custom locale already active; keep the original backup")
            backup = {"path": str(args.argv.resolve()), "present": "locale" in data,
                      "value": data.get("locale"), "activated": LOCALE}
            result = patch(text, True, LOCALE)
            with args.backup.open("x", encoding="utf-8") as file:
                json.dump(backup, file, indent=2)
                file.write("\n")
        else:
            backup = json.loads(args.backup.read_text())
            if backup["path"] != str(args.argv.resolve()) or backup["activated"] != LOCALE:
                raise ValueError("Backup is for a different configuration")
            if data.get("locale") != LOCALE:
                raise ValueError("Locale changed since activation; refusing to overwrite user's choice")
            result = patch(text, backup["present"], backup["value"])
        atomic_write(args.argv, result, text)
        print(json.dumps({"action": args.action, "locale": parse(result)[0].get("locale"),
                          "backup": str(args.backup), "restart_performed": False,
                          "argv_sha256": hashlib.sha256(args.argv.read_bytes()).hexdigest()}))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Locale configuration failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
