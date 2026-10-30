"""
scripts/tests/test_python_baseline.py

PT-30..PT-33 (python_tool_envs_plan.md D18/D19): planted violations
(R-REQ-9) for PYV-1 and PYB-1, the baseline generator's conflict refusal
and determinism, and toolchain:docs checked against toolchain's own
source baseline. Temp trees only; pip and the Conan cache are faked.

Run:
    py -m unittest discover -s scripts/tests
    (from the superproject root)
"""

import datetime
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import check_invariants  # noqa: E402
import make_python_baseline  # noqa: E402
import python_baseline  # noqa: E402

REAL_TC = check_invariants.ROOT / "modules" / "toolchain" / "adas_build_tools"

ENV_YML = """\
python_envs:
  {env}:
    python: "{python}"
    intent: {intent}
    lock: {lock}
    default: true
{extra}"""


class Tree(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="baseline_")
        self.root = Path(self._tmp)
        pkg = self.root / "modules" / "toolchain" / "adas_build_tools"
        pkg.mkdir(parents=True)
        for f in ("__init__.py", "config.py", "bundle_layout.py"):
            shutil.copy(REAL_TC / f, pkg / f)
        (self.root / "modules" / "toolchain" / "pyproject.toml").write_text(
            '[project]\nname = "adas-build-tools"\nversion = "1.0.30"\n', encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def comp(self, name, env="tool", python="3.12", intent="req.txt", lock="req.lock",
             lock_lines=("numpy==2.5.3",), intent_text="numpy\n", exception=None):
        d = self.root / "modules" / name
        (d / "conf").mkdir(parents=True, exist_ok=True)
        (d / "conanfile.py").write_text("", encoding="utf-8")
        extra = f'    exception: "{exception}"\n' if exception is not None else ""
        (d / "conf" / "build.yml").write_text(ENV_YML.format(
            env=env, python=python, intent=intent, lock=lock, extra=extra), encoding="utf-8")
        (d / intent).write_text(intent_text, encoding="utf-8")
        (d / lock).write_text("# LOCK\n" + "".join(f"{l}\n" for l in lock_lines),
                              encoding="utf-8")
        return d


class PyvTests(Tree):

    def test_platform_python_is_clean(self):
        self.comp("df")
        self.assertEqual(check_invariants.check_pyv1(self.root), [])

    def test_other_python_without_exception_is_a_finding(self):
        self.comp("df", python="3.13")
        (finding,) = check_invariants.check_pyv1(self.root)  # one per env
        self.assertIn("df:tool", finding)
        self.assertIn('"3.13"', finding)
        self.assertIn("3.12 on vs2026", finding)

    def test_other_python_as_exception_is_allowed(self):
        self.comp("df", python="3.13", exception="CARLA wheel is cp313 only")
        self.assertEqual(check_invariants.check_pyv1(self.root), [])


class PybTests(Tree):

    BASE = {"numpy": ("numpy", "2.5.3"), "protobuf": ("protobuf", "7.36.2")}

    def _check(self):
        return check_invariants.check_pyb1(
            self.root, baseline_for=lambda root, comp: (self.BASE, "adas-build-tools/1.0.30"))

    def test_lock_equal_to_baseline_is_clean(self):
        self.comp("df")
        self.assertEqual(self._check(), [])

    def test_different_version_is_a_finding_naming_both(self):
        self.comp("df", lock_lines=("numpy==2.4.0",))
        (finding,) = self._check()
        for part in ("df:tool", "numpy==2.4.0", "numpy==2.5.3", "adas-build-tools/1.0.30"):
            self.assertIn(part, finding)

    def test_package_not_in_baseline_is_a_finding(self):
        self.comp("df", lock_lines=("numpy==2.5.3", "rich==14.0.0"))
        (finding,) = self._check()
        self.assertIn("rich==14.0.0", finding)
        self.assertIn("not in the baseline", finding)

    def test_exception_env_is_not_checked(self):
        self.comp("df", lock_lines=("numpy==1.26.4",), exception="CARLA needs numpy 1.x")
        self.assertEqual(self._check(), [])

    def test_pin_without_baseline_is_a_finding_with_run(self):
        self.comp("df")

        def missing(root, comp):
            raise python_baseline.BaselineMissing(
                "adas-build-tools/1.0.29 (pinned by df) ships no python_baseline.txt",
                "move df's pin to 1.0.30.",
                python_baseline.pin_move_command(root, comp, "1.0.30"))
        (finding,) = check_invariants.check_pyb1(self.root, baseline_for=missing)
        self.assertIn("ships no python_baseline.txt", finding)
        self.assertIn("build_tools.version", finding)
        self.assertIn("1.0.30", finding)

    def test_conan_not_on_path_is_a_finding_not_a_crash(self):
        # A fresh WSL has no conan until setup runs there.
        def no_conan(*args, **kwargs):
            raise FileNotFoundError(2, "No such file or directory", "conan")
        with unittest.mock.patch.object(python_baseline.subprocess, "run", side_effect=no_conan):
            with self.assertRaises(python_baseline.BaselineMissing) as ctx:
                python_baseline._wheel_in_cache("adas-build-tools/1.0.30")
        self.assertIn("conan is not on PATH", ctx.exception.reason)
        self.assertIn("setup", ctx.exception.run)

    def test_toolchain_docs_uses_toolchain_source_baseline(self):
        self.comp("toolchain", env="docs", lock_lines=("numpy==2.4.0",))
        src = self.root / python_baseline.SOURCE_BASELINE
        src.write_text("# BASELINE\nnumpy==2.5.3\n", encoding="utf-8")
        baseline, where = python_baseline.baseline_for(self.root, "toolchain")
        self.assertEqual(where, python_baseline.SOURCE_BASELINE.as_posix())
        (finding,) = check_invariants.check_pyb1(self.root)  # real resolver, no Conan call
        self.assertIn("toolchain:docs", finding)
        self.assertIn("numpy==2.5.3", finding)
        src.write_text("# BASELINE\nnumpy==2.4.0\n", encoding="utf-8")
        self.assertEqual(check_invariants.check_pyb1(self.root), [])


class TagPinTests(Tree):
    def test_git_tag_pin_is_refused_naming_the_bare_version_not_a_cache_miss(self):
        d = self.comp("df")
        (d / "conf" / "build_tools.version").write_text("v1.0.38\n", encoding="utf-8")
        with self.assertRaises(python_baseline.BaselineMissing) as ctx:
            python_baseline.baseline_for(self.root, "df")
        self.assertIn("git tag", ctx.exception.reason)
        self.assertNotIn("Conan cache", ctx.exception.reason)
        self.assertIn("1.0.38", ctx.exception.run)
        self.assertNotIn("v1.0.38", ctx.exception.run)


class FakePip:
    """Resolves unless the intent files of both `clash` envs are present."""

    def __init__(self, clash=None, freeze=""):
        self.clash, self.freeze, self.calls = clash or (), freeze, []

    def __call__(self, args):
        self.calls.append(args)
        if args[0] == "freeze":
            return subprocess.CompletedProcess(args, 0, self.freeze, "")
        joined = " ".join(args)
        if self.clash and all(c in joined for c in self.clash):
            return subprocess.CompletedProcess(
                args, 1, "",
                "ERROR: Cannot install -r a (line 1) and -r b (line 1) because these package "
                "versions have conflicting dependencies.\nThe conflict is caused by:\n"
                "    The user requested numpy==2.4.0\n    The user requested numpy==2.5.3\n"
                "ERROR: ResolutionImpossible")
        return subprocess.CompletedProcess(args, 0, "", "")


class GeneratorTests(Tree):

    def _gen(self, pip):
        return make_python_baseline.generate(self.root, pip_factory=lambda tmp, py: pip,
                                             today=datetime.date(2026, 9, 28), commit="abc1234")

    def test_incompatible_intents_stop_naming_both_envs_and_package(self):
        a = self.comp("df", intent="ra.txt", intent_text="numpy==2.4.0\n")
        self.comp("sim", intent="rb.txt", intent_text="numpy==2.5.3\n")
        self.comp("viz", intent="rc.txt", intent_text="pyyaml\n")
        pip = FakePip(clash=(str(a / "ra.txt"), "rb.txt"))
        with self.assertRaises(make_python_baseline.Refusal) as ctx:
            self._gen(pip)
        exc = ctx.exception
        self.assertIn("df:tool and sim:tool", exc.reason)
        self.assertIn("numpy", exc.reason)
        self.assertIn("modules/sim/conf/build.yml", exc.fix)
        self.assertNotIn("<", exc.run)
        self.assertFalse((self.root / python_baseline.SOURCE_BASELINE).exists(),
                         "a failed generation must write nothing")
        self.assertFalse(any(c[0] == "freeze" for c in pip.calls))

    def test_exception_env_is_left_out_of_the_resolve(self):
        self.comp("df", intent="ra.txt")
        self.comp("sim", intent="rb.txt", exception="needs numpy 1.x")
        pip = FakePip(freeze="numpy==2.5.3\n")
        self._gen(pip)
        install = next(c for c in pip.calls if c[0] == "install")
        self.assertTrue(any(a.endswith("ra.txt") for a in install))
        self.assertFalse(any(a.endswith("rb.txt") for a in install))

    def test_same_inputs_give_identical_bytes_minus_date(self):
        self.comp("df", intent="pyproject.toml", intent_text='[project]\nname = "adas-df"\n')
        freeze = "zstandard==0.25.0\npip==25.2\nnumpy==2.5.3\nadas-df==0.1\nPyYAML==6.0.3\n"
        out, count = self._gen(FakePip(freeze=freeze))
        first = out.read_bytes()
        make_python_baseline.generate(self.root, pip_factory=lambda t, p: FakePip(freeze=freeze),
                                      today=datetime.date(2027, 1, 1), commit="abc1234")
        second = out.read_bytes()
        strip = lambda b: [l for l in b.splitlines() if not l.startswith(b"# date:")]  # noqa: E731
        self.assertEqual(strip(first), strip(second))
        self.assertNotEqual(first, second)  # only the date line differs
        body = [l for l in first.decode().splitlines() if not l.startswith("#")]
        self.assertEqual(body, ["numpy==2.5.3", "PyYAML==6.0.3", "zstandard==0.25.0"])
        self.assertEqual(count, 3)


if __name__ == "__main__":
    unittest.main()
