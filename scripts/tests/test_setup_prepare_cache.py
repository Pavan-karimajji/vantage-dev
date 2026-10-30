"""
scripts/tests/test_setup_prepare_cache.py

WP-2/NS-11 (cache_first_no_server_plan.md D2/D4b) - scripts/setup.py::
prepare_conan_cache(): the cache-fill step that replaces "reach for a
server" with "fill the cache from the checkout, then the bundle". Pure
unittest + unittest.mock, same convention as test_setup_conan_environment.py
- every subprocess boundary mocked, no real conan/network/process calls.

Run:
    py -m unittest discover -s scripts/tests
    (from the superproject root)
"""
import contextlib
import io
import json
import os
import sys
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


def _cache_list_json(cached_refs):
    """A `conan list <ref> --format=json` payload as if `ref` (and only
    `ref`) were in the local cache, keyed under "Local Cache" - matches
    what a real `conan list` call reports for a single-ref query."""
    return json.dumps({"Local Cache": {ref: {} for ref in cached_refs}})


class _Ctx:
    def __init__(self, dry_run=False, build_missing_from_source=False):
        self.dry_run = dry_run
        self.build_missing_from_source = build_missing_from_source


class RefCachedTests(unittest.TestCase):
    """_ref_cached() deliberately calls subprocess.run() directly, NOT this
    file's own run(..., capture=True) - that helper merges stderr into
    stdout, and a real `conan list --format=json` prints an informational
    line to stderr that breaks JSON parsing when merged (real bug, found
    running this for real - see _ref_cached()'s own docstring). Mocking
    subprocess.run() here matches the real call site, and would have
    caught that bug immediately if it had been written this way from the
    start."""

    def test_ref_in_local_cache_key_is_cached(self):
        with mock.patch("subprocess.run",
                         return_value=_fake_run(0, _cache_list_json(["adas-toolchain/1.0.4"]))):
            self.assertTrue(setup._ref_cached("adas-toolchain/1.0.4"))

    def test_ref_not_present_is_not_cached(self):
        with mock.patch("subprocess.run",
                         return_value=_fake_run(0, _cache_list_json([]))):
            self.assertFalse(setup._ref_cached("adas-toolchain/1.0.4"))

    def test_conan_list_failure_is_not_cached(self):
        with mock.patch("subprocess.run", return_value=_fake_run(1, "", "boom")):
            self.assertFalse(setup._ref_cached("adas-toolchain/1.0.4"))

    def test_planted_stderr_informational_line_does_not_break_parsing(self):
        """Planted violation for the real bug this function's docstring
        describes: a real `conan list --format=json` combined/merged
        transcript (informational line ahead of the JSON) must never be
        what _ref_cached() parses - it calls subprocess.run() with
        separate streams precisely to avoid this. Simulated here by
        asserting the JSON-only stdout (what capture_output=True actually
        hands back) parses correctly even though a real merged capture of
        the same command would not."""
        json_only_stdout = _cache_list_json(["adas-build-tools/1.0.19"])
        with mock.patch("subprocess.run",
                         return_value=_fake_run(0, json_only_stdout,
                                                 stderr="Found 1 pkg/version recipes "
                                                        "matching adas-build-tools/1.0.19 "
                                                        "in local cache\n")):
            self.assertTrue(setup._ref_cached("adas-build-tools/1.0.19"))


class PrepareConanCacheTests(unittest.TestCase):

    def setUp(self):
        self.toolchain_dir_patch = mock.patch.object(
            setup, "ROOT", Path("/repo"))
        self.toolchain_dir_patch.start()
        self.addCleanup(self.toolchain_dir_patch.stop)
        # D14: never let the real checkout's bundle layout decide these tests.
        layout = mock.patch.object(setup, "host_bundle_dir", return_value=None)
        layout.start()
        self.addCleanup(layout.stop)

    def _run_prepare(self, ctx, cached_refs, toolchain_ref="adas-toolchain/1.0.4",
                      build_tools_ref="adas-build-tools/1.0.19", conanfile_exists=True,
                      bundle_exists=False, export_ok=True, create_ok=True):
        cached = set(cached_refs)

        def fake_run(cmd, **kwargs):
            # export/create go through setup.run() - _ref_cached() itself
            # calls subprocess.run() directly (see fake_subprocess_run).
            if cmd[:2] == ["conan", "export"]:
                if export_ok:
                    cached.add(toolchain_ref)
                    return _fake_run(0)
                return _fake_run(1, "", "export failed")
            if cmd[:2] == ["conan", "create"]:
                if create_ok:
                    cached.add(build_tools_ref)
                    return _fake_run(0)
                return _fake_run(1, "", "create failed")
            return _fake_run(0)

        def fake_subprocess_run(cmd, **kwargs):
            assert cmd[:2] == ["conan", "list"], cmd
            ref = cmd[2]
            present = [ref] if ref in cached else []
            return _fake_run(0, _cache_list_json(present))

        with mock.patch.object(setup, "run", side_effect=fake_run), \
                mock.patch("subprocess.run", side_effect=fake_subprocess_run), \
                mock.patch.object(setup.check_conan_resolution,
                                   "discover_python_requires_refs",
                                   return_value={toolchain_ref}), \
                mock.patch.object(setup.check_conan_resolution,
                                   "discover_build_tools_refs",
                                   return_value={build_tools_ref}), \
                mock.patch.object(Path, "is_file", return_value=conanfile_exists), \
                mock.patch.object(Path, "is_dir", return_value=bundle_exists), \
                mock.patch.object(Path, "mkdir"), \
                mock.patch.object(setup, "record_prepared_module") as record_mock:
            self.record_mock = record_mock
            return setup.prepare_conan_cache(ctx)

    def test_export_runs_when_toolchain_ref_not_cached(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self._run_prepare(_Ctx(), cached_refs=[])
        self.assertIn("conan export", buf.getvalue())
        self.assertIn("running conan create", buf.getvalue())

    def test_fresh_export_records_a_fingerprint(self):
        """NS-05a (cache_first_no_server_plan.md D4a, STEP 3): 'the
        export/create in prepare_conan_cache' is one of the two places
        this file records a fingerprint (the other is STEP 1's
        --prepare) - only for a REAL export, never an 'already cached'
        skip (test_export_skipped_... below)."""
        self._run_prepare(_Ctx(), cached_refs=[])
        self.record_mock.assert_called_once()
        args = self.record_mock.call_args[0]
        self.assertEqual(args[1], "toolchain")
        self.assertEqual(args[2], "adas-toolchain/1.0.4")

    def test_export_skipped_when_toolchain_ref_already_cached(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self._run_prepare(_Ctx(), cached_refs=["adas-toolchain/1.0.4",
                                                     "adas-build-tools/1.0.19"])
        self.assertIn("adas-toolchain/1.0.4: already cached - conan export skipped.",
                       buf.getvalue())
        self.assertIn("adas-build-tools/1.0.19: already cached - conan create skipped.",
                       buf.getvalue())
        self.assertNotIn("running conan export", buf.getvalue())
        self.assertNotIn("running conan create", buf.getvalue())
        self.record_mock.assert_not_called()

    def test_second_run_is_a_no_op_once_both_are_cached(self):
        """WP-2 §2b: 'the build-tools pin is created only when absent; a
        second run is a no-op.' Simulated here as one call with both refs
        pre-cached (equivalent to 'after the first run filled them')."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self._run_prepare(_Ctx(), cached_refs=["adas-toolchain/1.0.4",
                                                     "adas-build-tools/1.0.19"])
        self.assertNotIn("running conan export", buf.getvalue())
        self.assertNotIn("running conan create", buf.getvalue())

    def test_planted_neither_cached_nor_bundled_fails_naming_ref_and_setup_bat(self):
        """WP-2 §2b planted criterion."""
        with self.assertRaises(setup.StepFailed) as ctx_mgr:
            self._run_prepare(_Ctx(), cached_refs=[], export_ok=False, create_ok=False,
                               bundle_exists=False)
        exc = ctx_mgr.exception
        self.assertIn("adas-toolchain/1.0.4", str(exc))
        self.assertIn("adas-build-tools/1.0.19", str(exc))
        self.assertIn("setup.bat", exc.fix)

    def test_dry_run_makes_no_real_calls(self):
        with mock.patch.object(setup, "run") as run_mock, \
                mock.patch.object(Path, "is_dir", return_value=False):
            outcome = setup.prepare_conan_cache(_Ctx(dry_run=True))
        run_mock.assert_not_called()
        self.assertEqual(outcome, "skip")


class PrepareConanCacheBundleRestoreTests(PrepareConanCacheTests):
    """NS-40: third-party refs are restored from the bundle whether or not
    either pin's own export/create succeeded."""

    PINS = {"third_party": ["protobuf/3.21.12", "zlib/1.3.1"], "third_party_tool": [],
            "toolchain": ["adas-toolchain/1.0.4"], "build_tools": ["adas-build-tools/1.0.19"]}

    def _prepare_with_bundle(self, cached_refs, pins=None, **kw):
        import make_offline_bundle as mob
        with mock.patch.object(setup, "restore_missing_refs_from_bundle",
                                return_value=set()) as restore_mock, \
                mock.patch.object(mob, "derive_pins", return_value=pins or self.PINS):
            self._run_prepare(_Ctx(), cached_refs=cached_refs, bundle_exists=True, **kw)
        return restore_mock

    def test_pins_create_cleanly_and_third_party_absent_bundle_is_restored(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            restore_mock = self._prepare_with_bundle(cached_refs=[])
        self.assertIn("running conan create", buf.getvalue())  # not failure-triggered
        restore_mock.assert_called_once()
        self.assertEqual(sorted(restore_mock.call_args[0][1]),
                         ["adas-build-tools/1.0.19", "adas-toolchain/1.0.4",
                          "protobuf/3.21.12", "zlib/1.3.1"])

    def test_bundle_present_always_calls_restore_regardless_of_cache_state(self):
        """NS-41: the caller no longer pre-filters to what ITS OWN narrow
        `needed` derivation thinks is absent before deciding whether to call
        the restore function at all -- that gate is exactly what let a
        transitive ref (zlib behind protobuf) go unconsidered whenever
        every DIRECT ref happened to already be cached, since the restore
        function was then never even invoked. The call is now unconditional
        whenever a bundle is present; restore_missing_refs_from_bundle()
        itself (tested directly in test_offline_bundle_automatic.py,
        including the true 'nothing physically restored when already
        cached' case) decides, from its own manifest's ref list, what
        actually needs restoring."""
        restore_mock = self._prepare_with_bundle(
            cached_refs=["protobuf/3.21.12", "zlib/1.3.1"])
        restore_mock.assert_called_once()

    def test_needed_refs_are_derived_not_hard_coded(self):
        pins = dict(self.PINS, third_party=self.PINS["third_party"] + ["newlib/9.9.9"])
        restore_mock = self._prepare_with_bundle(cached_refs=[], pins=pins)
        self.assertIn("newlib/9.9.9", restore_mock.call_args[0][1])

    def test_derivation_reads_a_real_conf_build_yml(self):
        """The derivation itself, end to end: a ref added to a fake
        conf/build.yml shows up (make_offline_bundle.derive_pins, unmocked)."""
        import tempfile
        import make_offline_bundle as mob
        with tempfile.TemporaryDirectory() as tmp:
            conf = Path(tmp) / "modules" / "m" / "conf"
            conf.mkdir(parents=True)
            (conf / "build.yml").write_text(
                "requires:\n  - protobuf/3.21.12\n  - adas-sim/1.0.0\n"
                "tool_requires:\n  - cmake/3.28.1\n", encoding="utf-8")
            first = mob.all_pin_refs(mob.derive_pins(tmp))
            (conf / "build.yml").write_text(
                "requires:\n  - protobuf/3.21.12\n  - freshlib/2.0.0\n", encoding="utf-8")
            second = mob.all_pin_refs(mob.derive_pins(tmp))
        self.assertEqual(first, ["cmake/3.28.1", "protobuf/3.21.12"])
        self.assertIn("freshlib/2.0.0", second)


if __name__ == "__main__":
    unittest.main()
