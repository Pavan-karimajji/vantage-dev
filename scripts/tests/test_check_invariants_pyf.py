"""
scripts/tests/test_check_invariants_pyf.py

Regression tests for PYF-1 (scripts/check_invariants.py, PT-29 --
python_tool_envs_plan.md D20). Planted-violation proof (R-REQ-9): each
failure mode is planted in a synthetic tree and must be reported; the
allowed shapes must stay clean; the real checkout passes with today's
_PYF1_OFFENDERS.

Run:
    py -m unittest discover -s scripts/tests
    (from the superproject root)
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import check_invariants  # noqa: E402 - path must be set up first

HEADER = "import sys\nfrom pathlib import Path\n"


class PyfTreeFixture(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="pyf_invariant_")
        self.root = Path(self._tmp)
        for comp in ("df", "viz", "interfaces", "sim"):
            d = self.root / "modules" / comp
            (d / "conf").mkdir(parents=True)
            (d / "conanfile.py").write_text("", encoding="utf-8")
            (d / "conf" / "build.yml").write_text("", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _py(self, rel, body):
        path = self.root / "modules" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(HEADER + body, encoding="utf-8")
        return path

    def _check(self, offenders=None, test_pairs=None):
        return check_invariants.check_pyf1(
            self.root, offenders={} if offenders is None else offenders,
            test_pairs={} if test_pairs is None else test_pairs)

    def test_clean_tree_passes(self):
        self.assertEqual(self._check(), [])

    def test_other_component_folder_is_a_finding(self):
        self._py("df/tools/new_tool.py",
                 "MODULES_ROOT = Path(__file__).resolve().parents[2]\n"
                 "sys.path.insert(0, str(MODULES_ROOT / 'viz' / 'src'))\n")
        findings = self._check()
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("modules/df/tools/new_tool.py:4", findings[0])
        self.assertIn("modules/viz/src", findings[0])

    def test_same_line_inside_interfaces_is_allowed(self):
        self._py("interfaces/tools/new_tool.py",
                 "MODULES_ROOT = Path(__file__).resolve().parents[2]\n"
                 "sys.path.insert(0, str(MODULES_ROOT / 'viz' / 'src'))\n")
        self.assertEqual(self._check(), [])

    def test_own_component_folder_is_allowed(self):
        self._py("df/docs/bsd/py/probe.py",
                 "THIS_DIR = Path(__file__).resolve().parent\n"
                 "DF_ROOT = THIS_DIR.parents[2]\n"
                 "CARLA_TOOLS_DIR = DF_ROOT / 'tools' / 'carla'\n"
                 "sys.path.insert(0, str(CARLA_TOOLS_DIR))\n")
        self.assertEqual(self._check(), [])

    def test_generated_py_is_a_finding(self):
        self._py("df/tools/replay.py",
                 "import os\n"
                 "GEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', "
                 "'interfaces', 'build', 'generated_py')\n"
                 "sys.path.append(GEN)\n")
        findings = self._check()
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("generated_py", findings[0])

    def test_mentioning_generated_py_is_not_a_finding(self):
        self._py("viz/scripts/fence.py",
                 "# never import from generated_py or modules/sim\n"
                 "EXCLUDED = {'generated_py', 'node_modules', 'sim'}\n"
                 "print('generated_py is forbidden')\n")
        self.assertEqual(self._check(), [])

    def test_unresolvable_expression_naming_a_component_is_a_finding(self):
        self._py("df/tools/env_tool.py",
                 "import os\n"
                 "sys.path.insert(0, os.environ['ROOT'] + '/viz/src')\n")
        findings = self._check()
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("could not be fully resolved", findings[0])
        self.assertIn("viz", findings[0])

    def test_loop_over_paths_judges_each(self):
        self._py("viz/tools/loop.py",
                 "HERE = Path(__file__).resolve().parent\n"
                 "for _p in (HERE, HERE.parents[1] / 'sim' / 'src'):\n"
                 "    sys.path.insert(0, str(_p))\n")
        findings = self._check()
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("modules/sim/src", findings[0])

    def test_offender_on_list_is_suppressed(self):
        self._py("df/tools/new_tool.py",
                 "sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'viz'))\n")
        self.assertEqual(self._check({"modules/df/tools/new_tool.py": "planted"}), [])

    def test_list_entry_that_no_longer_offends_is_a_finding(self):
        self._py("df/tools/fixed_tool.py", "print('fixed')\n")
        findings = self._check({"modules/df/tools/fixed_tool.py": "was fixed"})
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("no longer offends", findings[0])

    # --- D24 (PT-43) ---------------------------------------------------
    def test_unparseable_file_is_a_finding_naming_file_and_interpreter(self):
        self._py("df/tools/broken.py", "def broken(:\n")
        (finding,) = self._check()
        self.assertIn("modules/df/tools/broken.py", finding)
        self.assertIn(f"Python {sys.version_info.major}.{sys.version_info.minor}", finding)
        self.assertIn("cannot be parsed", finding)
        self.assertIn("check_invariants.py", finding)

    def test_unparseable_offender_is_not_no_longer_offends(self):
        self._py("df/tools/broken.py", "def broken(:\n")
        findings = self._check({"modules/df/tools/broken.py": "planted"})
        self.assertEqual(len(findings), 1, findings)
        self.assertNotIn("no longer offends", findings[0])
        self.assertIn("cannot be parsed", findings[0])

    def test_older_interpreter_prints_one_reason_fix_run(self):
        from unittest import mock
        with mock.patch.object(check_invariants, "_platform_python", return_value="3.99"):
            lines = check_invariants.older_interpreter_notice(self.root)
        self.assertEqual([l.split(":")[0] for l in lines], ["Reason", "Fix", "Run"])
        self.assertIn("3.99", lines[2])
        self.assertIn("check_invariants.py", lines[2])
        self.assertNotIn("<", lines[2])
        with mock.patch.object(check_invariants, "_platform_python",
                               return_value=f"{sys.version_info.major}.{sys.version_info.minor}"):
            self.assertEqual(check_invariants.older_interpreter_notice(self.root), [])

    # --- D23 (PT-44) ---------------------------------------------------
    def _cross_test(self):
        self._py("sim/tests/unit/test_pack.py",
                 "sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'interfaces' / "
                 "'scripts'))\n")

    def test_test_pair_with_a_reason_naming_the_component_is_allowed(self):
        self._cross_test()
        self.assertEqual(self._check(test_pairs={
            "modules/sim/tests/unit/test_pack.py":
                "round-trips interfaces' packer against sim's reader"}), [])

    def test_unresolved_test_pair_does_not_demand_its_own_component_in_the_reason(self):
        """A reason must name the components a test REACHES, never the one it
        lives in (found in review, close-open-points item 9)."""
        self._py("sim/tests/unit/test_env.py",
                 "import os\n"
                 "sys.path.insert(0, os.environ['ROOT'] + '/viz/src')\n")
        self.assertEqual(self._check(test_pairs={
            "modules/sim/tests/unit/test_env.py": "reads viz's own renderer output"}), [])

    def test_test_pair_without_reason_is_a_finding(self):
        self._cross_test()
        (finding,) = self._check(test_pairs={"modules/sim/tests/unit/test_pack.py": "  "})
        self.assertIn("without a reason", finding)

    def test_test_pair_reason_that_does_not_name_the_component_is_a_finding(self):
        self._cross_test()
        (finding,) = self._check(test_pairs={
            "modules/sim/tests/unit/test_pack.py": "it is a file under a tests/ folder"})
        self.assertIn("does not name interfaces", finding)

    def test_non_test_file_on_the_tests_list_is_a_finding(self):
        self._py("viz/sim/compare.py",
                 "sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'sim' / 'src'))\n")
        (finding,) = self._check(test_pairs={"modules/viz/sim/compare.py":
                                             "compares viz's scene with sim's"})
        self.assertIn("is not a test", finding)

    def test_stale_tests_entry_is_a_finding(self):
        self._py("sim/tests/unit/test_fixed.py", "print('fixed')\n")
        (finding,) = self._check(test_pairs={"modules/sim/tests/unit/test_fixed.py":
                                             "used interfaces' packer"})
        self.assertIn("no longer offends", finding)

    def test_real_repo_is_clean(self):
        self.assertEqual(check_invariants.check_pyf1(), [])


if __name__ == "__main__":
    unittest.main()
