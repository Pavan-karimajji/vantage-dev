"""AB-12: the aggregate GUI's dependency-ticking rule, as pure functions (no Tk)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
try:
    import build_gui  # noqa: E402 - imports tkinter at module level
except ImportError as exc:  # e.g. WSL/Linux python3 without python3-tk
    raise unittest.SkipTest(f"build_gui not importable here ({exc}); runs where Tk exists")

USERS = {"interfaces": ["sim", "viz"], "mathlib": [], "shared_config": []}


class ParseDepsLineTests(unittest.TestCase):
    def test_default_and_flagged_lines_parse(self):
        self.assertEqual(build_gui.parse_deps_line("mathlib"), ("mathlib", False, []))
        self.assertEqual(build_gui.parse_deps_line("shared_config [data]"),
                         ("shared_config", True, []))
        self.assertEqual(build_gui.parse_deps_line("interfaces  users: sim viz"),
                         ("interfaces", False, ["sim", "viz"]))


class ParseConfigTests(unittest.TestCase):
    """A fresh superproject clone: `build.py config` names modules that are not
    checked out, and the GUI offers them for check-out instead of building."""

    def test_matrix_and_not_checked_out_line_parse(self):
        out = ("python scripts/build.py df -t sil -p vs2026 -P base\n"
               "python scripts/build.py df -t gtest -p vs2026 -P base\n"
               "\nadd --clean to any of the above\n"
               "python scripts/build.py <module> -t <target> -p <platform> --with-all  <- aggregator\n"
               "not checked out: vdy viz\n")
        matrix, absent = build_gui.parse_config(out)
        self.assertEqual(matrix, {"base": {"df": {"sil": ["vs2026"], "gtest": ["vs2026"]}}})
        self.assertEqual(absent, ["vdy", "viz"])

    def test_fresh_clone_has_no_matrix_only_modules_to_check_out(self):
        matrix, absent = build_gui.parse_config("not checked out: df interfaces\n")
        self.assertEqual((matrix, absent), ({}, ["df", "interfaces"]))

    def test_no_line_means_nothing_to_check_out(self):
        self.assertEqual(build_gui.parse_config("python scripts/build.py df -t sil -p vs2026 -P base\n")[1], [])


class DepSelectionTests(unittest.TestCase):
    def test_planted_ticking_interfaces_ticks_and_locks_sim_and_viz(self):
        ticked, locked = build_gui.dep_selection({"interfaces"}, USERS)
        self.assertEqual(ticked, {"interfaces", "sim", "viz"})
        self.assertEqual(locked, {"sim": ["interfaces"], "viz": ["interfaces"]})

    def test_unticking_releases_the_forced_modules(self):
        self.assertEqual(build_gui.dep_selection(set(), USERS), (set(), {}))

    def test_a_module_needed_by_two_deps_stays_locked_until_both_go(self):
        users = {"a": ["z"], "b": ["z"]}
        _, locked = build_gui.dep_selection({"a", "b"}, users)
        self.assertEqual(locked, {"z": ["a", "b"]})
        ticked, locked = build_gui.dep_selection({"b"}, users)  # a unticked
        self.assertEqual((ticked, locked), ({"b", "z"}, {"z": ["b"]}))

    def test_user_tick_survives_the_lock_being_released(self):
        ticked, _ = build_gui.dep_selection({"sim"}, USERS)  # sim ticked by the user
        self.assertIn("sim", ticked)

    def test_data_dep_forces_nothing(self):
        self.assertEqual(build_gui.dep_selection({"shared_config"}, USERS),
                         ({"shared_config"}, {}))


if __name__ == "__main__":
    unittest.main()
