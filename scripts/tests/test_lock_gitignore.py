"""scripts/tests/test_lock_gitignore.py

NS-59 (cache_first_no_server_plan.md §5.3): locks live in
`<checkout>/conan_workarea/locks/` and are never committed (LK-D2). Every
component that carries a build-tools pin, and the superproject itself, must
git-ignore that path; `--clean` keeping the files is held by the toolchain's
own tests (test_lockfiles_clean.py). Planted: a repo with no such ignore rule.

Run:
    py -3.12 -m unittest scripts.tests.test_lock_gitignore
"""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCK = "conan_workarea/locks/df-sil-vs2026-base.lock"


def is_ignored(checkout, rel=LOCK):
    proc = subprocess.run(["git", "-C", str(checkout), "check-ignore", "-q", rel],
                          capture_output=True)
    return proc.returncode == 0


def pinned_components():
    return sorted(p.parent.parent.name for p in (ROOT / "modules").glob("*/conf/build_tools.version"))


class LockPathIsIgnoredTests(unittest.TestCase):
    def test_the_superproject_ignores_its_lock_folder(self):
        self.assertTrue(is_ignored(ROOT))

    def test_every_pinned_component_ignores_its_lock_folder(self):
        components = pinned_components()
        if not components:
            self.skipTest("no component with conf/build_tools.version is checked out")
        unignored = [c for c in components
                     if (ROOT / "modules" / c / ".git").exists()
                     and not is_ignored(ROOT / "modules" / c)]
        self.assertEqual(unignored, [], "these components would commit their locks (LK-D2)")

    def test_planted_repo_without_the_rule_is_caught(self):
        tmp = Path(tempfile.mkdtemp(prefix="lock_ignore_"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        subprocess.run(["git", "init", "-q", str(tmp)], check=True)
        self.assertFalse(is_ignored(tmp))
        (tmp / ".gitignore").write_text("conan_workarea/\n", encoding="utf-8")
        self.assertTrue(is_ignored(tmp))


if __name__ == "__main__":
    unittest.main()
