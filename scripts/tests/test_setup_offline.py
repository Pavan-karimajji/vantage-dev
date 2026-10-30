"""scripts/tests/test_setup_offline.py

OF-04 / OF-05 (offline_setup_plan.md): `scripts/setup.py --offline <dir>`.
Pure unittest + mock; every subprocess/pip/conan boundary is mocked, so no
network call is possible here - the tests also assert none is attempted.

Run:
    python -m unittest discover -s scripts/tests   (from the superproject root)
"""
import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import make_offline_bundle as mob  # noqa: E402
import setup  # noqa: E402

PINS = {"third_party": ["protobuf/3.21.12"], "third_party_tool": [],
        "toolchain": ["adas-toolchain/1.0.4"], "build_tools": ["adas-build-tools/1.0.17"]}
ALL_REFS = [("adas-build-tools/1.0.17", "r3", 1), ("adas-toolchain/1.0.4", "r2", 0),
            ("protobuf/3.21.12", "r1", 2)]


class _Ctx:
    def __init__(self, offline, dry_run=False):
        self.offline = str(offline)
        self.dry_run = dry_run
        self.yes = True


def _bundle(root, platform="vs2026", saved=ALL_REFS, wheels=True, archive=True):
    root = Path(root)
    (root / "bundle_manifest.txt").write_text(
        mob.manifest_text(platform, "2026-09-21", "abc12345", "Conan version 2.32.0", saved, PINS,
                          ["conan-2.32.0-py3-none-any.whl"]), encoding="utf-8")
    if archive:
        (root / f"adas_offline_{platform}_2026-09-21.tgz").write_bytes(b"x")
    if wheels:
        (root / "wheels").mkdir()
    return root


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name


class CheckOfflineBundleTests(_Base):

    def test_planted_violation_platform_mismatch_is_refused_by_name(self):
        _bundle(self.dir, platform="ubuntu_gcc")
        with mock.patch.object(setup, "offline_platform", return_value="vs2026"):
            with self.assertRaises(setup.StepFailed) as cm:
                setup.check_offline_bundle(_Ctx(self.dir))
        self.assertIn("'ubuntu_gcc'", cm.exception.reason)
        self.assertIn("'vs2026'", cm.exception.reason)

    def test_matching_platform_passes(self):
        _bundle(self.dir)
        with mock.patch.object(setup, "offline_platform", return_value="vs2026"), \
                contextlib.redirect_stdout(io.StringIO()):
            setup.check_offline_bundle(_Ctx(self.dir))

    def test_a_folder_that_is_not_a_bundle_is_refused(self):
        with self.assertRaises(setup.StepFailed):
            setup.load_offline_bundle(self.dir)                    # no manifest
        _bundle(self.dir, archive=False)
        with self.assertRaises(setup.StepFailed):
            setup.load_offline_bundle(self.dir)                    # no archive

    def test_a_bundle_without_wheels_is_refused(self):
        _bundle(self.dir, wheels=False)
        with self.assertRaises(setup.StepFailed):
            setup.load_offline_bundle(self.dir)


class CheckOfflinePinsTests(_Base):

    def test_planted_violation_a_pin_missing_from_the_manifest_is_refused(self):
        _bundle(self.dir, saved=[("protobuf/3.21.12", "r1", 2)])   # toolchain + build-tools absent
        with mock.patch.object(mob, "derive_pins", return_value=PINS):
            with self.assertRaises(setup.StepFailed) as cm:
                setup.check_offline_pins(_Ctx(self.dir))
        self.assertIn("adas-build-tools/1.0.17", cm.exception.reason)
        self.assertIn("adas-toolchain/1.0.4", cm.exception.reason)

    def test_complete_bundle_passes(self):
        _bundle(self.dir)
        with mock.patch.object(mob, "derive_pins", return_value=PINS):
            setup.check_offline_pins(_Ctx(self.dir))


class RestoreOfflineCacheTests(_Base):

    def _restore(self, remotes_json, url="http://127.0.0.1:9300", dry_run=False):
        _bundle(self.dir)
        calls, kwargs_by_call = [], []

        def fake_run(cmd, cwd=None, check=True, capture=False, timeout=None, merge_stderr=True):
            calls.append(list(cmd))
            kwargs_by_call.append({"check": check, "capture": capture, "merge_stderr": merge_stderr})
            return mock.Mock(returncode=0, stdout=remotes_json if cmd[:3] == ["conan", "remote", "list"] else "")

        with mock.patch.object(setup, "run", side_effect=fake_run), \
                mock.patch.object(setup, "read_team_server_url", return_value=url), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            setup.restore_offline_cache(_Ctx(self.dir, dry_run=dry_run))
        self.last_kwargs = kwargs_by_call
        return calls, out.getvalue()

    def test_restores_defines_adas_local_then_disables_every_remote(self):
        """OF-02: adas-local must be DEFINED-but-disabled, and the disable comes last."""
        calls, out = self._restore('[{"name": "conancenter"}]')
        cmds = [c[:3] for c in calls]
        self.assertEqual(cmds[0], ["conan", "cache", "restore"])
        self.assertIn(["conan", "remote", "add", "adas-local", "http://127.0.0.1:9300"], calls)
        self.assertEqual(calls[-1], ["conan", "remote", "disable", "*"])
        self.assertIn("protobuf/3.21.12#r1", out)

    def test_remote_list_discards_stderr_so_a_stray_warning_cant_break_the_json_parse(self):
        """A real machine's ambient Python can print a warning (e.g. an
        outdated urllib3/chardet pairing) on stderr during `conan remote
        list --format=json` -- found live on WSL, 2026-10-04, where that
        warning broke the JSON parse and made restore_offline_cache
        re-add an already-registered adas-local, failing the whole step."""
        calls, _ = self._restore('[{"name": "conancenter"}, {"name": "adas-local"}]')
        listing_call_index = next(i for i, c in enumerate(calls) if c[:3] == ["conan", "remote", "list"])
        self.assertFalse(self.last_kwargs[listing_call_index]["merge_stderr"])

    def test_planted_violation_no_network_command_is_ever_issued(self):
        calls, _ = self._restore('[{"name": "conancenter"}]')
        flat = [" ".join(c) for c in calls]
        for banned in ("download", "install", "upload", "search", " -r "):
            self.assertFalse([c for c in flat if banned in c], banned)

    def test_an_existing_adas_local_is_not_re_added(self):
        calls, _ = self._restore('[{"name": "conancenter"}, {"name": "adas-local"}]')
        self.assertFalse([c for c in calls if c[:3] == ["conan", "remote", "add"]])

    def test_dry_run_runs_nothing(self):
        calls, out = self._restore("[]", dry_run=True)
        self.assertEqual(calls, [])
        self.assertIn("[dry-run] would run: conan cache restore", out)


class InstallOfflineWheelsTests(_Base):

    def test_uses_no_index_and_the_bundle_wheels_only(self):
        _bundle(self.dir)
        with mock.patch.object(setup, "on_path", side_effect=[False, True]), \
                mock.patch.object(setup, "run") as run:
            setup.install_offline_wheels(_Ctx(self.dir))
        cmd = run.call_args.args[0]
        self.assertIn("--no-index", cmd)
        self.assertEqual(cmd[cmd.index("--find-links") + 1], str(Path(self.dir) / "wheels"))

    def test_planted_violation_conan_present_but_pyyaml_missing_is_not_skipped(self):
        """PASS: the wheels are installed when PyYAML is absent. FAIL (conan-only
        check): setup went on without PyYAML and the pin check crashed."""
        _bundle(self.dir)
        with mock.patch.object(setup, "on_path", return_value=True), \
                mock.patch.object(setup.importlib.util, "find_spec", return_value=None), \
                mock.patch.object(setup, "run") as run:
            setup.install_offline_wheels(_Ctx(self.dir))
        run.assert_called_once()

    def test_skipped_when_conan_is_already_installed(self):
        _bundle(self.dir)
        with mock.patch.object(setup, "on_path", return_value=True), \
                mock.patch.object(setup, "run") as run:
            self.assertEqual(setup.install_offline_wheels(_Ctx(self.dir)), "skip")
        run.assert_not_called()


class OfflineSetupOrderTests(_Base):

    def test_step_order_and_no_online_step(self):
        """The offline run touches none of the online steps (HTTPS trust, server
        on-demand, dependency configuration, resolution check)."""
        seen = []
        with mock.patch.object(setup, "step", side_effect=lambda ctx, name, fn: seen.append(fn.__name__)), \
                contextlib.redirect_stdout(io.StringIO()):
            setup.offline_setup(_Ctx(self.dir))
        self.assertEqual(seen, ["check_offline_bundle", "check_git", "check_visual_studio",
                                "install_offline_wheels", "check_offline_pins",
                                "ensure_conan_profile", "ensure_non_interactive_login",
                                "restore_offline_cache", "ensure_python_tool_envs"])
        for online in ("ensure_https_trust", "ensure_server_running", "configure_conan_dependencies",
                       "ensure_resolution_complete", "init_submodules", "check_or_install_conan"):
            self.assertNotIn(online, seen)

    def test_cli_flag_reaches_offline_setup_and_skips_the_online_steps(self):
        with mock.patch.object(sys, "argv", ["setup.py", "--offline", self.dir, "--dry-run"]), \
                mock.patch.object(setup, "offline_setup") as offline, \
                mock.patch.object(setup, "step") as online_step, \
                contextlib.redirect_stdout(io.StringIO()):
            setup.main()
        offline.assert_called_once()
        online_step.assert_not_called()   # not even the HTTPS-trust step

    def test_offline_with_role_server_is_refused(self):
        with mock.patch.object(sys, "argv", ["setup.py", "--offline", self.dir, "--role", "server"]), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                setup.main()

    def test_rd13_bare_flag_defaults_to_misc_offline_bundle(self):
        """RD-13 (remove_develop_mode_plan.md): `--offline` with NO
        BUNDLE_DIR resolves to misc/offline_bundle - the same location
        make_offline_bundle.py writes to by default (DEFAULT_OUT there).
        Planted violation: without `nargs="?"`/`const=`, argparse would
        either require a value (SystemExit, caught by the assertRaises
        this test does NOT wrap around) or leave ctx.offline unset/None
        (offline_setup never called)."""
        with mock.patch.object(sys, "argv", ["setup.py", "--offline", "--dry-run"]), \
                mock.patch.object(setup, "offline_setup") as offline_mock, \
                contextlib.redirect_stdout(io.StringIO()):
            setup.main()

        offline_mock.assert_called_once()
        ctx = offline_mock.call_args[0][0]
        self.assertEqual(Path(ctx.offline), setup.DEFAULT_OFFLINE_BUNDLE_DIR)

    def test_rd13_default_matches_make_offline_bundle_own_default(self):
        """The two tools' defaults must never drift apart by hand-typing
        the same path twice - setup.py's default is derived from the same
        misc/offline_bundle spelling make_offline_bundle.DEFAULT_OUT uses."""
        self.assertEqual(setup.DEFAULT_OFFLINE_BUNDLE_DIR,
                          setup.ROOT / mob.DEFAULT_OUT)


if __name__ == "__main__":
    unittest.main()
