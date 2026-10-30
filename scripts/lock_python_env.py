# Copyright (c) LT EPS. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SUPERPROJECT
# @file lock_python_env.py
# @brief Generate a Python tool environment's exact `==` lock (PT-03).
# @author Pavan Karimajji

"""python_tool_envs_plan.md D2 / PT-03 -- regenerate one declared Python
tool environment's lock file from its intent file.

    python scripts/lock_python_env.py <module> <env>

Reads `modules/<module>/conf/build.yml`'s `python_envs.<env>` through the
one parser (`adas_build_tools.config.declared_python_envs`, PT-01), builds a
throwaway venv on the declared interpreter (`py -3.N` on Windows,
`python3.N` elsewhere -- D4, never installed), installs the intent file
into it (`requirements*.txt` via `-r`, a `pyproject.toml` via its folder),
and writes every installed distribution as `name==version`, sorted, to the
declared `lock:` path. D19/PT-31: a non-exception env installs with the
component's baseline as pip constraints (`-c`, python_baseline.baseline_for:
the pinned adas-build-tools' baseline; toolchain's own source baseline), so
its lock is a subset of the baseline by construction. An `exception:` env
resolves on its own, as before. The project a `pyproject.toml` defines is not in its
own lock (`package:` installs it `--no-deps -e` on top, D1), nor are pip,
setuptools and wheel. The lock reflects the platform it was generated on:
generate it on the platform the tool runs on (Windows today).

This is a tool author's command (plan §4); it needs the network (PyPI) and
never runs during setup or a build (D10a). Every refusal is Reason / Fix /
Run (D11).
"""

from __future__ import annotations

import datetime
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import python_baseline  # noqa: E402
_EXCLUDED = {"pip", "setuptools", "wheel"}
_LOCK_LINE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*==[A-Za-z0-9][A-Za-z0-9.+!_-]*$")


class Refusal(Exception):
    def __init__(self, reason: str, fix: str, run: str):
        super().__init__(reason)
        self.reason, self.fix, self.run = reason, fix, run


def _self_cmd(module: str, env: str) -> str:
    launcher = "py -3" if sys.platform == "win32" else "python3"
    return f"{launcher} scripts{os.sep}lock_python_env.py {module} {env}"


def _load_envs(module: str, env: str) -> dict:
    tc = ROOT / "modules" / "toolchain"
    if not (tc / "adas_build_tools" / "config.py").is_file():
        raise Refusal("modules/toolchain is not checked out, and it holds the one "
                      "python_envs: parser (adas_build_tools.config).",
                      "check the toolchain submodule out, then re-run.",
                      "git submodule update --init modules/toolchain")
    sys.path.insert(0, str(tc))
    try:
        from adas_build_tools import config
    finally:
        sys.path.pop(0)
    build_yml = ROOT / "modules" / module / "conf" / "build.yml"
    if not build_yml.is_file():
        known = sorted(p.parent.parent.name for p in (ROOT / "modules").glob("*/conf/build.yml"))
        raise Refusal(f"modules/{module}/conf/build.yml does not exist -- '{module}' is not "
                      f"a checked-out component ({', '.join(known)}).",
                      "name a component that declares python_envs:.",
                      _self_cmd("df", "replay"))
    try:
        envs = config.declared_python_envs(config.load_conf(build_yml.parent.parent),
                                           component=module)
    except config.PythonEnvsError as exc:
        raise Refusal(str(exc), "correct the declaration in conf/build.yml, then re-run.",
                      _self_cmd(module, env)) from exc
    return envs


def find_interpreter(version: str) -> list[str]:
    """D4: the declared interpreter, checked by running it -- never installed."""
    cmd = ["py", f"-{version}"] if sys.platform == "win32" else [f"python{version}"]
    try:
        proc = subprocess.run(cmd + ["-c", "import sys, venv; print(sys.version)"],
                              capture_output=True, text=True, check=False)
        ok = proc.returncode == 0
    except OSError:
        ok = False
    if not ok:
        run = (f"winget install -e --id Python.Python.{version}" if sys.platform == "win32"
               else f"sudo apt install python{version} python{version}-venv")
        raise Refusal(f"Python {version} is not installed on this machine "
                      f"(`{' '.join(cmd)}` does not run).",
                      "install it (this script never installs an interpreter), then re-run.",
                      run)
    return cmd


def _venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def build_lock(module: str, env: str, today: datetime.date | None = None) -> tuple[Path, list[str]]:
    envs = _load_envs(module, env)
    if env not in envs:
        first = next(iter(envs), None)
        raise Refusal(f"{module} declares no python env '{env}' "
                      f"(declared: {', '.join(envs) or 'none'}).",
                      "name a declared env.",
                      _self_cmd(module, first) if first else _self_cmd("df", "replay"))
    decl = envs[env]
    comp = ROOT / "modules" / module
    intent = comp / decl["intent"]
    if not intent.is_file():
        raise Refusal(f"{module}:{env}'s intent file {intent.relative_to(ROOT)} does not exist.",
                      "create it or correct `intent:` in conf/build.yml, then re-run.",
                      _self_cmd(module, env))
    baseline_where = None
    constraints_text = None
    if not decl.get("exception"):
        try:
            baseline, baseline_where = python_baseline.baseline_for(ROOT, module)
        except python_baseline.BaselineMissing as exc:
            raise Refusal(exc.reason, exc.fix, exc.run) from exc
        constraints_text = "".join(f"{n}=={v}\n" for n, v in sorted(baseline.values()))
    interp = find_interpreter(decl["python"])

    with tempfile.TemporaryDirectory(prefix=f"lock-{module}-{env}-") as tmp:
        venv = Path(tmp) / "venv"
        made = subprocess.run(interp + ["-m", "venv", str(venv)], capture_output=True,
                              text=True, check=False)
        if made.returncode != 0:
            # `import venv` working (find_interpreter) does not mean `-m venv` can
            # create one: Debian's python3.N without python3.N-venv lacks ensurepip.
            detail = ((made.stderr or made.stdout).strip().splitlines() or ["no output"])[-1]
            raise Refusal(f"Python {decl['python']} is installed but cannot create a venv "
                          f"({detail}).",
                          "install its venv support (this script never installs an "
                          "interpreter), then re-run.",
                          f"winget install -e --id Python.Python.{decl['python']}"
                          if sys.platform == "win32"
                          else f"sudo apt install python{decl['python']}-venv")
        py = str(_venv_python(venv))
        project = None
        if intent.name == "pyproject.toml":
            project = subprocess.run(
                [py, "-c", "import sys, tomllib; print(tomllib.load(open(sys.argv[1], 'rb'))"
                           "['project']['name'])", str(intent)],
                capture_output=True, text=True, check=True).stdout.strip()
            target = [str(intent.parent)]
        else:
            target = ["-r", str(intent)]
        constrain = []
        if constraints_text is not None:
            cfile = Path(tmp) / "baseline-constraints.txt"
            cfile.write_text(constraints_text, encoding="utf-8")
            constrain = ["-c", str(cfile)]
        proc = subprocess.run([py, "-m", "pip", "install", "--disable-pip-version-check",
                               *constrain, *target], check=False)
        if proc.returncode != 0:
            raise Refusal(f"pip could not install {intent.relative_to(ROOT)} into a fresh "
                          f"Python {decl['python']} venv (exit {proc.returncode}, output above).",
                          "fix the intent file or the network (PyPI is required to lock), "
                          "then re-run.", _self_cmd(module, env))
        frozen = subprocess.run([py, "-m", "pip", "freeze", "--all",
                                 "--disable-pip-version-check"],
                                capture_output=True, text=True, check=True).stdout
    norm = lambda n: re.sub(r"[-_.]+", "-", n).lower()  # noqa: E731 - PEP 503
    skip = _EXCLUDED | ({norm(project)} if project else set())
    lines = []
    for line in frozen.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name = re.split(r"[=<>@ ]", line, maxsplit=1)[0]
        if norm(name) in skip:
            continue
        if not _LOCK_LINE_RE.match(line):
            raise Refusal(f"`pip freeze` produced `{line}`, which is not an exact "
                          f"name==version pin (a URL or editable requirement in the intent).",
                          f"make every entry in {intent.relative_to(ROOT)} a PyPI requirement, "
                          f"then re-run.", _self_cmd(module, env))
        lines.append(line)
    lines.sort(key=str.lower)

    today = today or datetime.date.today()
    lock = comp / decl["lock"]
    header = [
        "# LOCK -- generated, never hand-edited (python_tool_envs_plan.md D2).",
        f"# env:    {module}:{env}",
        f"# source: {decl['intent']}",
        f"# python: {decl['python']} ({sys.platform})",
        (f"# baseline: {baseline_where}" if baseline_where
         else f"# baseline: none -- exception: {decl['exception']}"),
        f"# date:   {today.isoformat()}",
        f"# regenerate: python scripts/lock_python_env.py {module} {env}",
    ]
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("\n".join(header + lines) + "\n", encoding="utf-8", newline="\n")
    return lock, lines


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("Reason: lock_python_env.py takes exactly two arguments, <module> <env>.")
        print("Fix:    name the component and one env from its conf/build.yml python_envs:.")
        print(f"Run:    {_self_cmd('df', 'replay')}")
        return 2
    try:
        lock, lines = build_lock(*argv)
    except Refusal as exc:
        print(f"Reason: {exc.reason}")
        print(f"Fix:    {exc.fix}")
        print(f"Run:    {exc.run}")
        return 1
    print(f"[OK] {lock.relative_to(ROOT)}: {len(lines)} packages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
