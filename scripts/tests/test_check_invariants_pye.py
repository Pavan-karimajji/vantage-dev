"""
scripts/tests/test_check_invariants_pye.py

Regression tests for PYE-1 (scripts/check_invariants.py, PT-02 --
python_tool_envs_plan.md D1/D2). The planted-violation proof (R-REQ-9):
each of PYE-1's failure modes is planted in a synthetic tree and must be
reported; a well-formed tree and the real checkout must both pass.

Isolated from the real tree with a tempfile fixture (same pattern as
test_check_invariants_bun.py). The fixture copies the real
adas_build_tools/config.py in, so PYE-1 exercises the one real parser.

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

REAL_CONFIG = check_invariants.ROOT / "modules" / "toolchain" / "adas_build_tools" / "config.py"

GOOD_BUILD_YML = """\
variants: {}
python_envs:
  replay:
    python: "3.12"
    intent: tools/requirements.txt
    lock: tools/requirements.lock
    default: true
"""
GOOD_LOCK = "# LOCK -- generated\nmcap==1.5.0\nPyYAML==6.0.3\n"


class PyeTreeFixture(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="pye_invariant_")
        self.root = Path(self._tmp)
        pkg = self.root / "modules" / "toolchain" / "adas_build_tools"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        shutil.copy(REAL_CONFIG, pkg / "config.py")
        (self.root / "modules" / "toolchain" / "pyproject.toml").write_text("", encoding="utf-8")
        self.comp = self._component("df", GOOD_BUILD_YML)
        self._write("df/tools/requirements.txt", "mcap>=1.0\n")
        self._write("df/tools/requirements.lock", GOOD_LOCK)

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _write(self, rel, text):
        path = self.root / "modules" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def _component(self, name, build_yml, gitignore=".venv-*/\n"):
        self._write(f"{name}/conf/build.yml", build_yml)
        if gitignore is not None:
            self._write(f"{name}/.gitignore", gitignore)
        return self.root / "modules" / name

    def findings(self):
        return check_invariants.check_pye1(self.root)


class Pye1Tests(PyeTreeFixture):

    def test_well_formed_tree_is_clean(self):
        self.assertEqual(self.findings(), [])

    def test_real_checkout_is_clean(self):
        self.assertEqual(check_invariants.check_pye1(), [])

    def test_missing_lock_is_reported(self):
        (self.comp / "tools" / "requirements.lock").unlink()
        found = self.findings()
        self.assertEqual(len(found), 1, found)
        self.assertIn("df:replay lock", found[0])
        self.assertIn("lock_python_env.py df replay", found[0])

    def test_missing_package_dir_is_reported(self):
        self._write("df/conf/build.yml", GOOD_BUILD_YML + "    package: nowhere\n")
        self.assertIn("df:replay package", " ".join(self.findings()))

    def test_undeclared_requirements_txt_is_reported(self):
        self._write("df/tools/other/requirements.txt", "numpy\n")
        found = self.findings()
        self.assertEqual(len(found), 1, found)
        self.assertIn("modules/df/tools/other/requirements.txt", found[0])

    def test_undeclared_pyproject_in_non_declaring_component_is_reported(self):
        self._component("vdy", "variants: {}\n", gitignore=None)
        self._write("vdy/pyproject.toml", "[project]\nname='x'\n")
        self.assertIn("modules/vdy/pyproject.toml", " ".join(self.findings()))

    def test_toolchain_pyproject_is_exempt_by_name(self):
        self.assertNotIn("toolchain", " ".join(self.findings()))

    def test_intent_pulled_in_by_dash_r_is_covered(self):
        self._write("df/tools/requirements-core.txt", "pyyaml\n")
        self._write("df/tools/requirements.txt", "-r requirements-core.txt\nmcap\n")
        self.assertEqual(self.findings(), [])

    def test_gitignore_without_venv_glob_is_reported(self):
        (self.comp / ".gitignore").write_text("build/\n.venv/\n", encoding="utf-8")
        self.assertIn(".gitignore lacks `.venv-*/`", " ".join(self.findings()))

    def test_non_exact_lock_line_is_reported(self):
        (self.comp / "tools" / "requirements.lock").write_text(
            GOOD_LOCK + "numpy>=1.26\n", encoding="utf-8")
        found = self.findings()
        self.assertEqual(len(found), 1, found)
        self.assertIn("requirements.lock:4", found[0])
        self.assertIn("numpy>=1.26", found[0])

    def test_schema_error_is_reported_naming_the_key(self):
        self._write("df/conf/build.yml", GOOD_BUILD_YML.replace('    python: "3.12"\n', ""))
        self.assertIn("python_envs.replay.python", " ".join(self.findings()))

    def test_requires_under_python_envs_is_reported(self):
        self._write("df/conf/build.yml", GOOD_BUILD_YML + "    requires: [protobuf/3.21.12]\n")
        self.assertIn("python_envs.replay.requires", " ".join(self.findings()))


if __name__ == "__main__":
    unittest.main()
