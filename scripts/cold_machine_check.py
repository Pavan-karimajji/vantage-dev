#!/usr/bin/env python3
# Copyright (c) LT EPS. All Rights Reserved.
# Proprietary and Confidential.
# @author Pavan Karimajji

"""
scripts/cold_machine_check.py

RD-14 (remove_develop_mode_plan.md, 2026-09-22): makes RD-09's real,
once-by-hand cold-machine proof permanent and one command. RD-09 proved
this class of bug by hand: a scratch CONAN_HOME, df's own component
.venv moved aside, then the exact commands a real fresh machine needs -
`setup.bat` and `python scripts\\build.py df -t sil -p vs2026 -P base`
(+ `--with viz`). This script runs that same sequence, prints PASS/FAIL per
step with the first error, and ALWAYS cleans up: stop any scratch server,
delete the scratch dir, restore .venv, restore
scripts/team_conan_server.txt - on success, on a real failure, and on
Ctrl-C (SIGINT/SIGTERM handlers call the same cleanup path as the normal
`finally`).

WP-5/NS-09 (cache_first_no_server_plan.md, TASK 2, 2026-09-24): the fresh-
machine flow documented above is now THREE commands, not two - a real
run proved (STEP 5, prior session) that `setup.bat` alone leaves a
genuinely empty scratch cache without df's own first-party dependency
closure (interfaces/mathlib/shared_config/sim/viz - `misc/offline_bundle/`
deliberately never carries these, D3/RQ-6), so `build.py` failed before it
ever had a chance to build them from source. `setup.py --prepare df -t sil
-p vs2026 -P base` now runs between `setup.bat` and the first `build.py`
step, in both modes.

D6/NS-21 (cache_first_no_server_plan.md, 2026-09-23): two modes.
  - Default (no flag): the cache-first proof - NO conan_server anywhere,
    `--remotes off` on every command, resolving from the Conan cache and
    misc/offline_bundle/ only.
  - `--with-server`: the OLDER proof, kept for the remotes-ON path - a
    real scratch conan_server (server.conf's permissions deliberately
    left broken so setup.bat's own NS-21/CE-34 self-heal fixes them for
    real, not just in a mocked unit test).
Both modes also plant a stray Conan editable pointing at a fake other
checkout (NS-22/CE-35) partway through, proving the aggregate build
refuses it by name, that `--clean-develop-leftovers --yes` clears it, and
that the SAME build then proceeds.

Never touches the real ~/.conan2 or the real adas-local storage:
CONAN_HOME is overridden in a per-subprocess env dict, never
os.environ itself, so this process's own environment (and anything it
does NOT explicitly launch with the scratch env) is unaffected;
scripts/team_conan_server.txt is restored from an in-memory copy of its
original bytes in every code path, verified against `git status` at the
end of a real run (see RD-09's own verification record).

Windows-only (setup.bat, vs2026/MSVC, conan_server.exe) - refuses cleanly,
without touching anything, on any other OS. Same "not this OS, skip"
pattern as setup.py::full_verify().

NS-25 (cache_first_no_server_plan.md, 2026-09-23): a real --with-server
run died hard enough that its `finally` never ran, leaving the machine
dirty - the supervisor had to restore it by hand. Cleanup is now
registered via `atexit` AND SIGINT/SIGTERM handlers AND the original
`finally` (all three call the same idempotent ColdMachineCheck.cleanup());
every mutation is recorded in a breadcrumb file, written incrementally as
it happens, at a FIXED path outside the scratch dir itself
(~/.adas_cold_check_breadcrumb.json); `--cleanup-only` reads that
breadcrumb (from a fresh process, with no memory of the dead run) and
finishes the job; and every run - normal or --cleanup-only - ends by
asserting the machine is actually back (assert_machine_clean()), printing
what it verified, not just trusting that cleanup() didn't raise.

Usage:
    python scripts\\cold_machine_check.py                 (no-server, default)
    python scripts\\cold_machine_check.py --with-server    (remotes-ON path)
    python scripts\\cold_machine_check.py --cleanup-only   (NS-25: finish an
                                                            interrupted cleanup)

Before changing setup.py/build.py/check_conan_resolution.py's Conan
wiring, run this first (see setup.md and
.claude/workflows/change_build_machinery.md).
"""
import os
import atexit
import json
import shutil
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conan_server_guard  # noqa: E402
import setup as adas_setup  # noqa: E402  (this repo's own scripts/setup.py)

ROOT = Path(__file__).resolve().parent.parent
DF_VENV_DIR = ROOT / "modules" / "df" / f".venv-{sys.platform}"
# PT-26: df's replay tool environment -- moved aside and restored exactly like
# DF_VENV_DIR (same mechanism, _move_aside_dirs()), never deleted.
REPLAY_VENV_DIR = ROOT / "modules" / "df" / f".venv-replay-{sys.platform}"
# NS-68 (WP-13): the locks the cold run's builds write land in the REAL checkout
# (modules/df/conan_workarea/locks for a root solo build, the superproject's own
# for an aggregate), pinning revisions of the SCRATCH cache - which the run
# deletes. Left behind they would make the developer's next real build refuse
# ("pinned revision not in the cache"), so they are moved aside and restored
# exactly like the venvs, and a folder that did not exist before is removed.
DF_LOCKS_DIR = ROOT / "modules" / "df" / "conan_workarea" / "locks"
ROOT_LOCKS_DIR = ROOT / "conan_workarea" / "locks"
DF_LOCK_NAME = "df-sil-vs2026-base.lock"
PORT_RANGE = range(9310, 9400)
SCRATCH_ROOT_NAME_PREFIX = "adas_cold_check_"

# NS-25 (cache_first_no_server_plan.md, 2026-09-23): a real --with-server
# run died without its finally running (no atexit/signal handler existed
# yet) and left the machine dirty - team_conan_server.txt stripped,
# modules/df/.venv-win32 not restored, an orphaned conan_server still
# LISTENING, two scratch dirs left in %USERPROFILE%; the supervisor
# restored it all by hand. BREADCRUMB_FIXED_PATH is written to on EVERY
# mutation (not just at cleanup time) and lives outside scratch_root
# itself - a scratch dir that never finished being created, or that a
# later run can't otherwise locate, still leaves a breadcrumb a human or
# --cleanup-only can find. A copy is also written inside scratch_root
# (when one exists) purely for a human poking around after a crash - only
# the fixed path is ever READ by --cleanup-only.
BREADCRUMB_FIXED_PATH = Path.home() / ".adas_cold_check_breadcrumb.json"
BREADCRUMB_FILENAME = "cold_check_breadcrumb.json"

# NS-26 (cache_first_no_server_plan.md, WP-7, TASK 3): two concurrent runs
# used to share BREADCRUMB_FIXED_PATH and every fixed-name backup path
# (modules/df/.venv-win32.cold_check_bak, ...) with no barrier at all - one
# run's cleanup() could restore over a still-in-progress sibling's own
# mutation (suspected cause of a `check_conan_resolution.py
# --publish-missing` upload error seen once, on a machine a second Claude
# Code session was later confirmed to be running its own cold-machine
# check on concurrently - `cache_first_no_server_plan.md` STEP 5's own
# record). A plain, best-effort PID lock file at a FIXED path (never
# inside scratch_root, which doesn't exist yet when the lock is taken):
# a second `run()` sees it and refuses immediately, before creating any
# scratch state, naming the owning pid and scratch root instead of racing
# ahead into "it worked the second time" confusion. `--cleanup-only`
# deliberately never calls `_acquire_lock()` (it must still work while a
# lock is held - that is exactly the tool for clearing a stale one left by
# a run that died hard enough that its own `cleanup()` never ran) and
# proactively removes any lock file it finds, whatever pid it names.
LOCK_FIXED_PATH = Path.home() / ".adas_cold_check.lock"

# NS-44 (cache_first_no_server_plan.md, RQ-8): a TRACKED record of the last
# PASSING run of this script, one entry per mode ("no-server"/"with-
# server"), so `RQ-8`'s "prove it on a manufactured machine before calling
# a machinery change done" can be enforced by check_invariants.py's COLD-1
# instead of depending on a human re-reading this file's own docstring.
# Inside scripts/ deliberately (not the scratch dir, not the home
# directory) so it is committed alongside the very machinery it proves was
# tested - but it is its OWN file, read/written only from here, and is
# EXCLUDED from COLD-1's own "did machinery move since the last passing
# run" walk (see check_invariants.check_cold1()'s own _COLD1_PATHS) so
# that writing this record is never itself the thing that invalidates it.
COLD_RUN_RECORD_PATH = ROOT / "scripts" / "cold_run_record.json"
# NS-55: the exact step name COLD-1 requires in the newest record - defined
# once, in check_invariants.py (the lighter module), so the two cannot drift.
from check_invariants import COLD1_WITH_ALL_STEP as WITH_ALL_STEP_NAME  # noqa: E402
# NS-68: same reasoning - the three lock steps are named once, in check_invariants.
from check_invariants import (COLD1_LOCK_MADE_STEP, COLD1_LOCK_REFUSED_STEP,  # noqa: E402
                              COLD1_LOCK_REUSED_STEP)


class ColdCheckLocked(RuntimeError):
    """NS-26: raised by _acquire_lock() when another cold_machine_check.py
    run already holds LOCK_FIXED_PATH. Carries the owning pid/scratch root
    (from the lock file's own contents) so the caller can name them in its
    refusal message without a second read."""

    def __init__(self, owner_pid, owner_scratch_root):
        self.owner_pid = owner_pid
        self.owner_scratch_root = owner_scratch_root
        super().__init__(
            f"another cold_machine_check.py run is already in progress "
            f"(pid {owner_pid}, scratch root {owner_scratch_root or '(not yet created)'})")


def _acquire_lock():
    """NS-26: the whole mechanism in one function - see the module-level
    comment above LOCK_FIXED_PATH for the incident this closes. Refuses
    (raises ColdCheckLocked) rather than overwriting an existing lock file,
    so two processes racing here can never both believe they hold it."""
    if LOCK_FIXED_PATH.exists():
        try:
            data = json.loads(LOCK_FIXED_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        raise ColdCheckLocked(data.get("pid"), data.get("scratch_root"))
    LOCK_FIXED_PATH.write_text(
        json.dumps({"pid": os.getpid(), "scratch_root": None}, indent=2) + "\n",
        encoding="utf-8")


def _update_lock_scratch_root(scratch_root):
    """Called once setup_scratch() knows its own scratch_root, so a second
    run's refusal message names it too, not just the pid. A no-op if this
    process doesn't actually own the lock file on disk (defensive only -
    should be unreachable, since only the process that just wrote it via
    _acquire_lock() ever calls this)."""
    if not LOCK_FIXED_PATH.exists():
        return
    try:
        data = json.loads(LOCK_FIXED_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if data.get("pid") != os.getpid():
        return
    data["scratch_root"] = str(scratch_root)
    LOCK_FIXED_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _release_lock():
    """Removes LOCK_FIXED_PATH only if it is still this process's own -
    never clobbers a different run's lock. Called unconditionally from
    ColdMachineCheck.cleanup() (a no-op if this process never acquired the
    lock in the first place, e.g. it was never reached because
    _acquire_lock() itself raised)."""
    if not LOCK_FIXED_PATH.exists():
        return
    try:
        data = json.loads(LOCK_FIXED_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if data.get("pid") == os.getpid():
        LOCK_FIXED_PATH.unlink(missing_ok=True)


class Step:
    def __init__(self, name):
        self.name = name
        self.ok = None
        self.first_error = None
        self.seconds = None  # R-TEST-7; None = not timed (older records lack it)


def _scratch_root():
    """Under %USERPROFILE% (Path.home() - identical on this repo's own
    Windows machines), never %TEMP% - RD-09's own explicit requirement, so
    a failed run leaves something a developer can go look at rather than
    something the OS silently sweeps."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path.home() / f"{SCRATCH_ROOT_NAME_PREFIX}{stamp}"


def _free_port():
    for port in PORT_RANGE:
        if not conan_server_guard._port_in_use(port, host="127.0.0.1"):
            return port
    raise SystemExit(f"No free port found in {PORT_RANGE.start}-{PORT_RANGE.stop}; "
                      "clean up any leftover adas_cold_check_* conan_server processes.")


# NS-21 (cache_first_no_server_plan.md, redo of CE-34): _ensure_section_
# line() and the permission-fixing half of _write_server_conf() below used
# to be this script's own local copy - found live writing this WP for real
# (2026-09-22), two copies had already begun to drift apart (this one never
# forced an active [read_permissions] line; scripts/setup.py's real
# ensure_server_running() needed exactly that too). Moved to setup.py, the
# single shared implementation, and re-exported here under the same name so
# every existing `cmc._ensure_section_line(...)` call (including this
# file's own tests) keeps working unchanged.
_ensure_section_line = adas_setup._ensure_section_line


def _write_server_conf_port(server_data_dir, port):
    """RD-09's own by-hand edit, applied programmatically: this scratch
    server needs a non-default, dynamically-chosen port (`_free_port()`)
    so it never collides with a real adas-local on this same machine -
    the ONLY thing this function still touches.

    NS-21 (cache_first_no_server_plan.md, redo of CE-34): the permission-
    line fix this function used to ALSO apply right here is deliberately
    NOT applied any more - left commented-out, on purpose, so the scratch
    machine this script manufactures is "closer to the real one" (a real
    corporate PC hit exactly this bug on a real server): `setup.bat`'s
    own `ensure_server_running()` (`adas_setup.ensure_server_conf_
    permissions()`/`_server_conf_permission_fix()`, the single shared
    implementation, never a second copy here) is now the thing that has
    to fix it, proving that fix for real on every run of this script, not
    just asserted in a mocked unit test. Was named `_write_server_conf()`,
    doing both jobs - split so the port-only half (still needed
    unconditionally) is never confused with the permission half (now
    deliberately left broken here)."""
    conf_path = server_data_dir / "server.conf"
    text = conf_path.read_text(encoding="utf-8")
    lines = []
    in_server_section = False
    port_written = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            in_server_section = (stripped == "[server]")
        if in_server_section and stripped.startswith("port"):
            lines.append(f"port: {port}")
            port_written = True
            continue
        lines.append(line)
    if not port_written:
        lines.append(f"port: {port}")
    text = "\n".join(lines) + "\n"

    conf_path.write_text(text, encoding="utf-8")


def _terminate_process_tree(proc):
    """Real bug found running this script for real (2026-09-22):
    `Popen.terminate()` on Windows only signals the ONE process it names -
    a launched conan_server can sit behind one or more wrapper/launcher
    processes (pip's own console-script .exe stub, previously this
    script's own conan_server_guard.py indirection before it was dropped),
    and terminating just the top PID orphaned the real server, still bound
    to the scratch port, silently serving the NEXT run's requests with
    THIS run's stale config. `taskkill /F /T /PID` recursively kills the
    whole tree regardless of how many wrapper layers deep it is - the
    robust fix, not "know the exact process shape and kill each PID"."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        capture_output=True)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)


class ColdMachineCheck:
    """Owns every piece of scratch/temporarily-modified state this script
    ever creates, and is the single place that knows how to undo all of
    it - `run()` calls `cleanup()` from a `finally`, and the signal
    handlers installed in `main()` call the exact same method.

    NS-21/D6 (cache_first_no_server_plan.md): two modes, `with_server`
    picks between them. Default (`with_server=False`) is what the proof
    changed TO with the cache-first model: no conan_server at all - the
    proof is that `setup.bat`/`build.py` resolve everything from the
    Conan cache + `misc/offline_bundle/` with remotes explicitly off, on
    a machine that never ran a server in the first place.
    `with_server=True` is the OLD proof, kept for the day a real remote
    matters again: a real scratch conan_server, exercising the remotes-ON
    path end-to-end - including NS-21/CE-34's server.conf self-heal
    (deliberately NOT pre-fixed here, see `_write_server_conf_port()`)
    and CE-36's reachability gate."""

    def __init__(self, with_server=False):
        self.with_server = with_server
        self.scratch_root = None
        self.conan_home = None
        self.server_data_dir = None
        self.port = None
        self.server_proc = None
        self.team_server_original_bytes = None
        self.team_server_backup_file = None
        # {original dir: backup dir} for every folder moved aside (PT-26:
        # DF_VENV_DIR and REPLAY_VENV_DIR, one mechanism for both).
        self.moved_aside = {}
        # PT-26: fingerprint of the real replay venv taken before the move,
        # compared by assert_machine_clean() after the move-back.
        self.replay_fingerprint = None
        # NS-68: lock folders that did not exist before the run (removed by
        # cleanup) and {folder: {file: sha256}} of those that did (compared by
        # assert_machine_clean after they are moved back).
        self.remove_if_present = []
        self.locks_before = {}
        # NS-25: guards cleanup() against being run twice - atexit, the
        # SIGINT/SIGTERM handlers, and the normal `finally` can all end up
        # calling it on the same process (e.g. Ctrl-C runs the signal
        # handler's cleanup() then sys.exit(130) unwinds into the still-
        # pending `finally`, which would otherwise call it again).
        self._cleaned_up = False

    def _move_df_venv_aside(self):
        """Moves every folder in _moved_aside_dirs() aside (renamed to
        `<name>.cold_check_bak`, never deleted); cleanup() moves each back.
        PT-26: the replay venv's fingerprint is taken first, so the
        post-cleanup assertions can prove it came back byte-identical."""
        if REPLAY_VENV_DIR.exists():
            self.replay_fingerprint = dir_fingerprint(REPLAY_VENV_DIR)
        for path in _lock_dirs():
            self.locks_before[str(path)] = lock_dir_listing(path)
            if not path.exists():
                self.remove_if_present.append(str(path))
        for path in _moved_aside_dirs():
            if path.exists():
                backup = path.with_name(path.name + ".cold_check_bak")
                if backup.exists():
                    # PT-47: an existing backup may be the only copy of a
                    # developer's real folder (an interrupted run) - never
                    # delete it to make room.
                    raise RuntimeError(
                        f"Reason: {backup} already exists (left by an interrupted run) and "
                        "may be the only copy of your real environment.\n"
                        "Fix: restore it first with the cold check's recovery mode.\n"
                        f"Run: {_cleanup_only_command()}")
                path.rename(backup)
                self.moved_aside[str(path)] = str(backup)
                print(f"[cold-check] moved aside: {path} -> {backup}")
            else:
                print(f"[cold-check] {path} doesn't exist yet - nothing to move aside.")
            self._write_breadcrumb()

    def _breadcrumb_dict(self):
        """NS-25: everything --cleanup-only (or a human) needs to finish
        an interrupted cleanup without this process's own in-memory
        state. Every value is a plain str/int/bool/null - json.dumps()
        needs no Path-aware encoder."""
        return {
            "version": 1,
            "pid": os.getpid(),
            "with_server": self.with_server,
            "scratch_root": str(self.scratch_root) if self.scratch_root else None,
            "team_server_file": str(adas_setup.TEAM_SERVER_FILE),
            "team_server_backup_file": (str(self.team_server_backup_file)
                                         if self.team_server_backup_file else None),
            "moved_aside": dict(self.moved_aside),
            "remove_if_present": list(self.remove_if_present),
            "locks_before": dict(self.locks_before),
            "replay_fingerprint": self.replay_fingerprint,
            "server_data_dir": str(self.server_data_dir) if self.server_data_dir else None,
            "port": self.port,
        }

    def _write_breadcrumb(self):
        """NS-25: called after EVERY mutation, not just at the end - a
        process killed between two mutations must still leave a
        breadcrumb naming the ones that already happened. Written to the
        fixed, outside-scratch_root path (survives even if scratch_root
        itself is later deleted or was never fully created) and, when a
        scratch_root already exists, also mirrored inside it purely for a
        human to find while poking around after a crash - only the fixed
        path is ever read back by --cleanup-only."""
        data = json.dumps(self._breadcrumb_dict(), indent=2) + "\n"
        BREADCRUMB_FIXED_PATH.write_text(data, encoding="utf-8")
        if self.scratch_root is not None and self.scratch_root.exists():
            (self.scratch_root / BREADCRUMB_FILENAME).write_text(data, encoding="utf-8")

    def setup_scratch(self):
        self.scratch_root = _scratch_root()
        self.scratch_root.mkdir(parents=True, exist_ok=False)
        self.conan_home = self.scratch_root / "conan_home"
        self.conan_home.mkdir()
        print(f"[cold-check] scratch root: {self.scratch_root}")
        print(f"[cold-check] scratch CONAN_HOME: {self.conan_home}")
        self._write_breadcrumb()
        # NS-26: the lock was acquired (pid only) before this method ever
        # ran - now that scratch_root is known, name it too, so a second
        # run's refusal message is fully specific.
        _update_lock_scratch_root(self.scratch_root)

        if not self.with_server:
            # D6 (cache_first_no_server_plan.md): the default proof - NO
            # conan_server anywhere, `--remotes off` passed explicitly to
            # every command run() issues (never relying on scripts/
            # team_conan_server.txt's own content, which NS-24 already
            # reads as off on THIS machine's committed loopback URL, but
            # a future edit to that file must never silently change what
            # this mode proves). team_conan_server.txt itself is left
            # completely untouched - nothing to restore in cleanup().
            print("[cold-check] no-server mode (default, D6): no conan_server "
                  "anywhere, --remotes off on every command.")
            self._move_df_venv_aside()
            return

        self.server_data_dir = self.scratch_root / "server_data"
        self.port = _free_port()
        print(f"[cold-check] scratch conan_server port: {self.port}")

        conan_server_exe = adas_setup._find_conan_server_exe()
        if conan_server_exe is None:
            raise RuntimeError(
                "conan_server executable not found (pip install --user conan_server). "
                "See setup.md section 5.4.")

        migrate = subprocess.run(
            [conan_server_exe, "--server_dir", str(self.server_data_dir), "--migrate"],
            capture_output=True, text=True, timeout=60)
        if migrate.returncode != 0:
            raise RuntimeError(
                f"conan_server --migrate failed (exit {migrate.returncode}): "
                f"{migrate.stderr.strip() or migrate.stdout.strip()}")

        _write_server_conf_port(self.server_data_dir, self.port)

        # NS-21 (cache_first_no_server_plan.md, redo of CE-34): the server
        # is deliberately NOT launched here any more - server.conf's
        # permission lines are still commented-out (the real, freshly-
        # migrated default template, per _write_server_conf_port()'s own
        # docstring), so `setup.bat`'s own ensure_server_running() is what
        # has to install/fix/launch it for real, exactly like a genuinely
        # fresh machine would - "closer to the real one" than a pre-
        # launched, already-correct server would prove, and it proves
        # NS-21's own self-heal on every run of this script rather than
        # only in a mocked unit test. self.server_proc therefore starts
        # this run as None; whatever ends up listening on self.port
        # (launched by setup.bat, a detached process this script never
        # directly Popen'd) is found and stopped by PID-by-port lookup in
        # cleanup() instead.
        print(f"[cold-check] server_data prepared, permissions left broken on "
              f"purpose (NS-21/CE-34) - setup.bat's own ensure_server_running() "
              f"must install/fix/launch conan_server on 127.0.0.1:{self.port}.")

        # Point THIS process's own view of the team server at the scratch
        # one - restored byte-for-byte in cleanup(). Never edited via
        # os.environ; setup.bat/build.py read the file fresh every run,
        # same as a real developer would. NOTE: this URL is loopback, so
        # NS-24 alone would read it as "no team server" - run() passes
        # `--remotes on` explicitly on every command in this mode, the
        # same override a real developer running their own local server
        # would need post-D1a.
        self.team_server_original_bytes = adas_setup.TEAM_SERVER_FILE.read_bytes()
        # NS-25: persisted to disk immediately, not just held in memory -
        # in-memory bytes are gone the instant this process dies, which is
        # exactly the failure this row closes. --cleanup-only (running as
        # a FRESH process, with no memory of this run at all) reads this
        # file back via the breadcrumb instead.
        self.team_server_backup_file = self.scratch_root / "team_conan_server.txt.orig"
        self.team_server_backup_file.write_bytes(self.team_server_original_bytes)
        adas_setup.TEAM_SERVER_FILE.write_text(
            f"http://127.0.0.1:{self.port}\n", encoding="utf-8")
        self._write_breadcrumb()

        self._move_df_venv_aside()

    def make_no_toolchain_home(self):
        """NS-56: a second, EMPTY CONAN_HOME under scratch_root, so "no
        adas-toolchain recipe" is a fact about the home rather than about the
        order steps ran in - setup.bat exports the pin into the main scratch
        home a moment later. Removed with scratch_root by cleanup()."""
        home = Path(self.scratch_root) / "conan_home_no_toolchain"
        home.mkdir()
        return home

    def subprocess_env(self):
        env = dict(os.environ)
        env["CONAN_HOME"] = str(self.conan_home)
        if self.with_server:
            # Real bug found running this script for real, 2026-09-23:
            # without this, setup.bat's own ensure_server_running() reads
            # ADAS_CONAN_SERVER_DIR's default (C:\ws\conan_server_data) -
            # THIS machine's real adas-local, not the scratch one this
            # run just prepared - so a real, already-running server there
            # reports "[SKIP] ... already satisfied" while the scratch
            # server.conf (deliberately left broken, NS-21) is never
            # looked at, let alone fixed or launched.
            env["ADAS_CONAN_SERVER_DIR"] = str(self.server_data_dir)
        else:
            # D6: no-server mode must never point a subprocess at ANY
            # server directory, including one an ambient shell happens to
            # have set - there is no scratch server here to forward.
            env.pop("ADAS_CONAN_SERVER_DIR", None)
        return env

    def cleanup(self):
        # NS-25: idempotency guard - atexit, the SIGINT/SIGTERM handlers,
        # and the normal `finally` can all reach this on the same
        # instance. Without it, a second pass would re-enter the
        # `venv_moved_aside` branch below, delete the JUST-RESTORED real
        # venv (because it still exists), then crash renaming a backup
        # path that no longer exists.
        if self._cleaned_up:
            print("[cold-check] cleanup() already ran for this instance - nothing more to do.")
            return
        print("[cold-check] cleaning up...")
        cleanly = True
        if self.server_proc is not None and self.server_proc.poll() is None:
            _terminate_process_tree(self.server_proc)
            print(f"[cold-check] scratch conan_server (pid {self.server_proc.pid}) "
                  "and its process tree stopped.")
            self.server_proc = None
        elif self.port is not None and adas_setup._port_reachable(self.port):
            # NS-21 (redo of CE-34): self.server_proc is None whenever
            # setup.bat's own ensure_server_running() was the one to
            # launch it (the normal case now, per setup_scratch()'s own
            # docstring) - this process never Popen'd it, so there is no
            # handle to .terminate()/.wait(). Found and stopped by
            # PID-by-port lookup instead (the identical mechanism NS-21's
            # own restart path uses in setup.py) - never leaves a real,
            # still-running conan_server behind just because this script
            # didn't launch it directly.
            pid = adas_setup._find_listening_pid(self.port)
            if pid is not None and adas_setup._kill_pid_tree(pid):
                print(f"[cold-check] scratch conan_server (pid {pid}, launched by "
                      f"setup.bat) on 127.0.0.1:{self.port} stopped.")
            else:
                print(f"[cold-check] WARNING: something is still listening on "
                      f"127.0.0.1:{self.port} and could not be found/stopped - "
                      "stop it by hand (check Task Manager for a stray "
                      "conan_server.exe).")
                cleanly = False
        if self.team_server_original_bytes is not None:
            adas_setup.TEAM_SERVER_FILE.write_bytes(self.team_server_original_bytes)
            print(f"[cold-check] restored {adas_setup.TEAM_SERVER_FILE}.")
            self.team_server_original_bytes = None
        # PT-47: never delete what can't be restored. A folder is removed
        # only after its backup is verified to exist; with no backup the
        # current folder is left untouched, reported, and kept pending in
        # the breadcrumb (rewritten after each entry so it never names a
        # folder that was already restored).
        skipped = _restore_moved_aside(self.moved_aside)
        if skipped:
            cleanly = False
        for fresh in list(self.remove_if_present):
            # NS-68: a lock folder this run created (none existed before it).
            if Path(fresh).exists():
                shutil.rmtree(fresh, ignore_errors=True)
                print(f"[cold-check] removed {fresh} (created by this run).")
            self.remove_if_present.remove(fresh)
        if BREADCRUMB_FIXED_PATH.exists() and self.moved_aside:
            self._write_breadcrumb()
        if self.scratch_root is not None and self.scratch_root.exists():
            shutil.rmtree(self.scratch_root, ignore_errors=True)
            print(f"[cold-check] removed {self.scratch_root}.")
        # PT-47: an instance rebuilt by --cleanup-only owns the breadcrumb it
        # was read from even when that breadcrumb names no scratch_root.
        if self.scratch_root is not None or getattr(self, "_from_breadcrumb", False):
            # NS-25: a breadcrumb was written (setup_scratch() writes one
            # before anything else it does) - clear it only once cleanup
            # actually finished cleanly, so a real leftover (the WARNING
            # branch above) still leaves a trail for --cleanup-only or a
            # human to find and finish.
            if cleanly:
                BREADCRUMB_FIXED_PATH.unlink(missing_ok=True)
                print(f"[cold-check] breadcrumb cleared ({BREADCRUMB_FIXED_PATH}) - "
                      "machine confirmed back to baseline.")
            else:
                print(f"[cold-check] breadcrumb LEFT IN PLACE ({BREADCRUMB_FIXED_PATH}) - "
                      "resolve the warning above, then re-run with --cleanup-only.")
        # NS-26: release the concurrency lock unconditionally - a no-op if
        # this process never held it (e.g. _acquire_lock() itself raised
        # before a check was even constructed, so cleanup() was never
        # reached for it) since _release_lock() only ever removes a lock
        # file naming THIS process's own pid.
        _release_lock()
        self._cleaned_up = True


def _cleanup_only_command():
    """The recovery command, spelled for the host that prints it."""
    if os.name == "nt":
        return "py -3 scripts\\cold_machine_check.py --cleanup-only"
    return "python3 scripts/cold_machine_check.py --cleanup-only"


def _restore_moved_aside(moved_aside):
    """PT-47: restores every {original: backup} entry in place, in order.
    Backup present -> the fresh folder (if any) is removed and the backup
    moved back; the entry is dropped. Backup MISSING -> nothing is deleted
    or moved, the entry stays in `moved_aside` (still pending) and a
    Reason / Fix / Run is printed. Returns the list of skipped originals."""
    skipped = []
    for original, backup in list(moved_aside.items()):
        original, backup = Path(original), Path(backup)
        if not backup.exists():
            skipped.append(str(original))
            print(f"[cold-check] SKIPPED {original}: its backup is missing - nothing deleted.")
            print(f"  Reason: the backup {backup} named in the breadcrumb does not exist, so "
                  f"{original} is left exactly as it is (it may already be your real folder).")
            print(f"  Fix: check {original}; if it is your real environment, delete the "
                  f"breadcrumb {BREADCRUMB_FIXED_PATH}; otherwise recreate the environment "
                  "with setup.")
            print(f"  Run: {_setup_recreate_command()}")
            continue
        if original.exists():  # the fresh one this run's setup created
            shutil.rmtree(original)
        backup.rename(original)
        print(f"[cold-check] restored {original}.")
        del moved_aside[str(original)]
    return skipped


def _setup_recreate_command():
    if os.name == "nt":
        return "setup.bat"
    return "python3 scripts/setup.py"


def _lock_dirs():
    """NS-68: the two lock folders a cold run's builds write into."""
    return [DF_LOCKS_DIR, ROOT_LOCKS_DIR]


def _moved_aside_dirs():
    """Every real folder a run moves aside and restores (never deleted)."""
    return [DF_VENV_DIR, REPLAY_VENV_DIR, *_lock_dirs()]


def lock_dir_listing(path):
    """NS-68: {file name: sha256} of a lock folder, {} when it is absent."""
    import hashlib
    path = Path(path)
    if not path.is_dir():
        return {}
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(path.iterdir()) if p.is_file()}


def dir_fingerprint(root):
    """PT-26: {files, listing_sha256, pyvenv_cfg_sha256, probe, probe_sha256}
    for a venv -- every relative path with its size (hashed as one
    listing), plus the content hash of pyvenv.cfg and of one site-packages
    file (the first, sorted). Symlinks are listed, never followed."""
    import hashlib
    root = Path(root)
    entries = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            path = Path(dirpath) / name
            try:
                size = path.lstat().st_size
            except OSError:
                size = -1
            entries.append(f"{path.relative_to(root).as_posix()}\t{size}")

    def sha(path):
        try:
            return hashlib.sha256(Path(path).read_bytes()).hexdigest()
        except OSError:
            return None
    site = sorted(p for p in root.glob("**/site-packages/*/*.py"))
    probe = site[0] if site else None
    return {"files": len(entries),
            "listing_sha256": hashlib.sha256("\n".join(entries).encode()).hexdigest(),
            "pyvenv_cfg_sha256": sha(root / "pyvenv.cfg"),
            "probe": probe.relative_to(root).as_posix() if probe else None,
            "probe_sha256": sha(probe) if probe else None}


def _load_breadcrumb():
    """NS-25: returns the parsed breadcrumb dict, or None if there isn't
    one - the normal case (no interrupted run pending)."""
    if not BREADCRUMB_FIXED_PATH.exists():
        return None
    return json.loads(BREADCRUMB_FIXED_PATH.read_text(encoding="utf-8"))


def _check_from_breadcrumb(data):
    """NS-25: rebuilds enough of a ColdMachineCheck for cleanup() to
    finish the job, from a breadcrumb written by a DIFFERENT (dead)
    process - team_server_original_bytes in particular can only come from
    team_server_backup_file on disk here, never from memory."""
    check = ColdMachineCheck(with_server=data.get("with_server", False))
    check.scratch_root = Path(data["scratch_root"]) if data.get("scratch_root") else None
    check.server_data_dir = Path(data["server_data_dir"]) if data.get("server_data_dir") else None
    check.port = data.get("port")
    backup_file = data.get("team_server_backup_file")
    if backup_file and Path(backup_file).exists():
        check.team_server_backup_file = Path(backup_file)
        check.team_server_original_bytes = check.team_server_backup_file.read_bytes()
    check.moved_aside = dict(data.get("moved_aside") or {})
    if data.get("venv_moved_aside") and data.get("venv_backup_path"):
        # a breadcrumb written before PT-26 (single-venv shape)
        check.moved_aside[data.get("venv_dir") or str(DF_VENV_DIR)] = data["venv_backup_path"]
    check.replay_fingerprint = data.get("replay_fingerprint")
    check.remove_if_present = list(data.get("remove_if_present") or [])
    check.locks_before = dict(data.get("locks_before") or {})
    check._from_breadcrumb = True
    return check


def assert_machine_clean(check):
    """NS-25: every run - a normal one via run(), or a resumed one via
    --cleanup-only - ends by ASSERTING the machine is actually back, not
    just trusting that cleanup() ran without raising. Prints what it
    verified either way and returns False if anything still looks wrong,
    so the caller can report a non-zero exit instead of a false PASS."""
    print("\n[cold-check] === post-cleanup assertions (NS-25) ===")
    all_clean = True

    team_server_path = adas_setup.TEAM_SERVER_FILE
    diff = subprocess.run(["git", "diff", "--quiet", "--", str(team_server_path)],
                          cwd=str(ROOT))
    if diff.returncode == 0:
        print(f"  OK    {team_server_path} matches git HEAD (no leftover edit).")
    else:
        all_clean = False
        print(f"  FAIL  {team_server_path} still differs from git HEAD.")

    if DF_VENV_DIR.exists():
        print(f"  OK    {DF_VENV_DIR} is present.")
    else:
        all_clean = False
        print(f"  FAIL  {DF_VENV_DIR} is MISSING.")

    for path in _moved_aside_dirs():
        backup = path.with_name(path.name + ".cold_check_bak")
        if backup.exists():
            all_clean = False
            print(f"  FAIL  leftover backup still present: {backup}")

    # PT-26: the developer's replay venv is back, byte-identical by listing,
    # sizes and two content hashes taken before the run.
    before = getattr(check, "replay_fingerprint", None)
    if before is not None:
        after = dir_fingerprint(REPLAY_VENV_DIR) if REPLAY_VENV_DIR.exists() else None
        if after == before:
            print(f"  OK    {REPLAY_VENV_DIR} is back and identical "
                  f"({before['files']} files, pyvenv.cfg + {before['probe']} hashes match).")
        else:
            all_clean = False
            print(f"  FAIL  {REPLAY_VENV_DIR} is {'MISSING' if after is None else 'different'} "
                  f"after cleanup (before: {before['files']} files).")

    # NS-68: the developer's own locks are back exactly as they were - and a
    # folder that did not exist before the run does not exist now.
    for folder, before in sorted((getattr(check, "locks_before", None) or {}).items()):
        after = lock_dir_listing(folder)
        if after == before:
            print(f"  OK    {folder} is back as it was ({len(before)} lock file(s)).")
        else:
            all_clean = False
            print(f"  FAIL  {folder} differs after cleanup (before: {sorted(before)}, "
                  f"after: {sorted(after)}).")
    for fresh in getattr(check, "remove_if_present", None) or []:
        if Path(fresh).exists():
            all_clean = False
            print(f"  FAIL  {fresh} was created by this run and is still there.")

    port = getattr(check, "port", None)
    if port is not None:
        if adas_setup._port_reachable(port):
            all_clean = False
            print(f"  FAIL  127.0.0.1:{port} is still LISTENING.")
        else:
            print(f"  OK    127.0.0.1:{port} is not listening.")

    scratch_root = getattr(check, "scratch_root", None)
    if scratch_root is not None:
        if Path(scratch_root).exists():
            all_clean = False
            print(f"  FAIL  scratch dir still present: {scratch_root}")
        else:
            print(f"  OK    scratch dir gone: {scratch_root}")

    if BREADCRUMB_FIXED_PATH.exists():
        all_clean = False
        print(f"  FAIL  breadcrumb still present: {BREADCRUMB_FIXED_PATH}")
    else:
        print(f"  OK    no breadcrumb pending ({BREADCRUMB_FIXED_PATH}).")

    # NS-26: the concurrency lock must be released by the time a run ends -
    # cleanup() calls _release_lock() unconditionally, so a lock file still
    # present here means either this process's own release somehow didn't
    # run, or (more likely, if this is ever seen live) a genuinely
    # different concurrent run is holding it - either way, worth failing
    # loudly rather than reporting a false PASS.
    if LOCK_FIXED_PATH.exists():
        all_clean = False
        print(f"  FAIL  concurrency lock still present: {LOCK_FIXED_PATH}")
    else:
        print(f"  OK    no concurrency lock pending ({LOCK_FIXED_PATH}).")

    print(f"[cold-check] assertions: {'ALL PASS' if all_clean else 'FAILED - see above'}")
    return all_clean


def _current_commit_sha():
    """`git rev-parse HEAD` at ROOT - None (never a guessed/empty sha) if
    that fails for any reason (e.g. run from a source archive with no
    .git)."""
    proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                          capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def record_passing_run(mode, steps, total_seconds=None):
    """NS-44 (RQ-8): write/update this run's entry in the TRACKED
    COLD_RUN_RECORD_PATH - commit sha, UTC timestamp, mode, and each
    step's name/ok - called only when the whole run (every step plus the
    post-cleanup assertions) passed. Both modes keep their own entry, so a
    `--with-server` PASS never overwrites a `no-server` PASS or vice
    versa - check_invariants.check_cold1() reads whichever entries are
    present and is satisfied by either. Never raises: a record-writing
    failure (e.g. a read-only checkout) is reported, not fatal - the real
    proof already happened, and failing to WRITE the receipt after the
    fact must not turn a real PASS into a reported FAIL."""
    sha = _current_commit_sha()
    if sha is None:
        print(f"[cold-check] NS-44: could not determine this checkout's commit sha - "
              f"{COLD_RUN_RECORD_PATH} not updated.")
        return
    try:
        existing = json.loads(COLD_RUN_RECORD_PATH.read_text(encoding="utf-8"))
        if not isinstance(existing, dict):
            existing = {}
    except (OSError, ValueError):
        existing = {}
    # R-TEST-7: seconds are optional per step and per mode -- every reader
    # (COLD-1 included) must keep accepting records written without them.
    def _entry(step):
        entry = {"name": step.name, "ok": step.ok}
        if getattr(step, "seconds", None) is not None:
            entry["seconds"] = round(step.seconds, 1)
        return entry

    existing[mode] = {
        "commit": sha,
        "timestamp_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": mode,
        "steps": [_entry(step) for step in steps],
    }
    if total_seconds is not None:
        existing[mode]["total_seconds"] = round(total_seconds, 1)
    try:
        COLD_RUN_RECORD_PATH.write_text(
            json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"[cold-check] NS-44: could not write {COLD_RUN_RECORD_PATH}: {exc}")
        return
    print(f"[cold-check] NS-44: recorded this PASS ({mode}, {sha[:8]}) in "
          f"{COLD_RUN_RECORD_PATH.relative_to(ROOT)}.")


def _clear_stale_lock():
    """NS-26: `--cleanup-only` is the explicit, human-invoked recovery tool
    for a run that died before its own `cleanup()` (and therefore its own
    `_release_lock()`) ever ran - unlike a live `run()`, which only ever
    removes a lock file naming its OWN pid, this removes ANY lock file it
    finds, whatever pid it names (a live run never reaches this function
    at all; only a dead one's stale lock could still be sitting here).
    Returns True iff a lock file was actually found and removed, purely
    for _cleanup_only_impl()'s own reporting."""
    if not LOCK_FIXED_PATH.exists():
        return False
    try:
        data = json.loads(LOCK_FIXED_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    print(f"[cold-check] found a concurrency lock (NS-26) from pid {data.get('pid')} - "
          "clearing it (--cleanup-only is the recovery tool for exactly this).")
    LOCK_FIXED_PATH.unlink(missing_ok=True)
    return True


def _cleanup_only_impl():
    """NS-25: the actual --cleanup-only body, split out from run_cleanup_
    only() purely so tests can exercise it without also faking os.name -
    Path() dispatches WindowsPath/PosixPath off the REAL os.name at
    construction time, so mocking os.name to "nt" to satisfy the OS guard
    below breaks every Path(...) call that follows it on a non-Windows
    test runner. The OS guard itself has nothing to do with the restore
    logic this function tests."""
    # NS-26: cleared unconditionally, before the breadcrumb check below -
    # a run can die in the narrow window after _acquire_lock() succeeds
    # but before setup_scratch() writes its first breadcrumb, leaving a
    # lock with no breadcrumb at all.
    lock_cleared = _clear_stale_lock()

    data = _load_breadcrumb()
    if data is None:
        if lock_cleared:
            print(f"[cold-check] no breadcrumb at {BREADCRUMB_FIXED_PATH} - nothing else "
                  "to finish, machine is now clean.")
        else:
            print(f"[cold-check] no breadcrumb at {BREADCRUMB_FIXED_PATH} - "
                  "nothing to finish, machine is already clean.")
        return 0

    print(f"[cold-check] found breadcrumb from pid {data.get('pid')} "
          f"(with_server={data.get('with_server')}): {data}")
    check = _check_from_breadcrumb(data)
    check.cleanup()
    return 0 if assert_machine_clean(check) else 1


def run_cleanup_only():
    """NS-25: finishes a cleanup an earlier run never got to run at all
    (killed hard enough that neither `finally` nor atexit nor the signal
    handlers fired - e.g. SIGKILL, a crashed machine, `taskkill /F` from
    outside this process). Reads BREADCRUMB_FIXED_PATH, rebuilds just
    enough state to undo every mutation it names, and asserts the machine
    is back - same assertion every normal run() also performs."""
    if os.name != "nt":
        print("cold_machine_check.py is Windows-only - nothing to clean up on this OS.")
        return 1
    return _cleanup_only_impl()


def _run_step(step, cmd, cwd, env, forbidden=(), required=()):
    """`forbidden` (NS-46): text that must not appear in the output even when
    the command exits 0 - a non-fatal contact with the planted dead remote
    is still a remotes-off build talking to a remote. `required` (NS-68): text
    that must appear - an exit code cannot tell a build that used its lock from
    one that quietly resolved again."""
    print(f"\n[cold-check] === {step.name} ===")
    print(f"[cold-check] $ {' '.join(cmd)}")
    started = time.monotonic()
    proc = subprocess.run(cmd, cwd=str(cwd), env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    step.seconds = time.monotonic() - started
    sys.stdout.write(proc.stdout)
    sys.stdout.write(proc.stderr)
    step.ok = (proc.returncode == 0)
    if not step.ok:
        combined = (proc.stderr or proc.stdout or "").strip().splitlines()
        step.first_error = combined[0] if combined else f"exit {proc.returncode}, no output"
    else:
        text = (proc.stdout or "") + (proc.stderr or "")
        hits = [f for f in forbidden if f in text]
        absent = [r for r in required if r not in text]
        if hits:
            step.ok = False
            step.first_error = f"exit 0, but the output contains {hits!r}"
        elif absent:
            step.ok = False
            step.first_error = f"exit 0, but the output lacks {absent!r}"
    return step.ok


def _run_step_expect_refusal(step, cmd, cwd, env, marker, forbidden=()):
    """NS-22 (cache_first_no_server_plan.md, redo of CE-35): like
    _run_step(), but SUCCESS for this particular step means the command
    REFUSED for the expected reason (`marker` found in its combined
    output) - a wrongly-succeeding build is exactly as much a FAIL here
    as a build that failed for some unrelated reason. Used for NS-22(a)'s
    own planted-violation proof: the stray editable planted just before
    this step must make the real aggregate build refuse, by name, not
    merely happen to fail.

    NS-56: `marker` may be a tuple (every one must appear), and `forbidden`
    names text that must NOT appear - a refusal for the right reason but
    signposted by a raw traceback is the RV-1 defect, not a pass."""
    markers = (marker,) if isinstance(marker, str) else tuple(marker)
    print(f"\n[cold-check] === {step.name} ===")
    print(f"[cold-check] $ {' '.join(cmd)}")
    started = time.monotonic()
    proc = subprocess.run(cmd, cwd=str(cwd), env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    step.seconds = time.monotonic() - started
    sys.stdout.write(proc.stdout)
    sys.stdout.write(proc.stderr)
    combined = proc.stdout + proc.stderr
    if proc.returncode == 0:
        step.ok = False
        step.first_error = ("expected a refusal (nonzero exit) but the build "
                             "succeeded - the planted condition was silently accepted")
    elif any(m not in combined for m in markers):
        step.ok = False
        lines = combined.strip().splitlines()
        missing = [m for m in markers if m not in combined]
        step.first_error = (f"failed, but not with the expected marker(s) {missing!r} "
                             f"({lines[-1] if lines else 'no output'})")
    elif any(f in combined for f in forbidden):
        step.ok = False
        step.first_error = (f"refused, but its output contains "
                            f"{[f for f in forbidden if f in combined]!r}")
    else:
        step.ok = True
    return step.ok


def _prove_locks(made_step, reused_step, refused_step, solo_cmd, env, dead):
    """NS-68 (cache_first_no_server_plan.md WP-13): three checks that follow the
    solo build, all on df's own lock (a root solo build delegates to the
    component launcher, so the lock is modules/df/conan_workarea/locks/...).

    1. the lock exists and pins adas-interfaces;
    2. a second build prints `--lockfile <that lock>` in its conan install, never
       `--lockfile-partial` / `--lockfile-out` / "lock created", and leaves the
       lock's bytes untouched;
    3. PLANTED: the lock's THIRD-PARTY protobuf pin is edited to a revision no cache
       holds; the build must refuse with Reason / Fix / Run naming
       `--update-lock`, run no `conan install`, and the lock is put back
       byte-for-byte afterwards (in a finally)."""
    lock = DF_LOCKS_DIR / DF_LOCK_NAME
    print(f"\n[cold-check] === {made_step.name} ===")
    try:
        text = lock.read_text(encoding="utf-8")
        pinned = "adas-interfaces/1.0.0#" in text
    except OSError as exc:
        text, pinned = "", False
        made_step.first_error = f"{lock} cannot be read ({exc})"
    made_step.ok = pinned
    if not pinned and not made_step.first_error:
        made_step.first_error = f"{lock} exists but does not pin adas-interfaces/1.0.0"
    print(f"[cold-check] {lock}: {'pins adas-interfaces/1.0.0' if pinned else made_step.first_error}")
    if not made_step.ok:
        return
    before = lock.read_bytes()
    if _run_step(reused_step, solo_cmd, ROOT, env,
                 forbidden=(*dead, "--lockfile-partial", "--lockfile-out", "lock created:"),
                 required=("--lockfile ", DF_LOCK_NAME, "lock: using")):
        if lock.read_bytes() != before:
            reused_step.ok = False
            reused_step.first_error = "the second build rewrote the lock (LK-D3: a build never does)"
    if not reused_step.ok:
        return
    import re
    # R-BUILD-7 (LK-D10): a FIRST-PARTY pin (adas-*) with a newer revision in the cache is
    # refreshed, never refused, so planting adas-interfaces would now succeed. A
    # THIRD-PARTY pin keeps the strict behaviour (a pinned revision missing from the
    # cache is refused, LK-D6) -- that is what this step proves, on protobuf.
    planted, count = re.subn(r'(protobuf/[0-9.]+#)[0-9a-f]{32}', r'\g<1>' + "0" * 32,
                             before.decode("utf-8"))
    if not count:
        refused_step.ok = False
        refused_step.first_error = f"{lock} has no third-party protobuf pin to plant"
        return
    # Remotes off: the lock gate refuses with Reason / Fix / Run before any `conan install`.
    # Remotes on: a third-party revision may still be fetched by its pinned revision, so the
    # gate leaves it to Conan, which fails naming the revision (R-BUILD-7, LK-D6).
    remotes_on = "--remotes" in solo_cmd and solo_cmd[solo_cmd.index("--remotes") + 1] == "on"
    if remotes_on:
        marker, forbidden = ("not resolved", "0" * 32), (*dead, "Traceback")
    else:
        marker, forbidden = ("Reason:", "Fix:", "Run:", "--update-lock"), (*dead, "Traceback", "conan install")
    try:
        lock.write_bytes(planted.encode("utf-8"))
        _run_step_expect_refusal(refused_step, solo_cmd, ROOT, env, marker=marker, forbidden=forbidden)
    finally:
        lock.write_bytes(before)


def _plant_stray_editable(scratch_root, env):
    """NS-22 (cache_first_no_server_plan.md, redo of CE-35): plants a
    stray Conan editable registration pointing at a FAKE 'different
    checkout' - faithfully reproducing the real corporate-PC incident
    this closes (a second, stale D:\\df\\1v-superproject checkout's
    mathlib registered editable in a D:\\1v-superproject machine's own
    CONAN_HOME, so viz compiled against old sim headers with no error at
    all). A full copy of this checkout's own real modules/mathlib
    (conanfile.py, CMakeLists.txt, source - a genuinely buildable recipe,
    not a stub) under a deliberately different path, then a real `conan
    editable add` against the SCRATCH CONAN_HOME (`env["CONAN_HOME"]`)
    only - so the aggregate build's own real `conan install` resolves
    adas-mathlib as Editable for real, exactly like the incident, never a
    mocked stand-in. Raises RuntimeError (never silently continues) if
    the registration itself fails."""
    fake_mathlib = Path(scratch_root) / "fake_other_checkout" / "modules" / "mathlib"
    shutil.copytree(
        ROOT / "modules" / "mathlib", fake_mathlib,
        ignore=shutil.ignore_patterns("conan_workarea", ".venv-*", "build-*", ".git"))
    proc = subprocess.run(["conan", "editable", "add", "."], cwd=str(fake_mathlib),
                          env=env, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(
            "conan editable add failed for the planted stray editable "
            f"(exit {proc.returncode}): {proc.stderr.strip() or proc.stdout.strip()}")
    print(f"[cold-check] planted stray editable: adas-mathlib -> {fake_mathlib} "
          "(NS-22's own real-incident shape - a full second checkout, not this one).")
    return fake_mathlib


def _plant_dead_remote(env):
    """NS-46 (cache_first_no_server_plan.md, RQ-5): a scratch CONAN_HOME has
    no remote registered, so it cannot show what a machine WITH history
    shows - an adas-local still registered and enabled from an earlier
    session, pointing at a server that is gone. Registers exactly that
    (`adas-local` -> a loopback port nothing listens on, enabled) in the
    scratch home only. Every remotes-off build step after this must be
    unaffected by it; before NS-46 the component build's own `conan
    install` consulted it and died on "actively refused". Raises
    RuntimeError (never silently continues) if the registration fails."""
    url = f"http://127.0.0.1:{_free_port()}"
    for cmd in (["conan", "remote", "add", "adas-local", url, "--force"],
                ["conan", "remote", "enable", "adas-local"]):
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)
        if proc.returncode != 0:
            raise RuntimeError(f"{' '.join(cmd)} failed (exit {proc.returncode}): "
                               f"{proc.stderr.strip() or proc.stdout.strip()}")
    print(f"[cold-check] planted a registered-but-dead remote: adas-local -> {url} "
          "(enabled; NS-46 - remotes-off builds must never consult it).")
    return url


# PT-12 (python_tool_envs_plan.md WP-8): the Python tool environment half of
# the cold proof. The recording is df's own committed BSD curve pass-by.
REPLAY_RECORDING = "bsd/bsd_curve_r172_passby.mcap"


def _replay_venv():
    return REPLAY_VENV_DIR


def _replay_python():
    return _replay_venv() / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def solo_df_library(solo_cmd):
    """The df_sil library `solo_cmd` (a root `build.py df -t T -p P -P X`)
    produces, named by df's own lookup (modules/df/tools/carla/dll_lookup.py,
    the one permitted copy of the build-folder naming, DLL-1) -- never a
    second copy of that naming here."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_cold_dll_lookup", ROOT / "modules" / "df" / "tools" / "carla" / "dll_lookup.py")
    lookup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lookup)
    opt = {flag: solo_cmd[solo_cmd.index(flag) + 1] for flag in ("-t", "-p", "-P")}
    return lookup.root_candidates(ROOT, opt["-t"], opt["-p"], opt["-P"])[0]


def _plant_absent_python_component(scratch_root):
    """PT-12 planted violation: a throwaway component (scratch only, never in
    the checkout) declaring an environment on a Python version no machine
    has. Its setup must refuse by Reason / Fix / Run, never try to install."""
    comp = Path(scratch_root) / "planted_component"
    (comp / "conf").mkdir(parents=True, exist_ok=True)
    (comp / "conf" / "build.yml").write_text(
        "variants: {}\n"
        "python_envs:\n"
        "  tool:\n"
        "    python: \"3.99\"\n"
        "    intent: requirements.txt\n"
        "    lock: requirements.lock\n"
        "    default: true\n", encoding="utf-8")
    (comp / "requirements.txt").write_text("mcap\n", encoding="utf-8")
    (comp / "requirements.lock").write_text("mcap==1.5.0\n", encoding="utf-8")
    return comp


def run(with_server=False):
    if os.name != "nt":
        print("cold_machine_check.py is Windows-only (setup.bat, vs2026/MSVC, "
              "conan_server.exe) - nothing to run on this OS.")
        return 1

    run_started = time.monotonic()

    # NS-26 (cache_first_no_server_plan.md, TASK 3): refuse a second
    # concurrent run BEFORE creating any scratch state, naming the owning
    # pid + scratch root instead of racing ahead into "it worked the
    # second time" confusion. `--cleanup-only` deliberately never reaches
    # here (see run_cleanup_only()) - it is the tool for clearing a stale
    # lock left by a run that died without its own cleanup() ever running.
    try:
        _acquire_lock()
    except ColdCheckLocked as exc:
        print(f"[cold-check] ERROR (NS-26): {exc}")
        print(f"[cold-check] refusing to start a second concurrent cold-machine check. "
              f"If that run is gone (crashed, killed, or you're sure it's stale), run "
              "`python scripts\\cold_machine_check.py --cleanup-only` first (it removes "
              f"a stale lock unconditionally), or delete {LOCK_FIXED_PATH} by hand.")
        return 1

    check = ColdMachineCheck(with_server=with_server)
    # NS-21/D1a (cache_first_no_server_plan.md): explicit on every command,
    # never left to team_conan_server.txt's own content - in --with-server
    # mode that file is pointed at THIS run's own scratch server, a
    # loopback URL, which NS-24 alone would read as remotes OFF.
    remotes_flag = ["--remotes", "on" if with_server else "off"]
    mode_label = "with-server" if with_server else "no-server (default, D6)"
    # WP-5/NS-09 (cache_first_no_server_plan.md, TASK 2): the fresh-machine
    # flow is now THREE commands, not two - setup.bat never compiles
    # anything (D4b), and `misc/offline_bundle/` never carries the
    # compiled first-party C++ libraries (D3/RQ-6). `--prepare df` builds
    # exactly the closure STEP 5's real run found MISSING (df's own
    # requires: - interfaces, mathlib, shared_config, viz - and viz's own
    # transitive requires: on sim - forward_closure() walks both, see
    # scripts/build.py::forward_closure()) into the scratch cache before
    # build.py ever runs.
    prepare_cmd = [sys.executable, "scripts/setup.py", "--prepare", "df", "-t", "sil",
                   "-p", "vs2026", "-P", "base", *remotes_flag]
    solo_cmd = [sys.executable, "scripts/build.py", "df", "-t", "sil",
                "-p", "vs2026", "-P", "base", *remotes_flag]
    agg_cmd = [sys.executable, "scripts/build.py", "df", "-t", "sil",
               "-p", "vs2026", "-P", "base", "--with", "viz", *remotes_flag]
    # NS-55 (RV-7): --with-all appeared nowhere in this check, which is why
    # the named-data-module defect (and RV-1 after it) reached a user.
    with_all_cmd = [sys.executable, "scripts/build.py", "df", "-t", "sil",
                    "-p", "vs2026", "-P", "base", "--with-all", *remotes_flag]
    # NS-56: RV-1 itself, planted. --with-all against a CONAN_HOME with no
    # adas-toolchain recipe must refuse by setup's name, never by a raw
    # "Cannot resolve python_requires" from the shared_config create.
    no_pin_step = Step("build.py df -t sil -p vs2026 -P base --with-all "
                       "(NS-56 refusal expected: no adas-toolchain pin in the cache)")
    absent_py_step = Step("planted env on Python 3.99 (PT-12 refusal expected: Reason / Fix / Run)")
    env_import_step = Step("df:replay env created by setup imports mcap_protobuf (PT-12)")
    replay_step = Step(f"df:replay env replays {REPLAY_RECORDING} headless (PT-12)")
    setup_step = Step(f"setup.bat [{mode_label}]")
    prepare_step = Step("setup.py --prepare df -t sil -p vs2026 -P base")
    solo_step = Step("build.py df -t sil -p vs2026 -P base")
    # NS-68 (WP-13): the build above pinned its revisions in a lock; prove it
    # exists, that the next build uses it strictly, and that a lock naming a
    # revision the cache does not hold is refused, not replaced.
    lock_made_step = Step(COLD1_LOCK_MADE_STEP)
    lock_reused_step = Step(COLD1_LOCK_REUSED_STEP)
    lock_refused_step = Step(COLD1_LOCK_REFUSED_STEP)
    refusal_step = Step("build.py df -t sil -p vs2026 -P base --with viz "
                        "(NS-22 refusal expected: a stray editable is planted first)")
    cleanup_step = Step("setup.py --clean-develop-leftovers --yes (NS-22 cleanup)")
    retry_step = Step("build.py df -t sil -p vs2026 -P base --with viz (retry, after cleanup)")
    with_all_step = Step(WITH_ALL_STEP_NAME)
    steps = [no_pin_step,
             absent_py_step,
             setup_step,
             env_import_step,
             prepare_step,
             solo_step,
             lock_made_step,
             lock_reused_step,
             lock_refused_step,
             replay_step,
             refusal_step,
             cleanup_step,
             retry_step,
             with_all_step]

    def _signal_cleanup(signum, frame):
        print(f"\n[cold-check] interrupted (signal {signum}) - cleaning up before exit.")
        check.cleanup()
        sys.exit(130)

    signal.signal(signal.SIGINT, _signal_cleanup)
    signal.signal(signal.SIGTERM, _signal_cleanup)
    # NS-25: belt-and-suspenders alongside the signal handlers above and
    # the `finally` below - cleanup() is idempotent (see its own guard),
    # so atexit firing after either of those already ran is a no-op, not
    # a double-cleanup. Covers exit paths neither of the other two catch
    # (e.g. a bare `sys.exit()`/`os._exit()` reached from somewhere deep
    # in a called module without unwinding through this function's own
    # `finally`).
    atexit.register(check.cleanup)

    try:
        check.setup_scratch()
        env = check.subprocess_env()
        _run_step_expect_refusal(
            no_pin_step, with_all_cmd, ROOT,
            dict(env, CONAN_HOME=str(check.make_no_toolchain_home())),
            marker=("adas-toolchain/", "setup.bat"),
            forbidden=("Cannot resolve python_requires",))
        # Absolute path, not a bare "setup.bat" - found live running this
        # tool's own PROOF requirement (CE-30..CE-32, conan_environment_
        # plan.md, 2026-09-23): a bare command name relies on cmd.exe's
        # own "search the current directory first" behavior, which some
        # hardened machines disable (NoDefaultCurrentDirectoryInExePath=1,
        # a real security policy - confirmed set on this machine)
        # regardless of `cwd=` being correctly passed to subprocess.run().
        # An absolute path needs no such search at all.
        # PT-12 planted: an environment on a Python this machine lacks is
        # refused by its component's setup, with a runnable Run: line.
        planted = _plant_absent_python_component(check.scratch_root)
        _run_step_expect_refusal(
            absent_py_step,
            [sys.executable, "-m", "adas_build_tools.setup_cli", "--python-envs-only"],
            planted, dict(env, PYTHONPATH=str(ROOT / "modules" / "toolchain")),
            marker=("Reason:", "Python 3.99", "Fix:", "Run:    winget install"),
            forbidden=("Traceback",))
        # PT-12: prove setup CREATES df's replay env on this empty home, not
        # that one happened to be left over (gitignored; setup rebuilds it
        # from the lock, D6).
        # PT-26: the real replay venv was moved aside in setup_scratch(), so
        # setup must create a fresh one here; cleanup() moves the real one back.
        if not _run_step(setup_step, [str(ROOT / "setup.bat"), *remotes_flag], ROOT, env):
            pass  # still attempt the build steps below? No - a failed setup
            # means resolution never completed; the build steps would just
            # repeat the same failure with a less specific message. Stop here.
        elif not _run_step(env_import_step,
                           [str(_replay_python()), "-c",
                            "import mcap_protobuf; print('mcap_protobuf', mcap_protobuf.__file__)"],
                           ROOT, env):
            pass  # the tool environment setup just claimed to create is unusable
        elif not _run_step(prepare_step, prepare_cmd, ROOT, env):
            pass  # WP-5/NS-09 (TASK 2): setup.bat passed but df's own
            # first-party dependency closure never made it into the cache -
            # every build step below would just repeat the identical
            # missing-ref failure with a less specific message. Stop here,
            # same reasoning as the setup.bat guard above.
        else:
            dead = ()
            if not with_server:
                # NS-46: from here on, every build step runs with a dead
                # adas-local registered and enabled, and its URL appearing in
                # any step's output fails that step - fatal or not. Remotes-on
                # mode is exempt: there a remote is supposed to be consulted.
                try:
                    dead = (_plant_dead_remote(env),)
                except RuntimeError as exc:
                    print(f"[cold-check] ERROR planting the dead remote: {exc}")
                    solo_step.ok = False
                    solo_step.first_error = f"NS-46 planting failed: {exc}"
            if solo_step.ok is None:
                _run_step(solo_step, solo_cmd, ROOT, env, forbidden=dead)
            if solo_step.ok:
                _prove_locks(lock_made_step, lock_reused_step, lock_refused_step,
                             solo_cmd, env, dead)
            if solo_step.ok:
                # PT-12: the env's own interpreter replays against the df_sil
                # the solo build just produced; headless (no --step/--viz).
                # That build is a ROOT build, and df's lookup (PT-40) uses a
                # root build only when its project is named -- without it
                # this replayed whatever stale COMPONENT build of df happened
                # to be on disk, and failed once none was; naming the project
                # alone then refused as ambiguous once an earlier run's -agg
                # build of the same project was on disk (both found
                # 2026-09-29). So name the exact library: the solo build's,
                # by df's own lookup naming (dll_lookup.py, DLL-1).
                _run_step(replay_step,
                          [str(_replay_python()), "df_dll_sim_mcap.py", REPLAY_RECORDING,
                           "--dll-path", str(solo_df_library(solo_cmd))],
                          ROOT / "modules" / "df" / "tools" / "carla" / "replay", env,
                          forbidden=dead)

            # NS-22 (cache_first_no_server_plan.md, redo of CE-35): plant a
            # stray editable pointing at a FAKE other checkout, prove the
            # aggregate build refuses it BY NAME (refusal_step), clean it up
            # for real via the documented command (cleanup_step), then prove
            # the SAME build now proceeds (retry_step) - exercised in BOTH
            # modes, since NS-22(a)'s refusal and NS-22(b)'s cleanup are
            # both remotes-independent (D:\1v-superproject's own real
            # incident had nothing to do with whether a server was
            # configured).
            try:
                _plant_stray_editable(check.scratch_root, env)
            except RuntimeError as exc:
                print(f"[cold-check] ERROR planting stray editable: {exc}")
                refusal_step.ok = False
                refusal_step.first_error = str(exc)
            else:
                _run_step_expect_refusal(refusal_step, agg_cmd, ROOT, env, marker="(CE-35)",
                                         forbidden=dead)
                if refusal_step.ok:
                    if _run_step(cleanup_step,
                                 [sys.executable, "scripts/setup.py",
                                  "--clean-develop-leftovers", "--yes"],
                                 ROOT, env):
                        if _run_step(retry_step, agg_cmd, ROOT, env, forbidden=dead):
                            # NS-55: every dependency in-tree, shared_config
                            # packaged from the checkout (A).
                            _run_step(with_all_step, with_all_cmd, ROOT, env,
                                      forbidden=dead)
    finally:
        check.cleanup()

    print("\n[cold-check] === summary ===")
    all_ok = True
    for step in steps:
        if step.ok is None:
            print(f"  SKIPPED  {step.name}  (an earlier step failed)")
            continue
        status = "PASS" if step.ok else "FAIL"
        line = f"  {status:8} {step.name}"
        if not step.ok:
            line += f"  -  {step.first_error}"
            all_ok = False
        print(line)

    # NS-25: every run ends by ASSERTING the machine is actually back,
    # not just trusting that cleanup() ran without raising an exception -
    # a build-step failure is reported above already; a cleanup failure
    # (the real incident this row closes) must ALSO fail the run, even if
    # every build step happened to pass.
    if not assert_machine_clean(check):
        all_ok = False

    # NS-44 (RQ-8): only a genuinely all-green run (every step AND the
    # post-cleanup assertions) is worth recording - a partial PASS with a
    # dirty machine left behind is not the proof RQ-8 asks for.
    if all_ok:
        record_passing_run("with-server" if with_server else "no-server", steps,
                           total_seconds=time.monotonic() - run_started)

    return 0 if all_ok else 1


if __name__ == "__main__":
    import argparse
    _parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    _parser.add_argument(
        "--with-server", action="store_true",
        help="D6/NS-21 (cache_first_no_server_plan.md): also exercise the "
             "remotes-ON path - a real scratch conan_server, NS-21/CE-34's "
             "server.conf self-heal, and CE-36's reachability gate. Default "
             "(no flag): the cache-first no-server model - no conan_server "
             "anywhere, remotes off, resolving from the Conan cache/"
             "misc/offline_bundle/ only.")
    _parser.add_argument(
        "--cleanup-only", action="store_true",
        help="NS-25 (cache_first_no_server_plan.md): finish a cleanup an "
             f"earlier run never got to run (breadcrumb at "
             f"{BREADCRUMB_FIXED_PATH}) - restores every mutation the "
             "breadcrumb names, then asserts the machine is back. Does not "
             "start a new check; ignores --with-server.")
    _args = _parser.parse_args()
    if _args.cleanup_only:
        sys.exit(run_cleanup_only())
    sys.exit(run(with_server=_args.with_server))
