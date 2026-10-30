"""scripts/tests/test_check_invariants_pkg.py

PKG-1 (partial_clone_correctness_plan.md D10): every checked-out module's
CMakeLists.txt project() name maps back to its own folder through
scripts/build.py's `adas-<x>` convention plus PACKAGE_DIR_EXCEPTIONS (read by
`ast`, never copied). Planted: a temp tree whose module breaks the mapping.

Run:
    py -3.12 -m unittest scripts.tests.test_check_invariants_pkg
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_invariants as ci  # noqa: E402


class Pkg1Tests(unittest.TestCase):

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="pkg1_"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / "scripts").mkdir()
        (self.root / "scripts" / "build.py").write_text(
            'PACKAGE_DIR_EXCEPTIONS = {"adas-shared-config": "shared_config"}\n',
            encoding="utf-8")

    def _module(self, folder, project, checked_out=True):
        mod = self.root / "modules" / folder
        mod.mkdir(parents=True)
        if checked_out:
            (mod / "conanfile.py").write_text("", encoding="utf-8")
            (mod / "CMakeLists.txt").write_text(f"project({project} VERSION 1.0.0)\n",
                                                encoding="utf-8")

    def test_real_tree_is_clean(self):
        self.assertEqual(ci.check_pkg1(), [])

    def test_convention_and_listed_exception_are_clean(self):
        self._module("interfaces", "adas-interfaces")
        self._module("shared_config", "adas-shared-config")
        self.assertEqual(ci.check_pkg1(self.root), [])

    def test_planted_unlisted_exception_is_reported(self):
        self._module("perception-core", "adas-perception_core")
        findings = ci.check_pkg1(self.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("modules/perception-core", findings[0])
        for part in ("Reason:", "Fix:", "Run:"):
            self.assertIn(part, findings[0])

    def test_absent_module_is_skipped(self):
        self._module("viz", "whatever", checked_out=False)
        self.assertEqual(ci.check_pkg1(self.root), [])


if __name__ == "__main__":
    unittest.main()
