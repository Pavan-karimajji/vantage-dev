#!/usr/bin/env python3
"""ADAS 1V Superproject Build Dispatcher — plan.md item 14
(docs/build_grammar.md).

Usage:
    python scripts/build.py <module> -t <target> -p <platform> [-P <project>] [options]
    python scripts/build.py all      -t <target> -p <platform> [-P <project>] [options]
    python scripts/build.py --modules a,b -t <target> -p <platform> [-P <project>]
    python scripts/build.py config

Four axes, two of them never inferred (docs/build_grammar.md):

    module    positional      df, vdy, sil_host, ... or `all`
    -t/--target    REQUIRED   sil, gtest, coverage, docs, prod, package
    -p/--platform  REQUIRED   vs2026, ubuntu_gcc, aarch64_qcc_qnx, tda4_ti, noarch
    -P/--project   base       base, cus1

Every one of those four is read from the modules themselves - there is no
superproject-level config file at all. A module's own conf/build.yml declares
which projects it builds for (variants: keys), and which targets and platforms
each of those supports. A project exists precisely when some module says it
does; a module belongs to a project precisely when it declares that project.
The old conf/<project>.yaml carried a hand-maintained `modules:` roster, which
drifted - `shared_config` had a real, buildable target and was missing from
both conf files, so every fan-out build silently skipped it and still exited 0.
Deriving makes that unrepresentable.

There is deliberately no "part" concept any more. It used to make `sil` mean
two different things at once — a key under conf/<project>.yaml's `parts:` AND
a real target key in modules/<name>/conf/build.yml — which is why this file
used to have to *guess* which one you meant, and why `build.py base sil --only
df` and `build.py base sil_host --local-all` looked alike while doing entirely
unrelated things. `sil` now means exactly one thing repo-wide: a target.

Three modes, told apart only by which flags are present — never by guessing
what a word means:

1. Delegate (a module name, no --with/--with-all) — hands off to that module's
   own scripts/build.py with the same flags; the output is relocated under
   this superproject's conan_workarea/ via --build-dir (package mode is the
   only mode, RD-03/remove_develop_mode_plan.md).

2. Aggregate (--with/--with-all) — the unified super-build
   (docs/build_superbuild_aggregator_plan.md). The named module is the PRIMARY;
   --with <mod...> marks which of its first-party dependencies (from
   forward_closure() below) get pulled in as real in-tree CMake source targets
   (add_subdirectory()) inside one generated aggregate project, instead of
   being resolved as prebuilt Conan packages; --with-all does that for every
   first-party dependency, discovered automatically. Everything not pulled
   in-tree still resolves as a normal Conan package in the same single
   `conan install`. Pure-data first-party dependencies with no compiled CMake
   target (today: shared_config) can never be add_subdirectory()'d — "local"
   for one of those means `conan editable add` only, while it stays a normal
   `requires:` entry. Output is one real Visual Studio solution with every
   in-tree module as its own target: one "Build" click incrementally rebuilds
   whatever changed across all of them and relinks. (--with/--with-all were
   called --local/--local-all before item 14.)

3. Fan-out (module is `all`, or --modules a,b) — every module that declares
   this project, each built standalone in dependency order. This is the CI
   job. Replaces the old whole-part dispatch and its --only flag.

Output locations (docs/build_grammar.md §5; WP-20, conan_environment_plan.md
§7 CE-24 renamed ws/ -> conan_workarea/ and redesigned the aggregate name
for parseability):
  root delegate   -> conan_workarea/<module>-<project>-<target>-<platform>/   (package)
  root aggregate  -> conan_workarea/build-<target>-<platform>-<project>-<primary>-<scope>/
  module-invoked  -> modules/<m>/conan_workarea/build-<target>-<platform>/   (WP-20)
A standalone clone of a submodule has no superproject to write into, so the
module-invoked path must keep working on its own. Mixing the two invocation
styles therefore produces two caches of the same module — accepted, not
engineered around.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

import yaml

import check_conan_resolution
from submodule_init import (SubmoduleInitError, init_submodules_for, possibly_uninitialised,
                            uninitialised_submodules)
from conan_home_resolution import (active_conan_home, auth_failure_message,  # noqa: F401
                                    compute_module_fingerprint, create_and_record_module,
                                    load_lockfiles, profile_args,
                                    read_prepared_modules, record_is_outdated_format,
                                    resolve_conan_home_and_mode, remotes_enabled, setup_command,
                                    setup_py_command,
                                    REMOTES_ENV_VAR)

# This dispatcher lives in <superproject>/scripts/build.py (moved there for
# consistency with each submodule's own scripts/build.py). ROOT is the
# superproject root - one level up from this scripts/ folder.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Platform token -> the CMake generator flags the aggregator configures with.
# The per-module path doesn't need this table (each module's own
# CMakePresets.json already declares its generator per target+platform); only
# the generated aggregate project, which has no presets of its own, does.
# Deliberately not a silent fallback: an unmapped platform errors rather than
# quietly configuring with whatever CMake's default happens to be.
_AGGREGATE_GENERATORS = {
    "vs2026": ["-G", "Visual Studio 18 2026", "-A", "x64", "-T", "v145"],
    "vs2026_debug": ["-G", "Visual Studio 18 2026", "-A", "x64", "-T", "v145"],
    # Unix Makefiles, not Ninja: matches the per-component path's own
    # ubuntu_gcc preset (modules/*/CMakePresets.json's "ubuntu_gcc" base
    # preset, "generator": "Unix Makefiles") - a different generator between
    # the two paths would be a silent divergence surfacing later as a mystery
    # (prompt 35 item 1).
    "ubuntu_gcc": ["-G", "Unix Makefiles"],
}

# Single-config generators (ubuntu_gcc's Unix Makefiles) bake the build type
# in at configure time; --build --config is a multi-config-only concept and
# is silently ignored for these, so CMAKE_BUILD_TYPE must be passed here too
# or the compiled config disagrees with what `conan install -s build_type=...`
# generated conan_toolchain.cmake for (the exact class of bug conan_ops.py's
# resolve_conan_preset_name() docstring records finding in the per-component
# path). Harmless no-op for multi-config generators (vs2026), which ignore it.
_SINGLE_CONFIG_GENERATORS = {"Unix Makefiles", "Ninja"}


# ---------------------------------------------------------------------------
# WP-23 (conan_environment_plan.md §6) - which CONAN_HOME this
# build resolves first-party dependencies from. resolve_conan_home_and_mode()
# itself lives in scripts/conan_home_resolution.py, shared with setup.py (both
# run in the superproject's own Python - a genuine sibling import, not a
# mirror) - adas_build_tools.conan_ops's own copy is the one remaining
# independent implementation, forced by R-BUILD's copy/reference split (it is
# pip-installed into each component's own .venv and cannot import a
# superproject-local file). scripts/tests/test_conan_home_resolution_matrix.py
# is the guard that keeps the two agreeing.
# ---------------------------------------------------------------------------


# RP-02 (root_build_package_mode_plan.md D2): the ONE place the root default
# is decided. Delegate, aggregate and fan-out all use it; `--mode develop` is
# the explicit opt-in. Every call into apply_conan_home() and every forward to
# a module's build.py passes the mode explicitly, so the superproject default
# in resolve_conan_home_and_mode() (invocation-level) is never consulted from
# this file.
ROOT_DEFAULT_MODE = "package"


def apply_conan_home(mode, label):
    """Sets os.environ["CONAN_HOME"] (if this decision calls for it) and
    ADAS_BUILD_INVOCATION=superproject BEFORE this process makes its own
    first conan call (conan install) or
    subprocesses into a module's build.py - both need to see
    the resolved cache, and the subprocess inherits this env verbatim plus
    the explicit --mode forwarded on its own command line (never re-derived
    downstream). This file's own invocation is always "superproject" by
    construction - delegate, aggregate and fan-out are ALL root-dispatcher
    entry points."""
    conan_home, resolved_mode, reason = resolve_conan_home_and_mode(mode, "superproject")
    if conan_home is not None:
        os.environ["CONAN_HOME"] = conan_home
    os.environ["ADAS_BUILD_INVOCATION"] = "superproject"
    print(f"[{label}] WP-23 CONAN_HOME resolution: mode={resolved_mode} - {reason}")
    print(f"[{label}] CONAN_HOME = {os.environ.get('CONAN_HOME') or '(unset - Conan default)'}")


# Build logging (plan.md item 18). Same shape and same rules as every module's
# own scripts/build.py: one file per target+platform, truncated per run, living
# inside the build output it describes so it follows the output folder around
# and --clean takes it with the tree.
_LOG = None


def log(text=""):
    print(text, flush=True)
    if _LOG is not None:
        _LOG.write(text + "\n")
        _LOG.flush()


def open_log(log_dir, name):
    global _LOG
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, f"{name}.log")
    _LOG = open(path, "w", encoding="utf-8", errors="replace")
    return path


def close_log():
    global _LOG
    if _LOG is not None:
        _LOG.close()
        _LOG = None


def run_logged(cmd, cwd):
    """Run a child process, streaming its output to console and log at once.
    Returns the exit code rather than exiting, so callers keep their existing
    error handling. Only the aggregator needs this - delegate and fan-out hand
    off to each module's own scripts/build.py, which writes its own log."""
    log(" ".join(str(c) for c in cmd))
    proc = subprocess.Popen(
        cmd, cwd=cwd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
    )
    for line in proc.stdout:
        log(line.rstrip("\n"))
    proc.wait()
    if proc.returncode != 0:
        log(f"\nFAILED (exit {proc.returncode}): {' '.join(str(c) for c in cmd)}")
    return proc.returncode


# CE-28 auth-failure matching lives in conan_home_resolution.py (CE-29: one
# source, shared with check_conan_resolution.py); imported at the top.


def run_install_logged(cmd, cwd, explain=None):
    """Like run_logged(), but for a `conan install ... --format=json`
    invocation (WP-20, conan_environment_plan.md §7 CE-24): stdout (the
    graph JSON) and stderr (Conan's ordinary human-readable progress) are
    kept separate, the same split adas_build_tools.builder.run_install()
    already uses for a component's own install, and for the identical
    reason - a merged stream (run_logged()'s own shape) can't be parsed as
    pure JSON. Returns (returncode, parsed_json_or_None); a non-zero exit
    or unparseable stdout both return None for the graph, matching
    run_install()'s own "convenience only" treatment. `explain` (WP-13): called
    with Conan's stderr on failure; the lines it returns are logged after it."""
    log(" ".join(str(c) for c in cmd))
    proc = subprocess.Popen(
        cmd, cwd=cwd,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace",
    )
    stdout_data, stderr_data = proc.communicate()
    for line in (stderr_data or "").splitlines():
        log(line)
    if proc.returncode != 0:
        log(f"\nFAILED (exit {proc.returncode}): {' '.join(str(c) for c in cmd)}")
        auth = auth_failure_message(stderr_data or "", os.environ.get("CONAN_HOME"))
        if auth:
            log(f"ERROR: {auth}")
        for line in (explain(stderr_data or "") if explain else None) or []:
            log(line)
        return proc.returncode, None
    try:
        return proc.returncode, json.loads(stdout_data)
    except (json.JSONDecodeError, ValueError, TypeError):
        log("WARNING: could not parse the Conan dependency graph JSON - "
            "conan_workarea/used/ will not be updated for this aggregate build.")
        return proc.returncode, None


def _create_windows_lnk(lnk_path, target_path):
    """Last-resort fallback, ported from adas_build_tools.workarea's own
    copy of the same name (imp_design.md §3.4) - a real Windows `.lnk`
    shortcut file via PowerShell's WScript.Shell COM object, no new pip
    dependency. Kept a literal duplicate rather than imported (see
    refresh_aggregate_used_shortcuts()'s own docstring for why the
    aggregate can't import adas_build_tools at all); agreement between the
    two copies is guarded by scripts/tests/test_used_shortcuts_agreement.py,
    the same pattern test_profile_path_agreement.py already uses for
    conan_home_resolution.py vs. adas_build_tools.conan_ops."""
    script = (
        "$s = New-Object -ComObject WScript.Shell; "
        f"$sc = $s.CreateShortcut('{lnk_path}'); "
        f"$sc.TargetPath = '{target_path}'; "
        "$sc.Save()"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=True,
    )


def _create_link(link_path, target_path):
    """Tries a real symlink, then (Windows only) a junction, then a
    `.lnk` file - never raises, never fails the build over a convenience
    shortcut it couldn't create. Ported from adas_build_tools.workarea's
    own `_create_link()` (imp_design.md §3.4); see that function's
    docstring for the full rationale of each rung. Returns True if some
    form of link was created, False if every option failed."""
    try:
        os.symlink(target_path, link_path, target_is_directory=True)
        return True
    except OSError:
        pass

    if os.name == "nt":
        proc = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link_path), str(target_path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if proc.returncode == 0:
            return True

        try:
            # CE-19: appended, never replacing a dotted version's own
            # trailing digit the way Path.with_suffix() would - see the
            # ported original's own docstring for the lz4-1.9.4 incident.
            _create_windows_lnk(link_path + ".lnk", target_path)
            return True
        except (OSError, subprocess.CalledProcessError):
            pass

    log(f"NOTE: could not create a shortcut at {link_path} for {target_path} "
        f"(tried a real symlink, a junction, and a .lnk shortcut) - "
        f"conan_workarea/used/ will be missing this entry. This is a "
        f"convenience only; the build itself is unaffected.")
    return False


def aggregate_graph_nodes(graph_json):
    """The non-Consumer nodes of a `conan install --format=json` graph as
    (ref-without-revision, node) pairs - the one parser of that shape, shared
    by refresh_aggregate_used_shortcuts() and resolved_kind_mismatches()
    (AB-02: no second parser)."""
    nodes = (graph_json or {}).get("graph", {}).get("nodes", {})
    return [(node["ref"].split("#", 1)[0], node)
            for node in nodes.values()
            if node.get("recipe") != "Consumer" and node.get("ref")]


def _node_libdirs(node):
    """A graph node's cpp_info.root.libdirs (AB-10, AB-13: one source)."""
    return list(((node.get("cpp_info") or {}).get("root") or {}).get("libdirs") or [])


def aggregate_used_targets(graph_json):
    """AB-13: {used/ entry name: folder it links to}. An Editable node with
    libdirs links its FIRST libdir - its build output, the same place AB-10
    checks - rather than package_folder (= its repo root); the remaining
    libdirs are logged, never given a folder of their own. A data editable
    (no libdirs, e.g. shared_config) and every non-editable node keep
    package_folder."""
    wanted = {}
    for ref, node in aggregate_graph_nodes(graph_json):
        package_folder = node.get("package_folder")
        libdirs = _node_libdirs(node)
        if node.get("binary") == "Editable" and libdirs:
            target = libdirs[0]
            if len(libdirs) > 1:
                log(f"NOTE: {ref} has {len(libdirs)} libdirs; used/ links the first "
                    f"({target}), not: {'; '.join(libdirs[1:])}")
        elif package_folder:
            target = package_folder
        else:
            continue
        wanted[ref.replace("/", "-")] = target
    return wanted


_CMAKE_CACHE_PATH_ENTRY = re.compile(r"^([A-Za-z0-9_.+\-]+):(FILEPATH|PATH)=(.*)$")


def stale_cmake_cache_vars(build_dir):
    """Sorted names of FILEPATH/PATH entries in build_dir/CMakeCache.txt whose
    value is an absolute path that no longer exists. A reused aggregate
    folder otherwise keeps calling a protoc.exe from a Conan cache that is
    gone (Conan's protobuf module searches only while PROTOC_PROGRAM is
    unset) - found 2026-09-29 after a cold-check scratch CONAN_HOME was
    deleted. Same function as adas_build_tools/cmake_cache.py (this file
    cannot import that package); scripts/tests/test_stale_cmake_cache.py
    holds the two to the same answers."""
    cache = os.path.join(str(build_dir), "CMakeCache.txt")
    if not os.path.isfile(cache):
        return []
    stale = set()
    with open(cache, encoding="utf-8", errors="ignore") as f:
        lines = f.read().splitlines()
    for line in lines:
        match = _CMAKE_CACHE_PATH_ENTRY.match(line.strip())
        if not match:
            continue
        value = match.group(3).strip()
        if not value or value.endswith("-NOTFOUND") or not os.path.isabs(value):
            continue
        if not os.path.exists(value):
            stale.add(match.group(1))
    return sorted(stale)


def cmake_cmd_with_unsets(cmd, names):
    """`cmd` with -U<name> inserted right after the cmake executable, before
    -S/--preset and every -D, skipping names `cmd` itself sets with -D.
    Same as adas_build_tools/cmake_cache.py with_unsets()."""
    defined = {re.split(r"[:=]", a[2:], maxsplit=1)[0] for a in cmd if a.startswith("-D")}
    return [cmd[0], *(f"-U{n}" for n in names if n not in defined), *cmd[1:]]


def refresh_aggregate_used_shortcuts(ws_dir, graph_json):
    """conan_workarea/<scope>/used/<name>-<version> - the aggregate's own
    equivalent of adas_build_tools.workarea.refresh_used_shortcuts(), for
    the SAME reason WP-20 (conan_environment_plan.md §7 CE-24) requires
    it: "the same name must mean the same shape" - a conan_workarea/ that
    only ever holds build folders would teach a reader the wrong thing
    about a folder they already learned elsewhere (every component's own
    conan_workarea/used/). Not imported from adas_build_tools (that
    package is never installed at the superproject level - it lives inside
    each COMPONENT's own .venv, imp_design.md's own bootstrap design) -
    reimplemented here, duplicating adas_build_tools.workarea's own
    junction/`.lnk`/text-note ladder (item 4, prompt 35): a real symlink
    fails outright on a non-elevated machine with Developer Mode off (the
    common case, and the one the office-laptop profile this whole chain
    serves actually hits - confirmed live, WinError 1314), which the
    previous symlink-only version degraded gracefully around but never
    actually resolved. `_create_link()`/`_create_windows_lnk()` above are
    literal ports, not a redesign; `test_used_shortcuts_agreement.py`
    keeps them from drifting since they can't be merged into one copy.

    A `package_folder` that doesn't exist on disk (an editable dependency
    with no build output yet for this exact target+platform - the same
    case adas_build_tools.workarea's own EDITABLE_NOTE_SUFFIX exists for)
    gets a `.txt` note instead of a dangling link, never a broken shortcut.
    adas-shared-config's own package_folder (its repo root, package_type
    "unknown", no layout()) is a real, existing directory either way, so
    it links normally once the ladder itself can succeed - no separate
    case needed for it.

    delivered/ is deliberately never created here: it exists for a
    component only after a `-t package` build produces something to
    archive (§5.2 - "correct behavior, not a gap" for a component that
    has only ever run `-t sil"), and the aggregate has no package step at
    all - the same convention, applied honestly, produces no folder rather
    than an empty one that would need explaining."""
    used_dir = os.path.join(ws_dir, "used")
    os.makedirs(used_dir, exist_ok=True)
    wanted = aggregate_used_targets(graph_json)

    def _remove_entry(existing_path):
        try:
            if os.path.islink(existing_path):
                os.unlink(existing_path)
            elif os.path.isdir(existing_path):
                # rmdir(), not rmtree(): a junction/directory-symlink
                # reports as a directory but rmdir() only removes the
                # reparse point itself, never the target's contents - the
                # same guarantee _remove_existing() documents in the
                # ported original.
                try:
                    os.rmdir(existing_path)
                except OSError:
                    shutil.rmtree(existing_path)
            else:
                os.unlink(existing_path)
        except OSError:
            pass

    for existing in list(os.listdir(used_dir)) if os.path.isdir(used_dir) else []:
        base = existing[:-4] if existing.lower().endswith((".lnk", ".txt")) else existing
        if base not in wanted:
            _remove_entry(os.path.join(used_dir, existing))

    for name, target in wanted.items():
        link_path = os.path.join(used_dir, name)
        note_path = link_path + ".txt"
        for candidate in (link_path, link_path + ".lnk", note_path):
            if os.path.islink(candidate) or os.path.exists(candidate):
                _remove_entry(candidate)

        if not os.path.isdir(target):
            with open(note_path, "w", encoding="utf-8") as note_file:
                note_file.write(
                    f"No build output yet for this target+platform.\n"
                    f"Expected at: {target}\n"
                )
            continue

        _create_link(link_path, target)


def load_yaml(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def module_dirs():
    modules_dir = os.path.join(ROOT, "modules")
    return sorted(
        name for name in os.listdir(modules_dir)
        if os.path.isdir(os.path.join(modules_dir, name))
    )


def module_conanfile_text(mod):
    conanfile = os.path.join(ROOT, "modules", mod, "conanfile.py")
    if not os.path.exists(conanfile):
        return None
    return open(conanfile, encoding="utf-8").read()


def is_valid_module(mod):
    return module_conanfile_text(mod) is not None


def module_package_name(mod):
    """The real Conan package name (e.g. "adas-shared-config") read from that
    module's own CMakeLists.txt project() line - the same single source of
    truth the byte-identical conanfile.py's set_name() reads (plan.md item 20,
    docs/conanfile_commonality_plan.md). NOT scraped from conanfile.py any
    more: since item 20 the recipe carries no `name = "..."` literal (set_name()
    derives it from CMakeLists), so the old regex found nothing and silently
    emptied package_to_module_map(), collapsing the aggregate to a
    packages-only (find_package) build with no in-tree targets. The conanfile
    existence check below still gates "is this a real module" (placeholders
    have none)."""
    if module_conanfile_text(mod) is None:
        return None
    cmakelists = os.path.join(ROOT, "modules", mod, "CMakeLists.txt")
    if not os.path.exists(cmakelists):
        return None
    text = open(cmakelists, encoding="utf-8").read()
    match = re.search(r'project\(\s*([A-Za-z0-9_\-]+)', text)
    return match.group(1) if match else None


def module_package_type(mod):
    """Conan's own self.package_type off that module's conanfile.py
    (plan.md item 13, docs/build_superbuild_aggregator_plan.md §5) - decides
    whether a module CAN be pulled in-tree (shared-library/static-library/
    application, i.e. it has a real compiled CMake target to
    add_subdirectory()) or is a pure-data package with none (today: only
    shared_config, package_type "unknown") - those are never add_subdirectory
    candidates; "local" for one of those means a Conan editable override
    only, since there's no compiled target for an ALIAS to point at and no
    add_subdirectory() would provide anything a consumer's find_package()
    actually needs (e.g. shared_config's own
    ${adas-shared-config_PACKAGE_FOLDER_RELEASE} CMake variable only exists
    via Conan's CMakeDeps, never via add_subdirectory()).

    Read from this module's conf/build.yml recipe.type (plan.md item 20 moved
    it there; the byte-identical conanfile.py reads the same field at import).
    Was scraped from a `package_type = "..."` literal in conanfile.py before
    item 20 - that literal is gone now (the template computes package_type from
    this same conf field), so the old regex returned None for every module."""
    conf = load_module_conf(mod)
    if conf is None:
        return None
    return (conf.get("recipe") or {}).get("type")


def module_version(mod):
    """The version this module's own `conan export` would produce (AB-06,
    aggregate_build_integrity_plan.md D3) - the same single source of truth
    modules/toolchain/base_recipe.py's set_version() reads: CMakeLists.txt's
    `project(<name> VERSION x.y.z ...)`, else the module's VERSION file (a
    project() with no VERSION, e.g. sim, LANGUAGES NONE shared_config).
    None if neither yields one - never a guessed default."""
    name = module_package_name(mod)
    if not name:
        return None
    mod_dir = os.path.join(ROOT, "modules", mod)
    with open(os.path.join(mod_dir, "CMakeLists.txt"), encoding="utf-8") as f:
        text = f.read()
    match = re.search(rf"project\(\s*{re.escape(name)}\s+VERSION\s+([0-9]+\.[0-9]+\.[0-9]+)",
                      text, re.IGNORECASE)
    if match:
        return match.group(1)
    version_file = os.path.join(mod_dir, "VERSION")
    if os.path.exists(version_file):
        with open(version_file, encoding="utf-8") as f:
            return f.read().strip() or None
    return None


def package_to_module_map():
    return {
        pkg: mod
        for mod in module_dirs()
        for pkg in [module_package_name(mod)]
        if pkg
    }


FIRST_PARTY_PREFIX = "adas-"
# D10 (partial_clone_correctness_plan.md): the only first-party package whose
# folder breaks the adas-<x> -> modules/<x> convention. check_invariants.py
# PKG-1 keeps this list honest.
PACKAGE_DIR_EXCEPTIONS = {"adas-shared-config": "shared_config"}


def module_for_package(pkg_name):
    """D10: the folder under modules/ for a first-party package, None for a
    third-party one. Works with the module NOT checked out (an uninitialised
    submodule is still an empty directory). Exits on a first-party name with
    no such folder - a refusal, never a silent drop."""
    if not pkg_name.startswith(FIRST_PARTY_PREFIX):
        return None
    folder = PACKAGE_DIR_EXCEPTIONS.get(pkg_name, pkg_name[len(FIRST_PARTY_PREFIX):])
    if not os.path.isdir(os.path.join(ROOT, "modules", folder)):
        print(f"ERROR: first-party package '{pkg_name}' maps to modules/{folder}, which "
              f"does not exist - add it to PACKAGE_DIR_EXCEPTIONS in scripts/build.py "
              f"(currently: {PACKAGE_DIR_EXCEPTIONS})")
        sys.exit(1)
    return folder


def load_module_conf(mod):
    conf_path = os.path.join(ROOT, "modules", mod, "conf", "build.yml")
    if not os.path.exists(conf_path):
        return None
    return load_yaml(conf_path)


def module_declares(mod, project, target, platform):
    """Whether this module's own conf/build.yml really declares this
    target+platform pair for this project - the same target_blocks()/
    platforms: reading each module's own scripts/build.py does, duplicated
    here only so fan-out mode can SKIP a module that doesn't build this pair
    instead of failing the whole batch on it. A directly-named module is never
    pre-checked this way: it goes straight to its own build.py so the error
    comes from the one authority on its own targets."""
    conf = load_module_conf(mod)
    if conf is None:
        return False
    block = (conf.get("variants") or {}).get(project, {}).get(target)
    if not isinstance(block, dict) or "platforms" not in block:
        return False
    return platform in [entry["build"] for entry in block["platforms"]]


def first_party_requires(mod, project, pkg_map):
    """Resolved module-directory names this module's own conf/build.yml
    requires: for <project> (docs/conan_requires_in_build_yml.md's single
    source of truth) - third-party deps (protobuf, yaml-cpp) are silently
    excluded since they don't map to any local module directory."""
    conf = load_module_conf(mod)
    if conf is None:
        return []
    variant = conf.get("variants", {}).get(project, {})
    result = []
    for ref in variant.get("requires", []):
        pkg_name = ref.split("/")[0]
        dep_mod = pkg_map.get(pkg_name)
        if dep_mod and dep_mod != mod:
            result.append(dep_mod)
    return result


def raw_requires_for(mod, project, key):
    """Raw Conan ref strings (e.g. "adas-interfaces/1.0.0", "protobuf/3.21.12")
    this module's own conf/build.yml declares under requires:/tool_requires:
    for <project> - both third-party and first-party refs, unlike
    first_party_requires() above which resolves only the first-party ones
    down to module directory names. Used to build the aggregate's own
    generated conanfile.py (plan.md item 13 §5 step 2)."""
    conf = load_module_conf(mod)
    if conf is None:
        return []
    return conf.get("variants", {}).get(project, {}).get(key, [])


def absent_first_party_refs(mods, project):
    """D2: the first-party requires: of `mods` whose module is not checked out
    (no conanfile.py), as {folder: "adas-x/1.2.3"}. forward_closure() walks
    present modules only, so the walk stops at these - they are consumed as
    packages (D9) or, where the closure is a work list, refused (D3)."""
    absent = {}
    for mod in sorted(mods):
        for ref in raw_requires_for(mod, project, "requires"):
            folder = module_for_package(ref.split("/")[0])
            if folder and folder != mod and not is_valid_module(folder):
                absent[folder] = ref
    return absent


def init_absent_modules(mods):
    """W3 (D3/D4): initialise the submodules in `mods` - exactly the set about
    to be compiled from source. A refusal (half-populated, git failure) prints
    its lines and exits."""
    try:
        return init_submodules_for(mods, root=ROOT)
    except SubmoduleInitError as exc:
        print("\n".join(exc.lines))
        sys.exit(1)


def init_if_uninitialised(mods):
    """D0/D4 for a fresh superproject clone: of `mods`, initialise those git
    reports as not initialised. A populated module - including a checked-out
    placeholder with no conanfile.py - is left alone, so a name that is not a
    real module still gets the ordinary `unknown module` error later."""
    candidates = possibly_uninitialised(mods, ROOT)  # no git call when all are checked out
    if not candidates:
        return []
    wanted = [mod for mod in candidates if mod in uninitialised_submodules(ROOT)]
    return init_absent_modules(wanted) if wanted else []


def absent_dep_problems(absent, primary, target, platform, project):
    """D9: gate the first-party dependencies that are not checked out. In the
    cache (profile-matched) -> silent. Not cached -> an error, whatever the
    remotes switch says: the component build refuses any uncached first-party
    dependency before `conan install` (NS-07, adas_build_tools builder.py), and
    nothing downloads a first-party binary into the local cache, so a NOTE
    promising a remote fetch would be false. Returns a list of message lines."""
    settings = check_conan_resolution.pinned_profile_settings(platform)
    errors = []
    for folder, ref in sorted(absent.items()):
        if settings is not None and check_conan_resolution._cache_matches_profile(ref, settings):
            continue
        errors.append(f"ERROR: {folder} ({ref}) is not checked out and not in this machine's "
                      f"Conan cache. Run: git submodule update --init modules/{folder}, then "
                      f"{setup_py_command()} --prepare {primary} -t {target} "
                      f"-p {platform} -P {project}")
    return errors


def enabled_functions_for(mod, project):
    """Semicolon-joined ENABLED_FUNCTIONS value, same as df's own conanfile.py
    _enabled_functions_for() - read here too so the aggregate's generated
    CMakeLists.txt can set the identical CMake cache variable when df is
    pulled in-tree (plan.md item 13 §5 step 3)."""
    conf = load_module_conf(mod)
    if conf is None:
        return ""
    values = conf.get("variants", {}).get(project, {}).get("enabled_functions", [])
    return ";".join(values)


def forward_closure(start_mods, project, pkg_map):
    """Every first-party dependency transitively reachable from start_mods,
    walking requires: forward (§6.5) - the developer names only the target,
    not its whole dependency chain."""
    seen = set()
    stack = [m for m in start_mods if load_module_conf(m) is not None]
    while stack:
        mod = stack.pop()
        if mod in seen:
            continue
        seen.add(mod)
        for dep in first_party_requires(mod, project, pkg_map):
            if dep not in seen:
                stack.append(dep)
    return seen


def topo_sort(mods, project, pkg_map):
    """Dependency-first build order over `mods`, with cycle detection
    (§6.2's corner case, §6.5 step 2) - command-line/discovery order must
    never be load-bearing."""
    done = set()
    visiting = set()
    order = []

    def visit(mod, path):
        if mod in done:
            return
        if mod in visiting:
            print(f"ERROR: dependency cycle detected: {' -> '.join(path + [mod])}")
            sys.exit(1)
        visiting.add(mod)
        for dep in first_party_requires(mod, project, pkg_map):
            if dep in mods:
                visit(dep, path + [mod])
        visiting.discard(mod)
        done.add(mod)
        order.append(mod)

    for mod in sorted(mods):
        visit(mod, [])
    return order


def validate_with_module(mod, primary=None, project=None):
    if not is_valid_module(mod):
        if primary is not None and is_valid_module(primary):
            absent = absent_first_party_refs(
                forward_closure({primary}, project, package_to_module_map()), project)
            if mod in absent:
                print(f"ERROR: '{mod}' is a dependency of '{primary}' but is not checked "
                      f"out - run git submodule update --init modules/{mod}")
                sys.exit(1)
        print(f"ERROR: unknown --with module '{mod}' - no modules/{mod}/conanfile.py")
        sys.exit(1)


_PYTHON_REQUIRES_RE = re.compile(r'python_requires\s*=\s*["\']adas-toolchain/([0-9.]+)["\']')


def discover_toolchain_pins(mods):
    """The set of distinct `adas-toolchain/<version>` versions pinned by
    `python_requires =` across `mods`' own conanfile.py (CE-18's discovery,
    scoped to this dispatcher's own callers rather than checker-wide)."""
    pins = set()
    for mod in mods:
        conanfile = os.path.join(ROOT, "modules", mod, "conanfile.py")
        if not os.path.exists(conanfile):
            continue
        with open(conanfile, encoding="utf-8") as f:
            match = _PYTHON_REQUIRES_RE.search(f.read())
        if match:
            pins.add(match.group(1))
    return pins


def toolchain_checkout_version():
    """The version modules/toolchain's own VERSION file declares - the same
    `cat VERSION` its conf/build.yml documents as the publish step.
    module_version() can't be reused here: toolchain has no CMakeLists.txt
    and is excluded from discover_components() by name (its own conf/
    build.yml explains why)."""
    version_file = os.path.join(ROOT, "modules", "toolchain", "VERSION")
    if not os.path.exists(version_file):
        return None
    with open(version_file, encoding="utf-8") as f:
        return f.read().strip() or None


def require_toolchain_checkout():
    """D0 (partial_clone_correctness_plan.md): modules/toolchain is build
    machinery the root scripts read by path (VERSION for the pin check, the
    Conan profiles, the lockfiles), not a package taken from the cache - so it
    is always checked out, even in a partial clone. Refuses early, with the
    one-line init command, before any conan call."""
    if toolchain_checkout_version() is None:
        print("ERROR: modules/toolchain is not checked out. It is build machinery every "
              "root command reads (toolchain pin, Conan profiles, locks), not a package. "
              "Run: git submodule update --init modules/toolchain")
        sys.exit(1)


def missing_toolchain_pin(mods):
    """NS-05 (cache_first_no_server_plan.md D4, STEP 2): read-only
    replacement for the deleted ensure_toolchain_exported()'s own export (NS-34) - this never
    touches the cache, it only reports which of `mods`' pinned
    `adas-toolchain/<version>` refs this machine's cache cannot resolve
    (recipe presence only, CE-18's own reasoning: a python_requires
    package has no settings axis to match a binary against). A pin that
    disagrees with the checkout (the deleted ensure_toolchain_exported()'s drift
    case) is reported the same way here - the checkout can never supply a
    different version than its own, so a mismatched pin is exactly as
    "missing" as an absent one. Returns a sorted list of ref strings."""
    pins = discover_toolchain_pins(mods)
    if not pins:
        return []
    checkout_version = toolchain_checkout_version()
    missing = []
    for pin in sorted(pins):
        ref = f"adas-toolchain/{pin}"
        if pin != checkout_version or not check_conan_resolution._cache_has_recipe(ref):
            missing.append(ref)
    return missing


def missing_cache_refs(mods, project, platform):
    """NS-05 (cache_first_no_server_plan.md D4, STEP 2): read-only
    replacement for the deleted export_first_party_deps()'s own export - reports which
    of `mods`' own first-party Conan packages this machine's cache cannot
    resolve a binary for, against `platform`'s pinned profile. Reuses
    check_conan_resolution's own cache-first "can this machine resolve it"
    check (check_conan_resolution._cache_matches_profile(), the SAME
    function setup.py's --prepare and its "Conan package resolution
    completeness" step already use, NS-03/STEP 1) rather than growing a
    second, divergent notion of "cached" in this file. A module with no
    determinable package name/version (a placeholder, or a module missing
    a CMakeLists.txt VERSION) is silently skipped - is_valid_module()/
    forward_closure() already excluded those from ever reaching here in
    the normal case; this is defence, not the primary filter. Returns a
    sorted list of (mod, ref) pairs still missing."""
    profile_settings = check_conan_resolution.pinned_profile_settings(platform)
    missing = []
    for mod in sorted(mods):
        pkg_name = module_package_name(mod)
        version = module_version(mod)
        if not pkg_name or not version:
            continue
        ref = f"{pkg_name}/{version}"
        if (profile_settings is None
                or not check_conan_resolution._cache_matches_profile(ref, profile_settings)):
            missing.append((mod, ref))
    return missing


def stale_cache_refs(mods):
    """NS-05a (cache_first_no_server_plan.md D4a, STEP 3): "refuse a stale
    cache, don't refresh it." For each module in `mods` (only ones already
    confirmed present in the cache - missing_cache_refs() is the "is it
    there at all" check; this is never the primary filter), recompute its
    fingerprint (conan_home_resolution.compute_module_fingerprint(), the
    SAME function setup.py used to record it) and compare against what
    setup.py recorded the last time it actually exported/created that
    module's ref (conan_home_resolution.record_prepared_module(), STEP 1/
    prepare_conan_cache's own toolchain export). A module setup.py has
    never recorded at all - the whole prepared_modules.json is missing (a
    machine prepared before this mechanism existed), or this one module
    simply isn't in it - is reported separately as `unrecorded`, never as
    `stale`: refusing there would break every existing machine on upgrade
    (D4a's own escape hatch, mirrored from missing_cache_refs' own "never
    guess" discipline).

    Returns (stale, unrecorded): `stale` is a sorted list of
    (mod, recorded_git, current_git) triples whose fingerprint disagrees;
    `unrecorded` is a sorted list of module names with nothing recorded.

    NS-52: a record written under an older fingerprint format is in
    NEITHER list - its `dirty` means something else, so calling it stale
    would tell the developer their source changed when it did not. Those
    are reported by outdated_format_refs(), which every caller checks
    first."""
    # D1 (partial_clone_correctness_plan.md): no source, no claim. A module
    # with no conanfile.py is not checked out; absence is not evidence of
    # change. Filtered BEFORE the early return below (F5), which would
    # otherwise report it as "unrecorded".
    mods = [mod for mod in mods if is_valid_module(mod)]
    recorded = read_prepared_modules(ROOT)
    if recorded is None:
        return [], sorted(mods)
    stale = []
    unrecorded = []
    for mod in sorted(mods):
        entry = recorded.get(mod)
        if entry is None:
            unrecorded.append(mod)
            continue
        if record_is_outdated_format(entry):
            continue
        fp = compute_module_fingerprint(os.path.join(ROOT, "modules", mod))
        if fp["git"] != entry.get("git") or fp["dirty"] != entry.get("dirty"):
            stale.append((mod, entry.get("git"), fp["git"]))
    return stale, unrecorded


def unrecorded_message(unrecorded, primary, target, platform, project):
    """NS-37's refusal for cached first-party refs with no freshness record -
    one line per ref, then the ONE command that records them all (it used to
    repeat that command once per ref, e.g. five times after the superproject's
    conan_workarea/ was deleted). Returns the message lines."""
    lines = [f"ERROR: {dep} ({module_package_name(dep)}/{module_version(dep)}) is in this "
             "machine's Conan cache but has no recorded freshness fingerprint (NS-37/RQ-4)"
             for dep in unrecorded]
    lines.append(f"Run: {setup_py_command()} --prepare {primary} -t {target} -p {platform} "
                 f"-P {project}  to build and record "
                 f"{'it' if len(unrecorded) == 1 else 'them'}")
    return lines


def outdated_format_refs(mods):
    """NS-52: the third bucket beside stale_cache_refs()'s stale/unrecorded -
    modules whose freshness record predates the current fingerprint format
    (NS-51 changed what `dirty` hashes). Sorted module names."""
    recorded = read_prepared_modules(ROOT) or {}
    return sorted(mod for mod in mods
                  if mod in recorded and record_is_outdated_format(recorded[mod]))


def outdated_format_message(dep, primary, target, platform, project):
    """NS-52: the refusal for an outdated-format record. Says the FORMAT
    changed and names --prepare; never "changed since it was cached", which
    would be a lie about the developer's own source."""
    ref = f"{module_package_name(dep)}/{module_version(dep)}"
    return (f"ERROR: {dep} ({ref}) has a freshness record in an older fingerprint "
            f"format (NS-51 made it hash file content, not just file names), so it "
            f"cannot be compared - your source did not necessarily move. Run "
            f"python scripts/setup.py --prepare {primary} -t {target} -p {platform} "
            f"-P {project}  once to re-record it.")


def stale_cache_message(dep, primary, target, platform, project, old_git, new_git):
    """The refusal for a stale cached package. The commit moved (a pull or
    submodule update the developer may not know about) -> --prepare. Same
    commit -> only uncommitted work differs, which the developer did -> build
    from source with --with first, --prepare second. One side's commit unknown
    -> not comparable, so claim neither cause and offer both."""
    heads = (f"(HEAD {old_git[:8]}, unchanged)" if old_git and old_git == new_git
             else f"(HEAD {(old_git or '?')[:8]} -> {(new_git or '?')[:8]})")
    prepare = (f"python scripts/setup.py --prepare {primary} -t {target} "
               f"-p {platform} -P {project}")
    with_dep = (f"python scripts/build.py {primary} -t {target} -p {platform} "
                f"-P {project} --with {dep}")
    if old_git and new_git and old_git != new_git:
        return (f"ERROR: {dep} changed since it was cached {heads} - a pull or "
                f"submodule update moved its commit. Run {prepare}")
    if old_git == new_git:
        return (f"ERROR: {dep} has uncommitted changes since it was cached {heads}. "
                f"To build it from source (no re-prepare needed between edits), run "
                f"{with_dep} ; or to re-record the cache, run {prepare}")
    return (f"ERROR: {dep} changed since it was cached {heads}, and the commits "
            f"cannot be compared, so the cause is unknown. To build it from source, "
            f"run {with_dep} ; or to re-record the cache, run {prepare}")


# ---------------------------------------------------------------------------
# Delegate mode - one module, built by its own scripts/build.py
# ---------------------------------------------------------------------------


def delegate_folder_name(module, project, target, platform):
    """RP-04: a delegate build is a `solo` build in the one root folder
    grammar (ws_folder_name) - same fields, no second naming scheme."""
    return ws_folder_name(target, platform, project, module, None, False)


def delegate_build_dir(module, project, target, platform):
    return os.path.join(ROOT, "conan_workarea",
                        delegate_folder_name(module, project, target, platform))


def ws_logs_dir():
    """One central log directory for every superproject-triggered build
    (delegate, aggregate, and the fan-out summary). Logs used to live inside
    each build tree; centralizing them here means one folder to scan for
    "what got built", and it survives a per-build --clean. Standalone module
    builds (no superproject) still log inside their own build tree - they have
    no conan_workarea/ to write to (WP-20, conan_environment_plan.md §7 CE-24
    renamed ws/ -> conan_workarea/; this function's own name is otherwise
    unchanged internal vocabulary)."""
    return os.path.join(ROOT, "conan_workarea", "logs")


def delegate_log_path(module, project, target, platform):
    """Where that module's own scripts/build.py will have written its log -
    now the central conan_workarea/logs/, since the superproject passes
    --log-dir there when it delegates. Named after the build's own
    conan_workarea folder, so every log is self-identifying
    (build-sil-vs2026-base-df-pkg-solo.log, RP-04). The old cmake_layout "one level deeper under
    build/" special case is gone: --log-dir is honored verbatim, independent
    of the module's layout_kind."""
    log_name = delegate_folder_name(module, project, target, platform)
    return os.path.join(ws_logs_dir(), f"{log_name}.log")


def run_delegate(module, project, target, platform, clean, no_log, remotes_state=None,
                 update_lock=False):
    """Hand off to the module's own scripts/build.py. This dispatcher
    deliberately knows nothing about targets, presets, Conan or CMake - the
    module's own build.py is the single authority on how to build it, and is
    byte-identical across every module. All this adds is where the output
    goes.

    NS-05 (cache_first_no_server_plan.md D4, STEP 2): build.py builds, and
    nothing else - no pre-flight `conan export`/`conan create` here any
    more (the removed export pre-flight, deleted
    outright in NS-34; setup.py owns cache preparation, D4/
    D4b, `setup.bat --prepare <module> -t -p [-P]`). What replaces it is
    read-only: every first-party dependency this module is about to
    resolve as a plain Conan package (deps, below) is checked against this
    machine's own cache (missing_toolchain_pin()/missing_cache_refs(),
    both read-only) BEFORE the subprocess is even started - a ref missing
    from the cache and not being built here STOPS the build, naming the
    ref and the exact `setup.bat --prepare` command (RQ-9), rather than
    letting a raw Conan graph-resolution error surface from deep inside
    the child process.

    NS-32: no `mode` parameter - package is the only mode (RD-03,
    remove_develop_mode_plan.md), so it is ROOT_DEFAULT_MODE here, applied
    and forwarded explicitly on the subprocess command line so the module's
    own build.py never has to re-derive it.

    NS-46 (RQ-5): `remotes_state` is THIS dispatcher's resolved switch
    (main()'s `--remotes`/team-file decision). When given, it is forwarded to
    the child as REMOTES_ENV_VAR, so the component build decides the same
    way the root did - `build.py df --remotes off` must not quietly become
    "on" inside the component because the child re-read the team file
    without the flag. adas_build_tools then adds `-nr` to its own conan
    install/create when the switch is off. None (the default, every existing
    direct caller) leaves the child's environment untouched."""
    mode = ROOT_DEFAULT_MODE
    script = os.path.join(ROOT, "modules", module, "scripts", "build.py")
    if not os.path.exists(script):
        print(f"ERROR: module '{module}' has no scripts/build.py")
        sys.exit(1)

    apply_conan_home(mode, "build")

    pkg_map = package_to_module_map()
    deps = forward_closure({module}, project, pkg_map) - {module}
    missing_pin = missing_toolchain_pin(deps | {module})
    missing = missing_cache_refs(deps, project, platform)
    if missing_pin or missing:
        for ref in missing_pin:
            log(f"ERROR: {ref} is not in this machine's Conan cache "
                "(no local cache recipe, or its pin disagrees with modules/toolchain's "
                f"own checkout) - run {setup_command()} --no-submodules (it puts the build "
                "machinery in the cache and leaves your modules as they are; D4: setup "
                "prepares, build builds).")
        for dep, ref in missing:
            log(f"ERROR: {dep} ({ref}) is not in this machine's Conan cache for "
                f"platform {platform} - run "
                f"python scripts/setup.py --prepare {module} -t {target} -p {platform} "
                f"-P {project}  (or --with {dep} to build it here instead).")
        return False

    # NS-05a (D4a, STEP 3): refuse a stale cache, never silently refresh it.
    # Only checked for deps actually resolving FROM the cache (never a dep
    # being built here, which has nothing here to compare against).
    outdated = outdated_format_refs(deps)
    if outdated:
        for dep in outdated:
            log(outdated_format_message(dep, module, target, platform, project))
        return False
    stale, unrecorded = stale_cache_refs(deps)
    if unrecorded:
        # NS-37 (RQ-4, cache_first_no_server_plan.md): NS-05a's grace
        # period for a missing freshness record is over. D3 means the
        # bundle never carries a first-party library, and --prepare/
        # setup.bat have recorded a fingerprint for every ref they put in
        # the cache since NS-28 - so a first-party ref resolved from the
        # cache with no record can now only come from a hand-run `conan
        # create`, a pre-NS-28 setup, or a copied cache, and none of those
        # is trustworthy enough to link silently (RQ-4: refuse, never link
        # something stale silently - and "stale or not" is unanswerable
        # with no record to compare against).
        for line in unrecorded_message(unrecorded, module, target, platform, project):
            log(line)
        return False
    if stale:
        for dep, old_git, new_git in stale:
            log(stale_cache_message(dep, module, target, platform, project,
                                    old_git, new_git))
        return False

    # D2/D9: dependencies that are not checked out are packages - the walk
    # above stopped at them. In the cache -> silent; else refuse.
    absent = absent_first_party_refs(forward_closure({module}, project, pkg_map), project)
    errors = absent_dep_problems(absent, module, target, platform, project)
    for line in errors:
        log(line)
    if errors:
        return False

    build_dir = delegate_build_dir(module, project, target, platform)
    log_dir = ws_logs_dir()
    cmd = [sys.executable, script, "-P", project, "-t", target, "-p", platform,
           "--log-dir", log_dir, "--mode", mode, "--build-dir", build_dir]
    if clean:
        cmd.append("--clean")
    if no_log:
        cmd.append("--no-log")
    if update_lock:
        cmd.append("--update-lock")  # WP-13: the component re-resolves its own lock

    # flush before handing stdout to the child: without it these two lines sit
    # in this process's buffer while the child writes straight to the terminal,
    # so a child error appears ABOVE the header describing what was being built.
    print(f"[build] {module} (project={project} target={target} platform={platform} "
          f"mode={mode})", flush=True)
    print(f"[build] -> {build_dir}", flush=True)
    if remotes_state is None:
        proc = subprocess.run(cmd, cwd=os.path.join(ROOT, "modules", module))
    else:
        proc = subprocess.run(cmd, cwd=os.path.join(ROOT, "modules", module),
                              env=dict(os.environ,
                                       **{REMOTES_ENV_VAR: "on" if remotes_state else "off"}))
    if os.path.isdir(build_dir):
        # RP-05: written after the run so --clean cannot delete it.
        with open(os.path.join(build_dir, "ws_manifest.txt"), "w", encoding="utf-8",
                  newline="\n") as f:
            f.write(delegate_manifest_text(module, project, target, platform, mode))
    return proc.returncode == 0


# ---------------------------------------------------------------------------
# Fan-out mode - every module of the project, each built standalone
# ---------------------------------------------------------------------------


def module_projects(mod):
    """Which projects this module declares, straight off its own
    conf/build.yml's variants: keys."""
    conf = load_module_conf(mod)
    if conf is None:
        return []
    return list((conf.get("variants") or {}).keys())


def all_projects():
    """Every project any module builds for. A project exists precisely when
    some module says it does - there is no separate registry to keep in sync
    (plan.md item 14 follow-up; matches a comparable production repo, where each
    component's own file declares its variants: and no central roster exists)."""
    projects = set()
    for mod in module_dirs():
        projects.update(module_projects(mod))
    return sorted(projects)


def project_modules(project):
    """Every module that declares this project - derived, never listed.

    This used to read a `modules:` roster out of conf/<project>.yaml. That
    file is gone (plan.md item 14 follow-up): a hand-maintained roster can
    drift from reality and silently exclude a real module, which it actually
    did - `shared_config` had a real, buildable `sil` target and was missing
    from both conf/*.yaml, so every fan-out build skipped it and still exited
    0. Deriving from each module's own conf/build.yml makes that class of bug
    unrepresentable: project membership is one fact, in one place, owned by
    the module it describes."""
    return [mod for mod in module_dirs() if project in module_projects(mod)]


def placeholder_modules():
    """Module directories with no conf/build.yml at all - the empty submodule
    placeholders. Reported once by fan-out so they stay visible rather than
    silently invisible now that nothing lists them centrally."""
    return [mod for mod in module_dirs() if load_module_conf(mod) is None]


def run_fanout(modules, project, target, platform, clean, no_log, remotes_state=None,
               update_lock=False):
    """WP-23 (conan_environment_plan.md §6): fan-out's own default is
    "package", not "develop" - unlike delegate/aggregate, it is this file's
    own docstring that calls fan-out "the CI job", each module "built
    standalone in dependency order". That is exactly the submodule-
    invocation semantic (corner case 18: CI wants the packaged path, the one
    closest to what a fresh machine actually does), even though fan-out is
    literally started from the superproject - the rule is "where you start
    the build", read as "what is being validated", not "which process
    argv[0] happened to be". NS-32: no `mode` parameter - package is the only
    mode."""
    pkg_map = package_to_module_map()
    ordered = topo_sort(set(modules), project, pkg_map)

    print(f"Fan-out build: project={project} target={target} platform={platform}")
    print(f"Modules in scope: {', '.join(ordered)}")
    placeholders = placeholder_modules()
    if placeholders:
        print(f"Not yet buildable (no conf/build.yml): {', '.join(placeholders)}")
    print()

    results = {}
    for module in ordered:
        # Skipping rather than failing is deliberate, and the one place fan-out
        # differs from naming a module directly: a batch across every module
        # must tolerate a module that simply doesn't build this target+platform
        # (docs/build_grammar.md §4), while an explicit single-module request
        # must never silently do nothing.
        if not module_declares(module, project, target, platform):
            print(f"[skip]  {module}: does not declare {target}/{platform} for {project}")
            results[module] = "skipped"
            continue
        results[module] = "built" if run_delegate(
            module, project, target, platform, clean, no_log,
            remotes_state=remotes_state,
            **({"update_lock": True} if update_lock else {})) else "failed"
        print()

    # Summary log for the batch. Deliberately a summary, not a concatenation:
    # each module already wrote its own full log next to its own output, so
    # this records what ran, what it produced, and where to look next - the
    # thing you actually need when one module out of six failed an hour ago.
    lines = ["Summary:"]
    for module, status in results.items():
        lines.append(f"  {status:8s} {module}")
    for line in lines:
        print(line)

    if not no_log:
        summary_dir = ws_logs_dir()
        os.makedirs(summary_dir, exist_ok=True)
        summary_path = os.path.join(
            summary_dir, f"fanout-{project}-{target}-{platform}.log")
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(f"Fan-out build: project={project} target={target} platform={platform}\n")
            f.write(f"Modules in scope: {', '.join(ordered)}\n")
            if placeholders:
                f.write(f"Not yet buildable (no conf/build.yml): {', '.join(placeholders)}\n")
            f.write("\n")
            for module, status in results.items():
                f.write(f"  {status:8s} {module}\n")
                if status != "skipped":
                    f.write(f"           log: {delegate_log_path(module, project, target, platform)}\n")
        print(f"\nSummary log: {summary_path}")

    return "failed" not in results.values()


# ---------------------------------------------------------------------------
# Unified super-build aggregator (plan.md item 13,
# docs/build_superbuild_aggregator_plan.md)
# ---------------------------------------------------------------------------

_COMPILED_PACKAGE_TYPES = ("shared-library", "static-library", "application")


def version_agreement_violations(closure, project, pkg_map):
    """AB-07 (aggregate_build_integrity_plan.md G4/D3): every first-party
    package must be requested at one identical version by every closure module
    that requires it, and that version must equal the checkout's own
    module_version() - generate_aggregate_conanfile() drops refs to in-tree
    modules before Conan sees them, so Conan's own conflict detection cannot
    catch this. Applied to every closure module, not only in-tree ones: a
    pkg_only module resolves from the cache (setup.py prepares it, NS-05/NS-34).
    Returns sorted (package, requester, requested, actual) tuples; `actual` is
    the checkout version, or "<v>" per other requester when requesters disagree
    among themselves."""
    requested = {}  # package -> {requester module: requested version}
    for mod in closure:
        for ref in raw_requires_for(mod, project, "requires"):
            pkg = ref.split("/")[0]
            if pkg not in pkg_map or pkg_map[pkg] == mod:
                continue
            version = ref.split("/", 1)[1].split("@")[0] if "/" in ref else ""
            requested.setdefault(pkg, {})[mod] = version
    violations = []
    for pkg, by_mod in requested.items():
        actual = module_version(pkg_map[pkg])
        for mod, version in by_mod.items():
            if actual is not None and version != actual:
                violations.append((pkg, mod, version, actual))
            elif len(set(by_mod.values())) > 1:
                others = sorted({v for m, v in by_mod.items() if m != mod and v != version})
                violations.append((pkg, mod, version, ", ".join(others)))
    return sorted(violations)


def reverse_rebuild_violations(total, closure, project, pkg_map):
    """AB-05 (aggregate_build_integrity_plan.md G3, D1/D2): rebuilt => its
    users rebuilt. For each compiled module X in `total`, every closure module
    that transitively requires X and is not itself in `total` would link a
    binary built against the old X. Pure-data modules are exempt as X (no
    binary to mismatch). The primary needs no exclusion: nothing in the
    closure requires it. Returns sorted (X, user) pairs; the caller prints
    them and refuses (never auto-adds)."""
    violations = []
    for x in total:
        if module_package_type(x) not in _COMPILED_PACKAGE_TYPES:
            continue
        for y in closure - total:
            if x in forward_closure({y}, project, pkg_map) - {y}:
                violations.append((x, y))
    return sorted(violations)


def ws_folder_name(target, platform, project, primary, with_mods, with_all):
    """RP-04 (root_build_package_mode_plan.md D5): the ONE folder grammar for
    every root build, delegate and aggregate alike -
    `conan_workarea/build-<target>-<platform>-<project>-<primary>-<mode>-<scope>`,
    seven FIXED fields, `name.split("-", 6)` always yields
    `["build", target, platform, project, primary, "pkg", scope]`.
    `<mode>` is the literal `pkg`, FIXED (NS-32): develop mode was removed
    2026-09-22 (RD-03), so the field can only ever be `pkg`; it is kept, not
    dropped, because renaming every build folder a third time costs more than
    the one constant field saves. A `dev`-era folder from before 2026-09-22
    is still readable - same seven fields, `dev` in place of `pkg`. `<scope>` is `solo` (no
    --with/--with-all: delegate) or `agg` (aggregate, any tick list). No hash:
    the same command reuses the same folder, and a different tick list reuses
    it too (CMake reconfigures) - WHICH modules were ticked lives in
    ws_manifest.txt and the log header, rewritten every run, not in the name.
    Supersedes the AB-03 `with<N>-<hash8>`/`all` scope, which left one folder
    per tick list ever tried.

    `project` and `platform` stay in the name (plan.md items 13/14): `base df`
    and `cus1 df`, or `vs2026` and `ubuntu_gcc`, must never collide."""
    scope = "agg" if (with_all or with_mods) else "solo"
    return f"build-{target}-{platform}-{project}-{primary}-pkg-{scope}"


def parse_editable_list(stdout):
    """AB-01: `conan editable list --format=json` stdout -> {ref: path}, the
    ref WITHOUT revision. Any shape other than a JSON object of objects is a
    ValueError - a registration list nobody can read is never guessed at."""
    try:
        data = json.loads(stdout)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        raise ValueError(f"not JSON ({exc})")
    if not isinstance(data, dict) or not all(isinstance(v, dict) for v in data.values()):
        raise ValueError("expected a JSON object of {ref: {path: ...}}")
    return {ref.split("#", 1)[0]: (entry.get("path") or "") for ref, entry in data.items()}


def read_editable_registrations():
    """AB-01: the ACTIVE CONAN_HOME's real editable registrations (call after
    apply_conan_home()). Returns {ref: path}; any failure is a ValueError -
    the header must never claim a kind it could not read."""
    try:
        proc = subprocess.run(["conan", "editable", "list", "--format=json"],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
    except OSError as exc:
        raise ValueError(f"could not run conan ({exc})")
    if proc.returncode != 0:
        raise ValueError(f"conan editable list exited {proc.returncode}: "
                         f"{(proc.stderr or '').strip()[:200]}")
    return parse_editable_list(proc.stdout)


def aggregate_module_plan(closure, compiled_intree, pkg_only, registrations):
    """AB-01 (aggregate_build_integrity_plan.md D4): what each first-party
    closure module will be, before conan runs. Returns
    {module: {"version", "kind", "path"}}, kind in in-tree / editable /
    package. compiled_intree -> in-tree (add_subdirectory, modules/<m>).
    RD-03 (remove_develop_mode_plan.md): the editable_only bucket
    (register_editable(), modules/<m>) is gone - nothing is ever
    auto-registered any more. `pkg_only` is still read, not assumed: a
    module is "editable" iff its name/version ref is in `registrations`
    ({ref: path} from the active CONAN_HOME, see
    read_editable_registrations) - a stray hand-registered editable (or a
    leftover from before this removal) is still detected and reported
    honestly, never silently treated as a package."""
    plan = {}
    for mod in closure:
        version = module_version(mod) or "unknown"
        if mod in compiled_intree:
            kind, path = "in-tree", os.path.join("modules", mod)
        else:
            reg_path = registrations.get(f"{module_package_name(mod)}/{version}")
            if reg_path is not None:
                kind, path = "editable", os.path.dirname(reg_path) or reg_path
            else:
                kind, path = "package", "(conan cache)"
        plan[mod] = {"version": version, "kind": kind, "path": path}
    return plan


def format_module_plan(plan, order):
    """AB-01: one aligned `name  version  kind  path` line per module."""
    width = max((len(m) for m in order), default=0)
    vwidth = max((len(plan[m]["version"]) for m in order), default=0)
    return [f"[aggregate]   {m:<{width}}  {plan[m]['version']:<{vwidth}}  "
            f"{plan[m]['kind']:<8}  {plan[m]['path']}" for m in order]


# Conan's own graph "binary" values -> the header's vocabulary (AB-02).
_BINARY_TO_KIND = {"Editable": "editable", "Cache": "package", "Download": "package",
                   "Update": "package", "Build": "package"}


def resolved_kind_mismatches(graph_json, plan, pkg_map, primary):
    """AB-02 (D4): the resolved binary kind of every first-party graph node vs
    the header's kind. Returns (resolved, mismatches): resolved is
    {module: actual kind}; mismatches is sorted (module, expected, actual).
    An in-tree module must NOT appear as a node at all (that is double
    resolution); a module expected editable/package must appear, except the
    primary, which nothing in the closure requires."""
    resolved = {}
    for ref, node in aggregate_graph_nodes(graph_json):
        mod = pkg_map.get(ref.split("/")[0])
        if mod is not None:
            binary = node.get("binary") or "unknown"
            resolved[mod] = _BINARY_TO_KIND.get(binary, binary.lower())
    mismatches = []
    for mod, entry in plan.items():
        expected, actual = entry["kind"], resolved.get(mod, "absent")
        if expected == "in-tree":
            if mod in resolved:
                mismatches.append((mod, "in-tree (no graph node)", actual))
        elif actual != expected and not (mod == primary and mod not in resolved):
            mismatches.append((mod, expected, actual))
    return resolved, sorted(mismatches)


def _path_outside_root(path):
    """CE-35(c) (conan_environment_plan.md): True if `path` does not live
    under this checkout's own ROOT - the stale-copy case (a registration
    pointing at a DIFFERENT checkout entirely) earns a more specific
    warning line at the call site. Best-effort: an unresolvable or
    cross-drive (Windows) path is treated as outside, never as a crash -
    "probably a stale copy" is the safer default than silently calling
    an unparseable path "fine"."""
    try:
        return os.path.commonpath([os.path.abspath(path), ROOT]) != ROOT
    except ValueError:
        return True  # e.g. a different drive letter on Windows


def first_party_package_mode_editable_violations(resolved, plan, registrations, mode):
    """CE-35(c) (conan_environment_plan.md): in package mode, a first-
    party ref resolving Editable is never acceptable - not even when it
    exactly matches what aggregate_module_plan() already predicted, so
    resolved_kind_mismatches() (AB-01/AB-02, just above) finds no
    disagreement to flag. A correctly-PREDICTED editable is still a
    POLICY violation, not merely a consistency bug - the AB-01/AB-02
    machinery only ever asks "did the header guess right", never "should
    this be allowed at all". Real evidence, a second corporate PC,
    2026-09-23: a package-mode aggregate resolved interfaces/mathlib/sim/
    shared_config as Editable pointing at a DIFFERENT, stale checkout
    entirely (D:\\df\\1v-superproject, this run was D:\\1v-superproject) -
    both plan and resolved agreed it would be Editable, so AB-02's own
    mismatch check had nothing to flag, and the build proceeded to link
    `viz` against stale `sim` headers ("'TranslatingReader': is not a
    member of 'simcore::io'").

    Returns a sorted list of (module, ref, path) for every module (other
    than a compiled-in-tree one, which is never a Conan node at all)
    whose RESOLVED kind is "editable" when `mode == "package"`; always
    empty for any other mode (there is currently only one real mode,
    RD-03/remove_develop_mode_plan.md, but this stays an explicit
    checked condition rather than an unconditional refusal, matching
    this function's own name)."""
    if mode != "package":
        return []
    violations = []
    for mod, kind in resolved.items():
        if kind != "editable" or plan.get(mod, {}).get("kind") == "in-tree":
            continue
        version = plan.get(mod, {}).get("version", "unknown")
        ref = f"{module_package_name(mod)}/{version}"
        path = registrations.get(ref) or plan.get(mod, {}).get("path", "(unknown path)")
        violations.append((mod, ref, path))
    return sorted(violations)


def rebuild_closure(total, closure, project, pkg_map):
    """AB-05/AB-10: `total` grown to a fixed point under reverse_rebuild_violations -
    the smallest module set that rebuilds every user of everything it rebuilds.
    Only ever printed as a suggestion (D1), never applied."""
    needed = set(total)
    while True:
        more = {u for _, u in reverse_rebuild_violations(needed, closure, project, pkg_map)}
        if not more:
            return needed
        needed |= more


def resolved_lib_dirs(graph_json, pkg_map):
    """AB-10: {module: [libdirs]} from each first-party graph node's
    cpp_info.root.libdirs - for an editable these are the module's build output
    (base_recipe.py layout()), which is where its libraries must already be."""
    return {pkg_map[ref.split("/")[0]]: _node_libdirs(node)
            for ref, node in aggregate_graph_nodes(graph_json)
            if ref.split("/")[0] in pkg_map}


def resolved_package_folders(graph_json, pkg_map):
    """AB-02: {module: package_folder} for every first-party graph node - for
    an editable this is where its build output really is, the "which path"
    the header cannot know before conan runs. "" when Conan reports none."""
    return {pkg_map[ref.split("/")[0]]: node.get("package_folder") or ""
            for ref, node in aggregate_graph_nodes(graph_json)
            if ref.split("/")[0] in pkg_map}


def format_resolved_table(plan, resolved, folders, order, libdirs=None):
    """AB-02: one line per module - header kind, resolved kind, real path. An
    editable that reports libdirs shows those (AB-10), not the module root."""
    lines = []
    for mod in order:
        if plan[mod]["kind"] == "in-tree":
            where = f"in-tree ({plan[mod]['path'].replace(os.sep, '/')})"
        elif resolved.get(mod) == "editable" and (libdirs or {}).get(mod):
            where = "libdirs: " + "; ".join(libdirs[mod])
        else:
            where = folders.get(mod) or "(no package_folder reported)"
        lines.append(f"[aggregate]   {mod}: header {plan[mod]['kind']}, "
                     f"resolved {resolved.get(mod, 'no graph node')}  {where}")
    return lines


def ws_manifest_text(target, platform, project, primary, with_mods, with_all, mode, plan, order):
    """AB-04: ws_manifest.txt - plain `key: value` lines that decode the
    folder name without re-running: the exact --with list (the folder name
    no longer carries it, RP-04), the mode, the scope field, and the AB-01
    per-module kind table."""
    folder = ws_folder_name(target, platform, project, primary, with_mods, with_all)
    lines = [f"primary: {primary}", f"project: {project}", f"target: {target}",
             f"platform: {platform}", f"mode: {mode}",
             f"with: {'(all)' if with_all else ' '.join(sorted(with_mods or [])) or '(none)'}",
             f"scope: {folder.split('-', 6)[6]}"]
    lines += [f"module: {m} {plan[m]['version']} {plan[m]['kind']} {plan[m]['path']}"
              for m in order]
    return "\n".join(lines) + "\n"


def delegate_manifest_text(module, project, target, platform, mode):
    """RP-05: ws_manifest.txt for a delegate (solo) build - same keys as
    ws_manifest_text, `with: (none)`, no per-module table (nothing ticked)."""
    folder = delegate_folder_name(module, project, target, platform)
    return "\n".join([f"primary: {module}", f"project: {project}", f"target: {target}",
                      f"platform: {platform}", f"mode: {mode}", "with: (none)",
                      f"scope: {folder.split('-', 6)[6]}"]) + "\n"


def remove_stale_build_dirs(ws_dir, compiled_intree):
    """RP-06 (D6): the folder always matches its manifest. Deletes `_bd_<m>/`
    for any module not in-tree this run, logged by name. Only `_bd_*`
    directories are considered - nothing else in the folder is touched.
    Returns the removed module names."""
    removed = []
    for entry in sorted(os.listdir(ws_dir)):
        path = os.path.join(ws_dir, entry)
        if entry.startswith("_bd_") and os.path.isdir(path) and entry[4:] not in compiled_intree:
            log(f"[aggregate] removing stale {entry}/ ({entry[4:]} is not in-tree this run)")
            shutil.rmtree(path)
            removed.append(entry[4:])
    return removed


def generate_aggregate_conanfile(ws_dir, project, closure, compiled_intree):
    """Synthetic, regenerated-every-run conanfile.py for the aggregate tree -
    same requirements()/build_requirements()/generate() shape every real
    component's own conanfile.py already uses (docs/build_superbuild_aggregator_plan.md
    §5 step 2), just collecting the union of every module in `closure`'s own
    requires:/tool_requires:, minus any ref whose package resolves to a
    module in `compiled_intree` (those are add_subdirectory()'d in-tree
    instead - the double-resolution guard this whole design depends on,
    docs/build_regression_tests.md §6.1)."""
    pkg_map = package_to_module_map()
    requires = set()
    tool_requires = set()
    for mod in closure:
        for ref in raw_requires_for(mod, project, "requires"):
            dep_mod = pkg_map.get(ref.split("/")[0])
            if dep_mod in compiled_intree:
                continue
            requires.add(ref)
        for ref in raw_requires_for(mod, project, "tool_requires"):
            tool_requires.add(ref)

    def method_body(refs, call):
        if not refs:
            return "        pass\n"
        return "".join(f'        self.{call}("{ref}")\n' for ref in sorted(refs))

    content = f'''"""Generated by the superproject scripts/build.py aggregator (plan.md item 13) -
regenerated fresh on every aggregator invocation, do not hand-edit."""
from conan import ConanFile
from conan.tools.cmake import CMakeDeps, CMakeToolchain


class AggregateConan(ConanFile):
    name = "adas-aggregate"
    version = "0.0.0"
    package_type = "application"
    settings = "os", "arch", "compiler", "build_type"
    options = {{"project": ["ANY"]}}
    default_options = {{
        "project": "{project}",
        "protobuf/*:shared": False,
        "protobuf/*:with_zlib": False,
        "yaml-cpp/*:shared": False,
    }}

    def requirements(self):
{method_body(requires, "requires")}
    def build_requirements(self):
{method_body(tool_requires, "tool_requires")}
    def generate(self):
        tc = CMakeToolchain(self)
        tc.generate()
        deps = CMakeDeps(self)
        deps.build_context_activated = ["protobuf"]
        deps.build_context_suffix = {{"protobuf": "_BUILD"}}
        deps.generate()
'''
    with open(os.path.join(ws_dir, "conanfile.py"), "w", encoding="utf-8") as f:
        f.write(content)


def generate_aggregate_cmakelists(ws_dir, project, target, compiled_intree, ordered_mods):
    """The actual umbrella CMakeLists.txt - add_subdirectory() for every
    in-tree module, in dependency order, plus the same top-level cache
    variables each module's own CMakeLists.txt already guards with
    if(NOT DEFINED ...) (docs/build_superbuild_aggregator_plan.md §4/§5 step 3)."""
    lines = [
        "cmake_minimum_required(VERSION 3.22)",
        "project(adas-aggregate LANGUAGES CXX)",
        "set(CMAKE_CXX_STANDARD 17)",
        "",
        f'set(TARGET_TYPE {target} CACHE STRING "Build target" FORCE)',
        f'set(ADAS_PROJECT {project} CACHE STRING "Active project" FORCE)',
        'set(BUILD_TESTING OFF CACHE BOOL "Tests are standalone-only, never part of the aggregate" FORCE)',
    ]
    if "df" in compiled_intree:
        funcs = enabled_functions_for("df", project)
        lines.append(f'set(ENABLED_FUNCTIONS "{funcs}" CACHE STRING "Enabled df functions" FORCE)')
    lines.append("")
    for mod in ordered_mods:
        src = os.path.join(ROOT, "modules", mod).replace("\\", "/")
        lines.append(f'add_subdirectory("{src}" "_bd_{mod}")')
    content = "\n".join(lines) + "\n"
    with open(os.path.join(ws_dir, "CMakeLists.txt"), "w", encoding="utf-8") as f:
        f.write(content)


def partition_aggregate_modules(total, closure):
    """Split an aggregate's modules into the three roles the build treats
    differently. `total` is what the user named (primary + --with, or the
    whole closure under --with-all); `closure` is the primary's full
    first-party dependency closure.

        compiled_intree - named AND has a compiled target: add_subdirectory()
        data_only       - named but nothing to compile: packaged from the
                          checkout (A, package_named_data_modules())
        pkg_only        - NOT named: comes from the Conan cache, and stops
                          the build if it is missing

    Extracted from run_aggregate_build() so it can be tested for real. The
    first version of its test recomputed this split inline, and therefore
    passed against a build.py mutated to package modules nobody had named -
    the exact silent-bug door D4 exists to keep shut, missed by the test
    written to guard it (the NS-31 failure mode).

    The invariant that matters: `data_only` is always a subset of `total`.
    A module outside `total` must never be built or packaged here, whatever
    its kind.
    """
    compiled_intree = {m for m in total
                       if module_package_type(m) in _COMPILED_PACKAGE_TYPES}
    data_only = set(total) - compiled_intree
    pkg_only = set(closure) - set(total)
    return compiled_intree, data_only, pkg_only


def missing_cache_ref_message(dep, ref, primary, target, platform, project):
    """The refusal text for a dependency that must come from the cache and
    isn't there. Split out of run_aggregate_build()'s guard so it is directly
    unit-testable (same reasoning as _remote_listing() in setup.py) - the
    first version of its test mirrored this logic instead of calling it, and
    so passed against a deliberately broken implementation.

    RQ-9: the alternative named must actually work. `--with <dep>` is real
    advice for BOTH kinds of module now (A, 2026-09-25): a compiled one
    becomes an in-tree source target, and a pure-data one is packaged from
    the checkout by package_named_data_modules(). The wording differs only
    because "build it here" means two different things - compiled from
    source vs packaged from the checkout - and saying which one the reader
    is about to get is worth one clause.

    (History, so it is not re-broken: for one commit this function told the
    reader that --with "cannot help" for a data module. That was true of the
    code at the time and is the symptom A fixed in the right layer. The fix
    is the feature, not the message.)
    """
    if module_package_type(dep) in _COMPILED_PACKAGE_TYPES:
        alternative = f"  (or --with {dep} to build it from source in this aggregate)"
    else:
        alternative = (f"  (or --with {dep} to package it from your checkout in "
                       "this aggregate - it is a data package, so there is nothing "
                       "to compile)")
    return (f"ERROR: {dep} ({ref}) is not in this machine's Conan cache for "
            f"platform {platform} - run "
            f"python scripts/setup.py --prepare {primary} -t {target} -p {platform} "
            f"-P {project}{alternative}.")


def package_named_data_modules(data_mods, project, target, platform, build_type, log=print):
    """A (2026-09-25): build what the user named, including a PURE-DATA module.

    D4's own words: *"build.py compiles **only** the primary and whatever
    `--with` names"*, and *"changing a module means ticking it (--with), which
    builds it from source here"*. build.py honoured that for compiled modules
    and silently refused for data ones - they were routed to pkg_only and
    demanded from the cache instead, so `--with shared_config` and
    `--with-all` both stopped on a cold machine with a refusal whose own
    suggested fix could not work. That was a bug against D4, not a limit of
    it: a data module cannot be an in-tree CMake target (nothing to compile),
    but it CAN be packaged from this checkout, which is what "build it" means
    for a package that is only data.

    The safety line D4 actually draws is *build what you named, never touch
    what you didn't* - which is why this function is only ever called with
    modules already in `total` (the primary plus --with/--with-all). A data
    module you did NOT name still comes from the cache and still stops the
    build if it is missing. That guard does not move.

    Skips a module whose binary is cached AND whose recorded fingerprint
    still matches the checkout (the NS-28 question, asked with build.py's own
    existing checks) - so a repeat build pays nothing. Rebuilds and re-records
    otherwise, which is also what closes the NS-37 trap: a package this
    function creates always carries a freshness record, so the guard below
    can never refuse it as unverifiable.

    Returns a list of (module, ref) that failed.
    """
    failed = []
    for mod in sorted(data_mods):
        pkg_name = module_package_name(mod)
        version = module_version(mod)
        if not pkg_name or not version:
            failed.append((mod, "<unknown ref>"))
            continue
        ref = f"{pkg_name}/{version}"
        missing = missing_cache_refs({mod}, project, platform)
        outdated = outdated_format_refs({mod})
        stale, unrecorded = stale_cache_refs({mod})
        if not missing and not outdated and not stale and not unrecorded:
            log(f"[aggregate] {mod} ({ref}): data package, already cached and "
                "unchanged since it was built - conan create skipped.")
            continue
        why = ("not in the cache" if missing
               else "its freshness record is in an older fingerprint format" if outdated
               else "its source changed since it was cached" if stale
               else "no freshness record")
        log(f"[aggregate] {mod} ({ref}): data package you asked for ({why}) - "
            f"packaging it from modules/{mod} ...")
        # NS-53 (RV-3): the same post-create check setup.py --prepare passes -
        # `conan create` returning 0 is not by itself proof a matching binary
        # landed, and recording one that did not would call it fresh.
        profile_settings = check_conan_resolution.pinned_profile_settings(platform)
        ok = create_and_record_module(
            mod, os.path.join(ROOT, "modules", mod), ref, project, build_type,
            profile_args(platform), ROOT, target=target, platform=platform,
            verify_cached=(None if profile_settings is None else
                           (lambda r=ref: check_conan_resolution._cache_matches_profile(
                               r, profile_settings))),
            log=log)
        if not ok:
            failed.append((mod, ref))
    return failed


def data_only_in_tree_notice(data_only, with_all, with_mods):
    """The NOTE an aggregate prints when the user asked for dependencies
    in-tree and one of them cannot be. Returns None when there is nothing to
    say. Split out for the same testability reason as the function above.

    --with-all's name promises every dependency becomes an in-tree source
    target. A pure-data module has no compiled CMake target to
    add_subdirectory() (module_package_type()), so it is *packaged from the
    checkout* instead (A - package_named_data_modules()). The build does the
    right thing either way; this line exists so the module table above, which
    shows it as `package`, does not read as the build ignoring your tick.

    Informational only: it names no command, because after A there is nothing
    for the reader to run.
    """
    if not data_only:
        return None
    if not (with_all or (set(with_mods or []) & set(data_only))):
        return None
    return (f"[aggregate] NOTE: {', '.join(sorted(data_only))} - data package(s), "
            "nothing to compile: packaged from your checkout rather than built "
            "in-tree. No action needed.")


def aggregate_lock_key(ws_dir, compiled_intree, data_only):
    """WP-13 / NS-61: the aggregate's lock key - its build folder's name plus a
    short hash of the modules built HERE, because the folder name alone is the
    same for every tick list while the cache-resolved requirement set is not:
    ticking a different `--with` must not turn a requirement into 'not in the
    lockfile'. The set of modules built here decides what is taken from the
    cache, so it belongs in the key."""
    built_here = ",".join(sorted(set(compiled_intree) | set(data_only)))
    return f"{os.path.basename(ws_dir)}-{hashlib.sha1(built_here.encode('utf-8')).hexdigest()[:8]}"


def run_aggregate_build(project, primary, target, platform, with_mods, with_all, clean, no_log,
                        mode=ROOT_DEFAULT_MODE, remotes_state=True, update_lock=False):
    """remotes_state (NS-05, STEP 2, D1/RQ-5) - True unless the caller's own
    remotes_enabled() said off; drives whether the `conan install` below
    carries `-nr` (never a remote when remotes are off). Defaulted True so
    every existing direct caller/test that doesn't pass it keeps today's
    behaviour (a real URL/remotes-on machine) rather than silently
    changing under them."""
    if not is_valid_module(primary):
        print(f"ERROR: unknown module '{primary}' - no modules/{primary}/conanfile.py")
        sys.exit(1)

    generator_flags = _AGGREGATE_GENERATORS.get(platform)
    if generator_flags is None:
        print(f"ERROR: the aggregator has no CMake generator mapping for platform "
              f"'{platform}' yet - known: {', '.join(sorted(_AGGREGATE_GENERATORS))}")
        sys.exit(1)

    build_type = "Debug" if platform.endswith("_debug") else "Release"

    if with_all:
        # W3: --with-all compiles the whole closure, so initialise it - and
        # repeat, because a newly checked-out module can declare more
        # dependencies (the graph is discovered from real files).
        while True:
            absent = absent_first_party_refs(
                forward_closure({primary}, project, package_to_module_map()), project)
            if not absent or not init_absent_modules(sorted(absent)):
                break  # nothing left, or no progress: the D9 gate below judges the rest

    pkg_map = package_to_module_map()
    closure = forward_closure({primary}, project, pkg_map)  # includes primary

    if with_all:
        total = set(closure)
    elif with_mods:
        allowed = closure - {primary}
        unknown = set(with_mods) - allowed
        if unknown:
            print(f"ERROR: --with names module(s) not in '{primary}'s dependency "
                  f"closure: {', '.join(sorted(unknown))} - valid: {', '.join(sorted(allowed)) or '(none)'}")
            sys.exit(1)
        total = {primary} | set(with_mods)
    else:
        total = {primary}

    # RP-03 (D4) / RD-03: package mode is the only mode - nothing is ever
    # registered editable. A (2026-09-25): a pure-data module the user NAMED
    # is packaged from the checkout by package_named_data_modules() below
    # (D4: "build.py compiles only the primary and whatever --with names");
    # one they did not name stays in pkg_only and comes from the cache.
    compiled_intree, data_only, pkg_only = partition_aggregate_modules(total, closure)

    ordered_mods = topo_sort(compiled_intree, project, pkg_map)

    # Log goes to the central conan_workarea/logs/ (not inside ws_dir), named after
    # ws_dir's folder itself so the filename alone identifies it as THIS aggregate build.
    # Living outside ws_dir, it also survives this build's own --clean (which
    # wipes ws_dir). Opened BEFORE the AB-07/AB-05 guards (AB-08 item 5) so a
    # refused build still leaves a log; only the central logs dir is created
    # here - ws_dir itself is neither created nor cleaned until the guards pass.
    ws_dir = os.path.join(ROOT, "conan_workarea",
                          ws_folder_name(target, platform, project, primary, with_mods,
                                         with_all))
    log_path = None if no_log else open_log(ws_logs_dir(), os.path.basename(ws_dir))
    try:
        # AB-07 / AB-05: pure checks, run before apply_conan_home() or any conan
        # command so a refused build touches nothing (D1 - refuse, never auto-add).
        version_bad = version_agreement_violations(closure, project, pkg_map)
        if version_bad:
            log("ERROR: first-party version disagreement (aggregate would build a mixed set):")
            for pkg, requester, requested, actual in version_bad:
                log(f"  {pkg}: {requester} requests {requested}, but {actual} "
                    f"(checkout version / other requesters)")
            sys.exit(1)

        rebuild_bad = reverse_rebuild_violations(total, closure, project, pkg_map)
        if rebuild_bad:
            log("ERROR: a rebuilt module is used by module(s) that would NOT be rebuilt "
                "(they would link their old binary against the old build):")
            for rebuilt, user in rebuild_bad:
                log(f"  {user} uses {rebuilt} (rebuilt via --with) but is not in --with")
            extended = sorted(rebuild_closure(total, closure, project, pkg_map) - {primary})
            log("Re-run with the extended --with list:")
            log(f"  python scripts/build.py {primary} -t {target} -p {platform} -P {project} "
                f"--with {' '.join(extended)}")
            sys.exit(1)

        absent = absent_first_party_refs(closure, project)

        apply_conan_home(mode, "aggregate")

        if clean and os.path.isdir(ws_dir):
            log(f"[aggregate] cleaning {ws_dir}")
            shutil.rmtree(ws_dir)
        os.makedirs(ws_dir, exist_ok=True)

        try:
            registrations = read_editable_registrations()
        except ValueError as exc:
            log(f"ERROR: cannot read the editable registrations of CONAN_HOME "
                f"({os.environ.get('CONAN_HOME') or 'Conan default'}): {exc}")
            sys.exit(1)
        plan = aggregate_module_plan(closure, compiled_intree, pkg_only, registrations)
        plan_order = topo_sort(closure, project, pkg_map)
        log(f"[aggregate] primary: {primary} (project={project} target={target} platform={platform})")
        log(f"[aggregate] mode={mode}  CONAN_HOME={os.environ.get('CONAN_HOME') or '(unset - Conan default)'}")
        log("[aggregate] first-party modules (AB-01; verified against the conan graph "
            "after install, AB-02):")
        for line in format_module_plan(plan, plan_order):
            log(line)
        # D (2026-09-25): say out loud what "all deps in-tree" could NOT take
        # in-tree, and why. --with-all's name promises every dependency becomes
        # an in-tree source target; a pure-data module has no compiled CMake
        # target to add_subdirectory() (module_package_type()), so it is
        # packaged from the checkout instead (package_named_data_modules()).
        notice = data_only_in_tree_notice(data_only, with_all, with_mods)
        if notice:
            log(notice)
        log(f"[aggregate] workspace: {ws_dir}")
        with open(os.path.join(ws_dir, "ws_manifest.txt"), "w", encoding="utf-8") as f:
            f.write(ws_manifest_text(target, platform, project, primary, with_mods, with_all,
                                     mode, plan, plan_order))
        log()

        # NS-05 (cache_first_no_server_plan.md D4, STEP 2): build.py builds,
        # and nothing else - no pre-flight `conan export`/`conan create`
        # here any more (the removed export pre-flight, deleted
        # outright in NS-34;
        # setup.py owns cache preparation, D4/D4b). Read-only check
        # instead, scoped to pkg_only exactly as the export pre-flight was
        # (compiled_intree builds from live in-tree source via
        # add_subdirectory(), so it is never resolved as a plain Conan
        # package and has nothing here to be missing FROM): a ref missing
        # from the cache and not being built here STOPS the build, naming
        # the ref and the exact `setup.bat --prepare` command (RQ-9).
        #
        # CORRECTION (2026-09-25, found by a user running --with-all on a
        # genuinely cold machine), kept as history: this comment used to
        # claim "--with-all makes total == closure, so pkg_only is empty and
        # this is a no-op then". At the time that was FALSE - pkg_only was
        # computed as the named-set complement unioned with data_only, so
        # --with-all emptied the first term but never the second and a
        # pure-data module (shared_config) was demanded from an empty cache.
        # A fixed that: partition_aggregate_modules() now keeps a named data
        # module out of pkg_only entirely, so under --with-all pkg_only IS
        # empty and the `if pkg_only:` block below is skipped.
        #
        # NS-47 (RV-1): which is why the toolchain-pin check is no longer
        # inside that block. A named data module is packaged here with
        # `conan create`, whose recipe is a python_requires stub - so it
        # needs adas-toolchain/<pin> exactly as much as a cache-resolved
        # module does. The check covers pkg_only | data_only (the modules
        # whose own recipes this run evaluates) and runs BEFORE any create,
        # so a cold machine gets setup's name rather than a raw
        # "Cannot resolve python_requires". Not `closure`: a compiled_intree
        # module is add_subdirectory()'d and its recipe never loaded.
        missing_pin = missing_toolchain_pin(pkg_only | data_only)
        if missing_pin:
            for ref in missing_pin:
                log(f"ERROR: {ref} is not in this machine's Conan cache "
                    "(no local cache recipe, or its pin disagrees with modules/toolchain's "
                    f"own checkout) - run {setup_command()} --no-submodules (it puts the build "
                    "machinery in the cache and leaves your modules as they are; D4: setup "
                    "prepares, build builds).")
            sys.exit(1)

        # D2/D9: dependencies that are not checked out must be in the cache;
        # gated before anything is created.
        errors = absent_dep_problems(absent, primary, target, platform, project)
        for line in errors:
            log(line)
        if errors:
            sys.exit(1)

        # A: build what was named. Runs BEFORE the pkg_only guard so a data
        # module you asked for is in the cache (and recorded) by the time
        # anything checks, and before conan install needs it.
        data_failures = package_named_data_modules(
            data_only, project, target, platform, build_type, log=log)
        if data_failures:
            for mod, ref in data_failures:
                log(f"ERROR: {mod} ({ref}) is a data package you asked for with "
                    f"--with/--with-all, and packaging it from modules/{mod} "
                    "failed - the conan error is above.")
            sys.exit(1)

        if pkg_only:
            missing = missing_cache_refs(pkg_only, project, platform)
            if missing:
                for dep, ref in missing:
                    log(missing_cache_ref_message(dep, ref, primary, target,
                                                  platform, project))
                sys.exit(1)

            # NS-05a (D4a, STEP 3): refuse a stale cache, never silently
            # refresh it. Only checked for pkg_only (deps actually resolving
            # FROM the cache) - never a dep being built here. (Same 2026-09-25
            # correction as the block above, as history: it used to say
            # --with-all did NOT empty pkg_only, which was true of the pre-A
            # code. Since A, --with-all empties pkg_only and this whole block
            # is skipped - the reason NS-47 moved the pin check out of it.)
            outdated = outdated_format_refs(pkg_only)
            if outdated:
                for dep in outdated:
                    log(outdated_format_message(dep, primary, target, platform, project))
                sys.exit(1)
            stale, unrecorded = stale_cache_refs(pkg_only)
            if unrecorded:
                # NS-37 (RQ-4): see delegate mode's own note above - the
                # NS-05a grace period for a missing record is over.
                for line in unrecorded_message(unrecorded, primary, target, platform, project):
                    log(line)
                sys.exit(1)
            if stale:
                for dep, old_git, new_git in stale:
                    log(stale_cache_message(dep, primary, target, platform, project,
                                            old_git, new_git))
                sys.exit(1)

        generate_aggregate_conanfile(ws_dir, project, closure, compiled_intree)
        generate_aggregate_cmakelists(ws_dir, project, target, compiled_intree, ordered_mods)
        remove_stale_build_dirs(ws_dir, compiled_intree)  # RP-06, before cmake configure

        log("[aggregate] conan install ...")
        # NS-05: no --update - build.py never silently pulls a newer cached
        # or remote revision of a first-party package than what the
        # missing-ref check above already confirmed is in the cache
        # (D4/D4a: refuse a stale cache, never refresh it out from under
        # the developer). --build=missing still lets a third-party
        # (conancenter) dependency build from source when the cache lacks
        # a matching binary, unchanged from before.
        install_cmd = ["conan", "install", ".", "--output-folder", ".", "-o", f"project={project}",
                       "--build=missing", "-s", f"build_type={build_type}",
                       *profile_args(platform), "--format=json"]
        if not remotes_state:
            install_cmd.append("-nr")  # D2/RQ-5: cache-fill only, never a remote, when remotes are off.
        # WP-13 / NS-61: this aggregate's cache dependencies are pinned in a lock of
        # its own (LK-D1..LK-D6, shared with the component builder through
        # lockfiles.LockSession). Modules built here - --with, a named data module -
        # are left out of it (LK-D5): they are recompiled/repackaged every run.
        lockfiles = load_lockfiles()
        session = None
        if lockfiles is None:
            log("NOTE: modules/toolchain is not checked out, so this build is not pinned to a lock.")
        else:
            built_here_pkgs = [module_package_name(m) for m in sorted(compiled_intree | data_only)]
            cache_first_party = [f"{module_package_name(m)}/{module_version(m)}"
                                 for m in sorted(pkg_only)]
            session = lockfiles.LockSession(
                lockfiles.lock_path(ROOT, aggregate_lock_key(ws_dir, compiled_intree, data_only)),
                update_lock, cache_first_party,
                lockfiles.root_update_command(ROOT, primary, target, platform, project,
                                              with_mods or (), with_all),
                remotes_state, strip=built_here_pkgs, conan_home=active_conan_home,
                partial=bool(data_only))
            refusal = session.refusal()
            if refusal:
                for line in refusal:
                    log(line)
                sys.exit(1)
            log(session.describe())
            session.prepare()
            install_cmd += session.args
        rc, graph_json = run_install_logged(
            install_cmd, cwd=ws_dir, explain=session.explain if session else None)
        if rc != 0:
            sys.exit(rc)
        if session is not None:
            for line in session.finish():
                log(line)
        if graph_json is None:
            log("ERROR: conan install succeeded but its dependency graph is missing or "
                "unparseable - the header's module kinds cannot be verified (AB-02).")
            sys.exit(1)
        refresh_aggregate_used_shortcuts(ws_dir, graph_json)
        resolved, kind_bad = resolved_kind_mismatches(graph_json, plan, pkg_map, primary)
        log("[aggregate] resolved (AB-02):")
        for line in format_resolved_table(plan, resolved,
                                          resolved_package_folders(graph_json, pkg_map),
                                          plan_order, resolved_lib_dirs(graph_json, pkg_map)):
            log(line)
        if kind_bad:
            for mod, expected, actual in kind_bad:
                log(f"ERROR: {mod}: header said {expected}, conan resolved {actual}")
            sys.exit(1)

        editable_violations = first_party_package_mode_editable_violations(
            resolved, plan, registrations, mode)
        if editable_violations:
            for mod, ref, path in editable_violations:
                log(f"ERROR: {mod} ({ref}) resolved as a Conan Editable "
                    f"registration in package mode - {path} (CE-35)")
                log(f"  Fix: conan editable remove --refs {ref}")
                if _path_outside_root(path):
                    log(f"  NOTE: {path} is OUTSIDE this checkout's root "
                        f"({ROOT}) - almost certainly a STALE editable "
                        "left registered from a DIFFERENT checkout "
                        "entirely, not this one.")
            sys.exit(1)

        log("[aggregate] cmake configure ...")
        configure_cmd = (
            ["cmake", "-S", ".", "-B", "."] + generator_flags +
            ["-DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake",
             "-DCMAKE_POLICY_DEFAULT_CMP0091=NEW",
             f"-DPython3_EXECUTABLE={sys.executable}"]
        )
        if generator_flags[1] in _SINGLE_CONFIG_GENERATORS:
            configure_cmd.append(f"-DCMAKE_BUILD_TYPE={build_type}")
        stale = stale_cmake_cache_vars(ws_dir)
        if stale:
            log(f"[aggregate] NOTE: {len(stale)} cached path(s) in {ws_dir} no longer exist "
                f"({', '.join(stale)}) - CMake will search for them again.")
            # -U right after "cmake", before every -D: CMake applies them
            # in order, so an appended -UFOO erases a -DFOO just passed
            # (review, 2026-09-29). Names set with -D need no -U at all.
            configure_cmd = cmake_cmd_with_unsets(configure_cmd, stale)
        rc = run_logged(configure_cmd, cwd=ws_dir)
        if rc != 0:
            sys.exit(rc)

        log("[aggregate] cmake build ...")
        rc = run_logged(["cmake", "--build", ".", "--config", build_type], cwd=ws_dir)
        if rc != 0:
            sys.exit(rc)

        log(f"\n[aggregate] done - solution in {ws_dir}")
    finally:
        if log_path is not None:
            print(f"[aggregate] log: {log_path}")
        close_log()


def print_config():
    """python scripts/build.py config - every module of every project, with the real
    target/platform pairs that module's own conf/build.yml declares - every
    axis read from the modules themselves, since none of them lives anywhere
    else any more. Still no Conan dependency-chain expansion (that's Conan's
    job at install time, docs/build_conanfile_commonization_plan.md §4.3)."""
    for project in all_projects():
        for module in project_modules(project):
            conf = load_module_conf(module)
            project_conf = (conf.get("variants") or {}).get(project, {})
            for target, value in project_conf.items():
                if not isinstance(value, dict) or "platforms" not in value:
                    continue
                for platform in [e["build"] for e in value["platforms"]]:
                    print(f"python scripts/build.py {module} -t {target} -p {platform} -P {project}")
    print()
    print("add --clean to any of the above")
    print("python scripts/build.py all -t <target> -p <platform> [-P <project>]              <- fan-out (CI)")
    print("python scripts/build.py <module> -t <target> -p <platform> --with-all             <- aggregator")
    print("python scripts/build.py <module> -t <target> -p <platform> --with <mod...>        <- aggregator")
    # A module that is not checked out declares nothing yet (its targets live in
    # its own conf/build.yml), so it cannot appear above - list it by name, so a
    # fresh clone's GUI can offer it. toolchain is machinery, never a choice (D0).
    absent = [mod for mod in uninitialised_submodules(ROOT) if mod != "toolchain"]
    if absent:
        print(f"not checked out: {' '.join(absent)}")
        print("python scripts/build.py checkout <module...>                                    "
              "<- check out (or just build it: the module you name is checked out for you)")


def checkout_modules(mods):
    """python scripts/build.py checkout <module...> - initialise those submodules
    plus toolchain (D0), nothing else (D5). Never builds."""
    unknown = [mod for mod in mods if not os.path.isdir(os.path.join(ROOT, "modules", mod))]
    if unknown:
        print(f"ERROR: no such module: {', '.join(unknown)} - not a folder under modules/")
        sys.exit(1)
    if not init_if_uninitialised(["toolchain"] + list(mods)):
        print(f"Already checked out: {', '.join(mods)}")


def rebuild_users_map(module, project):
    """AB-12: {dep: sorted users} for every first-party dependency of `module`
    - the closure modules that MUST be in --with whenever `dep` is, computed by
    the SAME rebuild_closure()/reverse_rebuild_violations() the build enforces
    (AB-05, D2), so a GUI that ticks them can never emit a command AB-05
    refuses. A data dependency has no binary to mismatch, so lists none (D2)."""
    pkg_map = package_to_module_map()
    closure = forward_closure({module}, project, pkg_map)
    return {dep: sorted(rebuild_closure({module, dep}, closure, project, pkg_map) - {module, dep})
            for dep in closure - {module}}


def print_deps(module, project, rebuild_users=False):
    """python scripts/build.py deps <module> [-P <project>] - the first-party dependency
    closure of <module> for <project>, one per line, in dependency order. This
    is the exact set valid for `--with` in aggregate mode (run_aggregate_build
    validates against `forward_closure(primary) - {primary}`), so it is the
    single authority a GUI can render as `--with` checkboxes instead of a
    free-text box - and, because it is derived from each module's own
    conf/build.yml `requires:`, a dependency missing here is a visible symptom of
    a broken `requires:`, not a silent one. A trailing ` [data]` marks a
    pure-data dependency (no compiled CMake target): `--with` still accepts it,
    but "in-tree" for one of those means a Conan editable override only, never an
    add_subdirectory().

    `rebuild_users` (AB-12, opt-in; the default output is unchanged) appends
    `  users: a b` to a line whose dependency forces other closure modules into
    --with when it is chosen (rebuild_users_map())."""
    if not is_valid_module(module):
        print(f"ERROR: unknown module '{module}' - no modules/{module}/conanfile.py")
        sys.exit(1)
    pkg_map = package_to_module_map()
    closure = forward_closure({module}, project, pkg_map) - {module}
    users = rebuild_users_map(module, project) if rebuild_users else {}
    for dep in topo_sort(closure, project, pkg_map):
        marker = "" if module_package_type(dep) in _COMPILED_PACKAGE_TYPES else " [data]"
        suffix = f"  users: {' '.join(users[dep])}" if users.get(dep) else ""
        print(f"{dep}{marker}{suffix}")


def main():
    if sys.argv[1:] == ["config"]:
        print_config()
        return

    if len(sys.argv) >= 2 and sys.argv[1] == "checkout":
        if len(sys.argv) < 3:
            print("usage: python scripts/build.py checkout <module...>")
            sys.exit(2)
        checkout_modules(sys.argv[2:])
        return

    # python scripts/build.py deps <module> [-P <project>] - a discovery command, like
    # config: prints the module's first-party dependency closure and returns,
    # never builds. Parsed by hand (not the main argparse below) because it takes
    # no -t/-p and must not trip their `required=True`.
    if len(sys.argv) >= 2 and sys.argv[1] == "deps":
        rest, module, project, rebuild_users = sys.argv[2:], None, "base", False
        i = 0
        while i < len(rest):
            if rest[i] in ("-P", "--project") and i + 1 < len(rest):
                project = rest[i + 1]; i += 2
            elif rest[i] == "--rebuild-users":
                rebuild_users = True; i += 1
            else:
                module = rest[i]; i += 1
        if not module:
            print("usage: python scripts/build.py deps <module> [-P <project>] [--rebuild-users]")
            sys.exit(2)
        print_deps(module, project, rebuild_users)
        return

    parser = argparse.ArgumentParser(
        description="ADAS 1V Superproject Build Dispatcher (docs/build_grammar.md)")
    parser.add_argument("module", nargs="?",
                        help="Module to build (e.g. df), or `all` for every module of the project")
    parser.add_argument("-P", "--project", default="base",
                        help="Project name (default: base) - must be declared by some module's conf/build.yml")
    parser.add_argument("-t", "--target", required=True,
                        help="Target to build (sil/gtest/coverage/docs/prod/package) - never inferred")
    parser.add_argument("-p", "--platform", required=True,
                        help="Toolchain+arch token (vs2026/ubuntu_gcc/aarch64_qcc_qnx/tda4_ti/noarch) - never inferred")
    parser.add_argument("--modules",
                        help="Comma-separated module subset for fan-out mode (alternative to `all`)")
    parser.add_argument("--no-log", action="store_true",
                        help="Don't write log files (console output only); forwarded to each module")
    parser.add_argument("--clean", action="store_true",
                        help="Remove the build directory first (for the aggregator, wipes its conan_workarea/ build folder)")
    parser.add_argument("--with", dest="with_mods", nargs="+", metavar="MOD",
                        help="Aggregator: pull these first-party dependencies in-tree as real CMake source targets in the same solution")
    parser.add_argument("--with-all", action="store_true",
                        help="Aggregator: same as --with, but every first-party dependency is discovered and pulled in-tree automatically")
    parser.add_argument("--mode", choices=["develop", "package"], default=None,
                        help="RD-03 (remove_develop_mode_plan.md): 'package' (default, and the "
                             "only supported mode) - modules you name are built from source, "
                             "the rest come from Conan re-exported from your checkout. "
                             "'develop' is accepted only so it can be refused with a clear "
                             "message; it is retained as a choice, kept only to give that "
                             "refusal - never to succeed. An explicit CONAN_HOME already set "
                             "in the environment always wins over this flag.")
    parser.add_argument("--update-lock", action="store_true",
                        help="WP-13 (cache_first_no_server_plan.md §5): re-resolve this build's "
                             "Conan lock (conan_workarea/locks/) against the current cache and pin "
                             "what it finds. A build otherwise never changes an existing lock.")
    parser.add_argument("--remotes", choices=["on", "off"], default=None,
                         help="WP-1/NS-01 (cache_first_no_server_plan.md D1): override "
                              "scripts/team_conan_server.txt for this run only.")
    args = parser.parse_args()

    # WP-1/NS-01: computed and printed exactly once, here, before any build
    # path runs (fan-out/aggregate/delegate all pass through this point).
    cli_override = {"on": True, "off": False, None: None}[args.remotes]
    args.remotes_enabled, args.remotes_reason = remotes_enabled(cli_override=cli_override)
    print(f"Remotes: {'on' if args.remotes_enabled else 'off'} ({args.remotes_reason})")

    if args.mode == "develop":
        # RD-03 (remove_develop_mode_plan.md): develop mode is removed - was
        # a deprecation warning (RD-02), now a hard refusal.
        print("ERROR: --mode develop was removed. See remove_develop_mode_plan.md "
              "(package mode is the only mode).", file=sys.stderr)
        sys.exit(1)

    if args.with_mods and args.with_all:
        print("ERROR: --with and --with-all are mutually exclusive")
        sys.exit(1)

    # D0/D4, a fresh superproject clone: the module you name is about to be
    # compiled, so it is checked out for you - with toolchain, which every
    # build needs. Before the project check: a fresh clone declares no project
    # until a module is checked out. Dependencies are never checked out here
    # (D5); fan-out gets toolchain only.
    single = args.module if args.module and args.module != "all" and not args.modules else None
    init_if_uninitialised(["toolchain"] + ([single] if single else []))

    known_projects = all_projects()
    if args.project not in known_projects:
        print(f"ERROR: Unknown project '{args.project}' - no module declares it. "
              f"Valid: {', '.join(known_projects)}")
        sys.exit(1)

    if args.module and args.modules:
        print("ERROR: pass either a module name or --modules, not both")
        sys.exit(1)
    if not args.module and not args.modules:
        print("ERROR: name a module (e.g. `df`), or `all`, or pass --modules a,b")
        sys.exit(1)

    require_toolchain_checkout()

    # Fan-out mode
    if args.modules or args.module == "all":
        known = project_modules(args.project)
        if args.modules:
            wanted = [name.strip() for name in args.modules.split(",")]
            unknown = set(wanted) - set(known)
            if unknown:
                print(f"ERROR: --modules names modules not in project '{args.project}': "
                      f"{', '.join(sorted(unknown))} - valid: {', '.join(known)}")
                sys.exit(1)
        else:
            wanted = known
        if args.with_mods or args.with_all:
            print("ERROR: --with/--with-all is aggregator-only - it needs one primary module, not a fan-out batch")
            sys.exit(1)
        sys.exit(0 if run_fanout(wanted, args.project, args.target,
                                 args.platform, args.clean, args.no_log,
                                 remotes_state=args.remotes_enabled,
                                 **({"update_lock": True} if args.update_lock else {})) else 1)

    if not is_valid_module(args.module):
        print(f"ERROR: unknown module '{args.module}' - no modules/{args.module}/conanfile.py")
        sys.exit(1)

    # Aggregate mode
    if args.with_mods or args.with_all:
        # W3: a --with module that is a known dependency but not checked out is
        # about to be compiled from source, so initialise it first.
        absent = absent_first_party_refs(
            forward_closure({args.module}, args.project, package_to_module_map()), args.project)
        init_absent_modules([m for m in (args.with_mods or []) if m in absent])
        for mod in (args.with_mods or []):
            validate_with_module(mod, args.module, args.project)
        run_aggregate_build(args.project, args.module, args.target, args.platform,
                            args.with_mods, args.with_all, args.clean, args.no_log,
                            args.mode or ROOT_DEFAULT_MODE, args.remotes_enabled,
                            **({"update_lock": True} if args.update_lock else {}))
        return

    # Delegate mode
    sys.exit(0 if run_delegate(args.module, args.project, args.target,
                               args.platform, args.clean, args.no_log,
                               remotes_state=args.remotes_enabled,
                               **({"update_lock": True} if args.update_lock else {})) else 1)


if __name__ == "__main__":
    main()
