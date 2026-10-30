"""
scripts/tests/test_check_invariants_cold.py

Regression tests for COLD-1 (scripts/check_invariants.py, NS-44 --
cache_first_no_server_plan.md, RQ-8). RQ-8 says a machinery change is not
done until it is proven on a manufactured empty machine; before this
check, "was the cold check re-run since the last machinery change"
depended on a human re-reading this plan's own STATUS prose -- exactly
the discipline that let four accidental PASSes stand undetected. This is
the planted-violation proof (R-REQ-9): touch a machinery file after the
last recorded passing run, watch COLD-1 fail naming the commit; a record
that still covers HEAD (or no record at all) passes.

check_cold1() runs real `git log` against `root`, so this needs a real
(if tiny, temporary) git repository -- unlike REM-1/REM-2/BUN-1's plain
tempdir fixtures, which never touch git. Isolated from the real
superproject repo throughout.

Run:
    py -m unittest discover -s scripts/tests
    (from the superproject root)
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import check_invariants  # noqa: E402 - path must be set up first


def _git(root, *args, check=True):
    proc = subprocess.run(["git", *args], cwd=str(root), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    if check and proc.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {proc.stderr}")
    return proc


def _head(root):
    return _git(root, "rev-parse", "HEAD").stdout.strip()


class _GitRepoFixture(unittest.TestCase):
    """A real, tiny git repo under a temp dir -- COLD-1 shells out to
    `git log`, so it needs real commit history, not just files on disk."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cold_invariant_")
        self.root = Path(self._tmp)
        _git(self.root, "init", "-q")
        _git(self.root, "config", "user.email", "test@example.com")
        _git(self.root, "config", "user.name", "Test")
        (self.root / "README.md").write_text("seed\n", encoding="utf-8")
        _git(self.root, "add", "README.md")
        _git(self.root, "commit", "-q", "-m", "seed")

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _commit_file(self, rel_path, contents="x\n", message="change"):
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
        _git(self.root, "add", rel_path)
        _git(self.root, "commit", "-q", "-m", message)
        return _head(self.root)

    def _write_record(self, mode, commit, timestamp="2026-09-25T00:00:00Z",
                      with_all_ok=True, lock_steps_ok=True):
        """`with_all_ok`: True writes a passing NS-55 --with-all step, False a
        failing one, None omits it (a record from before NS-55). `lock_steps_ok`
        does the same for the three NS-68 lock steps."""
        record_path = self.root / "scripts" / "cold_run_record.json"
        record_path.parent.mkdir(parents=True, exist_ok=True)
        existing = {}
        if record_path.is_file():
            import json
            existing = json.loads(record_path.read_text(encoding="utf-8"))
        existing[mode] = {
            "commit": commit,
            "timestamp_utc": timestamp,
            "mode": mode,
            "steps": [{"name": "setup.bat [no-server]", "ok": True}],
        }
        if with_all_ok is not None:
            existing[mode]["steps"].append(
                {"name": check_invariants.COLD1_WITH_ALL_STEP, "ok": with_all_ok})
        if lock_steps_ok is not None:
            for name in check_invariants.COLD1_LOCK_STEPS:
                existing[mode]["steps"].append({"name": name, "ok": lock_steps_ok})
        import json
        record_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")


    def _write_all_modes(self, commit, **kwargs):
        """NS-45: a green tree needs EVERY required mode recorded."""
        for mode in check_invariants.COLD1_REQUIRED_MODES:
            self._write_record(mode, commit, **kwargs)


class CheckCold1Tests(_GitRepoFixture):

    def test_no_record_at_all_passes(self):
        self.assertEqual(check_invariants.check_cold1(self.root), [])

    def test_record_matching_head_passes(self):
        head = _head(self.root)
        self._write_all_modes(head)
        self.assertEqual(check_invariants.check_cold1(self.root), [])

    def test_record_older_but_no_machinery_touched_passes(self):
        """A commit landed after the recorded sha, but it never touched
        scripts/, adas_build_tools/, copy_files/ or a build_tools.version
        pin -- COLD-1 only cares about machinery paths."""
        recorded = _head(self.root)
        self._write_all_modes(recorded)
        self._commit_file("docs/unrelated.md", message="docs only")
        self.assertEqual(check_invariants.check_cold1(self.root), [])

    def test_planted_machinery_change_after_record_is_caught(self):
        """The exact live gap NS-44 closes: a commit touching scripts/
        landed after the last recorded passing cold-machine check."""
        recorded = _head(self.root)
        self._write_all_modes(recorded)
        new_sha = self._commit_file(
            "scripts/some_machinery.py", message="fix(scripts): touch machinery")

        findings = check_invariants.check_cold1(self.root)
        self.assertTrue(findings, "a machinery change after the recorded run must fail")
        joined = " ".join(findings)
        self.assertIn("COLD-1 (RQ-8)", joined)
        self.assertIn(recorded[:8], joined)
        self.assertIn("cold_machine_check.py", joined)
        self.assertIn(new_sha[:7], joined)

        # Watched it fail; now re-run the cold check (simulated by
        # updating the record to the new HEAD) and watch it pass.
        self._write_all_modes(new_sha)
        self.assertEqual(check_invariants.check_cold1(self.root), [])

    def test_planted_test_doc_changes_do_not_make_cold1_stale(self):
        """R-TEST-4: tests, markdown and toolchain docs ship nothing."""
        recorded = _head(self.root)
        self._write_all_modes(recorded)
        self._commit_file("scripts/tests/test_x.py", message="test only")
        self._commit_file("scripts/notes.md", message="md only")
        self._commit_file("modules/toolchain/docs/plan.html", message="docs")
        self._commit_file("modules/toolchain/adas_build_tools/tests/t.py",
                          message="nested tests")
        self.assertEqual(check_invariants.check_cold1(self.root), [])

    def test_planted_a_gate_check_change_does_not_make_cold1_stale(self):
        """R-TEST-4: scripts/check_invariants.py is the gate itself; it ships nothing."""
        recorded = _head(self.root)
        self._write_all_modes(recorded)
        self._commit_file("scripts/check_invariants.py", message="gate only")
        self.assertEqual(check_invariants.check_cold1(self.root), [])

    def test_planted_setup_py_change_still_makes_cold1_stale(self):
        """The other direction of the exclusion: real machinery stays watched."""
        recorded = _head(self.root)
        self._write_all_modes(recorded)
        self._commit_file("scripts/tests/test_x.py", message="test only")
        self._commit_file("scripts/setup.py", message="machinery")
        findings = check_invariants.check_cold1(self.root)
        self.assertTrue(findings)
        self.assertIn("machinery", " ".join(findings))
        self.assertNotIn("test only", " ".join(findings))

    def test_planted_build_tools_pin_change_after_record_is_caught(self):
        """A conf/build_tools.version pin bump is also machinery, even
        though its path is outside scripts/ and adas_build_tools/."""
        self._commit_file("modules/df/conf/build_tools.version", "1.0.22\n",
                          message="seed pin")
        recorded = _head(self.root)
        self._write_all_modes(recorded)
        self._commit_file("modules/df/conf/build_tools.version", "1.0.23\n",
                          message="bump(df): build_tools pin")
        findings = check_invariants.check_cold1(self.root)
        self.assertTrue(findings, "a build_tools.version pin bump must be caught")

    def test_planted_every_mode_is_checked_not_only_the_newest(self):
        """NS-45: this test used to assert the OPPOSITE -- that a fresh
        with-server entry made a stale no-server entry invisible. That is
        the defect: re-recording one mode cleared the check for both."""
        old_sha = _head(self.root)
        new_sha = self._commit_file("scripts/some_machinery.py", message="machinery")
        self._write_record("no-server", old_sha, timestamp="2026-09-25T00:00:00Z")
        self._write_record("with-server", new_sha, timestamp="2026-09-25T01:00:00Z")
        joined = " ".join(check_invariants.check_cold1(self.root))
        self.assertIn("`no-server`", joined, "the stale older mode must be named")
        self.assertIn(old_sha[:8], joined)
        self.assertNotIn("`with-server` cold-machine check", joined)
        self._write_record("no-server", new_sha, timestamp="2026-09-25T02:00:00Z")
        self.assertEqual(check_invariants.check_cold1(self.root), [])

    def test_planted_a_mode_with_no_record_is_named(self):
        """NS-45: a record file with only one mode is not proof of the other."""
        self._write_record("no-server", _head(self.root))
        joined = " ".join(check_invariants.check_cold1(self.root))
        self.assertIn("no `with-server` cold-run record", joined)
        self.assertIn("--with-server", joined)

    def test_planted_committing_the_record_itself_never_invalidates_it(self):
        """The exact self-referential trap the module docstring calls out:
        `scripts` is a directory pathspec, so a commit that touches ONLY
        scripts/cold_run_record.json (i.e. committing the record itself,
        the real workflow after a passing run) must not register as a
        machinery change -- or writing the receipt would immediately
        invalidate it."""
        recorded = _head(self.root)
        self._write_all_modes(recorded)
        # Commit the record file itself, as the real workflow does.
        _git(self.root, "add", "scripts/cold_run_record.json")
        _git(self.root, "commit", "-q", "-m", "chore: record cold-run pass")
        self.assertEqual(check_invariants.check_cold1(self.root), [],
                         "committing the record itself must never make COLD-1 fail")

    def test_planted_record_without_the_with_all_step_is_caught(self):
        """NS-55: a record that covers HEAD but never ran --with-all (every
        record before NS-55) is not proof of the flag that broke."""
        head = _head(self.root)
        for with_all_ok in (None, False):
            self._write_all_modes(head, with_all_ok=with_all_ok)
            joined = " ".join(check_invariants.check_cold1(self.root))
            self.assertIn("NS-55", joined, f"with_all_ok={with_all_ok}")
            self.assertIn("--with-all", joined)
        self._write_all_modes(head, with_all_ok=True)
        self.assertEqual(check_invariants.check_cold1(self.root), [])

    def test_planted_a_record_without_the_lock_steps_is_caught(self):
        """NS-68: a record from before the lockfile proof does not clear COLD-1."""
        head = _head(self.root)
        for lock_steps_ok in (None, False):
            self._write_all_modes(head, lock_steps_ok=lock_steps_ok)
            joined = " ".join(check_invariants.check_cold1(self.root))
            self.assertIn("NS-68", joined, f"lock_steps_ok={lock_steps_ok}")
            for name in check_invariants.COLD1_LOCK_STEPS:
                self.assertIn(name, joined)
        self._write_all_modes(head, lock_steps_ok=True)
        self.assertEqual(check_invariants.check_cold1(self.root), [])

    def test_cold_check_writes_the_lock_step_names_cold1_reads(self):
        src = (Path(check_invariants.__file__).parent / "cold_machine_check.py").read_text(
            encoding="utf-8")
        self.assertIn("COLD1_LOCK_MADE_STEP", src)
        self.assertIn("COLD1_LOCK_REUSED_STEP", src)
        self.assertIn("COLD1_LOCK_REFUSED_STEP", src)

    def test_cold_check_writes_the_step_name_cold1_reads(self):
        """The name is defined once; the writer must use it verbatim."""
        src = (Path(check_invariants.__file__).parent / "cold_machine_check.py").read_text(
            encoding="utf-8")
        self.assertIn("from check_invariants import COLD1_WITH_ALL_STEP", src)
        self.assertIn("Step(WITH_ALL_STEP_NAME)", src)

    def test_invalid_json_is_a_named_finding_not_a_crash(self):
        record_path = self.root / "scripts" / "cold_run_record.json"
        record_path.parent.mkdir(parents=True, exist_ok=True)
        record_path.write_text("{not valid json", encoding="utf-8")
        findings = check_invariants.check_cold1(self.root)
        self.assertTrue(findings)
        self.assertIn("COLD-1 (RQ-8)", " ".join(findings))


if __name__ == "__main__":
    unittest.main()
