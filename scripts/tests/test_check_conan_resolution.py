"""
scripts/tests/test_check_conan_resolution.py

Regression tests for scripts/check_conan_resolution.py
(docs: modules/toolchain/docs/imp_design.md §6 SS7, DRT-10).
Pure unittest + unittest.mock - no pytest, no real conan/network calls;
every subprocess boundary is mocked, matching this repo's own convention
for a scripts/-root script (scripts/tests/test_conan_publish.py).

Run:
    py -m unittest discover -s scripts/tests
    (from the superproject root)
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import check_conan_resolution as ccr  # noqa: E402 - path must be set up first


def _fake_run(returncode=0, stdout="", stderr=""):
    result = mock.Mock()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


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


def _adas_local_json(ref, settings_list):
    """A conan list <ref>:* -r adas-local --format=json payload with one
    package per settings dict in settings_list (each landing under its
    own arbitrary package_id key)."""
    packages = {
        f"pkgid{i}": {"info": {"settings": settings}}
        for i, settings in enumerate(settings_list)
    }
    return json.dumps({
        "adas-local": {
            ref: {"revisions": {"rev1": {"packages": packages}}}
        }
    })


class DiscoverComponentsTests(unittest.TestCase):
    """discover_components()/discover_required_refs() - real filesystem,
    a throwaway modules/ tree standing in for this checkout's own, so the
    test never depends on this repo's actual component roster."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self._root_patch = mock.patch.object(ccr, "ROOT", self.root)
        self._root_patch.start()
        self.addCleanup(self._root_patch.stop)

    def _make_component(self, name, build_yml_text, with_conanfile=True):
        comp_dir = self.root / "modules" / name
        (comp_dir / "conf").mkdir(parents=True)
        if with_conanfile:
            (comp_dir / "conanfile.py").write_text("# stub", encoding="utf-8")
        (comp_dir / "conf" / "build.yml").write_text(build_yml_text, encoding="utf-8")
        return comp_dir

    def test_component_without_conanfile_is_excluded(self):
        """Same predicate as scripts/setup.py::discover_components() -
        conf/build.yml alone is not enough, a placeholder submodule has
        one but no conanfile.py."""
        self._make_component("real_comp", "variants: {}\n")
        self._make_component("placeholder", "variants: {}\n", with_conanfile=False)
        self.assertEqual(ccr.discover_components(), ["real_comp"])

    def test_discover_required_refs_collects_across_components_and_variants(self):
        self._make_component("df", """
variants:
  base:
    requires: [adas-interfaces/1.0.0, adas-mathlib/1.0.0, protobuf/3.21.12]
    tool_requires: [protobuf/3.21.12]
  cus1:
    requires: [adas-interfaces/1.0.0, adas-viz/1.0.0]
""")
        self._make_component("mathlib", "variants:\n  base: {}\n")
        refs = ccr.discover_required_refs()
        self.assertEqual(refs, ["adas-interfaces/1.0.0", "adas-mathlib/1.0.0", "adas-viz/1.0.0"])

    def test_non_adas_and_malformed_yaml_are_tolerated(self):
        self._make_component("ok", "variants:\n  base:\n    requires: [adas-x/1.0.0]\n")
        self._make_component("broken", "variants: [this is not a mapping\n")
        refs = ccr.discover_required_refs()
        self.assertEqual(refs, ["adas-x/1.0.0"])

    def _make_component_with_conanfile(self, name, conanfile_text, build_yml_text="variants: {}\n"):
        comp_dir = self.root / "modules" / name
        (comp_dir / "conf").mkdir(parents=True)
        (comp_dir / "conanfile.py").write_text(conanfile_text, encoding="utf-8")
        (comp_dir / "conf" / "build.yml").write_text(build_yml_text, encoding="utf-8")
        return comp_dir

    def test_discover_python_requires_refs_reads_conanfile_py(self):
        """CE-18: python_requires is declared in conanfile.py, not
        conf/build.yml - real shape of every one of this repo's 8
        components."""
        self._make_component_with_conanfile(
            "df",
            'from conan import ConanFile\n\n\n'
            'class DfConan(ConanFile):\n'
            '    python_requires = "adas-toolchain/1.0.4"\n'
            '    python_requires_extend = "adas-toolchain.AdasComponent"\n',
        )
        self.assertEqual(ccr.discover_python_requires_refs(), {"adas-toolchain/1.0.4"})

    def test_discover_python_requires_refs_ignores_placeholder_and_non_adas(self):
        self._make_component_with_conanfile(
            "placeholder", "# Conan configuration placeholder\n")
        self._make_component_with_conanfile(
            "other",
            'class X:\n    python_requires = "somevendor-thing/1.0.0"\n',
        )
        self.assertEqual(ccr.discover_python_requires_refs(), set())

    def test_discover_required_refs_unions_build_yml_and_python_requires(self):
        """CE-18's own fix, end to end: discover_required_refs() (the
        function ensure_resolution_complete()/main() actually call) must
        report adas-toolchain even though no conf/build.yml anywhere
        declares it under requires:/tool_requires: - only conanfile.py
        does. Root-cause incident: this exact gap let adas-toolchain go
        unpublished on adas-local with nothing ever flagging it."""
        self._make_component_with_conanfile(
            "df",
            'python_requires = "adas-toolchain/1.0.4"\n',
            build_yml_text="variants:\n  base:\n    requires: [adas-interfaces/1.0.0]\n",
        )
        refs = ccr.discover_required_refs()
        self.assertEqual(refs, ["adas-interfaces/1.0.0", "adas-toolchain/1.0.4"])

    def test_discover_build_tools_refs_reads_bare_pin(self):
        comp_dir = self._make_component("df", "variants: {}\n")
        (comp_dir / "conf" / "build_tools.version").write_text("1.0.19\n", encoding="utf-8")
        self.assertEqual(ccr.discover_build_tools_refs(), {"adas-build-tools/1.0.19"})

    def test_discover_build_tools_refs_skips_git_tag_pin(self):
        """imp_design.md §10: a `vX.Y.Z` pin installs via `pip install
        git+<url>@<tag>`, not from adas-local - correctly not a ref."""
        comp_dir = self._make_component("df", "variants: {}\n")
        (comp_dir / "conf" / "build_tools.version").write_text("v1.0.19\n", encoding="utf-8")
        self.assertEqual(ccr.discover_build_tools_refs(), set())

    def test_discover_build_tools_refs_tolerates_missing_pin_file(self):
        self._make_component("df", "variants: {}\n")
        self.assertEqual(ccr.discover_build_tools_refs(), set())

    def test_discover_required_refs_unions_build_tools_pin(self):
        """RD-14's own real proof, 2026-09-22: a solo/delegate build fails
        downloading adas-build-tools even after every other required ref
        is published, because this THIRD source was never in the union."""
        comp_dir = self._make_component("df", "variants:\n  base:\n    requires: [adas-interfaces/1.0.0]\n")
        (comp_dir / "conf" / "build_tools.version").write_text("1.0.19\n", encoding="utf-8")
        refs = ccr.discover_required_refs()
        self.assertEqual(refs, ["adas-build-tools/1.0.19", "adas-interfaces/1.0.0"])

    def test_ce18_planted_violation_checker_fails_when_python_requires_ref_unpublished(self):
        """R-REQ-9 planted-violation case: prove the EXTENDED checker
        actually fails (reports MISSING, non-zero exit) when a
        python_requires ref is absent from the remote and not editable -
        the exact live incident (adas-toolchain published nowhere) this
        row exists to catch. A check nobody has seen fail is a check
        nobody should believe."""
        self._make_component_with_conanfile(
            "df", 'python_requires = "adas-toolchain/1.0.4"\n')
        with mock.patch.object(ccr, "pinned_profile_settings", return_value=PINNED_PROFILE), \
             mock.patch("subprocess.run",
                         return_value=_fake_run(0, json.dumps({"adas-local": {}}))):
            exit_code = ccr.main([])
        self.assertEqual(exit_code, 1)


class CheckResolvableTests(unittest.TestCase):
    """DRT-10 (F-REQUIRED-VS-PUBLISHED): a ref missing from adas-local is
    correctly flagged."""

    def test_drt10_c1_neither_editable_nor_published_is_missing(self):
        """PASS: reported MISSING. FAIL: reported resolvable when it isn't."""
        payload = _adas_local_json("adas-viz/1.0.0", [])
        with mock.patch("subprocess.run", return_value=_fake_run(0, payload)):
            resolvable, reason = ccr.check_resolvable(
                "adas-viz/1.0.0", remote="adas-local",
                profile_settings=PINNED_PROFILE)
        self.assertFalse(resolvable)
        self.assertIn("no adas-local binary matches", reason)

    def test_drt10_c2_matching_binary_on_remote_is_resolvable(self):
        """PASS: a ref that IS present on adas-local with a binary matching
        the current profile is reported resolvable."""
        payload = _adas_local_json("adas-viz/1.0.0", [PINNED_PROFILE])
        with mock.patch("subprocess.run", return_value=_fake_run(0, payload)):
            resolvable, reason = ccr.check_resolvable(
                "adas-viz/1.0.0", remote="adas-local",
                profile_settings=PINNED_PROFILE)
        self.assertTrue(resolvable)
        self.assertIn("adas-local", reason)

    def test_old_compiler_binary_is_not_good_enough(self):
        """SS4's own callout: a recipe that exists with only an OLD
        compiler's binary is exactly as unresolvable as one missing
        outright - "the recipe exists" is not treated as good enough."""
        old_compiler_settings = dict(PINNED_PROFILE, **{"compiler.version": "193"})
        payload = _adas_local_json("adas-viz/1.0.0", [old_compiler_settings])
        with mock.patch("subprocess.run", return_value=_fake_run(0, payload)):
            resolvable, reason = ccr.check_resolvable(
                "adas-viz/1.0.0", remote="adas-local",
                profile_settings=PINNED_PROFILE)
        self.assertFalse(resolvable)

    def test_no_pinned_profile_shipped_never_confirms_via_remote(self):
        """profile_settings=None (no profile shipped for this platform) -
        RD-03: package-mode resolution only, so nothing can be confirmed
        resolvable at all."""
        resolvable, _ = ccr.check_resolvable(
            "adas-viz/1.0.0", remote="adas-local", profile_settings=None)
        self.assertFalse(resolvable)

    def test_expired_session_error_payload_is_treated_as_not_found(self):
        """Same "error" key defensiveness as conan_publish.py's own
        list_remote_versions() - never crash, never treat an auth failure
        as a false PASS."""
        payload = json.dumps({"adas-local": {"error": "not authenticated"}})
        with mock.patch("subprocess.run", return_value=_fake_run(0, payload)):
            resolvable, _ = ccr.check_resolvable(
                "adas-viz/1.0.0", remote="adas-local",
                profile_settings=PINNED_PROFILE)
        self.assertFalse(resolvable)


class PythonRequireComponentTests(unittest.TestCase):
    """CE-18: `is_python_require=True` is passed in by the CALLER (from
    `discover_python_requires_refs()`), never inferred by opening the
    ref's own component's conf/build.yml - the cold-machine case this
    exists for (only `df` cloned) has no local `toolchain` checkout to
    open at all, so the flag must work with zero local knowledge of the
    ref's own component."""

    def test_remote_resolution_for_python_require_ref_checks_recipe_only(self):
        """CE-18's second half: adas-toolchain published via `conan
        export` has zero binary packages forever - `_adas_local_matches_
        profile()`'s package/settings walk must never be the gate for a
        python_requires ref. Recipe-only existence (`_adas_local_has_
        recipe()`) is."""
        # WP-2/NS-03: cache-first now probes the local cache too (payload
        # keyed "adas-local", not "Local Cache" - the cache probe misses),
        # so this fixture falls through to the remote exactly as before.
        payload = json.dumps({"adas-local": {"adas-toolchain/1.0.4": {}}})
        with mock.patch("subprocess.run", return_value=_fake_run(0, payload)) as run_mock:
            resolvable, reason = ccr.check_resolvable(
                "adas-toolchain/1.0.4", remote="adas-local",
                profile_settings=PINNED_PROFILE, is_python_require=True)
        self.assertTrue(resolvable)
        self.assertIn("python_requires recipe published", reason)
        # Unqualified `conan list <ref>` (no `:*` binary selector), once for
        # the cache probe and once for the remote probe.
        list_calls = [c for c in run_mock.call_args_list if c.args[0][:2] == ["conan", "list"]]
        self.assertEqual(len(list_calls), 2)
        for call in list_calls:
            self.assertEqual(call.args[0][2], "adas-toolchain/1.0.4")
        remote_calls = [c for c in list_calls if "-r" in c.args[0]]
        self.assertEqual(len(remote_calls), 1)

    def test_remote_resolution_for_python_require_ref_missing_recipe_is_missing(self):
        payload = json.dumps({"adas-local": {"error": "Recipe not found"}})
        with mock.patch("subprocess.run", return_value=_fake_run(0, payload)):
            resolvable, reason = ccr.check_resolvable(
                "adas-toolchain/1.0.4", remote="adas-local",
                profile_settings=PINNED_PROFILE, is_python_require=True)
        self.assertFalse(resolvable)
        self.assertIn("no adas-local recipe published", reason)

    def test_is_python_require_component_used_by_publish_ref_false_for_missing_comp_dir(self):
        self.assertFalse(ccr._is_python_require_component(None))


class SettingsLessPackageTests(unittest.TestCase):
    """DRT-12 (F-SETTINGS-LESS-PACKAGE, DR-10): a genuinely settings-less
    package (adas-shared-config's own real shape - conanfile.py declares no
    `settings` field at all, so `info.settings` on a real published binary
    is genuinely `{}`) is resolvable when published, on any platform -
    while a package with a real, non-empty, MISMATCHING settings dict must
    still correctly report MISSING (the fix must not become "anything
    published counts")."""

    def test_drt12_c1_genuinely_settings_less_package_is_resolvable(self):
        """PASS: reported resolvable, regardless of what profile_settings
        asks for - there is nothing to mismatch. FAIL: reported MISSING
        despite a real, correctly-published binary existing."""
        payload = _adas_local_json("adas-shared-config/1.0.0", [{}])
        with mock.patch("subprocess.run", return_value=_fake_run(0, payload)):
            resolvable, reason = ccr.check_resolvable(
                "adas-shared-config/1.0.0", remote="adas-local",
                profile_settings=PINNED_PROFILE)
        self.assertTrue(resolvable)
        self.assertIn("adas-local", reason)

    def test_drt12_c2_mismatching_non_empty_settings_still_missing(self):
        """PASS: a package with a real, non-empty, mismatching info.settings
        (wrong compiler version) is still correctly reported MISSING - the
        fix must not over-correct into "anything published counts". FAIL:
        the fix over-corrects and stops catching a real profile mismatch."""
        mismatching_settings = dict(PINNED_PROFILE, **{"compiler.version": "193"})
        payload = _adas_local_json("adas-viz/1.0.0", [mismatching_settings])
        with mock.patch("subprocess.run", return_value=_fake_run(0, payload)):
            resolvable, reason = ccr.check_resolvable(
                "adas-viz/1.0.0", remote="adas-local",
                profile_settings=PINNED_PROFILE)
        self.assertFalse(resolvable)
        self.assertIn("no adas-local binary matches", reason)


class PinnedProfileSettingsTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self._root_patch = mock.patch.object(ccr, "ROOT", self.root)
        self._root_patch.start()
        self.addCleanup(self._root_patch.stop)

    def test_parses_settings_section(self):
        profile_dir = self.root / "modules" / "toolchain" / "adas_build_tools" / "conan_profiles"
        profile_dir.mkdir(parents=True)
        (profile_dir / "vs2026.profile").write_text(
            "[settings]\narch=x86_64\ncompiler.version=195\nos=Windows\n"
            "[buildenv]\nSOME_VAR=ignored\n",
            encoding="utf-8",
        )
        settings = ccr.pinned_profile_settings("vs2026")
        self.assertEqual(settings, {"arch": "x86_64", "compiler.version": "195", "os": "Windows"})

    def test_missing_profile_returns_none(self):
        self.assertIsNone(ccr.pinned_profile_settings("ubuntu_gcc"))


class FindComponentDirTests(unittest.TestCase):
    """RD-14's own real proof, 2026-09-22: `adas-build-tools`'s recipe
    lives nested at modules/toolchain/conan_package/, not at any
    modules/<x> top level discover_components() enumerates - a real
    solo/delegate build never found it to publish until this candidate
    was added."""

    def _inspect_result(self, name):
        return _fake_run(0, json.dumps({"name": name}))

    def test_finds_conan_package_dir_for_adas_build_tools(self):
        with mock.patch.object(ccr, "discover_components", return_value=["df"]), \
             mock.patch.object(ccr, "ROOT", Path("/repo")), \
             mock.patch("subprocess.run") as run_mock:
            run_mock.side_effect = [
                self._inspect_result("adas-df"),
                self._inspect_result("adas-build-tools"),
            ]
            comp_dir = ccr._find_component_dir("adas-build-tools/1.0.19")

        self.assertEqual(comp_dir, Path("/repo") / "modules" / "toolchain" / "conan_package")

    def test_still_finds_an_ordinary_component(self):
        with mock.patch.object(ccr, "discover_components", return_value=["df"]), \
             mock.patch.object(ccr, "ROOT", Path("/repo")), \
             mock.patch("subprocess.run") as run_mock:
            run_mock.side_effect = [self._inspect_result("adas-df")]
            comp_dir = ccr._find_component_dir("adas-df/1.0.0")

        self.assertEqual(comp_dir, Path("/repo") / "modules" / "df")


class PublishRefTests(unittest.TestCase):
    """DR-09: build + upload a MISSING ref that has local source, with the
    PINNED profile (not this machine's own auto-detected default, which
    is a different compiler version - confirmed live)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self._root_patch = mock.patch.object(ccr, "ROOT", self.root)
        self._root_patch.start()
        self.addCleanup(self._root_patch.stop)
        profile_dir = self.root / "modules" / "toolchain" / "adas_build_tools" / "conan_profiles"
        profile_dir.mkdir(parents=True)
        (profile_dir / "vs2026.profile").write_text("[settings]\ncompiler.version=195\n",
                                                      encoding="utf-8")

    def test_create_command_carries_the_pinned_profile_flags(self):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return _fake_run(0, "")

        with mock.patch("subprocess.run", side_effect=fake_run):
            result = ccr.publish_ref("adas-viz/1.0.0", self.root / "modules" / "viz",
                                      "adas-local", "vs2026")

        self.assertTrue(result)
        create_calls = [c for c in calls if c[:2] == ["conan", "create"]]
        self.assertEqual(len(create_calls), 1)
        create_cmd = create_calls[0]
        self.assertIn("--profile:host", create_cmd)
        self.assertIn("--profile:build", create_cmd)
        profile_path = str(self.root / "modules" / "toolchain" / "adas_build_tools"
                            / "conan_profiles" / "vs2026.profile")
        host_idx = create_cmd.index("--profile:host")
        self.assertEqual(create_cmd[host_idx + 1], profile_path)

    def test_create_failure_returns_false_before_upload(self):
        """RD-05 (remove_develop_mode_plan.md, WP-4): was
        test_create_failure_restores_editable_and_returns_false - the
        editable-restore assertion is gone with editable_refs()/
        was_editable (RD-01's own verdict), what remains is that a
        failed build never reaches the upload step."""
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            if cmd[:2] == ["conan", "create"]:
                return _fake_run(1, "", "build failed")
            return _fake_run(0, "")

        with mock.patch("subprocess.run", side_effect=fake_run):
            result = ccr.publish_ref("adas-viz/1.0.0", self.root / "modules" / "viz",
                                      "adas-local", "vs2026")

        self.assertFalse(result)
        self.assertNotIn(["conan", "upload", "adas-viz/1.0.0", "-r", "adas-local", "--confirm"],
                          calls)

    def test_python_require_component_publishes_via_export_not_create(self):
        """CE-18: adas-toolchain's own documented publish step
        (modules/toolchain/conf/build.yml) is `conan export`, not `conan
        create` - it has no CMakeLists.txt, nothing to compile, and no
        settings axis to pin with profile flags. RD-08: the pinned
        version (1.0.4) must equal the checkout's own recipe version
        (mocked to 1.0.4 here via `conan inspect`) or publish is refused -
        see test_relabel_refused_when_pin_disagrees_with_checkout below."""
        comp_dir = self.root / "modules" / "toolchain"
        (comp_dir / "conf").mkdir(parents=True)
        (comp_dir / "conf" / "build.yml").write_text(
            "recipe:\n  type: python-require\n", encoding="utf-8")
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            if cmd[:2] == ["conan", "inspect"]:
                return _fake_run(0, json.dumps({"version": "1.0.4"}))
            return _fake_run(0, "")

        with mock.patch("subprocess.run", side_effect=fake_run):
            result = ccr.publish_ref("adas-toolchain/1.0.4", comp_dir, "adas-local", "vs2026")

        self.assertTrue(result)
        export_calls = [c for c in calls if c[:2] == ["conan", "export"]]
        create_calls = [c for c in calls if c[:2] == ["conan", "create"]]
        self.assertEqual(len(export_calls), 1)
        self.assertEqual(len(create_calls), 0)
        self.assertEqual(export_calls[0], ["conan", "export", "."])
        self.assertIn(["conan", "upload", "adas-toolchain/1.0.4", "-r", "adas-local", "--confirm"],
                       calls)

    def test_relabel_refused_when_pin_disagrees_with_checkout(self):
        """RD-08 planted violation: the real incident this closes -
        `adas-toolchain`'s checkout was at 1.0.5 while a stale consumer
        pin asked for 1.0.4, and the old `conan export . --version=1.0.4`
        would have happily exported the 1.0.5 source mislabelled as
        1.0.4. publish_ref() must refuse instead of relabelling: no
        export, no upload, a clear reason printed."""
        comp_dir = self.root / "modules" / "toolchain"
        (comp_dir / "conf").mkdir(parents=True)
        (comp_dir / "conf" / "build.yml").write_text(
            "recipe:\n  type: python-require\n", encoding="utf-8")
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            if cmd[:2] == ["conan", "inspect"]:
                return _fake_run(0, json.dumps({"version": "1.0.5"}))
            return _fake_run(0, "")

        with mock.patch("subprocess.run", side_effect=fake_run):
            result = ccr.publish_ref("adas-toolchain/1.0.4", comp_dir, "adas-local", "vs2026")

        self.assertFalse(result)
        self.assertFalse(any(c[:2] == ["conan", "export"] for c in calls))
        self.assertFalse(any(c[:2] == ["conan", "upload"] for c in calls))

    def test_upload_failure_returns_false(self):
        def fake_run(cmd, **kwargs):
            if cmd[:2] == ["conan", "upload"]:
                return _fake_run(1, "", "upload failed")
            return _fake_run(0, "")

        with mock.patch("subprocess.run", side_effect=fake_run):
            result = ccr.publish_ref("adas-viz/1.0.0", self.root / "modules" / "viz",
                                      "adas-local", "vs2026")
        self.assertFalse(result)



class MainTests(unittest.TestCase):
    """main()'s own PASS/MISSING report and exit code, and --publish-missing
    wiring - the pieces it composes from are each tested above, so this
    only checks the composition. RD-03: package-mode resolution only, so
    PASS/MISSING is driven entirely by the mocked `adas-local` remote
    payload (no more editable_refs()/build-output stand-in)."""

    def setUp(self):
        self._refs_patch = mock.patch.object(
            ccr, "discover_required_refs", return_value=["adas-viz/1.0.0", "adas-mathlib/1.0.0"])
        self._refs_patch.start()
        self.addCleanup(self._refs_patch.stop)

    @staticmethod
    def _remote_payload(resolvable_refs):
        """A `conan list <ref>:* -r adas-local --format=json` payload
        covering both of this class's refs at once - `_adas_local_matches_
        profile()` only ever reads the one key matching the ref it asked
        about, so one combined payload safely serves every call."""
        data = {"adas-local": {}}
        for ref in ("adas-viz/1.0.0", "adas-mathlib/1.0.0"):
            packages = ({"pkgid": {"info": {"settings": PINNED_PROFILE}}}
                        if ref in resolvable_refs else {})
            data["adas-local"][ref] = {"revisions": {"rev1": {"packages": packages}}}
        return json.dumps(data)

    def test_exits_zero_when_everything_resolvable(self):
        payload = self._remote_payload({"adas-viz/1.0.0", "adas-mathlib/1.0.0"})
        with mock.patch.object(ccr, "pinned_profile_settings", return_value=PINNED_PROFILE), \
             mock.patch("subprocess.run", return_value=_fake_run(0, payload)):
            # NS-24: the real team_conan_server.txt is now a loopback URL,
            # which reads as remotes-off (D1a) - force remotes on so this
            # test still exercises the real remote-query path it mocks.
            exit_code = ccr.main(["--remotes", "on"])
        self.assertEqual(exit_code, 0)

    def test_exits_nonzero_when_something_missing(self):
        payload = self._remote_payload({"adas-mathlib/1.0.0"})
        with mock.patch.object(ccr, "pinned_profile_settings", return_value=PINNED_PROFILE), \
             mock.patch("subprocess.run", return_value=_fake_run(0, payload)):
            exit_code = ccr.main([])
        self.assertEqual(exit_code, 1)

    def test_publish_missing_flag_calls_publish_ref_for_each_missing_with_local_source(self):
        comp_dir = Path("modules") / "viz"
        payload = self._remote_payload({"adas-mathlib/1.0.0"})
        with mock.patch.object(ccr, "pinned_profile_settings", return_value=PINNED_PROFILE), \
             mock.patch("subprocess.run", return_value=_fake_run(0, payload)), \
             mock.patch.object(ccr, "_find_component_dir",
                                return_value=comp_dir) as find_mock, \
             mock.patch.object(ccr, "publish_ref", return_value=True) as publish_mock:
            # NS-24: force remotes on (see test_exits_zero_when_everything_
            # resolvable above for why).
            exit_code = ccr.main(["--remotes", "on", "--publish-missing"])

        self.assertEqual(exit_code, 0)
        find_mock.assert_any_call("adas-viz/1.0.0")
        publish_mock.assert_called_once_with("adas-viz/1.0.0", comp_dir, "adas-local", "vs2026")

    def test_missing_ref_with_no_local_source_is_reported_not_skipped(self):
        """DR-09's own explicit requirement: a MISSING ref with no local
        source is reported plainly, never silently dropped."""
        payload = self._remote_payload({"adas-mathlib/1.0.0"})
        with mock.patch.object(ccr, "pinned_profile_settings", return_value=PINNED_PROFILE), \
             mock.patch("subprocess.run", return_value=_fake_run(0, payload)), \
             mock.patch.object(ccr, "_find_component_dir", return_value=None):
            exit_code = ccr.main(["--publish-missing"])
        self.assertEqual(exit_code, 1)

    def test_rd11_planted_violation_toolchain_published_before_dependents(self):
        """RD-11: the real ordering bug reproduced live in RD-09 - a
        component needing adas-toolchain cannot be probed by
        `_find_component_dir()` (its `conan inspect .` fails to resolve
        `python_requires`) until adas-toolchain has itself been published
        earlier in the SAME --publish-missing loop. Planted:
        `_find_component_dir` returns None for the non-toolchain ref until
        `publish_ref` has been called for the toolchain ref - failing
        without the RD-11 fix (which processes missing in discover order:
        mathlib before toolchain) and passing with it (toolchain first)."""
        refs = ["adas-mathlib/1.0.0", "adas-toolchain/1.0.5"]
        toolchain_published = []

        def fake_find_component_dir(ref):
            if ref == "adas-toolchain/1.0.5":
                return Path("modules") / "toolchain"
            if not toolchain_published:
                return None
            return Path("modules") / "mathlib"

        def fake_publish_ref(ref, comp_dir, remote, platform):
            if ref == "adas-toolchain/1.0.5":
                toolchain_published.append(True)
            return True

        with mock.patch.object(ccr, "discover_required_refs", return_value=refs), \
             mock.patch.object(ccr, "discover_python_requires_refs",
                                return_value={"adas-toolchain/1.0.5"}), \
             mock.patch.object(ccr, "pinned_profile_settings", return_value=PINNED_PROFILE), \
             mock.patch.object(ccr, "check_resolvable", return_value=(False, "missing")), \
             mock.patch.object(ccr, "_find_component_dir",
                                side_effect=fake_find_component_dir), \
             mock.patch.object(ccr, "publish_ref", side_effect=fake_publish_ref):
            # NS-24: force remotes on (see test_exits_zero_when_everything_
            # resolvable above for why).
            exit_code = ccr.main(["--remotes", "on", "--publish-missing"])

        self.assertEqual(exit_code, 0)


class ExpiredLoginTests(unittest.TestCase):
    """CE-29: an expired adas-local login is reported once, by name, and never
    as a list of MISSING refs; --publish-missing never runs on it."""

    REAL_ERROR = json.dumps({"adas-local": {
        "error": "Conan interactive mode disabled. [Remote: adas-local]"}})

    def _main(self, run_result, argv=()):
        import contextlib
        import io
        out = io.StringIO()
        with mock.patch.object(ccr, "discover_required_refs",
                                return_value=["adas-mathlib/1.0.0", "adas-viz/1.0.0"]),              mock.patch.object(ccr, "discover_python_requires_refs", return_value=set()),              mock.patch.object(ccr, "pinned_profile_settings", return_value=PINNED_PROFILE),              mock.patch("subprocess.run", return_value=run_result),              mock.patch.object(ccr, "_find_component_dir",
                                 return_value=None) as find_mock,              mock.patch.object(ccr, "publish_ref") as publish_mock,              contextlib.redirect_stdout(out):
            code = ccr.main(list(argv))
        return code, out.getvalue(), find_mock, publish_mock

    def test_planted_violation_auth_failure_reports_login_once_no_missing_no_publish(self):
        """PASS: the message once, non-zero exit, zero MISSING lines, publish
        never reached even with --publish-missing. FAIL (pre-CE-29): every
        ref listed MISSING (seen live 2026-09-21)."""
        code, out, find_mock, publish_mock = self._main(
            _fake_run(0, self.REAL_ERROR),
            argv=["--remotes", "on", "--publish-missing"])
        self.assertNotEqual(code, 0)
        self.assertEqual(out.count("adas-local login expired - run: "
                                   "conan remote login adas-local demo -p demo"), 1)
        self.assertIn("(CONAN_HOME=", out)
        self.assertNotIn("MISSING", out)
        find_mock.assert_not_called()
        publish_mock.assert_not_called()

    def test_auth_failure_on_a_nonzero_exit_is_also_reported_by_name(self):
        code, out, _, publish_mock = self._main(
            _fake_run(1, "", "ERROR: EOF when reading a line. [Remote: adas-local]"),
            argv=["--remotes", "on", "--publish-missing"])
        self.assertNotEqual(code, 0)
        self.assertIn("adas-local login expired", out)
        self.assertNotIn("MISSING", out)
        publish_mock.assert_not_called()

    def test_genuine_missing_ref_is_still_reported_missing(self):
        code, out, _, _ = self._main(_fake_run(0, json.dumps({"adas-local": {}})))
        self.assertEqual(code, 1)
        self.assertIn("MISSING", out)
        self.assertNotIn("login expired", out)

    def test_a_non_auth_remote_error_is_not_mistaken_for_an_expired_login(self):
        code, out, _, _ = self._main(_fake_run(0, json.dumps(
            {"adas-local": {"error": "Remote unreachable"}})))
        self.assertEqual(code, 1)
        self.assertIn("MISSING", out)
        self.assertNotIn("login expired", out)

    def test_one_matcher_shared_with_build_py(self):
        import build as build_dispatcher
        self.assertIs(ccr.auth_failure_message, build_dispatcher.auth_failure_message)


if __name__ == "__main__":
    unittest.main()


class Pt28NotbuiltHintTests(unittest.TestCase):
    """PT-28 (D11): the NOTBUILT hint is one runnable `--prepare` per
    checked-out module that requires the ref directly, each with a target/
    platform/project that module really declares -- never a placeholder.
    Planted: a ref nobody requires gets Fix only, no Run: line."""

    BUILD_YML = """\
variants:
  base:
    requires: [adas-mathlib/1.0.0]
    sil:
      platforms: [{build: vs2026}]
    gtest:
      platforms: [{build: vs2026}]
"""
    OTHER_PROJECT = """\
variants:
  cus1:
    requires: [adas-mathlib/1.0.0]
    hil:
      platforms: [{build: vs2026}]
"""

    def _tree(self, tmp):
        import tempfile as _t  # noqa: F401
        root = Path(tmp)
        for name, text in (("df", self.BUILD_YML), ("vdy", self.OTHER_PROJECT),
                           ("quiet", "variants: {base: {sil: {platforms: [{build: vs2026}]}}}\n")):
            comp = root / "modules" / name
            (comp / "conf").mkdir(parents=True)
            (comp / "conf" / "build.yml").write_text(text, encoding="utf-8")
            (comp / "conanfile.py").write_text("", encoding="utf-8")
        return root

    def test_hint_names_every_dependent_with_a_real_command(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            lines = ccr.notbuilt_hint(
                "adas-mathlib/1.0.0", "mathlib", "vs2026", root=self._tree(tmp))
        text = "\n".join(lines)
        self.assertNotIn("<", text)
        runs = [l for l in lines if l.startswith("Run:")]
        self.assertEqual(len(runs), 2, text)
        self.assertIn("--prepare df -t sil -p vs2026 -P base", text)
        self.assertIn("--prepare vdy -t hil -p vs2026 -P cus1", text)
        self.assertNotIn("quiet", text)

    def test_planted_ref_nobody_requires_prints_no_run(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            lines = ccr.notbuilt_hint(
                "adas-nobody/9.9.9", "nobody", "vs2026", root=self._tree(tmp))
        self.assertFalse([l for l in lines if l.startswith("Run:")], lines)
        self.assertTrue(lines[0].startswith("Fix:"))
        self.assertIn("no checked-out module requires adas-nobody/9.9.9", lines[0])
