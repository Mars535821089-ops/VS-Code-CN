import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


SPEC = importlib.util.spec_from_file_location("custom_pack", Path(__file__).with_name("custom_pack.py"))
PACK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACK)


class CustomPackTests(unittest.TestCase):
    def test_build_reproducibility_identity_complete_resources_and_official_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app, official, generated = root / "app", root / "official", root / "generated"
            for path in [app / "out", official / "translations/extensions", generated]:
                path.mkdir(parents=True)
            files = {
                app / "product.json": {"commit": "fixture"},
                app / "package.json": {"version": "1.144.0"},
                app / "out/nls.keys.json": [["m", ["old", "new"]]],
                app / "out/nls.messages.json": ["Old", "New"],
                official / "package.json": {"contributes": {"localizations": [{"translations": [
                    {"id": "vscode", "path": "./translations/main.i18n.json"},
                    {"id": "vscode.test", "path": "./translations/extensions/test.json"},
                ]}]}},
                official / "translations/main.i18n.json": {"contents": {"m": {"old": "旧"}}},
                official / "translations/extensions/test.json": {"contents": {}},
                generated / "merged-main.i18n.json": {"contents": {"m": {"old": "旧", "new": "新"}}},
            }
            for path, data in files.items():
                path.write_text(json.dumps(data))
            import hashlib
            audit = {
                "build": {"version": "1.144.0", "commit": "fixture"},
                "inputs_sha256": {label: hashlib.sha256(path.read_bytes()).hexdigest() for label, path in [
                    ("keys", app / "out/nls.keys.json"), ("messages", app / "out/nls.messages.json"),
                    ("official", official / "translations/main.i18n.json")]},
                "applied": [{"module": "m", "key": "new", "translation": "新"}],
                "summary": {"applied": 1},
            }
            (generated / "audit.json").write_text(json.dumps(audit))
            first = PACK.build(app, official, generated, root / "first")
            second = PACK.build(app, official, generated, root / "second")
            self.assertEqual(first["vsix_sha256"], second["vsix_sha256"])
            with zipfile.ZipFile(first["vsix"]) as archive:
                manifest = json.loads(archive.read("extension/package.json"))
                self.assertEqual(manifest["publisher"], "mars-localization")
                self.assertEqual(manifest["engines"]["vscode"], "1.144.0")
                self.assertEqual(manifest["contributes"]["localizations"][0]["languageId"], "zh-cn-mars")
                self.assertEqual(len(manifest["contributes"]["localizations"][0]["translations"]), 2)
                self.assertIn("extension/LICENSE.md", archive.namelist())
                self.assertIn("extension/translations/extensions/test.json", archive.namelist())
            (generated / "merged-main.i18n.json").write_text('{"contents":{"m":{"old":"changed"}}}')
            with self.assertRaises(ValueError):
                PACK.build(app, official, generated, root / "invalid")


if __name__ == "__main__":
    unittest.main()
