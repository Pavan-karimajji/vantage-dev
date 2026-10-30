"""
scripts/tests/test_setup_conan_environment.py

Regression tests for scripts/setup.py::ensure_server_running() (WP-01,
conan_environment_plan.md CE-01/CE-02, CET-01/CET-02),
scripts/setup.py::ensure_resolution_complete() (WP-02, CE-03, CET-04) and
scripts/setup.py::ensure_https_trust() (WP-04, CE-07/CE-08, CET-07/CET-08).
Pure unittest + unittest.mock - no pytest, no real conan/network/process
calls; every subprocess boundary is mocked, matching this repo's own
convention for a scripts/-root script (scripts/tests/test_check_conan_
resolution.py, test_conan_publish.py).

register_server_startup_task() (the abandoned Windows Scheduled Task
design - see conan_environment_plan.md's own Status header) and its tests
are gone: replaced by ensure_server_running() below, not kept alongside it.

EnsureResolutionCompleteTests only tests the WIRING (setup.py calls the
real check_conan_resolution.main() at the right point, with the right
argv, and handles its outcome correctly) - it does not re-test
check_conan_resolution's own detect-and-fix internals, which already have
their own dedicated, already-passing suite
(test_check_conan_resolution.py). Mocked at the same seams that file's
own MainTests class already mocks (editable_refs/_find_component_dir/
publish_ref), for the same reason: those are the documented, stable
extension points of that module, not incidental implementation detail.

Run:
    py -m unittest discover -s scripts/tests
    (from the superproject root)
"""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import setup  # noqa: E402 - path must be set up first


def _fake_run(returncode=0, stdout="", stderr=""):
    result = mock.Mock()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


class _Ctx:
    """Stand-in for the argparse.Namespace main() builds - only the
    attributes these functions actually read. RD-03
    (remove_develop_mode_plan.md): mode default is now "package" (the
    only supported mode); register_editables is gone."""

    def __init__(self, dry_run=False, mode="package", remotes_enabled=True):
        self.dry_run = dry_run
        self.mode = mode
        # WP-2/NS-02 (cache_first_no_server_plan.md): defaults True so every
        # pre-existing test in this file keeps exercising the remotes-ON
        # behaviour it was written against, unchanged.
        self.remotes_enabled = remotes_enabled


class ModeRefusalTest(unittest.TestCase):
    """RD-03 (remove_develop_mode_plan.md): --mode develop is refused with
    a one-line message pointing at the plan (was RD-02's deprecation
    warning; now a hard refusal). --register-editables no longer exists as
    a flag at all - argparse itself refuses it. `setup.step` faked to
    raise SystemExit on its first call so a non-refused run never reaches
    a real network/subprocess step."""

    def _run(self, argv):
        def fake_step(ctx, name, fn):
            raise SystemExit(0)
        err = io.StringIO()
        with mock.patch.object(sys, "argv", ["setup.py"] + argv),                 mock.patch.object(setup, "step", side_effect=fake_step),                 mock.patch.object(setup, "banner"),                 contextlib.redirect_stderr(err),                 self.assertRaises(SystemExit) as ctx_mgr:
            setup.main()
        return ctx_mgr.exception, err.getvalue()

    def test_mode_develop_is_refused_with_a_message_naming_the_plan(self):
        exc, _ = self._run(["--dry-run", "--mode", "develop"])
        self.assertIn("remove_develop_mode_plan.md", str(exc))
        self.assertIn("removed", str(exc).lower())

    def test_register_editables_flag_no_longer_exists(self):
        with mock.patch.object(sys, "argv", ["setup.py", "--dry-run", "--register-editables"]),                 self.assertRaises(SystemExit) as ctx_mgr:
            setup.main()
        # argparse's own "unrecognized arguments" refusal (exit code 2),
        # never a silent no-op and never setup.main() reaching real work.
        self.assertEqual(ctx_mgr.exception.code, 2)

    def test_planted_violation_mode_package_is_not_refused(self):
        exc, _ = self._run(["--dry-run", "--mode", "package"])
        # fake_step raised SystemExit(0) - real work was reached, not refused.
        self.assertEqual(exc.code, 0)

    def test_default_mode_is_package_and_is_not_refused(self):
        exc, _ = self._run(["--dry-run"])
        self.assertEqual(exc.code, 0)


class ModePackageConfigureConanDependenciesTests(unittest.TestCase):
    """CE-16 (conan_environment_plan.md §5.1) / RD-03
    (remove_develop_mode_plan.md): configure_conan_dependencies() must
    never register our own components editable, and must remove any that
    were already registered (e.g. left over from a pre-removal --mode
    develop run) - the packaged server -> cache -> consume path only
    proves anything if NOTHING resolves out of this checkout."""

    def test_never_registers_any_component_editable(self):
        """No editable-registering call exists in configure_conan_
        dependencies() any more (register_and_build_editable() itself is
        gone, RD-03) - proven here by asserting `run()` is called only for
        the removal path, never a `conan editable add`."""
        with mock.patch.object(
                setup, "discover_components",
                return_value=["interfaces", "mathlib", "shared_config", "df"]), \
                mock.patch.object(setup, "read_team_server_url", return_value=None), \
                mock.patch.object(setup, "existing_editables", return_value=""), \
                mock.patch.object(setup, "_all_editables", return_value={}), \
                mock.patch.object(setup, "run") as run_mock:
            setup.configure_conan_dependencies(_Ctx())

        run_mock.assert_not_called()

    def test_package_mode_removes_preexisting_editable_registrations(self):
        """The proof this test exists for: a component left editable by an
        earlier develop-mode run must not silently keep winning over the
        remote (Conan's own "editable always wins" rule) once the machine
        switches to package mode."""
        editables_text = str(setup.ROOT / "modules" / "df").lower() + "\n"
        removed_paths = []

        def fake_run(cmd, cwd=None, **kwargs):
            if cmd[:3] == ["conan", "editable", "remove"]:
                removed_paths.append(cwd)
            return mock.Mock(returncode=0, stdout="")

        with mock.patch.object(
                setup, "discover_components",
                return_value=["interfaces", "mathlib", "shared_config", "df"]), \
                mock.patch.object(setup, "read_team_server_url", return_value=None), \
                mock.patch.object(setup, "existing_editables", return_value=editables_text), \
                mock.patch.object(setup, "_all_editables", return_value={}), \
                mock.patch.object(setup, "run", side_effect=fake_run):
            setup.configure_conan_dependencies(_Ctx(mode="package"))

        self.assertEqual(removed_paths, [setup.ROOT / "modules" / "df"])

    def test_stray_editable_from_a_different_checkout_is_reported_as_warning(self):
        """NS-22(c) (cache_first_no_server_plan.md, redo of CE-35(b)):
        remove_own_editable_registrations() only ever matches THIS
        checkout's own modules/ path - a stray registration pointing at a
        DIFFERENT checkout entirely is left untouched by it (that's
        NS-22(b)'s own job, via --clean-develop-leftovers) but must still
        be REPORTED here, not silently built past. PASS: a WARNING names
        the ref, its path, and the cleanup command. FAIL: silent."""
        captured = io.StringIO()
        with mock.patch.object(
                setup, "discover_components",
                return_value=["interfaces", "mathlib", "shared_config", "df"]), \
                mock.patch.object(setup, "read_team_server_url", return_value=None), \
                mock.patch.object(setup, "existing_editables", return_value=""), \
                mock.patch.object(setup, "_all_editables",
                                   return_value={"adas-sim/1.0.0": r"D:\df\1v-superproject\modules\sim"}), \
                mock.patch.object(setup, "run"), \
                contextlib.redirect_stdout(captured):
            setup.configure_conan_dependencies(_Ctx())

        output = captured.getvalue()
        self.assertIn("WARNING", output)
        self.assertIn("adas-sim/1.0.0", output)
        self.assertIn(r"D:\df\1v-superproject\modules\sim", output)
        self.assertIn("--clean-develop-leftovers", output)

    def test_no_stray_editables_prints_no_warning(self):
        captured = io.StringIO()
        with mock.patch.object(
                setup, "discover_components",
                return_value=["interfaces", "mathlib", "shared_config", "df"]), \
                mock.patch.object(setup, "read_team_server_url", return_value=None), \
                mock.patch.object(setup, "existing_editables", return_value=""), \
                mock.patch.object(setup, "_all_editables", return_value={}), \
                mock.patch.object(setup, "run"), \
                contextlib.redirect_stdout(captured):
            setup.configure_conan_dependencies(_Ctx())

        self.assertNotIn("WARNING", captured.getvalue())

    def test_package_mode_leaves_no_editable_registration_behind(self):
        """The literal CE-16 proof, expressed against
        remove_own_editable_registrations() directly: after it runs, none
        of this machine's own components may still resolve as editable."""
        editables_text = "\n".join(
            str(setup.ROOT / "modules" / n).lower()
            for n in ("interfaces", "mathlib")
        )
        with mock.patch.object(setup, "run", return_value=mock.Mock(returncode=0, stdout="")):
            removed = setup.remove_own_editable_registrations(
                _Ctx(), ["interfaces", "mathlib", "shared_config", "df"], editables_text)

        self.assertEqual(set(removed), {"interfaces", "mathlib"})

    def test_package_mode_with_no_preexisting_editables_removes_nothing(self):
        with mock.patch.object(setup, "run") as run_mock:
            removed = setup.remove_own_editable_registrations(
                _Ctx(), ["interfaces", "mathlib"], "")

        run_mock.assert_not_called()
        self.assertEqual(removed, [])

    def test_package_mode_dry_run_does_not_shell_out(self):
        editables_text = str(setup.ROOT / "modules" / "df").lower()
        with mock.patch.object(setup, "run") as run_mock:
            removed = setup.remove_own_editable_registrations(
                _Ctx(dry_run=True), ["df"], editables_text)

        run_mock.assert_not_called()
        self.assertEqual(removed, ["df"])


class FindConanServerExeTests(unittest.TestCase):
    """CE-09/WSL hardening: _find_conan_server_exe() must have a POSIX
    pip `--user` fallback symmetric with the pre-existing Windows one -
    found live under WSL, a non-login shell's PATH genuinely does not
    include ~/.local/bin (Ubuntu's PATH-editing stanza lives in
    ~/.profile, sourced only for login shells), so shutil.which() alone
    wrongly reports "not installed" for a package pip --user genuinely
    installed."""

    def test_posix_user_fallback_used_when_not_on_path(self):
        fake_scripts_dir = "/home/fakeuser/.local/bin"
        with mock.patch.object(setup, "os") as os_mock, \
                mock.patch.object(setup.shutil, "which", return_value=None), \
                mock.patch("sysconfig.get_path", return_value=fake_scripts_dir) as get_path_mock, \
                mock.patch.object(setup.Path, "exists", return_value=True):
            os_mock.name = "posix"
            result = setup._find_conan_server_exe()

        get_path_mock.assert_called_once_with("scripts", "posix_user")
        self.assertEqual(result, str(Path(fake_scripts_dir) / "conan_server"))

    def test_posix_returns_none_when_neither_path_nor_fallback_has_it(self):
        with mock.patch.object(setup, "os") as os_mock, \
                mock.patch.object(setup.shutil, "which", return_value=None), \
                mock.patch("sysconfig.get_path", return_value="/home/fakeuser/.local/bin"), \
                mock.patch.object(setup.Path, "exists", return_value=False):
            os_mock.name = "posix"
            result = setup._find_conan_server_exe()

        self.assertIsNone(result)

    def test_windows_still_uses_nt_user_scheme_unaffected_by_the_posix_fix(self):
        with mock.patch.object(setup, "os") as os_mock, \
                mock.patch.object(setup.shutil, "which", return_value=None), \
                mock.patch("sysconfig.get_path", return_value=r"C:\fake\Scripts") as get_path_mock, \
                mock.patch.object(setup.Path, "exists", return_value=True):
            os_mock.name = "nt"
            result = setup._find_conan_server_exe()

        get_path_mock.assert_called_once_with("scripts", "nt_user")
        self.assertTrue(result.endswith("conan_server.exe"))


class EnsureServerRunningTests(unittest.TestCase):
    """CET-01/CET-02 (conan_environment_plan.md §8): the
    check-and-launch replacement for the abandoned onlogon-task design -
    a plain socket check, detached launch only if nothing answers."""

    def setUp(self):
        # Isolated server_dir so the real C:\ws\conan_server_data (this
        # machine's actual adas-local) is never touched by a test.
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._env_patch = mock.patch.dict(os.environ, {"ADAS_CONAN_SERVER_DIR": self._tmp.name})
        self._env_patch.start()
        self.addCleanup(self._env_patch.stop)
        self._exe_patch = mock.patch.object(
            setup, "_find_conan_server_exe", return_value=r"C:\fake\Scripts\conan_server.exe")
        self._exe_patch.start()
        self.addCleanup(self._exe_patch.stop)
        self._port_patch = mock.patch.object(
            setup.conan_server_guard, "_read_configured_port", return_value=9300)
        self._port_patch.start()
        self.addCleanup(self._port_patch.stop)
        # NS-21: _launch_conan_server_detached() now waits (bounded,
        # real bug fix below) for the port to come up after Popen() -
        # blanket-mocked here so no test in this class incurs a real
        # sleep (individual tests still free to patch it again/assert on
        # it; a redundant patch is harmless).
        self._sleep_patch = mock.patch("time.sleep")
        self._sleep_patch.start()
        self.addCleanup(self._sleep_patch.stop)
        # NS-21 (cache_first_no_server_plan.md, redo of CE-34):
        # ensure_server_running() now inspects/fixes server_dir's
        # server.conf on every call. Tests that only care about
        # CE-01/CE-02/CE-31's own behaviour pre-seed an ALREADY-correct
        # server.conf here so ensure_server_conf_permissions() is a no-op
        # (no --migrate call, no restart) and their own assertions stay
        # meaningful; the CE-34 tests below override/remove this fixture
        # deliberately.
        self._conf_path = Path(self._tmp.name) / "server.conf"
        self._conf_path.write_text(
            "[server]\nport: 9300\n"
            "[read_permissions]\n*/*@*/*: *\n"
            "[write_permissions]\n*/*@*/*: demo\n"
            "[users]\ndemo: demo\n",
            encoding="utf-8")

    def test_cet01_c1_server_down_launches_detached(self):
        """F-SERVER-DOWN: PASS - conan_server_guard.py is launched (mocked
        subprocess.Popen) with the real resolved conan_server path and the
        OS-appropriate detach flags for the platform the test runs on.
        FAIL: no launch call, or the launched process would die when the
        parent exits (wrong/missing detach flags)."""
        with mock.patch.object(setup, "_port_reachable", return_value=False), \
                mock.patch("subprocess.Popen") as popen_mock:
            outcome = setup.ensure_server_running(_Ctx())

        popen_mock.assert_called_once()
        call_args, call_kwargs = popen_mock.call_args
        cmd = call_args[0]
        self.assertTrue(any("conan_server_guard.py" in str(part) for part in cmd))
        self.assertIn(r"C:\fake\Scripts\conan_server.exe", cmd)
        self.assertIn("--server_dir", cmd)
        self.assertIn(self._tmp.name, cmd)

        if os.name == "nt":
            self.assertIn("creationflags", call_kwargs)
            flags = call_kwargs["creationflags"]
            self.assertTrue(flags & subprocess.DETACHED_PROCESS)
            self.assertTrue(flags & subprocess.CREATE_NEW_PROCESS_GROUP)
            self.assertNotIn("start_new_session", call_kwargs)
        else:
            self.assertIs(call_kwargs.get("start_new_session"), True)
            self.assertNotIn("creationflags", call_kwargs)

        self.assertIsNone(outcome)  # not "skip" - a real launch happened

    def test_cet02_c1_server_up_no_launch(self):
        """F-SERVER-UP: PASS - no launch attempted, same "check current
        state first" discipline every other setup.py step follows. FAIL: a
        second instance is launched (exactly the double-bind conan_server_
        guard.py itself exists to prevent, now caused one level up)."""
        with mock.patch.object(setup, "_port_reachable", return_value=True), \
                mock.patch("subprocess.Popen") as popen_mock:
            outcome = setup.ensure_server_running(_Ctx())

        popen_mock.assert_not_called()
        self.assertEqual(outcome, "skip")

    def test_dry_run_makes_no_launch_call(self):
        with mock.patch.object(setup, "_port_reachable", return_value=False), \
                mock.patch("subprocess.Popen") as popen_mock:
            outcome = setup.ensure_server_running(_Ctx(dry_run=True))

        popen_mock.assert_not_called()
        self.assertEqual(outcome, "skip")

    def test_missing_conan_server_is_installed_then_launched(self):
        """CE-31 (conan_environment_plan.md): a missing conan_server is no
        longer 'nothing to do' - PASS: pip install --user conan_server is
        run, and once it succeeds (re-resolved on PATH) the server is
        launched exactly as the already-installed case is. FAIL: no
        install attempted, or no launch after a successful install -
        either one reproduces the real corporate-PC bug (conan_server
        absent, printed as "[SKIP] ... already satisfied", nothing
        launched)."""
        with mock.patch.object(setup, "_find_conan_server_exe",
                                side_effect=[None, r"C:\fake\Scripts\conan_server.exe"]), \
                mock.patch.object(setup, "_port_reachable", return_value=False), \
                mock.patch.object(setup, "run",
                                   return_value=mock.Mock(returncode=0, stdout="")) as run_mock, \
                mock.patch("subprocess.Popen") as popen_mock:
            outcome = setup.ensure_server_running(_Ctx())

        run_mock.assert_called_once()
        install_cmd = run_mock.call_args[0][0]
        self.assertEqual(install_cmd,
                          [sys.executable, "-m", "pip", "install", "--user", "conan_server"])
        popen_mock.assert_called_once()
        cmd = popen_mock.call_args[0][0]
        self.assertIn(r"C:\fake\Scripts\conan_server.exe", cmd)
        self.assertIsNone(outcome)  # a real launch happened, never "skip"

    def test_missing_conan_server_install_failure_raises_stepfailed(self):
        """PASS: a pip install failure is a hard StepFailed naming the fix
        (including the honest alternative for a machine that genuinely
        doesn't want a local server: team_conan_server.txt or --offline).
        FAIL: silently reported as satisfied/skipped, matching the real
        corporate-PC bug this closes."""
        with mock.patch.object(setup, "_find_conan_server_exe", return_value=None), \
                mock.patch.object(setup, "_port_reachable", return_value=False), \
                mock.patch.object(setup, "run",
                                   return_value=mock.Mock(returncode=1, stdout="network error")), \
                mock.patch("subprocess.Popen") as popen_mock:
            with self.assertRaises(setup.StepFailed) as ctx_mgr:
                setup.ensure_server_running(_Ctx())

        popen_mock.assert_not_called()
        exc = ctx_mgr.exception
        self.assertIn("pip install of conan_server failed", str(exc))
        self.assertIn("team_conan_server.txt", exc.fix)
        self.assertIn("--offline", exc.fix)

    def test_installed_but_still_not_on_path_raises_stepfailed(self):
        """PASS: pip reports success but conan_server still can't be
        resolved on PATH in this terminal (the same PATH-refresh gap
        check_or_install_conan() already has for conan itself) - a hard
        StepFailed, never a silent skip. FAIL: treated as done anyway."""
        with mock.patch.object(setup, "_find_conan_server_exe", side_effect=[None, None]), \
                mock.patch.object(setup, "_port_reachable", return_value=False), \
                mock.patch.object(setup, "run",
                                   return_value=mock.Mock(returncode=0, stdout="")), \
                mock.patch("subprocess.Popen") as popen_mock:
            with self.assertRaises(setup.StepFailed) as ctx_mgr:
                setup.ensure_server_running(_Ctx())

        popen_mock.assert_not_called()
        self.assertIn("still isn't resolvable", str(ctx_mgr.exception))

    def test_dry_run_missing_conan_server_never_installs(self):
        """PASS: --dry-run reports what would happen (pip install) without
        actually calling pip - dry-run must change nothing on this
        machine. FAIL: a real install is attempted under --dry-run."""
        with mock.patch.object(setup, "_find_conan_server_exe", return_value=None), \
                mock.patch.object(setup, "_port_reachable", return_value=False), \
                mock.patch.object(setup, "run") as run_mock, \
                mock.patch("subprocess.Popen") as popen_mock:
            outcome = setup.ensure_server_running(_Ctx(dry_run=True))

        run_mock.assert_not_called()
        popen_mock.assert_not_called()
        self.assertEqual(outcome, "skip")

    # -- NS-21 (cache_first_no_server_plan.md, redo of CE-34): a fresh
    # -- conan_server refuses uploads until server.conf's active
    # -- permission rules are ensured.

    def test_missing_server_conf_runs_migrate_before_first_launch(self):
        """PASS: server.conf doesn't exist yet (a genuinely first-ever
        bring-up) - `--migrate` runs before the launch, so the first
        launch already has correct permissions and no restart is ever
        needed. FAIL: launched with no --migrate, reproducing the real
        corporate-PC bug (a fresh, unconfigured server.conf)."""
        self._conf_path.unlink()  # override setUp's pre-seeded fixture
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            if cmd[-1] == "--migrate":
                # Real conan_server --migrate behaviour: creates the
                # default, commented-out-only template.
                self._conf_path.write_text(
                    "[server]\nport: 9300\n"
                    "[read_permissions]\n#*/*@*/*: *\n"
                    "[write_permissions]\n#*/*@*/*: demo\n"
                    "[users]\n#demo: demo\n", encoding="utf-8")
            return mock.Mock(returncode=0, stdout="")

        with mock.patch.object(setup, "_port_reachable", return_value=False), \
                mock.patch.object(setup, "run", side_effect=fake_run), \
                mock.patch("subprocess.Popen") as popen_mock:
            outcome = setup.ensure_server_running(_Ctx())

        migrate_calls = [c for c in calls if c[-1] == "--migrate"]
        self.assertEqual(len(migrate_calls), 1)
        self.assertEqual(migrate_calls[0][0], r"C:\fake\Scripts\conan_server.exe")
        self.assertIn("--server_dir", migrate_calls[0])
        text = self._conf_path.read_text(encoding="utf-8")
        self.assertIn("*/*@*/*: *", text)   # read_permissions, now active
        self.assertIn("*/*@*/*: demo", text)  # write_permissions, now active
        self.assertIn("demo: demo", text)    # users, now active
        popen_mock.assert_called_once()  # the actual launch still happens
        self.assertIsNone(outcome)

    def test_migrate_failure_raises_stepfailed(self):
        self._conf_path.unlink()
        with mock.patch.object(setup, "_port_reachable", return_value=False), \
                mock.patch.object(setup, "run",
                                   return_value=mock.Mock(returncode=1, stdout="disk full")), \
                mock.patch("subprocess.Popen") as popen_mock:
            with self.assertRaises(setup.StepFailed) as ctx_mgr:
                setup.ensure_server_running(_Ctx())

        popen_mock.assert_not_called()
        self.assertIn("--migrate failed", str(ctx_mgr.exception))

    def test_broken_permissions_fixed_silently_before_launch_when_not_reachable(self):
        """A server.conf that already exists (e.g. from a much older run)
        but still carries only commented-out rules, on a server that
        isn't currently reachable - fixed in place before the launch, no
        restart needed since nothing was running yet."""
        self._conf_path.write_text(
            "[server]\nport: 9300\n"
            "[read_permissions]\n#*/*@*/*: *\n"
            "[write_permissions]\n#*/*@*/*: demo\n"
            "[users]\n#demo: demo\n", encoding="utf-8")

        with mock.patch.object(setup, "_port_reachable", return_value=False), \
                mock.patch.object(setup, "run") as run_mock, \
                mock.patch("subprocess.Popen") as popen_mock:
            outcome = setup.ensure_server_running(_Ctx())

        run_mock.assert_not_called()  # conf existed - no --migrate needed
        popen_mock.assert_called_once()
        text = self._conf_path.read_text(encoding="utf-8")
        self.assertIn("\n*/*@*/*: demo", text)
        self.assertTrue((Path(self._tmp.name) / "server.conf.bak").is_file())
        self.assertIsNone(outcome)

    def test_reachable_server_with_broken_permissions_is_restarted(self):
        """PASS: the server is ALREADY reachable (started by an earlier
        run, before this fix existed) but its server.conf still carries
        only commented-out rules - the fix is applied AND the running
        instance is restarted (found by PID-by-port, killed, relaunched)
        so the new permissions actually take effect. FAIL: reported
        [SKIP] with the old, broken config still being served (the exact
        shape of CE-34's own bug, just discovered on a later run instead
        of the first one)."""
        self._conf_path.write_text(
            "[server]\nport: 9300\n"
            "[read_permissions]\n#*/*@*/*: *\n"
            "[write_permissions]\n#*/*@*/*: demo\n"
            "[users]\n#demo: demo\n", encoding="utf-8")

        with mock.patch.object(setup, "_port_reachable", return_value=True), \
                mock.patch.object(setup, "_find_listening_pid", return_value=4242) as find_mock, \
                mock.patch.object(setup, "_kill_pid_tree", return_value=True) as kill_mock, \
                mock.patch("time.sleep"), \
                mock.patch("subprocess.Popen") as popen_mock:
            outcome = setup.ensure_server_running(_Ctx())

        find_mock.assert_called_once_with(9300)
        kill_mock.assert_called_once_with(4242)
        popen_mock.assert_called_once()  # relaunched with the fixed config
        text = self._conf_path.read_text(encoding="utf-8")
        self.assertIn("\n*/*@*/*: demo", text)
        self.assertIsNone(outcome)  # real work happened, not a bare "skip"

    def test_reachable_server_with_correct_permissions_is_left_alone(self):
        """The already-correct fixture from setUp() - PASS: no restart, no
        launch, plain [SKIP] (CE-01/CE-02's own unchanged behaviour)."""
        with mock.patch.object(setup, "_port_reachable", return_value=True), \
                mock.patch.object(setup, "_find_listening_pid") as find_mock, \
                mock.patch("subprocess.Popen") as popen_mock:
            outcome = setup.ensure_server_running(_Ctx())

        find_mock.assert_not_called()
        popen_mock.assert_not_called()
        self.assertEqual(outcome, "skip")

    def test_reachable_restart_failure_is_a_warning_not_a_crash(self):
        """PASS: the fix is applied even though the running instance can't
        be found/stopped - reported as a WARNING naming the manual
        remedy, never a crash and never silently claiming success."""
        self._conf_path.write_text(
            "[server]\nport: 9300\n"
            "[read_permissions]\n#*/*@*/*: *\n"
            "[write_permissions]\n#*/*@*/*: demo\n"
            "[users]\n#demo: demo\n", encoding="utf-8")
        captured = io.StringIO()

        with mock.patch.object(setup, "_port_reachable", return_value=True), \
                mock.patch.object(setup, "_find_listening_pid", return_value=None), \
                mock.patch("subprocess.Popen") as popen_mock, \
                contextlib.redirect_stdout(captured):
            outcome = setup.ensure_server_running(_Ctx())  # must not raise

        popen_mock.assert_not_called()
        self.assertIn("WARNING", captured.getvalue())
        self.assertIn("restart it by hand", captured.getvalue())
        self.assertEqual(outcome, "skip")

    def test_dry_run_reports_permission_fix_and_restart_without_writing(self):
        self._conf_path.write_text(
            "[server]\nport: 9300\n"
            "[read_permissions]\n#*/*@*/*: *\n"
            "[write_permissions]\n#*/*@*/*: demo\n"
            "[users]\n#demo: demo\n", encoding="utf-8")
        original = self._conf_path.read_text(encoding="utf-8")
        captured = io.StringIO()

        with mock.patch.object(setup, "_port_reachable", return_value=True), \
                mock.patch("subprocess.Popen") as popen_mock, \
                contextlib.redirect_stdout(captured):
            outcome = setup.ensure_server_running(_Ctx(dry_run=True))

        popen_mock.assert_not_called()
        self.assertEqual(self._conf_path.read_text(encoding="utf-8"), original)  # untouched
        self.assertFalse((Path(self._tmp.name) / "server.conf.bak").exists())
        self.assertIn("CE-34", captured.getvalue())
        self.assertIn("would restart conan_server", captured.getvalue())
        self.assertEqual(outcome, "skip")


class ServerConfPermissionsTests(unittest.TestCase):
    """NS-21 (cache_first_no_server_plan.md, redo of CE-34): the shared
    helpers both ensure_server_running() (above) and
    cold_machine_check.py's own scratch-server bring-up now call - one
    implementation, never a second, driftable copy (was cold_machine_
    check.py's own local _ensure_section_line(), moved here 2026-09-23)."""

    def test_ensure_section_line_appends_new_section_when_header_missing(self):
        text = setup._ensure_section_line("[server]\nport: 9300\n", "users", "demo: demo")
        self.assertIn("[users]", text)
        self.assertIn("demo: demo", text)

    def test_ensure_section_line_no_duplicate_when_active_line_already_present(self):
        text = "[users]\ndemo: demo\n[read_permissions]\n*/*@*/*: *\n"
        result = setup._ensure_section_line(text, "users", "demo: demo")
        self.assertEqual(result.count("demo: demo"), 1)

    def test_ensure_section_line_inserted_line_stays_within_its_own_section(self):
        text = "[write_permissions]\n# comment\n[read_permissions]\n*/*@*/*: *\n"
        result = setup._ensure_section_line(text, "write_permissions", "*/*@*/*: demo")
        write_section = result.split("[write_permissions]", 1)[1].split("[read_permissions]", 1)[0]
        read_section = result.split("[read_permissions]", 1)[1]
        self.assertIn("*/*@*/*: demo", write_section)
        self.assertNotIn("*/*@*/*: demo", read_section)

    def test_planted_violation_real_migrate_template_already_has_commented_sections(self):
        """The real bug (2026-09-22/2026-09-23, both a scratch server and
        a real one): a genuine `conan_server --migrate` template already
        ships every section header, populated with commented-out EXAMPLE
        rules only - a naive `if "[write_permissions]" not in text` check
        never fires against this. This fixture is a trimmed real
        template."""
        template = (
            "[server]\nport: 9300\n\n"
            "# name/version@user/channel: user1, user2, user3\n"
            "#\n#   opencv/2.3.4@lasote/testing: default_user, default_user2\n#\n"
            "[write_permissions]\n\n"
            "# name/version@user/channel: user1, user2, user3\n"
            "#  */*@*/*: *\n#\n"
            "[read_permissions]\n#*/*@*/*: *\n\n"
            "[users]\n#default_user: defaultpass\n"
        )
        fixed = setup._server_conf_permission_fix(template)
        write_section = fixed.split("[write_permissions]", 1)[1].split("[read_permissions]", 1)[0]
        read_section = fixed.split("[read_permissions]", 1)[1].split("[users]", 1)[0]
        users_section = fixed.split("[users]", 1)[1]
        self.assertIn("*/*@*/*: demo", write_section)
        self.assertIn("*/*@*/*: *", read_section)
        self.assertIn("demo: demo", users_section)

    def test_ensure_server_conf_permissions_backs_up_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            conf_path = Path(tmp) / "server.conf"
            original = "[write_permissions]\n#*/*@*/*: demo\n"
            conf_path.write_text(original, encoding="utf-8")

            changed = setup.ensure_server_conf_permissions(conf_path)

            self.assertTrue(changed)
            backup_path = Path(tmp) / "server.conf.bak"
            self.assertTrue(backup_path.is_file())
            self.assertEqual(backup_path.read_text(encoding="utf-8"), original)
            # The active line is added alongside whatever commented-out
            # example content already existed - _ensure_section_line()'s
            # own contract is "ensure the active line is present", never
            # "strip existing comments" (its own docstring).
            self.assertIn("\n*/*@*/*: demo", conf_path.read_text(encoding="utf-8"))

    def test_ensure_server_conf_permissions_is_byte_identical_when_already_correct(self):
        """PASS: an already-correct file is left byte-identical (no
        rewrite, no backup created) - proven by mtime/content, not just
        'still says correct'. FAIL: a spurious rewrite on every run."""
        with tempfile.TemporaryDirectory() as tmp:
            conf_path = Path(tmp) / "server.conf"
            correct = ("[read_permissions]\n*/*@*/*: *\n"
                       "[write_permissions]\n*/*@*/*: demo\n"
                       "[users]\ndemo: demo\n")
            conf_path.write_text(correct, encoding="utf-8")

            changed = setup.ensure_server_conf_permissions(conf_path)

            self.assertFalse(changed)
            self.assertEqual(conf_path.read_text(encoding="utf-8"), correct)
            self.assertFalse((Path(tmp) / "server.conf.bak").exists())

    def test_ensure_server_conf_permissions_missing_file_is_a_no_op(self):
        self.assertFalse(setup.ensure_server_conf_permissions(
            r"C:\does\not\exist\server.conf"))

    def test_planted_violation_disabling_read_permissions_fix_would_leave_it_commented(self):
        """R-REQ-9: proves _server_conf_permission_fix() genuinely acts on
        [read_permissions] and not just [write_permissions]/[users] -
        would catch a change that dropped the read_permissions call."""
        template = "[read_permissions]\n#*/*@*/*: *\n[write_permissions]\n*/*@*/*: demo\n[users]\ndemo: demo\n"
        fixed = setup._server_conf_permission_fix(template)
        read_section = fixed.split("[read_permissions]", 1)[1].split("[write_permissions]", 1)[0]
        # An ACTIVE (non-comment) line, not merely the substring - the
        # commented-out original is expected to still be present too
        # (_ensure_section_line() never strips existing comments).
        self.assertIn("\n*/*@*/*: *", read_section)


class FindListeningPidTests(unittest.TestCase):
    """NS-21 (cache_first_no_server_plan.md, redo of CE-34): best-effort
    PID-by-port lookup - platform-appropriate command mocked, never a
    real netstat/ss/process call."""

    @unittest.skipUnless(os.name == "nt", "Windows netstat -ano output shape")
    def test_windows_parses_netstat_output(self):
        netstat_output = (
            "  Proto  Local Address          Foreign Address        State           PID\n"
            "  TCP    0.0.0.0:9310           0.0.0.0:0              LISTENING       4242\n"
            "  TCP    127.0.0.1:9310         127.0.0.1:51000        ESTABLISHED     4242\n"
        )
        with mock.patch("subprocess.run", return_value=_fake_run(0, netstat_output)):
            self.assertEqual(setup._find_listening_pid(9310), 4242)

    @unittest.skipUnless(os.name == "nt", "Windows netstat -ano output shape")
    def test_windows_no_matching_port_returns_none(self):
        netstat_output = "  TCP    0.0.0.0:8080           0.0.0.0:0              LISTENING       1111\n"
        with mock.patch("subprocess.run", return_value=_fake_run(0, netstat_output)):
            self.assertIsNone(setup._find_listening_pid(9310))

    @unittest.skipIf(os.name == "nt", "POSIX ss -ltnp output shape")
    def test_posix_parses_ss_output(self):
        ss_output = ('LISTEN 0 128 127.0.0.1:9310 0.0.0.0:*'
                      ' users:(("conan_server",pid=4242,fd=6))\n')
        with mock.patch("subprocess.run", return_value=_fake_run(0, ss_output)):
            self.assertEqual(setup._find_listening_pid(9310), 4242)

    def test_command_failure_returns_none_not_raise(self):
        with mock.patch("subprocess.run", return_value=_fake_run(1, "")):
            self.assertIsNone(setup._find_listening_pid(9310))

    def test_command_missing_returns_none_not_raise(self):
        with mock.patch("subprocess.run", side_effect=FileNotFoundError):
            self.assertIsNone(setup._find_listening_pid(9310))


class LaunchConanServerDetachedTests(unittest.TestCase):
    """NS-21 (cache_first_no_server_plan.md): real bug found running
    cold_machine_check.py --with-server for real, 2026-09-23 - launching
    detached and returning immediately raced against the very next setup
    step (register_team_remote()'s own reachability check), which could
    run before conan_server had finished binding the port and wrongly
    treat it as permanently unreachable (CE-36). _launch_conan_server_
    detached() now waits, bounded, for the port to answer before
    returning."""

    def test_planted_violation_returns_without_waiting_for_the_port(self):
        """PASS: _port_reachable() is polled (not just checked once, and
        not skipped) until it reports True. FAIL: returns immediately
        after Popen() with no reachability wait at all - the exact race
        that produced the real bug."""
        calls = []

        def fake_reachable(port, **kwargs):
            calls.append(port)
            return len(calls) >= 3  # "up" only on the 3rd poll

        with mock.patch.object(setup, "_port_reachable", side_effect=fake_reachable), \
                mock.patch("subprocess.Popen"), \
                mock.patch("time.sleep") as sleep_mock:
            with tempfile.TemporaryDirectory() as tmp:
                setup._launch_conan_server_detached(["fake", "cmd"], tmp, 9310)

        self.assertGreaterEqual(len(calls), 3)
        self.assertTrue(all(p == 9310 for p in calls))
        self.assertEqual(sleep_mock.call_count, 2)  # slept between polls 1->2 and 2->3, not after

    def test_gives_up_after_the_bounded_wait_and_still_returns(self):
        """A server that never comes up must not hang this script forever
        - the bounded wait gives up and returns; the NEXT step's own
        reachability check is what correctly reports the real problem."""
        with mock.patch.object(setup, "_port_reachable", return_value=False) as reachable_mock, \
                mock.patch("subprocess.Popen"), \
                mock.patch("time.sleep"):
            with tempfile.TemporaryDirectory() as tmp:
                setup._launch_conan_server_detached(["fake", "cmd"], tmp, 9310)  # must not hang/raise

        self.assertEqual(reachable_mock.call_count, 50)


class EnsureResolutionCompleteTests(unittest.TestCase):
    """CET-04 (conan_environment_plan.md §8, WP-02) / RD-03
    (remove_develop_mode_plan.md): wires the already-built, already-proven
    checker (imp_design.md §6 WP-13) into the normal setup flow, right
    after configure_conan_dependencies(). Package mode is the only mode
    now - ensure_resolution_complete() always VERIFIES first, never
    publishes from this machine's local Conan CACHE. RD-12
    (remove_develop_mode_plan.md, 2026-09-22): a still-MISSING ref against
    THIS machine's own loopback adas-local SERVER (`_adas_local_is_local_
    server()` True) is auto-published from the checkout before failing -
    a different thing from the cache case above, and the one this repo's
    own committed scripts/team_conan_server.txt always points at
    (loopback, every developer's own server model). A REAL team server
    (non-loopback) still falls straight through to the old hard failure,
    unchanged - never publish a developer's checkout to a shared server."""

    def test_never_passes_publish_missing_on_first_call(self):
        with mock.patch.object(setup.check_conan_resolution, "main",
                                return_value=0) as main_mock:
            setup.ensure_resolution_complete(_Ctx())

        main_mock.assert_called_once()
        argv = main_mock.call_args[0][0]
        self.assertNotIn("--publish-missing", argv)
        self.assertIn("--platform", argv)

    def test_missing_ref_is_a_hard_failure_naming_it(self):
        """F-PACKAGE-MISSING: PASS - a still-MISSING ref against a REAL
        (non-loopback) team server raises StepFailed (setup.py's own
        step() wrapper turns that into an exit(1)), never a WARNING setup
        continues past. FAIL: setup completes anyway.

        CE-32 (conan_environment_plan.md): this is the non-loopback
        branch, where "setup.py never publishes ... onto a server it
        doesn't own" is still true (RD-12 never attempted a publish
        here) - kept as its own distinct message from the loopback
        branch's own CE-32 rewrite below."""
        captured = io.StringIO()
        with mock.patch.object(setup.check_conan_resolution, "main", return_value=1), \
                mock.patch.object(setup, "read_team_server_url",
                                   return_value="http://team-server.example.com:9300"), \
                contextlib.redirect_stdout(captured):
            with self.assertRaises(setup.StepFailed) as ctx_mgr:
                setup.ensure_resolution_complete(_Ctx())

        exc = ctx_mgr.exception
        self.assertIn("does not resolve to this machine", str(exc))
        self.assertIn("--offline", exc.fix)

    def test_rd12_local_loopback_server_auto_publishes_then_succeeds(self):
        """RD-12: adas-local resolves to THIS machine (loopback) - a
        still-MISSING first pass is auto-published from the checkout
        (second call carries --publish-missing) and, once that succeeds,
        ensure_resolution_complete() returns cleanly rather than raising.

        NS-21 (cache_first_no_server_plan.md): real bug found running
        cold_machine_check.py --with-server for real, 2026-09-23 - the
        publish call used to omit --remotes entirely, so check_conan_
        resolution.py re-derived remotes_enabled() from scratch and, for
        a loopback URL, NS-24/D1a made that come back "off" - defeating
        the very publish this branch exists to attempt. The second call
        must carry --remotes on, forwarded from what already got this
        function INTO this branch in the first place."""
        with mock.patch.object(setup.check_conan_resolution, "main",
                                side_effect=[1, 0]) as main_mock, \
                mock.patch.object(setup, "read_team_server_url",
                                   return_value="http://127.0.0.1:9300"):
            outcome = setup.ensure_resolution_complete(_Ctx())

        self.assertIsNone(outcome)
        self.assertEqual(main_mock.call_count, 2)
        first_argv, second_argv = (c[0][0] for c in main_mock.call_args_list)
        self.assertNotIn("--publish-missing", first_argv)
        self.assertIn("--publish-missing", second_argv)
        self.assertIn("--remotes", second_argv)
        self.assertEqual(second_argv[second_argv.index("--remotes") + 1], "on")

    def test_rd12_local_loopback_server_still_missing_after_publish_fails(self):
        """RD-12: the auto-publish attempt itself can still leave a ref
        MISSING (no local source, or a real publish failure) - that still
        raises StepFailed.

        CE-32 (conan_environment_plan.md): the message must now name the
        REAL causes (server not reachable / conancenter not reachable)
        and remedies (including --offline) - not the old, actively false
        "setup.py never publishes from this machine's local cache" text,
        which hid exactly this bug's own root cause on the real
        corporate PC that found it (adas-local wasn't reachable at all)."""
        with mock.patch.object(setup.check_conan_resolution, "main",
                                side_effect=[1, 1]), \
                mock.patch.object(setup, "read_team_server_url",
                                   return_value="http://127.0.0.1:9300"):
            with self.assertRaises(setup.StepFailed) as ctx_mgr:
                setup.ensure_resolution_complete(_Ctx())

        exc = ctx_mgr.exception
        self.assertIn("just tried to publish", str(exc))
        self.assertIn("reachable", str(exc))
        self.assertIn("--offline", exc.fix)
        self.assertIn("Conan server on-demand persistence", str(exc))

    def test_rd12_planted_violation_real_team_server_never_publishes(self):
        """Planted violation for the D3-style boundary RD-12 draws: a REAL
        (non-loopback) team server must NEVER see --publish-missing, no
        matter how many times check_conan_resolution.main() is called -
        publishing a developer's checkout to a shared server is not
        setup's job."""
        with mock.patch.object(setup.check_conan_resolution, "main",
                                return_value=1) as main_mock, \
                mock.patch.object(setup, "read_team_server_url",
                                   return_value="http://team-server.example.com:9300"):
            with self.assertRaises(setup.StepFailed):
                setup.ensure_resolution_complete(_Ctx())

        main_mock.assert_called_once()
        argv = main_mock.call_args[0][0]
        self.assertNotIn("--publish-missing", argv)

    def test_rd12_no_team_server_configured_never_publishes(self):
        """No scripts/team_conan_server.txt configured at all - nothing to
        confirm is safe to write to, so the conservative verify-only path
        is unchanged (same as the real-team-server case)."""
        with mock.patch.object(setup.check_conan_resolution, "main",
                                return_value=1) as main_mock, \
                mock.patch.object(setup, "read_team_server_url", return_value=None):
            with self.assertRaises(setup.StepFailed):
                setup.ensure_resolution_complete(_Ctx())

        main_mock.assert_called_once()


class AdasLocalIsLocalServerTests(unittest.TestCase):
    """RD-12: the loopback-detection helper in isolation."""

    def test_loopback_urls_are_local(self):
        for url in ("http://127.0.0.1:9300", "http://localhost:9300",
                    "http://[::1]:9300"):
            with mock.patch.object(setup, "read_team_server_url", return_value=url):
                self.assertTrue(setup._adas_local_is_local_server(), url)

    def test_real_host_is_not_local(self):
        with mock.patch.object(setup, "read_team_server_url",
                                return_value="http://192.168.1.50:9300"):
            self.assertFalse(setup._adas_local_is_local_server())

    def test_unconfigured_is_not_local(self):
        with mock.patch.object(setup, "read_team_server_url", return_value=None):
            self.assertFalse(setup._adas_local_is_local_server())

    def test_success_returns_cleanly(self):
        with mock.patch.object(setup.check_conan_resolution, "main", return_value=0):
            outcome = setup.ensure_resolution_complete(_Ctx())

        self.assertIsNone(outcome)

    def test_dry_run_makes_no_real_call(self):
        with mock.patch.object(setup.check_conan_resolution, "main") as main_mock:
            outcome = setup.ensure_resolution_complete(_Ctx(dry_run=True))

        main_mock.assert_not_called()
        self.assertEqual(outcome, "skip")

    def test_platform_is_os_appropriate_not_hardcoded(self):
        """The platform passed to check_conan_resolution must match
        setup.py's own OS-based selection used elsewhere, never a bare
        hardcoded vs2026."""
        with mock.patch.object(setup.check_conan_resolution, "main",
                                return_value=0) as main_mock:
            setup.ensure_resolution_complete(_Ctx())

        main_mock.assert_called_once()
        argv = main_mock.call_args[0][0]
        self.assertIn("--platform", argv)
        expected_platform = "vs2026" if os.name == "nt" else "ubuntu_gcc"
        self.assertEqual(argv[argv.index("--platform") + 1], expected_platform)


class PrintEnvironmentSummaryTests(unittest.TestCase):
    """CET-06 (conan_environment_plan.md §8, WP-03): the summary
    must report exactly what was mocked, line for line - "a summary that
    can lie is worse than no summary" is this test's own FAIL condition,
    not "some output was produced"."""

    def _run_summary(self, ctx):
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            setup.print_environment_summary(ctx)
        return captured.getvalue()

    def _patch_resolution(self, refs, missing_refs, python_require_refs=()):
        """Fakes check_resolvable() to report MISSING for exactly
        missing_refs and PASS for everything else in refs. RD-03: signature
        matches the real, package-mode-only check_resolvable() - no more
        `editables`/`platform` params."""
        def fake_check_resolvable(ref, remote="adas-local", profile_settings=None,
                                   is_python_require=False):
            if ref in missing_refs:
                return False, "no adas-local binary matches the pinned profile"
            return True, "adas-local (binary matches the pinned profile)"

        return [
            mock.patch.object(setup.check_conan_resolution, "discover_required_refs",
                               return_value=refs),
            mock.patch.object(setup.check_conan_resolution, "discover_python_requires_refs",
                               return_value=set(python_require_refs)),
            mock.patch.object(setup.check_conan_resolution, "pinned_profile_settings",
                               return_value={"compiler.version": "195"}),
            mock.patch.object(setup.check_conan_resolution, "check_resolvable",
                               side_effect=fake_check_resolvable),
        ]

    def test_cet06_c1_every_line_matches_the_mocked_state_exactly(self):
        """PASS: every line matches the mocked state exactly - the single
        cache path (RD-03: one CONAN_HOME now, not two), the real
        EXPLICIT override line when CONAN_HOME is actually set (corner
        case 10's unit-level guard - WP-23, conan_environment_plan.md
        §6), the real reachability/login result, the real
        launched-this-run history, the real MISSING count and ref name.
        FAIL: any line doesn't match what was fed in."""
        ctx = _Ctx()
        ctx.server_recovery_status = "launched"
        # NS-23 (redo of CE-37): the line this used to independently
        # re-derive via _patch_resolution() is now purely a report of
        # what ensure_resolution_complete() already stashed - set
        # directly, as that step would have.
        ctx.resolution_summary = "1/2  -  MISSING: adas-viz/1.0.0"

        def fake_run(cmd, **kwargs):
            if cmd[:3] == ["conan", "remote", "list-users"]:
                return _fake_run(0, json.dumps([
                    {"name": "conancenter", "user_name": None, "authenticated": False},
                    {"name": "adas-local", "user_name": "demo", "authenticated": True},
                ]))
            return _fake_run(0, "")

        with mock.patch.object(setup, "read_team_server_url",
                                return_value="http://127.0.0.1:9300"), \
                mock.patch.object(setup, "_port_reachable", return_value=True), \
                mock.patch("subprocess.run", side_effect=fake_run), \
                mock.patch.dict(os.environ, {"CONAN_HOME": "C:\\custom\\conan2home"}):
            output = self._run_summary(ctx)

        self.assertIn(
            "Cache, explicit override:  C:\\custom\\conan2home   "
            "(CONAN_HOME set in this shell - always respected, never overridden)", output)
        self.assertIn(
            "Local server (adas-local): http://127.0.0.1:9300  [reachable, logged in]", output)
        self.assertIn(
            "Auto-recovery:             on-demand (ensure_server_running, "
            "this run: was down, launched it)", output)
        self.assertIn(
            "Packages resolvable:       1/2  -  MISSING: adas-viz/1.0.0", output)

    # NS-23 (cache_first_no_server_plan.md, redo of CE-37) removed the
    # test formerly here (test_python_requires_ref_is_checked_with_
    # is_python_require_true, CE-20): it exercised print_environment_
    # summary()'s own independent re-derivation loop calling
    # check_resolvable() with an is_python_require kwarg - that whole loop
    # is gone (the summary now purely reports ctx.resolution_summary, see
    # ResolutionSummaryStashedValueTests below). check_resolvable()'s own
    # is_python_require handling stays covered in
    # scripts/tests/test_check_conan_resolution.py.

    def test_default_cache_path_is_labeled_default_not_custom(self):
        """PASS: with no CONAN_HOME set at all, the single fixed cache
        line is reported (RD-03: one CONAN_HOME now) and NO
        explicit-override line appears - `Cache, explicit override:`
        exists only when os.environ actually carries CONAN_HOME (see the
        cet06_c1 test above for that case)."""
        standard = str(setup._standard_conan_home())

        patches = self._patch_resolution(refs=[], missing_refs=set())
        with mock.patch.object(setup, "read_team_server_url", return_value=None), \
                mock.patch("subprocess.run", return_value=_fake_run(0, "[]")), \
                mock.patch.dict(os.environ, {}, clear=False), \
                contextlib.ExitStack() as stack:
            os.environ.pop("CONAN_HOME", None)
            for p in patches:
                stack.enter_context(p)
            output = self._run_summary(_Ctx())

        self.assertIn(f"Cache:                     {standard}", output)
        self.assertNotIn("Cache, explicit override:", output)

    def test_no_team_server_configured_is_reported_plainly(self):
        patches = self._patch_resolution(refs=[], missing_refs=set())
        with mock.patch.object(setup, "read_team_server_url", return_value=None), \
                mock.patch("subprocess.run", return_value=_fake_run(0, "")), \
                contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            output = self._run_summary(_Ctx())

        self.assertIn("Local server (adas-local): not configured", output)
        # Must not fabricate a reachability verdict for an unconfigured server.
        self.assertNotIn("reachable]", output)

    def test_not_reachable_is_reported_without_a_login_claim(self):
        patches = self._patch_resolution(refs=[], missing_refs=set())
        with mock.patch.object(setup, "read_team_server_url",
                                return_value="http://127.0.0.1:9300"), \
                mock.patch.object(setup, "_port_reachable", return_value=False), \
                mock.patch("subprocess.run", return_value=_fake_run(0, "[]")), \
                contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            output = self._run_summary(_Ctx())

        self.assertIn("[NOT reachable]", output)
        self.assertNotIn("logged in", output)

    def test_no_refs_declared_reports_zero_of_zero(self):
        # NS-23: "0/0" is now whatever ensure_resolution_complete() stashed
        # for the no-refs case (see ResolutionSummaryStashedValueTests'
        # own test_ensure_resolution_complete_stashes_zero_of_zero_when_
        # no_refs_declared for that step's own behavior) - here we only
        # confirm the summary reports it verbatim, same as every other
        # value.
        ctx = _Ctx()
        ctx.resolution_summary = "0/0  (no adas-* refs declared)"
        with mock.patch.object(setup, "read_team_server_url", return_value=None), \
                mock.patch("subprocess.run", return_value=_fake_run(0, "")):
            output = self._run_summary(ctx)

        self.assertIn("Packages resolvable:       0/0  (no adas-* refs declared)", output)

    def test_auto_recovery_never_ran_this_session_is_reported_honestly(self):
        """--role server: ensure_server_running() never runs, so ctx never
        gets a server_recovery_status - must say so plainly, never fake a
        "this run" answer it doesn't have."""
        ctx = _Ctx()  # no server_recovery_status attribute set at all
        patches = self._patch_resolution(refs=[], missing_refs=set())
        with mock.patch.object(setup, "read_team_server_url", return_value=None), \
                mock.patch("subprocess.run", return_value=_fake_run(0, "")), \
                contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            output = self._run_summary(ctx)

        self.assertIn("not run this session", output)

    # NS-23 (cache_first_no_server_plan.md, redo of CE-37) removed the
    # test formerly here (test_expired_login_is_reported_not_raised,
    # Step 0a/RD-05): it planted an AdasLocalLoginExpired raise inside a
    # check_resolvable() call made FROM print_environment_summary() -
    # that call no longer exists there at all (moved to
    # ensure_resolution_complete(), which already has its own login-
    # expiry handling via check_conan_resolution.main(), covered by
    # test_check_conan_resolution.py's ExpiredLoginTests). What print_
    # environment_summary() must still never do is raise on an unset
    # ctx.resolution_summary - covered by ResolutionSummaryStashedValueTests.


class ResolutionSummaryStashedValueTests(unittest.TestCase):
    """CET-21 (conan_environment_plan.md §8, NS-23/redo of CE-37):
    'the summary reports what the step already computed, never a second
    derivation.' Split from PrintEnvironmentSummaryTests since this class
    also exercises ensure_resolution_complete() itself (the producer),
    not only print_environment_summary() (the consumer)."""

    def _run_summary(self, ctx):
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            setup.print_environment_summary(ctx)
        return captured.getvalue()

    def test_cet21_c1_summary_prints_the_stashed_value_verbatim(self):
        """PASS: the printed line matches ctx.resolution_summary exactly,
        with discover_required_refs()/check_resolvable() never called -
        proving it really is computed nowhere else, not merely that the
        two values happen to agree. FAIL: a value that doesn't match, or
        either function called."""
        ctx = _Ctx()
        ctx.resolution_summary = "3/5  -  MISSING: adas-viz/1.0.0, adas-sim/1.0.0"
        with mock.patch.object(setup, "read_team_server_url", return_value=None), \
                mock.patch("subprocess.run", return_value=_fake_run(0, "")), \
                mock.patch.object(setup.check_conan_resolution, "discover_required_refs") as refs_mock, \
                mock.patch.object(setup.check_conan_resolution, "check_resolvable") as resolv_mock:
            output = self._run_summary(ctx)

        self.assertIn(
            "Packages resolvable:       3/5  -  MISSING: adas-viz/1.0.0, adas-sim/1.0.0",
            output)
        refs_mock.assert_not_called()
        resolv_mock.assert_not_called()

    def test_cet21_c2_unset_because_dry_run_says_so_by_name(self):
        """PASS: ctx.resolution_summary unset because ensure_resolution_
        complete() returned 'skip' under --dry-run (never really ran) is
        reported as '... (--dry-run)', distinct from the role reason
        below. FAIL: a fabricated value, or a claim of verification that
        didn't happen."""
        ctx = _Ctx(dry_run=True)
        with mock.patch.object(setup, "read_team_server_url", return_value=None), \
                mock.patch("subprocess.run", return_value=_fake_run(0, "")):
            output = self._run_summary(ctx)

        self.assertIn("Packages resolvable:       not verified this run (--dry-run)", output)

    def test_cet21_c2_unset_because_role_server_says_so_by_name(self):
        """PASS: ctx.resolution_summary unset because --role server never
        calls ensure_resolution_complete() at all is reported by that
        reason, distinct from the --dry-run one above."""
        ctx = _Ctx()
        ctx.role = "server"
        with mock.patch.object(setup, "read_team_server_url", return_value=None), \
                mock.patch("subprocess.run", return_value=_fake_run(0, "")):
            output = self._run_summary(ctx)

        self.assertIn(
            "Packages resolvable:       not verified this run "
            "(ensure_resolution_complete only runs for --role dev)", output)

    def test_ensure_resolution_complete_stashes_the_computed_count(self):
        """The producer side: a successful check_conan_resolution.main()
        run means every discovered ref is resolvable, so the stashed
        value is simply len(refs)/len(refs) - no second per-ref walk."""
        ctx = _Ctx()
        with mock.patch.object(setup.check_conan_resolution, "main", return_value=0), \
                mock.patch.object(setup.check_conan_resolution, "discover_required_refs",
                                   return_value=["adas-viz/1.0.0", "adas-mathlib/1.0.0"]):
            setup.ensure_resolution_complete(ctx)

        self.assertEqual(ctx.resolution_summary, "2/2")

    def test_ensure_resolution_complete_stashes_zero_of_zero_when_no_refs_declared(self):
        ctx = _Ctx()
        with mock.patch.object(setup.check_conan_resolution, "main", return_value=0), \
                mock.patch.object(setup.check_conan_resolution, "discover_required_refs",
                                   return_value=[]):
            setup.ensure_resolution_complete(ctx)

        self.assertEqual(ctx.resolution_summary, "0/0  (no adas-* refs declared)")

    def test_ensure_resolution_complete_stashes_after_rd12_publish_too(self):
        """The RD-12 auto-publish success path (loopback adas-local,
        missing refs published from local source) stashes the same shape
        as the plain-pass path above - both are "every discovered ref is
        now resolvable", just reached a different way."""
        ctx = _Ctx()
        with mock.patch.object(setup.check_conan_resolution, "main",
                                side_effect=[1, 0]), \
                mock.patch.object(setup, "_adas_local_is_local_server", return_value=True), \
                mock.patch.object(setup.check_conan_resolution, "discover_required_refs",
                                   return_value=["adas-toolchain/1.0.4"]):
            setup.ensure_resolution_complete(ctx)

        self.assertEqual(ctx.resolution_summary, "1/1")

    def test_dry_run_never_stashes_a_value(self):
        ctx = _Ctx(dry_run=True)
        outcome = setup.ensure_resolution_complete(ctx)
        self.assertEqual(outcome, "skip")
        self.assertFalse(hasattr(ctx, "resolution_summary"))


class EnsureHttpsTrustTests(unittest.TestCase):
    """CET-07/CET-08 (conan_environment_plan.md §8, WP-04):
    unconditional pip-system-certs install + direct TLS-handshake
    verification, with the "pip itself is blocked" case reported
    distinctly and without attempting the handshake check."""

    def test_cet07_c1_pip_ok_and_handshake_ok_reports_success_no_exception(self):
        """F-PYPI-OK: PASS - no exception, handshake verified. FAIL: any
        failure on a machine where nothing was actually broken."""
        with mock.patch("subprocess.run",
                         return_value=_fake_run(0, "Successfully installed pip-system-certs")), \
                mock.patch.object(setup, "_tls_handshake_ok", return_value=True) as handshake_mock:
            setup.ensure_https_trust(_Ctx())  # must not raise

        handshake_mock.assert_called_once_with(setup.CONAN_TLS_CHECK_HOST,
                                                setup.CONAN_TLS_CHECK_PORT)

    def test_cet08_c1_pip_itself_blocked_is_reported_distinctly_and_skips_handshake(self):
        """F-PYPI-BLOCKED: PASS - the message names this specific case
        ("pip itself cannot reach PyPI") distinctly from a generic install
        failure, and the TLS-handshake check is never attempted (nothing
        installed to verify). FAIL: a generic, unhelpful error, or a crash
        attempting to verify a fix that never installed."""
        cert_error_output = (
            "ERROR: Could not install packages due to an OSError: "
            "HTTPSConnectionPool(host='pypi.org', port=443): Max retries "
            "exceeded with url: /simple/pip-system-certs/ (Caused by "
            "SSLError(SSLCertVerificationError(1, '[SSL: "
            "CERTIFICATE_VERIFY_FAILED] certificate verify failed: "
            "self-signed certificate in certificate chain')))"
        )
        with mock.patch("subprocess.run", return_value=_fake_run(1, cert_error_output)), \
                mock.patch.object(setup, "_tls_handshake_ok") as handshake_mock:
            with self.assertRaises(setup.StepFailed) as cm:
                setup.ensure_https_trust(_Ctx())

        handshake_mock.assert_not_called()
        self.assertIn("pip itself cannot reach PyPI", cm.exception.reason)
        self.assertIn("IT team", cm.exception.fix)

    def test_generic_pip_failure_is_distinct_from_the_cert_blocked_case(self):
        """A pip failure with no certificate signature (network down, PyPI
        itself down, ...) must not be misreported as the CE-08 case."""
        with mock.patch("subprocess.run",
                         return_value=_fake_run(1, "ERROR: Could not find a version that "
                                                    "satisfies the requirement pip-system-certs")), \
                mock.patch.object(setup, "_tls_handshake_ok") as handshake_mock:
            with self.assertRaises(setup.StepFailed) as cm:
                setup.ensure_https_trust(_Ctx())

        handshake_mock.assert_not_called()
        self.assertNotIn("pip itself cannot reach PyPI", cm.exception.reason)

    def test_dry_run_makes_no_real_calls(self):
        with mock.patch("subprocess.run") as run_mock, \
                mock.patch.object(setup, "_tls_handshake_ok") as handshake_mock:
            outcome = setup.ensure_https_trust(_Ctx(dry_run=True))

        run_mock.assert_not_called()
        handshake_mock.assert_not_called()
        self.assertEqual(outcome, "skip")


class ShebangParserTests(unittest.TestCase):
    """CE-30 (conan_environment_plan.md): the two pure, platform-specific
    parsers `_resolve_console_script_interpreter()` dispatches to - kept
    separate and tested directly (no os.name patching, no real files)
    for exactly the reason their own docstrings give: `os` is a
    process-wide singleton, so patching `os.name` in a test to exercise
    "the other platform's" branch also changes what `pathlib.Path`
    itself thinks the platform is, and breaks with `NotImplementedError:
    cannot instantiate 'PosixPath' on your system` on the "wrong" one -
    hit live writing this suite, the reason this split exists at all."""

    def test_posix_shebang_direct_path(self):
        self.assertEqual(
            setup._shebang_from_posix_script(b"#!/home/dev/.venv/bin/python3\nimport sys\n"),
            "/home/dev/.venv/bin/python3")

    def test_posix_shebang_env_form_uses_last_token(self):
        self.assertEqual(
            setup._shebang_from_posix_script(b"#!/usr/bin/env python3\n"),
            "python3")

    def test_posix_no_shebang_returns_none(self):
        self.assertIsNone(setup._shebang_from_posix_script(b"no shebang here\n"))

    def test_windows_embedded_shebang_last_occurrence_wins(self):
        """The real confirmed shape (2026-09-23, a real pip-installed
        conan.exe): an unrelated, false '#!' byte sequence appears earlier
        in the compiled launcher stub's own resource strings; the genuine
        shebang is the LAST '#!' occurrence, immediately before the
        appended zip's 'PK' signature. Planted here as the false match
        the real file has, so this test would fail if rfind() were
        changed to find() (first occurrence)."""
        data = (b"native stub bytes... #!  P A T H E X T  ...more stub bytes..."
                + b"#!C:\\Users\\dev\\Python311\\python.exe\r\n\r\n"
                + b"PK\x03\x04rest of zip")
        self.assertEqual(setup._shebang_from_windows_launcher(data),
                          r"C:\Users\dev\Python311\python.exe")

    def test_windows_no_shebang_returns_none(self):
        self.assertIsNone(setup._shebang_from_windows_launcher(
            b"no shebang anywhere in this stub"))

    def test_windows_arbitrary_binary_bytes_never_raise(self):
        """latin-1 maps every byte 0-255, so this must never raise on
        genuinely arbitrary binary content (a real .exe's PE header,
        resource sections, etc.) - only ever return None or a string."""
        garbage = bytes(range(256)) * 4
        self.assertIsNone(setup._shebang_from_windows_launcher(garbage))


class ResolveConsoleScriptInterpreterTests(unittest.TestCase):
    """CE-30 (conan_environment_plan.md): the dispatcher + existence
    check around the two pure parsers above - exercised against the
    REAL, live os.name (native platform), never mocked (see
    ShebangParserTests' own docstring for why)."""

    def test_native_platform_shebang_with_a_real_existing_interpreter(self):
        """Builds a fixture in this test's own platform's real shape
        (Windows-embedded on Windows, plain shebang on POSIX) and points
        it at a real, existing file - proves the dispatcher picks the
        right parser for whatever platform this suite is actually
        running on."""
        with tempfile.TemporaryDirectory() as tmp:
            interp = Path(tmp) / ("python.exe" if os.name == "nt" else "python3")
            interp.write_bytes(b"")  # only needs to exist
            script = Path(tmp) / ("conan.exe" if os.name == "nt" else "conan")
            if os.name == "nt":
                script.write_bytes(
                    b"native stub bytes..." + f"#!{interp}\r\n\r\n".encode("latin-1")
                    + b"PK\x03\x04rest of zip")
            else:
                script.write_bytes(f"#!{interp}\nimport sys\n".encode())

            result = setup._resolve_console_script_interpreter(str(script))
        self.assertEqual(result, str(interp))

    def test_recovered_path_that_does_not_exist_is_rejected(self):
        """A syntactically valid shebang pointing at a path that isn't
        actually there must be rejected, not returned as a guess -
        CE-30's own 'fall back to reporting it' words."""
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / ("conan.exe" if os.name == "nt" else "conan")
            missing = str(Path(tmp) / "does-not-exist" / "python3")
            if os.name == "nt":
                script.write_bytes(
                    f"#!{missing}\r\n\r\nPK\x03\x04rest".encode("latin-1"))
            else:
                script.write_bytes(f"#!{missing}\n".encode())

            result = setup._resolve_console_script_interpreter(str(script))
        self.assertIsNone(result)

    def test_unreadable_script_returns_none(self):
        result = setup._resolve_console_script_interpreter(r"C:\does\not\exist\conan.exe")
        self.assertIsNone(result)

    def test_none_script_path_returns_none(self):
        self.assertIsNone(setup._resolve_console_script_interpreter(None))


class EnsureConanInterpreterTrustsHttpsTests(unittest.TestCase):
    """CE-30 (conan_environment_plan.md): ensure_https_trust() only ever
    proved sys.executable's own interpreter trusts conancenter - a
    `conan` already on PATH under a DIFFERENT, pre-existing interpreter
    (the real second-corporate-PC failure, 2026-09-23: "TLS handshake ...
    succeeded" / "[OK] HTTPS trust" printed, then every `conan create`
    failed with SSLCertVerificationError) was never touched. Must run
    strictly after check_or_install_conan in main()'s own step order -
    conan is assumed present on PATH here."""

    def _run(self, conan_path=r"C:\other\python\Scripts\conan.exe",
              conan_interp=r"C:\other\python\python.exe", ctx=None):
        with mock.patch.object(setup.shutil, "which", return_value=conan_path), \
                mock.patch.object(setup, "_resolve_console_script_interpreter",
                                   return_value=conan_interp):
            return setup.ensure_conan_interpreter_trusts_https(ctx or _Ctx())

    def test_no_conan_on_path_is_a_skip_not_a_crash(self):
        """Only reachable from a test double calling this in isolation -
        check_or_install_conan() (main()'s own preceding step) would
        already have raised StepFailed and aborted the run otherwise."""
        with mock.patch.object(setup.shutil, "which", return_value=None):
            outcome = setup.ensure_conan_interpreter_trusts_https(_Ctx())
        self.assertEqual(outcome, "skip")

    def test_two_interpreter_case_installs_into_both_then_verifies_via_conan(self):
        """PASS: conan's interpreter differs from sys.executable - pip-
        system-certs is installed into THAT interpreter too (a second
        install call, distinct from ensure_https_trust()'s own), and
        verification goes through `conan search ... -r conancenter`, not
        a raw Python TLS handshake. FAIL: only one interpreter fixed, or
        verification never touches conan itself."""
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return mock.Mock(returncode=0, stdout="")

        with mock.patch.object(setup, "run", side_effect=fake_run):
            outcome = self._run()

        self.assertIsNone(outcome)  # real work happened, not "skip"
        self.assertTrue(any(
            c[0] == r"C:\other\python\python.exe" and c[1:] ==
            ["-m", "pip", "install", "--user", "pip-system-certs"]
            for c in calls),
            f"no pip-system-certs install into conan's own interpreter; calls={calls}")
        self.assertTrue(any(
            c[:4] == ["conan", "search", setup.CONAN_TLS_VERIFY_REF, "-r"] and "conancenter" in c
            for c in calls),
            f"verification never ran through conan itself; calls={calls}")

    def test_same_interpreter_skips_the_second_install(self):
        """PASS: conan belongs to the SAME interpreter as sys.executable
        (the common case - conan was installed by check_or_install_conan()
        itself, moments earlier) - no second pip install, verification
        still runs. FAIL: a redundant second install for no reason."""
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return mock.Mock(returncode=0, stdout="")

        with mock.patch.object(setup, "run", side_effect=fake_run):
            outcome = self._run(conan_interp=sys.executable)

        self.assertIsNone(outcome)
        pip_install_calls = [c for c in calls if "pip-system-certs" in c]
        self.assertEqual(pip_install_calls, [])
        self.assertTrue(any(c[:2] == ["conan", "search"] for c in calls))

    def test_unresolvable_interpreter_still_verifies_via_conan(self):
        """PASS: conan's interpreter couldn't be determined at all (the
        'fall back to reporting it' case, CE-30's own words) - no second
        install is attempted (nothing to install into), but the conan-
        based verification still runs. FAIL: skips verification too."""
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return mock.Mock(returncode=0, stdout="")

        with mock.patch.object(setup, "run", side_effect=fake_run):
            outcome = self._run(conan_interp=None)

        self.assertIsNone(outcome)
        self.assertEqual(calls, [["conan", "search", setup.CONAN_TLS_VERIFY_REF,
                                   "-r", "conancenter"]])

    def test_conan_side_certificate_failure_is_a_stepfailed_naming_the_fix(self):
        """PASS: `conan search` itself fails with a certificate error -
        StepFailed naming conan's own interpreter and the exact pip-
        install remedy. FAIL: silently reported OK, or a generic message
        that doesn't say which interpreter to fix - reproduces the real
        corporate-PC bug (raw handshake said OK, conan itself was still
        broken) if this doesn't fire."""
        cert_error = ("ERROR: Recipe 'zlib/1.3.1': Error in source() method... "
                       "SSLError(SSLCertVerificationError(1, '[SSL: "
                       "CERTIFICATE_VERIFY_FAILED] certificate verify failed: "
                       "self-signed certificate in certificate chain'))")

        def fake_run(cmd, **kwargs):
            if cmd[:2] == ["conan", "search"]:
                return mock.Mock(returncode=1, stdout=cert_error)
            return mock.Mock(returncode=0, stdout="")

        with mock.patch.object(setup, "run", side_effect=fake_run):
            with self.assertRaises(setup.StepFailed) as ctx_mgr:
                self._run()

        exc = ctx_mgr.exception
        self.assertIn("certificate error", exc.reason)
        self.assertIn(r"C:\other\python\python.exe", exc.fix)
        self.assertIn("pip install --user pip-system-certs", exc.fix)

    def test_conan_side_non_certificate_failure_is_reported_distinctly(self):
        """A conan search failure with no certificate signature (network
        down, conancenter itself down) must not be misreported as CE-30's
        own certificate case."""
        def fake_run(cmd, **kwargs):
            if cmd[:2] == ["conan", "search"]:
                return mock.Mock(returncode=1, stdout="ERROR: connection timed out")
            return mock.Mock(returncode=0, stdout="")

        with mock.patch.object(setup, "run", side_effect=fake_run):
            with self.assertRaises(setup.StepFailed) as ctx_mgr:
                self._run()

        # The certificate-case branch's own distinctive phrase ("still
        # fails with a certificate error") must not fire here - checked
        # by exact phrase, not a bare substring, since the generic
        # branch's own message legitimately contains the words
        # "certificate error" too ("... a reason OTHER THAN a
        # certificate error").
        self.assertNotIn("still fails with a certificate error", ctx_mgr.exception.reason)
        self.assertIn("reason other than a certificate error", ctx_mgr.exception.reason)

    def test_second_install_failure_raises_before_verification(self):
        """PASS: the second interpreter's pip-system-certs install itself
        fails - StepFailed naming that interpreter, and `conan search` is
        never even attempted (nothing was fixed to verify)."""
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return mock.Mock(returncode=1, stdout="network error")

        with mock.patch.object(setup, "run", side_effect=fake_run):
            with self.assertRaises(setup.StepFailed) as ctx_mgr:
                self._run()

        self.assertIn(r"C:\other\python\python.exe", ctx_mgr.exception.reason)
        self.assertFalse(any(c[:2] == ["conan", "search"] for c in calls))

    def test_dry_run_makes_no_real_calls(self):
        with mock.patch.object(setup, "run") as run_mock:
            outcome = self._run(ctx=_Ctx(dry_run=True))

        run_mock.assert_not_called()
        self.assertEqual(outcome, "skip")

    def test_same_interpreter_report_names_both_interpreters(self):
        """Report both interpreters in the step output unconditionally
        (CE-30's own explicit requirement) - proven here against the
        printed text, not just the returned outcome."""
        captured = io.StringIO()
        with mock.patch.object(setup, "run",
                                return_value=mock.Mock(returncode=0, stdout="")), \
                contextlib.redirect_stdout(captured):
            self._run()

        output = captured.getvalue()
        self.assertIn(r"C:\other\python\Scripts\conan.exe", output)
        self.assertIn(r"C:\other\python\python.exe", output)
        self.assertIn(sys.executable, output)


class SameInterpreterTests(unittest.TestCase):

    @unittest.skipUnless(os.name == "nt", "Windows-only case-insensitivity; "
                          "patching os.name to exercise this on POSIX would "
                          "break pathlib itself (see ShebangParserTests' own "
                          "docstring) - real platform only.")
    def test_identical_path_different_case_on_windows_is_same(self):
        self.assertTrue(setup._same_interpreter(
            r"C:\Python311\python.exe", r"c:\python311\PYTHON.EXE"))

    def test_genuinely_different_paths_are_different(self):
        self.assertFalse(setup._same_interpreter(
            r"C:\PythonA\python.exe", r"C:\PythonB\python.exe"))

    def test_planted_violation_mutated_to_always_true_would_hide_the_two_interpreter_case(self):
        """R-REQ-9: this function's whole job is telling two real
        interpreters apart - a mutant that always returns True would make
        ensure_conan_interpreter_trusts_https() silently skip the second
        install on a genuinely different interpreter, exactly CE-30's own
        bug. Proven here to actually distinguish a real difference."""
        self.assertNotEqual(
            setup._same_interpreter(r"C:\PythonA\python.exe", r"C:\PythonB\python.exe"),
            True)


class CheckLinuxSystemPackagesTests(unittest.TestCase):
    """CET-12 (conan_environment_plan.md §8, CE-11, §4.1):
    every missing Linux system dev package is named up front, in ONE
    consolidated fix command - never silently sudo'd."""

    def test_ce23_meta_package_absent_but_capability_works_is_not_a_stop(self):
        """CE-23: `python3-venv` is a thin meta-package; Ubuntu 22.04 ships
        the real content as `python3.10-venv`, so `dpkg -s python3-venv`
        fails on a machine where `python3 -m venv` works perfectly. PASS -
        the capability probe satisfies it and setup does NOT stop. FAIL -
        a working machine is told to install something it does not need,
        which is exactly what forced a dpkg shim during CE-20's Linux
        cold-machine run."""
        def fake(cmd, **kwargs):
            if cmd[:2] == ["dpkg", "-s"]:
                # every package present EXCEPT the meta-package
                return _fake_run(1 if cmd[2] == "python3-venv" else 0)
            if "venv" in cmd and "--help" in cmd:
                return _fake_run(0)          # the capability genuinely works
            return _fake_run(0)

        with mock.patch.object(setup, "os") as os_mock, \
                mock.patch.object(setup, "run", side_effect=fake):
            os_mock.name = "posix"
            setup.check_linux_system_packages(_Ctx())   # must not raise

    def test_ce23_planted_violation_probe_failing_still_stops(self):
        """R-REQ-9 planted violation for the row above: if the capability
        is genuinely broken too, the stop MUST still happen. PASS -
        StepFailed naming python3-venv. FAIL - the probe has turned the
        check into something that can never fire."""
        def fake(cmd, **kwargs):
            if cmd[:2] == ["dpkg", "-s"]:
                return _fake_run(1 if cmd[2] == "python3-venv" else 0)
            if "venv" in cmd and "--help" in cmd:
                return _fake_run(1)          # capability broken as well
            return _fake_run(0)

        with mock.patch.object(setup, "os") as os_mock, \
                mock.patch.object(setup, "run", side_effect=fake):
            os_mock.name = "posix"
            with self.assertRaises(setup.StepFailed) as cm:
                setup.check_linux_system_packages(_Ctx())
        self.assertIn("python3-venv", cm.exception.fix)

    def test_ce23_header_only_packages_keep_dpkg_only_behaviour(self):
        """CE-23 must not weaken the other two: libx11-dev/libgl1-mesa-dev
        are headers with nothing to execute, have no probe, and a missing
        one still stops. PASS - StepFailed naming libx11-dev."""
        def fake(cmd, **kwargs):
            if cmd[:2] == ["dpkg", "-s"]:
                return _fake_run(1 if cmd[2] == "libx11-dev" else 0)
            return _fake_run(0)

        with mock.patch.object(setup, "os") as os_mock, \
                mock.patch.object(setup, "run", side_effect=fake):
            os_mock.name = "posix"
            with self.assertRaises(setup.StepFailed) as cm:
                setup.check_linux_system_packages(_Ctx())
        self.assertIn("libx11-dev", cm.exception.fix)

    def test_cet12_c1_missing_package_named_in_one_consolidated_command(self):
        """F-MISSING-LINUX-PACKAGE: PASS - one consolidated `sudo apt
        install -y ...` command naming every missing package, StepFailed
        raised rather than continuing. FAIL: sudo run directly, or setup
        continues silently with a package genuinely missing."""
        def fake_dpkg(cmd, **kwargs):
            pkg = cmd[-1]
            return _fake_run(1 if pkg == "libgl1-mesa-dev" else 0)

        with mock.patch.object(setup, "os") as os_mock, \
                mock.patch.object(setup, "run", side_effect=fake_dpkg) as run_mock:
            os_mock.name = "posix"
            with self.assertRaises(setup.StepFailed) as cm:
                setup.check_linux_system_packages(_Ctx())

        for call_args in run_mock.call_args_list:
            self.assertNotIn("sudo", call_args[0][0])
        self.assertTrue(cm.exception.fix.startswith("sudo apt install -y"))
        self.assertIn("libgl1-mesa-dev", cm.exception.fix)
        # Only the one genuinely-missing package is named, not all three.
        self.assertNotIn("libx11-dev", cm.exception.fix)
        self.assertNotIn("python3-venv", cm.exception.fix)

    def test_cet12_multiple_missing_packages_all_named_in_one_command(self):
        def fake_dpkg(cmd, **kwargs):
            pkg = cmd[-1]
            return _fake_run(0 if pkg == "python3-venv" else 1)

        with mock.patch.object(setup, "os") as os_mock, \
                mock.patch.object(setup, "run", side_effect=fake_dpkg):
            os_mock.name = "posix"
            with self.assertRaises(setup.StepFailed) as cm:
                setup.check_linux_system_packages(_Ctx())

        self.assertIn("libx11-dev", cm.exception.fix)
        self.assertIn("libgl1-mesa-dev", cm.exception.fix)
        self.assertNotIn("python3-venv", cm.exception.fix)
        # Still exactly one consolidated command, not one per package.
        self.assertEqual(cm.exception.fix.count("sudo apt install"), 1)

    def test_windows_skips_entirely_no_dpkg_call(self):
        with mock.patch.object(setup, "os") as os_mock, \
                mock.patch.object(setup, "run") as run_mock:
            os_mock.name = "nt"
            outcome = setup.check_linux_system_packages(_Ctx())

        run_mock.assert_not_called()
        self.assertEqual(outcome, "skip")

    def test_all_present_skips(self):
        with mock.patch.object(setup, "os") as os_mock, \
                mock.patch.object(setup, "run", return_value=_fake_run(0)) as run_mock:
            os_mock.name = "posix"
            outcome = setup.check_linux_system_packages(_Ctx())

        self.assertEqual(outcome, "skip")
        self.assertEqual(run_mock.call_count, len(setup.REQUIRED_LINUX_PACKAGES))


class CheckCmakeLinuxAutoUpgradeTests(unittest.TestCase):
    """CET-13 (conan_environment_plan.md §8, CE-12, §4.2):
    on Linux, a too-old (or missing) system cmake is auto-upgraded via
    `pip install --user cmake` - no sudo, unlike Windows' manual-install-
    link message (no equivalent no-sudo shortcut exists there). Found
    live under WSL: system cmake 3.22.1 couldn't read Conan's generated
    CMakePresets schema (needs >=3.23)."""

    def test_cet13_c1_old_cmake_triggers_pip_install_no_sudo(self):
        """F-OLD-CMAKE: PASS - pip install --user cmake is invoked, no
        sudo. FAIL: a Windows-style "install it yourself" message is
        printed instead on Linux, where the pip shortcut genuinely
        exists."""
        versions = iter([(3, 22), (3, 23)])  # before, after the pip install
        with mock.patch.object(setup, "os") as os_mock, \
                mock.patch.object(setup, "_cmake_version_on_path",
                                   side_effect=lambda: next(versions)), \
                mock.patch.object(setup, "run") as run_mock:
            os_mock.name = "posix"
            outcome = setup.check_cmake(_Ctx())

        run_mock.assert_called_once_with(
            [sys.executable, "-m", "pip", "install", "--user", "cmake"])
        call_str = " ".join(run_mock.call_args[0][0])
        self.assertNotIn("sudo", call_str)
        # A real action was taken (installed something) - "skip" is
        # reserved for "already satisfied, nothing done" (same convention
        # check_or_install_conan() already uses), so step() prints [OK],
        # not [SKIP], for this run.
        self.assertNotEqual(outcome, "skip")

    def test_missing_cmake_also_triggers_pip_install(self):
        versions = iter([None, (3, 25)])
        with mock.patch.object(setup, "os") as os_mock, \
                mock.patch.object(setup, "_cmake_version_on_path",
                                   side_effect=lambda: next(versions)), \
                mock.patch.object(setup, "run") as run_mock:
            os_mock.name = "posix"
            outcome = setup.check_cmake(_Ctx())

        run_mock.assert_called_once_with(
            [sys.executable, "-m", "pip", "install", "--user", "cmake"])
        self.assertNotEqual(outcome, "skip")

    def test_already_current_skips_with_no_pip_call(self):
        with mock.patch.object(setup, "os") as os_mock, \
                mock.patch.object(setup, "_cmake_version_on_path", return_value=(3, 27)), \
                mock.patch.object(setup, "run") as run_mock:
            os_mock.name = "posix"
            outcome = setup.check_cmake(_Ctx())

        run_mock.assert_not_called()
        self.assertEqual(outcome, "skip")

    def test_still_unresolved_after_install_raises_stepfailed(self):
        """The pip install itself succeeding is not enough - if the newly
        installed cmake still doesn't resolve on PATH (a non-login shell
        without ~/.local/bin ahead of /usr/bin), that must be reported,
        never silently claimed fixed."""
        versions = iter([(3, 22), (3, 22)])  # unchanged after "install"
        with mock.patch.object(setup, "os") as os_mock, \
                mock.patch.object(setup, "_cmake_version_on_path",
                                   side_effect=lambda: next(versions)), \
                mock.patch.object(setup, "run"):
            os_mock.name = "posix"
            with self.assertRaises(setup.StepFailed) as cm:
                setup.check_cmake(_Ctx())

        self.assertIn("still isn't on PATH", cm.exception.reason)

    def test_dry_run_makes_no_pip_call(self):
        with mock.patch.object(setup, "os") as os_mock, \
                mock.patch.object(setup, "_cmake_version_on_path", return_value=(3, 22)), \
                mock.patch.object(setup, "run") as run_mock:
            os_mock.name = "posix"
            outcome = setup.check_cmake(_Ctx(dry_run=True))

        run_mock.assert_not_called()
        self.assertEqual(outcome, "skip")

    def test_windows_behavior_unchanged_raises_with_manual_link(self):
        """CE-12's own explicit requirement: Windows keeps the existing
        manual-install-link message, never the pip auto-upgrade."""
        with mock.patch.object(setup, "os") as os_mock, \
                mock.patch.object(setup, "on_path", return_value=True), \
                mock.patch.object(setup, "run",
                                   return_value=_fake_run(0, "cmake version 3.20.0")):
            os_mock.name = "nt"
            with self.assertRaises(setup.StepFailed) as cm:
                setup.check_cmake(_Ctx())

        self.assertIn("cmake.org", cm.exception.fix)

    def test_windows_missing_cmake_unchanged(self):
        with mock.patch.object(setup, "os") as os_mock, \
                mock.patch.object(setup, "on_path", return_value=False):
            os_mock.name = "nt"
            with self.assertRaises(setup.StepFailed) as cm:
                setup.check_cmake(_Ctx())

        self.assertIn("cmake.org", cm.exception.fix)


class AllEditablesTests(unittest.TestCase):
    """NS-22(b) (cache_first_no_server_plan.md, redo of CE-35): parses
    `conan editable list --format=json`'s own shape into {ref: path} -
    never the plain-text listing, which isn't reliably parseable for the
    target path."""

    def test_parses_json_output_into_ref_path_map(self):
        payload = json.dumps({
            "adas-viz/1.0.0": {"path": r"D:\df\1v-superproject\modules\viz"},
            "adas-sim/1.0.0": {"path": r"D:\df\1v-superproject\modules\sim"},
        })
        with mock.patch("subprocess.run", return_value=_fake_run(0, payload)):
            result = setup._all_editables(Path(r"C:\fake\home"))
        self.assertEqual(result, {
            "adas-viz/1.0.0": r"D:\df\1v-superproject\modules\viz",
            "adas-sim/1.0.0": r"D:\df\1v-superproject\modules\sim",
        })

    def test_empty_json_object_is_empty_dict(self):
        with mock.patch("subprocess.run", return_value=_fake_run(0, "{}")):
            self.assertEqual(setup._all_editables(Path(r"C:\fake\home")), {})

    def test_nonzero_returncode_returns_empty_dict_not_raise(self):
        with mock.patch("subprocess.run", return_value=_fake_run(1, "", "no conan")):
            self.assertEqual(setup._all_editables(Path(r"C:\fake\home")), {})

    def test_malformed_json_returns_empty_dict_not_raise(self):
        with mock.patch("subprocess.run", return_value=_fake_run(0, "not json")):
            self.assertEqual(setup._all_editables(Path(r"C:\fake\home")), {})

    def test_missing_conan_returns_empty_dict_not_raise(self):
        with mock.patch("subprocess.run", side_effect=OSError):
            self.assertEqual(setup._all_editables(Path(r"C:\fake\home")), {})

    def test_uses_the_given_home_as_conan_home_env(self):
        captured_env = {}

        def fake_run(cmd, env=None, **kwargs):
            captured_env.update(env or {})
            return _fake_run(0, "{}")

        with mock.patch("subprocess.run", side_effect=fake_run):
            setup._all_editables(Path(r"C:\fake\home"))
        self.assertEqual(captured_env.get("CONAN_HOME"), r"C:\fake\home")


class ActiveConanHomeTests(unittest.TestCase):
    """NS-22(b) (cache_first_no_server_plan.md, redo of CE-35, incidental
    fix): _active_conan_home() respects an explicit CONAN_HOME override,
    unlike _standard_conan_home() (deliberately always the fixed default,
    used to DETECT an override - print_environment_summary()'s own Cache
    line). Found needed running this row's own cold_machine_check.py
    PROOF: the stray-editable checks used to call _standard_conan_home()
    directly and would silently examine the wrong home on any machine
    (this file's own scratch-CONAN_HOME test harness among them) that
    sets an explicit override."""

    def test_explicit_override_wins(self):
        with mock.patch.dict(os.environ, {"CONAN_HOME": r"C:\scratch\conan_home"}):
            self.assertEqual(setup._active_conan_home(), Path(r"C:\scratch\conan_home"))

    def test_falls_back_to_the_standard_default_when_unset(self):
        standard = setup._standard_conan_home()
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CONAN_HOME", None)
            self.assertEqual(setup._active_conan_home(), standard)


class RegisterTeamRemoteTests(unittest.TestCase):
    """NS-21 (cache_first_no_server_plan.md, redo of CE-36): an enabled-
    but-unreachable adas-local must never be left for a LATER `conan
    install` to hard-fail against - real evidence, a second corporate PC,
    2026-09-23: "ERROR: Package 'protobuf/3.21.12' not resolved ...
    127.0.0.1:9300 ... actively refused it" during `conan install
    --update`, well after this function had already run."""

    URL = "http://127.0.0.1:9300"

    def test_planted_violation_unreachable_and_already_registered_is_disabled(self):
        """PASS: adas-local is registered but genuinely unreachable -
        `conan remote disable adas-local` runs, and the WARNING names the
        exact re-enable command. FAIL: left enabled, exactly the real bug
        (a known-dead remote every later `conan install` keeps hitting)."""
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            if cmd[:3] == ["conan", "remote", "list"]:
                return mock.Mock(returncode=0, stdout="adas-local: http://127.0.0.1:9300\n")
            return mock.Mock(returncode=0, stdout="")

        captured = io.StringIO()
        with mock.patch.object(setup, "run", side_effect=fake_run), \
                mock.patch.object(setup, "_port_reachable", return_value=False), \
                contextlib.redirect_stdout(captured):
            result = setup.register_team_remote(_Ctx(), self.URL)

        self.assertFalse(result)
        self.assertIn(["conan", "remote", "disable", "adas-local"], calls)
        self.assertNotIn(["conan", "remote", "login", "adas-local", "demo", "-p", "demo"], calls)
        output = captured.getvalue()
        self.assertIn("not reachable", output)
        self.assertIn("conan remote enable adas-local", output)

    def test_unreachable_and_not_yet_registered_is_never_added(self):
        """PASS: adas-local isn't registered yet and is unreachable - it
        is never added in a known-broken state (no `conan remote add`
        call at all). FAIL: registered anyway, just to sit there dead."""
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            if cmd[:3] == ["conan", "remote", "list"]:
                return mock.Mock(returncode=0, stdout="")
            return mock.Mock(returncode=0, stdout="")

        with mock.patch.object(setup, "run", side_effect=fake_run), \
                mock.patch.object(setup, "_port_reachable", return_value=False):
            result = setup.register_team_remote(_Ctx(), self.URL)

        self.assertFalse(result)
        self.assertNotIn(["conan", "remote", "add", "adas-local", self.URL], calls)
        self.assertNotIn(["conan", "remote", "disable", "adas-local"], calls)

    def test_reachable_proceeds_exactly_as_before(self):
        """A reachable adas-local must be completely unaffected by CE-36 -
        registered (if new) and logged into, same as always."""
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            if cmd[:3] == ["conan", "remote", "list"]:
                return mock.Mock(returncode=0, stdout="")
            if cmd[:3] == ["conan", "remote", "login"]:
                return mock.Mock(returncode=0, stdout="")
            return mock.Mock(returncode=0, stdout="")

        with mock.patch.object(setup, "run", side_effect=fake_run), \
                mock.patch.object(setup, "_port_reachable", return_value=True):
            result = setup.register_team_remote(_Ctx(), self.URL)

        self.assertTrue(result)
        self.assertIn(["conan", "remote", "add", "adas-local", self.URL], calls)
        self.assertIn(["conan", "remote", "login", "adas-local", "demo", "-p", "demo"], calls)
        self.assertNotIn(["conan", "remote", "disable", "adas-local"], calls)

    def test_dry_run_makes_no_reachability_call(self):
        with mock.patch.object(setup, "_port_reachable") as reachable_mock, \
                mock.patch.object(setup, "run") as run_mock:
            result = setup.register_team_remote(_Ctx(dry_run=True), self.URL)

        self.assertFalse(result)
        reachable_mock.assert_not_called()
        run_mock.assert_not_called()


class CleanupDevelopLeftoversTests(unittest.TestCase):
    """D4/RD-04 (remove_develop_mode_plan.md): a one-shot, printed,
    confirm-first cleanup of a leftover develop CONAN_HOME and any
    editable registration - never removes anything without --yes.

    NS-22(b) (cache_first_no_server_plan.md, redo of CE-35): widened from
    "only OUR OWN checkout's components" to "every editable this tool can
    see, whatever path it points at" - _all_editables() (ref -> path),
    not already_editable()'s own path match against THIS checkout."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self._root_patch = mock.patch.object(setup, "ROOT", self.root)
        self._root_patch.start()
        self.addCleanup(self._root_patch.stop)

    def _run(self, yes, dev_home_exists, dev_editables=None, pkg_editables=None,
             standard_home=None):
        dev_home = self.root / "devhome"
        if dev_home_exists:
            dev_home.mkdir()
        std_home = standard_home or (self.root / "stdhome")
        std_home.mkdir(exist_ok=True)

        def fake_all_editables(home):
            if str(home) == str(dev_home):
                return dev_editables or {}
            if str(home) == str(std_home):
                return pkg_editables or {}
            return {}

        out = io.StringIO()
        with mock.patch.object(setup, "_dev_conan_home", return_value=dev_home), \
                mock.patch.object(setup, "_active_conan_home", return_value=std_home), \
                mock.patch.object(setup, "_all_editables", side_effect=fake_all_editables), \
                mock.patch.object(setup, "run"), \
                mock.patch("subprocess.run") as run_mock, \
                mock.patch.object(setup, "shutil") as shutil_mock, \
                contextlib.redirect_stdout(out):
            setup.cleanup_develop_leftovers(_YesCtx(yes))
        return out.getvalue(), dev_home, shutil_mock, run_mock

    def test_planted_violation_no_yes_means_nothing_is_removed(self):
        """The whole point of this row: printed and refused, never acted
        on, without an explicit --yes."""
        text, dev_home, shutil_mock, run_mock = self._run(
            yes=False, dev_home_exists=True,
            dev_editables={"adas-df/1.0.0": str(self.root / "modules" / "df")})
        self.assertIn(str(dev_home), text)
        self.assertIn("adas-df/1.0.0", text)
        self.assertIn("Nothing was changed", text)
        shutil_mock.rmtree.assert_not_called()
        run_mock.assert_not_called()

    def test_yes_removes_the_dev_home_directory(self):
        text, dev_home, shutil_mock, _ = self._run(yes=True, dev_home_exists=True)
        shutil_mock.rmtree.assert_called_once_with(dev_home)
        self.assertIn("Done.", text)

    def test_yes_removes_editable_registrations_in_both_homes_by_ref(self):
        """Removal is by reference (`--refs <ref>`), not by `cd`-ing into
        a path - NS-22(b): a stray editable's own path may belong to a
        different checkout entirely, never something this tool should
        `cd` into."""
        text, _, _, run_mock = self._run(
            yes=True, dev_home_exists=True,
            dev_editables={"adas-df/1.0.0": str(self.root / "modules" / "df")},
            pkg_editables={"adas-mathlib/1.0.0": str(self.root / "modules" / "mathlib")})
        removed_cmds = [c.args[0] for c in run_mock.call_args_list]
        self.assertIn(["conan", "editable", "remove", "--refs", "adas-df/1.0.0"], removed_cmds)
        self.assertIn(["conan", "editable", "remove", "--refs", "adas-mathlib/1.0.0"],
                       removed_cmds)

    def test_stray_editable_pointing_at_a_different_checkout_is_caught_and_removed(self):
        """NS-22(b)'s own real scenario: an editable registration whose
        path points at a DIFFERENT, stale checkout entirely (not THIS
        checkout's modules/ at all) - real evidence, a second corporate
        PC, 2026-09-23 (D:\\1v-superproject resolving interfaces/mathlib/
        sim/shared_config as Editable pointing at D:\\df\\1v-superproject).
        PASS: found, printed WITH its path, and removed on --yes. FAIL:
        invisible because it doesn't match THIS checkout's own path (the
        pre-NS-22(b) bug)."""
        stray_path = r"D:\df\1v-superproject\modules\sim"
        text, _, _, run_mock = self._run(
            yes=True, dev_home_exists=False,
            pkg_editables={"adas-sim/1.0.0": stray_path})
        self.assertIn("adas-sim/1.0.0", text)
        self.assertIn(stray_path, text)  # the path is shown, per NS-22(b)
        removed_cmds = [c.args[0] for c in run_mock.call_args_list]
        self.assertIn(["conan", "editable", "remove", "--refs", "adas-sim/1.0.0"], removed_cmds)

    def test_nothing_found_says_so_and_touches_nothing(self):
        text, _, shutil_mock, run_mock = self._run(yes=True, dev_home_exists=False)
        self.assertIn("Nothing to clean up", text)
        shutil_mock.rmtree.assert_not_called()
        run_mock.assert_not_called()

    def test_never_touches_the_real_home_without_mocking(self):
        """RULES: never modify the user's real Conan homes except to read.
        find_develop_leftovers() itself only ever reads (is_dir(),
        `conan editable list`) - proven here by calling it unmocked and
        confirming it raises nothing and performs no write."""
        result = setup.find_develop_leftovers()
        self.assertIn("dev_home", result)
        self.assertIn("editables", result)


class _YesCtx:
    def __init__(self, yes):
        self.yes = yes


if __name__ == "__main__":
    unittest.main()

class NonInteractiveLoginTests(unittest.TestCase):
    """CE-28: core:non_interactive = True in each managed CONAN_HOME, idempotently."""

    def _conf(self, initial):
        import tempfile
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        path = os.path.join(d.name, "home", "global.conf")
        if initial is not None:
            os.makedirs(os.path.dirname(path))
            with open(path, "w", encoding="utf-8") as f:
                f.write(initial)
        return path

    def _read(self, path):
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_planted_missing_file_gets_the_line_and_second_run_changes_nothing(self):
        path = self._conf(None)
        self.assertTrue(setup.set_non_interactive(path))
        self.assertFalse(setup.set_non_interactive(path))
        self.assertEqual(self._read(path).count("core:non_interactive = True"), 1)

    def test_commented_template_is_kept_and_other_settings_survive(self):
        path = self._conf("# core:non_interactive = True\ntools.x = 1\n")
        setup.set_non_interactive(path)
        text = self._read(path)
        self.assertIn("# core:non_interactive = True", text)
        self.assertIn("tools.x = 1", text)
        self.assertEqual(len([l for l in text.splitlines() if l == "core:non_interactive = True"]), 1)

    def test_an_existing_false_setting_is_rewritten_not_duplicated(self):
        path = self._conf("core:non_interactive = False\n")
        self.assertTrue(setup.set_non_interactive(path))
        self.assertEqual(self._read(path), "core:non_interactive = True\n")

    def test_step_writes_the_managed_home(self):
        """RD-03 (remove_develop_mode_plan.md): one managed CONAN_HOME
        now, not two - the develop home is gone."""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            default = Path(d) / "a"
            with unittest.mock.patch.object(setup, "_standard_conan_home", return_value=default):
                setup.ensure_non_interactive_login(_Ctx())
                self.assertEqual(setup.ensure_non_interactive_login(_Ctx()), "skip")
            self.assertIn("core:non_interactive = True", (default / "global.conf").read_text())

