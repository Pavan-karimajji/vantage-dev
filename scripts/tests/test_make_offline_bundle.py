"""scripts/tests/test_make_offline_bundle.py

OF-03 / OF-05 (offline_setup_plan.md): pin derivation, package filtering and
the bundle manifest of scripts/make_offline_bundle.py. Pure unittest; no conan,
no pip, no network.

Run:
    python -m unittest discover -s scripts/tests   (from the superproject root)
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import make_offline_bundle as mob  # noqa: E402 - path must be set up first

# vantage-dev: these tests assert 1v-superproject's own module set (they need df).
_DF_DECLARED = "modules/df" in ((Path(__file__).resolve().parents[2] / ".gitmodules")
                                .read_text(encoding="utf-8"))
_DF_REASON = "asserts 1v-superproject's own module set (df, CARLA, viz); not this superproject's"

PROFILE = {"os": "Windows", "arch": "x86_64", "build_type": "Release",
           "compiler": "msvc", "compiler.version": "195", "compiler.cppstd": "17"}


def _module(root, name, requires=(), tool_requires=(), toolchain=None, build_tools=None):
    mod = Path(root) / "modules" / name
    (mod / "conf").mkdir(parents=True)
    body = "variants:\n  base:\n"
    body += "    requires:\n" + "".join(f"      - {r}\n" for r in requires) if requires else ""
    body += "    tool_requires:\n" + "".join(f"      - {r}\n" for r in tool_requires) if tool_requires else ""
    body += "    sil:\n      cmake_targets: [\"mcap::mcap\"]\n      requires: [\"mcap::mcap\"]\n"
    (mod / "conf" / "build.yml").write_text(body, encoding="utf-8")
    if toolchain:
        (mod / "conanfile.py").write_text(f'class C:\n    python_requires = "{toolchain}"\n', encoding="utf-8")
    if build_tools:
        (mod / "conf" / "build_tools.version").write_text(build_tools + "\n", encoding="utf-8")


class DerivePinsTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = self._tmp.name
        _module(self.root, "df", requires=["protobuf/3.21.12", "adas-mathlib/1.0.0"],
                tool_requires=["protobuf/3.21.12"], toolchain="adas-toolchain/1.0.4",
                build_tools="1.0.17")
        _module(self.root, "sim", requires=["yaml-cpp/0.8.0"], toolchain="adas-toolchain/1.0.5",
                build_tools="1.0.18")

    def test_derives_every_kind_and_skips_first_party_and_targets(self):
        pins = mob.derive_pins(self.root)
        self.assertEqual(pins["third_party"], ["protobuf/3.21.12", "yaml-cpp/0.8.0"])
        self.assertEqual(pins["third_party_tool"], ["protobuf/3.21.12"])
        self.assertEqual(pins["toolchain"], ["adas-toolchain/1.0.4", "adas-toolchain/1.0.5"])
        self.assertEqual(pins["build_tools"], ["adas-build-tools/1.0.17", "adas-build-tools/1.0.18"])
        self.assertNotIn("adas-mathlib/1.0.0", mob.all_pin_refs(pins))   # first party: from the checkout
        self.assertFalse([r for r in mob.all_pin_refs(pins) if "::" in r])  # cmake target, not a ref

    def test_planted_violation_a_new_pin_appears_in_the_next_derivation(self):
        """PASS: bumping any pin changes the bundle list with no script edit.
        FAIL (hard-coded versions): the new refs would be missing."""
        _module(self.root, "vdy", requires=["fmt/10.2.1"], toolchain="adas-toolchain/1.0.6",
                build_tools="1.0.19")
        refs = mob.all_pin_refs(mob.derive_pins(self.root))
        for new in ("fmt/10.2.1", "adas-toolchain/1.0.6", "adas-build-tools/1.0.19"):
            self.assertIn(new, refs)

    def test_a_git_tag_build_tools_pin_is_not_a_conan_ref(self):
        _module(self.root, "viz", build_tools="v1.0.20")
        self.assertNotIn("adas-build-tools/v1.0.20", mob.all_pin_refs(mob.derive_pins(self.root)))

    @unittest.skipUnless(_DF_DECLARED, _DF_REASON)
    def test_the_real_repo_derives_the_known_pins(self):
        refs = mob.all_pin_refs(mob.derive_pins())
        for ref in ("protobuf/3.21.12", "yaml-cpp/0.8.0", "mcap/1.2.0"):
            self.assertIn(ref, refs)


class MatchingPackagesTests(unittest.TestCase):

    def test_conflicting_settings_are_dropped_omitted_keys_are_kept(self):
        packages = {
            "full": {"info": {"settings": dict(PROFILE)}},
            "c_lib": {"info": {"settings": {"os": "Windows", "arch": "x86_64", "build_type": "Release",
                                            "compiler": "msvc", "compiler.version": "195"}}},
            "old_compiler": {"info": {"settings": {**PROFILE, "compiler.version": "193"}}},
            "debug": {"info": {"settings": {**PROFILE, "build_type": "Debug"}}},
            "settingsless": {"info": {}},
        }
        self.assertEqual(sorted(mob.matching_packages(packages, PROFILE)),
                         ["c_lib", "full", "settingsless"])

    def test_no_profile_keeps_everything(self):
        self.assertEqual(len(mob.matching_packages({"a": {}, "b": {}}, None)), 2)


class ManifestTests(unittest.TestCase):

    def _manifest(self, saved):
        pins = {"third_party": ["protobuf/3.21.12"], "third_party_tool": [],
                "toolchain": ["adas-toolchain/1.0.4"], "build_tools": ["adas-build-tools/1.0.17"]}
        text = mob.manifest_text("vs2026", "2026-09-21", "abc123", "Conan version 2.32.0", saved, pins,
                                 ["conan-2.32.0-py3-none-any.whl"])
        return text, pins

    def test_contents_and_round_trip(self):
        text, _ = self._manifest([("protobuf/3.21.12", "rev1", 2), ("adas-toolchain/1.0.4", "rev2", 0)])
        self.assertIn("platform: vs2026", text)
        self.assertIn("source_commit: abc123", text)
        self.assertIn("ref: protobuf/3.21.12#rev1 packages=2", text)
        self.assertIn("wheel: conan-2.32.0-py3-none-any.whl", text)
        parsed = mob.parse_manifest(text)
        self.assertEqual(parsed["platform"], "vs2026")
        self.assertEqual(parsed["refs"], {"protobuf/3.21.12": "rev1", "adas-toolchain/1.0.4": "rev2"})
        self.assertEqual(parsed["wheels"], ["conan-2.32.0-py3-none-any.whl"])

    def test_planted_violation_a_pin_missing_from_the_manifest_is_reported(self):
        text, pins = self._manifest([("protobuf/3.21.12", "rev1", 2)])  # toolchain + build-tools absent
        self.assertEqual(mob.missing_pins(mob.parse_manifest(text), pins),
                         ["adas-build-tools/1.0.17", "adas-toolchain/1.0.4"])

    def test_complete_manifest_reports_nothing_missing(self):
        text, pins = self._manifest([("protobuf/3.21.12", "r1", 2), ("adas-toolchain/1.0.4", "r2", 0),
                                     ("adas-build-tools/1.0.17", "r3", 1)])
        self.assertEqual(mob.missing_pins(mob.parse_manifest(text), pins), [])


class DryRunTests(unittest.TestCase):

    def test_dry_run_prints_pins_and_touches_nothing(self):
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = mob.main(["--platform", "vs2026", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("third_party:", out.getvalue())
        self.assertIn("build_tools:", out.getvalue())


if __name__ == "__main__":
    unittest.main()
