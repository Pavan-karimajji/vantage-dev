"""scripts/tests/test_bundle_guide.py

The guided bundle maker (scripts/bundle_guide.py, reached by running
make_offline_bundle.py with no options). Every path a user can take is driven
with scripted answers: happy path, decline, a failed prerequisite, a failed
bundle, a wrong answer. Pure unittest; no conan, no pip, no network.

Run:
    python -m unittest discover -s scripts/tests   (from the superproject root)
"""
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bundle_guide as bg  # noqa: E402
import make_offline_bundle as mob  # noqa: E402

# vantage-dev: these tests assert 1v-superproject's own module set (they need df).
_DF_DECLARED = "modules/df" in ((Path(__file__).resolve().parents[2] / ".gitmodules")
                                .read_text(encoding="utf-8"))
_DF_REASON = "asserts 1v-superproject's own module set (df, CARLA, viz); not this superproject's"

HOST = mob._bundle_layout().host_bundle_platform()


def _ok_checks(*_a, **_k):
    return [bg.Check("everything", True, "fine")]


def _drive(answers, **kw):
    """Run the guide with scripted answers; return (exit code, printed text, run calls)."""
    answers = list(answers)
    calls = []
    printed = []

    def run_fn(*args):
        calls.append(args)
        return run_code

    run_code = kw.pop("run_code", 0)
    code = bg.guide(input_fn=lambda _p: answers.pop(0), print_fn=printed.append,
                    run_fn=run_fn, out_dir=kw.pop("out_dir", tempfile.gettempdir()),
                    preflight_fn=kw.pop("preflight_fn", _ok_checks), host_platform=HOST, **kw)
    return code, "\n".join(map(str, printed)), calls


class TheBoxListIsDerived(unittest.TestCase):

    @unittest.skipUnless(_DF_DECLARED, _DF_REASON)
    def test_box_list_matches_derive_tool_envs(self):
        boxes = bg.box_list()
        self.assertEqual([b[0] for b in boxes], [e["label"] for e in mob.derive_tool_envs()])
        self.assertIn("df:carla", [b[0] for b in boxes])

    @unittest.skipUnless(_DF_DECLARED, _DF_REASON)
    def test_an_external_is_named_so_the_user_knows_carla_must_be_installed(self):
        notes = dict(bg.box_list())
        self.assertIn("carla installed", notes["df:carla"])

    def test_command_dry_runs_to_the_same_boxes_the_list_shows(self):
        boxes = bg.box_list()
        argv = bg.command_for(HOST).split()[2:]  # drop "python scripts/make_offline_bundle.py"
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(mob.main(argv + ["--dry-run"]), 0)
        line = next(l for l in out.getvalue().splitlines() if l.startswith("python_envs:"))
        self.assertEqual(line.split(":", 1)[1].strip(), ", ".join(b[0] for b in boxes))


class TheGuide(unittest.TestCase):

    def test_happy_path_runs_the_bundle_once_after_a_yes(self):
        code, text, calls = _drive(["", "y"])
        self.assertEqual(code, 0)
        self.assertEqual(len(calls), 1)
        platform, _out = calls[0]
        self.assertEqual(platform, HOST)
        self.assertIn(f"--platform {HOST}", text)
        self.assertIn(bg.unpack_command(HOST), text)

    def test_the_next_step_uses_the_unpacking_pcs_own_command_and_folder(self):
        self.assertEqual(bg.unpack_command("vs2026"),
                         "setup.bat --offline <where you put it>\\vs2026")
        self.assertEqual(bg.unpack_command("ubuntu_gcc"),
                         "python3 scripts/setup.py --offline <where you put it>/ubuntu_gcc")

    def test_setup_accepts_the_folder_the_guide_points_to(self):
        """Fool-proofing the hand-off: build a minimal bundle in exactly the folder the guide
        names, and check setup's own loader takes it."""
        import setup
        with tempfile.TemporaryDirectory() as tmp:
            folder = bg.bundle_folder(tmp, HOST)
            (folder / "wheels").mkdir(parents=True)
            (folder / f"adas_offline_{HOST}_2026-10-04.tgz").write_bytes(b"x")
            (folder / "bundle_manifest.txt").write_text(
                mob.manifest_text(HOST, "2026-10-04", "abc", "Conan version 2.20.1", [],
                                  {"third_party": [], "third_party_tool": [], "toolchain": [], "build_tools": []}, []),
                encoding="utf-8")
            manifest, archive, wheels = setup.load_offline_bundle(folder)
            self.assertEqual(archive.parent, folder)
            self.assertEqual(manifest["platform"], HOST)

    def test_declining_runs_nothing(self):
        code, text, calls = _drive(["", "n"])
        self.assertEqual((code, calls), (0, []))
        self.assertIn("Nothing was run.", text)

    def test_enter_at_the_confirm_means_no(self):
        code, _text, calls = _drive(["", ""])
        self.assertEqual((code, calls), (0, []))

    def test_a_wrong_answer_is_asked_again(self):
        code, text, calls = _drive(["9", "", "x", "y"])
        self.assertEqual(code, 0)
        self.assertEqual(len(calls), 1)
        self.assertIn("please type one of", text)

    def test_a_failed_prerequisite_stops_before_running_and_shows_the_fix(self):
        bad = lambda *_a, **_k: [bg.Check("Conan 2", False, "not found", ["python -m pip install conan"])]
        code, text, calls = _drive([""], preflight_fn=bad)
        self.assertEqual((code, calls), (1, []))
        self.assertIn("fix: python -m pip install conan", text)
        self.assertIn(f"--platform {HOST}", text)

    def test_a_failed_bundle_says_to_rerun_the_exact_command(self):
        code, text, calls = _drive(["", "y"], run_code=1)
        self.assertEqual(code, 1)
        self.assertEqual(len(calls), 1)
        self.assertIn("run exactly this again", text)

    def test_an_existing_bundle_is_announced_before_it_is_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / HOST
            folder.mkdir(parents=True)
            (folder / "adas_offline_x_2026-10-01.tgz").write_bytes(b"0" * 2048)
            _code, text, _calls = _drive(["", "n"], out_dir=tmp)
        self.assertIn("2026-10-01", text)
        self.assertIn("REPLACED", text)


class TheChecks(unittest.TestCase):

    def _proc(self, rc, out=""):
        return lambda *a, **k: subprocess.CompletedProcess(a[0], rc, out, "")

    def test_conan_missing_gives_the_install_command(self):
        c = bg.check_conan(self._proc(127))
        self.assertFalse(c.ok)
        self.assertIn('pip install "conan>=2,<3"', c.fix[0])

    def test_conan_1_is_refused(self):
        self.assertFalse(bg.check_conan(self._proc(0, "Conan version 1.66.0")).ok)

    def test_conan_2_passes(self):
        self.assertTrue(bg.check_conan(self._proc(0, "Conan version 2.20.1")).ok)

    def test_pip_missing_gives_ensurepip(self):
        c = bg.check_pip(self._proc(1))
        self.assertFalse(c.ok)
        self.assertIn("ensurepip", c.fix[0])

    def test_no_internet_names_the_proxy_fix(self):
        def boom(*_a, **_k):
            raise OSError("no route")
        c = bg.check_internet(boom)
        self.assertFalse(c.ok)
        self.assertTrue(any("HTTPS_PROXY" in f for f in c.fix))

    def test_low_disk_is_refused(self):
        usage = lambda _p: mock.Mock(free=10 * 1024 ** 2)
        self.assertFalse(bg.check_disk(tempfile.gettempdir(), usage).ok)

    def test_wrong_host_gives_the_command_for_the_right_one(self):
        other = "ubuntu_gcc" if HOST == "vs2026" else "vs2026"
        c = bg.check_host(other)
        self.assertFalse(c.ok)
        self.assertTrue(c.fix and "make_offline_bundle.py" in " ".join(c.fix) or "Windows" in " ".join(c.fix))

    def test_wrong_host_stops_before_any_conan_call(self):
        other = "ubuntu_gcc" if HOST == "vs2026" else "vs2026"
        seen = []

        def runner(cmd, **_k):
            seen.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, "pip 25.0", "")
        checks = bg.preflight(other, tempfile.gettempdir(), runner=runner,
                              opener=lambda *a, **k: None, usage=lambda _p: mock.Mock(free=10 ** 12))
        self.assertFalse(checks[-1].ok)
        self.assertFalse(any(cmd[0] == "conan" for cmd in seen))

    def test_missing_toolchain_checkout_gives_the_submodule_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = bg.check_toolchain_checkout(tmp)
        self.assertFalse(c.ok)
        self.assertIn("git submodule update --init modules/toolchain", c.fix[0])


class TheEntryPoint(unittest.TestCase):

    def test_no_options_without_a_terminal_explains_instead_of_erroring(self):
        out = io.StringIO()
        with mock.patch.object(bg, "is_interactive", return_value=False), contextlib.redirect_stdout(out):
            code = mob.main([])
        self.assertEqual(code, 2)
        self.assertIn("What is an offline bundle?", out.getvalue())
        self.assertIn("make_offline_bundle.py", out.getvalue())

    def test_no_platform_uses_this_pcs_and_says_so(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(mob.main(["--dry-run"]), 0)
        self.assertIn(f"using {HOST} (this PC's platform)", out.getvalue())

    def test_ci_environment_is_never_interactive(self):
        tty = mock.Mock(isatty=lambda: True)
        with mock.patch.dict(os.environ, {"CI": "1"}):
            self.assertFalse(bg.is_interactive(tty))

    def test_a_bundle_refusal_becomes_exit_1_with_its_message(self):
        out = io.StringIO()
        with mock.patch.object(mob, "make_bundle", side_effect=SystemExit("ERROR: foo is not in the cache")), \
                contextlib.redirect_stdout(out):
            self.assertEqual(bg._run_bundle(HOST, Path(tempfile.gettempdir())), 1)
        self.assertIn("foo is not in the cache", out.getvalue())

    def test_a_failed_tool_call_becomes_reason_fix_run(self):
        out = io.StringIO()
        err = subprocess.CalledProcessError(1, ["conan", "install"])
        with mock.patch.object(mob, "make_bundle", side_effect=err), contextlib.redirect_stdout(out):
            self.assertEqual(bg._run_bundle(HOST, Path(tempfile.gettempdir())), 1)
        self.assertIn("Reason:", out.getvalue())
        self.assertIn("Run:", out.getvalue())


if __name__ == "__main__":
    unittest.main()
