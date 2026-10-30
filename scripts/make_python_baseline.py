# Copyright (c) LT EPS. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SUPERPROJECT
# @file make_python_baseline.py
# @brief Generate the one third-party Python baseline (D19, PT-31).
# @author Pavan Karimajji

"""python_tool_envs_plan.md D19 / PT-31 -- generate the baseline of
third-party Python versions shipped inside adas-build-tools.

    py -3 scripts/make_python_baseline.py          (Windows)
    python3 scripts/make_python_baseline.py        (Linux)

Superproject only: it is the one place that sees every component's intent
files. Collects every NON-exception python_envs: entry across the
checked-out components (the discover_components() predicate), installs ALL
their intent files in ONE pip resolve into a scratch venv on the platform
Python (bundle_layout.PLATFORM_PYTHON, D18), and writes `pip freeze`
(minus pip/setuptools/wheel and the components' own projects), sorted, to
modules/toolchain/adas_build_tools/python_baseline.txt. If the one resolve
is impossible, it finds the two environments that conflict, names them and
the package, and writes nothing (D19: one of them must become an
`exception:`). Needs PyPI; never runs during setup or a build.
"""

from __future__ import annotations

import datetime
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import python_baseline  # noqa: E402

OUT_REL = python_baseline.SOURCE_BASELINE
_EXCLUDED = {"pip", "setuptools", "wheel"}
DATE_PREFIX = "# date:"


class Refusal(Exception):
    def __init__(self, reason: str, fix: str, run: str):
        super().__init__(reason)
        self.reason, self.fix, self.run = reason, fix, run


@dataclass(frozen=True)
class Intent:
    env: str            # "<component>:<env>"
    path: Path          # the intent file
    project: str | None  # the pyproject's own project name, never in the baseline

    def pip_args(self) -> list[str]:
        return [str(self.path.parent)] if self.path.name == "pyproject.toml" else ["-r", str(self.path)]


def self_cmd(root: Path = ROOT) -> str:
    py = "py -3" if sys.platform == "win32" else "python3"
    return f"{py} \"{root / 'scripts' / 'make_python_baseline.py'}\""


def _toolchain(root: Path):
    tc = root / "modules" / "toolchain"
    if not (tc / "adas_build_tools" / "config.py").is_file():
        raise Refusal("modules/toolchain is not checked out; it holds the python_envs: parser "
                      "and the platform Python (D18).", "check it out, then re-run.",
                      "git submodule update --init modules/toolchain")
    sys.path.insert(0, str(tc))
    try:
        from adas_build_tools import bundle_layout, config
    finally:
        sys.path.pop(0)
    return config, bundle_layout


def collect_intents(root: Path = ROOT) -> list[Intent]:
    """Every non-exception env's intent file, in component/env order."""
    config, _ = _toolchain(root)
    mdir = root / "modules"
    comps = sorted(d.name for d in mdir.iterdir()
                   if (d / "conanfile.py").exists() and (d / "conf" / "build.yml").exists())
    intents = []
    for comp in comps:
        envs = config.declared_python_envs(config.load_conf(mdir / comp), component=comp)
        for env, decl in envs.items():
            if decl.get("exception"):
                continue
            path = mdir / comp / decl["intent"]
            project = None
            if path.name == "pyproject.toml":
                m = re.search(r'^name\s*=\s*"([^"]+)"', path.read_text(encoding="utf-8"), re.M)
                project = m.group(1) if m else None
            intents.append(Intent(f"{comp}:{env}", path, project))
    return intents


def conflicting_package(pip_output: str) -> str | None:
    """The package pip's ResolutionImpossible report is about."""
    names = re.findall(r"(?:user requested|depends on)\s+\(?([A-Za-z0-9][A-Za-z0-9._-]*)",
                       pip_output)
    if not names:
        m = re.search(r"Cannot install .*? and ([A-Za-z0-9][A-Za-z0-9._-]*)", pip_output)
        return m.group(1) if m else None
    counts: dict[str, int] = {}
    for n in names:
        counts[python_baseline.norm(n)] = counts.get(python_baseline.norm(n), 0) + 1
    return max(counts, key=lambda k: (counts[k], k))


PipRun = Callable[[list[str]], "subprocess.CompletedProcess[str]"]


def find_conflict(intents: list[Intent], pip: PipRun) -> tuple[Intent, Intent, str | None] | None:
    """The first pair of intents that cannot be resolved together
    (`pip install --dry-run`, resolution only), with the package."""
    for i, a in enumerate(intents):
        for b in intents[i + 1:]:
            proc = pip(["install", "--dry-run", "--ignore-installed", "--disable-pip-version-check",
                        *a.pip_args(), *b.pip_args()])
            if proc.returncode != 0:
                return a, b, conflicting_package(proc.stdout + proc.stderr)
    return None


def render(frozen: str, intents: list[Intent], *, commit: str, platform: str, python: str,
           today: datetime.date) -> str:
    skip = _EXCLUDED | {python_baseline.norm(i.project) for i in intents if i.project}
    lines = []
    for line in frozen.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name = re.split(r"[=<>@ ]", line, maxsplit=1)[0]
        if python_baseline.norm(name) in skip:
            continue
        if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*==\S+$", line):
            raise Refusal(f"`pip freeze` produced `{line}`, not an exact name==version pin.",
                          "make every intent entry a PyPI requirement, then re-run.",
                          self_cmd())
        lines.append(line)
    lines.sort(key=str.lower)
    header = [
        "# BASELINE -- generated, never hand-edited (python_tool_envs_plan.md D19).",
        "# Every non-exception python_envs: lock is narrowed from this file",
        "# (scripts/lock_python_env.py) and checked against it (PYB-1).",
        f"# source commit: {commit}",
        f"# platform: {platform} (one baseline for every platform while the locks agree;",
        "#           if a package ever needs different versions per OS, split it per platform)",
        f"# python: {python}",
        f"# envs: {', '.join(i.env for i in intents)}",
        f"{DATE_PREFIX}   {today.isoformat()}",
        f"# regenerate: python scripts/make_python_baseline.py",
    ]
    return "\n".join(header + lines) + "\n"


def generate(root: Path = ROOT, *, pip_factory=None, today: datetime.date | None = None,
             commit: str | None = None) -> tuple[Path, int]:
    config, bundle_layout = _toolchain(root)
    platform = bundle_layout.host_bundle_platform()
    python = bundle_layout.platform_python(platform)
    intents = collect_intents(root)
    if not intents:
        raise Refusal("no non-exception python_envs: entry is declared anywhere.",
                      "declare an env, then re-run.", self_cmd(root))
    commit = commit or subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(root),
                                      capture_output=True, text=True).stdout.strip()
    with tempfile.TemporaryDirectory(prefix="python-baseline-") as tmp:
        pip = pip_factory(Path(tmp), python) if pip_factory else _venv_pip(Path(tmp), python)
        args = ["install", "--disable-pip-version-check"]
        for intent in intents:
            args += intent.pip_args()
        proc = pip(args)
        if proc.returncode != 0:
            text = proc.stdout + proc.stderr
            if "ResolutionImpossible" in text or "conflict" in text.lower():
                pair = find_conflict(intents, pip)
                if pair:
                    a, b, pkg = pair
                    raise Refusal(
                        f"{a.env} and {b.env} cannot share one version of "
                        f"{pkg or 'a package (see pip output above)'} -- the baseline needs one "
                        f"version for every environment (D19). Nothing was written.",
                        f"declare one of them an exception, e.g. add `exception:` with its "
                        f"reason under python_envs.{b.env.split(':', 1)[1]} in "
                        f"modules/{b.env.split(':', 1)[0]}/conf/build.yml, then re-run.",
                        self_cmd(root))
            raise Refusal(f"pip could not install every intent file in one resolve "
                          f"(exit {proc.returncode}, output above). Nothing was written.",
                          "fix the intent files or the network (PyPI is required), then re-run.",
                          self_cmd(root))
        frozen = pip(["freeze", "--exclude-editable", "--disable-pip-version-check"]).stdout
    text = render(frozen, intents, commit=commit, platform=platform, python=python,
                  today=today or datetime.date.today())
    out = root / OUT_REL
    out.write_text(text, encoding="utf-8", newline="\n")
    return out, sum(1 for line in text.splitlines() if line and not line.startswith("#"))


def _venv_pip(tmp: Path, python: str) -> PipRun:
    interp = ["py", f"-{python}"] if sys.platform == "win32" else [f"python{python}"]
    venv = tmp / "venv"
    if subprocess.run(interp + ["-m", "venv", str(venv)], check=False).returncode != 0:
        raise Refusal(f"Python {python} (the platform Python, D18) cannot create a venv here.",
                      "install it (this script never installs an interpreter), then re-run.",
                      f"winget install -e --id Python.Python.{python}" if sys.platform == "win32"
                      else f"sudo apt install python{python} python{python}-venv")
    py = str(venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python"))

    def pip(args: list[str]) -> subprocess.CompletedProcess:
        proc = subprocess.run([py, "-m", "pip", *args], capture_output=True, text=True, check=False)
        if args[0] == "install":
            sys.stdout.write(proc.stdout[-4000:])
            sys.stderr.write(proc.stderr[-4000:])
        return proc
    return pip


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        print("Reason: make_python_baseline.py takes no arguments.")
        print("Fix:    run it bare, from anywhere.")
        print(f"Run:    {self_cmd()}")
        return 2
    try:
        out, count = generate()
    except Refusal as exc:
        print(f"Reason: {exc.reason}")
        print(f"Fix:    {exc.fix}")
        print(f"Run:    {exc.run}")
        return 1
    print(f"[OK] {out.relative_to(ROOT)}: {count} packages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
