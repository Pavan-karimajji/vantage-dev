"""
scripts/tests/test_setup_remotes_off_no_remotes.py

NS-45 (cache_first_no_server_plan.md D1, RQ-1/RQ-5) - `remotes off` must mean
EVERY remote off, conancenter included.

The real defect these tests pin, found by the user on 2026-09-25 running a
plain `setup.bat` against a genuinely empty Conan cache: `remotes_enabled()`
only ever governed `adas-local`, but Conan 2 re-creates `conancenter`,
ENABLED, in every fresh home. So a "remotes off" cold machine silently
downloaded lz4/zlib/protobuf from the internet rather than from
misc/offline_bundle/, and every cold-machine PASS to date happened to run on
a machine with working internet - so nothing caught it.

Also covers the two steps that made a plain `setup.bat` impossible to finish
with the network down (both hard-failed on PyPI/conancenter regardless of the
switch): ensure_https_trust() and ensure_conan_interpreter_trusts_https().

Pure unittest + unittest.mock, same convention as test_setup_prepare_cache.py
- every subprocess boundary mocked, no real conan/network/process calls.

Run:
    py -m unittest discover -s scripts/tests
    (from the superproject root)
"""
import contextlib
import inspect
import io
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import setup  # noqa: E402 - path must be set up first


def _fake_run(returncode=0, stdout="", stderr=""):
    result = mock.Mock()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


def _remote_list_json(remotes):
    """`conan remote list --format=json` payload. `remotes` is a list of
    (name, disabled) pairs, emitted in the shape real Conan 2 prints - an
    `enabled` key (verified against Conan 2.32, 2026-09-28). The fixture
    once emitted `disabled`, which no Conan prints, so the tests passed
    while every real run reported `STILL ENABLED` for a disabled remote."""
    return json.dumps([{"name": name, "url": "http://x", "verify_ssl": True,
                        "enabled": not disabled} for name, disabled in remotes])


class _Ctx:
    def __init__(self, remotes_enabled=False, dry_run=False):
        self.remotes_enabled = remotes_enabled
        self.remotes_reason = "test"
        self.dry_run = dry_run


def _conan_commands(run_mock):
    """Every `conan ...` argv actually issued, as lists."""
    return [call.args[0] for call in run_mock.call_args_list
            if call.args and isinstance(call.args[0], list)
            and call.args[0][:1] == ["conan"]]


class SyncRemoteEnablementOffTests(unittest.TestCase):
    """Remotes off -> every remote disabled, conancenter included."""

    def test_disables_every_remote_including_conancenter(self):
        listing = _remote_list_json([("conancenter", False), ("adas-local", True)])
        with mock.patch.object(setup, "run") as run_mock:
            after = _remote_list_json([("conancenter", True), ("adas-local", True)])
            run_mock.side_effect = [_fake_run(stdout=listing), _fake_run(),
                                    _fake_run(stdout=after)]
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                setup.sync_remote_enablement(_Ctx(remotes_enabled=False))
        cmds = _conan_commands(run_mock)
        self.assertIn(["conan", "remote", "disable", "*"], cmds,
                      "remotes off must disable EVERY remote (D1) - this is the "
                      "defect NS-45 closes: conancenter stayed enabled and served "
                      "third-party from the internet on a 'cold' machine")
        out = buf.getvalue()
        self.assertIn("conancenter", out)
        self.assertIn("misc/offline_bundle/", out,
                      "the message must name where third-party comes from instead "
                      "(RQ-9: a failure/decision names the alternative)")
        self.assertNotIn("STILL ENABLED", out)

    def test_summary_is_observed_not_asserted(self):
        """NS-57: if Conan still reports a remote enabled after the disable,
        the summary says so rather than printing `disabled` regardless."""
        listing = _remote_list_json([("conancenter", False)])
        stuck = _remote_list_json([("conancenter", False)])
        with mock.patch.object(setup, "run") as run_mock:
            run_mock.side_effect = [_fake_run(stdout=listing), _fake_run(),
                                    _fake_run(stdout=stuck)]
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                setup.sync_remote_enablement(_Ctx(remotes_enabled=False))
        self.assertIn("conancenter: STILL ENABLED", buf.getvalue())

    def test_already_all_disabled_is_a_noop(self):
        listing = _remote_list_json([("conancenter", True), ("adas-local", True)])
        with mock.patch.object(setup, "run") as run_mock:
            run_mock.side_effect = [_fake_run(stdout=listing)]
            with contextlib.redirect_stdout(io.StringIO()):
                result = setup.sync_remote_enablement(_Ctx(remotes_enabled=False))
        self.assertEqual(result, "skip")
        self.assertNotIn(["conan", "remote", "disable", "*"],
                         _conan_commands(run_mock),
                         "idempotent: a second remotes-off run must not re-issue "
                         "the disable")

    def test_no_remotes_defined_is_a_noop(self):
        with mock.patch.object(setup, "run") as run_mock:
            run_mock.side_effect = [_fake_run(stdout="[]")]
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                setup.sync_remote_enablement(_Ctx(remotes_enabled=False))
        self.assertNotIn(["conan", "remote", "disable", "*"],
                         _conan_commands(run_mock))
        self.assertIn("nothing to disable", buf.getvalue())

    def test_failed_listing_degrades_to_no_remotes(self):
        with mock.patch.object(setup, "run") as run_mock:
            run_mock.side_effect = [_fake_run(returncode=1, stdout="boom")]
            with contextlib.redirect_stdout(io.StringIO()):
                setup.sync_remote_enablement(_Ctx(remotes_enabled=False))
        self.assertNotIn(["conan", "remote", "disable", "*"],
                         _conan_commands(run_mock),
                         "a broken listing must not raise, and must not pretend "
                         "to have disabled anything")

    def test_dry_run_makes_no_calls(self):
        with mock.patch.object(setup, "run") as run_mock:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                result = setup.sync_remote_enablement(
                    _Ctx(remotes_enabled=False, dry_run=True))
        self.assertEqual(result, "skip")
        run_mock.assert_not_called()
        self.assertIn("remote disable", buf.getvalue())


class SyncRemoteEnablementOnTests(unittest.TestCase):
    """Remotes on -> the disable an earlier off-run wrote is undone (RQ-3)."""

    def test_re_enables_owned_remotes_left_disabled(self):
        listing = _remote_list_json([("conancenter", True), ("adas-local", True)])
        with mock.patch.object(setup, "run") as run_mock:
            after = _remote_list_json([("conancenter", False), ("adas-local", False)])
            run_mock.side_effect = [_fake_run(stdout=listing), _fake_run(), _fake_run(),
                                    _fake_run(stdout=after)]
            with contextlib.redirect_stdout(io.StringIO()):
                setup.sync_remote_enablement(_Ctx(remotes_enabled=True))
        cmds = _conan_commands(run_mock)
        self.assertIn(["conan", "remote", "enable", "conancenter"], cmds,
                      "RQ-3: a leftover disable from an earlier remotes-off run "
                      "must not silently decide that --remotes on cannot download")
        self.assertIn(["conan", "remote", "enable", "adas-local"], cmds)

    def test_never_re_enables_a_remote_we_do_not_own(self):
        listing = _remote_list_json([("conancenter", True), ("mycorp-mirror", True)])
        after = _remote_list_json([("conancenter", False), ("mycorp-mirror", True)])
        with mock.patch.object(setup, "run") as run_mock:
            run_mock.side_effect = [_fake_run(stdout=listing), _fake_run(),
                                    _fake_run(stdout=after)]
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                setup.sync_remote_enablement(_Ctx(remotes_enabled=True))
        cmds = _conan_commands(run_mock)
        out = buf.getvalue()
        # NS-57 (RV-8): named, with the command, but not acted on.
        self.assertIn("mycorp-mirror", out.split("not ours to re-enable")[-1])
        self.assertIn("conan remote enable mycorp-mirror", out)
        self.assertIn("conancenter: enabled", out)
        self.assertIn(["conan", "remote", "enable", "conancenter"], cmds)
        self.assertNotIn(["conan", "remote", "enable", "mycorp-mirror"], cmds,
                         "we did not create a hand-added remote, so we do not get "
                         "to decide it should come back")

    def test_foreign_disabled_is_named_even_when_ours_need_nothing(self):
        listing = _remote_list_json([("conancenter", False), ("mycorp-mirror", True)])
        with mock.patch.object(setup, "run") as run_mock:
            run_mock.side_effect = [_fake_run(stdout=listing)]
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                result = setup.sync_remote_enablement(_Ctx(remotes_enabled=True))
        self.assertEqual(result, "skip")
        self.assertIn("conan remote enable mycorp-mirror", buf.getvalue())
        self.assertNotIn(["conan", "remote", "enable", "mycorp-mirror"],
                         _conan_commands(run_mock))

    def test_nothing_disabled_is_a_noop(self):
        listing = _remote_list_json([("conancenter", False)])
        with mock.patch.object(setup, "run") as run_mock:
            run_mock.side_effect = [_fake_run(stdout=listing)]
            with contextlib.redirect_stdout(io.StringIO()):
                result = setup.sync_remote_enablement(_Ctx(remotes_enabled=True))
        self.assertEqual(result, "skip")
        self.assertEqual(
            [c for c in _conan_commands(run_mock) if c[1:3] == ["remote", "enable"]],
            [])

    def test_missing_attribute_defaults_to_remotes_on(self):
        """Upgrade safety: a ctx predating ctx.remotes_enabled keeps today's
        behaviour rather than silently disabling a working machine's remotes."""
        class _Bare:
            dry_run = False

        listing = _remote_list_json([("conancenter", False)])
        with mock.patch.object(setup, "run") as run_mock:
            run_mock.side_effect = [_fake_run(stdout=listing)]
            with contextlib.redirect_stdout(io.StringIO()):
                setup.sync_remote_enablement(_Bare())
        self.assertNotIn(["conan", "remote", "disable", "*"],
                         _conan_commands(run_mock))


class OfflineCapableTlsStepsTests(unittest.TestCase):
    """The two steps that made a plain `setup.bat` impossible with Wi-Fi off."""

    def test_conan_interpreter_trust_skipped_when_remotes_off(self):
        with mock.patch.object(setup, "run") as run_mock, \
             mock.patch.object(setup.shutil, "which") as which_mock:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                result = setup.ensure_conan_interpreter_trusts_https(
                    _Ctx(remotes_enabled=False))
        self.assertEqual(result, "skip")
        which_mock.assert_not_called()
        run_mock.assert_not_called()
        self.assertNotIn("conancenter TLS", buf.getvalue())

    def test_https_trust_is_not_fatal_with_remotes_off(self):
        """A disconnected machine fails this pip install for the most ordinary
        reason there is. Aborting there is what made RQ-1 unreachable."""
        with mock.patch.object(setup, "run") as run_mock, \
             mock.patch.object(setup, "_tls_handshake_ok") as handshake:
            run_mock.return_value = _fake_run(
                returncode=1, stdout="Could not find a version that satisfies ...")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                try:
                    setup.ensure_https_trust(_Ctx(remotes_enabled=False))
                except setup.StepFailed as exc:
                    self.fail("remotes off must not make a failed pip install "
                              f"fatal (NS-45/RQ-1); raised: {exc}")
        self.assertIn("NOT fatal", buf.getvalue())
        handshake.assert_not_called()

    def test_https_trust_still_fatal_with_remotes_on(self):
        """Regression guard: the remotes-ON path keeps today's behaviour."""
        with mock.patch.object(setup, "run") as run_mock:
            run_mock.return_value = _fake_run(
                returncode=1, stdout="CERTIFICATE_VERIFY_FAILED")
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(setup.StepFailed):
                    setup.ensure_https_trust(_Ctx(remotes_enabled=True))

    def test_https_trust_skips_the_handshake_when_remotes_off(self):
        with mock.patch.object(setup, "run") as run_mock, \
             mock.patch.object(setup, "_tls_handshake_ok") as handshake:
            run_mock.return_value = _fake_run(returncode=0)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                setup.ensure_https_trust(_Ctx(remotes_enabled=False))
        handshake.assert_not_called()
        self.assertIn("skipping the conancenter TLS handshake", buf.getvalue())


class StepOrderTests(unittest.TestCase):
    """The disable must happen before anything can resolve a package."""

    def test_remote_sync_registered_before_the_conancenter_trust_step(self):
        src = inspect.getsource(setup.main)
        sync_at = src.find("sync_remote_enablement")
        trust_at = src.find("ensure_conan_interpreter_trusts_https")
        prepare_at = src.find("prepare_conan_cache")
        self.assertNotEqual(sync_at, -1,
                            "the remote-sync step must be registered in main()")
        self.assertLess(sync_at, trust_at,
                        "must run before the step that contacts conancenter")
        self.assertLess(sync_at, prepare_at,
                        "must run before anything that resolves a package")
