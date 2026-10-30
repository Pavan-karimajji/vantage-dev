"""
scripts/tests/test_conan_publish.py

Regression tests for scripts/conan_publish.py, added per plan.md items 14/15's
"Fix plan" (docs/test_13_14_15.md §5.1). Pure unittest + unittest.mock - no
pytest dependency, no real conan/network calls; every subprocess boundary is
mocked.

Bug #17's original driver (the editable-aware 4-command publish path only
firing when publishing the exact version currently registered editable) no
longer applies - RD-05 (remove_develop_mode_plan.md, WP-4) removed that
path along with is_editable()/was_editable (RD-01's own verdict: it was
permanently unreachable once nothing is ever editable). What remains here
is regression coverage for the plain create/upload sequence per declared
variant.

Run:
    py -m unittest discover -s scripts/tests
    (from the superproject root)
"""

import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import conan_publish  # noqa: E402 - path must be set up first


def _fake_run(returncode=0, stdout="", stderr=""):
    result = mock.Mock()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


class ListRemoteVersionsTests(unittest.TestCase):

    def test_sorts_semantically_not_lexicographically(self):
        """Bug #11: plain sorted() puts '10.0.0' before '2.0.0'."""
        payload = json.dumps({
            "adas-local": {
                "adas-df/1.0.0": {}, "adas-df/10.0.0": {}, "adas-df/2.0.0": {},
            }
        })
        with mock.patch("subprocess.run", return_value=_fake_run(0, payload)):
            versions = conan_publish.list_remote_versions("adas-df")
        self.assertEqual(versions, ["1.0.0", "2.0.0", "10.0.0"])

    def test_genuinely_empty_is_not_an_error(self):
        payload = json.dumps({"adas-local": {}})
        with mock.patch("subprocess.run", return_value=_fake_run(0, payload)):
            versions = conan_publish.list_remote_versions("adas-df")
        self.assertEqual(versions, [])

    def test_expired_session_raises_remote_unavailable(self):
        """Bug #9: an expired JWT session makes `conan list` return
        {"error": "..."} for the remote key instead of a refs dict - this
        used to be silently filtered into the same [] as a real empty
        result by the "/" in ref check."""
        payload = json.dumps({"adas-local": {"error": "not authenticated"}})
        with mock.patch("subprocess.run", return_value=_fake_run(0, payload)):
            with self.assertRaises(conan_publish.RemoteUnavailableError):
                conan_publish.list_remote_versions("adas-df")

    def test_nonzero_returncode_raises_remote_unavailable(self):
        with mock.patch("subprocess.run", return_value=_fake_run(1, "", "connection refused")):
            with self.assertRaises(conan_publish.RemoteUnavailableError):
                conan_publish.list_remote_versions("adas-df")

    def test_unreachable_host_raises_remote_unavailable(self):
        import subprocess
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("conan", 15)):
            with self.assertRaises(conan_publish.RemoteUnavailableError):
                conan_publish.list_remote_versions("adas-df")


class BumpVersionFileTests(unittest.TestCase):

    def test_rejects_non_numeric_version(self):
        """Bug #12: bump_version_file used to accept anything - Conan itself
        also accepts arbitrary version strings for a package with no
        CMakeLists.txt to reject them (confirmed live by publishing
        adas-testpkg/1.0.0-alpha)."""
        with mock.patch("builtins.open", mock.mock_open()):
            with self.assertRaises(ValueError):
                conan_publish.bump_version_file("VERSION", "1.0.0-alpha")

    def test_accepts_plain_semver(self):
        m = mock.mock_open()
        with mock.patch("builtins.open", m):
            conan_publish.bump_version_file("VERSION", "1.2.3")
        m().write.assert_called_once_with("1.2.3\n")


class PublishCommandsTests(unittest.TestCase):
    """RD-05 (remove_develop_mode_plan.md, WP-4): was
    PublishCommandsEditablePathTests (Bug #17's regression test) - the
    editable-aware 4/5-command path is gone with is_editable()/
    was_editable (RD-01's own verdict: with no editables ever registered,
    that path was permanently unreachable dead code, not a behaviour
    users ever saw). What remains is the always-taken plain path."""

    def setUp(self):
        patcher_deps = mock.patch.object(conan_publish, "_missing_dependencies", return_value=[])
        self.addCleanup(patcher_deps.stop)
        patcher_deps.start()
        patcher_variants = mock.patch.object(
            conan_publish, "_own_variants", return_value=["base", "cus1"])
        self.addCleanup(patcher_variants.stop)
        patcher_variants.start()

    def test_publish_commands_multi_variant_component(self):
        """One `conan create` per declared variant (base, cus1) plus one
        upload, in that order (plan.md item 14/15 follow-up: a publish
        must build every declared variant, not just one, before the
        single upload call)."""
        cmds = conan_publish.publish_commands("modules/df", "adas-df", "1.0.3")

        self.assertEqual(len(cmds), 3)
        self.assertEqual(cmds[0][:2], ["conan", "create"])
        self.assertIn("project=base", cmds[0])
        self.assertEqual(cmds[1][:2], ["conan", "create"])
        self.assertIn("project=cus1", cmds[1])
        self.assertEqual(cmds[2][:3], ["conan", "upload", "adas-df/1.0.3"])

    def test_publish_commands_single_variant_component(self):
        """interfaces/shared_config have no project axis at all -
        _own_variants() returns [None] - exactly one create (no -o project
        flag) plus one upload, same shape as before this change."""
        with mock.patch.object(conan_publish, "_own_variants", return_value=[None]):
            cmds = conan_publish.publish_commands("modules/interfaces", "adas-interfaces", "1.0.1")

        self.assertEqual(len(cmds), 2)
        self.assertEqual(
            cmds[0], ["conan", "create", ".", "--build=missing", "-s", "build_type=Release"])
        self.assertEqual(cmds[1][:3], ["conan", "upload", "adas-interfaces/1.0.1"])


class PublishCommandsMissingDependencyTests(unittest.TestCase):
    """Bug #15's regression test."""

    def test_raises_when_own_adas_dependency_missing_from_remote(self):
        with mock.patch.object(conan_publish, "_own_variants", return_value=["base"]), \
             mock.patch.object(
                conan_publish, "_missing_dependencies",
                return_value=["adas-interfaces/1.0.0"],
             ):
            with self.assertRaises(conan_publish.MissingDependencyError):
                conan_publish.publish_commands("modules/df", "adas-df", "1.0.3")

    def test_raises_when_dependency_missing_for_any_variant(self):
        """The missing-deps x multi-variant combination: `base` has no
        missing dependency, only `cus1` does - the loop must check every
        variant, not just the first, and the second variant's gap alone
        must still be caught."""
        def fake_missing(component_dir, remote, variant):
            return ["adas-interfaces/1.0.0"] if variant == "cus1" else []

        with mock.patch.object(conan_publish, "_own_variants", return_value=["base", "cus1"]), \
             mock.patch.object(conan_publish, "_missing_dependencies", side_effect=fake_missing):
            with self.assertRaises(conan_publish.MissingDependencyError):
                conan_publish.publish_commands("modules/df", "adas-df", "1.0.3")

    def test_missing_dependency_raises_before_create_commands_built(self):
        """A component that can't be published gets no create/upload
        commands at all - the missing-dependency check must happen (and
        raise) strictly before publish_commands() builds anything."""
        with mock.patch.object(conan_publish, "_own_variants", return_value=["base"]), \
             mock.patch.object(
                conan_publish, "_missing_dependencies",
                return_value=["adas-interfaces/1.0.0"],
             ):
            with self.assertRaises(conan_publish.MissingDependencyError):
                conan_publish.publish_commands("modules/df", "adas-df", "1.0.3")

    def test_own_adas_requires_filters_out_third_party(self):
        build_yml = {
            "variants": {
                "base": {
                    "requires": [
                        "protobuf/3.21.12",
                        "yaml-cpp/0.8.0",
                        "adas-interfaces/1.0.0",
                        "adas-shared-config/1.0.0",
                    ]
                }
            }
        }
        m = mock.mock_open(read_data="")
        with mock.patch("os.path.isfile", return_value=True), \
             mock.patch("builtins.open", m), \
             mock.patch("yaml.safe_load", return_value=build_yml):
            refs = conan_publish._own_adas_requires("modules/df", "base")
        self.assertEqual(refs, ["adas-interfaces/1.0.0", "adas-shared-config/1.0.0"])

    def test_own_adas_requires_empty_when_no_build_yml(self):
        with mock.patch("os.path.isfile", return_value=False):
            refs = conan_publish._own_adas_requires("modules/shared_config", None)
        self.assertEqual(refs, [])

    def test_own_adas_requires_empty_when_variant_is_none(self):
        refs = conan_publish._own_adas_requires("modules/interfaces", None)
        self.assertEqual(refs, [])


class OwnVariantsTests(unittest.TestCase):
    """_has_project_option() is always mocked here, never left to shell
    out to a real `conan inspect` - these are unit tests, not integration
    tests against this machine's actual Conan cache/recipes."""

    def test_reads_conf_build_yml_variants_sorted(self):
        build_yml = {"variants": {"cus1": {}, "base": {}}}
        m = mock.mock_open(read_data="")
        with mock.patch.object(conan_publish, "_has_project_option", return_value=True), \
             mock.patch("os.path.isfile", return_value=True), \
             mock.patch("builtins.open", m), \
             mock.patch("yaml.safe_load", return_value=build_yml):
            variants = conan_publish._own_variants("modules/df")
        self.assertEqual(variants, ["base", "cus1"])

    def test_sentinel_when_no_build_yml(self):
        with mock.patch.object(conan_publish, "_has_project_option", return_value=True), \
             mock.patch("os.path.isfile", return_value=False):
            variants = conan_publish._own_variants("modules/df")
        self.assertEqual(variants, [None])

    def test_sentinel_when_conanfile_has_no_project_option(self):
        """The regression this class exists to catch: modules/interfaces
        has a conf/build.yml with base/cus1 variants (plan.md item 12,
        added only to stop build.py's dispatcher from skipping it), but
        its conanfile.py declares no `project` option at all. An earlier
        version of _own_variants() only checked whether conf/build.yml
        existed, and would have generated `-o project=base` /
        `-o project=cus1` conan create commands for interfaces - a hard
        Conan error, since that option was never declared. _own_variants()
        must defer to _has_project_option(), not file existence alone."""
        with mock.patch.object(conan_publish, "_has_project_option", return_value=False):
            variants = conan_publish._own_variants("modules/interfaces")
        self.assertEqual(variants, [None])

    def test_has_project_option_true_when_conan_inspect_declares_it(self):
        payload = json.dumps({"options_definitions": {"project": ["ANY"]}})
        with mock.patch("subprocess.run", return_value=_fake_run(0, payload)):
            self.assertTrue(conan_publish._has_project_option("modules/df"))

    def test_has_project_option_false_when_conan_inspect_omits_it(self):
        payload = json.dumps({"options_definitions": {}})
        with mock.patch("subprocess.run", return_value=_fake_run(0, payload)):
            self.assertFalse(conan_publish._has_project_option("modules/interfaces"))


if __name__ == "__main__":
    unittest.main()
