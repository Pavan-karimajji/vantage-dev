# Copyright (c) LT EPS. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SUPERPROJECT
# @file submodule_init.py
# @brief Initialise exactly the submodules a command is about to compile (W3).
# @author Pavan Karimajji

"""W3 (partial_clone_correctness_plan.md): clone what you compile.

`init_submodules_for(mods)` initialises the named `modules/<m>` submodules and
nothing else (D4/D5). It never deletes anything (D6), never prompts and never
replaces git configuration (D7), prints the plan before acting (D8) and clones
nothing under `dry_run`. It does NOT depend on the Conan remotes switch: that
switch says whether Conan may contact a package server, not whether git can
reach the submodule's repository - and an unreachable one fails in seconds
here (no prompt), naming the manual command.

D6 - two questions, two definitions, deliberately: "is there source to judge?"
is `modules/<m>/conanfile.py` existing (build.py's is_valid_module()); "may git
populate this directory?" is `git submodule status` showing a leading `-`.
A directory that is initialised but has no conanfile.py is half-populated and
refused with a recovery command.
"""
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class SubmoduleInitError(Exception):
    """A refusal; `lines` are the message lines to print (last one is the
    command to run)."""

    def __init__(self, lines):
        super().__init__(lines[0])
        self.lines = list(lines)


def git_environment(base=None, run=subprocess.run):
    """D7: never prompt, never clobber. An existing GIT_SSH_COMMAND wins over
    core.sshCommand, which wins over plain `ssh`; ` -o BatchMode=yes` is
    appended to whichever it is (so a `-o Port=22` survives)."""
    env = dict(os.environ if base is None else base)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "never"
    ssh = env.get("GIT_SSH_COMMAND")
    if not ssh:
        configured = run(["git", "config", "core.sshCommand"], capture_output=True, text=True)
        ssh = (configured.stdout or "").strip() if configured.returncode == 0 else ""
    env["GIT_SSH_COMMAND"] = f"{ssh or 'ssh'} -o BatchMode=yes"
    return env


def _is_checked_out(mod, root):
    return (Path(root) / "modules" / mod / "conanfile.py").is_file()


def _status_char(mod, root, run):
    """First character of `git submodule status modules/<m>`: '-' not
    initialised; ' ', '+' or 'U' initialised; None when git does not know it."""
    result = run(["git", "submodule", "status", f"modules/{mod}"], cwd=str(root),
                 capture_output=True, text=True)
    out = (result.stdout or "").rstrip("\n")
    return out[0] if result.returncode == 0 and out else None


def possibly_uninitialised(mods, root=ROOT):
    """The subset of `mods` that MAY need checking out: an existing modules/<m>
    folder with no `.git` entry (a checked-out submodule always has one). A
    filesystem test, so the usual everything-is-checked-out case costs no git
    call; uninitialised_submodules() confirms the rest."""
    base = Path(root) / "modules"
    return [m for m in mods if (base / m).is_dir() and not (base / m / ".git").exists()]


def uninitialised_submodules(root=ROOT, run=subprocess.run):
    """Names of the modules/<m> submodules git reports as not initialised
    (`git submodule status`, leading `-`) - e.g. every module of a fresh
    superproject clone. [] when git cannot answer."""
    result = run(["git", "submodule", "status"], cwd=str(root),
                 capture_output=True, text=True)
    if result.returncode != 0:
        return []
    names = []
    for line in (result.stdout or "").splitlines():
        parts = line[1:].split()
        if line.startswith("-") and len(parts) >= 2 and parts[1].startswith("modules/"):
            names.append(parts[1][len("modules/"):])
    return sorted(names)


def init_submodules_for(mods, *, root=ROOT, run=subprocess.run, dry_run=False, log=print):
    """Initialise the submodules of `mods` that are not yet. Returns the list
    initialised (under dry_run: the list that would be). Raises
    SubmoduleInitError for a half-populated module or a failed git call.
    Populated modules are never passed to git."""
    to_init, present = [], []
    for mod in sorted(set(mods)):
        status = _status_char(mod, root, run)
        if status is None:
            raise SubmoduleInitError([
                f"ERROR: modules/{mod} is not a submodule git knows about.",
                f"Run: git -C {root} submodule status"])
        if status == "-":
            to_init.append(mod)
        elif _is_checked_out(mod, root):
            present.append(mod)
        else:
            raise SubmoduleInitError([
                f"ERROR: modules/{mod} is initialised but has no conanfile.py - it is "
                "half-populated, and nothing here deletes it.",
                f"Run: git submodule update --init --force modules/{mod}"])

    manual = "git submodule update --init " + " ".join(f"modules/{m}" for m in to_init)
    if not to_init:
        return []
    log(f"Submodules to initialise: {', '.join(to_init)}"
        + (f"  (already present: {', '.join(present)})" if present else ""))
    if dry_run:
        log("(--dry-run: nothing is cloned)")
        return to_init

    env = git_environment(run=run)
    for mod in to_init:
        result = run(["git", "submodule", "update", "--init", "--", f"modules/{mod}"],
                     cwd=str(root), env=env, capture_output=True, text=True)
        if result.returncode != 0:
            raise SubmoduleInitError([
                f"ERROR: git could not initialise modules/{mod}: "
                f"{(result.stderr or result.stdout or '').strip()}",
                f"Run: {manual}"])
        head = run(["git", "-C", f"modules/{mod}", "rev-parse", "HEAD"], cwd=str(root),
                   capture_output=True, text=True)
        log(f"  initialised modules/{mod} at {(head.stdout or '').strip()[:12] or '(unknown)'}")
    return to_init
