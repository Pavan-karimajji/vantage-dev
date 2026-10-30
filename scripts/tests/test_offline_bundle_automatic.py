"""
scripts/tests/test_offline_bundle_automatic.py

WP-3/NS-04 (cache_first_no_server_plan.md D2): scripts/setup.py::
restore_missing_refs_from_bundle() - misc/offline_bundle/ used
automatically (no --offline flag), only refs missing from the cache are
restored, a bundle missing a pinned ref is reported (not fatal) when the
rest still resolves, and a wrong-platform bundle is still refused
(existing OF-04 contract, unchanged).

The restore mechanism itself (restore_missing_refs_from_bundle(),
prepare_conan_cache()'s own call into it) landed in the WP-2 commit -
NS-11's own preparation step order names "restore from the bundle" as
its step 3, and both plan rows (NS-04, NS-11) are satisfied by the one
function tested directly here. This file is WP-3's own dedicated test
coverage for that function's contract, kept separate per work package.

Run:
    py -m unittest discover -s scripts/tests
    (from the superproject root)
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
import setup  # noqa: E402 - path must be set up first
import make_offline_bundle as mob  # noqa: E402


def _write_fake_bundle(bundle_dir, platform, refs, with_wheels=True):
    """A minimal folder shaped like scripts/make_offline_bundle.py's real
    output: one archive, a wheels/ folder, and a manifest listing `refs`
    (a dict of {bare ref: revision})."""
    bundle_dir.mkdir(parents=True, exist_ok=True)
    archive = bundle_dir / f"adas_offline_{platform}_2026-09-23.tgz"
    archive.write_bytes(b"fake-tgz")
    if with_wheels:
        (bundle_dir / "wheels").mkdir(exist_ok=True)
    saved = [(ref, rev, 1) for ref, rev in refs.items()]
    text = mob.manifest_text(platform, "2026-09-23", "deadbeef", "2.32.0",
                              saved, {"third_party": [], "third_party_tool": [],
                                      "toolchain": [], "build_tools": []}, [])
    (bundle_dir / "bundle_manifest.txt").write_text(text, encoding="utf-8")
    return archive


class RestoreMissingRefsFromBundleTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.bundle_dir = Path(self._tmp.name) / "offline_bundle" / "vs2026"
        self.addCleanup(self._tmp.cleanup)
        self._platform_patch = mock.patch.object(
            setup, "offline_platform", return_value="vs2026")
        self._platform_patch.start()
        self.addCleanup(self._platform_patch.stop)

    def test_only_missing_refs_are_restored_and_each_is_printed(self):
        _write_fake_bundle(self.bundle_dir, "vs2026", {
            "adas-toolchain/1.0.4": "rev1",
            "adas-build-tools/1.0.19": "rev2",
        })
        cached = {"adas-toolchain/1.0.4"}  # already cached; build-tools is not

        def fake_ref_cached(ref):
            return ref in cached

        run_calls = []

        def fake_run(cmd, **kwargs):
            run_calls.append(cmd)
            if cmd[:3] == ["conan", "cache", "restore"]:
                cached.add("adas-build-tools/1.0.19")  # simulate the restore working
            m = mock.Mock(returncode=0, stdout="")
            return m

        buf = io.StringIO()
        with mock.patch.object(setup, "_ref_cached", side_effect=fake_ref_cached), \
                mock.patch.object(setup, "run", side_effect=fake_run), \
                contextlib.redirect_stdout(buf):
            restored = setup.restore_missing_refs_from_bundle(
                self.bundle_dir, ["adas-toolchain/1.0.4", "adas-build-tools/1.0.19"])

        self.assertEqual(restored, {"adas-build-tools/1.0.19"})
        self.assertIn("adas-toolchain/1.0.4: already cached - bundle restore skipped.",
                       buf.getvalue())
        self.assertIn("adas-build-tools/1.0.19: restored from the bundle.", buf.getvalue())
        # Exactly one `conan cache restore` call - not one per ref.
        restore_calls = [c for c in run_calls if c[:3] == ["conan", "cache", "restore"]]
        self.assertEqual(len(restore_calls), 1)

    def test_no_restore_call_when_everything_already_cached(self):
        _write_fake_bundle(self.bundle_dir, "vs2026", {"adas-toolchain/1.0.4": "rev1"})
        with mock.patch.object(setup, "_ref_cached", return_value=True), \
                mock.patch.object(setup, "run") as run_mock:
            restored = setup.restore_missing_refs_from_bundle(
                self.bundle_dir, ["adas-toolchain/1.0.4"])
        self.assertEqual(restored, set())
        run_mock.assert_not_called()

    def test_planted_transitive_ref_absent_triggers_restore_even_when_every_direct_ref_is_cached(self):
        """NS-41: the exact defect. `needed_refs` (what a caller's direct
        requires: derivation asked about) is fully cached; `zlib`, a
        TRANSITIVE dep of `protobuf` that only the bundle's own manifest
        knows about, is not. Before the fix, the candidate set was
        `needed_refs` alone, so this never ran `conan cache restore` at
        all - the decision never even looked at zlib. Now the manifest's
        own ref list is unioned in, so it does."""
        _write_fake_bundle(self.bundle_dir, "vs2026", {
            "protobuf/3.21.12": "rev1",
            "zlib/1.3.2": "rev2",  # transitive dep of protobuf; not in needed_refs
        })
        cached = {"protobuf/3.21.12"}  # every DIRECT ref is cached; zlib is not

        def fake_ref_cached(ref):
            return ref in cached

        run_calls = []

        def fake_run(cmd, **kwargs):
            run_calls.append(cmd)
            if cmd[:3] == ["conan", "cache", "restore"]:
                cached.add("zlib/1.3.2")  # simulate the whole-archive restore working
            return mock.Mock(returncode=0, stdout="")

        buf = io.StringIO()
        with mock.patch.object(setup, "_ref_cached", side_effect=fake_ref_cached), \
                mock.patch.object(setup, "run", side_effect=fake_run), \
                contextlib.redirect_stdout(buf):
            # needed_refs deliberately omits zlib - simulates the direct-
            # requires-only derivation that missed it.
            restored = setup.restore_missing_refs_from_bundle(
                self.bundle_dir, ["protobuf/3.21.12"])

        restore_calls = [c for c in run_calls if c[:3] == ["conan", "cache", "restore"]]
        self.assertEqual(len(restore_calls), 1,
                         "a transitive ref missing from the cache must still trigger "
                         "the whole-archive restore, even though every ref in "
                         "needed_refs was already cached")
        self.assertEqual(restored, {"zlib/1.3.2"})
        self.assertIn("protobuf/3.21.12: already cached - bundle restore skipped.",
                       buf.getvalue())
        self.assertIn("zlib/1.3.2: restored from the bundle.", buf.getvalue())

    def test_planted_everything_manifest_and_needed_cached_no_restore(self):
        """NS-41 companion: once BOTH needed_refs and every manifest ref are
        already cached, no restore call happens - the fix does not turn
        this into an unconditional restore."""
        _write_fake_bundle(self.bundle_dir, "vs2026", {
            "protobuf/3.21.12": "rev1", "zlib/1.3.2": "rev2"})
        with mock.patch.object(setup, "_ref_cached", return_value=True), \
                mock.patch.object(setup, "run") as run_mock:
            restored = setup.restore_missing_refs_from_bundle(
                self.bundle_dir, ["protobuf/3.21.12"])
        self.assertEqual(restored, set())
        run_mock.assert_not_called()

    def test_planted_bundle_missing_a_pinned_ref_is_reported_not_fatal(self):
        """WP-3 §2b planted: a bundle missing a pinned ref is reported and
        does not abort a run whose other refs resolve."""
        _write_fake_bundle(self.bundle_dir, "vs2026", {"adas-toolchain/1.0.4": "rev1"})

        def fake_ref_cached(ref):
            return False

        def fake_run(cmd, **kwargs):
            return mock.Mock(returncode=0, stdout="")

        buf = io.StringIO()
        with mock.patch.object(setup, "_ref_cached", side_effect=fake_ref_cached), \
                mock.patch.object(setup, "run", side_effect=fake_run), \
                contextlib.redirect_stdout(buf):
            # adas-build-tools/1.0.19 is NOT in the bundle's manifest at all.
            restored = setup.restore_missing_refs_from_bundle(
                self.bundle_dir, ["adas-toolchain/1.0.4", "adas-build-tools/1.0.19"])

        self.assertNotIn("adas-build-tools/1.0.19", restored)
        self.assertIn("adas-build-tools/1.0.19: not in", buf.getvalue())
        self.assertIn("adas-build-tools/1.0.19", buf.getvalue())
        # Did not raise - the run continues.

    def test_planted_wrong_platform_bundle_is_refused(self):
        """WP-3 §2b planted: existing OF-04 behaviour must survive."""
        _write_fake_bundle(self.bundle_dir, "ubuntu_gcc", {"adas-toolchain/1.0.4": "rev1"})
        with self.assertRaises(setup.StepFailed) as ctx_mgr:
            setup.restore_missing_refs_from_bundle(
                self.bundle_dir, ["adas-toolchain/1.0.4"])
        self.assertIn("ubuntu_gcc", str(ctx_mgr.exception))
        self.assertIn("vs2026", str(ctx_mgr.exception))


class AutomaticUseNoFlagTests(unittest.TestCase):
    """WP-3 §2b: misc/offline_bundle/ present -> used with no flag; absent
    -> setup continues and says so. Exercised through prepare_conan_cache()
    (setup's own entry point into the mechanism), not by calling
    restore_missing_refs_from_bundle() directly - the point being that
    NOTHING has to pass --offline for this to happen."""

    def _prepare_with_bundle_state(self, bundle_present):
        layout = mock.patch.object(setup, "host_bundle_dir", return_value=None)
        layout.start()
        self.addCleanup(layout.stop)
        with mock.patch.object(setup.check_conan_resolution,
                                "discover_python_requires_refs",
                                return_value={"adas-toolchain/1.0.4"}), \
                mock.patch.object(setup.check_conan_resolution,
                                   "discover_build_tools_refs",
                                   return_value=set()), \
                mock.patch.object(setup, "_ref_cached", return_value=False), \
                mock.patch.object(setup, "run",
                                   return_value=mock.Mock(returncode=1, stdout="")), \
                mock.patch.object(setup.DEFAULT_OFFLINE_BUNDLE_DIR.__class__, "is_dir",
                                   return_value=bundle_present), \
                mock.patch.object(setup.Path, "is_file", return_value=True), \
                mock.patch.object(setup.Path, "mkdir"), \
                mock.patch.object(mob, "derive_pins", return_value={
                    "third_party": ["protobuf/3.21.12"], "third_party_tool": [],
                    "toolchain": [], "build_tools": []}), \
                mock.patch.object(setup, "restore_missing_refs_from_bundle",
                                   return_value=set()) as restore_mock:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), self.assertRaises(setup.StepFailed):
                setup.prepare_conan_cache(setup.argparse.Namespace(
                    dry_run=False, build_missing_from_source=False))
            return buf.getvalue(), restore_mock

    def test_bundle_present_is_consulted_with_no_flag(self):
        output, restore_mock = self._prepare_with_bundle_state(bundle_present=True)
        restore_mock.assert_called_once()

    def test_bundle_absent_setup_continues_and_says_so(self):
        output, restore_mock = self._prepare_with_bundle_state(bundle_present=False)
        restore_mock.assert_not_called()
        self.assertIn("not present - nothing to restore from", output)


if __name__ == "__main__":
    unittest.main()
