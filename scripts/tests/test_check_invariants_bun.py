"""
scripts/tests/test_check_invariants_bun.py

Regression tests for BUN-1 (scripts/check_invariants.py, NS-42(b) --
cache_first_no_server_plan.md, RQ-6). A stale offline bundle passes a
cold-machine build right up until the moment nothing else can supply an
`adas-build-tools`/`adas-toolchain` package -- found live 2026-09-25 when
the bundle shipped `adas-build-tools/1.0.19` while every component had
already moved its `conf/build_tools.version` pin to `1.0.22`. This is the
planted-violation proof (R-REQ-9): a stale manifest fails, a matching one
and a missing bundle both pass.

Isolated from the real tree with a tempfile fixture (same pattern as
test_check_invariants_rem.py) -- check_bun1() walks `root`, so a small
synthetic tree under a temp dir exercises the same logic without ever
touching the real misc/offline_bundle/ or modules/.

Run:
    py -m unittest discover -s scripts/tests
    (from the superproject root)
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import check_invariants  # noqa: E402 - path must be set up first


class _BundleTreeFixture(unittest.TestCase):
    """Builds a synthetic tree: N components each with their own
    conf/build_tools.version, a modules/toolchain/VERSION, and (unless a
    test wants "no bundle present") a misc/offline_bundle/bundle_manifest
    .txt."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="bun_invariant_")
        self.root = Path(self._tmp)

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _write_component(self, name, build_tools_pin):
        pin_file = self.root / "modules" / name / "conf" / "build_tools.version"
        pin_file.parent.mkdir(parents=True, exist_ok=True)
        pin_file.write_text(build_tools_pin + "\n", encoding="utf-8")

    def _write_toolchain_version(self, version):
        version_file = self.root / "modules" / "toolchain" / "VERSION"
        version_file.parent.mkdir(parents=True, exist_ok=True)
        version_file.write_text(version + "\n", encoding="utf-8")

    def _write_manifest(self, build_tools_ref, toolchain_ref):
        manifest = self.root / "misc" / "offline_bundle" / "vs2026" / "bundle_manifest.txt"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "platform: vs2026",
            "date: 2026-09-25",
            "source_commit: deadbeef",
            "conan_version: Conan version 2.32.0",
            f"ref: {build_tools_ref}#abc packages=1",
            f"ref: {toolchain_ref}#def packages=0",
            f"pin: {build_tools_ref}",
            f"pin: {toolchain_ref}",
        ]
        manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")


class CheckBun1Tests(_BundleTreeFixture):

    def test_no_bundle_present_passes_silently(self):
        self._write_component("df", "1.0.22")
        # No misc/offline_bundle/bundle_manifest.txt written at all.
        self.assertEqual(check_invariants.check_bun1(self.root), [])

    def test_matching_bundle_passes(self):
        self._write_component("df", "1.0.22")
        self._write_component("interfaces", "1.0.22")
        self._write_toolchain_version("1.0.5")
        self._write_manifest("adas-build-tools/1.0.22", "adas-toolchain/1.0.5")
        self.assertEqual(check_invariants.check_bun1(self.root), [])

    def test_planted_stale_build_tools_pin_is_caught(self):
        """The exact live defect: manifest ships an older adas-build-tools
        than what components now pin."""
        self._write_component("df", "1.0.22")
        self._write_component("interfaces", "1.0.22")
        self._write_toolchain_version("1.0.5")
        self._write_manifest("adas-build-tools/1.0.19", "adas-toolchain/1.0.5")
        findings = check_invariants.check_bun1(self.root)
        self.assertTrue(findings, "stale adas-build-tools pin must be caught")
        joined = " ".join(findings)
        self.assertIn("BUN-1 (RQ-6)", joined)
        self.assertIn("adas-build-tools/1.0.19", joined)
        self.assertIn("df pins '1.0.22'", joined)
        # Restored (matching) tree passes -- watched it fail, watched it pass.
        self._write_manifest("adas-build-tools/1.0.22", "adas-toolchain/1.0.5")
        self.assertEqual(check_invariants.check_bun1(self.root), [])

    def test_planted_stale_toolchain_pin_is_caught(self):
        self._write_component("df", "1.0.22")
        self._write_toolchain_version("1.0.5")
        self._write_manifest("adas-build-tools/1.0.22", "adas-toolchain/1.0.4")
        findings = check_invariants.check_bun1(self.root)
        self.assertTrue(findings, "stale adas-toolchain pin must be caught")
        joined = " ".join(findings)
        self.assertIn("BUN-1 (RQ-6)", joined)
        self.assertIn("adas-toolchain/1.0.4", joined)
        self.assertIn("modules/toolchain/VERSION is '1.0.5'", joined)

    def test_a_vtag_pin_is_out_of_scope(self):
        """A `vX.Y.Z` build_tools.version installs via pip (docs/imp_design.md
        §10), never names a Conan ref -- never compared against the bundle."""
        self._write_component("df", "v1.0.22")
        self._write_toolchain_version("1.0.5")
        self._write_manifest("adas-build-tools/1.0.19", "adas-toolchain/1.0.5")
        self.assertEqual(check_invariants.check_bun1(self.root), [])

    def test_multiple_components_all_named_in_one_finding(self):
        self._write_component("df", "1.0.22")
        self._write_component("interfaces", "1.0.22")
        self._write_toolchain_version("1.0.5")
        self._write_manifest("adas-build-tools/1.0.19", "adas-toolchain/1.0.5")
        findings = check_invariants.check_bun1(self.root)
        joined = " ".join(findings)
        self.assertIn("df pins '1.0.22'", joined)
        self.assertIn("interfaces pins '1.0.22'", joined)


if __name__ == "__main__":
    unittest.main()
