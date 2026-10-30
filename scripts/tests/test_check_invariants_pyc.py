"""scripts/tests/test_check_invariants_pyc.py

PYC-1 (2026-09-29): an install(DIRECTORY) of a Python-bearing source
directory must exclude __pycache__ and *.pyc -- those bytes differ per
machine and per run, so a package carrying them is not reproducible.
Planted: a temp modules/<m>/CMakeLists.txt installing a directory with a
.py file, with and without the excludes.

Run:
    py -3.12 -m unittest scripts.tests.test_check_invariants_pyc
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_invariants as ci  # noqa: E402


class Pyc1Tests(unittest.TestCase):

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="pyc1_"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.comp = self.root / "modules" / "comp"
        (self.comp / "scripts").mkdir(parents=True)
        (self.comp / "scripts" / "tool.py").write_text("X = 1\n", encoding="utf-8")
        (self.comp / "cpp").mkdir()
        (self.comp / "cpp" / "a.h").write_text("", encoding="utf-8")

    def _cmake(self, text):
        (self.comp / "CMakeLists.txt").write_text(text, encoding="utf-8")
        return ci.check_pyc1(self.root)

    def test_real_tree_is_clean(self):
        self.assertEqual(ci.check_pyc1(), [])

    def test_python_dir_without_excludes_is_reported(self):
        findings = self._cmake('install(DIRECTORY scripts/ DESTINATION scripts\n'
                               '    PATTERN "build.py" EXCLUDE\n)\n')
        self.assertEqual(len(findings), 1)
        self.assertIn("modules/comp/CMakeLists.txt:1 install(DIRECTORY scripts/)", findings[0])
        for part in ("Reason:", "Fix:", "Run:"):
            self.assertIn(part, findings[0])

    def test_only_one_exclude_is_still_reported(self):
        self.assertEqual(len(self._cmake(
            'install(DIRECTORY scripts/ DESTINATION scripts PATTERN "__pycache__" EXCLUDE)\n')), 1)

    def test_python_dir_with_both_excludes_is_clean(self):
        self.assertEqual(self._cmake(
            'install(DIRECTORY scripts/ DESTINATION scripts\n'
            '    PATTERN "__pycache__" EXCLUDE\n    PATTERN "*.pyc" EXCLUDE)\n'), [])

    def test_non_python_dir_and_commented_install_are_ignored(self):
        self.assertEqual(self._cmake(
            'install(DIRECTORY cpp/ DESTINATION include)\n'
            '# install(DIRECTORY scripts/ DESTINATION scripts)\n'
            'install(TARGETS foo DESTINATION lib)\n'), [])


if __name__ == "__main__":
    unittest.main()
