"""
scripts/tests/test_bundle_tool_envs.py

PT-08 / PT-09 (python_tool_envs_plan.md D9): make_offline_bundle.py puts
every default Python tool env's wheels in wheels/cp<XY>/ and lists each
lock's sha256 in the manifest; BUN-1 reports a default env lock the
manifest does not carry. Planted violations (R-REQ-9): a changed lock is a
finding, and the message names the bundle's real platform.

Run:
    py -m unittest discover -s scripts/tests
    (from the superproject root)
"""

import contextlib
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import check_invariants  # noqa: E402
import make_offline_bundle as mob  # noqa: E402

REAL_CONFIG = check_invariants.ROOT / "modules" / "toolchain" / "adas_build_tools" / "config.py"

# vantage-dev: these tests assert 1v-superproject's own module set (they need df).
_DF_DECLARED = "modules/df" in ((Path(__file__).resolve().parents[2] / ".gitmodules")
                                .read_text(encoding="utf-8"))
_DF_REASON = "asserts 1v-superproject's own python_envs (df, sim, viz); not this superproject's module set"
LOCK = "# LOCK\nmcap==1.5.0\n"
BUILD_YML = """\
variants: {}
python_envs:
  replay:
    python: "3.12"
    intent: r.txt
    lock: r.lock
    default: true
  viz:
    python: "3.12"
    intent: v.txt
    lock: v.lock
    default: false
"""


class DeriveAndDownloadTests(unittest.TestCase):

    @unittest.skipUnless(_DF_DECLARED, _DF_REASON)
    def test_real_repo_derives_default_envs_only(self):
        envs = {e["label"]: e for e in mob.derive_tool_envs()}
        self.assertEqual(sorted(envs),
                         ["df:carla", "df:replay", "sim:sim", "toolchain:docs", "viz:parity"])
        self.assertEqual(envs["df:replay"]["lock_rel"], "modules/df/tools/carla/replay/requirements.lock")
        self.assertIn("wheel", envs["sim:sim"]["build_requires"])
        self.assertEqual(envs["df:replay"]["build_requires"], [])

    def test_wheels_land_in_cp312_for_the_platform_tag(self):
        calls = []

        def fake_run(cmd, check):
            calls.append(cmd)
            dest = Path(cmd[cmd.index("-d") + 1])
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "mcap-1.5.0-py3-none-any.whl").write_text("", encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0)

        with tempfile.TemporaryDirectory() as tmp:
            wroot = Path(tmp) / "wheels"
            (wroot / "cp312").mkdir(parents=True)
            (wroot / "cp312" / "stale-0.1-py3-none-any.whl").write_text("", encoding="utf-8")
            env = {"label": "df:replay", "python": "3.12", "lock": Path(tmp) / "r.lock",
                   "lock_rel": "modules/df/r.lock", "build_requires": []}
            with mock.patch.object(mob.subprocess, "run", fake_run):
                names, build = mob.download_tool_wheels([env], "vs2026", wroot)
        self.assertEqual(build, [])
        self.assertEqual(names, ["cp312/mcap-1.5.0-py3-none-any.whl"], "stale wheel cleared")
        cmd = calls[0]
        for flag in ("--only-binary=:all:", "--no-deps"):
            self.assertIn(flag, cmd)
        self.assertEqual(cmd[cmd.index("--platform") + 1], "win_amd64")
        self.assertEqual(cmd[cmd.index("--python-version") + 1], "3.12")

    def test_build_backend_is_recorded_with_exact_versions_not_in_the_lock(self):
        def fake_run(cmd, check):
            dest = Path(cmd[cmd.index("-d") + 1])
            dest.mkdir(parents=True, exist_ok=True)
            if "-r" in cmd:
                (dest / "mcap-1.5.0-py3-none-any.whl").write_text("", encoding="utf-8")
            else:
                for w in ("setuptools-84.0.0-py3-none-any.whl", "wheel-0.48.0-py3-none-any.whl"):
                    (dest / w).write_text("", encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0)

        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / "r.lock"
            lock.write_text(LOCK, encoding="utf-8")
            env = {"label": "sim:sim", "python": "3.12", "lock": lock,
                   "lock_rel": "modules/sim/requirements.lock",
                   "build_requires": ["setuptools>=68", "wheel"]}
            with mock.patch.object(mob.subprocess, "run", fake_run):
                names, build = mob.download_tool_wheels([env], "vs2026", Path(tmp) / "wheels")
            self.assertEqual(lock.read_text(encoding="utf-8"), LOCK, "lock untouched")
        self.assertIn("cp312/setuptools-84.0.0-py3-none-any.whl", names)
        text = mob.manifest_text("vs2026", "d", "c", "v", [], {
            "third_party": [], "third_party_tool": [], "toolchain": [], "build_tools": []},
            names, [], build)
        self.assertIn("build-wheel: sim:sim setuptools==84.0.0 "
                      "cp312/setuptools-84.0.0-py3-none-any.whl", text)
        self.assertIn("build-wheel: sim:sim wheel==0.48.0", text)
        self.assertEqual(len(mob.parse_manifest(text)["build_wheels"]), 2)

    def test_glibc_2_35_tags_cover_a_manylinux_2_28_only_wheel(self):
        """PT-19. Planted: the old single-tag list does not cover it."""
        wheel = "numpy-2.5.3-cp312-cp312-manylinux_2_28_x86_64.whl"
        tags = set(wheel[:-4].split("-")[-1].split("."))
        self.assertTrue(tags & set(mob.wheel_platform_tags("ubuntu_gcc")))
        self.assertFalse(tags & {"manylinux2014_x86_64"}, "planted: 2014 alone misses it")
        self.assertEqual(mob.wheel_platform_tags("ubuntu_gcc")[-1], "manylinux_2_35_x86_64")
        self.assertEqual(mob.wheel_platform_tags("vs2026"), ["win_amd64"])

    def test_manifest_round_trips_lock_sha256(self):
        text = mob.manifest_text("vs2026", "2026-09-28", "abc", "Conan 2", [], {
            "third_party": [], "third_party_tool": [], "toolchain": [], "build_tools": []},
            ["cp312/mcap-1.5.0-py3-none-any.whl"], [("df:replay", "modules/df/r.lock", "ff" * 32)])
        self.assertIn("wheel: cp312/mcap-1.5.0-py3-none-any.whl", text)
        self.assertIn(f"lock: df:replay modules/df/r.lock sha256={'ff' * 32}", text)
        parsed = mob.parse_manifest(text)
        self.assertEqual(parsed["locks"], {"ff" * 32: ("df:replay", "modules/df/r.lock")})


class Bun1LockTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="bun_lock_")
        self.root = Path(self._tmp)
        pkg = self.root / "modules" / "toolchain" / "adas_build_tools"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        shutil.copy(REAL_CONFIG, pkg / "config.py")
        comp = self.root / "modules" / "df"
        (comp / "conf").mkdir(parents=True)
        (comp / "conanfile.py").write_text("", encoding="utf-8")
        (comp / "conf" / "build.yml").write_text(BUILD_YML, encoding="utf-8")
        (comp / "r.lock").write_text(LOCK, encoding="utf-8")
        (comp / "v.lock").write_text("# optional, never bundled\n", encoding="utf-8")
        self.lock = comp / "r.lock"

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _manifest(self, sha, platform="ubuntu_gcc"):
        path = self.root / "misc" / "offline_bundle" / platform / "bundle_manifest.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"platform: {platform}\nlock: df:replay modules/df/r.lock sha256={sha}\n",
                        encoding="utf-8")

    def test_matching_lock_passes(self):
        self._manifest(hashlib.sha256(self.lock.read_bytes()).hexdigest())
        self.assertEqual(check_invariants.check_bun1(self.root), [])

    def test_optional_lock_checked_only_when_the_manifest_says_included(self):
        sha = hashlib.sha256(self.lock.read_bytes()).hexdigest()
        self._manifest(sha)
        self.assertEqual(check_invariants.check_bun1(self.root), [], "not included: ignored")
        path = self.root / "misc" / "offline_bundle" / "ubuntu_gcc" / "bundle_manifest.txt"
        path.write_text(path.read_text() + "optional: included\n", encoding="utf-8")
        found = check_invariants.check_bun1(self.root)
        self.assertEqual(len(found), 1, found)
        self.assertIn("df:viz", found[0])

    def test_planted_changed_lock_is_a_finding_naming_the_real_platform(self):
        self._manifest(hashlib.sha256(self.lock.read_bytes()).hexdigest())
        self.lock.write_text(LOCK + "pyyaml==6.0.3\n", encoding="utf-8")
        found = check_invariants.check_bun1(self.root)
        self.assertEqual(len(found), 1, found)
        self.assertIn("df:replay", found[0])
        self.assertIn("--platform ubuntu_gcc", found[0])
        self.assertNotIn("<p>", found[0])


class Bun1StagedPinTests(unittest.TestCase):
    """A bundle carrying two adas-build-tools versions covers components on
    either one (pins move per component, WP-8); a pin it lacks still fails."""

    def test_two_versions_cover_two_pins_and_a_third_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for comp, pin in (("df", "1.0.26"), ("vdy", "1.0.24")):
                f = root / "modules" / comp / "conf" / "build_tools.version"
                f.parent.mkdir(parents=True)
                f.write_text(pin, encoding="utf-8")
            manifest = root / "misc" / "offline_bundle" / "vs2026" / "bundle_manifest.txt"
            manifest.parent.mkdir(parents=True)
            manifest.write_text("platform: vs2026\npin: adas-build-tools/1.0.24\n"
                                "pin: adas-build-tools/1.0.26\n", encoding="utf-8")
            self.assertEqual(check_invariants.check_bun1(root), [])
            (root / "modules" / "vdy" / "conf" / "build_tools.version").write_text("1.0.25")
            found = check_invariants.check_bun1(root)
            self.assertEqual(len(found), 1, found)
            self.assertIn("vdy pins '1.0.25'", found[0])


class PerPlatformBundleTests(unittest.TestCase):
    """PT-17/18/24 (D14/D15)."""

    def _fake_make(self, out, platform):
        """make_bundle() with every conan/pip/git call faked."""
        def fake_run(cmd, **kwargs):
            if "download" in cmd:
                dest = Path(cmd[cmd.index("-d") + 1])
                dest.mkdir(parents=True, exist_ok=True)
                (dest / "pyyaml-6.0.3-py3-none-any.whl").write_text("", encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "abc\n", "")

        def fake_conan(*args, **kwargs):
            if args[:2] == ("cache", "save"):
                Path(args[3].split("=", 1)[1]).write_text("tgz", encoding="utf-8")
            return subprocess.CompletedProcess(args, 0, "Conan version 2\n", "")
        pins = {"third_party": [], "third_party_tool": [], "toolchain": [], "build_tools": []}
        with mock.patch.object(mob, "derive_pins", return_value=pins), \
             mock.patch.object(mob, "_profile_settings", return_value={}), \
             mock.patch.object(mob, "_transitive_refs", return_value=[]), \
             mock.patch.object(mob, "_conan", side_effect=fake_conan), \
             mock.patch.object(mob, "derive_tool_envs", return_value=[]), \
             mock.patch.object(mob.subprocess, "run", side_effect=fake_run):
            mob.make_bundle(platform, out)

    def test_making_one_platform_leaves_the_other_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            planted = out / "vs2026" / "wheels" / "cp312" / "x.whl"
            planted.parent.mkdir(parents=True)
            planted.write_bytes(b"windows wheel")
            (out / "vs2026" / "bundle_manifest.txt").write_text("platform: vs2026\n")
            before = {p: p.read_bytes() for p in (out / "vs2026").rglob("*") if p.is_file()}
            self._fake_make(out, "ubuntu_gcc")
            after = {p: p.read_bytes() for p in (out / "vs2026").rglob("*") if p.is_file()}
            self.assertEqual(before, after)
            self.assertTrue((out / "ubuntu_gcc" / "bundle_manifest.txt").is_file())
            self.assertEqual(len(list((out / "ubuntu_gcc").glob("adas_offline_*.tgz"))), 1)

    def test_rerun_cleans_its_own_subfolder(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            stale = out / "vs2026" / "adas_offline_vs2026_2020-01-01.tgz"
            stale.parent.mkdir(parents=True)
            stale.write_text("old")
            self._fake_make(out, "vs2026")
            self.assertFalse(stale.exists())
            self.assertEqual(len(list((out / "vs2026").glob("adas_offline_*.tgz"))), 1)

    def test_wrong_host_is_refused_before_any_conan_or_pip_call(self):
        other = "ubuntu_gcc" if sys.platform == "win32" else "vs2026"
        out = io.StringIO()
        with mock.patch.object(mob, "_conan") as conan, \
             mock.patch.object(mob.subprocess, "run") as run, \
             mock.patch.object(mob, "derive_pins") as pins, \
             contextlib.redirect_stdout(out):
            rc = mob.main(["--platform", other])
        self.assertEqual(rc, 1)
        conan.assert_not_called()
        run.assert_not_called()
        pins.assert_not_called()
        text = out.getvalue()
        self.assertIn("Reason:", text)
        self.assertNotIn("<", text)

    def test_wrong_host_commands_are_platform_correct(self):
        win = mob.bundle_command("ubuntu_gcc", host="win32")
        self.assertTrue(win.startswith('wsl --cd "'), win)
        self.assertIn('-e bash -lc "python3 scripts/make_offline_bundle.py --platform ubuntu_gcc"', win)
        with mock.patch.object(mob, "_is_wsl", return_value=True):
            wsl = mob.bundle_command("vs2026", host="linux")
        for bad in ("setup.bat", "cd /d", "Scripts\\"):
            self.assertNotIn(bad, wsl)
        self.assertIn("py.exe -3 scripts/make_offline_bundle.py --platform vs2026", wsl)
        with mock.patch.object(mob, "_is_wsl", return_value=False):
            self.assertIsNone(mob.bundle_command("vs2026", host="linux"))

    def test_include_optional_marks_the_manifest(self):
        text = mob.manifest_text("vs2026", "d", "c", "v", [], {
            "third_party": [], "third_party_tool": [], "toolchain": [], "build_tools": []},
            [], optional_included=True)
        self.assertIn("optional: included", text)
        self.assertTrue(mob.parse_manifest(text)["optional_included"])

    def test_include_optional_today_changes_nothing_in_the_real_repo(self):
        # Every declared env is default now (python_tool_envs_plan.md);
        # --include-optional is a kept escape hatch for a future non-default
        # box, not a selector that currently does anything.
        self.assertEqual({e["label"] for e in mob.derive_tool_envs(include_optional=True)},
                         {e["label"] for e in mob.derive_tool_envs()})


class RootFlatLayoutTests(unittest.TestCase):
    """PT-17: the root setup refuses a flat pre-D14 bundle (Reason / Fix /
    Run), and uses the host subfolder of a D14 one."""

    def test_flat_bundle_is_refused_with_the_move_command(self):
        import setup
        with tempfile.TemporaryDirectory() as tmp:
            top = Path(tmp) / "offline_bundle"
            top.mkdir()
            (top / "bundle_manifest.txt").write_text("platform: vs2026\n", encoding="utf-8")
            (top / "adas_offline_vs2026_2026-09-28.tgz").write_text("x", encoding="utf-8")
            with self.assertRaises(setup.StepFailed) as ctx:
                setup.host_bundle_dir(top)
            self.assertIn("old flat layout", ctx.exception.reason)
            self.assertIn("vs2026", ctx.exception.run)
            self.assertNotIn("<", ctx.exception.run)

    def test_subfolder_layout_resolves_to_this_hosts_platform(self):
        import setup
        with tempfile.TemporaryDirectory() as tmp:
            top = Path(tmp) / "offline_bundle"
            sub = top / setup.offline_platform()
            sub.mkdir(parents=True)
            (top / "some_other_platform").mkdir()
            self.assertEqual(setup.host_bundle_dir(top), sub)


class Hpm1Tests(unittest.TestCase):
    """HPM-1: the stub's copy of HOST_BUNDLE_PLATFORM equals the canonical."""

    def _tree(self, tmp, canon, stub):
        root = Path(tmp)
        a = root / "modules" / "toolchain" / "adas_build_tools" / "bundle_layout.py"
        b = root / "modules" / "toolchain" / "copy_files" / "scripts" / "build.py"
        for path, text in ((a, canon), (b, stub)):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return root

    def test_real_checkout_agrees(self):
        self.assertEqual(check_invariants.check_hpm1(), [])

    def test_planted_divergence_is_a_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            same = 'HOST_BUNDLE_PLATFORM = {"win32": "vs2026", "linux": "ubuntu_gcc"}\n'
            self.assertEqual(check_invariants.check_hpm1(self._tree(tmp, same, same)), [])
        with tempfile.TemporaryDirectory() as tmp:
            other = 'HOST_BUNDLE_PLATFORM = {"win32": "vs2026", "linux": "ubuntu_clang"}\n'
            found = check_invariants.check_hpm1(self._tree(tmp, same, other))
            self.assertEqual(len(found), 1)
            self.assertIn("HPM-1", found[0])


class Pt27MachineryTransferTests(unittest.TestCase):
    """PT-27 (D14/D16): in WSL, a machinery pin missing from the local cache is
    refused before any `conan download`, with a Windows save line and a WSL
    restore line carrying the real revision. Windows keeps today's path."""
    PINS = {"third_party": [], "third_party_tool": [],
            "toolchain": ["adas-toolchain/1.0.5"], "build_tools": ["adas-build-tools/1.0.29"]}
    REVS = {"adas-toolchain/1.0.5": "9baa9626f21efa26eefe39484d098584",
            "adas-build-tools/1.0.29": "a95e165d44239422548de405289c92bf"}

    def _refusal(self, have=False, revs=None, host="linux"):
        with mock.patch.object(mob, "_have_in_cache",
                               side_effect=lambda ref, pk: have or ref.startswith("adas-toolchain")), \
             mock.patch.object(mob, "_windows_revisions", return_value=self.REVS if revs is None else revs), \
             mock.patch.object(mob, "_windows_path", return_value="C:\\adas\\1v-superproject"):
            return mob.machinery_transfer_refusal(self.PINS, host=host)

    def test_missing_pin_in_wsl_is_refused_with_both_host_commands(self):
        lines = self._refusal()
        text = "\n".join(lines)
        self.assertIn("adas-build-tools/1.0.29", lines[0])
        win = [l for l in lines if l.startswith("Run (Windows): ")]
        wsl = [l for l in lines if l.startswith("Run (WSL):     ")]
        self.assertEqual((len(win), len(wsl)), (1, 1), text)
        self.assertIn('conan cache save "adas-build-tools/1.0.29#a95e165d44239422548de405289c92bf:*"', win[0])
        self.assertIn('cd /d "C:\\adas\\1v-superproject"', win[0])
        self.assertIn("conan cache restore misc/offline_bundle/transfer/adas-build-tools-1.0.29.tgz", wsl[0])
        self.assertNotIn("cd /d", wsl[0])
        self.assertNotIn("adas-toolchain", text, "only what is missing")
        self.assertNotIn("<", text)

    def test_main_refuses_before_any_download(self):
        with mock.patch.object(mob, "wrong_host_refusal", return_value=None), \
             mock.patch.object(mob, "derive_pins", return_value=self.PINS), \
             mock.patch.object(mob, "machinery_transfer_refusal", return_value=["Reason: x"]) as ref, \
             mock.patch.object(mob, "make_bundle") as make, \
             mock.patch.object(mob, "_ensure_in_cache") as ensure, \
             contextlib.redirect_stdout(io.StringIO()):
            rc = mob.main(["--platform", "ubuntu_gcc"])
        self.assertEqual(rc, 1)
        ref.assert_called_once()
        make.assert_not_called()
        ensure.assert_not_called()

    def test_no_download_call_while_checking(self):
        calls = []
        with mock.patch.object(mob, "_conan", side_effect=lambda *a, **k: calls.append(a) or
                               subprocess.CompletedProcess(a, 0, "{}", "")), \
             mock.patch.object(mob, "_windows_revisions", return_value=self.REVS), \
             mock.patch.object(mob, "_windows_path", return_value="C:\\x"):
            mob.machinery_transfer_refusal(self.PINS, host="linux")
        self.assertTrue(calls)
        self.assertFalse([c for c in calls if "download" in c], calls)

    def test_windows_keeps_todays_behaviour(self):
        self.assertIsNone(self._refusal(host="win32"))

    def test_nothing_missing_is_no_refusal(self):
        self.assertIsNone(self._refusal(have=True))

    def test_planted_unknown_revision_prints_no_run(self):
        lines = self._refusal(revs={})
        self.assertFalse([l for l in lines if l.startswith("Run")], lines)
        self.assertIn("make the vs2026 bundle on Windows first", lines[1])

    def test_missing_ref_error_listing_is_not_cached(self):
        """The bug PT-27's planting found: a missing ref's listing is an error."""
        with mock.patch.object(mob, "_list_json",
                               return_value={"adas-build-tools/1.0.29": {"error": "not found"}}):
            self.assertFalse(mob._have_in_cache("adas-build-tools/1.0.29", True))
        with mock.patch.object(mob, "_list_json", return_value={"error": "not found"}):
            self.assertFalse(mob._have_in_cache("adas-build-tools/1.0.29", True))


if __name__ == "__main__":
    unittest.main()
