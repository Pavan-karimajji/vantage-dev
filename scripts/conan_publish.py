"""
scripts/conan_publish.py

Shared, cross-component publish helper for the `adas-local` Conan remote
(docs/conan_server_remote.md, plan.md item 15). Lives in root scripts/
(not a per-component modules/<name>/scripts/ folder) because every
component's dev-ops GUI - interfaces, shared_config, df, vdy - imports this
instead of duplicating the conan create -> conan upload sequence four
times. Pure subprocess/file-editing helpers; no GUI/Tkinter code here.

RD-05 (remove_develop_mode_plan.md, WP-4): the editable-remove ->
... -> editable-restore wrapping this docstring used to describe is
removed. RD-01's own verdict (WP-1 gate) already established that with
no editables ever registered (RD-03/RD-04), `is_editable()` permanently
returns False and the wrapping was a permanent no-op requiring no
functional fix - this is that "simplify: remove now-unreachable code"
follow-up, not a behaviour change. `conan create` on a real (never
editable) package is the whole sequence now.
"""

import json
import os
import re
import subprocess

import yaml

REMOTE = "adas-local"


class RemoteUnavailableError(Exception):
    """Raised by list_remote_versions() when the remote couldn't be queried
    (unreachable, or the JWT login session expired - server.conf's
    jwt_expire_minutes) - distinct from a genuine empty result (package
    name simply never published yet). Bug #9: before this existed, both
    cases silently collapsed into the same [], and a GUI whose session had
    quietly expired looked exactly like "nothing published, publish
    anything" - the collision guard most needs real data right there."""


class MissingDependencyError(Exception):
    """Raised by publish_commands() when the component being published
    depends on an adas-* package that isn't on the target remote yet (Bug
    #15) - publishing anyway would succeed but produce a package nobody
    else can actually consume, discovered only later at install time."""


def _version_sort_key(version):
    """Parses "X.Y.Z" into a tuple of ints so versions sort numerically, not
    lexicographically (Bug #11: plain sorted() put "10.0.0" before "2.0.0").
    Falls back to -1 for any non-numeric segment instead of raising, so a
    stray non-standard version (pre Bug #12 fix, or a third-party import)
    doesn't crash the whole listing - it just sorts first."""
    return tuple(int(p) if p.isdigit() else -1 for p in version.split("."))


def list_remote_versions(package_name, remote=REMOTE):
    """Versions already published for this package name on the remote,
    sorted oldest-to-newest, e.g. ["1.0.0", "2.0.0"]. Raises
    RemoteUnavailableError if the remote can't be queried at all (network
    down, auth session expired) - callers must handle this distinctly from
    a genuine empty result, which is a normal [] return (package name never
    published, not an error)."""
    try:
        result = subprocess.run(
            ["conan", "list", f"{package_name}/*", "-r", remote, "--format=json"],
            capture_output=True, text=True, timeout=15,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        raise RemoteUnavailableError(f"could not run conan list: {exc}") from exc

    try:
        data = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError) as exc:
        raise RemoteUnavailableError(
            result.stderr.strip() or result.stdout.strip() or str(exc)
        ) from exc

    refs = data.get(remote, {})
    # An expired JWT session makes `conan list` hit an interactive re-auth
    # prompt it can't answer non-interactively - the JSON it still prints
    # comes back as {"error": "..."} for this remote key instead of a real
    # refs dict. Iterating that dict's own key ("error", no "/") used to be
    # silently filtered out by the `"/" in ref` check below, producing an
    # indistinguishable-from-empty [] - this is what Bug #9 was.
    if isinstance(refs, dict) and "error" in refs:
        raise RemoteUnavailableError(str(refs["error"]))
    if result.returncode != 0:
        raise RemoteUnavailableError(
            result.stderr.strip() or f"conan list exited with code {result.returncode}"
        )

    versions = [ref.split("/", 1)[1] for ref in refs if "/" in ref]
    return sorted(versions, key=_version_sort_key)


def read_package_name(component_dir):
    """The Conan package name (e.g. "adas-df") read from this component's
    CMakeLists.txt project() line - the same single source of truth the
    byte-identical conanfile.py's set_name() reads (plan.md item 20,
    docs/conanfile_commonality_plan.md). NOT scraped from conanfile.py any
    more: since item 20 the recipe carries no `name = "..."` literal (set_name()
    derives it), so the old regex would return None and the byte-identical
    build/publish GUI could no longer discover its own package name. Lets a
    single, component-agnostic GUI derive its package name instead of hardcoding
    one per component (plan.md item 17). Returns None if it can't be read."""
    path = os.path.join(component_dir, "CMakeLists.txt")
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None
    match = re.search(r'project\(\s*([A-Za-z0-9_\-]+)', text)
    return match.group(1) if match else None


def _version_file(component_dir):
    return os.path.join(component_dir, "VERSION")


def read_current_version(component_dir):
    """The version this component would publish right now, read from whichever
    source its own conanfile.py's set_version() actually uses: a plain VERSION
    file if one exists (shared_config), else the project(<name> VERSION X.Y.Z
    ...) line in CMakeLists.txt (interfaces/df/vdy). This is the read-side
    twin of bump_version() below - both hide the per-component source
    difference so one byte-identical GUI (plan.md item 17) works for all of
    them. Returns "?" if neither source is readable, so a GUI shows that
    rather than crashing."""
    version_file = _version_file(component_dir)
    if os.path.isfile(version_file):
        try:
            with open(version_file, encoding="utf-8") as f:
                return f.read().strip() or "?"
        except OSError:
            return "?"
    package_name = read_package_name(component_dir)
    cmakelists = os.path.join(component_dir, "CMakeLists.txt")
    try:
        with open(cmakelists, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return "?"
    if package_name:
        match = re.search(
            r"project\(\s*" + re.escape(package_name) + r"\s+VERSION\s+([0-9]+\.[0-9]+\.[0-9]+)",
            content, re.IGNORECASE,
        )
        if match:
            return match.group(1)
    return "?"


def bump_version(component_dir, new_version):
    """Rewrite this component's version at whichever source it really uses -
    a VERSION file if present (shared_config), else the CMakeLists.txt
    project(...) line (interfaces/df/vdy) - so one component-agnostic GUI can
    bump any of them without knowing which kind it is. Delegates to
    bump_version_file/bump_cmake_version, keeping their identical X.Y.Z
    validation. Raises ValueError on a bad version or an unfindable source,
    same as the two helpers it wraps."""
    version_file = _version_file(component_dir)
    if os.path.isfile(version_file):
        bump_version_file(version_file, new_version)
        return
    package_name = read_package_name(component_dir)
    if not package_name:
        raise ValueError(
            f"could not read a package name from {component_dir}/conanfile.py"
        )
    bump_cmake_version(os.path.join(component_dir, "CMakeLists.txt"), package_name, new_version)


def bump_cmake_version(cmakelists_path, package_name, new_version):
    """Rewrites the VERSION number in `project(<package_name> VERSION X.Y.Z
    ...)` inside the given CMakeLists.txt - the same line every component's
    conanfile.py's set_version() already reads. Used by interfaces/df/vdy
    (shared_config has no CMakeLists.txt - see bump_version_file below).
    Raises ValueError if the expected project(...) line isn't found, or if
    new_version isn't a plain X.Y.Z numeric version - CMake's own
    project(VERSION ...) rejects anything else (confirmed live: a
    "0.1.1-guitest" value fails with 'VERSION "..." format invalid' deep
    inside cmake.configure(), not a clean, early error) - so a GUI can
    surface a clear error immediately instead of a build failing later."""
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", new_version):
        raise ValueError(
            f"'{new_version}' is not a plain X.Y.Z numeric version - "
            "CMake's project(VERSION ...) doesn't accept anything else."
        )
    # newline="" on both read and write: preserves the file's original line
    # endings exactly (CRLF on this repo's CMakeLists.txt files) instead of
    # Python's default universal-newlines translation silently rewriting
    # every line ending to the platform default on save - confirmed live,
    # this turned a one-character version bump into a full-file diff.
    with open(cmakelists_path, encoding="utf-8", newline="") as f:
        content = f.read()
    # Matches the whole VERSION token (non-whitespace run), not just a
    # numeric prefix - a strict [0-9]+\.[0-9]+\.[0-9]+ pattern here would
    # only replace a leading numeric segment and silently leave any
    # trailing garbage (e.g. a prior malformed "0.1.1-guitest") in place.
    pattern = re.compile(
        r"(project\(\s*" + re.escape(package_name) + r"\s+VERSION\s+)\S+",
        re.IGNORECASE,
    )
    new_content, count = pattern.subn(r"\g<1>" + new_version, content)
    if count == 0:
        raise ValueError(
            f"Could not find 'project({package_name} VERSION ...)' in {cmakelists_path}"
        )
    with open(cmakelists_path, "w", encoding="utf-8", newline="") as f:
        f.write(new_content)


def bump_version_file(version_file_path, new_version):
    """Overwrites a plain VERSION file (shared_config's own version source -
    its conanfile.py's set_version() reads this file verbatim). Raises
    ValueError if new_version isn't a plain X.Y.Z numeric version - Bug
    #12: this used to accept anything (confirmed live by publishing
    "adas-testpkg/1.0.0-alpha"), the only one of the two version-source
    helpers with zero format validation. Same X.Y.Z-only guard as
    bump_cmake_version, for consistency - nothing in shared_config's design
    calls for non-numeric versioning."""
    new_version = new_version.strip()
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", new_version):
        raise ValueError(
            f"'{new_version}' is not a plain X.Y.Z numeric version."
        )
    with open(version_file_path, "w", encoding="utf-8") as f:
        f.write(new_version + "\n")


def _has_project_option(component_dir):
    """True if this component's conanfile.py actually declares a `project`
    Conan option - checked via Conan's own recipe introspection
    (`conan inspect . --format=json`'s options_definitions), not inferred
    from conf/build.yml's shape. conf/build.yml existing is NOT enough on
    its own: modules/interfaces/conf/build.yml exists purely to stop
    build.py's dispatcher from skipping it (plan.md item 12) and has no
    `project` option behind it at all - confirmed live that passing
    `-o project=...` to it is a hard Conan error, not a harmless no-op."""
    try:
        result = subprocess.run(
            ["conan", "inspect", ".", "--format=json"],
            capture_output=True, text=True, timeout=15, cwd=component_dir,
        )
        if result.returncode != 0:
            return False
        data = json.loads(result.stdout)
        return "project" in data.get("options_definitions", {})
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError, ValueError):
        return False


def _own_variants(component_dir):
    """Project variants this component actually supports (e.g. ["base",
    "cus1"]), sorted for determinism - the source of truth for "how many
    configurations does a real release of this component need." Only
    components whose conanfile.py declares a real `project` Conan option
    (_has_project_option) get more than one; everyone else gets a
    single-element [None] sentinel meaning "build once, no -o project
    flag" rather than "build the base variant" only."""
    if not _has_project_option(component_dir):
        return [None]
    build_yml = os.path.join(component_dir, "conf", "build.yml")
    if not os.path.isfile(build_yml):
        return [None]
    try:
        with open(build_yml, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        variants = sorted(data.get("variants", {}).keys())
        return variants or [None]
    except (OSError, yaml.YAMLError, AttributeError):
        return [None]


def _own_adas_requires(component_dir, variant):
    """adas-* dependencies this component's `variant` build declares in
    conf/build.yml, e.g. ["adas-interfaces/1.0.0",
    "adas-shared-config/1.0.0"] - only these need to exist on the target
    remote before publishing; a conancenter dependency (protobuf, yaml-cpp)
    resolves from conancenter, not adas-local, so it's out of scope here.
    variant=None (components with no conf/build.yml, or no project axis at
    all) always returns []."""
    if variant is None:
        return []
    build_yml = os.path.join(component_dir, "conf", "build.yml")
    if not os.path.isfile(build_yml):
        return []
    try:
        with open(build_yml, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        variant_data = data.get("variants", {}).get(variant, {})
        return [r for r in variant_data.get("requires", []) if r.startswith("adas-")]
    except (OSError, yaml.YAMLError, AttributeError):
        return []


def _missing_dependencies(component_dir, remote=REMOTE, variant=None):
    """adas-* dependency refs (from _own_adas_requires) for this variant
    whose exact version isn't on `remote` yet. Propagates
    RemoteUnavailableError from list_remote_versions() rather than
    swallowing it - if the remote can't be queried, publishing can't be
    safely allowed to proceed either."""
    missing = []
    for ref in _own_adas_requires(component_dir, variant):
        name, _, version = ref.partition("/")
        if version not in list_remote_versions(name, remote):
            missing.append(ref)
    return missing


def publish_commands(component_dir, package_name, version, remote=REMOTE):
    """Ordered list of commands (each a list[str], run from component_dir)
    that publish a new version to the remote. Returned as data - not run
    here - so a GUI can display "$ <command>" for each step first, matching
    every other section's command-display convention, then hand the list to
    its existing process-runner (which already stops the whole sequence at
    the first failing command). Caller must have already updated the
    version source (bump_cmake_version/bump_version_file) before running
    these - `conan create` publishes whatever version is currently declared,
    it doesn't take a version argument itself.

    Builds EVERY project variant this component declares (_own_variants -
    plan.md item 14/15 follow-up: one release version is expected to
    cover every declared variant together, and that guarantee has to come
    from the build sequence, not from Conan itself - `conan upload` was
    confirmed live to upload whatever's in the local cache with zero
    warning if a variant was never built at all). One `conan upload` call
    at the end picks up every package_id just built for this reference, so
    building every variant first, before that single call, is what makes a
    publish all-or-nothing across every configuration - if any variant's
    `conan create` fails, the runner stops before ever reaching upload.

    Raises MissingDependencyError (Bug #15) if this component's own adas-*
    dependencies (checked across every variant, not just one) aren't on
    `remote` yet - refusing to publish a package nobody else could
    actually consume, instead of only discovering that later at install
    time."""
    variants = _own_variants(component_dir)

    missing = []
    for variant in variants:
        for ref in _missing_dependencies(component_dir, remote, variant):
            if ref not in missing:
                missing.append(ref)
    if missing:
        raise MissingDependencyError(
            f"{package_name}/{version} depends on "
            f"{', '.join(missing)} which "
            f"{'is' if len(missing) == 1 else 'are'} not on remote "
            f"'{remote}' yet - publish "
            f"{'it' if len(missing) == 1 else 'them'} first."
        )

    ref = f"{package_name}/{version}"
    cmds = []

    for variant in variants:
        create_cmd = ["conan", "create", ".", "--build=missing", "-s", "build_type=Release"]
        if variant is not None:
            create_cmd += ["-o", f"project={variant}"]
        cmds.append(create_cmd)

    cmds.append(["conan", "upload", ref, "-r", remote, "--confirm"])
    return cmds
