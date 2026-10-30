#!/usr/bin/env python3
"""
scripts/check_conan_resolution.py

Standalone resolution-completeness checker (docs: modules/toolchain/docs/
imp_design.md §6) - built after a real incident:
a developer's `sil_viz` build failed to resolve `adas-viz` even though a
real, profile-matching binary for it existed on THIS machine's own
`adas-local`. The root cause traced back to `scripts/setup.py`:
`configure_conan_dependencies()` only ever registers a non-base component
editable or leaves it to a team server - there is no code path, for
anyone, that ever builds and publishes a non-base component to a
machine's own `adas-local`. A partial-clone/single-component checkout has
no way for such a dependency to ever become resolvable.

Deliberately standalone - NOT inside `adas_build_tools` (that package
only exists inside a component's own `.venv`, which doesn't exist yet the
first time a developer runs setup) and NOT importing it. Stdlib + PyYAML
(already a `scripts/setup.py` dependency, see `check_or_install_pyyaml()`)
+ subprocess calls to the `conan` CLI only.

Wiring this into `scripts/setup.py`'s normal flow is explicitly NOT this
script's job - that belongs to a separate, root-level plan
(conan_environment_plan.md). This script only builds the check/fix tool
itself and is run by hand.

CE-18 (conan_environment_plan.md §5.3, WP-08): a second real incident
found this checker itself was blind to `python_requires` refs -
`adas-toolchain/1.0.4`, the recipe all 8 real components open with, was
never published anywhere because `discover_required_refs()` read only
`requires:`/`tool_requires:` out of `conf/build.yml`, and `python_requires`
lives in `conanfile.py` instead. `discover_python_requires_refs()` closes
that second source.

RD-03 (remove_develop_mode_plan.md, 2026-09-22): develop mode, editable
registrations and the develop CONAN_HOME are removed. `check_resolvable()`'s
editable branch and `check_pin_freshness()` (prompt 40 item 2's stale-
editable-drift check, added and since removed - there is nothing left to
drift once nothing is ever editable) are gone with them; this checker is
now package-mode resolution only.

Usage:
    python scripts/check_conan_resolution.py
    python scripts/check_conan_resolution.py --publish-missing
    python scripts/check_conan_resolution.py --platform vs2026 --remote adas-local
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

from conan_home_resolution import auth_failure_message, remotes_enabled

PYTHON_REQUIRES_RE = re.compile(r'python_requires\s*=\s*["\']([^"\']+)["\']')
BARE_BUILD_TOOLS_VERSION_RE = re.compile(r'^\d+\.\d+\.\d+$')

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REMOTE = "adas-local"
DEFAULT_PLATFORM = "vs2026"
# WP-5/NS-09 (cache_first_no_server_plan.md): the target `main()` suggests
# in a NOTBUILT hint's `--prepare` command when it has no better one to
# offer (this checker only ever sees --platform, never --target). "sil" is
# every real component's own default delivery target (R-SIL-1) - a
# reasonable default to print, not a promise it's the only correct one for
# every module; the hint still names the real module and platform.
DEFAULT_PREPARE_TARGET_HINT = "sil"


def _setup_python():
    return "python" if os.name == "nt" else "python3"


def _prepare_choice(conf, platform):
    """(target, project) this module really declares for `platform`, preferring
    project `base` and target DEFAULT_PREPARE_TARGET_HINT; None if it declares
    no target for that platform at all."""
    options = []
    for project, pconf in (conf.get("variants") or {}).items():
        for target, block in (pconf or {}).items():
            if isinstance(block, dict) and any(
                    isinstance(p, dict) and p.get("build") == platform
                    for p in block.get("platforms") or []):
                options.append((project != "base", target != DEFAULT_PREPARE_TARGET_HINT,
                                project, target))
    if not options:
        return None
    _, _, project, target = min(options)
    return target, project


def dependents_of(ref, root=None):
    """PT-28: every checked-out component whose conf/build.yml requires `ref`
    DIRECTLY (any project's requires:/tool_requires:), as {name: conf}."""
    root = Path(root or ROOT)
    out = {}
    for comp_dir in sorted((root / "modules").glob("*/")):
        build_yml = comp_dir / "conf" / "build.yml"
        if not (build_yml.is_file() and (comp_dir / "conanfile.py").is_file()):
            continue
        conf = yaml.safe_load(build_yml.read_text(encoding="utf-8")) or {}
        declared = set()
        for pconf in (conf.get("variants") or {}).values():
            for key in ("requires", "tool_requires"):
                declared.update(r for r in (pconf or {}).get(key) or [] if isinstance(r, str))
        if ref in declared:
            out[comp_dir.name] = conf
    return out


def notbuilt_hint(ref, component, platform, root=None):
    """PT-28 (D11): Fix plus one runnable `setup.py --prepare` per checked-out
    module that requires `ref` directly, each with a target/project that
    module really declares for `platform`. Nobody requires it -> Fix only."""
    runs = []
    for name, conf in dependents_of(ref, root).items():
        choice = _prepare_choice(conf, platform)
        if choice:
            target, project = choice
            runs.append(f"Run:    {_setup_python()} scripts/setup.py --prepare {name} "
                        f"-t {target} -p {platform} -P {project}")
    if not runs:
        return [f"Fix:    no checked-out module requires {ref} directly for platform "
                f"{platform}, so nothing here needs it built; it is built on demand if one ever does."]
    return [f"Fix:    build it on demand, or prepare a module that needs it (each command "
            f"builds that module's dependencies, {component} among them):", *runs]


def discover_components():
    """Every modules/<x> with BOTH conanfile.py and conf/build.yml -
    intentionally the exact same predicate as `scripts/setup.py::
    discover_components()` (not imported from there - this script must
    run standalone, and setup.py is explicitly out of scope for this WP -
    but re-derived identically, never a divergent guess). Includes
    `toolchain` (it has both files, for the `adas-toolchain` python_requires
    package) - harmless here since its own conf/build.yml declares no
    requires:/tool_requires: at all, so it contributes zero refs below."""
    mdir = ROOT / "modules"
    if not mdir.is_dir():
        return []
    return sorted(
        d.name for d in mdir.iterdir()
        if (d / "conanfile.py").exists() and (d / "conf" / "build.yml").exists()
    )


def discover_python_requires_refs():
    """Every `adas-*` ref declared as `python_requires` in ANY real
    component's `conanfile.py` (CE-18, conan_environment_plan.md §5.3) -
    the gap that hid `adas-toolchain` from `discover_required_refs()`
    entirely. Read from `conanfile.py` itself, never `conf/build.yml`,
    because that IS where every component declares it
    (`python_requires = "adas-toolchain/1.0.4"`, confirmed live across all
    8 real components) - `conf/build.yml` has no field for it and adding
    one would be a second, divergence-prone place to say the same thing.
    A plain regex, not a Conan/AST parse: this script must run standalone
    before any component's own tooling exists (see module docstring), and
    the declaration is always a single literal string assignment on the
    class body, never computed. Placeholder conanfile.py stubs
    (`# Conan configuration placeholder`) and toolchain's own conanfile.py
    (which BUILDS adas-toolchain rather than requiring it) correctly
    contribute nothing here."""
    refs = set()
    for name in discover_components():
        conanfile = ROOT / "modules" / name / "conanfile.py"
        try:
            text = conanfile.read_text(encoding="utf-8")
        except OSError:
            continue
        match = PYTHON_REQUIRES_RE.search(text)
        if match and match.group(1).startswith("adas-"):
            refs.add(match.group(1))
    return refs


def discover_build_tools_refs():
    """Every `adas-build-tools/<version>` ref a real component pins via
    `conf/build_tools.version` (R-BUILD-2) - a THIRD ref source, distinct
    from `python_requires` (adas-toolchain) and `conf/build.yml`'s
    requires:/tool_requires:. Found missing running RD-14's own real
    cold-machine proof, 2026-09-22: a component's own `scripts/build.py`
    bootstrap stub `conan download`s this ref straight off `adas-local`
    with no other resolution path, so a solo/delegate build (`build.py df
    -t sil -p vs2026`, no `--with`) failed at that download - `Recipe not
    found: 'adas-build-tools/1.0.19@_/_'` - even once every other required
    ref (including `adas-toolchain`) had already been published.

    Only a BARE `X.Y.Z` pin names a Conan ref (docs/imp_design.md §10): a
    `vX.Y.Z` pin installs via `pip install git+<url>@<tag>` instead and
    needs nothing from `adas-local` - correctly skipped here, not a gap."""
    refs = set()
    for name in discover_components():
        pin_file = ROOT / "modules" / name / "conf" / "build_tools.version"
        try:
            text = pin_file.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if BARE_BUILD_TOOLS_VERSION_RE.match(text):
            refs.add(f"adas-build-tools/{text}")
    return refs


def discover_required_refs():
    """Every `adas-*` ref this repo actually needs to exist - editable or
    on `adas-local` - for the repo to build at all: `requires:`/
    `tool_requires:` in ANY variant of ANY real component's `conf/
    build.yml` (R-VAR-3), UNION `python_requires` declared in ANY real
    component's `conanfile.py` (CE-18 - see discover_python_requires_refs()
    docstring for why `adas-toolchain` needed a second source), UNION
    `adas-build-tools/<version>` pinned via any real component's `conf/
    build_tools.version` (see discover_build_tools_refs() docstring - the
    third source, found by RD-14's own real proof). A conancenter
    dependency (protobuf, yaml-cpp, zlib, ...) is out of scope - those
    resolve from conancenter directly, never from `adas-local`, and were
    never the incident this script exists to catch."""
    refs = set(discover_python_requires_refs()) | discover_build_tools_refs()
    for name in discover_components():
        build_yml = ROOT / "modules" / name / "conf" / "build.yml"
        try:
            data = yaml.safe_load(build_yml.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        for variant in (data.get("variants") or {}).values():
            if not isinstance(variant, dict):
                continue
            for key in ("requires", "tool_requires"):
                for ref in (variant.get(key) or []):
                    if isinstance(ref, str) and ref.startswith("adas-"):
                        refs.add(ref)
    return sorted(refs)


def _run(cmd, cwd=None, env=None):
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd is not None else None,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env,
    )


def pinned_profile_settings(platform):
    """The `[settings]` section of `adas_build_tools/conan_profiles/
    <platform>.profile`, read as a plain file from the checked-out
    `modules/toolchain` source tree - never imported as a Python package
    (this script must run before any component's `.venv`/adas_build_tools
    exists). Returns None if no profile is shipped for `platform` (the
    same "unpinned platform" case `adas_build_tools.conan_ops.
    project_profile_path()` already tolerates for a real build)."""
    profile_path = (ROOT / "modules" / "toolchain" / "adas_build_tools"
                     / "conan_profiles" / f"{platform}.profile")
    if not profile_path.is_file():
        return None
    settings = {}
    in_settings_section = False
    for line in profile_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            in_settings_section = (line == "[settings]")
            continue
        if in_settings_section and "=" in line:
            key, _, value = line.partition("=")
            settings[key.strip()] = value.strip()
    return settings


class AdasLocalLoginExpired(Exception):
    """CE-29: the remote refused because its login expired - not a statement
    about any package. Carries the one-line message (auth_failure_message)."""


def _raise_if_auth_failure(text):
    """CE-29: `text` is conan's stderr or a `conan list --format=json` remote
    "error" - raise AdasLocalLoginExpired iff it is an auth failure (matched by
    the same auth_failure_message() scripts/build.py uses, CE-28)."""
    msg = auth_failure_message(text or "", os.environ.get("CONAN_HOME"))
    if msg:
        raise AdasLocalLoginExpired(msg)


def _packages_match_profile(ref_data, profile_settings):
    """WP-2/NS-03: the settings-matching walk shared by the cache-first and
    remote checks below - factored out so both ask the identical question
    of whatever `ref_data` (one source's `conan list <ref>:* --format=json`
    entry for `ref`) they were handed, cache or remote alike."""
    if profile_settings is None:
        return False
    for revision_data in (ref_data.get("revisions") or {}).values():
        for package_data in (revision_data.get("packages") or {}).values():
            settings = (package_data.get("info") or {}).get("settings")
            if not settings:
                # Genuinely settings-less package (conanfile.py declares no
                # `settings` field at all - `adas-shared-config`'s own real
                # shape, DR-10/DRT-12): there is no settings axis to mismatch
                # against, so any published binary is an automatic match on
                # every platform. Distinct from a real, non-empty settings
                # dict that simply doesn't match the pinned profile below.
                return True
            if all(settings.get(k) == v for k, v in profile_settings.items()):
                return True
    return False


def _cache_matches_profile(ref, profile_settings):
    """WP-2/NS-03 (cache_first_no_server_plan.md): "can THIS MACHINE
    resolve it", asked of the local Conan cache - no `-r`, no network, no
    auth failure possible (CE-29 is a remote-only concept, so no
    _raise_if_auth_failure() call here). `conan list <ref>:* --format=json`
    with no `-r` reports the local cache under the fixed key "Local
    Cache"."""
    if profile_settings is None:
        return False
    proc = _run(["conan", "list", f"{ref}:*", "--format=json"])
    if proc.returncode != 0:
        return False
    try:
        data = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        return False
    cache_data = data.get("Local Cache")
    if not isinstance(cache_data, dict):
        return False
    return _packages_match_profile(cache_data.get(ref) or {}, profile_settings)


def _cache_has_recipe(ref):
    """WP-2/NS-03: cache-first counterpart of _adas_local_has_recipe() -
    the recipe (no binary requirement) exists in THIS machine's own Conan
    cache. Used only for a python_requires ref (CE-18's own reasoning, see
    _adas_local_has_recipe()'s docstring)."""
    proc = _run(["conan", "list", ref, "--format=json"])
    if proc.returncode != 0:
        return False
    try:
        data = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        return False
    cache_data = data.get("Local Cache")
    if not isinstance(cache_data, dict):
        return False
    return ref in cache_data


def _adas_local_matches_profile(ref, remote, profile_settings):
    """True if `ref` has at least one built package on `remote` whose
    settings match `profile_settings` on every key the pinned profile
    declares. A recipe that exists on `remote` with only an OLD
    compiler's binary (this machine's own auto-detected default profile
    is msvc 193; the pinned profile is msvc 195 - confirmed live,
    `conan profile show`) is exactly as unresolvable as one missing
    outright (SS4) - "the recipe exists" is deliberately not treated as
    good enough on its own. `profile_settings=None` (no pinned profile
    shipped for this platform) always returns False - there is nothing
    to match against, so nothing can be confirmed resolvable this way."""
    if profile_settings is None:
        return False
    proc = _run(["conan", "list", f"{ref}:*", "-r", remote, "--format=json"])
    if proc.returncode != 0:
        _raise_if_auth_failure(proc.stderr)  # CE-29
        return False
    try:
        data = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        return False

    remote_data = data.get(remote)
    if isinstance(remote_data, dict):
        _raise_if_auth_failure(str(remote_data.get("error") or ""))  # CE-29
    if not isinstance(remote_data, dict) or "error" in remote_data:
        return False
    ref_data = remote_data.get(ref) or {}
    for revision_data in (ref_data.get("revisions") or {}).values():
        for package_data in (revision_data.get("packages") or {}).values():
            settings = (package_data.get("info") or {}).get("settings")
            if not settings:
                # Genuinely settings-less package (conanfile.py declares no
                # `settings` field at all - `adas-shared-config`'s own real
                # shape, DR-10/DRT-12): there is no settings axis to mismatch
                # against, so any published binary is an automatic match on
                # every platform. Distinct from a real, non-empty settings
                # dict that simply doesn't match the pinned profile below.
                return True
            if all(settings.get(k) == v for k, v in profile_settings.items()):
                return True
    return False


def _adas_local_has_recipe(ref, remote):
    """True if `ref`'s RECIPE (any revision) exists on `remote`, with no
    binary-package requirement at all. Used only for a `python_requires`
    ref (CE-18): graph resolution needs the recipe text to import
    `AdasComponent` from, never a compiled package_id - `adas-toolchain`
    published via `conan export` (its own documented publish step, see
    conf/build.yml) has zero packages forever (`conan list <ref>:* -r
    remote` returns `packages: {}` for it, confirmed live 2026-09-15), so
    `_adas_local_matches_profile()`'s package/settings walk would report
    it MISSING even once correctly published. Deliberately the UNqualified
    `conan list <ref>` form (no `:*` binary selector) - existence of the
    recipe reference itself is the whole question here."""
    proc = _run(["conan", "list", ref, "-r", remote, "--format=json"])
    if proc.returncode != 0:
        _raise_if_auth_failure(proc.stderr)  # CE-29
        return False
    try:
        data = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        return False
    remote_data = data.get(remote)
    if isinstance(remote_data, dict):
        _raise_if_auth_failure(str(remote_data.get("error") or ""))  # CE-29
    if not isinstance(remote_data, dict) or "error" in remote_data:
        return False
    return ref in remote_data


def check_resolvable(ref, remote=DEFAULT_REMOTE, profile_settings=None,
                      is_python_require=False, remotes_enabled=True):
    """(bool resolvable, str reason) for one `adas-*` ref. RD-03
    (remove_develop_mode_plan.md): package-mode resolution only - editable
    is no longer a resolution path this checker recognizes (develop mode
    and editable registrations are removed). Resolvable iff a real
    `remote` binary matches the CURRENT pinned profile exactly (DRT-10's
    own PASS/FAIL split: a false MISSING sends someone chasing a
    non-problem, a false PASS is the exact failure mode that let the real
    `sil_viz` incident go unnoticed until a developer hit it).

    WP-2/NS-03 (cache_first_no_server_plan.md): "can THIS MACHINE resolve
    it" - the local Conan cache is checked FIRST, unconditionally (no
    network, no auth to fail). Only when the cache doesn't already have a
    match AND `remotes_enabled` is True does this fall through to `remote`
    at all; with `remotes_enabled=False` an unresolved ref is reported
    without ever touching the network, and the reason text never mentions
    `remote` by name (a false "no {remote} binary matches" would wrongly
    imply a remote was actually asked).

    `is_python_require` (CE-18) is passed in by the caller - determined
    from `discover_python_requires_refs()`, i.e. from WHICH conanfile.py
    declared the ref, never from inspecting `ref`'s own component
    directory. That matters on a cold, single-component clone: the
    caller can see "`df`'s conanfile.py declares `python_requires =
    "adas-toolchain/1.0.4"`" with zero local knowledge of `toolchain`
    itself, but a check that tried to open `modules/toolchain/conf/
    build.yml` to learn the same fact would find nothing there to open.
    A python_requires ref needs only its RECIPE (to import
    `AdasComponent` from) - never a compiled binary - so remote
    resolution asks `_adas_local_has_recipe()` instead of
    `_adas_local_matches_profile()` (a `python_requires`-only recipe
    published via `conan export` has zero packages forever - confirmed
    live, `packages: {}` - so the package/settings walk would wrongly
    report it MISSING even once correctly published)."""
    if is_python_require:
        if _cache_has_recipe(ref):
            return True, "Local Cache (python_requires recipe)"
        if not remotes_enabled:
            return False, "no local cache recipe (remotes are off)"
        if _adas_local_has_recipe(ref, remote):
            return True, f"{remote} (python_requires recipe published)"
        return False, f"no {remote} recipe published"
    if _cache_matches_profile(ref, profile_settings):
        return True, "Local Cache (binary matches the pinned profile)"
    if not remotes_enabled:
        return False, "no local cache binary matches the pinned profile (remotes are off)"
    if _adas_local_matches_profile(ref, remote, profile_settings):
        return True, f"{remote} (binary matches the pinned profile)"
    return False, f"no {remote} binary matches the pinned profile"


def _find_component_dir(ref):
    """The directory whose OWN Conan package name matches ref's name half -
    asked of each real component's own recipe (`conan inspect .`) rather
    than guessed from the ref string, since a component's package name
    doesn't always match its directory name letter-for-letter
    (`shared_config` -> `adas-shared-config`). Returns None if no
    checked-out component's recipe reports this name - a real "no local
    source on this machine" case, not an error.

    `modules/toolchain/conan_package/` is checked too (found by RD-14's
    real cold-machine proof, 2026-09-22): `adas-build-tools`'s own recipe
    lives there, nested under `toolchain`, not at any `modules/<x>`
    top level `discover_components()` itself enumerates - the one ref
    `discover_build_tools_refs()` can add that isn't one of that list's
    own components."""
    name = ref.split("/", 1)[0]
    candidate_dirs = [ROOT / "modules" / comp_name for comp_name in discover_components()]
    candidate_dirs.append(ROOT / "modules" / "toolchain" / "conan_package")
    for comp_dir in candidate_dirs:
        proc = _run(["conan", "inspect", ".", "--format=json"], cwd=comp_dir)
        if proc.returncode != 0:
            continue
        try:
            data = json.loads(proc.stdout)
        except (json.JSONDecodeError, ValueError):
            continue
        if data.get("name") == name:
            return comp_dir
    return None


def _is_python_require_component(comp_dir):
    """True if `comp_dir`'s own `conf/build.yml` declares `recipe.type:
    python-require` (`adas-toolchain`'s own real shape). Used only by
    `publish_ref()`, where `comp_dir` is always a real local checkout
    (nothing is ever published FROM a machine that doesn't have the
    source) - unlike `check_resolvable()`'s `is_python_require` flag,
    which must also work with no local checkout of the ref's own
    component at all (see that function's docstring)."""
    if comp_dir is None:
        return False
    build_yml = comp_dir / "conf" / "build.yml"
    try:
        data = yaml.safe_load(build_yml.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return False
    return ((data.get("recipe") or {}).get("type")) == "python-require"


def _recipe_version(comp_dir):
    """The version `comp_dir`'s own conanfile.py resolves to right now (its
    real `conan inspect .` version) - never the version a caller is trying
    to publish a ref under. RD-08 (remove_develop_mode_plan.md): used by
    `publish_ref()` to refuse relabelling a python-require's checkout as a
    version it isn't - `conan export . --version=<pinned>` happily exports
    whatever is checked out under any label you hand it, which is exactly
    how `adas-toolchain/1.0.5`'s real source got published as `1.0.4`
    before this check existed."""
    proc = _run(["conan", "inspect", ".", "--format=json"], cwd=comp_dir)
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        return None
    return data.get("version")


def publish_ref(ref, comp_dir, remote, platform):
    """Builds and uploads `ref` for real, from `comp_dir`'s own source -
    the actual fix, not just the diagnosis (DR-09). Deliberately NOT
    `scripts/conan_publish.py::publish_commands()` here: that helper's
    `conan create` carries no `--profile:host/--profile:build` flags at
    all, so on a machine whose own auto-detected default profile differs
    from the pinned one (confirmed live: 193 here, pinned is 195) it
    would publish a binary that still fails this script's OWN
    pinned-profile check - "fixing" nothing. `conan create` (WITH the
    pinned profile) -> `conan upload`, profile flags added because this
    tool's definition of "resolvable" is stricter than a bare recipe
    match. Returns True on success, never raises - a failed publish
    attempt is reported, not fatal to the rest of the run.

    RD-05 (remove_develop_mode_plan.md, WP-4): the editable-remove ->
    ... -> editable-restore wrapping this used to have is gone -
    `editable_refs()` is permanently empty with no editables ever
    registered (RD-03/RD-04), so `was_editable` was permanently False,
    the same "simplify: remove now-unreachable code" verdict RD-01
    already reached for `scripts/conan_publish.py::publish_commands()`."""
    name, _, version = ref.partition("/")

    if _is_python_require_component(comp_dir):
        # RD-08: a python-require is published ONLY when the pinned version
        # equals the checkout's own version - otherwise this would export
        # the checkout's current source under a label it isn't (see
        # _recipe_version()'s docstring for the real incident this closes).
        checkout_version = _recipe_version(comp_dir)
        if checkout_version != version:
            print(f"    REFUSED: {ref} pins {version}, but {comp_dir} is checked out "
                  f"at {checkout_version} - publishing would relabel the checkout's own "
                  f"source under a version it isn't. Bump the pin to "
                  f"adas-toolchain/{checkout_version} in the consumer(s) instead, or "
                  f"check out the {version} tag here.")
            return False
        # adas-toolchain's own shape (conf/build.yml's own documented
        # publish recipe): a python_requires package has no CMakeLists.txt
        # and nothing to compile, so `conan export` - not `conan create` -
        # is the entire publish step; no profile flags, since there is no
        # settings axis to pin. No `--version=` override: the recipe's own
        # `version = ...` (read from VERSION) already matches, just checked.
        create_cmd = ["conan", "export", "."]
    else:
        create_cmd = ["conan", "create", ".", "--build=missing", "-s", "build_type=Release"]
        profile_path = (ROOT / "modules" / "toolchain" / "adas_build_tools"
                         / "conan_profiles" / f"{platform}.profile")
        if profile_path.is_file():
            create_cmd += ["--profile:host", str(profile_path), "--profile:build", str(profile_path)]
    create_proc = _run(create_cmd, cwd=comp_dir)
    if create_proc.returncode != 0:
        print(f"    FAILED: {' '.join(create_cmd)} (exit {create_proc.returncode}):")
        print(f"    {create_proc.stderr.strip() or create_proc.stdout.strip()}")
        return False

    upload_proc = _run(["conan", "upload", ref, "-r", remote, "--confirm"])
    if upload_proc.returncode != 0:
        print(f"    FAILED: conan upload {ref} -r {remote} --confirm "
              f"(exit {upload_proc.returncode}): {upload_proc.stderr.strip()}")
        return False

    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--remote", default=DEFAULT_REMOTE,
                         help=f"Conan remote to check/publish to (default: {DEFAULT_REMOTE})")
    parser.add_argument("--platform", default=DEFAULT_PLATFORM,
                         help=f"Pinned profile platform to check against (default: {DEFAULT_PLATFORM})")
    parser.add_argument("--publish-missing", action="store_true",
                         help="Build and upload any MISSING ref whose source is checked out here")
    parser.add_argument("--remotes", choices=["on", "off"], default=None,
                         help="WP-1/NS-01 (cache_first_no_server_plan.md D1): override "
                              "scripts/team_conan_server.txt for this run only.")
    args = parser.parse_args(argv)

    # WP-1/NS-03: computed and printed exactly once, here, before any
    # cache/remote check runs.
    cli_override = {"on": True, "off": False, None: None}[args.remotes]
    args.remotes_enabled, args.remotes_reason = remotes_enabled(cli_override=cli_override)
    print(f"Remotes: {'on' if args.remotes_enabled else 'off'} ({args.remotes_reason})")

    # Item 2 (prompt 40): unconditional, every run, both modes - the whole
    # point is that it fires without anyone remembering to ask for it.
    # Placed ahead of the early "nothing to check" return below so a
    # module-less checkout (never actually seen in this repo, but not
    # this check's business to assume) still gets scanned. Warns only -
    refs = discover_required_refs()
    if not refs:
        print("No adas-* refs declared under requires:/tool_requires:/python_requires "
              "anywhere - nothing to check.")
        return 0

    python_require_refs = discover_python_requires_refs()
    build_tools_refs = discover_build_tools_refs()
    profile_settings = pinned_profile_settings(args.platform)
    if profile_settings is None:
        print(f"WARNING: no pinned profile shipped for platform {args.platform!r} "
              f"(modules/toolchain/adas_build_tools/conan_profiles/{args.platform}.profile "
              f"not found) - resolution cannot be confirmed this run.\n")

    # WP-5/NS-09 (cache_first_no_server_plan.md, TASK 1): a real cold run
    # (STEP 5, this same plan) reported adas-interfaces/mathlib/shared-
    # config/sim/viz all MISSING and failed setup.bat outright on a
    # genuinely empty scratch cache with every module checked out - even
    # though "not yet compiled into the cache" and "no source exists on
    # this machine at all" are different situations with different
    # remedies (D4b: setup restores/exports by default, it compiles on
    # demand; RQ-10: a standalone submodule build never builds a sibling).
    # With remotes off, a plain first-party ref (never adas-toolchain/
    # adas-build-tools - D3/RQ-6's own "ships in the bundle" category,
    # resolved by setup.py's cache-fill step BEFORE this checker ever
    # runs, so one still missing here is a real gap, not "not built yet")
    # is reclassified:
    #   - its own component IS checked out here -> NOTBUILT, not fatal.
    #   - no local checkout of it at all -> still MISSING/fatal, naming
    #     setup.bat explicitly (the lone-submodule-clone case).
    # Remotes-ON behaviour is completely unchanged (the `not args.
    # remotes_enabled` guard below), and check_resolvable() itself is
    # untouched - only main()'s OWN reporting of an unresolvable ref gains
    # a third bucket.
    missing = []
    not_built = []
    try:
        for ref in refs:
            resolvable, reason = check_resolvable(
                ref, args.remote, profile_settings,
                is_python_require=(ref in python_require_refs),
                remotes_enabled=args.remotes_enabled)
            if resolvable:
                print(f"{'PASS':8} {ref:32} ({reason})")
                continue

            if (not args.remotes_enabled
                    and ref not in python_require_refs
                    and ref not in build_tools_refs):
                comp_dir = _find_component_dir(ref)
                if comp_dir is not None:
                    print(f"{'NOTBUILT':8} {ref:32} ({comp_dir.name} is checked out here "
                          "but has no cached binary matching the pinned profile - not "
                          "built yet)")
                    for line in notbuilt_hint(ref, comp_dir.name, args.platform):
                        print(f"         {line}")
                    not_built.append(ref)
                    continue
                reason = (f"{reason}, and no local checkout of its own component either "
                          "(RQ-10) - run setup.bat here, or clone the superproject and "
                          "run it there")

            print(f"{'MISSING':8} {ref:32} ({reason})")
            missing.append(ref)
    except AdasLocalLoginExpired as exc:
        # CE-29: an expired login says nothing about any package - report it
        # once, list nothing as MISSING, and never reach --publish-missing.
        print(f"\nERROR: {exc}")
        return 1

    # WP-2/NS-02/NS-03: --publish-missing is a real `conan create`+`conan
    # upload` - a remote write. Never attempted with remotes off, whatever
    # the caller passed on the command line.
    if missing and args.publish_missing and not args.remotes_enabled:
        print(f"\nRemotes are off - not publishing {len(missing)} missing "
              "ref(s). Point scripts/team_conan_server.txt at a real "
              "server, or pass --remotes on, or re-run setup.bat to let "
              "the cache-fill preparation step restore from "
              "misc/offline_bundle/.")
    elif missing and args.publish_missing:
        # RD-11 (remove_develop_mode_plan.md): publish `python_requires`
        # refs (adas-toolchain) FIRST. `_find_component_dir()` probes every
        # checked-out component with `conan inspect .`, and that probe
        # fails for any component whose conanfile.py itself declares
        # `python_requires = "adas-toolchain/X"` until adas-toolchain has
        # been `conan export`ed at least once (RD-09's real, reproduced
        # ordering bug: pass 1 published only toolchain, the other 5 all
        # reported "no local source found" until a second pass). A stable
        # sort keeping python_requires refs first is sufficient - `conan
        # export` populates the LOCAL cache immediately, before the
        # `conan upload` half of publish_ref() ever runs, so every later
        # probe in this same loop already sees it.
        publish_order = sorted(missing, key=lambda r: r not in python_require_refs)
        print(f"\nPublishing {len(missing)} missing ref(s) with local source available...")
        still_missing = []
        for ref in publish_order:
            comp_dir = _find_component_dir(ref)
            if comp_dir is None:
                print(f"  {ref}: MISSING, no local source found on this machine - "
                      f"a real gap (a different machine, or a real team server, "
                      f"needs to supply it), not something to silently skip.")
                still_missing.append(ref)
                continue
            print(f"  {ref}: building and uploading from {comp_dir} ...")
            if publish_ref(ref, comp_dir, args.remote, args.platform):
                print(f"  {ref}: published.")
            else:
                still_missing.append(ref)
        missing = still_missing

    print()
    if missing:
        print(f"{len(missing)} ref(s) still MISSING: {', '.join(missing)}")
        return 1
    if not_built:
        # WP-5/NS-09: NOT a failure - see the big comment above the loop.
        print(f"{len(not_built)} ref(s) checked out here but not built yet (see NOTBUILT "
              "lines above) - build on demand, or `setup.py --prepare`, as needed.")
        return 0
    print("All required adas-* refs are resolvable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
