import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


SPEC = importlib.util.spec_from_file_location("isolated", Path(__file__).with_name("verify_isolated.py"))
ISOLATED = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ISOLATED)


class FixtureTests(unittest.TestCase):
    def test_independent_unsigned_fixture_and_baseline_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            official = root / "official"
            (official / "translations/extensions").mkdir(parents=True)
            translations = [
                {"id": "vscode", "path": "./translations/main.i18n.json"},
                {"id": "vscode.test", "path": "./translations/extensions/test.json"},
            ]
            (official / "package.json").write_text(json.dumps({
                "contributes": {"localizations": [{"translations": translations}]}}))
            core = official / "translations/main.i18n.json"
            core.write_text('{"contents": {}}')
            (official / "translations/extensions/test.json").write_text('{"contents": {}}')
            for kind in ["base", "merged"]:
                target = root / f"{kind}.vsix"
                ISOLATED.fixture(target, kind, core, official)
                with zipfile.ZipFile(target) as archive:
                    package = json.loads(archive.read("extension/package.json"))
                    self.assertEqual(package["publisher"], "local-vscode-cn-audit")
                    self.assertEqual(package["contributes"]["localizations"][0]["languageId"], "zh-cn")
                    self.assertNotIn("main", package)
                    self.assertNotIn("activationEvents", package)
                    self.assertNotIn("extensionSignature", archive.namelist())
                    self.assertEqual(archive.read("extension/translations/main.i18n.json"), core.read_bytes())
                    self.assertEqual(len(package["contributes"]["localizations"][0]["translations"]),
                                     2 if kind == "base" else 1)
                    if kind == "base":
                        self.assertIn("extension/translations/extensions/test.json", archive.namelist())
                with self.assertRaises(FileExistsError):
                    ISOLATED.fixture(target, kind, core, official)


if __name__ == "__main__":
    unittest.main()
