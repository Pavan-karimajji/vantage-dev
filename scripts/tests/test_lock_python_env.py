"""
scripts/tests/test_lock_python_env.py

Unit tests for scripts/lock_python_env.py (PT-03, python_tool_envs_plan.md
D2/D4/D11). subprocess is mocked: what is proven here is the lock's shape
(exact `==` lines only, sorted, pip/setuptools/wheel and the pyproject's own
project excluded, header naming source and date) and that every refusal is
Reason / Fix / Run with a runnable command. The real network run is the
PT-04 locks themselves, re-checked by PYE-1.

Run:
    py -m unittest discover -s scripts/tests
    (from the superproject root)
"""

import contextlib
import datetime
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
import lock_python_env  # noqa: E402 - path must be set up first

BUILD_YML = """\
python_envs:
  replay:
    python: "3.12"
    intent: tools/requirements.txt
    lock: tools/requirements.lock
    default: true
  sim:
    python: "3.12"
    intent: pyproject.toml
    lock: requirements.lock
    default: true
    package: .
"""


def _fake_run(freeze_out, pip_rc=0, interp_ok=True, installs=None, venv_rc=0):
    def run(cmd, **kwargs):
        text = " ".join(map(str, cmd))
        if "import sys, venv" in text:
            if not interp_ok:
                raise FileNotFoundError(cmd[0])
            return subprocess.CompletedProcess(cmd, 0, "3.12.0", "")
        if "tomllib" in text:
            return subprocess.CompletedProcess(cmd, 0, "adas-sim\n", "")
        if "pip freeze" in text or ("freeze" in cmd):
            return subprocess.CompletedProcess(cmd, 0, freeze_out, "")
        if "install" in cmd:
            if installs is not None:
                cfile = cmd[cmd.index("-c") + 1] if "-c" in cmd else None
                installs.append((list(cmd), Path(cfile).read_text(encoding="utf-8")
                                 if cfile else None))
            return subprocess.CompletedProcess(cmd, pip_rc, "", "")
        if "venv" in cmd:  # venv creation
            if venv_rc and kwargs.get("check"):
                raise subprocess.CalledProcessError(venv_rc, cmd)
            return subprocess.CompletedProcess(cmd, venv_rc, "", "ensurepip is not available")
        return subprocess.CompletedProcess(cmd, 0, "", "")
    return run


class LockTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="lock_env_")
        self.root = Path(self._tmp)
        real_tc = lock_python_env.ROOT / "modules" / "toolchain" / "adas_build_tools"
        pkg = self.root / "modules" / "toolchain" / "adas_build_tools"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        shutil.copy(real_tc / "config.py", pkg / "config.py")
        comp = self.root / "modules" / "df"
        (comp / "conf").mkdir(parents=True)
        (comp / "conf" / "build.yml").write_text(BUILD_YML, encoding="utf-8")
        (comp / "tools").mkdir()
        (comp / "tools" / "requirements.txt").write_text("mcap>=1.0\n", encoding="utf-8")
        (comp / "pyproject.toml").write_text("[project]\nname='adas-sim'\n", encoding="utf-8")
        self.comp = comp
        self._patch = mock.patch.object(lock_python_env, "ROOT", self.root)
        self._patch.start()
        # D19: the component's baseline (the pinned wheel's, in real use).
        self.baseline = {"mcap": ("mcap", "1.5.0"), "pyyaml": ("PyYAML", "6.0.3")}
        self._bpatch = mock.patch.object(
            lock_python_env.python_baseline, "baseline_for",
            side_effect=lambda root, comp: (self.baseline, "adas-build-tools/1.0.30 (test)"))
        self.baseline_for = self._bpatch.start()

    def tearDown(self):
        self._bpatch.stop()
        self._patch.stop()
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _main(self, *argv, **fake):
        out = io.StringIO()
        with mock.patch.object(lock_python_env.subprocess, "run", _fake_run(**fake)), \
                contextlib.redirect_stdout(out):
            rc = lock_python_env.main(list(argv))
        return rc, out.getvalue()

    def assert_refusal(self, out):
        lines = out.strip().splitlines()
        self.assertTrue(lines[-3].startswith("Reason: "), out)
        self.assertTrue(lines[-2].startswith("Fix:    "), out)
        self.assertTrue(lines[-1].startswith("Run:    "), out)
        self.assertNotIn("<", lines[-1], "Run: must carry no placeholder")

    def test_lock_is_exact_sorted_and_filtered(self):
        freeze = "zstandard==0.25.0\npip==25.2\nPyYAML==6.0.3\nsetuptools==80.0\nwheel==0.45\nmcap==1.5.0\n"
        rc, out = self._main("df", "replay", freeze_out=freeze)
        self.assertEqual(rc, 0, out)
        text = (self.comp / "tools" / "requirements.lock").read_text(encoding="utf-8")
        body = [l for l in text.splitlines() if not l.startswith("#")]
        self.assertEqual(body, ["mcap==1.5.0", "PyYAML==6.0.3", "zstandard==0.25.0"])
        self.assertIn("# source: tools/requirements.txt", text)
        self.assertIn(f"# date:   {datetime.date.today().isoformat()}", text)

    def test_lock_is_narrowed_from_the_component_baseline(self):
        # PT-31 (D19): pip installs with the baseline as -c constraints.
        installs = []
        rc, out = self._main("df", "replay", freeze_out="mcap==1.5.0\n", installs=installs)
        self.assertEqual(rc, 0, out)
        self.baseline_for.assert_called_once_with(self.root, "df")
        (cmd, constraints), = installs
        self.assertIn("-c", cmd)
        self.assertEqual(constraints, "PyYAML==6.0.3\nmcap==1.5.0\n")
        text = (self.comp / "tools" / "requirements.lock").read_text(encoding="utf-8")
        self.assertIn("# baseline: adas-build-tools/1.0.30 (test)", text)

    def test_exception_env_resolves_on_its_own(self):
        yml = self.comp / "conf" / "build.yml"
        yml.write_text(yml.read_text(encoding="utf-8").replace(
            "    default: true\n  sim:",
            "    default: true\n    exception: \"needs numpy 1.x\"\n  sim:"), encoding="utf-8")
        installs = []
        rc, out = self._main("df", "replay", freeze_out="mcap==1.5.0\n", installs=installs)
        self.assertEqual(rc, 0, out)
        self.baseline_for.assert_not_called()
        (cmd, constraints), = installs
        self.assertNotIn("-c", cmd)
        text = (self.comp / "tools" / "requirements.lock").read_text(encoding="utf-8")
        self.assertIn("# baseline: none -- exception: needs numpy 1.x", text)

    def test_missing_baseline_is_refused(self):
        self.baseline_for.side_effect = lock_python_env.python_baseline.BaselineMissing(
            "adas-build-tools/1.0.29 ships no python_baseline.txt", "move the pin",
            "py -3 -c \"open('x', 'w').write('1.0.30')\"")
        rc, out = self._main("df", "replay", freeze_out="")
        self.assertEqual(rc, 1)
        self.assert_refusal(out)
        self.assertIn("ships no python_baseline.txt", out)

    def test_pyproject_project_itself_is_excluded(self):
        rc, out = self._main("df", "sim", freeze_out="adas-sim==0.1.0\nmcap==1.5.0\n")
        self.assertEqual(rc, 0, out)
        body = [l for l in (self.comp / "requirements.lock").read_text().splitlines()
                if not l.startswith("#")]
        self.assertEqual(body, ["mcap==1.5.0"])

    def test_url_requirement_is_refused(self):
        rc, out = self._main("df", "replay", freeze_out="foo @ file:///x/foo.whl\n")
        self.assertEqual(rc, 1)
        self.assert_refusal(out)
        self.assertIn("not an exact", out)

    def test_missing_interpreter_is_refused_with_install_command(self):
        rc, out = self._main("df", "replay", freeze_out="", interp_ok=False)
        self.assertEqual(rc, 1)
        self.assert_refusal(out)
        self.assertIn("Python 3.12 is not installed", out)
        self.assertRegex(out, r"Run:    (winget install -e --id Python\.Python\.3\.12|sudo apt install python3\.12)")

    def test_venv_creation_failure_is_refused_not_a_traceback(self):
        rc, out = self._main("df", "replay", freeze_out="", venv_rc=1)
        self.assertEqual(rc, 1)
        self.assert_refusal(out)
        self.assertIn("cannot create a venv", out)
        self.assertIn("ensurepip is not available", out)

    def test_pip_failure_is_refused(self):
        rc, out = self._main("df", "replay", freeze_out="", pip_rc=1)
        self.assertEqual(rc, 1)
        self.assert_refusal(out)
        self.assertIn("lock_python_env.py df replay", out)

    def test_unknown_env_is_refused_naming_declared_ones(self):
        rc, out = self._main("df", "nope", freeze_out="")
        self.assertEqual(rc, 1)
        self.assert_refusal(out)
        self.assertIn("declared: replay, sim", out)

    def test_unknown_module_is_refused(self):
        rc, out = self._main("nomod", "replay", freeze_out="")
        self.assertEqual(rc, 1)
        self.assert_refusal(out)

    def test_wrong_arg_count_is_refused(self):
        rc, out = self._main("df", freeze_out="")
        self.assertEqual(rc, 2)
        self.assert_refusal(out)


if __name__ == "__main__":
    unittest.main()
