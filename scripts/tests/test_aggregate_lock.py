"""
scripts/tests/test_aggregate_lock.py

WP-13 (cache_first_no_server_plan.md §5): NS-61 - the root aggregate pins the
cache dependencies of each tick list in a lock of its own, and modules built
here (`--with`, a named data module) are not pinned (LK-D5); NS-62's root half
(`--update-lock`); NS-64/NS-65 as the aggregate prints them. The machinery is
lockfiles.LockSession, shared with the component builder and tested for itself
in modules/toolchain/tests/test_lockfiles.py; this file holds the aggregate's
wiring. Conan is stubbed: the install command line is what is asserted.

Run:
    py -3.12 -m unittest scripts.tests.test_aggregate_lock
"""
import hashlib
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import build as adas_build  # noqa: E402 - path must be set up first
from conan_home_resolution import load_lockfiles  # noqa: E402

REV_A, REV_B, REV_TP = "a" * 32, "b" * 32, "c" * 32
CONFS = {
    "df": {"recipe": {"type": "shared-library"},
           "variants": {"base": {"requires": ["adas-mathlib/1.0.0", "adas-shared-config/1.0.0"]}}},
    "mathlib": {"recipe": {"type": "static-library"}, "variants": {"base": {"requires": []}}},
    "shared-config": {"recipe": {"type": "unknown"}, "variants": {"base": {"requires": []}}},
}


def lock_text(pins):
    return json.dumps({"version": "0.5", "requires": [f"{r}#{v}%{t}" for r, v, t in pins],
                       "build_requires": [], "python_requires": [], "config_requires": []})


class AggregateLockTests(unittest.TestCase):
    def setUp(self):
        self.lockfiles = load_lockfiles()
        self.assertIsNotNone(self.lockfiles, "modules/toolchain must be checked out for these tests")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = tmp.name
        self.installs = []
        self.install_writes = [("adas-mathlib/1.0.0", REV_A, 100.0),
                               ("adas-shared-config/1.0.0", REV_B, 100.0),
                               ("zlib/1.3.1", REV_TP, 50.0)]
        self.install_rc = 0
        self.cache = {"adas-mathlib/1.0.0": {REV_A: 100.0},
                      "adas-shared-config/1.0.0": {REV_B: 100.0},
                      "zlib/1.3.1": {REV_TP: 50.0}}

        def fake_install(cmd, cwd, explain=None):
            self.installs.append(list(cmd))
            if "--lockfile-out" in cmd and self.install_rc == 0:
                with open(cmd[cmd.index("--lockfile-out") + 1], "w", encoding="utf-8") as f:
                    f.write(lock_text(self.install_writes))
            return self.install_rc, {"graph": {"nodes": {}}}

        patch = mock.patch.object
        for p in (
                patch(adas_build, "ROOT", self.root),
                patch(adas_build, "is_valid_module", return_value=True), patch(adas_build, "absent_first_party_refs", return_value={}),
                patch(adas_build, "module_package_type", side_effect=lambda m: CONFS[m]["recipe"]["type"]),
                patch(adas_build, "load_module_conf", side_effect=CONFS.get),
                patch(adas_build, "module_version", return_value="1.0.0"),
                patch(adas_build, "module_package_name", side_effect=lambda m: f"adas-{m}"),
                patch(adas_build, "package_to_module_map",
                      return_value={f"adas-{m}": m for m in CONFS}),
                patch(adas_build, "apply_conan_home"),
                patch(adas_build, "missing_toolchain_pin", return_value=[]),
                patch(adas_build, "missing_cache_refs", return_value=[]),
                patch(adas_build, "stale_cache_refs", return_value=([], [])),
                patch(adas_build, "outdated_format_refs", return_value=[]),
                patch(adas_build, "package_named_data_modules", return_value=[]),
                patch(adas_build, "generate_aggregate_conanfile"),
                patch(adas_build, "generate_aggregate_cmakelists"),
                patch(adas_build, "remove_stale_build_dirs"),
                patch(adas_build, "refresh_aggregate_used_shortcuts"),
                patch(adas_build, "read_editable_registrations", return_value={}),
                patch(adas_build, "resolved_kind_mismatches", return_value=({}, [])),
                patch(adas_build, "resolved_package_folders", return_value={}),
                patch(adas_build, "resolved_lib_dirs", return_value={}),
                patch(adas_build, "first_party_package_mode_editable_violations", return_value=[]),
                patch(adas_build, "run_logged", return_value=0),
                patch(adas_build, "run_install_logged", side_effect=fake_install),
                patch(adas_build, "active_conan_home", return_value=os.path.join(self.root, "home")),
                patch(self.lockfiles, "cache_revisions", side_effect=lambda *a, **k: self.cache),
        ):
            p.start()
            self.addCleanup(p.stop)

    def run_build(self, with_mods=None, with_all=False, clean=False, update_lock=False,
                  remotes_state=False):
        code = None
        try:
            adas_build.run_aggregate_build("base", "df", "sil", "vs2026", with_mods or [], with_all,
                                           clean, False, mode="package", remotes_state=remotes_state,
                                           update_lock=update_lock)
        except SystemExit as exc:
            code = exc.code
        logs = os.path.join(self.root, "conan_workarea", "logs")
        with open(os.path.join(logs, sorted(os.listdir(logs))[-1]), encoding="utf-8") as f:
            return code, f.read()

    def locks(self):
        folder = os.path.join(self.root, "conan_workarea", "locks")
        return sorted(os.listdir(folder)) if os.path.isdir(folder) else []

    def lock_file(self, index=0):
        return os.path.join(self.root, "conan_workarea", "locks", self.locks()[index])

    def pins(self, index=0):
        return [p.name for p in self.lockfiles.read_pins(self.lock_file(index))]

    def sha(self):
        with open(self.lock_file(), "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    # NS-61 -------------------------------------------------------------------
    def test_no_lock_is_created_and_a_second_build_uses_it_strictly(self):
        code, text = self.run_build()
        self.assertIsNone(code)
        self.assertIn("--lockfile-out", self.installs[0])
        self.assertNotIn("--lockfile", self.installs[0])
        self.assertIn("lock created:", text)
        code, text = self.run_build()
        second = self.installs[1]
        self.assertEqual(second[second.index("--lockfile") + 1], self.lock_file())
        self.assertNotIn("--lockfile-partial", second)
        self.assertNotIn("--lockfile-out", second)

    def test_a_build_never_rewrites_an_existing_lock(self):
        self.run_build()
        before = self.sha()
        self.cache["adas-mathlib/1.0.0"][REV_B] = 300.0  # something newer appears in the cache
        self.run_build()
        self.run_build()
        self.assertEqual(before, self.sha())

    def test_a_module_built_here_is_absent_from_the_lock(self):
        """LK-D5. The stubbed Conan writes every package into the lock, including
        the ticked one - the aggregate must take it out."""
        self.run_build(with_mods=["mathlib"])
        self.assertNotIn("adas-mathlib", self.pins())
        self.assertIn("zlib", self.pins())

    def test_planted_a_lock_that_pins_the_ticked_module_is_caught(self):
        """R-REQ-9: what the test above looks for, shown to be findable."""
        self.run_build()  # nothing ticked: mathlib comes from the cache and IS pinned
        self.assertIn("adas-mathlib", self.pins())

    def test_a_named_data_module_is_left_out_and_partial_is_used_only_then(self):
        self.run_build(with_mods=["shared-config"])
        self.assertNotIn("adas-shared-config", self.pins())
        self.run_build(with_mods=["shared-config"])
        used = self.installs[1]
        self.assertIn("--lockfile-partial", used)
        self.run_build()  # a different tick list -> a different lock, strict
        self.assertEqual(len(self.locks()), 2)
        self.assertNotIn("--lockfile-partial", self.installs[2])

    def test_each_tick_list_has_its_own_lock(self):
        self.run_build()
        self.run_build(with_mods=["mathlib"])
        self.run_build(with_all=True)
        self.assertEqual(len(self.locks()), 3)

    def test_clean_removes_the_build_folder_but_not_the_lock(self):
        self.run_build()
        marker = os.path.join(self.root, "conan_workarea",
                              "build-sil-vs2026-base-df-pkg-solo", "x.txt")
        # the aggregate folder for the no-tick case is "-solo"; make a real one to clean
        agg = os.path.join(self.root, "conan_workarea", "build-sil-vs2026-base-df-pkg-agg")
        os.makedirs(agg, exist_ok=True)
        with open(os.path.join(agg, "x.txt"), "w") as f:
            f.write("x")
        self.run_build(with_mods=["mathlib"])
        before = self.locks()
        self.run_build(with_mods=["mathlib"], clean=True)
        self.assertFalse(os.path.exists(os.path.join(agg, "x.txt")))
        self.assertEqual(before, self.locks())
        del marker

    # NS-62 (root half) ------------------------------------------------------
    def test_update_lock_resolves_fresh_and_reports_old_to_new(self):
        self.run_build()
        self.install_writes[0] = ("adas-mathlib/1.0.0", REV_B, 300.0)
        self.cache["adas-mathlib/1.0.0"][REV_B] = 300.0
        code, text = self.run_build(update_lock=True)
        self.assertIsNone(code)
        update = self.installs[1]
        self.assertIn("--lockfile-out", update)
        self.assertNotIn("--lockfile", update)
        self.assertIn("lock updated:", text)
        self.assertIn(f"adas-mathlib/1.0.0  #{REV_A[:8]} -> #{REV_B[:8]}", text)

    def test_a_failed_update_keeps_the_old_lock(self):
        self.run_build()
        before = self.sha()
        self.install_rc = 1
        code, _ = self.run_build(update_lock=True)
        self.assertEqual(code, 1)
        self.assertEqual(before, self.sha())

    # NS-64 -----------------------------------------------------------------
    def test_newer_cache_revision_prints_the_notice_with_the_root_command(self):
        self.run_build(with_mods=["shared-config"])
        self.cache["adas-mathlib/1.0.0"][REV_B] = 300.0
        code, text = self.run_build(with_mods=["shared-config"])
        (line,) = [l for l in text.splitlines() if l.startswith("adas-mathlib/1.0.0 pinned")]
        self.assertIn(f"newer #{REV_B[:8]}", line)
        run = line.split("Run: ", 1)[1]
        self.assertIn("scripts/build.py df -t sil -p vs2026 -P base --with shared-config --update-lock", run)
        self.assertIn(self.root, run)
        self.assertNotIn("<", line)

    def test_no_notice_when_nothing_is_newer(self):
        self.run_build()
        _, text = self.run_build()
        (line,) = [l for l in text.splitlines() if l.startswith("adas-mathlib/1.0.0 pinned")]
        self.assertNotIn("newer", line)

    # NS-65 -----------------------------------------------------------------
    def test_a_pinned_revision_missing_from_the_cache_is_refused_before_conan(self):
        self.run_build()
        self.cache["adas-mathlib/1.0.0"] = {REV_B: 0.5}  # older than the pin: no LK-D10 refresh
        count = len(self.installs)
        code, text = self.run_build()
        self.assertEqual(code, 1)
        self.assertEqual(len(self.installs), count, "conan install must not have run")
        for word in ("Reason:", "Fix:", "Run:"):
            self.assertIn(word, text)
        self.assertEqual(len([l for l in text.splitlines() if l.startswith("Run:")]), 1)
        self.assertIn("--update-lock", text)

    def test_requirement_not_in_lock_is_explained(self):
        self.run_build()

        def failing(cmd, cwd, explain=None):
            self.installs.append(list(cmd))
            lines = explain("ERROR: Requirement 'adas-new/1.0.0' not in lockfile 'requires'")
            for line in lines or []:
                adas_build.log(line)
            return 1, None

        with mock.patch.object(adas_build, "run_install_logged", side_effect=failing):
            code, text = self.run_build()
        self.assertEqual(code, 1)
        self.assertIn("adas-new/1.0.0 is required now", text)
        self.assertIn("Run:", text)


class ScriptsAndComponentAgree(unittest.TestCase):
    """The root and the component builder load the SAME implementation."""

    def test_the_root_loads_the_toolchain_checkouts_file(self):
        module = load_lockfiles()
        expected = os.path.join("modules", "toolchain", "adas_build_tools", "lockfiles.py")
        self.assertTrue(module.__file__.endswith(expected), module.__file__)


if __name__ == "__main__":
    unittest.main()
