# Copyright (c) LT EPS. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SUPERPROJECT
# @file python_baseline.py
# @brief Where a component's third-party Python baseline comes from (D19).
# @author Pavan Karimajji

"""python_tool_envs_plan.md D19 (PT-31/PT-33): the ONE place that answers
"which baseline applies to this component" and parses it -- used by
lock_python_env.py (narrowing) and check_invariants.py PYB-1 (the net).

A component uses the baseline inside the adas-build-tools version it PINS
(conf/build_tools.version), read from that version's wheel in the Conan
cache -- never from this checkout, so moving the pin is how a component
adopts a new baseline. toolchain cannot pin a released copy of itself (D8):
its envs use the baseline in its own source tree.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLCHAIN = "toolchain"
BASELINE_IN_PACKAGE = "adas_build_tools/python_baseline.txt"
SOURCE_BASELINE = Path("modules") / "toolchain" / "adas_build_tools" / "python_baseline.txt"
_LINE_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9.+!_-]*)$")


class BaselineMissing(Exception):
    def __init__(self, reason: str, fix: str, run: str):
        super().__init__(reason)
        self.reason, self.fix, self.run = reason, fix, run


def norm(name: str) -> str:
    """PEP 503 name normalisation."""
    return re.sub(r"[-_.]+", "-", name).lower()


def parse(text: str) -> dict[str, tuple[str, str]]:
    """{normalised name: (name as written, version)}; comments ignored."""
    out = {}
    for line in text.splitlines():
        m = _LINE_RE.match(line.strip())
        if m:
            out[norm(m.group(1))] = (m.group(1), m.group(2))
    return out


def toolchain_source_version(root: Path = ROOT) -> str | None:
    pyproject = root / "modules" / "toolchain" / "pyproject.toml"
    if not pyproject.is_file():
        return None
    m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else None


def pin_move_command(root: Path, component: str, version: str) -> str:
    """One command, runnable as printed on this host, that moves
    `component`'s adas-build-tools pin to `version`."""
    target = root / "modules" / component / "conf" / "build_tools.version"
    py = "py -3" if sys.platform == "win32" else "python3"
    return f"{py} -c \"open(r'{target}', 'w').write('{version}')\""


def _wheel_in_cache(ref: str) -> Path | None:
    try:
        proc = subprocess.run(["conan", "list", f"{ref}:*", "--format=json"],
                              capture_output=True, text=True, check=False)
    except FileNotFoundError:
        # A host where setup has not run yet (e.g. a fresh WSL) has no conan:
        # say so, rather than crash every caller or call the ref "not cached".
        raise BaselineMissing(f"conan is not on PATH on this host, so {ref}'s baseline cannot "
                              f"be read from the Conan cache.",
                              "run setup on this host (it installs conan), then re-run.",
                              "setup.bat" if sys.platform == "win32"
                              else "python3 scripts/setup.py")
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    ids = [pid for cache in data.values()
           for rev in cache.get(ref, {}).get("revisions", {}).values()
           for pid in rev.get("packages", {})]
    if not ids:
        return None
    path = subprocess.run(["conan", "cache", "path", f"{ref}:{ids[0]}"],
                          capture_output=True, text=True, check=False)
    if path.returncode != 0:
        return None
    wheels = sorted(Path(path.stdout.strip()).glob("adas_build_tools-*.whl"))
    return wheels[0] if wheels else None


def baseline_for(root: Path, component: str) -> tuple[dict[str, tuple[str, str]], str]:
    """(parsed baseline, where it came from) for `component`, or raises
    BaselineMissing with Reason / Fix / Run."""
    if component == TOOLCHAIN:
        src = root / SOURCE_BASELINE
        if not src.is_file():
            raise BaselineMissing(
                f"{SOURCE_BASELINE.as_posix()} does not exist (toolchain's envs use the "
                f"baseline in its own source tree, D8).",
                "generate it in the superproject.",
                f"{'py -3' if sys.platform == 'win32' else 'python3'} "
                f"{root / 'scripts' / 'make_python_baseline.py'}")
        return parse(src.read_text(encoding="utf-8")), SOURCE_BASELINE.as_posix()
    pin_file = root / "modules" / component / "conf" / "build_tools.version"
    pin = pin_file.read_text(encoding="utf-8").strip() if pin_file.is_file() else None
    if not pin:
        raise BaselineMissing(f"modules/{component}/conf/build_tools.version is missing or "
                              f"empty, so no adas-build-tools baseline applies.",
                              "pin the current adas-build-tools version.",
                              pin_move_command(root, component,
                                               toolchain_source_version(root) or "1.0.30"))
    if pin.startswith("v"):
        # R-BUILD-2: a `vX.Y.Z` pin installs from a git tag, and only a bare
        # X.Y.Z names a Conan package whose wheel carries the baseline.
        bare = pin.lstrip("v")
        raise BaselineMissing(
            f"{component} pins adas-build-tools by git tag ({pin}); its baseline is read from "
            f"the Conan package adas-build-tools/{bare}, which a tag pin does not name.",
            f"move {component}'s pin to the bare version {bare}.",
            pin_move_command(root, component, bare))
    ref = f"adas-build-tools/{pin}"
    wheel = _wheel_in_cache(ref)
    if wheel is None:
        raise BaselineMissing(f"{ref} (pinned by {component}) is not in the local Conan cache, "
                              f"so its baseline cannot be read.",
                              "put the pinned package in the cache (setup does, from the bundle "
                              "or the server).",
                              f'"{root / "setup.bat"}"' if sys.platform == "win32"
                              else f'python3 "{root / "scripts" / "setup.py"}"')
    with zipfile.ZipFile(wheel) as zf:
        if BASELINE_IN_PACKAGE not in zf.namelist():
            latest = toolchain_source_version(root) or pin
            raise BaselineMissing(
                f"{ref} (pinned by {component}) ships no python_baseline.txt -- it predates "
                f"the shared baseline (D19, adas-build-tools 1.0.30+).",
                f"move {component}'s pin to {latest}.",
                pin_move_command(root, component, latest))
        text = zf.read(BASELINE_IN_PACKAGE).decode("utf-8")
    return parse(text), f"{ref} ({wheel.name})"
