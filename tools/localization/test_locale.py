import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location("locale_config", Path(__file__).with_name("set_locale.py"))
LOCALE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LOCALE)


class LocaleTests(unittest.TestCase):
    def test_existing_locale_preserves_comments_and_other_values(self):
        text = '// header\n{"locale": "zh-cn", /* note */ "other": "https://a/b",}'
        patched = LOCALE.patch(text, True, "zh-cn-mars")
        self.assertEqual(patched, text.replace('"zh-cn"', '"zh-cn-mars"'))
        self.assertEqual(LOCALE.patch(patched, True, "zh-cn"), text)

    def test_adding_and_removing_keeps_other_settings(self):
        for text in ['{}', '{// comment\n}', '{"a": 1}', '{"a": 1,}', '{"nested":{"locale":"en"}}',
                     '{"value":"locale", "format":",}"}', '{"value":"// not a comment"}']:
            with self.subTest(text=text):
                result = LOCALE.patch(text, True, "zh-cn-mars")
                restored = LOCALE.patch(result, False, None)
                self.assertEqual(LOCALE.parse(restored)[0], LOCALE.parse(text)[0])

    def test_remove_locale_at_any_position(self):
        for text in ['{"locale":"zh-cn-mars","a":1}', '{"a":1,"locale":"zh-cn-mars"}',
                     '{"a":1,"locale":"zh-cn-mars",}', '{"locale":"zh-cn-mars"}']:
            result = LOCALE.patch(text, False, None)
            self.assertNotIn("locale", LOCALE.parse(result)[0])

    def test_duplicate_and_invalid_values_rejected(self):
        for text in ['{"locale":"en","locale":"zh-cn"}', '{"locale":42}', '{"locale":null}']:
            with self.assertRaises(ValueError):
                LOCALE.patch(text, True, "zh-cn-mars")

    def test_cli_backup_contains_only_locale_and_restore_retains_new_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            argv, backup = root / "argv.json", root / "backup.json"
            argv.write_text('// comment\n{"crash-reporter-id":"not-copied","locale":"zh-cn"}')
            command = [sys.executable, str(Path(__file__).with_name("set_locale.py"))]
            flags = ["--argv", str(argv), "--backup", str(backup)]
            activate = subprocess.run(command + ["activate"] + flags, capture_output=True, text=True)
            self.assertEqual(activate.returncode, 0, activate.stderr)
            self.assertNotIn("not-copied", backup.read_text())
            self.assertEqual(json.loads(backup.read_text())["value"], "zh-cn")
            argv.write_text(argv.read_text().replace('{"', '{"new":true,"', 1))
            restore = subprocess.run(command + ["restore"] + flags, capture_output=True, text=True)
            self.assertEqual(restore.returncode, 0, restore.stderr)
            self.assertTrue(LOCALE.parse(argv.read_text())[0]["new"])
            self.assertEqual(LOCALE.parse(argv.read_text())[0]["locale"], "zh-cn")

    def test_cli_restore_refuses_changed_locale(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            argv, backup = root / "argv.json", root / "backup.json"
            argv.write_text("{}")
            command = [sys.executable, str(Path(__file__).with_name("set_locale.py"))]
            flags = ["--argv", str(argv), "--backup", str(backup)]
            self.assertEqual(subprocess.run(command + ["activate"] + flags, capture_output=True).returncode, 0)
            argv.write_text('{"locale":"fr"}')
            result = subprocess.run(command + ["restore"] + flags, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(argv.read_text(), '{"locale":"fr"}')


if __name__ == "__main__":
    unittest.main()
