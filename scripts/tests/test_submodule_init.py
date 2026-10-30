# Copyright (c) LT EPS. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SUPERPROJECT
# @file test_submodule_init.py
# @brief W3: init_submodules_for() asserted against a fake git runner.
# @author Pavan Karimajji

"""scripts/tests/test_submodule_init.py

W3 (partial_clone_correctness_plan.md): exact argv, populated modules never
passed to git, half-populated refused with nothing deleted, env merge keeps an
existing GIT_SSH_COMMAND and appends BatchMode, dry-run clones nothing,
cloning is independent of the Conan remotes switch, and the not-initialised
listing reads `git submodule status`'s leading `-`.

Run:
    py -3.12 -m unittest scripts.tests.test_submodule_init
"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import submodule_init as si  # noqa: E402


class _FakeGit:
    """status: {module: '-' | ' ' | None}. Records every argv and env."""

    def __init__(self, status, ssh_config=""):
        self.status = status
        self.ssh_config = ssh_config
        self.calls = []
        self.fail = set()

    def __call__(self, argv, **kwargs):
        self.calls.append((list(argv), kwargs))
        if argv[:3] == ["git", "submodule", "status"]:
            mod = argv[3].split("/")[1]
            char = self.status.get(mod)
            return SimpleNamespace(returncode=0 if char else 1,
                                   stdout=f"{char}abc123 modules/{mod}\n" if char else "",
                                   stderr="")
        if argv[:3] == ["git", "config", "core.sshCommand"]:
            return SimpleNamespace(returncode=0 if self.ssh_config else 1,
                                   stdout=self.ssh_config, stderr="")
        if argv[:3] == ["git", "submodule", "update"]:
            mod = argv[-1].split("/")[1]
            if mod in self.fail:
                return SimpleNamespace(returncode=1, stdout="", stderr="boom")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if argv[:2] == ["git", "-C"]:
            return SimpleNamespace(returncode=0, stdout="0123456789abcdef\n", stderr="")
        raise AssertionError(f"unexpected git call {argv}")

    def updates(self):
        return [c[0] for c in self.calls if c[0][:3] == ["git", "submodule", "update"]]


class InitSubmodulesForTests(unittest.TestCase):

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="subinit_"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.lines = []

    def _populate(self, mod):
        d = self.root / "modules" / mod
        d.mkdir(parents=True, exist_ok=True)
        (d / "conanfile.py").write_text("", encoding="utf-8")
        return d

    def _call(self, git, mods, **kwargs):
        return si.init_submodules_for(mods, root=self.root, run=git, log=self.lines.append,
                                      **kwargs)

    def test_uninitialised_modules_get_exact_argv_one_per_module(self):
        git = _FakeGit({"interfaces": "-", "viz": "-"})
        done = self._call(git, ["viz", "interfaces"])
        self.assertEqual(done, ["interfaces", "viz"])
        self.assertEqual(git.updates(), [
            ["git", "submodule", "update", "--init", "--", "modules/interfaces"],
            ["git", "submodule", "update", "--init", "--", "modules/viz"]])
        self.assertTrue(any("modules/interfaces at 0123456789ab" in line for line in self.lines))

    def test_a_populated_module_is_never_passed_to_git_update(self):
        self._populate("mathlib")
        git = _FakeGit({"mathlib": " ", "viz": "-"})
        self._call(git, ["mathlib", "viz"])
        self.assertEqual(git.updates(),
                         [["git", "submodule", "update", "--init", "--", "modules/viz"]])

    def test_everything_present_is_a_no_op_with_no_update(self):
        self._populate("mathlib")
        git = _FakeGit({"mathlib": " "})
        self.assertEqual(self._call(git, ["mathlib"]), [])
        self.assertEqual(git.updates(), [])

    def test_half_populated_is_refused_with_recovery_and_nothing_deleted(self):
        half = self.root / "modules" / "viz"
        half.mkdir(parents=True)
        (half / "stray.txt").write_text("keep me", encoding="utf-8")
        git = _FakeGit({"viz": " "})  # initialised, but no conanfile.py
        with self.assertRaises(si.SubmoduleInitError) as caught:
            self._call(git, ["viz"])
        self.assertEqual(caught.exception.lines[-1],
                         "Run: git submodule update --init --force modules/viz")
        self.assertEqual(git.updates(), [])
        self.assertTrue((half / "stray.txt").is_file())

    def test_unknown_to_git_is_refused(self):
        with self.assertRaises(si.SubmoduleInitError):
            self._call(_FakeGit({}), ["nosuch"])

    def test_dry_run_prints_the_plan_and_clones_nothing(self):
        git = _FakeGit({"interfaces": "-"})
        done = self._call(git, ["interfaces"], dry_run=True)
        self.assertEqual(done, ["interfaces"])
        self.assertEqual(git.updates(), [])
        self.assertIn("nothing is cloned", " ".join(self.lines))

    def test_cloning_does_not_depend_on_the_conan_remotes_switch(self):
        # The remotes switch governs Conan's package servers, not git; on a
        # machine where it is always off, auto-checkout must still happen.
        import inspect
        self.assertNotIn("remotes_on", inspect.signature(si.init_submodules_for).parameters)
        git = _FakeGit({"interfaces": "-"})
        self.assertEqual(self._call(git, ["interfaces"]), ["interfaces"])
        self.assertEqual(len(git.updates()), 1)

    def test_uninitialised_submodules_reads_the_leading_dash_only(self):
        status = ("-2067355be7cd modules/df\n"
                  " 5334f91661c6 modules/interfaces (heads/main)\n"
                  "+3b9bdae751df modules/toolchain (heads/main)\n"
                  "-0d09a2ca4c63 modules/isp\n"
                  "-aaaaaaaaaaaa vendor/elsewhere\n")
        run = mock.Mock(return_value=SimpleNamespace(returncode=0, stdout=status, stderr=""))
        self.assertEqual(si.uninitialised_submodules(self.root, run=run), ["df", "isp"])
        self.assertEqual(run.call_args.args[0], ["git", "submodule", "status"])

    def test_possibly_uninitialised_is_a_filesystem_test_with_no_git_call(self):
        modules = Path(self.root) / "modules"
        for name in ("df", "viz"):
            (modules / name).mkdir(parents=True, exist_ok=True)
        (modules / "df" / ".git").write_text("gitdir: ../../.git/modules/df\n")  # checked out
        with mock.patch.object(si.subprocess, "run") as run:
            self.assertEqual(si.possibly_uninitialised(["df", "viz", "nosuch"], self.root),
                             ["viz"])
        run.assert_not_called()

    def test_uninitialised_submodules_is_empty_when_git_cannot_answer(self):
        run = mock.Mock(return_value=SimpleNamespace(returncode=128, stdout="", stderr="no repo"))
        self.assertEqual(si.uninitialised_submodules(self.root, run=run), [])

    def test_a_failed_update_is_refused_with_the_manual_command(self):
        git = _FakeGit({"interfaces": "-"})
        git.fail.add("interfaces")
        with self.assertRaises(si.SubmoduleInitError) as caught:
            self._call(git, ["interfaces"])
        self.assertIn("boom", caught.exception.lines[0])

    def test_update_runs_with_a_non_interactive_environment(self):
        git = _FakeGit({"interfaces": "-"})
        with mock.patch.dict(os.environ, {"GIT_SSH_COMMAND": "ssh -o Port=22"}):
            self._call(git, ["interfaces"])
        env = [c[1]["env"] for c in git.calls if c[0][:3] == ["git", "submodule", "update"]][0]
        self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(env["GCM_INTERACTIVE"], "never")
        self.assertEqual(env["GIT_SSH_COMMAND"], "ssh -o Port=22 -o BatchMode=yes")


class GitEnvironmentTests(unittest.TestCase):

    def test_existing_ssh_command_is_extended_never_replaced(self):
        env = si.git_environment({"GIT_SSH_COMMAND": "ssh -o Port=22"}, run=_FakeGit({}))
        self.assertEqual(env["GIT_SSH_COMMAND"], "ssh -o Port=22 -o BatchMode=yes")

    def test_core_ssh_command_is_used_when_the_env_has_none(self):
        git = _FakeGit({}, ssh_config="ssh -i key")
        env = si.git_environment({}, run=git)
        self.assertEqual(env["GIT_SSH_COMMAND"], "ssh -i key -o BatchMode=yes")

    def test_plain_ssh_is_the_last_resort(self):
        env = si.git_environment({}, run=_FakeGit({}))
        self.assertEqual(env["GIT_SSH_COMMAND"], "ssh -o BatchMode=yes")

    def test_other_environment_is_kept(self):
        env = si.git_environment({"PATH": "x", "GIT_SSH_COMMAND": "ssh"}, run=_FakeGit({}))
        self.assertEqual(env["PATH"], "x")


if __name__ == "__main__":
    unittest.main()
