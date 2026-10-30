import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location("incremental", Path(__file__).with_name("build_incremental.py"))
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)


class IncrementalTests(unittest.TestCase):
    def run_audit(self, entries, contents, dictionary=None):
        return BUILD.audit(entries, {"version": "1", "contents": contents},
                           dictionary or {"entries": [], "keep": []})

    def test_exact_key_source_donor(self):
        delta, merged, report = self.run_audit(
            [("a", "retry", "Retry"), ("b", "retry", "Retry")], {"a": {"retry": "重试"}})
        self.assertEqual(delta["contents"], {"b": {"retry": "重试"}})
        self.assertEqual(merged["contents"]["a"]["retry"], "重试")
        self.assertEqual(report["summary"]["applied"], 1)

    def test_no_cross_key_or_changed_source_reuse(self):
        _, _, report = self.run_audit(
            [("a", "retry", "Retry"), ("b", "other", "Retry"), ("c", "retry", "Retry now")],
            {"a": {"retry": "重试"}})
        self.assertEqual(report["summary"]["pending"], 2)

    def test_ambiguous_donor_not_reused(self):
        _, _, report = self.run_audit(
            [("a", "x", "Run"), ("b", "x", "Run"), ("c", "x", "Run")],
            {"a": {"x": "运行"}, "b": {"x": "执行"}})
        self.assertEqual(report["summary"]["pending"], 1)

    def test_official_values_never_replaced(self):
        base = {"a": {"x": "官方译文", "y": "Run"}}
        _, merged, report = self.run_audit(
            [("a", "x", "Run"), ("a", "y", "Run")], base,
            {"entries": [{"source": "Run", "translation": "运行"}], "keep": []})
        self.assertEqual(merged["contents"], base)
        self.assertEqual(report["pending"][0]["reason"], "official_unchanged")
        self.assertEqual(report["summary"]["applied"], 0)

    def test_empty_value_can_be_filled(self):
        _, merged, _ = self.run_audit(
            [("a", "x", "Run")], {"a": {"x": ""}},
            {"entries": [{"source": "Run", "translation": "运行"}], "keep": []})
        self.assertEqual(merged["contents"]["a"]["x"], "运行")

    def test_formatting_damage_rejected(self):
        for source, translation in [
            ("Open {0}", "打开"), ("{0} {0}", "{0}"),
            ("`command.id`", "`different.id`"), ("$(gear)", "齿轮"),
            ("[help](https://example.com)", "[帮助](https://wrong.com)"),
            ("<b>Run</b>", "运行"), ("Run\nNow", "立即运行"), ("&&Run", "运行"),
            ("Value %s", "值"), ("Value ${name}", "值 ${other}"),
        ]:
            with self.subTest(source=source), self.assertRaises(ValueError):
                BUILD.validate_translation(source, translation)

    def test_reordered_placeholders_allowed(self):
        BUILD.validate_translation("{0} on {1}", "在 {1} 上的 {0}")

    def test_keep_and_format_only_classification(self):
        _, _, report = self.run_audit(
            [("a", "brand", "GitHub"), ("a", "format", "{0} {1}")], {},
            {"entries": [], "keep": ["GitHub"]})
        self.assertEqual(report["summary"]["kept_nontranslatable"], 2)
        self.assertEqual(report["summary"]["pending"], 0)

    def test_no_silent_dropping(self):
        entries = [("a", "a", "Run"), ("b", "b", "Else"), ("a", "c", "GitHub")]
        _, _, report = self.run_audit(entries, {}, {
            "entries": [{"source": "Run", "translation": "运行"}], "keep": ["GitHub"]})
        summary = report["summary"]
        self.assertEqual(sum(summary["candidates"].values()),
                         summary["applied"] + summary["pending"] + summary["kept_nontranslatable"])

    def test_keys_messages_alignment_and_duplicates(self):
        for keys, messages in [([["m", ["x"]]], []), ([["m", ["x", "x"]]], ["a", "b"])]:
            with self.assertRaises(ValueError):
                BUILD.flatten(keys, messages)

    def test_same_source_repeated_runtime_occurrences(self):
        entries = BUILD.flatten([["a", ["x", "x"]]], ["Run", "Run"])
        _, _, report = self.run_audit(entries, {})
        self.assertEqual(report["summary"]["runtime_occurrences"], 2)
        self.assertEqual(report["summary"]["unique_build_keys"], 1)
        self.assertEqual(len(report["pending"]), 1)

    def test_duplicate_json_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"
            path.write_text('{"a": 1, "a": 2}')
            with self.assertRaises(ValueError):
                BUILD.read_json(path)

    def test_reviewed_dictionary_is_format_safe(self):
        dictionary = BUILD.read_json(Path(__file__).with_name("reviewed-zh-cn.json"))
        self.run_audit([], {}, dictionary)

    def test_deterministic_and_input_immutable(self):
        contents = {"a": {"x": "运行"}}
        before = json.dumps(contents)
        args = ([("a", "x", "Run"), ("b", "x", "Run")], contents)
        self.assertEqual(self.run_audit(*args), self.run_audit(*args))
        self.assertEqual(json.dumps(contents), before)

    def test_cli_outputs_repeatability_and_safe_refusal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = root / "app"
            (app / "out").mkdir(parents=True)
            files = {
                app / "package.json": {"version": "1.144.0"},
                app / "product.json": {"commit": "fixture"},
                app / "out/nls.keys.json": [["m", ["x", "y"]]],
                app / "out/nls.messages.json": ["Retry", "Unknown sentence"],
                root / "official.json": {"contents": {}},
            }
            # Keep the official resource in its own protected directory.
            official = root / "official" / "main.json"
            official.parent.mkdir()
            files[official] = files.pop(root / "official.json")
            for path, data in files.items():
                path.write_text(json.dumps(data))
            command = [sys.executable, str(Path(__file__).with_name("build_incremental.py")),
                       "--app", str(app), "--official", str(official)]
            for name in ["first", "second"]:
                result = subprocess.run(command + ["--output", str(root / name)],
                                        text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            for name in ["audit.json", "delta.json", "merged-main.i18n.json"]:
                self.assertEqual((root / "first" / name).read_bytes(),
                                 (root / "second" / name).read_bytes())
            report = BUILD.read_json(root / "first/audit.json")
            self.assertEqual(report["summary"]["applied"], 1)
            self.assertEqual(report["summary"]["pending"], 1)
            self.assertFalse(report["summary"]["installed"])
            for blocked in [root / "first", app / "new", official.parent / "new"]:
                result = subprocess.run(command + ["--output", str(blocked)],
                                        text=True, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Incremental localization failed:", result.stderr)
            self.assertFalse((app / "new").exists())


if __name__ == "__main__":
    unittest.main()
