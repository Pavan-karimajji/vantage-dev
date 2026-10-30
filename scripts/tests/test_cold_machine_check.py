# Copyright (c) LT EPS. All Rights Reserved.
# Proprietary and Confidential.
# @author Pavan Karimajji

"""
scripts/tests/test_cold_machine_check.py

RD-14 (remove_develop_mode_plan.md): mocked, fast tests for scripts/
cold_machine_check.py. No real conan_server, subprocess, filesystem-under-
%USERPROFILE% or network call is ever made here - every boundary
(subprocess.run/Popen, conan_server_guard._port_in_use,
adas_setup._port_reachable/_find_conan_server_exe, and every path this
script writes to) is mocked or redirected into a tempfile.TemporaryDirectory,
matching this repo's own scripts/tests convention.

Run:
    py -m unittest discover -s scripts/tests
    (from the superproject root)
"""
import io
import contextlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cold_machine_check as cmc  # noqa: E402

_REAL_OS_NAME = os.name
_REAL_SOLO_DF_LIBRARY = cmc.solo_df_library

# vantage-dev: these tests assert 1v-superproject's own module set (they need df).
_DF_DECLARED = "modules/df" in ((Path(__file__).resolve().parents[2] / ".gitmodules")
                                .read_text(encoding="utf-8"))
_DF_REASON = "needs modules/df (the cold check builds df's DLL); df is not part of this superproject"


def _solo_df_library_under_real_os(solo_cmd):
    """run() is exercised with os.name faked to "nt" so its Windows-only guard
    passes, but pathlib dispatches WindowsPath/PosixPath off the REAL os.name,
    so the real df-library lookup cannot build a Path while it is faked (7
    errors under WSL). Run that one lookup with the real value restored --
    the naming it proves stays real on every platform."""
    with mock.patch.object(os, "name", _REAL_OS_NAME):
        return _REAL_SOLO_DF_LIBRARY(solo_cmd)


def _fake_completed(returncode=0, stdout="", stderr=""):
    result = mock.Mock()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result



# PT-12/PT-26: no test in this module may move, delete or read the real
# checkout's replay venv, or write a planted component to disk -- the planting
# seam is patched and REPLAY_VENV_DIR points at a path that never exists.
_REAL_PLANT_ABSENT_PYTHON = cmc._plant_absent_python_component
_NO_REPLAY_DIR = tempfile.mkdtemp(prefix="cold_test_no_replay_")
# NS-68: nor may any test touch the developer's REAL lock folders (they are now
# moved aside by a real run); they point at paths that never exist, and
# _prove_locks() - which reads the real lock - is replaced by a fake that passes
# its three steps (its own tests, Ns68LockProofTests, call the saved original).
_REAL_PROVE_LOCKS = cmc._prove_locks


def _fake_prove_locks(made_step, reused_step, refused_step, solo_cmd, env, dead):
    for step in (made_step, reused_step, refused_step):
        step.ok = True


_PT12_PATCHES = [mock.patch.object(cmc, "_plant_absent_python_component"),
                 mock.patch.object(cmc, "REPLAY_VENV_DIR",
                                   Path(_NO_REPLAY_DIR) / "never" / ".venv-replay-test"),
                 mock.patch.object(cmc, "DF_LOCKS_DIR", Path(_NO_REPLAY_DIR) / "never" / "df_locks"),
                 mock.patch.object(cmc, "ROOT_LOCKS_DIR", Path(_NO_REPLAY_DIR) / "never" / "root_locks"),
                 mock.patch.object(cmc, "_prove_locks", side_effect=_fake_prove_locks)]


def setUpModule():
    for patcher in _PT12_PATCHES:
        patcher.start()


def tearDownModule():
    for patcher in _PT12_PATCHES:
        patcher.stop()


class RecordSecondsTests(unittest.TestCase):
    """R-TEST-7: per-step `seconds` and per-mode `total_seconds` are written,
    and a record without them is still read by COLD-1."""

    def test_record_carries_seconds_and_total_seconds(self):
        steps = [cmc.Step("timed"), cmc.Step("untimed")]
        for st in steps:
            st.ok = True
        steps[0].seconds = 12.345
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rec.json"
            with mock.patch.object(cmc, "COLD_RUN_RECORD_PATH", path), \
                    mock.patch.object(cmc, "ROOT", Path(tmp)), \
                    mock.patch.object(cmc, "_current_commit_sha", return_value="a" * 40):
                cmc.record_passing_run("no-server", steps, total_seconds=99.96)
            entry = json.loads(path.read_text(encoding="utf-8"))["no-server"]
        self.assertEqual(entry["total_seconds"], 100.0)
        self.assertEqual(entry["steps"][0]["seconds"], 12.3)
        self.assertNotIn("seconds", entry["steps"][1])

    def test_run_step_times_itself(self):
        step = cmc.Step("echo")
        proc = mock.Mock(returncode=0, stdout="ok", stderr="")
        with mock.patch.object(cmc.subprocess, "run", return_value=proc), \
                contextlib.redirect_stdout(io.StringIO()):
            cmc._run_step(step, ["x"], ".", {})
        self.assertIsNotNone(step.seconds)

    def test_cold1_still_accepts_a_record_without_seconds(self):
        import check_invariants
        entry = {"commit": "abc", "steps": [{"name": "s", "ok": True}]}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "scripts" / "cold_run_record.json").write_text(
                json.dumps({m: entry for m in check_invariants.COLD1_REQUIRED_MODES}),
                encoding="utf-8")
            findings = check_invariants.check_cold1(root)  # must not raise
        self.assertIsInstance(findings, list)


class NonWindowsGuardTests(unittest.TestCase):
    def test_refuses_cleanly_on_non_windows(self):
        with mock.patch.object(os, "name", "posix"), \
                mock.patch.object(cmc, "ColdMachineCheck") as check_cls, \
                contextlib.redirect_stdout(io.StringIO()) as out:
            exit_code = cmc.run()

        self.assertEqual(exit_code, 1)
        check_cls.assert_not_called()
        self.assertIn("Windows-only", out.getvalue())


class WriteServerConfPortTests(unittest.TestCase):
    """NS-21 (cache_first_no_server_plan.md, redo of CE-34):
    _write_server_conf_port() now does ONLY the port rewrite - the
    permission-line fix it used to also apply moved to setup.py
    (ensure_server_conf_permissions()/_server_conf_permission_fix()), and
    is deliberately NOT applied here any more, so the scratch server this
    script manufactures is "closer to the real one": setup.bat's own
    ensure_server_running() has to fix it for real, on every run."""

    def test_rewrites_existing_port_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            server_dir = Path(tmp)
            (server_dir / "server.conf").write_text(
                "[server]\nport: 9300\nhost_name: 127.0.0.1\n", encoding="utf-8")

            cmc._write_server_conf_port(server_dir, 9377)

            text = (server_dir / "server.conf").read_text(encoding="utf-8")
        self.assertIn("port: 9377", text)
        self.assertNotIn("port: 9300", text)

    def test_adds_port_line_when_none_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            server_dir = Path(tmp)
            (server_dir / "server.conf").write_text("[server]\n", encoding="utf-8")

            cmc._write_server_conf_port(server_dir, 9312)

            text = (server_dir / "server.conf").read_text(encoding="utf-8")
        self.assertIn("port: 9312", text)

    def test_permission_lines_are_left_untouched_on_purpose(self):
        """NS-21: a genuine `conan_server --migrate` template's commented-
        out permission rules must survive THIS function unchanged - the
        whole point of splitting it (setup.bat's own NS-21/CE-34 fix is
        what must correct them now, proven for real by
        cold_machine_check.py itself, not pre-corrected here where no
        code under test would ever see the broken state)."""
        template = (
            "[server]\nport: 9300\n\n"
            "[write_permissions]\n\n"
            "#  */*@*/*: *\n#\n"
            "[read_permissions]\n#*/*@*/*: *\n\n"
            "[users]\n#default_user: defaultpass\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            server_dir = Path(tmp)
            (server_dir / "server.conf").write_text(template, encoding="utf-8")

            cmc._write_server_conf_port(server_dir, 9310)

            text = (server_dir / "server.conf").read_text(encoding="utf-8")

        self.assertIn("port: 9310", text)
        write_section = text.split("[write_permissions]", 1)[1].split("[read_permissions]", 1)[0]
        self.assertNotIn("\n*/*@*/*: demo", write_section)  # no active line added
        self.assertIn("#  */*@*/*: *", write_section)       # still commented-out


class EnsureSectionLineTests(unittest.TestCase):
    """NS-21: cmc._ensure_section_line is now a re-export of
    adas_setup._ensure_section_line - the single shared implementation,
    never a second, driftable copy. These tests keep exercising it under
    its original name so nothing here needed to change when the
    implementation moved."""

    def test_appends_new_section_when_header_missing(self):
        text = cmc._ensure_section_line("[server]\nport: 9300\n", "users", "demo: demo")
        self.assertIn("[users]", text)
        self.assertIn("demo: demo", text)

    def test_no_duplicate_when_active_line_already_present(self):
        text = "[users]\ndemo: demo\n[read_permissions]\n*/*@*/*: *\n"
        result = cmc._ensure_section_line(text, "users", "demo: demo")
        self.assertEqual(result.count("demo: demo"), 1)

    def test_inserted_line_stays_within_its_own_section(self):
        text = "[write_permissions]\n# comment\n[read_permissions]\n*/*@*/*: *\n"
        result = cmc._ensure_section_line(text, "write_permissions", "*/*@*/*: demo")
        write_section = result.split("[write_permissions]", 1)[1].split("[read_permissions]", 1)[0]
        read_section = result.split("[read_permissions]", 1)[1]
        self.assertIn("*/*@*/*: demo", write_section)
        self.assertNotIn("*/*@*/*: demo", read_section)

    def test_is_the_same_function_object_as_setup_py(self):
        self.assertIs(cmc._ensure_section_line, cmc.adas_setup._ensure_section_line)


class RunStepExpectRefusalTests(unittest.TestCase):
    """NS-22 (cache_first_no_server_plan.md, redo of CE-35): direct unit
    coverage of _run_step_expect_refusal()'s own marker-matching logic -
    RunStepOrderingTests above mocks this function away entirely (it
    tests run()'s CONTROL FLOW), so this is the only place its internals
    are exercised without a real subprocess."""

    def _run(self, returncode, stdout="", stderr=""):
        step = cmc.Step("fake step")
        with mock.patch("subprocess.run",
                         return_value=_fake_completed(returncode, stdout, stderr)), \
                contextlib.redirect_stdout(io.StringIO()):
            ok = cmc._run_step_expect_refusal(step, ["fake", "cmd"], "cwd", {}, marker="(CE-35)")
        return ok, step

    def test_planted_violation_zero_exit_is_a_fail_even_with_the_marker_present(self):
        """PASS: a build that SUCCEEDS (exit 0) is a FAIL for this step,
        even if the marker text happens to appear in its output somehow -
        the whole point is proving the build REFUSED. FAIL: a zero exit
        treated as success just because the marker string matched."""
        ok, step = self._run(0, stdout="unrelated success output (CE-35) mentioned in passing")
        self.assertFalse(ok)
        self.assertFalse(step.ok)
        self.assertIn("succeeded", step.first_error)

    def test_nonzero_exit_without_marker_is_a_fail_naming_the_real_error(self):
        ok, step = self._run(1, stderr="ERROR: some unrelated conan failure\n")
        self.assertFalse(ok)
        self.assertIn("not with the expected", step.first_error)
        self.assertIn("some unrelated conan failure", step.first_error)

    def test_nonzero_exit_with_marker_is_a_pass(self):
        ok, step = self._run(1, stderr="ERROR: adas-mathlib resolved as Editable (CE-35)\n")
        self.assertTrue(ok)
        self.assertTrue(step.ok)


class FreePortTests(unittest.TestCase):
    def test_skips_ports_already_in_use(self):
        busy = {9310, 9311}
        with mock.patch.object(cmc.conan_server_guard, "_port_in_use",
                                side_effect=lambda port, host="127.0.0.1": port in busy):
            port = cmc._free_port()
        self.assertEqual(port, 9312)

    def test_raises_when_the_whole_range_is_busy(self):
        with mock.patch.object(cmc, "PORT_RANGE", range(9310, 9312)), \
                mock.patch.object(cmc.conan_server_guard, "_port_in_use", return_value=True):
            with self.assertRaises(SystemExit):
                cmc._free_port()


class SubprocessEnvTests(unittest.TestCase):
    """Real bug found running cold_machine_check.py --with-server for
    real, 2026-09-23: without ADAS_CONAN_SERVER_DIR forwarded, setup.bat's
    own ensure_server_running() reads its default (C:\\ws\\conan_server_
    data - THIS machine's real adas-local), not the scratch server this
    run just prepared, so a real already-running server elsewhere reports
    "[SKIP] ... already satisfied" while the scratch server.conf
    (deliberately left broken, NS-21) is never looked at."""

    def test_with_server_forwards_scratch_server_dir(self):
        check = cmc.ColdMachineCheck(with_server=True)
        check.conan_home = Path(r"C:\fake\conan_home")
        check.server_data_dir = Path(r"C:\fake\scratch\server_data")

        env = check.subprocess_env()

        self.assertEqual(env["ADAS_CONAN_SERVER_DIR"], str(check.server_data_dir))
        self.assertEqual(env["CONAN_HOME"], str(check.conan_home))

    def test_no_server_mode_never_sets_it(self):
        """PASS: the no-server default never points setup.bat at ANY
        server_data_dir (there isn't one, self.server_data_dir stays
        None) - an ambient ADAS_CONAN_SERVER_DIR from the real shell must
        not leak through either, or a real machine's own scratch runs
        could accidentally observe each other's server."""
        check = cmc.ColdMachineCheck(with_server=False)
        check.conan_home = Path(r"C:\fake\conan_home")

        with mock.patch.dict(os.environ, {"ADAS_CONAN_SERVER_DIR": r"C:\ambient\leak"}):
            env = check.subprocess_env()

        self.assertNotIn("ADAS_CONAN_SERVER_DIR", env)


class ColdMachineCheckCleanupTests(unittest.TestCase):
    """cleanup() must be safe to call on PARTIAL state - every field it
    inspects can be None/False if setup_scratch() failed partway through,
    and cleanup() is the one thing every code path (success, real failure,
    signal) must be able to call unconditionally."""

    def setUp(self):
        # NS-26: cleanup() now calls _release_lock() unconditionally -
        # patched to an isolated tempfile path so these tests never read
        # or touch the REAL ~/.adas_cold_check.lock on the machine running
        # them.
        self._lock_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._lock_tmp.cleanup)
        self._lock_patch = mock.patch.object(
            cmc, "LOCK_FIXED_PATH", Path(self._lock_tmp.name) / "cold_check.lock")
        self._lock_patch.start()
        self.addCleanup(self._lock_patch.stop)

    def test_cleanup_on_fully_uninitialised_state_does_nothing_and_does_not_raise(self):
        check = cmc.ColdMachineCheck()
        with contextlib.redirect_stdout(io.StringIO()):
            check.cleanup()  # must not raise

    def test_cleanup_restores_team_server_file_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            team_file = Path(tmp) / "team_conan_server.txt"
            original = b"http://127.0.0.1:9300\n"
            team_file.write_bytes(original)

            check = cmc.ColdMachineCheck()
            check.team_server_original_bytes = original
            team_file.write_text("http://127.0.0.1:9377\n", encoding="utf-8")

            with mock.patch.object(cmc.adas_setup, "TEAM_SERVER_FILE", team_file), \
                    contextlib.redirect_stdout(io.StringIO()):
                check.cleanup()

            self.assertEqual(team_file.read_bytes(), original)

    def test_cleanup_restores_moved_aside_venv(self):
        with tempfile.TemporaryDirectory() as tmp:
            venv_dir = Path(tmp) / ".venv-win32"
            backup_dir = Path(tmp) / ".venv-win32.cold_check_bak"
            backup_dir.mkdir()
            (backup_dir / "marker.txt").write_text("original venv", encoding="utf-8")

            check = cmc.ColdMachineCheck()
            check.moved_aside = {str(venv_dir): str(backup_dir)}

            with mock.patch.object(cmc, "DF_VENV_DIR", venv_dir), \
                    contextlib.redirect_stdout(io.StringIO()):
                check.cleanup()

            self.assertTrue(venv_dir.exists())
            self.assertFalse(backup_dir.exists())
            self.assertEqual((venv_dir / "marker.txt").read_text(encoding="utf-8"),
                              "original venv")

    def test_cleanup_removes_scratch_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp) / "scratch_root"
            scratch.mkdir()
            (scratch / "leftover.txt").write_text("x", encoding="utf-8")
            breadcrumb = Path(tmp) / "breadcrumb.json"

            check = cmc.ColdMachineCheck()
            check.scratch_root = scratch

            with mock.patch.object(cmc, "BREADCRUMB_FIXED_PATH", breadcrumb), \
                    contextlib.redirect_stdout(io.StringIO()):
                check.cleanup()

            self.assertFalse(scratch.exists())
            self.assertFalse(breadcrumb.exists())

    def test_cleanup_terminates_a_still_running_server_process(self):
        """RD-14 (2026-09-22, found live running this script for real):
        cleanup() must stop the WHOLE process tree via
        _terminate_process_tree(), never a bare proc.terminate() - a
        launched conan_server can sit behind a wrapper/launcher process,
        and Popen.terminate() on Windows only signals the one PID it
        names, orphaning the real server still bound to the scratch port.
        This test used to assert the pre-RD-14 contract directly
        (proc.terminate()/proc.wait()) and failed on every Windows run
        since - fixed to the real, current contract; the platform-
        specific mechanics of _terminate_process_tree() itself are
        already covered by TerminateProcessTreeTests below."""
        check = cmc.ColdMachineCheck()
        proc = mock.Mock()
        proc.poll.return_value = None
        proc.pid = 12345
        check.server_proc = proc

        with mock.patch.object(cmc, "_terminate_process_tree") as terminate_mock, \
                contextlib.redirect_stdout(io.StringIO()):
            check.cleanup()

        terminate_mock.assert_called_once_with(proc)


class TerminateProcessTreeTests(unittest.TestCase):
    """RD-14: the real orphaning bug found running this script for real
    (2026-09-22) - a launched conan_server can sit behind a wrapper/
    launcher process (this script's own now-dropped conan_server_guard.py
    indirection was one such wrapper), and `Popen.terminate()` on Windows
    only signals the one PID it names, orphaning the real server child
    still bound to the scratch port. On Windows, cleanup must kill the
    WHOLE process tree (`taskkill /T`), never just the top PID."""

    def test_windows_uses_taskkill_with_tree_flag(self):
        proc = mock.Mock()
        proc.pid = 4242
        proc.wait.return_value = None
        with mock.patch.object(os, "name", "nt"), \
                mock.patch.object(cmc.subprocess, "run") as run_mock:
            cmc._terminate_process_tree(proc)

        run_mock.assert_called_once()
        cmd = run_mock.call_args[0][0]
        self.assertEqual(cmd[0], "taskkill")
        self.assertIn("/T", cmd)
        self.assertIn("/F", cmd)
        self.assertIn(str(4242), cmd)
        proc.terminate.assert_not_called()

    def test_planted_violation_windows_must_not_fall_back_to_bare_terminate(self):
        """If this ever regresses to calling `proc.terminate()` directly
        on Windows (the exact shape of the real bug), a wrapped conan_
        server's child process is orphaned again - this must never
        happen on the `os.name == "nt"` branch."""
        proc = mock.Mock()
        proc.pid = 99
        with mock.patch.object(os, "name", "nt"), \
                mock.patch.object(cmc.subprocess, "run"):
            cmc._terminate_process_tree(proc)
        proc.terminate.assert_not_called()

    def test_non_windows_falls_back_to_terminate(self):
        proc = mock.Mock()
        proc.pid = 4242
        proc.wait.return_value = None
        with mock.patch.object(os, "name", "posix"), \
                mock.patch.object(cmc.subprocess, "run") as run_mock:
            cmc._terminate_process_tree(proc)

        run_mock.assert_not_called()
        proc.terminate.assert_called_once()


class RunStepOrderingTests(unittest.TestCase):
    """RD-14: the build steps only run if `setup.bat` itself passed -
    running them against a resolution that never completed would just
    repeat the same failure with a less specific message (run()'s own
    control flow).

    NS-22 (cache_first_no_server_plan.md, redo of CE-35): run() now also
    plants a stray editable, proves the aggregate build refuses it
    (steps[2]), cleans it up for real (steps[3]), then proves the SAME
    build now proceeds (steps[4]) - _plant_stray_editable()/_run_step_
    expect_refusal() are mocked here at the same seams _run_step() already
    is, for the same reason: this class tests run()'s own CONTROL FLOW,
    not those functions' internals (each has its own dedicated test
    class). Mode-agnostic (default no-server vs --with-server): both
    exercise the identical steps[0..5] control flow, only remotes_flag/
    ColdMachineCheck's own with_server differ, neither of which these
    fully-mocked tests observe."""

    def setUp(self):
        # NS-26: run() now acquires/releases a real lock file at module
        # scope - patched to an isolated tempfile path so these tests
        # never touch the REAL ~/.adas_cold_check.lock, and so a lock left
        # by one test (if a bug ever left it) can't leak into the next.
        self._lock_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._lock_tmp.cleanup)
        self._lock_patch = mock.patch.object(
            cmc, "LOCK_FIXED_PATH", Path(self._lock_tmp.name) / "cold_check.lock")
        self._lock_patch.start()
        self.addCleanup(self._lock_patch.stop)

    def test_planted_violation_build_steps_are_skipped_when_setup_bat_fails(self):
        check = mock.Mock()
        check.subprocess_env.return_value = {}
        run_calls = []

        def fake_run_step(step, cmd, cwd, env, forbidden=()):
            run_calls.append(step.name)
            step.ok = (step.name == "setup.bat" and False) or False
            return step.ok

        with mock.patch.object(os, "name", "nt"), \
                mock.patch.object(cmc, "ColdMachineCheck", return_value=check), \
                mock.patch.object(cmc, "_run_step", side_effect=fake_run_step), \
                mock.patch.object(cmc, "solo_df_library",
                                   side_effect=_solo_df_library_under_real_os), \
                mock.patch.object(cmc, "_plant_stray_editable") as plant_mock, \
                mock.patch.object(cmc, "_plant_dead_remote"), \
                mock.patch.object(cmc, "_run_step_expect_refusal") as refusal_mock, \
                mock.patch.object(cmc, "assert_machine_clean", return_value=True), \
                mock.patch.object(cmc, "record_passing_run"), \
                mock.patch.object(cmc.atexit, "register"), \
                mock.patch.object(cmc.signal, "signal"), \
                contextlib.redirect_stdout(io.StringIO()):
            exit_code = cmc.run()

        self.assertEqual(len(run_calls), 1)
        self.assertEqual(exit_code, 1)
        check.cleanup.assert_called_once()
        plant_mock.assert_not_called()
        # NS-56: the no-pin refusal runs before setup.bat, in its own home;
        # the NS-22 refusal after it never does.
        self.assertEqual(refusal_mock.call_count, 2)  # + PT-12's planted Python
        self.assertIn("NS-56", refusal_mock.call_args_list[0].args[0].name)

    def test_planted_violation_build_steps_are_skipped_when_prepare_fails(self):
        """WP-5/NS-09 (TASK 2): the same stop-here reasoning as the
        setup.bat guard above, one step later - a failed `--prepare df`
        means the build steps would just repeat the identical missing-ref
        failure with a less specific message."""
        check = mock.Mock()
        check.subprocess_env.return_value = {}
        run_calls = []

        def fake_run_step(step, cmd, cwd, env, forbidden=()):
            run_calls.append(step.name)
            step.ok = step.name.startswith("setup.bat")
            return step.ok

        with mock.patch.object(os, "name", "nt"), \
                mock.patch.object(cmc, "ColdMachineCheck", return_value=check), \
                mock.patch.object(cmc, "_run_step", side_effect=fake_run_step), \
                mock.patch.object(cmc, "solo_df_library",
                                   side_effect=_solo_df_library_under_real_os), \
                mock.patch.object(cmc, "_plant_stray_editable") as plant_mock, \
                mock.patch.object(cmc, "_plant_dead_remote"), \
                mock.patch.object(cmc, "_run_step_expect_refusal") as refusal_mock, \
                mock.patch.object(cmc, "assert_machine_clean", return_value=True), \
                mock.patch.object(cmc, "record_passing_run"), \
                mock.patch.object(cmc.atexit, "register"), \
                mock.patch.object(cmc.signal, "signal"), \
                contextlib.redirect_stdout(io.StringIO()):
            exit_code = cmc.run()

        # setup.bat, then --prepare (fails) - no build step ever attempted.
        self.assertEqual(len(run_calls), 2)
        self.assertEqual(exit_code, 1)
        check.cleanup.assert_called_once()
        plant_mock.assert_not_called()
        self.assertEqual(refusal_mock.call_count, 2)  # NS-56's, before setup.bat

    @unittest.skipUnless(_DF_DECLARED, _DF_REASON)
    def test_all_six_steps_run_and_pass_end_to_end(self):
        check = mock.Mock()
        check.subprocess_env.return_value = {}
        check.scratch_root = r"C:\fake\scratch"
        run_calls = []
        run_cmds = {}
        refusal_calls = []

        def fake_run_step(step, cmd, cwd, env, forbidden=()):
            run_calls.append(step.name)
            run_cmds[step.name] = cmd
            step.ok = True
            return True

        def fake_run_step_expect_refusal(step, cmd, cwd, env, marker, forbidden=()):
            refusal_calls.append((step.name, cmd, env, marker, forbidden))
            step.ok = True  # the refusal fired, exactly as expected
            return True

        with mock.patch.object(os, "name", "nt"), \
                mock.patch.object(cmc, "ColdMachineCheck", return_value=check), \
                mock.patch.object(cmc, "_run_step", side_effect=fake_run_step), \
                mock.patch.object(cmc, "solo_df_library",
                                   side_effect=_solo_df_library_under_real_os), \
                mock.patch.object(cmc, "_plant_stray_editable") as plant_mock, \
                mock.patch.object(cmc, "_plant_dead_remote"), \
                mock.patch.object(cmc, "_run_step_expect_refusal",
                                   side_effect=fake_run_step_expect_refusal), \
                mock.patch.object(cmc, "assert_machine_clean", return_value=True), \
                mock.patch.object(cmc, "record_passing_run"), \
                mock.patch.object(cmc.atexit, "register"), \
                mock.patch.object(cmc.signal, "signal"), \
                contextlib.redirect_stdout(io.StringIO()):
            exit_code = cmc.run()

        plant_mock.assert_called_once_with(check.scratch_root, {})
        # NS-56 (first, in its own CONAN_HOME) and NS-22.
        self.assertEqual(len(refusal_calls), 3)  # + PT-12's planted Python
        name, cmd, env, marker, forbidden = refusal_calls[0]
        self.assertIn("NS-56", name)
        self.assertIn("--with-all", cmd)
        self.assertEqual(env["CONAN_HOME"], str(check.make_no_toolchain_home.return_value))
        self.assertEqual(set(marker), {"adas-toolchain/", "setup.bat"})
        self.assertIn("Cannot resolve python_requires", forbidden)
        # setup.bat, --prepare, solo build, cleanup, retry, --with-all (NS-55)
        # - the refusal-expect steps go through _run_step_expect_refusal(),
        # never _run_step().
        self.assertEqual(len(run_calls), 8)  # + PT-12's env import and replay
        self.assertEqual(run_calls[-1], cmc.WITH_ALL_STEP_NAME)
        # The replay uses exactly the df_sil the solo build just made -- a
        # root build: never a stale component build, never ambiguous with an
        # -agg build of the same project (2026-09-29).
        solo = next(c for n, c in run_cmds.items() if n.startswith("build.py df") and
                    "--with" not in c and "--with-all" not in c)
        replay = next(c for n, c in run_cmds.items() if "replays" in n)
        dll = Path(replay[replay.index("--dll-path") + 1])
        project = solo[solo.index("-P") + 1]
        self.assertEqual(dll.parts[-6], f"build-sil-vs2026-{project}-df-pkg-solo")
        self.assertEqual(dll.parts[-5:], ("src", "platform", "df_sil", "Release", "df_sil.dll"))
        self.assertEqual(dll.parents[5], cmc.ROOT / "conan_workarea")
        self.assertEqual(exit_code, 0)
        check.cleanup.assert_called_once()

    @unittest.skipUnless(_DF_DECLARED, _DF_REASON)
    def test_planted_violation_retry_is_skipped_when_refusal_never_fires(self):
        """NS-22's own FAIL condition: if the stray editable is silently
        accepted (no refusal), the cleanup/retry steps must NOT run -
        retrying a build that never actually proved the refusal would
        hide exactly the regression this proof exists to catch."""
        check = mock.Mock()
        check.subprocess_env.return_value = {}
        check.scratch_root = r"C:\fake\scratch"
        run_calls = []

        def fake_run_step(step, cmd, cwd, env, forbidden=()):
            run_calls.append(step.name)
            step.ok = True
            return True

        def fake_run_step_expect_refusal(step, cmd, cwd, env, marker, forbidden=()):
            if "NS-56" in step.name:
                step.ok = True
                return True
            step.ok = False  # build wrongly succeeded - no refusal
            step.first_error = "expected an NS-22 refusal but the build succeeded"
            return False

        with mock.patch.object(os, "name", "nt"), \
                mock.patch.object(cmc, "ColdMachineCheck", return_value=check), \
                mock.patch.object(cmc, "_run_step", side_effect=fake_run_step), \
                mock.patch.object(cmc, "solo_df_library",
                                   side_effect=_solo_df_library_under_real_os), \
                mock.patch.object(cmc, "_plant_stray_editable"), \
                mock.patch.object(cmc, "_plant_dead_remote"), \
                mock.patch.object(cmc, "_run_step_expect_refusal",
                                   side_effect=fake_run_step_expect_refusal), \
                mock.patch.object(cmc, "assert_machine_clean", return_value=True), \
                mock.patch.object(cmc, "record_passing_run"), \
                mock.patch.object(cmc.atexit, "register"), \
                mock.patch.object(cmc.signal, "signal"), \
                contextlib.redirect_stdout(io.StringIO()):
            exit_code = cmc.run()

        # setup.bat + --prepare + solo build only - cleanup/retry never
        # attempted.
        self.assertEqual(len(run_calls), 5)  # + PT-12's env import and replay
        self.assertEqual(exit_code, 1)

    @unittest.skipUnless(_DF_DECLARED, _DF_REASON)
    def test_planting_failure_is_reported_not_crashed(self):
        """A RuntimeError from _plant_stray_editable() (e.g. `conan
        editable add` itself failed) must be caught and reported as this
        step's own failure, never an unhandled traceback that skips
        cleanup()."""
        check = mock.Mock()
        check.subprocess_env.return_value = {}
        check.scratch_root = r"C:\fake\scratch"
        run_calls = []

        def fake_run_step(step, cmd, cwd, env, forbidden=()):
            run_calls.append(step.name)
            step.ok = True
            return True

        with mock.patch.object(os, "name", "nt"), \
                mock.patch.object(cmc, "ColdMachineCheck", return_value=check), \
                mock.patch.object(cmc, "_run_step", side_effect=fake_run_step), \
                mock.patch.object(cmc, "solo_df_library",
                                   side_effect=_solo_df_library_under_real_os), \
                mock.patch.object(cmc, "_plant_stray_editable",
                                   side_effect=RuntimeError("conan editable add failed")), \
                mock.patch.object(cmc, "_plant_dead_remote"), \
                mock.patch.object(cmc, "_run_step_expect_refusal") as refusal_mock, \
                mock.patch.object(cmc, "assert_machine_clean", return_value=True), \
                mock.patch.object(cmc, "record_passing_run"), \
                mock.patch.object(cmc.atexit, "register"), \
                mock.patch.object(cmc.signal, "signal"), \
                contextlib.redirect_stdout(io.StringIO()):
            exit_code = cmc.run()

        self.assertEqual(refusal_mock.call_count, 2)  # NS-56's only
        self.assertEqual(exit_code, 1)
        check.cleanup.assert_called_once()

    def test_with_server_flag_forwarded_to_coldmachinecheck_and_remotes_on(self):
        """D6/NS-21: --with-server both constructs ColdMachineCheck(with_
        server=True) and switches every command's --remotes flag to on -
        the two must never disagree (D1a: a loopback URL alone no longer
        turns remotes on)."""
        check = mock.Mock()
        check.subprocess_env.return_value = {}
        cmds = []

        def fake_run_step(step, cmd, cwd, env, forbidden=()):
            cmds.append(cmd)
            step.ok = (step.name.startswith("setup.bat"))
            return step.ok

        with mock.patch.object(os, "name", "nt"), \
                mock.patch.object(cmc, "ColdMachineCheck") as check_cls, \
                mock.patch.object(cmc, "_run_step", side_effect=fake_run_step), \
                mock.patch.object(cmc, "solo_df_library",
                                   side_effect=_solo_df_library_under_real_os), \
                mock.patch.object(cmc, "_plant_stray_editable"), \
                mock.patch.object(cmc, "_plant_dead_remote"), \
                mock.patch.object(cmc, "_run_step_expect_refusal"), \
                mock.patch.object(cmc, "assert_machine_clean", return_value=True), \
                mock.patch.object(cmc, "record_passing_run"), \
                mock.patch.object(cmc.atexit, "register"), \
                mock.patch.object(cmc.signal, "signal"), \
                contextlib.redirect_stdout(io.StringIO()):
            check_cls.return_value = check
            cmc.run(with_server=True)

        check_cls.assert_called_once_with(with_server=True)
        self.assertIn("--remotes", cmds[0])
        self.assertEqual(cmds[0][cmds[0].index("--remotes") + 1], "on")

    def test_cleanup_still_runs_when_setup_scratch_itself_raises(self):
        """The whole point of the try/finally: even a failure BEFORE any
        step runs (e.g. no free port, conan_server not found) must still
        clean up whatever setup_scratch() managed to create."""
        check = mock.Mock()
        check.setup_scratch.side_effect = RuntimeError("no free port")

        with mock.patch.object(os, "name", "nt"), \
                mock.patch.object(cmc, "ColdMachineCheck", return_value=check), \
                mock.patch.object(cmc.atexit, "register"), \
                mock.patch.object(cmc.signal, "signal"), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError):
                cmc.run()

        check.cleanup.assert_called_once()


class RunStepForbiddenOutputTests(unittest.TestCase):
    """NS-46: _run_step(forbidden=...) fails an exit-0 step whose output
    names a forbidden string, and leaves a clean one passing."""

    def _run(self, stdout, stderr=""):
        step = cmc.Step("s")
        with mock.patch("subprocess.run", return_value=_fake_completed(0, stdout, stderr)), \
                contextlib.redirect_stdout(io.StringIO()):
            ok = cmc._run_step(step, ["x"], "cwd", {}, forbidden=("http://127.0.0.1:9310",))
        return ok, step

    def test_exit_zero_with_forbidden_text_fails(self):
        ok, step = self._run("", "Unable to connect to remote adas-local=http://127.0.0.1:9310")
        self.assertFalse(ok)
        self.assertIn("127.0.0.1:9310", step.first_error)

    def test_exit_zero_clean_passes(self):
        ok, _ = self._run("Build finished")
        self.assertTrue(ok)


class Ns46DeadRemoteTests(unittest.TestCase):
    """NS-46: the dead remote is planted only in no-server mode, before the
    first build step, and a planting failure fails that step rather than
    letting it run without the condition it exists to prove."""

    def _run(self, with_server, plant_side_effect=None):
        check = mock.Mock()
        check.subprocess_env.return_value = {}
        check.scratch_root = r"C:\fake\scratch"
        order = []

        self.forbidden_by_step = {}

        def fake_run_step(step, cmd, cwd, env, forbidden=()):
            order.append(step.name)
            self.forbidden_by_step[step.name] = tuple(forbidden)
            step.ok = True
            return True

        def fake_refusal(step, cmd, cwd, env, marker, forbidden=()):
            self.forbidden_by_step[step.name] = tuple(forbidden)
            step.ok = True
            return True

        def fake_plant(env):
            order.append("PLANT")
            if plant_side_effect:
                raise plant_side_effect
            return "http://127.0.0.1:1"

        lock_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(lock_tmp.cleanup)
        with mock.patch.object(cmc, "LOCK_FIXED_PATH", Path(lock_tmp.name) / "l.lock"), \
                mock.patch.object(os, "name", "nt"), \
                mock.patch.object(cmc, "ColdMachineCheck", return_value=check), \
                mock.patch.object(cmc, "_run_step", side_effect=fake_run_step), \
                mock.patch.object(cmc, "solo_df_library",
                                   side_effect=_solo_df_library_under_real_os), \
                mock.patch.object(cmc, "_run_step_expect_refusal", side_effect=fake_refusal), \
                mock.patch.object(cmc, "_plant_stray_editable"), \
                mock.patch.object(cmc, "_plant_dead_remote", side_effect=fake_plant), \
                mock.patch.object(cmc, "assert_machine_clean", return_value=True), \
                mock.patch.object(cmc, "record_passing_run"), \
                mock.patch.object(cmc.atexit, "register"), \
                mock.patch.object(cmc.signal, "signal"), \
                contextlib.redirect_stdout(io.StringIO()):
            code = cmc.run(with_server=with_server)
        return code, order

    @unittest.skipUnless(_DF_DECLARED, _DF_REASON)
    def test_no_server_plants_before_the_first_build(self):
        code, order = self._run(with_server=False)
        self.assertEqual(code, 0)
        self.assertEqual(order.index("PLANT"), 3, order)  # after setup.bat, --prepare

    @unittest.skipUnless(_DF_DECLARED, _DF_REASON)
    def test_every_later_build_step_forbids_the_dead_url(self):
        """NS-46: the dead remote's URL appearing in any build step's output
        fails that step, even at exit 0 - the non-fatal login this exposed."""
        self._run(with_server=False)
        for name, forbidden in self.forbidden_by_step.items():
            if name.startswith("build.py") and "NS-56" not in name:
                self.assertEqual(forbidden, ("http://127.0.0.1:1",), name)

    @unittest.skipUnless(_DF_DECLARED, _DF_REASON)
    def test_with_server_does_not_plant(self):
        _, order = self._run(with_server=True)
        self.assertNotIn("PLANT", order)

    def test_planting_failure_fails_the_build_step_not_skips_the_proof(self):
        code, order = self._run(with_server=False,
                                plant_side_effect=RuntimeError("remote add failed"))
        self.assertEqual(code, 1)
        self.assertNotIn("build.py df -t sil -p vs2026 -P base", order)


class Ns25BreadcrumbTests(unittest.TestCase):
    """NS-25 (cache_first_no_server_plan.md): the breadcrumb is written
    incrementally, at a fixed path OUTSIDE scratch_root, on every
    mutation - never only at the end, since the whole point is surviving
    a process that never reaches its own end."""

    def test_write_breadcrumb_writes_fixed_and_scratch_copies(self):
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp) / "scratch_root"
            scratch.mkdir()
            fixed = Path(tmp) / "fixed_breadcrumb.json"

            check = cmc.ColdMachineCheck(with_server=True)
            check.scratch_root = scratch
            check.port = 9345

            with mock.patch.object(cmc, "BREADCRUMB_FIXED_PATH", fixed), \
                    mock.patch.object(cmc.adas_setup, "TEAM_SERVER_FILE",
                                       Path(tmp) / "team_conan_server.txt"):
                check._write_breadcrumb()

            scratch_copy = scratch / cmc.BREADCRUMB_FILENAME
            self.assertTrue(fixed.exists())
            self.assertTrue(scratch_copy.exists())
            data = json.loads(fixed.read_text(encoding="utf-8"))
            self.assertEqual(data["scratch_root"], str(scratch))
            self.assertEqual(data["port"], 9345)
            self.assertTrue(data["with_server"])
            self.assertEqual(data, json.loads(scratch_copy.read_text(encoding="utf-8")))

    def test_write_breadcrumb_before_scratch_root_exists_writes_fixed_copy_only(self):
        """A crash between _scratch_root() being computed and .mkdir()
        completing must still leave a breadcrumb somewhere findable -
        the fixed path never depends on scratch_root existing."""
        with tempfile.TemporaryDirectory() as tmp:
            fixed = Path(tmp) / "fixed_breadcrumb.json"
            check = cmc.ColdMachineCheck()

            with mock.patch.object(cmc, "BREADCRUMB_FIXED_PATH", fixed):
                check._write_breadcrumb()

            self.assertTrue(fixed.exists())
            self.assertIsNone(json.loads(fixed.read_text(encoding="utf-8"))["scratch_root"])


class Ns25CleanupIdempotencyTests(unittest.TestCase):
    """NS-25: cleanup() must be safe to call more than once - atexit, the
    signal handlers, and the normal `finally` can all reach it on the
    same instance. The pre-NS-25 shape of this code crashed on the
    second call: venv_moved_aside stayed True after the first restore,
    so a second call deleted the just-restored real venv and then tried
    to rename a backup path that no longer existed."""

    def test_second_cleanup_call_is_a_true_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            venv_dir = Path(tmp) / ".venv-win32"
            backup_dir = Path(tmp) / ".venv-win32.cold_check_bak"
            backup_dir.mkdir()
            (backup_dir / "marker.txt").write_text("original venv", encoding="utf-8")

            team_file = Path(tmp) / "team_conan_server.txt"
            original_bytes = b"http://127.0.0.1:9300\n"
            team_file.write_bytes(original_bytes)

            scratch = Path(tmp) / "scratch_root"
            scratch.mkdir()
            fixed_breadcrumb = Path(tmp) / "fixed_breadcrumb.json"
            fixed_breadcrumb.write_text("{}", encoding="utf-8")

            check = cmc.ColdMachineCheck()
            check.scratch_root = scratch
            check.moved_aside = {str(venv_dir): str(backup_dir)}
            check.team_server_original_bytes = original_bytes
            team_file.write_text("http://127.0.0.1:9377\n", encoding="utf-8")  # mutated

            with mock.patch.object(cmc, "DF_VENV_DIR", venv_dir), \
                    mock.patch.object(cmc.adas_setup, "TEAM_SERVER_FILE", team_file), \
                    mock.patch.object(cmc, "BREADCRUMB_FIXED_PATH", fixed_breadcrumb), \
                    mock.patch.object(cmc, "LOCK_FIXED_PATH", Path(tmp) / "cold_check.lock"), \
                    contextlib.redirect_stdout(io.StringIO()):
                check.cleanup()
                check.cleanup()  # must not raise, must not re-mutate anything

            self.assertTrue(venv_dir.exists())
            self.assertFalse(backup_dir.exists())
            self.assertEqual((venv_dir / "marker.txt").read_text(encoding="utf-8"),
                              "original venv")
            self.assertEqual(team_file.read_bytes(), original_bytes)
            self.assertFalse(fixed_breadcrumb.exists())

    def test_second_cleanup_call_prints_noop_message(self):
        check = cmc.ColdMachineCheck()
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(cmc, "LOCK_FIXED_PATH", Path(tmp) / "cold_check.lock"):
            with contextlib.redirect_stdout(io.StringIO()):
                check.cleanup()
            with contextlib.redirect_stdout(io.StringIO()) as out:
                check.cleanup()
        self.assertIn("already ran", out.getvalue())


class Ns25CleanupOnlyTests(unittest.TestCase):
    """NS-25's actual planted test: kill the run mid-way (no finally, no
    atexit, no signal handler - the exact shape of the real incident this
    row closes), then prove `--cleanup-only`, running as a completely
    FRESH process with no memory of the dead one, finishes the job purely
    from the breadcrumb + the files it points at on disk."""

    def test_no_breadcrumb_is_a_clean_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixed = Path(tmp) / "does_not_exist.json"
            lock = Path(tmp) / "does_not_exist.lock"
            with mock.patch.object(os, "name", "nt"), \
                    mock.patch.object(cmc, "BREADCRUMB_FIXED_PATH", fixed), \
                    mock.patch.object(cmc, "LOCK_FIXED_PATH", lock), \
                    contextlib.redirect_stdout(io.StringIO()):
                exit_code = cmc.run_cleanup_only()
            self.assertEqual(exit_code, 0)

    def test_stale_lock_is_cleared_even_with_no_breadcrumb(self):
        """NS-26: the narrow window between _acquire_lock() succeeding and
        setup_scratch() writing its first breadcrumb - a lock file can
        exist with no breadcrumb at all if the process dies in that
        window. --cleanup-only must still clear it."""
        with tempfile.TemporaryDirectory() as tmp:
            fixed = Path(tmp) / "does_not_exist.json"
            lock = Path(tmp) / "stale.lock"
            lock.write_text('{"pid": 99999, "scratch_root": null}\n', encoding="utf-8")
            with mock.patch.object(os, "name", "nt"), \
                    mock.patch.object(cmc, "BREADCRUMB_FIXED_PATH", fixed), \
                    mock.patch.object(cmc, "LOCK_FIXED_PATH", lock), \
                    contextlib.redirect_stdout(io.StringIO()) as out:
                exit_code = cmc.run_cleanup_only()
            self.assertEqual(exit_code, 0)
            self.assertFalse(lock.exists())
            self.assertIn("99999", out.getvalue())

    def test_refuses_cleanly_on_non_windows(self):
        with mock.patch.object(os, "name", "posix"), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            exit_code = cmc.run_cleanup_only()
        self.assertEqual(exit_code, 1)
        self.assertIn("Windows-only", out.getvalue())

    def test_planted_mid_run_death_is_fully_restored_by_cleanup_only(self):
        """The mutation-check: simulate the process dying between two
        mutations (venv moved aside, team server file rewritten,
        breadcrumb written after each - but cleanup() itself NEVER runs,
        exactly like a SIGKILL or a crashed machine). A fresh
        ColdMachineCheck-free call to run_cleanup_only() must restore
        both mutations, remove the breadcrumb, and report the machine
        clean - using only what's on disk, never this test's own `check`
        object."""
        with tempfile.TemporaryDirectory() as tmp:
            venv_dir = Path(tmp) / ".venv-win32"
            venv_dir.mkdir()
            (venv_dir / "marker.txt").write_text("pre-existing real venv", encoding="utf-8")

            team_file = Path(tmp) / "team_conan_server.txt"
            original_bytes = b"http://127.0.0.1:9300\n"
            team_file.write_bytes(original_bytes)

            fixed_breadcrumb = Path(tmp) / "fixed_breadcrumb.json"

            with mock.patch.object(cmc, "DF_VENV_DIR", venv_dir), \
                    mock.patch.object(cmc.adas_setup, "TEAM_SERVER_FILE", team_file), \
                    mock.patch.object(cmc, "BREADCRUMB_FIXED_PATH", fixed_breadcrumb), \
                    mock.patch.object(cmc, "LOCK_FIXED_PATH", Path(tmp) / "cold_check.lock"), \
                    contextlib.redirect_stdout(io.StringIO()):
                # --- the dying process's own partial work, mirroring
                # setup_scratch()'s real mutation order - no cleanup(),
                # no finally, no atexit: the process is simply gone after
                # this point. ---
                dying = cmc.ColdMachineCheck(with_server=True)
                dying.scratch_root = Path(tmp) / "scratch_root"
                dying.scratch_root.mkdir()
                dying._write_breadcrumb()

                dying.team_server_original_bytes = team_file.read_bytes()
                dying.team_server_backup_file = (
                    dying.scratch_root / "team_conan_server.txt.orig")
                dying.team_server_backup_file.write_bytes(dying.team_server_original_bytes)
                team_file.write_text("http://127.0.0.1:9377\n", encoding="utf-8")
                dying._write_breadcrumb()

                dying._move_df_venv_aside()  # renames venv_dir aside, writes breadcrumb

                # sanity: the simulated crash really did leave a mess
                self.assertFalse(venv_dir.exists())
                self.assertNotEqual(team_file.read_bytes(), original_bytes)
                self.assertTrue(fixed_breadcrumb.exists())

                # --- a later, completely independent process ---
                # Calls _cleanup_only_impl() directly (the OS guard in
                # run_cleanup_only() is covered separately by
                # test_refuses_cleanly_on_non_windows) - Path() dispatches
                # WindowsPath/PosixPath off the REAL os.name, so faking it
                # to "nt" here would break every Path(...) call below on a
                # non-Windows test runner. assert_machine_clean()'s
                # git-diff check assumes TEAM_SERVER_FILE lives inside
                # this repo's ROOT (always true for real usage) - mocked
                # to a tempdir path here, so the git-diff subprocess call
                # itself is stubbed out rather than asserting anything
                # about this fake path.
                with mock.patch.object(cmc.adas_setup, "_port_reachable",
                                        return_value=False), \
                        mock.patch.object(cmc.subprocess, "run",
                                           return_value=_fake_completed(returncode=0)):
                    exit_code = cmc._cleanup_only_impl()

            self.assertEqual(exit_code, 0)
            self.assertTrue(venv_dir.exists())
            self.assertEqual((venv_dir / "marker.txt").read_text(encoding="utf-8"),
                              "pre-existing real venv")
            self.assertEqual(team_file.read_bytes(), original_bytes)
            self.assertFalse(fixed_breadcrumb.exists())


class Ns26ConcurrencyLockTests(unittest.TestCase):
    """NS-26 (cache_first_no_server_plan.md, WP-7, TASK 3): two concurrent
    cold_machine_check.py runs used to share BREADCRUMB_FIXED_PATH and
    every fixed backup path with no barrier at all - one run's cleanup()
    could restore over a still-in-progress sibling's own mutation."""

    def setUp(self):
        self._lock_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._lock_tmp.cleanup)
        self.lock_path = Path(self._lock_tmp.name) / "cold_check.lock"

    def test_acquire_writes_pid_when_free(self):
        with mock.patch.object(cmc, "LOCK_FIXED_PATH", self.lock_path):
            cmc._acquire_lock()
        data = json.loads(self.lock_path.read_text(encoding="utf-8"))
        self.assertEqual(data["pid"], os.getpid())
        self.assertIsNone(data["scratch_root"])

    def test_planted_violation_second_acquire_raises_naming_owner(self):
        """PASS: a second _acquire_lock() while the first is still held
        raises ColdCheckLocked naming the owning pid/scratch root. FAIL
        (the real NS-26 bug): a second run silently proceeds and creates
        its own scratch state alongside the first."""
        self.lock_path.write_text(
            '{"pid": 4242, "scratch_root": "C:\\\\fake\\\\scratch"}\n', encoding="utf-8")
        with mock.patch.object(cmc, "LOCK_FIXED_PATH", self.lock_path):
            with self.assertRaises(cmc.ColdCheckLocked) as ctx:
                cmc._acquire_lock()
        self.assertEqual(ctx.exception.owner_pid, 4242)
        self.assertEqual(ctx.exception.owner_scratch_root, "C:\\fake\\scratch")
        # PASS: the lock file itself is untouched by the failed second
        # acquire (never overwritten with the second process's own pid).
        data = json.loads(self.lock_path.read_text(encoding="utf-8"))
        self.assertEqual(data["pid"], 4242)

    def test_update_scratch_root_fills_it_in_once_known(self):
        with mock.patch.object(cmc, "LOCK_FIXED_PATH", self.lock_path):
            cmc._acquire_lock()
            cmc._update_lock_scratch_root(r"C:\fake\scratch_root_123")
            data = json.loads(self.lock_path.read_text(encoding="utf-8"))
        self.assertEqual(data["scratch_root"], r"C:\fake\scratch_root_123")
        self.assertEqual(data["pid"], os.getpid())

    def test_update_scratch_root_never_clobbers_a_different_owner(self):
        """Defensive-only path - should be unreachable in practice, since
        only the process that just acquired the lock ever calls this."""
        self.lock_path.write_text(
            '{"pid": 9999, "scratch_root": null}\n', encoding="utf-8")
        with mock.patch.object(cmc, "LOCK_FIXED_PATH", self.lock_path):
            cmc._update_lock_scratch_root(r"C:\should\not\land")
        data = json.loads(self.lock_path.read_text(encoding="utf-8"))
        self.assertIsNone(data["scratch_root"])

    def test_release_removes_own_lock(self):
        with mock.patch.object(cmc, "LOCK_FIXED_PATH", self.lock_path):
            cmc._acquire_lock()
            cmc._release_lock()
        self.assertFalse(self.lock_path.exists())

    def test_release_never_clobbers_a_different_owners_lock(self):
        """PASS: a lock file naming a DIFFERENT pid is left untouched -
        this process never acquired it, so it must never remove it. FAIL:
        _release_lock() removes any lock file it finds regardless of pid,
        which would let one run's cleanup() silently release a sibling's
        still-active lock."""
        self.lock_path.write_text(
            '{"pid": 424242, "scratch_root": null}\n', encoding="utf-8")
        with mock.patch.object(cmc, "LOCK_FIXED_PATH", self.lock_path):
            cmc._release_lock()
        self.assertTrue(self.lock_path.exists())

    def test_run_refuses_when_a_lock_is_already_held(self):
        """The end-to-end planted violation: run() itself, with a lock
        already present, must refuse before ever constructing a
        ColdMachineCheck (no scratch state created, no cleanup to run)."""
        self.lock_path.write_text(
            '{"pid": 1234, "scratch_root": "C:\\\\fake\\\\scratch"}\n', encoding="utf-8")
        with mock.patch.object(os, "name", "nt"), \
                mock.patch.object(cmc, "LOCK_FIXED_PATH", self.lock_path), \
                mock.patch.object(cmc, "ColdMachineCheck") as check_cls, \
                contextlib.redirect_stdout(io.StringIO()) as out:
            exit_code = cmc.run()
        self.assertEqual(exit_code, 1)
        check_cls.assert_not_called()
        self.assertIn("1234", out.getvalue())
        self.assertIn("C:\\fake\\scratch", out.getvalue())
        # PASS: the pre-existing lock (a different, still-running owner)
        # is left in place, not silently cleared by the refused run.
        self.assertTrue(self.lock_path.exists())

    @unittest.skipUnless(_DF_DECLARED, _DF_REASON)
    def test_run_acquires_and_releases_the_lock_end_to_end(self):
        """A full, successfully-mocked run() acquires the lock at the
        start and releases it (via cleanup()) at the end - the lock file
        must not still be present once run() returns."""
        check = mock.Mock()
        check.subprocess_env.return_value = {}
        check.scratch_root = None

        def fake_setup_scratch():
            check.scratch_root = r"C:\fake\scratch"

        check.setup_scratch.side_effect = fake_setup_scratch

        def fake_run_step(step, cmd, cwd, env, forbidden=()):
            step.ok = True
            return True

        with mock.patch.object(os, "name", "nt"), \
                mock.patch.object(cmc, "LOCK_FIXED_PATH", self.lock_path), \
                mock.patch.object(cmc, "ColdMachineCheck", return_value=check), \
                mock.patch.object(cmc, "_run_step", side_effect=fake_run_step), \
                mock.patch.object(cmc, "solo_df_library",
                                   side_effect=_solo_df_library_under_real_os), \
                mock.patch.object(cmc, "_plant_stray_editable"), \
                mock.patch.object(cmc, "_plant_dead_remote"), \
                mock.patch.object(cmc, "_run_step_expect_refusal",
                                   side_effect=lambda step, cmd, cwd, env, marker, forbidden=(): (
                                       setattr(step, "ok", True) or True)), \
                mock.patch.object(cmc, "assert_machine_clean", return_value=True), \
                mock.patch.object(cmc, "record_passing_run"), \
                mock.patch.object(cmc.atexit, "register"), \
                mock.patch.object(cmc.signal, "signal"), \
                contextlib.redirect_stdout(io.StringIO()):
            cmc.run()

        # cleanup() was mocked away on `check` here (it's a Mock, not a
        # real ColdMachineCheck), so this test asserts run()'s own lock
        # acquisition landed - real release-on-cleanup is covered by
        # test_release_removes_own_lock above and by the real
        # ColdMachineCheck.cleanup() integration in the other test
        # classes in this file.
        data = json.loads(self.lock_path.read_text(encoding="utf-8"))
        self.assertEqual(data["pid"], os.getpid())

    def test_cleanup_only_never_calls_acquire_lock(self):
        """--cleanup-only must work even while a (possibly stale) lock is
        held - it is the explicit recovery tool for exactly that case.
        Calls _cleanup_only_impl() directly, not run_cleanup_only() -
        Path() dispatches WindowsPath/PosixPath off the REAL os.name at
        construction time (see _cleanup_only_impl()'s own docstring), so
        mocking os.name to satisfy run_cleanup_only()'s OS guard would
        break every Path(...) call in this test on a non-Windows runner;
        the OS guard itself is already covered by NonWindowsGuardTests/
        test_refuses_cleanly_on_non_windows above."""
        self.lock_path.write_text(
            '{"pid": 777, "scratch_root": null}\n', encoding="utf-8")
        breadcrumb_path = Path(self._lock_tmp.name) / "breadcrumb.json"
        with mock.patch.object(cmc, "LOCK_FIXED_PATH", self.lock_path), \
                mock.patch.object(cmc, "BREADCRUMB_FIXED_PATH", breadcrumb_path), \
                mock.patch.object(cmc, "_acquire_lock") as acquire_mock, \
                contextlib.redirect_stdout(io.StringIO()) as out:
            exit_code = cmc._cleanup_only_impl()
        self.assertEqual(exit_code, 0)
        acquire_mock.assert_not_called()
        self.assertFalse(self.lock_path.exists())
        self.assertIn("777", out.getvalue())


class Pt12PlantedAbsentPythonTests(unittest.TestCase):
    """PT-12's planted violation, run for real (no mocks): the component's
    own setup refuses an env on a Python this machine lacks, with Reason /
    Fix / Run, and never a traceback. If it ever stops refusing, the cold
    step fails -- this is the same command that step runs."""

    def test_planted_component_is_refused_with_reason_fix_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            comp = _REAL_PLANT_ABSENT_PYTHON(tmp)
            proc = subprocess.run(
                [sys.executable, "-m", "adas_build_tools.setup_cli", "--python-envs-only"],
                cwd=str(comp), capture_output=True, text=True,
                env=dict(os.environ, PYTHONPATH=str(cmc.ROOT / "modules" / "toolchain")))
        out = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 1, out)
        for marker in ("Reason:", "Python 3.99", "Fix:", "Run:"):
            self.assertIn(marker, out)
        self.assertNotIn("Traceback", out)
        run = [l for l in out.splitlines() if l.strip().startswith("Run:")][0]
        self.assertNotIn("<", run)


class Pt26ReplayVenvSurvivesTests(unittest.TestCase):
    """PT-26: the developer's replay venv is moved aside (never deleted), a
    fresh one may be created in its place, and cleanup moves the original
    back; the post-cleanup assertions prove it is byte-identical. Planted: a
    cleanup that forgets the move-back fails the assertion. Temp folders
    only -- the real .venv-replay-* is never touched."""

    def _fake_venv(self, root, marker):
        (root / "Lib" / "site-packages" / "pkg").mkdir(parents=True)
        (root / "pyvenv.cfg").write_text("version = 3.12.4\n", encoding="utf-8")
        (root / "Lib" / "site-packages" / "pkg" / "__init__.py").write_text(marker, encoding="utf-8")

    def _assert_clean(self, check, tmp):
        out = io.StringIO()
        with mock.patch.object(cmc.subprocess, "run", return_value=_fake_completed(returncode=0)), \
                mock.patch.object(cmc, "BREADCRUMB_FIXED_PATH", Path(tmp) / "none.json"), \
                mock.patch.object(cmc, "LOCK_FIXED_PATH", Path(tmp) / "none.lock"), \
                contextlib.redirect_stdout(out):
            ok = cmc.assert_machine_clean(check)
        return ok, out.getvalue()

    def _run(self, forget_move_back):
        with tempfile.TemporaryDirectory() as tmp:
            df_venv = Path(tmp) / ".venv-win32"
            df_venv.mkdir()
            replay = Path(tmp) / ".venv-replay-win32"
            self._fake_venv(replay, "the developer's own")
            with mock.patch.object(cmc, "DF_VENV_DIR", df_venv), \
                    mock.patch.object(cmc, "REPLAY_VENV_DIR", replay), \
                    mock.patch.object(cmc, "BREADCRUMB_FIXED_PATH", Path(tmp) / "crumb.json"), \
                    mock.patch.object(cmc, "LOCK_FIXED_PATH", Path(tmp) / "cold.lock"), \
                    contextlib.redirect_stdout(io.StringIO()):
                check = cmc.ColdMachineCheck()
                check._move_df_venv_aside()
                self.assertFalse(replay.exists(), "moved aside, not left in place")
                self.assertTrue(replay.with_name(replay.name + ".cold_check_bak").exists())
                self._fake_venv(replay, "fresh one setup created")  # the run's own
                if forget_move_back:
                    check.moved_aside.pop(str(replay))
                check.cleanup()
                ok, text = self._assert_clean(check, tmp)
                marker = (replay / "Lib" / "site-packages" / "pkg" / "__init__.py").read_text()
        return ok, text, marker

    def test_original_is_moved_back_and_identical(self):
        ok, text, marker = self._run(forget_move_back=False)
        self.assertTrue(ok, text)
        self.assertEqual(marker, "the developer's own")
        self.assertIn("is back and identical", text)

    def test_planted_cleanup_forgetting_the_move_back_fails(self):
        ok, text, marker = self._run(forget_move_back=True)
        self.assertFalse(ok)
        self.assertEqual(marker, "fresh one setup created")
        self.assertIn("FAIL", text)
        self.assertIn(".venv-replay-win32", text)

    def test_fingerprint_sees_a_one_byte_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "v"
            self._fake_venv(root, "a")
            before = cmc.dir_fingerprint(root)
            (root / "Lib" / "site-packages" / "pkg" / "__init__.py").write_text("b")
            self.assertNotEqual(before, cmc.dir_fingerprint(root))


class Pt47NeverDeleteWhatCantBeRestoredTests(unittest.TestCase):
    """PT-47 (python_tool_envs_plan.md, WP-16): the cold test's cleanup
    must never delete a folder whose backup it cannot verify. Every case
    runs in temp dirs, never the real modules/."""

    def _write_breadcrumb(self, path, moved_aside, scratch_root=None):
        path.write_text(json.dumps({
            "version": 1, "pid": 99999, "with_server": False,
            "scratch_root": str(scratch_root) if scratch_root else None,
            "team_server_backup_file": None,
            "moved_aside": {str(k): str(v) for k, v in moved_aside.items()},
            "replay_fingerprint": None, "server_data_dir": None, "port": None,
        }, indent=2) + "\n", encoding="utf-8")

    def _cleanup_only(self, tmp, fixed, df_venv, replay_venv):
        with mock.patch.object(cmc, "DF_VENV_DIR", df_venv), \
                mock.patch.object(cmc, "REPLAY_VENV_DIR", replay_venv), \
                mock.patch.object(cmc, "BREADCRUMB_FIXED_PATH", fixed), \
                mock.patch.object(cmc, "LOCK_FIXED_PATH", Path(tmp) / "cold_check.lock"), \
                mock.patch.object(cmc.adas_setup, "_port_reachable", return_value=False), \
                mock.patch.object(cmc.subprocess, "run",
                                  return_value=_fake_completed(returncode=0)), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            code = cmc._cleanup_only_impl()
        return code, out.getvalue()

    def _venv(self, path, marker):
        path.mkdir(parents=True)
        (path / "marker.txt").write_text(marker, encoding="utf-8")
        return path

    def test_interrupted_run_backup_and_fresh_present_restores_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            df = Path(tmp) / ".venv-win32"
            backup = self._venv(Path(tmp) / ".venv-win32.cold_check_bak", "REAL")
            self._venv(df, "fresh from the cold run")
            fixed = Path(tmp) / "bc.json"
            self._write_breadcrumb(fixed, {df: backup})
            code, _ = self._cleanup_only(tmp, fixed, df, Path(tmp) / "no-replay")
            self.assertEqual(code, 0)
            self.assertEqual((df / "marker.txt").read_text(encoding="utf-8"), "REAL")
            self.assertFalse(backup.exists())
            self.assertFalse(fixed.exists())

    def test_planted_backup_missing_leaves_folder_and_deletes_nothing(self):
        """FAIL before PT-47: the folder was rmtree'd, then the rename of the
        missing backup raised - the developer's only copy was gone."""
        with tempfile.TemporaryDirectory() as tmp:
            df = self._venv(Path(tmp) / ".venv-win32", "ONLY COPY")
            backup = Path(tmp) / ".venv-win32.cold_check_bak"  # missing
            fixed = Path(tmp) / "bc.json"
            self._write_breadcrumb(fixed, {df: backup})
            code, out = self._cleanup_only(tmp, fixed, df, Path(tmp) / "no-replay")
            self.assertEqual((df / "marker.txt").read_text(encoding="utf-8"), "ONLY COPY")
            self.assertNotEqual(code, 0)
            self.assertIn("SKIPPED", out)
            for label in ("Reason:", "Fix:", "Run:"):
                self.assertIn(label, out)
            self.assertNotIn("<", out.split("Run:")[1].splitlines()[0])
            # still pending, never forgotten
            data = json.loads(fixed.read_text(encoding="utf-8"))
            self.assertEqual(data["moved_aside"], {str(df): str(backup)})

    def test_cleanup_only_twice_in_a_row_second_is_a_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            df = Path(tmp) / ".venv-win32"
            backup = self._venv(Path(tmp) / ".venv-win32.cold_check_bak", "REAL")
            self._venv(df, "fresh")
            fixed = Path(tmp) / "bc.json"
            self._write_breadcrumb(fixed, {df: backup})
            self.assertEqual(self._cleanup_only(tmp, fixed, df, Path(tmp) / "nr")[0], 0)
            listing = sorted(p.relative_to(tmp).as_posix() for p in Path(tmp).rglob("*"))
            code, out = self._cleanup_only(tmp, fixed, df, Path(tmp) / "nr")
            self.assertEqual(code, 0)
            self.assertIn("nothing to finish", out)
            self.assertEqual(
                sorted(p.relative_to(tmp).as_posix() for p in Path(tmp).rglob("*")), listing)
            self.assertEqual((df / "marker.txt").read_text(encoding="utf-8"), "REAL")

    def test_cleanup_only_twice_with_missing_backup_deletes_nothing_either_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            df = self._venv(Path(tmp) / ".venv-win32", "ONLY COPY")
            fixed = Path(tmp) / "bc.json"
            self._write_breadcrumb(fixed, {df: Path(tmp) / "gone.cold_check_bak"})
            self._cleanup_only(tmp, fixed, df, Path(tmp) / "nr")
            self._cleanup_only(tmp, fixed, df, Path(tmp) / "nr")
            self.assertEqual((df / "marker.txt").read_text(encoding="utf-8"), "ONLY COPY")

    def test_two_folders_one_backup_missing_restores_other_and_keeps_only_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            df = self._venv(Path(tmp) / ".venv-win32", "fresh df")
            df_bak = self._venv(Path(tmp) / ".venv-win32.cold_check_bak", "REAL df")
            replay = self._venv(Path(tmp) / ".venv-replay-win32", "ONLY COPY replay")
            replay_bak = Path(tmp) / ".venv-replay-win32.cold_check_bak"  # missing
            fixed = Path(tmp) / "bc.json"
            self._write_breadcrumb(fixed, {df: df_bak, replay: replay_bak})
            self._cleanup_only(tmp, fixed, df, replay)
            self.assertEqual((df / "marker.txt").read_text(encoding="utf-8"), "REAL df")
            self.assertFalse(df_bak.exists())
            self.assertEqual((replay / "marker.txt").read_text(encoding="utf-8"),
                             "ONLY COPY replay")
            data = json.loads(fixed.read_text(encoding="utf-8"))
            self.assertEqual(data["moved_aside"], {str(replay): str(replay_bak)})

    def test_old_single_venv_breadcrumb_format_is_still_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            df = Path(tmp) / ".venv-win32"
            backup = self._venv(Path(tmp) / "old.bak", "REAL")
            fixed = Path(tmp) / "bc.json"
            fixed.write_text(json.dumps({"pid": 1, "with_server": False, "scratch_root": None,
                                         "venv_moved_aside": True, "venv_dir": str(df),
                                         "venv_backup_path": str(backup)}), encoding="utf-8")
            self._cleanup_only(tmp, fixed, df, Path(tmp) / "nr")
            self.assertEqual((df / "marker.txt").read_text(encoding="utf-8"), "REAL")

    def test_planted_existing_backup_is_never_deleted_by_a_new_move_aside(self):
        """FAIL before PT-47: _move_df_venv_aside() rmtree'd an existing
        backup - possibly the only copy left by an interrupted run."""
        with tempfile.TemporaryDirectory() as tmp:
            df = self._venv(Path(tmp) / ".venv-win32", "current")
            backup = self._venv(Path(tmp) / ".venv-win32.cold_check_bak", "ONLY COPY")
            check = cmc.ColdMachineCheck()
            with mock.patch.object(cmc, "DF_VENV_DIR", df), \
                    mock.patch.object(cmc, "REPLAY_VENV_DIR", Path(tmp) / "nr"), \
                    mock.patch.object(cmc, "BREADCRUMB_FIXED_PATH", Path(tmp) / "bc.json"), \
                    contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(RuntimeError) as ctx:
                    check._move_df_venv_aside()
            self.assertIn("--cleanup-only", str(ctx.exception))
            self.assertEqual((backup / "marker.txt").read_text(encoding="utf-8"), "ONLY COPY")
            self.assertEqual((df / "marker.txt").read_text(encoding="utf-8"), "current")


if __name__ == "__main__":
    unittest.main()


class Ns68LockProofTests(unittest.TestCase):
    """NS-68 (cache_first_no_server_plan.md WP-13): _prove_locks() - the lock
    exists, the second build uses it strictly, and a planted lock naming a
    revision the cache lacks is refused - and the lock-folder bookkeeping that
    keeps a cold run from leaving pins of a deleted scratch cache in the real
    checkout."""

    REV = "a" * 32
    LOCK = ('{"version": "0.5", "requires": ["adas-interfaces/1.0.0#' + "a" * 32
            + '%1.0", "protobuf/3.21.12#' + "c" * 32 + '%1.5", "zlib/1.3.1#' + "b" * 32 + '%2.0"]}')

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.locks = Path(tmp.name) / "locks"
        self.locks.mkdir()
        self.lock = self.locks / cmc.DF_LOCK_NAME
        self.lock.write_text(self.LOCK, encoding="utf-8")
        patcher = mock.patch.object(cmc, "DF_LOCKS_DIR", self.locks)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.steps = [cmc.Step("made"), cmc.Step("reused"), cmc.Step("refused")]
        self.seen = {}

    def prove(self, run_step=None, refusal=None, dead=()):
        def default_run_step(step, cmd, cwd, env, forbidden=(), required=()):
            self.seen["reuse"] = (forbidden, required)
            step.ok = True
            return True

        def default_refusal(step, cmd, cwd, env, marker, forbidden=()):
            self.seen["planted"] = self.lock.read_text(encoding="utf-8")
            self.seen["refusal"] = (marker, forbidden)
            step.ok = True
            return True

        with mock.patch.object(cmc, "_run_step", side_effect=run_step or default_run_step), \
                mock.patch.object(cmc, "_run_step_expect_refusal",
                                  side_effect=refusal or default_refusal), \
                contextlib.redirect_stdout(io.StringIO()):
            _REAL_PROVE_LOCKS(*self.steps, ["solo"], {}, dead)
        return [step.ok for step in self.steps]

    def test_all_three_pass_and_the_lock_is_put_back_byte_for_byte(self):
        self.assertEqual(self.prove(), [True, True, True])
        self.assertEqual(self.lock.read_text(encoding="utf-8"), self.LOCK)

    def test_the_planted_lock_names_a_revision_no_cache_holds_and_only_that_pin(self):
        self.prove()
        planted = self.seen["planted"]
        # R-BUILD-7: a first-party pin is refreshed, not refused, so only a THIRD-PARTY pin is planted
        self.assertIn("protobuf/3.21.12#" + "0" * 32, planted)
        self.assertIn("adas-interfaces/1.0.0#" + "a" * 32, planted)
        self.assertIn("zlib/1.3.1#" + "b" * 32, planted)
        marker, forbidden = self.seen["refusal"]
        self.assertEqual(set(marker), {"Reason:", "Fix:", "Run:", "--update-lock"})
        self.assertIn("conan install", forbidden)

    def test_planted_a_lock_with_no_third_party_protobuf_pin_fails_the_refusal_step(self):
        self.lock.write_text('{"requires": ["adas-interfaces/1.0.0#' + "a" * 32 + '%1.0"]}', encoding="utf-8")
        result = self.prove()
        self.assertEqual(result, [True, True, False])
        self.assertIn("no third-party protobuf pin", self.steps[2].first_error)
        self.assertNotIn("planted", self.seen, "no build may run on a lock nothing was planted in")

    def test_with_remotes_on_the_refusal_is_conans_naming_the_planted_revision(self):
        with mock.patch.object(cmc, "_run_step_expect_refusal") as expect, \
                mock.patch.object(cmc, "_run_step",
                                  side_effect=lambda step, *a, **k: setattr(step, "ok", True) or True), \
                contextlib.redirect_stdout(io.StringIO()):
            _REAL_PROVE_LOCKS(*self.steps, ["solo", "--remotes", "on"], {}, ())
        marker = expect.call_args.kwargs["marker"]
        self.assertEqual(set(marker), {"not resolved", "0" * 32})
        self.assertNotIn("conan install", expect.call_args.kwargs["forbidden"])

    def test_the_second_build_must_show_lockfile_and_never_partial_or_out(self):
        self.prove(dead=("http://dead",))
        forbidden, required = self.seen["reuse"]
        self.assertIn("--lockfile ", required)
        self.assertIn("lock: using", required)
        for text in ("--lockfile-partial", "--lockfile-out", "lock created:", "http://dead"):
            self.assertIn(text, forbidden)

    def test_planted_a_second_build_that_rewrites_the_lock_fails_and_stops(self):
        def rewriting(step, cmd, cwd, env, forbidden=(), required=()):
            self.lock.write_text(self.LOCK.replace("zlib", "zlibx"), encoding="utf-8")
            step.ok = True
            return True
        result = self.prove(run_step=rewriting)
        self.assertEqual(result, [True, False, None])
        self.assertIn("rewrote the lock", self.steps[1].first_error)

    def test_planted_a_missing_lock_fails_the_first_step_and_runs_nothing_else(self):
        self.lock.unlink()
        self.assertEqual(self.prove(), [False, None, None])

    def test_planted_a_lock_that_does_not_pin_interfaces_fails_the_first_step(self):
        self.lock.write_text('{"requires": ["zlib/1.3.1#' + "b" * 32 + '%2.0"]}', encoding="utf-8")
        self.assertEqual(self.prove(), [False, None, None])

    def test_a_crash_in_the_refusal_step_still_restores_the_lock(self):
        def crashing(step, cmd, cwd, env, marker, forbidden=()):
            raise RuntimeError("boom")
        with self.assertRaises(RuntimeError):
            self.prove(refusal=crashing)
        self.assertEqual(self.lock.read_text(encoding="utf-8"), self.LOCK)

    def test_lock_folders_are_moved_aside_with_the_venvs(self):
        self.assertIn(cmc.DF_LOCKS_DIR, cmc._moved_aside_dirs())
        self.assertIn(cmc.ROOT_LOCKS_DIR, cmc._moved_aside_dirs())

    def test_a_lock_folder_created_by_the_run_is_removed_and_a_leftover_is_reported(self):
        fresh = self.locks.parent / "fresh_locks"
        check = cmc.ColdMachineCheck()
        check.remove_if_present = [str(fresh)]
        check.locks_before = {str(fresh): {}}
        fresh.mkdir()
        (fresh / "x.lock").write_text("{}", encoding="utf-8")
        with mock.patch.object(cmc, "_release_lock"), contextlib.redirect_stdout(io.StringIO()):
            check.cleanup()
        self.assertFalse(fresh.exists())
        self.assertEqual(check.remove_if_present, [])
        fresh.mkdir()
        check.remove_if_present = [str(fresh)]  # as if cleanup had not run
        buf = io.StringIO()
        with mock.patch.object(cmc, "DF_VENV_DIR", self.locks), \
                mock.patch.object(cmc, "_moved_aside_dirs", return_value=[]), \
                mock.patch.object(cmc.subprocess, "run", return_value=_fake_completed(0)), \
                contextlib.redirect_stdout(buf):
            clean = cmc.assert_machine_clean(check)
        self.assertFalse(clean)
        self.assertIn("was created by this run and is still there", buf.getvalue())

    def test_a_lock_folder_that_differs_after_cleanup_is_a_finding(self):
        check = cmc.ColdMachineCheck()
        check.locks_before = {str(self.locks): {cmc.DF_LOCK_NAME: "0" * 64}}
        buf = io.StringIO()
        with mock.patch.object(cmc, "DF_VENV_DIR", self.locks), \
                mock.patch.object(cmc, "_moved_aside_dirs", return_value=[]), \
                mock.patch.object(cmc.subprocess, "run", return_value=_fake_completed(0)), \
                contextlib.redirect_stdout(buf):
            clean = cmc.assert_machine_clean(check)
        self.assertFalse(clean)
        self.assertIn("differs after cleanup", buf.getvalue())
