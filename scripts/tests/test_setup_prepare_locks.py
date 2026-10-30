"""
scripts/tests/test_setup_prepare_locks.py

WP-13 / NS-63 (cache_first_no_server_plan.md §5, LK-D3): `setup.py --prepare
<m> -t -p -P` moves the locks of the root build keys it prepared for - the
module's own lock (root solo builds delegate to it) and every aggregate lock of
that key - to the revisions it just created, and prints old -> new. Nothing
else moves a lock but `--update-lock`. Real files in a scratch superproject,
real lockfiles.py; only Conan's cache listing is stubbed.

Run:
    py -3.12 -m unittest scripts.tests.test_setup_prepare_locks
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import setup  # noqa: E402 - path must be set up first
from conan_home_resolution import load_lockfiles  # noqa: E402

REV_A, REV_B, REV_TP = "a" * 32, "b" * 32, "c" * 32
IFACE = "adas-interfaces/1.0.0"


def lock_text(pins):
    return json.dumps({"version": "0.5", "requires": [f"{r}#{v}%{t}" for r, v, t in pins],
                       "build_requires": [], "python_requires": [], "config_requires": []})


class _Ctx:
    prepare, target, platform, project = "df", "sil", "vs2026", "base"


class RefreshRootLocksTests(unittest.TestCase):
    def setUp(self):
        self.lockfiles = load_lockfiles()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "super"
        self.elsewhere = Path(tmp.name) / "standalone_df"
        self.home = Path(tmp.name) / "home"
        pins = [(IFACE, REV_A, 100.0), ("zlib/1.3.1", REV_TP, 50.0)]
        self.own = self.lockfiles.lock_path(self.root / "modules" / "df", "df-sil-vs2026-base")
        self.agg = self.lockfiles.lock_path(self.root, "build-sil-vs2026-base-df-pkg-agg-12345678")
        self.solo = self.lockfiles.lock_path(self.root, "build-sil-vs2026-base-df-pkg-solo-9abcdef0")
        self.other_project = self.lockfiles.lock_path(self.root / "modules" / "df", "df-sil-vs2026-cus1")
        self.other_module = self.lockfiles.lock_path(self.root, "build-sil-vs2026-base-vdy-pkg-agg-12345678")
        self.standalone = self.lockfiles.lock_path(self.elsewhere, "df-sil-vs2026-base")
        self.files = [self.own, self.agg, self.solo, self.other_project, self.other_module,
                      self.standalone]
        for path in self.files:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(lock_text(pins), encoding="utf-8")
        self.before = {p: p.read_bytes() for p in self.files}
        self.cache = {IFACE: {REV_A: 100.0, REV_B: 200.0}, "zlib/1.3.1": {REV_TP: 50.0}}
        for p in (mock.patch.object(setup, "ROOT", self.root),
                  mock.patch.object(setup, "active_conan_home", return_value=str(self.home)),
                  mock.patch.object(self.lockfiles, "cache_revisions",
                                    side_effect=lambda *a, **k: self.cache),
                  mock.patch.object(setup.adas_build, "module_package_name",
                                    side_effect=lambda m: f"adas-{m}"),
                  mock.patch.object(setup.adas_build, "module_version", return_value="1.0.0")):
            p.start()
            self.addCleanup(p.stop)

    def refresh(self, created=("interfaces",)):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            setup.refresh_root_locks(_Ctx, list(created))
        return out.getvalue()

    def pinned(self, path):
        return {p.ref: p.rrev for p in self.lockfiles.read_pins(path)}

    def test_the_keys_own_locks_move_to_the_new_revision_and_say_so(self):
        text = self.refresh()
        for path in (self.own, self.agg, self.solo):
            self.assertEqual(self.pinned(path)[IFACE], REV_B, path)
            self.assertEqual(self.pinned(path)["zlib/1.3.1"], REV_TP)
        self.assertEqual(text.count(f"{IFACE}  #{REV_A[:8]} -> #{REV_B[:8]}"), 3)

    def test_no_other_lock_is_touched(self):
        """A standalone clone elsewhere and another module's lock keep their
        bytes - the point of a per-checkout lock."""
        self.refresh()
        for path in (self.other_module, self.standalone):
            self.assertEqual(path.read_bytes(), self.before[path], path)

    def test_planted_a_refresh_that_touched_every_lock_would_be_caught(self):
        with mock.patch.object(self.lockfiles, "root_lock_paths", return_value=self.files):
            self.refresh()
        self.assertNotEqual(self.standalone.read_bytes(), self.before[self.standalone])

    def test_a_second_prepare_changes_nothing_and_says_already_current(self):
        self.refresh()
        after = {p: p.read_bytes() for p in self.files}
        text = self.refresh()
        self.assertEqual(after, {p: p.read_bytes() for p in self.files})
        self.assertIn("already current", text)

    def test_every_lock_of_the_module_is_refreshed_even_for_another_key(self):
        """LK-D10: --prepare leaves no stale lock of the prepared module behind -
        another project's lock of the same module included."""
        text = self.refresh(created=())
        self.assertEqual(self.pinned(self.other_project)[IFACE], REV_B)
        self.assertEqual(self.pinned(self.other_project)["zlib/1.3.1"], REV_TP)
        self.assertIn(f"lock: df-sil-vs2026-cus1: {IFACE} refreshed {REV_A[:8]} -> {REV_B[:8]}", text)
        for path in (self.other_module, self.standalone):
            self.assertEqual(path.read_bytes(), self.before[path], path)

    def test_nothing_newer_in_the_cache_moves_no_lock(self):
        self.cache[IFACE] = {REV_A: 100.0}
        self.refresh(created=())
        self.assertEqual({p: p.read_bytes() for p in self.files}, self.before)

    def test_planted_stale_third_party_pin_is_never_refreshed_by_prepare(self):
        self.cache["zlib/1.3.1"][REV_B] = 999.0
        self.refresh(created=())
        self.assertEqual(self.pinned(self.other_project)["zlib/1.3.1"], REV_TP)

    def test_a_package_the_lock_does_not_pin_is_not_added(self):
        self.cache["adas-mathlib/1.0.0"] = {REV_B: 300.0}
        self.refresh(created=("interfaces", "mathlib"))
        self.assertNotIn("adas-mathlib/1.0.0", self.pinned(self.own))

    def test_no_lock_yet_is_said_not_invented(self):
        for path in (self.own, self.agg, self.solo):
            path.unlink()
        text = self.refresh()
        self.assertIn("No lock exists yet", text)
        self.assertFalse(self.own.exists())

    def test_the_revisions_origin_is_remembered_for_the_notice(self):
        self.refresh()
        origins = self.lockfiles.read_origins(str(self.home))
        self.assertEqual(origins[f"{IFACE}#{REV_B}"], str(self.root))


if __name__ == "__main__":
    unittest.main()
