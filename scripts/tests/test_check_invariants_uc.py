# Copyright (c) LT EPS. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SUPERPROJECT
# @file test_check_invariants_uc.py
# @brief UC-1: the use-case tags are checked from the invariants gate, and a planted violation is seen.
# @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

"""R-REQ-9: a check nobody has seen fail is a check nobody should believe. Scratch trees, no real df checkout needed.
Run from the superproject root: python -m pytest scripts/tests/test_check_invariants_uc.py"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import check_invariants as ci  # noqa: E402

DF = ROOT / "modules" / "df"
TABLE = ("| Box | ID | WP | Question | Variants | Decided by | Where | Starting point |\n|---|---|---|---|---|---|---|---|\n"
         "| `[x]` | `UC-01` | `WP-U01` | q | v | `SYS-1` | B | - |\n")


@unittest.skipUnless((DF / "scripts" / "check_use_cases.py").is_file(), "modules/df is not checked out")
class UseCaseGateTests(unittest.TestCase):
    def tree(self, spec_tag):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        shutil.copytree(DF / "scripts", root / "modules" / "df" / "scripts", ignore=shutil.ignore_patterns("__pycache__", "tests"))
        shutil.copytree(DF / "tools" / "carla", root / "modules" / "df" / "tools" / "carla", ignore=shutil.ignore_patterns("__pycache__", "replay"))
        folder = root / "modules" / "df" / "docs" / "f"
        folder.mkdir(parents=True)
        (folder / "F_Use_Case_Catalogue.md").write_text(TABLE, encoding="utf-8")
        (folder / "F_Test_Spec.md").write_text(f"**`SYT-F-01`** - t\n- `.c1` {spec_tag} **PASS:** a. **FAIL:** b.\n", encoding="utf-8")
        (folder / "F_Test_Execution_d_usecases.md").write_text("### UC-01 - q\n\n| bench | `SYT-F-01.c1` | PASS | e |\n", encoding="utf-8")
        return root

    def test_a_consistent_tree_is_clean(self):
        self.assertEqual(ci.check_uc1(self.tree("[UC-01]")), [])

    def test_planted_a_tag_naming_no_row_is_a_finding(self):
        findings = ci.check_uc1(self.tree("[UC-77]"))
        self.assertTrue(any("UC-77" in f for f in findings), findings)

    def test_the_real_tree_is_clean(self):
        self.assertEqual(ci.check_uc1(ROOT), [])


if __name__ == "__main__":
    unittest.main()
