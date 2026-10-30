# Copyright (c) LT EPS. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SUPERPROJECT
# @file test_vantage_bat_guard.py
# @brief vantage.bat's no-arguments guard must survive a quoted argument with a space.
# @author Pavan Karimajji

"""close-open-points item 9 (found in review): `if "%*"=="" (` makes cmd.exe
stop with `... was unexpected at this time.` for `vantage.bat "C:\\a b\\c.mcap"`.
`%~1` strips the quotes. The guard line is lifted from the real vantage.bat
and run for real, so this fails the day someone writes `"%*"` there again."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

VANTAGE = Path(__file__).resolve().parents[2] / "modules" / "sim" / "vantage.bat"


@unittest.skipUnless(sys.platform == "win32", "needs cmd.exe to parse a batch `if`")
@unittest.skipUnless(VANTAGE.is_file(), "modules/sim is not checked out")
class VantageGuardTests(unittest.TestCase):
    def _run(self, *args):
        guard = next(l for l in VANTAGE.read_text(encoding="ascii").splitlines()
                     if l.startswith("if ") and '=="" (' in l)
        with tempfile.TemporaryDirectory() as tmp:
            bat = Path(tmp) / "guard.bat"
            bat.write_text(f"@echo off\r\n{guard}\r\n  echo NOARGS\r\n  exit /b 0\r\n)\r\n"
                           "echo HASARGS\r\n", encoding="ascii")
            return subprocess.run(["cmd", "/c", "call", str(bat), *args],
                                  capture_output=True, text=True)

    def test_planted_quoted_path_with_a_space_is_not_a_syntax_error(self):
        proc = self._run("C:\\a b\\c.mcap")  # subprocess quotes it, as a user would
        self.assertIn("HASARGS", proc.stdout, proc.stdout + proc.stderr)
        self.assertNotIn("unexpected", proc.stdout + proc.stderr)

    def test_no_arguments_still_opens_the_launcher_branch(self):
        self.assertIn("NOARGS", self._run().stdout)


if __name__ == "__main__":
    unittest.main()
