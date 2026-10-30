"""
scripts/tests/test_module_fingerprint.py

NS-51 (cache_first_no_server_plan.md WP-11, RV-2): compute_module_fingerprint()
against a REAL git working tree, not a mock.

Format 1 hashed `git status --porcelain` - file names and status letters only -
so editing an already-modified file a second time produced the same
fingerprint, and `build.py df --with shared_config` skipped the re-create and
shipped the previous calibration YAML. These tests drive the actual loop a
developer performs: clean -> edit -> edit the same file again -> revert.

Needs `git` on PATH; skipped (not failed) without it.

Run:
    py -m unittest discover -s scripts/tests
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from conan_home_resolution import compute_module_fingerprint  # noqa: E402


def _git(repo, *args):
    subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True)


@unittest.skipIf(shutil.which("git") is None, "git not on PATH")
class ContentFingerprintTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = self._tmp.name
        _git(self.repo, "init", "-q")
        _git(self.repo, "config", "user.email", "t@example.invalid")
        _git(self.repo, "config", "user.name", "t")
        _git(self.repo, "config", "core.autocrlf", "false")
        self._write("ego_params.yaml", "EGO_WHEELBASE_M: 2.70\n")
        self._write(".gitignore", "*.log\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "init")

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, rel, text):
        with open(os.path.join(self.repo, rel), "w", encoding="utf-8", newline="") as f:
            f.write(text)

    def _fp(self):
        return compute_module_fingerprint(self.repo)

    def test_second_edit_to_the_same_file_changes_the_fingerprint(self):
        """The RV-2 case. Fails against format 1 (porcelain only)."""
        clean = self._fp()
        self._write("ego_params.yaml", "EGO_WHEELBASE_M: 2.80\n")
        edit1 = self._fp()
        self._write("ego_params.yaml", "EGO_WHEELBASE_M: 2.90\n")
        edit2 = self._fp()
        self.assertNotEqual(clean["dirty"], edit1["dirty"])
        self.assertNotEqual(edit1["dirty"], edit2["dirty"],
                            "a second edit to an already-modified file must be visible - "
                            "otherwise the calibration loop ships the previous value")
        self.assertEqual(clean["git"], edit2["git"])

    def test_untracked_file_content_counts(self):
        clean = self._fp()
        self._write("new.yaml", "A: 1\n")
        first = self._fp()
        self._write("new.yaml", "A: 2\n")
        second = self._fp()
        self.assertNotEqual(clean["dirty"], first["dirty"])
        self.assertNotEqual(first["dirty"], second["dirty"])

    def test_ignored_file_does_not_count(self):
        clean = self._fp()
        self._write("build.log", "noise\n")
        self.assertEqual(clean, self._fp(),
                         "a .gitignore'd file is not source and must not force a rebuild")

    def test_reverting_returns_the_clean_fingerprint_exactly(self):
        """Symmetric, not merely sensitive: undoing every edit is 'unchanged'."""
        clean = self._fp()
        self._write("ego_params.yaml", "EGO_WHEELBASE_M: 3.10\n")
        self._write("new.yaml", "A: 1\n")
        self.assertNotEqual(clean, self._fp())
        self._write("ego_params.yaml", "EGO_WHEELBASE_M: 2.70\n")
        os.remove(os.path.join(self.repo, "new.yaml"))
        self.assertEqual(clean, self._fp())

    def test_staged_edit_counts_and_a_second_staged_edit_too(self):
        clean = self._fp()
        self._write("ego_params.yaml", "EGO_WHEELBASE_M: 2.80\n")
        _git(self.repo, "add", "ego_params.yaml")
        staged1 = self._fp()
        self._write("ego_params.yaml", "EGO_WHEELBASE_M: 2.90\n")
        _git(self.repo, "add", "ego_params.yaml")
        staged2 = self._fp()
        self.assertEqual(len({clean["dirty"], staged1["dirty"], staged2["dirty"]}), 3)


class NonGitFingerprintTests(unittest.TestCase):
    """The fallback branch (not a git checkout) must not hash local build
    output, or building the module would change its own fingerprint."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self._write("src/a.cpp", "int a;\n")

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text)

    def _fp(self):
        return compute_module_fingerprint(self.root)

    def test_build_output_does_not_count(self):
        clean = self._fp()
        self._write("conan_workarea/x.json", "{}")
        self._write(".venv-win32/lib/y.py", "y")
        self._write("build-sil-vs2026/z.obj", "z")
        self.assertEqual(clean, self._fp())

    def test_planted_source_edit_still_counts(self):
        clean = self._fp()
        self._write("src/b.cpp", "int b;\n")
        self.assertNotEqual(clean["dirty"], self._fp()["dirty"])

    def test_only_skipped_dirs_is_stable(self):
        with tempfile.TemporaryDirectory() as only:
            os.makedirs(os.path.join(only, "conan_workarea"))
            with open(os.path.join(only, "conan_workarea", "f"), "w") as f:
                f.write("x")
            self.assertEqual(compute_module_fingerprint(only),
                             compute_module_fingerprint(only))



class AbsentModuleFingerprintTests(unittest.TestCase):
    """D1 / Q2 (partial_clone_correctness_plan.md): an absent module has no
    source to fingerprint - raising beats the sha256 of nothing, which would
    read as "changed"."""

    def test_missing_directory_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                compute_module_fingerprint(os.path.join(tmp, "modules", "interfaces"))


if __name__ == "__main__":
    unittest.main()
