#!/usr/bin/env python3
# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# @author Pavan Karimajji

"""Offline bundle for corporate PCs (OF-03, offline_setup_plan.md).

Run on a machine that CAN reach the network (and has built the project once):

    python scripts/make_offline_bundle.py --platform vs2026 [--out <dir>] [--dry-run]
                                          [--include-optional]

D14 (python_tool_envs_plan.md): the bundle for platform X lives in
<dir>/X/ and a run writes and cleans ONLY that subfolder, so a Windows
(vs2026) and a WSL (ubuntu_gcc) bundle share one checkout without touching
each other. A platform is made on its own host (a Linux bundle compiles
gcc packages): the wrong host is refused before any conan/pip call, with
the exact command for the right one.

Writes into <dir> (default misc/offline_bundle/ as of RD-13,
remove_develop_mode_plan.md - `scripts/setup.py --offline` with no argument
looks there too, so the two tools agree on a default with no flag on either
side; was conan_workarea/offline_bundle/ before RD-13. Gitignored either
way - a bundle is data, never committed, D3):

    adas_offline_<platform>_<date>.tgz   `conan cache save` of exactly the refs below
    wheels/                              `pip download` of what setup.py installs
    wheels/cp<XY>/                       every DEFAULT Python tool env's locked wheels,
                                         for that env's Python and this platform
                                         (python_tool_envs_plan.md D9, PT-08)
    bundle_manifest.txt                  platform, date, source commit, every ref+revision

Every pin is DERIVED from the repo, never typed (D4): third-party refs from
each `modules/*/conf/build.yml` requires:/tool_requires: (everything not
`adas-*`) plus their transitive closure from a real Conan graph, the
`adas-toolchain` recipes from each `conanfile.py` python_requires, and the
`adas-build-tools` packages from each `conf/build_tools.version` bare pin. A
pin bump therefore shows up in the next bundle automatically.

Binaries are saved with their PACKAGE revisions (`ref#latest:*#latest`): a
list without them makes `conan cache save` silently drop the binaries (found
in OF-01), and only the packages matching the platform's pinned profile are
kept. `scripts/setup.py --offline <dir>` (OF-04) consumes the result and
shares parse_manifest()/missing_pins() below.
"""
import argparse
import datetime
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from conan_home_resolution import profile_args  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
# RD-13 (remove_develop_mode_plan.md, 2026-09-22): was conan_workarea/
# offline_bundle - moved so `scripts/setup.py --offline` (no argument) has
# a fixed default location to look in that isn't nested under a directory
# scripts/build.py also writes real build output into.
DEFAULT_OUT = Path("misc") / "offline_bundle"
# What scripts/setup.py pip-installs on a dev machine (check_or_install_conan,
# check_or_install_pyyaml, ensure_https_trust) - the wheels a corporate PC
# needs. "pip" itself is here too (setup_followup_prompt.md step 4):
# venv_util.create_venv() makes every tool-box venv WITHOUT pip, then
# bootstraps pip --no-compile from a wheel - the bundle's own flat wheels/
# (pure-Python, one for every cp<XY> folder) when remotes are off, never a
# network call.
WHEEL_REQUIREMENTS = ["conan>=2,<3", "pyyaml", "pip-system-certs", "pip"]
# PT-08: the pip platform tag a tool env's wheels are fetched for, per bundle
# platform. A bundle is made for one platform (setup accepts one per folder).
# PT-19 (D14): a Linux platform declares its target glibc and the pip tags are
# DERIVED from it -- pip matches --platform exactly, and a wheel published
# only as manylinux_2_28 (numpy 2.5.3) is invisible to manylinux2014 alone.
PY_PLATFORM_WHEELS = {"vs2026": {"tags": ["win_amd64"]},
                      "ubuntu_gcc": {"glibc": "2.35", "arch": "x86_64"}}


def wheel_platform_tags(platform):
    """Every pip --platform tag a wheel for `platform` may carry: Windows'
    declared tag, or manylinux2014 plus manylinux_2_17 .. manylinux_2_<glibc>
    for a Linux platform (manylinux2014 == glibc 2.17)."""
    spec = PY_PLATFORM_WHEELS[platform]
    if "tags" in spec:
        return list(spec["tags"])
    major, minor = (int(x) for x in spec["glibc"].split("."))
    arch = spec["arch"]
    return [f"manylinux2014_{arch}"] + [f"manylinux_{major}_{m}_{arch}"
                                         for m in range(17, minor + 1)]


def _bundle_layout():
    """adas_build_tools.bundle_layout (standard library only): the one host ->
    platform mapping (D14)."""
    tc = ROOT / "modules" / "toolchain"
    sys.path.insert(0, str(tc))
    try:
        from adas_build_tools import bundle_layout
    finally:
        sys.path.pop(0)
    return bundle_layout


def _is_wsl():
    try:
        return "microsoft" in Path("/proc/version").read_text(encoding="utf-8").lower()
    except OSError:
        return False


def bundle_command(platform, include_optional=False, host=None):
    """The exact command that makes `platform`'s bundle, as it runs from THIS
    host's shell (D11, PT-18): the plain command on the platform's own host;
    from Windows, the `wsl` command for a Linux bundle; from WSL, the Windows
    interpreter via interop for a vs2026 bundle; None on a plain Linux box,
    which cannot make a Windows bundle at all."""
    host = host or sys.platform
    flag = " --include-optional" if include_optional else ""
    own = _bundle_layout().HOST_BUNDLE_PLATFORM.get(host)
    if platform == own:
        py = "python" if host == "win32" else "python3"
        return f"{py} scripts/make_offline_bundle.py --platform {platform}{flag}"
    if host == "win32":
        # `bash -lc`, not a bare `-e python3`: `wsl -e` gets a non-login PATH
        # without ~/.local/bin, where a pip --user conan lives (found 2026-09-28).
        return (f'wsl --cd "{ROOT}" -e bash -lc "python3 scripts/make_offline_bundle.py '
                f'--platform {platform}{flag}"')
    if _is_wsl():
        return (f'cd "{ROOT}" && py.exe -3 scripts/make_offline_bundle.py '
                f'--platform {platform}{flag}')
    return None

_PYTHON_REQUIRES_RE = re.compile(r'python_requires\s*=\s*["\']([^"\']+)["\']')
_BARE_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
_REF_RE = re.compile(r"^[A-Za-z0-9_.+-]+/[A-Za-z0-9_.+-]+$")  # name/version, not `pkg::target`


# ---------------------------------------------------------------------------
# Pin derivation (D4) - pure, no conan
# ---------------------------------------------------------------------------


def _walk_requires(node, key, out):
    """Every string in any `<key>:` list anywhere inside a conf/build.yml."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key and isinstance(v, list):
                out.update(item for item in v if isinstance(item, str) and _REF_RE.match(item))
            else:
                _walk_requires(v, key, out)
    elif isinstance(node, list):
        for item in node:
            _walk_requires(item, key, out)


def derive_pins(root=ROOT):
    """OF-03 / D4: {"third_party": [...], "third_party_tool": [...],
    "toolchain": [...], "build_tools": [...]}, each a sorted list of bare
    `name/version` refs read from the repo under `root`."""
    import yaml
    third_party, tool, toolchain, build_tools = set(), set(), set(), set()
    for mod in sorted((Path(root) / "modules").glob("*/")):
        conanfile, conf = mod / "conanfile.py", mod / "conf"
        if conanfile.is_file():
            toolchain.update(_PYTHON_REQUIRES_RE.findall(conanfile.read_text(encoding="utf-8")))
        if (conf / "build_tools.version").is_file():
            pin = (conf / "build_tools.version").read_text(encoding="utf-8").strip()
            if _BARE_VERSION_RE.match(pin):  # a vX.Y.Z git tag installs via pip, not Conan
                build_tools.add(f"adas-build-tools/{pin}")
        if (conf / "build.yml").is_file():
            data = yaml.safe_load((conf / "build.yml").read_text(encoding="utf-8")) or {}
            direct, direct_tool = set(), set()
            _walk_requires(data, "requires", direct)
            _walk_requires(data, "tool_requires", direct_tool)
            third_party.update(r for r in direct if not r.startswith("adas-"))
            tool.update(r for r in direct_tool if not r.startswith("adas-"))
    return {"third_party": sorted(third_party), "third_party_tool": sorted(tool),
            "toolchain": sorted(toolchain), "build_tools": sorted(build_tools)}


def all_pin_refs(pins):
    """Every derived pin as one sorted bare-ref list."""
    return sorted(set(pins["third_party"]) | set(pins["third_party_tool"])
                  | set(pins["toolchain"]) | set(pins["build_tools"]))


def derive_tool_envs(root=ROOT, include_optional=False):
    """PT-08 / D9: every DEFAULT Python tool env of every discover_components()
    component, read through the one parser (adas_build_tools.config.
    declared_python_envs, PT-01) - derived, never typed (D4). Each item:
    {"label", "python", "lock" (Path), "lock_rel" (posix, from root),
    "build_requires" ([...] from the package's pyproject [build-system],
    only when `package:` is declared), "default"}. D15/PT-24: with
    `include_optional`, optional envs too."""
    import yaml
    tc = Path(root) / "modules" / "toolchain"
    sys.path.insert(0, str(tc))
    try:
        from adas_build_tools.config import declared_python_envs
    finally:
        sys.path.pop(0)
    from setup import discover_components  # scripts/setup.py (same folder)
    out = []
    for comp in discover_components():
        comp_dir = Path(root) / "modules" / comp
        conf = yaml.safe_load((comp_dir / "conf" / "build.yml").read_text(encoding="utf-8")) or {}
        for env, decl in declared_python_envs(conf, component=comp).items():
            if not decl["default"] and not include_optional:
                continue
            build_requires = []
            if decl["package"]:
                build_requires = _pyproject_build_requires(comp_dir / decl["package"] / "pyproject.toml")
            lock = comp_dir / decl["lock"]
            out.append({"label": f"{comp}:{env}", "python": decl["python"], "lock": lock,
                        "lock_rel": lock.relative_to(root).as_posix(),
                        "build_requires": build_requires, "default": decl["default"]})
    return out


def _pyproject_build_requires(pyproject):
    """[build-system] requires = [...] - what `pip install -e <package>`
    needs offline to build the editable (setuptools, wheel)."""
    if not pyproject.is_file():
        return []
    text = pyproject.read_text(encoding="utf-8")
    m = re.search(r"\[build-system\][^\[]*?requires\s*=\s*\[([^\]]*)\]", text, re.S)
    return re.findall(r'["\']([^"\']+)["\']', m.group(1)) if m else []


def lock_sha256(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def download_tool_wheels(envs, platform, wheels_root):
    """PT-08: `pip download --only-binary=:all: --python-version X.Y --platform
    <tag> --no-deps -r <lock>` per default env into wheels/cp<XY>/, plus the
    build backend of any `package:` env. Returns (wheel names relative to
    wheels/, build wheels). The build backend is resolved from ranges here,
    so each build wheel is returned as (label, "name==version", "cp<XY>/<file>")
    for the manifest's `build-wheel:` lines -- two bundles stay comparable,
    and the env's lock never carries them (they never enter the env)."""
    if platform not in PY_PLATFORM_WHEELS:
        sys.exit(f"ERROR: no pip platform tags for bundle platform {platform!r} "
                 f"(known: {', '.join(PY_PLATFORM_WHEELS)})")
    tag_args = [a for tag in wheel_platform_tags(platform) for a in ("--platform", tag)]
    import shutil
    build_wheels = []
    for old in Path(wheels_root).glob("cp*"):  # a wheel from an older lock must not linger
        if old.is_dir():
            shutil.rmtree(old)
    for env in envs:
        dest = Path(wheels_root) / f"cp{env['python'].replace('.', '')}"
        common = [sys.executable, "-m", "pip", "download", "--disable-pip-version-check",
                  "--only-binary=:all:", "--python-version", env["python"], *tag_args,
                  "-d", str(dest)]
        print(f"[bundle] {env['label']}: wheels for {env['lock_rel']} -> {dest.name}/", flush=True)
        subprocess.run([*common, "--no-deps", "-r", str(env["lock"])], check=True)
        if env["build_requires"]:
            with tempfile.TemporaryDirectory() as tmp:
                build = [*common[:-1], tmp]
                subprocess.run([*build, *env["build_requires"]], check=True)
                for whl in sorted(Path(tmp).glob("*.whl")):
                    name, version = whl.name.split("-")[:2]
                    build_wheels.append((env["label"], f"{name}=={version}",
                                         f"{dest.name}/{whl.name}"))
                    dest.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(whl, dest / whl.name)
    names = sorted(f"{d.name}/{w.name}" for d in Path(wheels_root).glob("cp*") if d.is_dir()
                   for w in d.glob("*.whl"))
    return names, build_wheels


# ---------------------------------------------------------------------------
# Package filtering + manifest - pure
# ---------------------------------------------------------------------------


def matching_packages(packages, profile_settings):
    """OF-03: the {package_id: data} entries whose settings match every key
    the platform's pinned profile does not CONTRADICT: a key the package
    declares must equal the profile's value, but a key the package omits is
    fine (a C library such as lz4 declares no compiler.cppstd). A settings-less
    package matches everywhere."""
    if profile_settings is None:
        return dict(packages)
    kept = {}
    for pid, data in packages.items():
        settings = (data.get("info") or {}).get("settings")
        if not settings or all(profile_settings.get(k, v) == v for k, v in settings.items()):
            kept[pid] = data
    return kept


def manifest_text(platform, date, commit, conan_version, saved, pins, wheels, locks=(),
                  build_wheels=(), optional_included=False):
    """bundle_manifest.txt: `key: value` header, `ref: <name/ver>#<rev> packages=<n>`
    per saved recipe, `pin: <bare ref>` per derived pin, `wheel: <file>` (a
    tool env wheel as `cp<XY>/<file>`), and PT-08's `lock: <m>:<env> <path>
    sha256=<hex>` per default env lock the wheels were fetched from, and
    `build-wheel: <m>:<env> <name>==<version> <cp<XY>/file>` per build-backend
    wheel a `package:` env's editable install needs (resolved, not locked)."""
    lines = [f"platform: {platform}", f"date: {date}", f"source_commit: {commit}",
             f"conan_version: {conan_version}",
             f"optional: {'included' if optional_included else 'not included'}"]
    lines += [f"ref: {ref}#{rev} packages={n}" for ref, rev, n in saved]
    lines += [f"pin: {ref}" for ref in all_pin_refs(pins)]
    lines += [f"wheel: {w}" for w in wheels]
    lines += [f"lock: {label} {rel} sha256={sha}" for label, rel, sha in locks]
    lines += [f"build-wheel: {label} {pin} {path}" for label, pin, path in build_wheels]
    return "\n".join(lines) + "\n"


def parse_manifest(text):
    """OF-03/OF-04: bundle_manifest.txt -> {"platform", "date", "source_commit",
    "refs": {bare ref: revision}, "pins": [bare ref], "wheels": [...]}."""
    out = {"platform": None, "date": None, "source_commit": None,
           "refs": {}, "pins": [], "wheels": [], "locks": {},
           "build_wheels": [], "optional_included": False}
    for line in text.splitlines():
        key, _, value = line.partition(": ")
        if key in ("platform", "date", "source_commit"):
            out[key] = value.strip()
        elif key == "ref":
            ref, _, rest = value.partition("#")
            out["refs"][ref] = rest.split()[0]
        elif key == "pin":
            out["pins"].append(value.strip())
        elif key == "wheel":
            out["wheels"].append(value.strip())
        elif key == "lock":
            parts = value.split()
            if len(parts) == 3 and parts[2].startswith("sha256="):
                out["locks"][parts[2][len("sha256="):]] = (parts[0], parts[1])
        elif key == "optional":
            out["optional_included"] = value.strip() == "included"
        elif key == "build-wheel":
            parts = value.split()
            if len(parts) == 3:
                out["build_wheels"].append(tuple(parts))
    return out


def missing_pins(manifest, pins):
    """OF-04: derived pins (this checkout) that the bundle's manifest does not
    contain as a saved ref - a bundle older than a pin bump."""
    return [ref for ref in all_pin_refs(pins) if ref not in manifest["refs"]]


# ---------------------------------------------------------------------------
# Orchestration - conan / pip / git subprocesses
# ---------------------------------------------------------------------------


def _conan(*args, check=True, cwd=None):
    proc = subprocess.run(["conan", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=cwd)
    if check and proc.returncode != 0:
        sys.exit(f"ERROR: conan {' '.join(args)} failed (exit {proc.returncode}):\n{proc.stderr[-800:]}")
    return proc


def _list_json(pattern):
    proc = _conan("list", pattern, "--format=json", check=False)
    try:
        return json.loads(proc.stdout).get("Local Cache", {}) if proc.returncode == 0 else {}
    except ValueError:
        return {}


def _have_in_cache(ref, with_packages):
    """True iff `ref` (and, with_packages, a package of it) is in the LOCAL
    Conan cache -- `conan list` only, never a remote."""
    listed = _list_json(f"{ref}#latest:*#latest" if with_packages else f"{ref}#latest")
    entry = listed.get(ref) if isinstance(listed, dict) else None
    if not isinstance(entry, dict) or "error" in entry:
        # A missing ref comes back as {"error": "..."} (or an error string),
        # not as an empty listing -- found planting PT-27's own violation.
        return False
    if with_packages:
        return any(isinstance(rv, dict) and rv.get("packages")
                   for rv in (entry.get("revisions") or {}).values())
    return bool(entry.get("revisions"))


def _fill_machinery_from_checkout():
    """The machinery pins (adas-toolchain recipe, adas-build-tools package)
    come from THIS checkout's modules/toolchain -- never from a remote (D2 of
    cache_first_no_server_plan.md). The one implementation is setup's own
    cache preparation (`conan export` / `conan create`, both `-nr`), so the
    bundle and setup can never disagree about how the machinery is made.
    Returns setup's StepFailed when it could not, else None.

    Until 2026-09-29 this downloaded from the `adas-local` server instead: on
    a fresh machine with no such remote it failed with a raw Conan error
    ("Remote 'adas-local' doesn't exist")."""
    import types
    import setup as adas_setup  # same folder
    ctx = types.SimpleNamespace(dry_run=False, build_missing_from_source=False)
    try:
        # A fresh Conan home has no default profile, and `conan create` of the
        # build-tools package needs one (found the same day) -- setup's own
        # step, the same one a plain setup.bat runs first.
        adas_setup.ensure_conan_profile(ctx)
        adas_setup.prepare_conan_cache(ctx)
    except adas_setup.StepFailed as exc:
        return exc
    return None


def _ensure_in_cache(ref, with_packages):
    """None when `ref` (and, for adas-build-tools, its package) is in the
    local cache, else the Reason / Fix / Run lines (D11). Never a download."""
    if _have_in_cache(ref, with_packages):
        return None
    setup_cmd = "python scripts/setup.py" if sys.platform == "win32" else "python3 scripts/setup.py"
    return [f"Reason: {ref} is not in this machine's Conan cache, and building it from this "
            f"checkout's modules/toolchain did not produce it (details above).",
            "Fix:    let setup prepare the build machinery and show why it failed, then re-run "
            "this bundle command.",
            f'Run:    cd {"/d " if sys.platform == "win32" else ""}"{ROOT}" && {setup_cmd}']


def _transitive_refs(pins, platform, work):
    """Third-party refs + their transitive closure, from a real install graph
    (also fills the cache, --build=missing)."""
    args = ["install"]
    for ref in pins["third_party"]:
        args += ["--requires", ref]
    for ref in pins["third_party_tool"]:
        args += ["--tool-requires", ref]
    graph = work / "graph.json"
    # cwd=work: `conan install` writes conanbuild/conanrun scripts into its cwd
    proc = _conan(*args, "--build=missing", *profile_args(platform), "--format=json", cwd=work)
    graph.write_text(proc.stdout, encoding="utf-8")
    listing = json.loads(_conan("list", f"--graph={graph}", "--graph-binaries=cache",
                                "--graph-recipes=cache", "--format=json").stdout)
    return sorted(ref for refs in listing.values() for ref in refs)


def _profile_settings(platform):
    import check_conan_resolution as ccr
    return ccr.pinned_profile_settings(platform)


def make_bundle(platform, out_dir, wheels_dir=True, include_optional=False):
    """D14: writes into <out_dir>/<platform>/ and cleans ONLY that subfolder
    (its old archives and wheels) -- another platform's subfolder beside it
    is never touched."""
    import shutil
    out_dir = Path(out_dir) / platform
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("adas_offline_*.tgz"):
        old.unlink()
    if wheels_dir and (out_dir / "wheels").is_dir():
        shutil.rmtree(out_dir / "wheels")
    date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    pins = derive_pins()
    settings = _profile_settings(platform)
    if settings is None:
        sys.exit(f"ERROR: no pinned profile for platform {platform!r}")

    # The machinery first: cheap, local, and the one step that needs no network,
    # so a problem there is reported before the long third-party resolve.
    wanted = [(ref, False) for ref in pins["toolchain"]] + \
             [(ref, True) for ref in pins["build_tools"]]
    if any(not _have_in_cache(ref, pk) for ref, pk in wanted):
        print("[bundle] build machinery not in the local cache - building it from this "
              "checkout's modules/toolchain (setup's cache preparation, no remote) ...", flush=True)
        _fill_machinery_from_checkout()
    for ref, with_packages in wanted:
        refusal = _ensure_in_cache(ref, with_packages)
        if refusal:
            sys.exit("\n".join(refusal))

    with tempfile.TemporaryDirectory() as work:  # install scripts + graph.json stay out of the bundle
        refs = _transitive_refs(pins, platform, Path(work))

    pkglist, saved = {"Local Cache": {}}, []
    for ref in sorted(set(refs) | set(pins["toolchain"]) | set(pins["build_tools"])):
        with_packages = ref not in pins["toolchain"]
        entry = _list_json(f"{ref}#latest:*#latest" if with_packages else f"{ref}#latest").get(ref)
        if not entry:
            sys.exit(f"ERROR: {ref} is not in the local Conan cache")
        (rev, rdata), = list(entry["revisions"].items())[:1]
        if with_packages:
            rdata["packages"] = matching_packages(rdata.get("packages", {}), settings)
        pkglist["Local Cache"][ref] = {"revisions": {rev: rdata}}
        saved.append((ref, rev, len(rdata.get("packages", {}))))

    listfile = out_dir / "pkglist.json"
    listfile.write_text(json.dumps(pkglist), encoding="utf-8")
    archive = out_dir / f"adas_offline_{platform}_{date}.tgz"
    _conan("cache", "save", f"--list={listfile}", f"--file={archive}")
    listfile.unlink()

    wheels, locks, build_wheels = [], [], []
    if wheels_dir:
        wdir = out_dir / "wheels"
        subprocess.run([sys.executable, "-m", "pip", "download", "-d", str(wdir), *WHEEL_REQUIREMENTS],
                       check=True)
        wheels = sorted(p.name for p in wdir.iterdir() if p.is_file())
        envs = derive_tool_envs(include_optional=include_optional)
        tool_wheels, build_wheels = download_tool_wheels(envs, platform, wdir)
        wheels += tool_wheels
        locks = [(e["label"], e["lock_rel"], lock_sha256(e["lock"])) for e in envs]

    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                            text=True).stdout.strip() or "unknown"
    version = _conan("--version").stdout.strip()
    (out_dir / "bundle_manifest.txt").write_text(
        manifest_text(platform, date, commit, version, saved, pins, wheels, locks, build_wheels,
                      optional_included=include_optional),
        encoding="utf-8")
    print(f"[bundle] {archive} ({archive.stat().st_size // 1024} KiB), {len(saved)} recipes, "
          f"{len(wheels)} wheels -> {out_dir}")
    return archive


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv:
        # No options: guide the user instead of an argparse "required" error
        # (bundle_guide.py). In a terminal it asks; anywhere else it explains.
        import bundle_guide
        return bundle_guide.guide() if bundle_guide.is_interactive() else bundle_guide.non_interactive_help()
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     epilog="Run with no options for the guided version.")
    parser.add_argument("--platform", default=None,
                        help="vs2026 (Windows PCs) or ubuntu_gcc (Linux/WSL PCs); default: this PC's")
    parser.add_argument("--out", default=str(ROOT / DEFAULT_OUT),
                        help=f"Output directory (default {DEFAULT_OUT}, gitignored)")
    parser.add_argument("--no-wheels", action="store_true", help="Skip `pip download`")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the derived pins and stop (no conan, no pip)")
    parser.add_argument("--include-optional", action="store_true",
                        help="D15: also bundle every OPTIONAL Python tool environment's wheels")
    args = parser.parse_args(argv)
    if args.platform is None:
        args.platform = _bundle_layout().host_bundle_platform()
        print(f"[bundle] --platform not given: using {args.platform} (this PC's platform).")
    if not args.dry_run:
        refusal = wrong_host_refusal(args.platform, args.include_optional)
        if refusal:
            print("\n".join(refusal))
            return 1
    pins = derive_pins()
    if not args.dry_run:
        refusal = machinery_transfer_refusal(pins)
        if refusal:
            print("\n".join(refusal))
            return 1
    if args.dry_run:
        for name, refs in pins.items():
            print(f"{name}: {', '.join(refs) or '(none)'}")
        envs = derive_tool_envs(include_optional=args.include_optional)
        print(f"python_envs: {', '.join(e['label'] for e in envs) or '(none)'}")
        return 0
    make_bundle(args.platform, args.out, wheels_dir=not args.no_wheels,
                include_optional=args.include_optional)
    return 0


TRANSFER_DIR = Path("misc") / "offline_bundle" / "transfer"


def _windows_revisions():
    """{bare ref: revision} of the machinery refs in THIS checkout's vs2026
    bundle manifest -- the revisions the Windows cache holds (D16: the one
    content of each version)."""
    manifest = ROOT / DEFAULT_OUT / "vs2026" / "bundle_manifest.txt"
    if not manifest.is_file():
        return {}
    return parse_manifest(manifest.read_text(encoding="utf-8"))["refs"]


def _windows_path(path):
    try:
        out = subprocess.run(["wslpath", "-w", str(path)], capture_output=True, text=True)
        return out.stdout.strip() if out.returncode == 0 and out.stdout.strip() else None
    except OSError:
        return None


def machinery_transfer_refusal(pins, host=None):
    """PT-27 (D14/D16): on a Linux host (WSL making ubuntu_gcc), a machinery
    pin (adas-build-tools, adas-toolchain) missing from THIS host's Conan
    cache is refused before any `conan download`. Its only D16-safe source
    is the exact revision the Windows cache already holds: the lines
    returned name a `conan cache save` to run on Windows and a `conan cache
    restore` to run in WSL, real paths and real revision. None when nothing
    is missing, or on Windows (unchanged behaviour there)."""
    if (host or sys.platform) != "linux":
        return None
    wanted = [(ref, False) for ref in pins["toolchain"]] + \
             [(ref, True) for ref in pins["build_tools"]]
    missing = [(ref, pk) for ref, pk in wanted if not _have_in_cache(ref, pk)]
    if not missing:
        return None
    revs = _windows_revisions()
    names = ", ".join(ref for ref, _ in missing)
    lines = [f"Reason: {names} {'is' if len(missing) == 1 else 'are'} not in this host's "
             f"(WSL's) Conan cache, and a built version is never rebuilt (D16) -- the exact "
             f"revision must come from the Windows cache.",
             "Fix:    copy it: run the first command in a Windows prompt, the second in WSL, "
             "then re-run this bundle command."]
    unknown = [ref for ref, _ in missing if ref not in revs]
    win_root = _windows_path(ROOT)
    if unknown or win_root is None:
        why = (f"no revision is recorded for {', '.join(unknown)} in "
               f"misc/offline_bundle/vs2026/bundle_manifest.txt -- make the vs2026 bundle on "
               f"Windows first (python scripts/make_offline_bundle.py --platform vs2026)"
               if unknown else "this Linux host has no Windows side to copy from")
        lines[1] = f"Fix:    {why}; then copy the exact revision from the Windows cache."
        return lines
    saves, restores = [], []
    for ref, with_packages in missing:
        name, version = ref.split("/", 1)
        file = TRANSFER_DIR / f"{name}-{version}.tgz"
        pattern = f"{ref}#{revs[ref]}" + (":*" if with_packages else "")
        saves.append(f'conan cache save "{pattern}" --file "{str(file).replace("/", chr(92))}"')
        restores.append(f"conan cache restore {file.as_posix()}")
    lines.append(f'Run (Windows): cd /d "{win_root}" && ' + " && ".join(saves))
    lines.append(f'Run (WSL):     cd "{ROOT}" && ' + " && ".join(restores))
    return lines


def wrong_host_refusal(platform, include_optional=False):
    """PT-18: None when this host makes `platform`'s bundle, else the Reason /
    Fix / Run lines -- decided before any conan or pip call."""
    own = _bundle_layout().host_bundle_platform()
    if platform == own:
        return None
    cmd = bundle_command(platform, include_optional)
    lines = [f"Reason: a {platform} bundle is made on its own host (its Conan half builds "
             f"{platform} packages); this host makes {own} bundles.",
             "Fix:    run it on the right host; it writes only "
             f"misc/offline_bundle/{platform}/."]
    if cmd:
        lines.append(f"Run:    {cmd}")
    else:
        lines[1] += " This Linux host has no Windows interop, so run it on a Windows machine."
    return lines


if __name__ == "__main__":
    sys.exit(main())
