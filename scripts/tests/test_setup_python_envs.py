"""
scripts/tests/test_setup_python_envs.py

PT-07 (python_tool_envs_plan.md D8, PR-2): the root setup's "Python tool
environments" step. Planted cases (R-REQ-9): the step sits after cache
preparation in BOTH step lists; a fake component declaring python_envs:
with a launcher is picked up with zero root edits; a launcher-less
component other than toolchain is refused by name and never run from
source; --python-env / --remotes are forwarded.

Run:
    py -m unittest discover -s scripts/tests
    (from the superproject root)
"""

import ast
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import setup  # noqa: E402

REAL_CONFIG = setup.ROOT / "modules" / "toolchain" / "adas_build_tools" / "config.py"
ENVS_YML = """\
variants: {}
python_envs:
  tool:
    python: "3.12"
    intent: r.txt
    lock: r.lock
    default: true
"""
CHILD_OUT = ("adas-build-tools setup - component: x\n--- Python tool environments ---\n"
             "zeta:tool  Python 3.12  lock 1 packages  .venv-tool-win32   already satisfied\n"
             "[OK]   Python tool environments\n")


def _step_names(func_name):
    tree = ast.parse((setup.ROOT / "scripts" / "setup.py").read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == func_name)
    names = []
    for node in ast.walk(fn):
        if (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "step"
                and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant)):
            names.append((node.lineno, node.args[1].value))
    return [n for _, n in sorted(names)]


class StepOrderTests(unittest.TestCase):

    def test_online_list_runs_it_after_cache_preparation(self):
        names = _step_names("main")
        cache = next(i for i, n in enumerate(names) if n.startswith("Cache preparation"))
        self.assertGreater(names.index("Python tool environments"), cache)

    def test_offline_list_runs_it_after_the_bundle_restore(self):
        names = _step_names("offline_setup")
        restore = next(i for i, n in enumerate(names) if n.startswith("Restore the bundle"))
        self.assertGreater(names.index("Python tool environments"), restore)


class RootStepTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="root_envs_")
        self.root = Path(self._tmp)
        pkg = self.root / "modules" / "toolchain" / "adas_build_tools"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        shutil.copy(REAL_CONFIG, pkg / "config.py")
        self.calls = []

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _component(self, name, launcher=True, build_yml=ENVS_YML):
        comp = self.root / "modules" / name
        (comp / "conf").mkdir(parents=True, exist_ok=True)
        (comp / "conf" / "build.yml").write_text(build_yml, encoding="utf-8")
        if launcher:
            (comp / "scripts").mkdir(exist_ok=True)
            (comp / "scripts" / "setup.py").write_text("", encoding="utf-8")
        return comp

    def _run(self, comps, **ctx):
        def fake_run(cmd, **kwargs):
            self.calls.append((cmd, kwargs))
            return subprocess.CompletedProcess(cmd, 0, CHILD_OUT, "")
        context = types.SimpleNamespace(dry_run=False, python_env=[], remotes=None, offline=None)
        context.__dict__.update(ctx)
        with mock.patch.object(setup, "ROOT", self.root), \
             mock.patch.object(setup, "discover_components", return_value=comps), \
             mock.patch.object(setup.subprocess, "run", fake_run):
            return setup.ensure_python_tool_envs(context)

    def test_new_component_with_a_launcher_is_picked_up_with_zero_root_edits(self):
        comp = self._component("zeta")
        self._component("quiet", build_yml="variants: {}\n")
        self._run(["quiet", "zeta"])
        self.assertEqual(len(self.calls), 1, "only the declaring component runs")
        cmd, kwargs = self.calls[0]
        self.assertEqual(cmd[1], str(comp / "scripts" / "setup.py"))
        self.assertIn("--python-envs-only", cmd)
        self.assertEqual(kwargs["cwd"], str(comp))

    def test_launcherless_component_other_than_toolchain_is_refused_by_name(self):
        self._component("rogue", launcher=False)
        with self.assertRaises(setup.StepFailed) as ctx:
            self._run(["rogue"])
        self.assertIn("rogue", ctx.exception.reason)
        self.assertEqual(self.calls, [], "never run from source")

    def test_toolchain_runs_from_source(self):
        self._component("toolchain", launcher=False)
        self._run(["toolchain"])
        cmd, kwargs = self.calls[0]
        self.assertEqual(cmd[1:3], ["-m", "adas_build_tools.setup_cli"])
        self.assertEqual(kwargs["env"]["PYTHONPATH"], str(self.root / "modules" / "toolchain"))

    def test_python_env_and_remotes_are_forwarded(self):
        self._component("zeta")
        self._run(["zeta"], python_env=["zeta:tool", "all"], remotes="on")
        cmd = self.calls[0][0]
        self.assertEqual(cmd[cmd.index("--remotes") + 1], "on")
        self.assertIn("zeta:tool", cmd)
        self.assertIn("all", cmd)

    def test_offline_forces_remotes_off(self):
        self._component("zeta")
        self._run(["zeta"], offline="misc/offline_bundle")
        cmd = self.calls[0][0]
        self.assertEqual(cmd[cmd.index("--remotes") + 1], "off")

    def test_unknown_component_in_python_env_is_refused(self):
        self._component("zeta")
        with self.assertRaises(setup.StepFailed) as ctx:
            self._run(["zeta"], python_env=["nosuch:env"])
        self.assertIn("nosuch:env", ctx.exception.reason)

    def test_a_failing_component_fails_the_step(self):
        self._component("zeta")

        def failing(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 1, CHILD_OUT.replace(
                "already satisfied", "REFUSED\n    Reason: x\n    Fix:    y\n    Run:    z"), "")
        with mock.patch.object(setup, "ROOT", self.root), \
             mock.patch.object(setup, "discover_components", return_value=["zeta"]), \
             mock.patch.object(setup.subprocess, "run", failing), \
             self.assertRaises(setup.StepFailed) as ctx:
            setup.ensure_python_tool_envs(types.SimpleNamespace(
                dry_run=False, python_env=[], remotes=None, offline=None))
        self.assertIn("zeta", ctx.exception.reason)


if __name__ == "__main__":
    unittest.main()


class PreparedEnvsTests(unittest.TestCase):
    """PT-38: `--prepare <m>` completes <m>'s Python tool environments that
    were WAITING for its first-party packages -- the command setup prints
    for a waiting env must actually complete it -- and touches no other
    component's envs."""

    setUp = RootStepTests.setUp
    tearDown = RootStepTests.tearDown
    _component = RootStepTests._component

    def _prepare(self, comps, platform):
        context = dict(prepare="zeta", platform=platform)
        with mock.patch.object(setup, "offline_platform", return_value="vs2026"):
            return self._run_prepare(comps, context)

    def _run_prepare(self, comps, context):
        def fake_run(cmd, **kwargs):
            self.calls.append((cmd, kwargs))
            return subprocess.CompletedProcess(cmd, 0, CHILD_OUT, "")
        ctx = types.SimpleNamespace(dry_run=False, python_env=[], remotes="off", offline=None,
                                    **context)
        with mock.patch.object(setup, "ROOT", self.root), \
             mock.patch.object(setup, "discover_components", return_value=comps), \
             mock.patch.object(setup.subprocess, "run", fake_run):
            return setup.complete_prepared_python_envs(ctx)

    def test_prepare_runs_only_the_prepared_components_env_setup(self):
        zeta = self._component("zeta")
        self._component("other")
        self._prepare(["other", "zeta"], "vs2026")
        self.assertEqual(len(self.calls), 1)
        cmd, kwargs = self.calls[0]
        self.assertEqual(cmd[1], str(zeta / "scripts" / "setup.py"))
        self.assertIn("--python-envs-only", cmd)
        self.assertEqual(cmd[cmd.index("--remotes") + 1], "off")

    def test_planted_prepare_for_another_platform_touches_no_env(self):
        self._component("zeta")
        self.assertEqual(self._prepare(["zeta"], "ubuntu_gcc"), "skip")
        self.assertEqual(self.calls, [])

    def test_prepare_step_follows_the_closure_step(self):
        tree = ast.parse((setup.ROOT / "scripts" / "setup.py").read_text(encoding="utf-8"))
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
        order = [n.args[2].id for n in ast.walk(fn)
                 if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "step"
                 and len(n.args) >= 3 and isinstance(n.args[2], ast.Name)]
        self.assertLess(order.index("prepare_first_party_deps"),
                        order.index("complete_prepared_python_envs"))
