"""
scripts/tests/test_check_invariants.py

Regression tests for LNC-1 (scripts/check_invariants.py): a launcher .bat
that resolves a Python interpreter via `where py`/`where python` must probe
the candidate with `-c ""` before trusting it. Added after a live incident
(2026-08-27) where `setup.bat`'s PYCMD detection passed on a teammate's
machine -- `where py` found the new-style py launcher stub -- but the
byte-identical block in `sim_gui.bat` then failed three tools later with
"No suitable Python runtime found" because no runtime was actually
registered behind it. The check is tested, not trusted (same discipline as
modules/sim's UT-A1-3).

Run:
    py -m unittest discover -s scripts/tests
    (from the superproject root)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import check_invariants  # noqa: E402 - path must be set up first


HARDENED_BLOCK = '''@echo off
set "PYCMD="
where py >nul 2>&1
if not errorlevel 1 (
  py -c "" >nul 2>&1
  if not errorlevel 1 set "PYCMD=py"
)
if not defined PYCMD (
  where python >nul 2>&1
  if not errorlevel 1 (
    python -c "" >nul 2>&1
    if not errorlevel 1 set "PYCMD=python"
  )
)
%PYCMD% "%~dp0scripts\\build.py" %*
'''

# The exact pre-fix pattern every launcher carried: `where py` succeeding is
# trusted outright, with no check that a runtime is actually behind it.
UNHARDENED_BLOCK = '''@echo off
set "PYCMD="
where py >nul 2>&1
if not errorlevel 1 (
  set "PYCMD=py"
) else (
  where python >nul 2>&1
  if not errorlevel 1 set "PYCMD=python"
)
%PYCMD% "%~dp0scripts\\build.py" %*
'''


class ParseQuietTests(unittest.TestCase):
    def test_planted_invalid_escape_parses_without_any_warning(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # any leaked warning becomes a failure
            check_invariants._parse("x = '\\d'\n")


class CheckLnc1Tests(unittest.TestCase):
    def test_passes_on_an_empty_tree(self):
        with self._tmp_tree() as tmp_path:
            self.assertEqual(check_invariants.check_lnc1(root=tmp_path), [])

    def test_passes_on_the_current_checkout(self):
        """The check is meant to run clean on this repo today -- a red
        result here means either a launcher regressed or the check itself
        drifted from what actually shipped."""
        self.assertEqual(check_invariants.check_lnc1(), [])

    def test_passes_on_a_hardened_launcher(self):
        with self._tmp_tree() as tmp_path:
            (tmp_path / "build.bat").write_text(HARDENED_BLOCK, encoding="utf-8")
            self.assertEqual(check_invariants.check_lnc1(root=tmp_path), [])

    def test_fails_on_a_deliberately_planted_unhardened_launcher(self):
        """The check is tested, not trusted: plant the exact bug that shipped
        (where py trusted without a runtime probe) and confirm it's caught."""
        with self._tmp_tree() as tmp_path:
            bat = tmp_path / "sim_gui.bat"
            bat.write_text(UNHARDENED_BLOCK, encoding="utf-8")
            findings = check_invariants.check_lnc1(root=tmp_path)
            self.assertTrue(findings)
            self.assertIn("LNC-1", findings[0])
            self.assertIn(str(bat), findings[0])

    def test_ignores_conan_generated_env_bats(self):
        """conanbuild.bat/conanrun.bat are Conan-generated and also spell
        the literal string "where py" nowhere -- but a look-alike name under
        a generated dir must not be flagged even if it did."""
        with self._tmp_tree() as tmp_path:
            gen_dir = tmp_path / "build-sil-vs2026"
            gen_dir.mkdir()
            (gen_dir / "conanbuild.bat").write_text(UNHARDENED_BLOCK, encoding="utf-8")
            self.assertEqual(check_invariants.check_lnc1(root=tmp_path), [])

    @staticmethod
    def _tmp_tree():
        import tempfile
        from contextlib import contextmanager
        from pathlib import Path

        @contextmanager
        def _ctx():
            with tempfile.TemporaryDirectory() as d:
                yield Path(d)

        return _ctx()


class WalkFilesTests(unittest.TestCase):
    """`_walk_files()` -- a subtree `os.scandir()` cannot even open (a
    foreign-OS symlink such as a WSL venv's `lib64` -> `lib`, found live via
    a real `WinError 1920` walking a real WSL-created `.venv` from native
    Windows) is skipped with a printed warning naming the exact path and
    error, never a hard crash -- and every OTHER path, including a real
    finding in a sibling directory, is still walked and checked exactly as
    before. A genuine cross-OS-incompatible symlink can't be created
    portably without admin rights on Windows, so the unreadable directory
    is mocked instead: `os.scandir()` raises for exactly one path, real
    everywhere else -- the same shape the live incident took."""

    def test_skips_an_unreadable_subtree_with_a_warning_and_keeps_walking(self):
        with self._tmp_tree() as tmp_path:
            good_dir = tmp_path / "good"
            good_dir.mkdir()
            (good_dir / "found.bat").write_text("hello", encoding="utf-8")

            bad_dir = tmp_path / "bad"
            bad_dir.mkdir()
            (bad_dir / "unreachable.bat").write_text("hello", encoding="utf-8")

            stderr_text, results = self._walk_with_bad_dir(tmp_path, bad_dir, suffix=".bat")

            self.assertEqual(results, [good_dir / "found.bat"])
            self.assertIn(str(bad_dir), stderr_text)
            self.assertIn("unreadable", stderr_text)

    def test_check_lnc1_does_not_crash_and_still_reports_findings_elsewhere(self):
        """End-to-end: an unreadable subtree must never swallow a REAL
        finding in a sibling directory that DOES resolve -- the fix only
        excuses a path it flatly cannot inspect, it must never weaken this
        check for a path it can."""
        with self._tmp_tree() as tmp_path:
            bad_dir = tmp_path / "bad"
            bad_dir.mkdir()

            victim = tmp_path / "sim_gui.bat"
            victim.write_text(UNHARDENED_BLOCK, encoding="utf-8")

            import io
            from contextlib import redirect_stderr
            from unittest import mock

            real_scandir = os.scandir
            bad_dir_str = str(bad_dir)

            def _fake_scandir(path="."):
                if str(path) == bad_dir_str:
                    raise OSError(1920, "The file cannot be accessed by the system", bad_dir_str)
                return real_scandir(path)

            stderr = io.StringIO()
            with mock.patch("os.scandir", side_effect=_fake_scandir):
                with redirect_stderr(stderr):
                    findings = check_invariants.check_lnc1(root=tmp_path)

            self.assertTrue(findings, "the real finding in a sibling directory must still be reported")
            self.assertIn(str(victim), findings[0])
            self.assertIn(bad_dir_str, stderr.getvalue())

    @staticmethod
    def _walk_with_bad_dir(tmp_path, bad_dir, suffix):
        import io
        from contextlib import redirect_stderr
        from unittest import mock

        real_scandir = os.scandir
        bad_dir_str = str(bad_dir)

        def _fake_scandir(path="."):
            if str(path) == bad_dir_str:
                raise OSError(1920, "The file cannot be accessed by the system", bad_dir_str)
            return real_scandir(path)

        stderr = io.StringIO()
        with mock.patch("os.scandir", side_effect=_fake_scandir):
            with redirect_stderr(stderr):
                results = check_invariants._walk_files(tmp_path, suffix=suffix)
        return stderr.getvalue(), results

    @staticmethod
    def _tmp_tree():
        import tempfile
        from contextlib import contextmanager
        from pathlib import Path

        @contextmanager
        def _ctx():
            with tempfile.TemporaryDirectory() as d:
                yield Path(d)

        return _ctx()


class CheckCpy1Tests(unittest.TestCase):
    """CPY-1 -- copy-distributed build files agree with modules/toolchain/
    copy_files/. Same "tested, not trusted" discipline as CheckLnc1Tests:
    the gate is proven to catch a real drift, and proven NOT to fire on a
    component that simply never carried one of these files
    (modules/toolchain/docs/imp_design.md §2.6 Option A)."""

    TRACKED = "build.bat"

    def test_passes_on_the_current_checkout(self):
        """Green today. A red result means a real copy-distributed file
        drifted from toolchain -- run
        `python modules/toolchain/scripts/check_copy_files.py` for the list."""
        self.assertEqual(check_invariants.check_cpy1(), [])

    def test_fails_on_a_deliberately_planted_drift(self):
        """Plant a real byte difference in a tracked copy and confirm it is
        reported. Restores the file even if the assertion fails."""
        from pathlib import Path

        root = Path(check_invariants.ROOT)
        canonical = root / "modules" / "toolchain" / "copy_files" / self.TRACKED
        if not canonical.is_file():
            self.skipTest("modules/toolchain is not checked out")
        victim = next(
            (p / self.TRACKED for p in sorted((root / "modules").iterdir())
             if (p / "conf" / "build.yml").is_file() and (p / self.TRACKED).is_file()),
            None,
        )
        if victim is None:
            self.skipTest("no component carries a tracked copy to plant into")

        original = victim.read_bytes()
        try:
            victim.write_bytes(original + b"\r\nREM planted drift (CPY-1 self-test)\r\n")
            findings = check_invariants.check_cpy1()
            self.assertTrue(findings, "planted drift was not caught")
            self.assertTrue(any(victim.parent.name in f and "differs" in f for f in findings), findings)
        finally:
            victim.write_bytes(original)

    def test_a_declared_gap_is_not_reported_as_a_violation(self):
        """Option A: a component that never carried a .clang-format is not a
        finding. This is the case the first wiring got wrong -- the gap lines
        also start with "modules/", so an unanchored filter reported all ten
        of them as violations alongside a single real drift."""
        findings = check_invariants.check_cpy1()
        self.assertFalse(
            [f for f in findings if "not distributed here" in f],
            "declared Option-A gaps must not be reported as CPY-1 violations",
        )


if __name__ == "__main__":
    unittest.main()
