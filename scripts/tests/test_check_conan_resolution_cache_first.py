"""
scripts/tests/test_check_conan_resolution_cache_first.py

WP-2/NS-03 (cache_first_no_server_plan.md): check_conan_resolution.py asks
"can THIS MACHINE resolve it" - the local Conan cache first, a remote only
when remotes are on. Covers: a cache hit never touches the remote; a
remotes-off run never prints "no adas-local binary" and never publishes
(the WP-2 §2b criterion, planted).

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
import check_conan_resolution as ccr  # noqa: E402 - path must be set up first

# vantage-dev: these tests assert 1v-superproject's own module set (they need df).
_DF_DECLARED = "modules/df" in ((Path(__file__).resolve().parents[2] / ".gitmodules")
                                .read_text(encoding="utf-8"))
_DF_REASON = "asserts 1v-superproject's own module set (df, CARLA, viz); not this superproject's"

PINNED_PROFILE = {
    "arch": "x86_64",
    "build_type": "Release",
    "compiler": "msvc",
    "compiler.cppstd": "17",
    "compiler.runtime": "dynamic",
    "compiler.runtime_type": "Release",
    "compiler.version": "195",
    "os": "Windows",
}


def _fake_run(returncode=0, stdout="", stderr=""):
    result = mock.Mock()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


def _cache_json(ref, settings_list):
    packages = {
        f"pkgid{i}": {"info": {"settings": settings}}
        for i, settings in enumerate(settings_list)
    }
    return json.dumps({
        "Local Cache": {
            ref: {"revisions": {"rev1": {"packages": packages}}}
        }
    })


class CacheFirstTests(unittest.TestCase):

    def test_cache_hit_never_queries_the_remote(self):
        """A ref that already matches in the local cache is resolvable
        without ever calling `conan list ... -r <remote>` - the whole
        point of cache-first (no network needed when the cache already
        has it)."""
        payload = _cache_json("adas-viz/1.0.0", [PINNED_PROFILE])
        with mock.patch("subprocess.run", return_value=_fake_run(0, payload)) as run_mock:
            resolvable, reason = ccr.check_resolvable(
                "adas-viz/1.0.0", remote="adas-local",
                profile_settings=PINNED_PROFILE, remotes_enabled=True)
        self.assertTrue(resolvable)
        self.assertIn("Local Cache", reason)
        remote_calls = [c for c in run_mock.call_args_list if "-r" in c.args[0]]
        self.assertEqual(remote_calls, [])

    def test_cache_hit_recipe_never_queries_the_remote(self):
        payload = json.dumps({"Local Cache": {"adas-toolchain/1.0.4": {}}})
        with mock.patch("subprocess.run", return_value=_fake_run(0, payload)) as run_mock:
            resolvable, reason = ccr.check_resolvable(
                "adas-toolchain/1.0.4", remote="adas-local",
                profile_settings=PINNED_PROFILE, is_python_require=True,
                remotes_enabled=True)
        self.assertTrue(resolvable)
        self.assertIn("Local Cache", reason)
        remote_calls = [c for c in run_mock.call_args_list if "-r" in c.args[0]]
        self.assertEqual(remote_calls, [])

    def test_cache_miss_remotes_on_falls_through_to_remote(self):
        # Local Cache empty; adas-local has it.
        payload = json.dumps({
            "Local Cache": {},
            "adas-local": {"adas-viz/1.0.0": {
                "revisions": {"rev1": {"packages": {
                    "p0": {"info": {"settings": PINNED_PROFILE}}}}}}},
        })
        with mock.patch("subprocess.run", return_value=_fake_run(0, payload)):
            resolvable, reason = ccr.check_resolvable(
                "adas-viz/1.0.0", remote="adas-local",
                profile_settings=PINNED_PROFILE, remotes_enabled=True)
        self.assertTrue(resolvable)
        self.assertIn("adas-local", reason)


class RemotesOffNeverTouchesRemoteTests(unittest.TestCase):
    """WP-2 §2b planted criterion: with remotes off, check_conan_resolution
    never prints 'no adas-local binary' and never publishes."""

    def test_cache_miss_remotes_off_is_missing_without_remote_text(self):
        payload = json.dumps({"Local Cache": {}})
        with mock.patch("subprocess.run", return_value=_fake_run(0, payload)) as run_mock:
            resolvable, reason = ccr.check_resolvable(
                "adas-viz/1.0.0", remote="adas-local",
                profile_settings=PINNED_PROFILE, remotes_enabled=False)
        self.assertFalse(resolvable)
        self.assertNotIn("no adas-local binary matches", reason)
        self.assertIn("remotes are off", reason)
        remote_calls = [c for c in run_mock.call_args_list if "-r" in c.args[0]]
        self.assertEqual(remote_calls, [])

    def test_main_with_remotes_off_never_prints_no_adas_local_binary(self):
        payload = json.dumps({"Local Cache": {}})
        buf = io.StringIO()
        with mock.patch.object(
                ccr, "discover_required_refs", return_value=["adas-viz/1.0.0"]), \
                mock.patch.object(ccr, "discover_python_requires_refs", return_value=[]), \
                mock.patch.object(ccr, "pinned_profile_settings", return_value=PINNED_PROFILE), \
                mock.patch("subprocess.run", return_value=_fake_run(0, payload)), \
                contextlib.redirect_stdout(buf):
            exit_code = ccr.main(["--remotes", "off"])
        self.assertEqual(exit_code, 1)
        self.assertNotIn("no adas-local binary", buf.getvalue())

    def test_main_with_remotes_off_never_publishes_even_with_publish_missing(self):
        payload = json.dumps({"Local Cache": {}})
        buf = io.StringIO()
        with mock.patch.object(
                ccr, "discover_required_refs", return_value=["adas-viz/1.0.0"]), \
                mock.patch.object(ccr, "discover_python_requires_refs", return_value=[]), \
                mock.patch.object(ccr, "pinned_profile_settings", return_value=PINNED_PROFILE), \
                mock.patch("subprocess.run", return_value=_fake_run(0, payload)) as run_mock, \
                mock.patch.object(ccr, "publish_ref") as publish_mock, \
                contextlib.redirect_stdout(buf):
            exit_code = ccr.main(["--remotes", "off", "--publish-missing"])
        self.assertEqual(exit_code, 1)
        publish_mock.assert_not_called()
        create_or_upload = [c for c in run_mock.call_args_list
                             if c.args[0][:2] in (["conan", "create"], ["conan", "upload"])]
        self.assertEqual(create_or_upload, [])
        self.assertIn("Remotes are off", buf.getvalue())


class NotBuiltClassificationTests(unittest.TestCase):
    """WP-5/NS-09 (cache_first_no_server_plan.md, TASK 1): the real STEP 5
    failure this closes - `setup.bat`'s "Conan package resolution
    completeness" step used to fail outright on a genuinely empty scratch
    cache even though every first-party module was checked out and simply
    not yet compiled into the cache. Three cases, one test each, matching
    the work order's own three bullets exactly."""

    def _run_main(self, refs, python_require_refs, comp_dir_by_ref,
                   build_tools_refs=frozenset()):
        buf = io.StringIO()

        def fake_find_component_dir(ref):
            return comp_dir_by_ref.get(ref)

        with mock.patch.object(ccr, "discover_required_refs", return_value=refs), \
                mock.patch.object(ccr, "discover_python_requires_refs",
                                   return_value=python_require_refs), \
                mock.patch.object(ccr, "discover_build_tools_refs",
                                   return_value=build_tools_refs), \
                mock.patch.object(ccr, "pinned_profile_settings", return_value=PINNED_PROFILE), \
                mock.patch("subprocess.run",
                            return_value=_fake_run(0, json.dumps({"Local Cache": {}}))), \
                mock.patch.object(ccr, "_find_component_dir",
                                   side_effect=fake_find_component_dir), \
                contextlib.redirect_stdout(buf):
            exit_code = ccr.main(["--remotes", "off"])
        return exit_code, buf.getvalue()

    def test_bullet1_python_requires_ref_absent_is_still_missing_and_fails(self):
        """"third-party absent from the cache -> MISSING, fail (unchanged)":
        adas-toolchain is D3/RQ-6's own "ships in the bundle" category, not
        reclassified even though `modules/toolchain` IS checked out here -
        it is resolved by setup.py's cache-fill step BEFORE this checker
        ever runs, so still-missing here is a real gap."""
        exit_code, out = self._run_main(
            refs=["adas-toolchain/1.0.5"],
            python_require_refs={"adas-toolchain/1.0.5"},
            comp_dir_by_ref={"adas-toolchain/1.0.5": Path("modules") / "toolchain"})
        self.assertEqual(exit_code, 1)
        self.assertIn("MISSING", out)
        self.assertNotIn("NOTBUILT", out)

    @unittest.skipUnless(_DF_DECLARED, _DF_REASON)
    def test_bullet2_first_party_ref_checked_out_is_notbuilt_and_does_not_fail(self):
        """"first-party absent but its module is checked out -> ... DO NOT
        fail the step": the exact STEP 5 shape - adas-viz's own module is
        checked out, so a missing cache binary for it is "not built yet",
        not a fatal error."""
        exit_code, out = self._run_main(
            refs=["adas-viz/1.0.0"],
            python_require_refs=set(),
            comp_dir_by_ref={"adas-viz/1.0.0": Path("modules") / "viz"})
        self.assertEqual(exit_code, 0)
        self.assertIn("NOTBUILT", out)
        self.assertNotIn("MISSING", out)
        self.assertIn("not built yet", out)
        # NS-29: --prepare X builds X's DEPENDENCIES, so the hint must name
        # a module that needs the leaf, never the NOTBUILT leaf itself.
        # PT-28: a real, runnable command per dependent (df requires viz in
        # this checkout), never a placeholder.
        self.assertIn("scripts/setup.py --prepare df -t sil -p vs2026 -P base", out)
        self.assertNotIn("--prepare viz", out)
        self.assertNotIn("<", out)
        self.assertIn("builds that module's dependencies, viz among them", out)

    def test_bullet3_first_party_ref_with_no_checkout_is_missing_and_fails(self):
        """"first-party absent and NOT checked out -> MISSING, fail, naming
        setup.bat (RQ-10's honest case)": a lone-submodule clone with no
        sibling source to build the missing ref from."""
        exit_code, out = self._run_main(
            refs=["adas-viz/1.0.0"],
            python_require_refs=set(),
            comp_dir_by_ref={"adas-viz/1.0.0": None})
        self.assertEqual(exit_code, 1)
        self.assertIn("MISSING", out)
        self.assertNotIn("NOTBUILT", out)
        self.assertIn("setup.bat", out)

    def test_fresh_scratch_cache_with_every_module_checked_out_lets_setup_bat_complete(self):
        """WP-5 §2b's own criterion, verbatim: a fresh scratch cache with
        every module checked out (STEP 5's real shape - interfaces,
        mathlib, shared-config, sim, viz all missing from the cache, all
        checked out) must let the resolution-completeness step PASS
        (exit 0), not fail setup.bat before build.py ever gets a chance to
        build them from source."""
        refs = ["adas-interfaces/1.0.0", "adas-mathlib/1.0.0",
                "adas-shared-config/1.0.0", "adas-sim/0.1.0", "adas-viz/1.0.0"]
        comp_dir_by_ref = {
            "adas-interfaces/1.0.0": Path("modules") / "interfaces",
            "adas-mathlib/1.0.0": Path("modules") / "mathlib",
            "adas-shared-config/1.0.0": Path("modules") / "shared_config",
            "adas-sim/0.1.0": Path("modules") / "sim",
            "adas-viz/1.0.0": Path("modules") / "viz",
        }
        exit_code, out = self._run_main(
            refs=refs, python_require_refs=set(), comp_dir_by_ref=comp_dir_by_ref)
        self.assertEqual(exit_code, 0)
        for ref in refs:
            self.assertIn(f"NOTBUILT {ref}", out)
        self.assertNotIn("MISSING", out)

    def test_build_tools_ref_absent_is_also_unchanged_missing(self):
        """Same reasoning as bullet 1, for the third D3/RQ-6 "ships in the
        bundle" source (adas-build-tools, not adas-toolchain)."""
        exit_code, out = self._run_main(
            refs=["adas-build-tools/1.0.20"],
            python_require_refs=set(),
            build_tools_refs={"adas-build-tools/1.0.20"},
            comp_dir_by_ref={"adas-build-tools/1.0.20":
                              Path("modules") / "toolchain" / "conan_package"})
        self.assertEqual(exit_code, 1)
        self.assertIn("MISSING", out)
        self.assertNotIn("NOTBUILT", out)


if __name__ == "__main__":
    unittest.main()
