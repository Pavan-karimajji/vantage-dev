#!/usr/bin/env python3
# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# @author Pavan Karimajji

"""The guided way to make an offline bundle: `python scripts/make_offline_bundle.py`
with no options.

It explains what a bundle is, checks every prerequisite (each failure comes
with the exact command that fixes it), lets the user pick the platform, shows
the exact command it will run, and runs it only after a yes. There is one
suitcase now: every declared Python tool box is default
(python_tool_envs_plan.md D26), so there is nothing left to choose between.

Nothing here decides WHAT goes into a bundle: the box list comes from
`derive_tool_envs()` / `declared_python_envs()` (D4: derived, never typed).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import make_offline_bundle as mob

PLATFORM_PURPOSE = {
    "vs2026": "Windows PCs (Visual Studio 2026 builds).",
    "ubuntu_gcc": "Linux PCs and WSL (gcc builds).",
}

MIN_FREE_BYTES = 2 * 1024 ** 3  # a vs2026 bundle with every box is ~160 MB; leave room for pip/conan temp


@dataclass
class Check:
    """One prerequisite: `ok`, a one-line `detail`, and the command(s) that fix it."""
    name: str
    ok: bool
    detail: str
    fix: list = field(default_factory=list)
    needed: bool = True  # False: shown as a warning, never blocks


# --------------------------------------------------------------------------- checks

def _run(cmd, runner):
    try:
        return runner(cmd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(cmd, 127, "", str(exc))


def check_python():
    ok = sys.version_info >= (3, 10)
    return Check("Python 3.10 or newer", ok, f"this is {sys.version.split()[0]} ({sys.executable})",
                 [] if ok else (["winget install -e --id Python.Python.3.12"] if sys.platform == "win32"
                                else ["sudo apt install python3.12"]))


def check_pip(runner=subprocess.run):
    proc = _run([sys.executable, "-m", "pip", "--version"], runner)
    ok = proc.returncode == 0
    return Check("pip", ok, proc.stdout.strip().split(" from ")[0] if ok else "pip is not available",
                 [] if ok else [f'"{sys.executable}" -m ensurepip --upgrade'])


def check_pyyaml():
    try:
        import yaml  # noqa: F401
        return Check("PyYAML (reads conf/build.yml)", True, "installed")
    except ImportError:
        return Check("PyYAML (reads conf/build.yml)", False, "not installed",
                     [f'"{sys.executable}" -m pip install pyyaml'])


def check_conan(runner=subprocess.run):
    proc = _run(["conan", "--version"], runner)
    ok = proc.returncode == 0 and "version 2." in proc.stdout.lower()
    detail = proc.stdout.strip() if proc.returncode == 0 else "the `conan` command was not found"
    if proc.returncode == 0 and not ok:
        detail += " -- Conan 2 is required"
    return Check("Conan 2", ok, detail, [] if ok else [f'"{sys.executable}" -m pip install "conan>=2,<3"'])


def check_toolchain_checkout(root=mob.ROOT):
    ok = (Path(root) / "modules" / "toolchain" / "adas_build_tools" / "config.py").is_file()
    return Check("modules/toolchain checked out", ok,
                 "present" if ok else "the toolchain submodule is empty",
                 [] if ok else [f'cd "{root}" && git submodule update --init modules/toolchain'])


def check_internet(opener=urllib.request.urlopen):
    try:
        opener("https://pypi.org/simple/pip/", timeout=8)
        return Check("Internet (pypi.org)", True, "reachable")
    except Exception as exc:  # noqa: BLE001 -- any failure means "not reachable", shown verbatim
        return Check("Internet (pypi.org)", False, f"not reachable ({exc.__class__.__name__}: {exc})",
                     ["connect this PC to the internet (a bundle is made where the internet is)",
                      "behind a proxy: set HTTPS_PROXY=http://<proxy>:<port> in this terminal, then re-run"])


def check_disk(out_dir, usage=shutil.disk_usage):
    probe = Path(out_dir)
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    free = usage(str(probe)).free
    ok = free >= MIN_FREE_BYTES
    return Check("Free disk space", ok, f"{free / 1024 ** 3:.1f} GB free at {probe}",
                 [] if ok else ["free some space, or choose another folder with --out <folder>"])


def check_host(platform):
    refusal = mob.wrong_host_refusal(platform)
    if not refusal:
        return Check("Right PC for this platform", True, f"this PC makes {platform} bundles")
    run = [line.split(":", 1)[1].strip() for line in refusal if line.startswith("Run:")]
    return Check("Right PC for this platform", False, refusal[0].split(":", 1)[1].strip(),
                 run or [refusal[1].split(":", 1)[1].strip()])


def check_machinery(pins):
    refusal = mob.machinery_transfer_refusal(pins)
    if not refusal:
        return Check("Build machinery in this PC's Conan cache", True, "present (or made from this checkout)")
    runs = [line.split(":", 1)[1].strip() for line in refusal if line.startswith("Run")]
    return Check("Build machinery in this PC's Conan cache", False, refusal[0].split(":", 1)[1].strip(),
                 runs or [refusal[1].split(":", 1)[1].strip()])


def existing_bundle(out_dir, platform):
    """(path, MB, date) of a bundle already in the target folder, else None."""
    folder = Path(out_dir) / platform
    tgz = sorted(folder.glob("adas_offline_*.tgz"))
    if not tgz:
        return None
    size = sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())
    return folder, size / 1024 ** 2, tgz[-1].stem.rsplit("_", 1)[-1]


def preflight(platform, out_dir, *, runner=subprocess.run,
              opener=urllib.request.urlopen, usage=shutil.disk_usage, pins_fn=None):
    """Every check, in the order a user would fix them. The host check comes before the
    ones that need conan, so a wrong-PC run is answered first."""
    checks = [check_python(), check_pip(runner), check_pyyaml(), check_toolchain_checkout(),
              check_host(platform)]
    if not checks[-1].ok:
        return checks
    checks += [check_conan(runner), check_internet(opener), check_disk(out_dir, usage)]
    if all(c.ok for c in checks) and sys.platform == "linux":
        checks.append(check_machinery((pins_fn or mob.derive_pins)()))
    return checks


# --------------------------------------------------------------------------- the box list

def box_list(root=mob.ROOT, envs_fn=None):
    """[(label, note)] for every env this bundle carries -- every declared
    env (D26: every box is default), noting the external it needs (e.g.
    'also needs carla installed on the PC that unpacks it')."""
    import yaml
    sys.path.insert(0, str(Path(root) / "modules" / "toolchain"))
    try:
        from adas_build_tools.config import declared_python_envs
    finally:
        sys.path.pop(0)
    from setup import discover_components
    notes = {}
    for comp in discover_components():
        conf = yaml.safe_load((Path(root) / "modules" / comp / "conf" / "build.yml").read_text(encoding="utf-8")) or {}
        for env, decl in declared_python_envs(conf, component=comp).items():
            ext = [e["name"] for e in decl.get("external") or []]
            notes[f"{comp}:{env}"] = ("also needs " + ", ".join(ext) +
                                      " installed on the PC that unpacks it") if ext else ""
    envs_fn = envs_fn or mob.derive_tool_envs
    return [(e["label"], notes.get(e["label"], "")) for e in envs_fn()]


def command_for(platform, out=None):
    """The exact command a user can copy -- the same text for the guide and for CI."""
    cmd = ["python" if sys.platform == "win32" else "python3", "scripts/make_offline_bundle.py",
           "--platform", platform]
    if out:
        cmd += ["--out", str(out)]
    return " ".join(cmd)


# --------------------------------------------------------------------------- the guide

INTRO = """\
What is an offline bundle?
  A "suitcase" with everything setup.bat needs, so a PC WITHOUT internet can be set up.
  You make it once, here (this PC needs internet). Then you copy the folder to the other PC
  and there run setup with --offline. setup can only unpack what is inside the suitcase.
"""


def _ask(input_fn, prompt, choices, default, print_fn=print):
    """Ask until the answer is one of `choices` (or empty -> default). Returns the choice."""
    while True:
        ans = input_fn(prompt).strip().lower()
        if not ans:
            return default
        if ans in choices:
            return ans
        print_fn(f"  please type one of: {', '.join(choices)}")


def _show_checks(checks, print_fn):
    blocking = False
    for c in checks:
        mark = "OK " if c.ok else ("!! " if c.needed else "?? ")
        print_fn(f"  [{mark}] {c.name}: {c.detail}")
        if not c.ok:
            blocking = blocking or c.needed
            for line in c.fix:
                print_fn(f"         fix: {line}")
    return blocking


def guide(input_fn=input, print_fn=print, *, run_fn=None, out_dir=None, preflight_fn=preflight,
          box_list_fn=box_list, host_platform=None):
    """Interactive. Returns the process exit code. Never runs anything without a yes."""
    out_dir = Path(out_dir or (mob.ROOT / mob.DEFAULT_OUT))
    host = host_platform or mob._bundle_layout().host_bundle_platform()
    print_fn(INTRO)

    # 1. platform
    print_fn("Step 1 - which kind of PC will UNPACK this suitcase?")
    plats = list(PLATFORM_PURPOSE)
    for i, p in enumerate(plats, 1):
        here = "  <- this PC" if p == host else ""
        print_fn(f"  {i}) {p:<11} {PLATFORM_PURPOSE[p]}{here}")
    print_fn("  A suitcase is made on the same kind of PC it is for (a Linux suitcase builds Linux packages).")
    pick = _ask(input_fn, f"  choose 1-{len(plats)} [Enter = {plats.index(host) + 1}, this PC]: ",
                [str(i) for i in range(1, len(plats) + 1)], str(plats.index(host) + 1), print_fn)
    platform = plats[int(pick) - 1]

    # 2. checks
    print_fn("\nStep 2 - checking this PC")
    checks = preflight_fn(platform, out_dir)
    boxes = box_list_fn()
    if _show_checks(checks, print_fn):
        print_fn("\nNot ready: fix the items marked !! with the command under each, then run this again:")
        print_fn(f"  {command_for(platform)}")
        return 1

    # 3. summary + confirm
    cmd = command_for(platform)
    print_fn("\nStep 3 - summary")
    print_fn(f"  platform : {platform}  ({PLATFORM_PURPOSE[platform]})")
    print_fn(f"  boxes    : {len(boxes)} Python tool box(es) + the C++ packages")
    for label, note in boxes:
        print_fn(f"       - {label:<16} {note}")
    folder = bundle_folder(out_dir, platform)
    print_fn(f"  written to: {folder}")
    old = existing_bundle(out_dir, platform)
    if old:
        print_fn(f"  NOTE: a bundle from {old[2]} ({old[1]:.0f} MB) is already there; it will be REPLACED.")
    print_fn(f"  command  : {cmd}")
    print_fn("  (copy that command to run the same thing later without these questions)")
    if _ask(input_fn, "  Run it now? [y/N]: ", ["y", "n", "yes", "no"], "n", print_fn) not in ("y", "yes"):
        print_fn("Nothing was run.")
        return 0

    code = (run_fn or _run_bundle)(platform, out_dir)
    if code == 0:
        print_fn("\nDone. Next, on the PC without internet:")
        print_fn(f"  1. copy the folder {folder} (keep its last part: "
                 f"{folder.relative_to(out_dir)})")
        print_fn(f"  2. run:  {unpack_command(platform)}")
    else:
        print_fn("\nThe bundle failed. The lines above say why (Reason / Fix / Run).")
        print_fn("Fix that, then run exactly this again:")
        print_fn(f"  {cmd}")
    return code


def bundle_folder(out_dir, platform):
    """Where make_offline_bundle.py writes this suitcase (D14)."""
    return Path(out_dir) / platform


def unpack_command(platform):
    """What to type on the PC that unpacks the suitcase -- its own shell, not this one."""
    if platform == "vs2026":
        return f"setup.bat --offline <where you put it>\\{platform}"
    return f"python3 scripts/setup.py --offline <where you put it>/{platform}"


def _run_bundle(platform, out_dir):
    try:
        mob.make_bundle(platform, out_dir)
        return 0
    except SystemExit as exc:  # make_bundle reports its refusals through sys.exit(<message>)
        if exc.code not in (0, None):
            print(exc.code if isinstance(exc.code, str) else f"exit code {exc.code}")
            return 1
        return 0
    except subprocess.CalledProcessError as exc:
        print(f"Reason: `{' '.join(map(str, exc.cmd))}` failed with exit code {exc.returncode}.")
        print("Fix:    read the output just above; most often the internet/proxy, or a Conan remote.")
        print("Run:    conan remote list    (a remote must be enabled to fetch third-party packages)")
        return 1


def non_interactive_help(print_fn=print):
    """No options and no terminal to ask in: explain instead of erroring."""
    host = mob._bundle_layout().host_bundle_platform()
    print_fn(INTRO)
    print_fn("Run it in a terminal with no options for the guided version, or run it directly:")
    print_fn(f"  {command_for(host)}")
    return 2


def wants_guide(argv):
    return not argv


def is_interactive(stdin=None):
    stdin = stdin or sys.stdin
    try:
        return stdin.isatty() and os.environ.get("CI") is None
    except (AttributeError, ValueError):
        return False
