# Copyright (c) LT EPS. All Rights Reserved.
# Proprietary and Confidential.
# @author Pavan Karimajji

"""Superproject-root invariant grep, mirroring modules/sim/scripts/
check_invariants.py's own shape (one function per gate, run_all() unions
them, main() prints findings). Today this holds the CarMaker integration's
two enforced boundaries (docs/cm/df_cm_architecture.md):

  CMG-1 -- src/platform/cm/src/host/** must not name a driving function or
           the df component (df_sil, AdasDf) -- host/ is CarMaker-generic.
  CMG-2 -- src/platform/cm/src/app/** (except CARMAKER_VERSION) must be
           byte-identical to IPG's own vendored skeleton.
  CPY-1 -- every component's copy-distributed build file (build.bat,
           build.sh, scripts/build.py, scripts/build_gui.py, .clang-format)
           must match modules/toolchain/copy_files/ (R-BUILD-3/4/5/6).
           These are the files that CANNOT travel via python_requires --
           a component runs build.bat before any `conan install` has
           happened -- so they are distributed by copy and held identical
           by this gate instead (modules/toolchain/docs/toolchain_plan.md
           §3). Delegates to that repo's own check_copy_files.py rather
           than reimplementing the file list here: COPY_FILES in
           modules/toolchain/scripts/_shared.py stays the one roster.
  LNC-1 -- every launcher .bat that resolves a Python interpreter via
           `where py`/`where python` must verify the candidate actually runs
           before trusting it, not just that `where` found an exe on PATH.
           2026-08-27 incident: setup.bat's PYCMD detection passed on a
           teammate's machine, sim_gui.bat's byte-identical block then failed
           three tools later with "No suitable Python runtime found" -- the
           new-style py launcher can be on PATH with zero runtimes registered,
           and `where` can't tell the difference (docs: R-BUILD-6).
  REM-1  -- NS-36(a) (cache_first_no_server_plan.md, RQ-3/RQ-5, applying
           RQ-8's "prove it on a manufactured machine" discipline to §0
           itself): every copy of `remotes_enabled()` is declared in
           `_SWITCH_FILES` below -- an undeclared copy (new duplicate
           nobody registered here) or a declared copy that stopped
           defining the function both fail. The declared copies' DECISION
           INPUTS must agree: same `REMOTES_ENV_VAR` string, the same
           three loopback hosts, and -- the specific defect this check
           exists to catch, found live 2026-09-24 -- the function body
           must never reference `ADAS_LOCAL_URL` (it may say WHERE a
           remote lives once remotes are already on, in
           `ensure_conan_environment()`/`_ensure_adas_local_remote()`,
           never WHETHER). Compared STRUCTURALLY, via `ast.get_source_
           segment()` on each file's own top-level `remotes_enabled` (and
           `_is_loopback_url`) function, never a raw file diff -- the three
           files legitimately differ elsewhere (docstrings, whether they
           accept a CLI override, surrounding helpers).
  REM-2  -- NS-36(b) (RQ-3/RQ-5): no environment variable other than the
           declared `REMOTES_ENV_VAR` ("ADAS_REMOTES_ENABLED") may decide
           whether remotes are on. Grepped across scripts/, modules/
           toolchain/adas_build_tools/ and modules/toolchain/copy_files/
           for any `ADAS_REMOTES_*`-shaped string literal that is not
           exactly that name -- a second, differently-named remotes flag
           introduced anywhere in those trees is exactly the kind of
           hidden-machine-state RQ-3 forbids.
  BUN-1  -- NS-42(b) (cache_first_no_server_plan.md, RQ-6): when
           misc/offline_bundle/bundle_manifest.txt is present, its
           `pin: adas-build-tools/<v>` must equal the version every
           component's conf/build_tools.version pins, and its
           `pin: adas-toolchain/<v>` must equal this checkout's own
           modules/toolchain/VERSION. A stale bundle looks correct and
           fails only on the offline machine it exists for -- found live
           2026-09-25 when the bundle shipped adas-build-tools/1.0.19
           while every component had already moved to 1.0.22. PASS
           silently when no bundle is present. PT-09 (python_tool_envs_
           plan.md D9): every DEFAULT Python tool env's lock must appear in
           the manifest's `lock:` lines by sha256 -- a lock changed since
           the bundle was made would be refused offline for a missing wheel.
  COLD-1 -- NS-44 (cache_first_no_server_plan.md, RQ-8): makes "re-run the
           cold-machine check after a machinery change" self-enforcing
           instead of a prose reminder. scripts/cold_run_record.json
           (written by cold_machine_check.py only on an all-green run)
           names the commit that run proved; this check fails when any
           commit since then touches scripts/, modules/toolchain/
           adas_build_tools/, modules/toolchain/copy_files/, or any
           component's conf/build_tools.version. No record at all is a
           PASS (most clones cannot run the real Windows-only build) --
           only a STALE record fails. NS-45: every mode in
           COLD1_REQUIRED_MODES is checked on its own entry; a missing mode
           is named. NS-55: each entry must carry a passing `--with-all`
           step (COLD1_WITH_ALL_STEP) -- the flag whose absence from the
           cold check let RV-1 ship.
  PYE-1  -- PT-02 (python_tool_envs_plan.md D1/D2): every component's
           `python_envs:` parses (through the ONE parser,
           adas_build_tools.config.declared_python_envs, imported in-process
           the way CPY-1 imports check_copy_files); every declared lock /
           intent / package path exists; every requirements*.txt and
           pyproject.toml under modules/ is some env's intent (directly or
           via `-r`) or listed in _PYE1_UNDECLARED with its reason; every
           declaring component's .gitignore carries `.venv-*/` (else a
           tool venv trips the freshness fingerprint, plan §5); every lock
           line is a comment or an exact `name==version`.
  DLL-1  -- PT-40: modules/df/tools/carla/dll_lookup.py's one copy of the
           build's folder naming (component build, root solo/agg, _bd_df,
           HOST_BUNDLE_PLATFORM) evaluates equal to workarea.py / build.py /
           bundle_layout.py for the same inputs (HPM-1 style, never text).
  PYF-1  -- PT-29 (python_tool_envs_plan.md D20): no .py under modules/
           outside modules/interfaces puts ANOTHER component's folder, or
           any generated_py folder, on sys.path. Read from the syntax tree
           (never text); a statically unresolvable entry that spells another
           component's name is reported as such. Today's offenders sit on
           _PYF1_OFFENDERS, which may only shrink and must match reality.
  PYV-1  -- PT-30 (D18): every python_envs: entry's `python:` equals the one
           platform Python (adas_build_tools/bundle_layout.py
           PLATFORM_PYTHON) unless it is a declared `exception:`.
  PYB-1  -- PT-33 (D19): every non-exception lock line equals the baseline
           of the adas-build-tools version that component pins (read from
           that wheel in the Conan cache; toolchain: its source baseline).
  PYC-1  -- every CMake `install(DIRECTORY <dir> ...)` under modules/ whose
           source directory holds Python files excludes `__pycache__` and
           `*.pyc`: those are per-machine, per-run bytes, and a package
           carrying them is not reproducible (found 2026-09-29 via
           adas-build-tools 1.0.33's recipe revision; the recipe side is
           modules/toolchain/tests/test_recipe_reproducible.py).
  SIG-1  -- R-IFACE-4's shape check: every message declared as a port
           payload (inputs AND outputs of every visible conf/ports.yaml)
           carries exactly one `sig_header`, nothing nested inside it does,
           or is named in modules/interfaces/scripts/signal_header_waivers.yaml
           (reported on every run; a stale waiver is a violation). Delegates
           to that module's own check_signal_header.py. It never skips: no
           protoc / PyYAML / checked-out interfaces module is a finding that
           names the reason.

Cross-platform leftover state: this repo is routinely built from both
Windows and WSL against the same NTFS-mounted checkout (docs/setup.md).
A WSL-created virtualenv leaves Linux-convention symlinks (e.g. `lib64`
-> `lib`) that native Windows Python cannot `scandir()` through --
WinError 1920, not a permission problem, not a real invariant violation.
Every tree walk here uses `_walk_files()` (`os.walk(..., onerror=...)`),
which skips just that unreadable subtree with a printed warning naming
the exact path and error, and keeps walking everything else -- so this
is expected, handled, and never a crash or a silent skip of a REACHABLE
path.
"""

from __future__ import annotations

import ast
import contextlib
import filecmp
import io
import json
import os
import re
import subprocess
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CM_ROOT = ROOT / "modules" / "df" / "src" / "platform" / "cm"

# REM-1 (NS-36a): the declared allowlist of files that may define
# remotes_enabled() -- module docstring above. Relative to ROOT so this
# reads the same on Windows and WSL.
_SWITCH_FILES = (
    "scripts/conan_home_resolution.py",
    "modules/toolchain/adas_build_tools/conan_ops.py",
    "modules/toolchain/copy_files/scripts/build.py",
)
_REM_LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")

# CMG-1: same word-boundary-on-alnum grep discipline as modules/sim's GT-1
# (a plain \b treats "_" as a word char and would miss a token embedded in a
# snake_case identifier).
_CMG1_TOKENS = re.compile(
    r"(?<![A-Za-z0-9])(aeb|bsd|acc|lca|ldw|lka|df_sil|AdasDf)(?![A-Za-z0-9])", re.IGNORECASE
)

# CMG-2: every app/ file except CARMAKER_VERSION (ours) and app_tmp.cpp
# (generated per build, never vendored) must match IPG's own template
# byte-for-byte.
_CMG2_EXCLUDED = {"CARMAKER_VERSION", "app_tmp.cpp"}
# Our filename differs from IPG's for the one file that is reference-only
# (never compiled) -- CMD-5's own table.
_CMG2_RENAMES = {"User.cpp.ipg-reference": "User.cpp"}


# Directory names no repo-wide walk should ever descend into. Distinct from
# `_LNC1_EXCLUDE_PARTS` below, which filters LNC-1's own findings after the
# fact: these prevent the traversal itself, and exist for cost and
# termination rather than for correctness of the result.
#
# "used" is belt-and-braces, not load-bearing: WP-22 removed the
# vantage<->viz `used/` symlink cycle structurally (a followlinks walk with
# no pruning at all terminates in ~1.0s), so this entry only guards against
# a future regression, not a live cycle.
_PRUNE_DIRNAMES = frozenset({"used", ".venv", "__pycache__", "node_modules"})


def _parse(text: str) -> ast.Module:
    """`ast.parse` for a scanned file: its own invalid escape sequence is that
    file's business, not a check's, and 3.11/3.12 must print the same (D24)."""
    with warnings.catch_warnings():
        # 3.12 reports a bad escape as SyntaxWarning, 3.11 as DeprecationWarning
        warnings.simplefilter("ignore", SyntaxWarning)
        warnings.simplefilter("ignore", DeprecationWarning)
        return ast.parse(text)


def _walk_files(root: Path, suffix: str | None = None) -> list[Path]:
    """Like `sorted(root.rglob(f"*{suffix}"))`, but a subtree `os.scandir()`
    cannot even open (a foreign-OS symlink such as a WSL venv's `lib64` ->
    `lib`, a permission-denied entry, anything OS-specific) is skipped with
    a printed warning naming the exact path and error, never a hard crash
    and never a silent skip -- see the module docstring's cross-platform
    leftover-state note. `Path.rglob()` cannot be told to do this itself
    (it propagates the first `OSError` and aborts the whole walk); plain
    `os.walk()` takes an `onerror` callback for exactly this purpose and
    simply does not recurse into the offending subtree, so every OTHER
    path -- including siblings of the unreadable one -- is still walked
    and checked exactly as before. This never weakens a real invariant:
    a path that DOES resolve is unaffected; only a path that cannot be
    inspected at all is excused, and that exclusion is never silent.
    """
    results: list[Path] = []

    def _onerror(exc: OSError) -> None:
        print(f"WARNING: {exc.filename}: unreadable, skipping ({exc})", file=sys.stderr)

    for dirpath, dirnames, filenames in os.walk(root, onerror=_onerror):
        # Prune DURING the walk, not after it. `conan_workarea/used/` holds
        # shortcuts into other places - the shared cache, or (for an
        # editable dependency) another component's whole source checkout -
        # so descending it walks other repos, and once two components are
        # editable in each other's graph it walks a CYCLE: viz -> used/ ->
        # sim -> vantage -> used/ -> viz -> ... Filtering the RESULTS
        # afterwards (which `check_lnc1`'s own `_LNC1_EXCLUDE_PARTS` does)
        # produces the right answer but only because Windows' path-length
        # limit eventually errors the walk out - an OS limit terminating it,
        # not logic. Measured before this prune: 9s for a check that greps a
        # handful of .bat files.
        #
        # Nothing is lost by pruning: every path reachable through `used/`
        # is either already walked at its own real location, or belongs to a
        # different repository that this check has no business scanning.
        dirnames[:] = [
            d for d in dirnames if d not in _PRUNE_DIRNAMES and not d.startswith(".venv-")
        ]
        for filename in filenames:
            if suffix is None or filename.endswith(suffix):
                results.append(Path(dirpath) / filename)
    return sorted(results)


def check_cmg1(cm_root: Path = CM_ROOT) -> list[str]:
    """CMG-1 -- no function/component name in host/ (CMA/CMD-2)."""
    findings = []
    host_dir = cm_root / "src" / "host"
    if not host_dir.is_dir():
        return findings
    for path in _walk_files(host_dir):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _CMG1_TOKENS.search(line):
                findings.append(f"CMG-1 {path}:{lineno}: function/component name in host/: {line.strip()!r}")
    return findings


def check_cmg2(cm_root: Path = CM_ROOT, carmaker_dir: str | None = None) -> list[str]:
    """CMG-2 -- app/ stays byte-identical to IPG's vendored skeleton
    (CMA/CMD-5). Needs a CarMaker installation to diff against; skipped (not
    failed) when CARMAKER_DIR/IPGHOME cannot be resolved, since most
    checkouts running this script have no CarMaker install."""
    findings = []
    app_dir = cm_root / "src" / "app"
    if not app_dir.is_dir():
        return findings

    cm_dir = carmaker_dir or os.environ.get("CARMAKER_DIR") or os.environ.get("IPGHOME")
    if not cm_dir:
        return findings
    template_src = Path(cm_dir) / "Templates" / "Car" / "src"
    if not template_src.is_dir():
        return findings

    for path in sorted(app_dir.iterdir()):
        if not path.is_file() or path.name in _CMG2_EXCLUDED:
            continue
        ref_name = _CMG2_RENAMES.get(path.name, path.name)
        ref_path = template_src / ref_name
        if not ref_path.is_file():
            findings.append(f"CMG-2 {path}: no corresponding IPG template file '{ref_path}'")
            continue
        if not filecmp.cmp(path, ref_path, shallow=False):
            findings.append(f"CMG-2 {path}: differs from vendored IPG template {ref_path}")
    return findings


_LNC1_EXCLUDE_PARTS = {".venv", "__pycache__", "node_modules", "generators", "used"}
# "used" -- conan_workarea/used/ (dependency-visibility symlinks/junctions,
# pure shortcuts, zero duplication). Excluded because it can cycle: a
# component's used/ symlinks into a sibling checkout that itself contains a
# used/ symlinking back, e.g. df's used/.../adas-sim-0.1.0 -> modules/sim,
# which now contains vantage/conan_workarea/used/.../adas-sim-0.1.0 ->
# modules/sim again. os.walk() follows the cycle on Windows junctions and
# never terminates a plain rglob; found live 2026-09-15 once vantage grew
# its own conan_workarea/used/ for the first time.


def _is_conan_generated_bat(path: Path) -> bool:
    return path.name.startswith(("conanbuild", "conanrun", "deactivate_conan"))


def check_lnc1(root: Path = ROOT) -> list[str]:
    """LNC-1 -- a launcher .bat using `where py`/`where python` must probe the
    candidate with `<cmd> -c ""` before trusting it (see module docstring)."""
    findings = []
    for path in _walk_files(root, suffix=".bat"):
        parts = path.parts
        if _LNC1_EXCLUDE_PARTS & set(parts):
            continue
        if any(p.startswith(".venv-") for p in parts):
            continue
        if any(p == "build" or p.startswith("build-") for p in parts):
            continue
        if _is_conan_generated_bat(path):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "where py" not in text:
            continue
        if '-c ""' not in text:
            findings.append(
                f'LNC-1 {path}: uses "where py"/"where python" without a '
                f'"<cmd> -c \\"\\"" probe -- where finding the launcher stub on '
                f"PATH does not prove a runtime is registered"
            )
    return findings


def check_cpy1(root: Path = ROOT) -> list[str]:
    """CPY-1 -- copy-distributed build files agree with modules/toolchain/
    copy_files/ (see module docstring).

    Runs toolchain's own check_copy_files.py in-process. Its "declared gap"
    output (a component that never carried one of these files -- Option A in
    modules/toolchain/docs/imp_design.md §2.6) is deliberately
    NOT a finding here; only real content drift is. A gap is surfaced by
    running that script directly, which prints the list."""
    scripts_dir = root / "modules" / "toolchain" / "scripts"
    if not (scripts_dir / "check_copy_files.py").is_file():
        # toolchain not checked out (partial clone, R-GIT-1's submodule
        # model) -- silence, not a false green: say so.
        return ["CPY-1 SKIPPED: modules/toolchain is not checked out"]
    sys.path.insert(0, str(scripts_dir))
    try:
        import check_copy_files
    finally:
        sys.path.pop(0)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        rc = check_copy_files.main([])
    if rc == 0:
        return []
    # Only the lines BELOW the "DRIFT DETECTED" header are findings. The
    # declared-gap block above it also lists "modules/..." paths, so a plain
    # startswith("modules/") filter reports Option-A gaps as violations --
    # exactly what this gate must not do (caught by planting a real drift,
    # 2026-09-04, which surfaced all 10 gaps alongside the one true finding).
    lines = buffer.getvalue().splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if "DRIFT DETECTED" in line)
    except StopIteration:
        return [f"CPY-1 check_copy_files failed with no DRIFT block:\n{buffer.getvalue()}"]
    return [
        f"CPY-1 {line.strip()}"
        for line in lines[start:]
        if line.strip().startswith("modules/")
    ]


def _find_function_defs(root: Path, name: str) -> list[Path]:
    """Every .py file under `root` that defines a top-level `def name(...)`,
    found by parsing (not grepping the literal text `def name(` -- that
    would also match a docstring or comment mentioning it). Skips a file
    that fails to parse (never this check's job to validate syntax) rather
    than crashing the whole invariant run over an unrelated file."""
    findings = []
    for path in _walk_files(root, suffix=".py"):
        try:
            tree = _parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        if any(isinstance(node, ast.FunctionDef) and node.name == name
               for node in tree.body):
            findings.append(path)
    return findings


def _function_source(path: Path, name: str) -> str | None:
    """The CODE of the top-level `def name(...)` in `path` -- every
    statement's own `ast.get_source_segment()`, EXCLUDING the function's
    docstring. REM-1's own "structural, not a raw diff" comparison unit
    (module docstring): comparing statements, never prose, so a docstring
    that explains "ADAS_LOCAL_URL is deliberately not read here" (as this
    fix's own remotes_enabled() now does) is never mistaken for the
    function actually reading it. None if `path` defines no such top-level
    function."""
    text = path.read_text(encoding="utf-8")
    tree = _parse(text)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            body = node.body
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                body = body[1:]  # drop the docstring statement
            return "\n".join(
                seg for stmt in body
                if (seg := ast.get_source_segment(text, stmt)) is not None
            )
    return None


def check_rem1(root: Path = ROOT) -> list[str]:
    """REM-1 (NS-36a) -- see module docstring. Two allowlist checks (a
    switch copy that isn't declared, or a declared one that vanished) plus,
    for every declared copy that does exist, three structural agreement
    checks on its `remotes_enabled()` body: no `ADAS_LOCAL_URL` reference,
    the same `REMOTES_ENV_VAR` value, and (via its own `_is_loopback_url`
    helper) the same three loopback hosts."""
    findings: list[str] = []

    declared = {(root / rel).resolve() for rel in _SWITCH_FILES}
    actual = {p.resolve() for p in _find_function_defs(root, "remotes_enabled")}

    # Every component's OWN modules/<name>/scripts/build.py is a copy-
    # distributed instance of modules/toolchain/copy_files/scripts/build.py
    # (R-BUILD-3/6), held byte-identical to it by CPY-1 already -- flagging
    # each one here too would be the same finding eight times over, never a
    # genuinely independent copy of the switch. REM-1 only cares about the
    # one file CPY-1 holds them identical TO, which is in _SWITCH_FILES.
    cpy1_copies = {
        p.resolve() for p in root.glob("modules/*/scripts/build.py")
    }
    actual -= cpy1_copies

    for path in sorted(actual - declared):
        findings.append(
            f"REM-1 (RQ-3/RQ-5): {path.relative_to(root)} defines remotes_enabled() "
            f"but is not declared in check_invariants._SWITCH_FILES -- a new copy of "
            f"the switch must be added there and held to the same agreement checks")
    for path in sorted(declared - actual):
        rel = path.relative_to(root) if path.is_relative_to(root) else path
        findings.append(
            f"REM-1 (RQ-3/RQ-5): declared switch copy {rel} no longer defines "
            f"remotes_enabled() -- either restore it or remove the declaration")

    for rel in _SWITCH_FILES:
        path = root / rel
        if not path.is_file():
            continue
        body = _function_source(path, "remotes_enabled")
        if body is None:
            continue  # already reported above, as a `declared - actual` finding

        if "ADAS_LOCAL_URL" in body:
            findings.append(
                f"REM-1 (RQ-3/RQ-5): {rel}'s remotes_enabled() references "
                f"ADAS_LOCAL_URL -- it may only ever say WHERE a remote lives "
                f"once remotes are already on, never WHETHER they are")

        env_var_match = re.search(r'REMOTES_ENV_VAR\s*=\s*"([^"]+)"', path.read_text(encoding="utf-8"))
        env_var = env_var_match.group(1) if env_var_match else None
        if env_var != "ADAS_REMOTES_ENABLED":
            findings.append(
                f"REM-1 (RQ-3/RQ-5): {rel}'s REMOTES_ENV_VAR is {env_var!r}, "
                f"not 'ADAS_REMOTES_ENABLED' -- every switch copy's override "
                f"name must agree")

        loopback_body = _function_source(path, "_is_loopback_url")
        if loopback_body is None:
            findings.append(
                f"REM-1 (RQ-3/RQ-5): {rel} has no _is_loopback_url() helper -- "
                f"NS-24/D1a's loopback-is-off rule must exist in every switch copy")
        else:
            missing_hosts = [h for h in _REM_LOOPBACK_HOSTS if h not in loopback_body]
            if missing_hosts:
                findings.append(
                    f"REM-1 (RQ-3/RQ-5): {rel}'s _is_loopback_url() is missing "
                    f"{missing_hosts} -- every switch copy must treat the same "
                    f"loopback hosts as 'not a team server'")

    return findings


# REM-2 (NS-36b): any `ADAS_REMOTES_...`-shaped string literal anywhere in
# the three trees this check scans. Matched loosely (any identifier-like
# token starting with the prefix) so a differently-cased or differently-
# suffixed second flag is still caught, not just an exact second copy of
# the declared name.
_REM2_ENV_VAR_LITERAL = re.compile(r'"(ADAS_REMOTES_[A-Z0-9_]*)"')
_REM2_ROOTS = (
    "scripts",
    "modules/toolchain/adas_build_tools",
    "modules/toolchain/copy_files",
)

# Nothing below ships to a component, so a change there cannot make a cold
# run stale (R-TEST-4): every `tests` path segment, markdown, toolchain docs.
_COLD1_EXCLUDES = (
    ":(exclude,glob)**/tests/**",
    ":(exclude,glob)**/*.md",
    ":(exclude)modules/toolchain/docs",
    # The gate's own checks run on a developer's tree and ship nothing to a
    # component, so editing them can never change what a cold machine builds
    # (R-TEST-4: a change that ships nothing must not turn COLD-1 red).
    ":(exclude)scripts/check_invariants.py",
)


def check_rem2(root: Path = ROOT) -> list[str]:
    """REM-2 (NS-36b) -- see module docstring. A grep, not a data-flow
    analysis (RQ-8's own "the message is the documentation people
    actually read" preference for something a reader can verify by eye):
    every `"ADAS_REMOTES_*"` string literal under scripts/, adas_build_
    tools/ and copy_files/ must read exactly `ADAS_REMOTES_ENABLED` --
    the one declared override. A second, differently-named remotes flag
    introduced anywhere in those trees is a finding, wherever it appears
    (not just inside remotes_enabled() itself, since REM-1 already covers
    that function specifically). A `tests/` directory is excluded: it
    legitimately constructs a fake "second flag" as planted-violation test
    data (this check's own regression suite does exactly that), which is
    never a real switch that could run."""
    findings: list[str] = []
    for rel_root in _REM2_ROOTS:
        base = root / rel_root
        if not base.is_dir():
            continue
        for path in _walk_files(base, suffix=".py"):
            if "tests" in path.relative_to(base).parts:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for match in _REM2_ENV_VAR_LITERAL.finditer(text):
                name = match.group(1)
                if name != "ADAS_REMOTES_ENABLED":
                    lineno = text.count("\n", 0, match.start()) + 1
                    findings.append(
                        f"REM-2 (RQ-3/RQ-5): {path.relative_to(root)}:{lineno}: "
                        f"env var literal {name!r} looks like a second remotes "
                        f"switch -- only 'ADAS_REMOTES_ENABLED' may decide "
                        f"whether remotes are on")
    return findings


# BUN-1 (NS-42b, cache_first_no_server_plan.md RQ-6): a stale bundle looks
# correct and fails only on the machine it exists for. A bare X.Y.Z pin
# names a Conan ref (docs/imp_design.md §10); a vX.Y.Z tag installs via pip
# and is out of scope for this bundle mechanism, same distinction
# discover_build_tools_refs() and make_offline_bundle.py's derive_pins()
# already draw.
_BUN1_BARE_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def check_bun1(root: Path = ROOT) -> list[str]:
    """BUN-1 -- D14/PT-21: every platform subfolder of misc/offline_bundle/
    that holds a manifest is checked against that manifest (and the locks it
    declares), with a regenerate command that runs from THIS host. A
    pre-D14 flat bundle in the top folder is itself a finding (it is refused
    by every reader). No bundle at all is a silent PASS."""
    top = root / "misc" / "offline_bundle"
    if not top.is_dir():
        return []
    findings: list[str] = []
    if (top / "bundle_manifest.txt").is_file() or any(top.glob("adas_offline_*.tgz")):
        sys.path.insert(0, str(ROOT / "modules" / "toolchain"))  # code: this checkout's
        try:
            from adas_build_tools.bundle_layout import flat_layout_move_command
        finally:
            sys.path.pop(0)
        findings.append(
            f"BUN-1 (D14): {top.relative_to(root)} holds a bundle in the old flat layout -- "
            f"every reader refuses it; move it into its platform subfolder: "
            f"`{flat_layout_move_command(top)}`")
    for sub in sorted(p for p in top.iterdir() if p.is_dir()):
        if (sub / "bundle_manifest.txt").is_file():
            findings += _bun1_one(root, sub / "bundle_manifest.txt")
    return findings


def _bun1_regen_hint(platform: str | None, include_optional: bool) -> str:
    """PT-21: the regenerate command as it runs from THIS host (the WSL
    command on Windows for a Linux bundle, and so on)."""
    import make_offline_bundle as mob
    platform = platform or "vs2026"
    cmd = mob.bundle_command(platform, include_optional)
    return f"`{cmd}`" if cmd else f"`make_offline_bundle.py --platform {platform}` on a Windows machine"


def _bun1_one(root: Path, manifest_path: Path) -> list[str]:
    """BUN-1 (NS-42b) -- see module docstring. When `misc/offline_bundle/
    bundle_manifest.txt` is present, its `pin: adas-build-tools/<v>` must
    equal the version every component's `conf/build_tools.version` pins,
    and its `pin: adas-toolchain/<v>` must equal this checkout's own
    `modules/toolchain/VERSION` (the same single source of truth `scripts/
    build.py::module_version()` reads for a module with no CMakeLists.txt
    `project(... VERSION ...)`, which is toolchain's case). When no bundle
    is present, PASS silently -- most machines have none (RQ-6: the bundle
    is offline-corporate-PC support, not something every checkout carries).
    Found live 2026-09-25 (second review): the bundle passed a cold run
    only because an unrelated failure (`NS-40`) left a restore path open;
    with that fixed, a stale `adas-build-tools` pin in the bundle is a
    silent `RQ-1` failure on the exact machine the bundle exists for."""
    findings: list[str] = []
    manifest_pins: dict[str, str] = {}
    # A bundle may carry several adas-build-tools versions while components
    # move their pins one at a time (PT-13/WP-8 staging); a pin is covered
    # iff the bundle carries THAT version.
    bundle_bt_versions: set[str] = set()
    manifest_locks: set[str] = set()
    platform = None
    optional_included = False
    for line in manifest_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        key, sep, value = line.partition(": ")
        if sep and key == "pin":
            name, _, version = value.strip().partition("/")
            manifest_pins[name] = version
            if name == "adas-build-tools":
                bundle_bt_versions.add(version)
        elif sep and key == "platform":
            platform = value.strip()
        elif sep and key == "optional":
            optional_included = value.strip() == "included"
        elif sep and key == "lock":
            sha = value.split()[-1]
            if sha.startswith("sha256="):
                manifest_locks.add(sha[len("sha256="):])
    fix_hint = _bun1_regen_hint(platform, optional_included)

    mdir = root / "modules"
    mismatched = []
    for comp_dir in sorted(mdir.iterdir()) if mdir.is_dir() else []:
        pin_file = comp_dir / "conf" / "build_tools.version"
        if not pin_file.is_file():
            continue
        pin_text = pin_file.read_text(encoding="utf-8", errors="ignore").strip()
        if not _BUN1_BARE_VERSION_RE.match(pin_text):
            continue
        if pin_text not in bundle_bt_versions:
            mismatched.append(f"{comp_dir.name} pins {pin_text!r}")
    if mismatched:
        findings.append(
            f"BUN-1 (RQ-6): {manifest_path.relative_to(root)} carries "
            f"'pin: adas-build-tools/{'/'.join(sorted(bundle_bt_versions)) or '(none)'}' but "
            f"{', '.join(mismatched)} -- "
            f"stale bundle, regenerate with {fix_hint}")

    bundle_tc = manifest_pins.get("adas-toolchain")
    version_file = mdir / "toolchain" / "VERSION"
    if version_file.is_file():
        checkout_tc = version_file.read_text(encoding="utf-8").strip()
        if checkout_tc and checkout_tc != bundle_tc:
            findings.append(
                f"BUN-1 (RQ-6): {manifest_path.relative_to(root)} carries "
                f"'pin: adas-toolchain/{bundle_tc}' but this checkout's "
                f"modules/toolchain/VERSION is {checkout_tc!r} -- stale bundle, "
                f"regenerate with {fix_hint}")

    findings += _bun1_stale_locks(root, manifest_path, manifest_locks, fix_hint,
                                  optional_included)
    return findings


def _bun1_stale_locks(root: Path, manifest_path: Path, manifest_locks: set[str],
                      fix_hint: str, optional_included: bool = False) -> list[str]:
    """PT-09: a default env lock whose sha256 is not in the manifest -- and
    (D15/PT-24) every optional env's lock too when the manifest says
    `optional: included`.
    Declarations are read through the one parser, as PYE-1 does; a parse
    error is PYE-1's finding, not repeated here."""
    import hashlib
    tc = root / "modules" / "toolchain"
    if not (tc / "adas_build_tools" / "config.py").is_file():
        return []
    sys.path.insert(0, str(tc))
    try:
        from adas_build_tools import config as bt_config
    finally:
        sys.path.pop(0)
    import yaml
    findings = []
    mdir = root / "modules"
    for comp_dir in sorted(mdir.iterdir()) if mdir.is_dir() else []:
        build_yml = comp_dir / "conf" / "build.yml"
        if not (build_yml.is_file() and (comp_dir / "conanfile.py").is_file()):
            continue  # discover_components()'s own rule
        try:
            envs = bt_config.declared_python_envs(
                yaml.safe_load(build_yml.read_text(encoding="utf-8")) or {},
                component=comp_dir.name)
        except (bt_config.PythonEnvsError, yaml.YAMLError):
            continue
        for env, decl in envs.items():
            lock = comp_dir / decl["lock"]
            if not (decl["default"] or optional_included) or not lock.is_file():
                continue
            if hashlib.sha256(lock.read_bytes()).hexdigest() not in manifest_locks:
                findings.append(
                    f"BUN-1 (PT-09): {manifest_path.relative_to(root)} has no wheels for "
                    f"{comp_dir.name}:{env}'s current lock ({lock.relative_to(root).as_posix()} "
                    f"changed since the bundle was made, or was never bundled) -- "
                    f"regenerate with {fix_hint}")
    return findings


# COLD-1 (NS-44, cache_first_no_server_plan.md RQ-8): every path a change
# to build/toolchain machinery can land in -- the same three trees REM-2
# scans, plus every real component's own conf/build_tools.version pin
# (R-BUILD-2's third ref source). Deliberately NOT scripts/cold_run_
# record.json itself -- the record's own write must never be the change
# that invalidates the record it just wrote.
# NS-55 (cache_first_no_server_plan.md WP-12, RV-7): the step the newest
# cold-run record must carry, passing. cold_machine_check.py imports this
# name rather than spelling it, so the record it writes and the check that
# reads it cannot disagree.
COLD1_WITH_ALL_STEP = "build.py df -t sil -p vs2026 -P base --with-all"

# NS-68 (cache_first_no_server_plan.md WP-13, LK-D3/LK-D6): the three steps that
# prove a build pins its revisions, defined here for the same reason as above -
# the cold check writes these names, COLD-1 reads them.
COLD1_LOCK_MADE_STEP = "a lock exists for the built key and pins adas-interfaces (NS-68)"
COLD1_LOCK_REUSED_STEP = ("second build uses the lock: --lockfile, never partial or "
                          "rewritten (NS-68)")
COLD1_LOCK_REFUSED_STEP = ("planted: a lock naming a revision not in the cache is refused "
                           "(NS-68 Reason / Fix / Run)")
COLD1_LOCK_STEPS = (COLD1_LOCK_MADE_STEP, COLD1_LOCK_REUSED_STEP, COLD1_LOCK_REFUSED_STEP)

# NS-45: the modes a green tree requires. Each has its own record entry and is
# checked on its own -- a mode with no record is named, never skipped.
COLD1_REQUIRED_MODES = ("no-server", "with-server")
_COLD1_RERUN = {
    "no-server": "py -3 scripts\\cold_machine_check.py",
    "with-server": "py -3 scripts\\cold_machine_check.py --with-server",
}

_COLD1_PATHS = (
    "scripts",
    "modules/toolchain/adas_build_tools",
    "modules/toolchain/copy_files",
)


def check_cold1(root: Path = ROOT) -> list[str]:
    """COLD-1 (NS-44) -- see module docstring. RQ-8 says a machinery change
    is not done until it is proven on a manufactured empty machine; before
    this check, "was the cold check re-run after the last machinery
    change" depended on a human reading `cache_first_no_server_plan.md`'s
    own STATUS prose -- exactly the discipline that let four accidental
    PASSes stand undetected. `scripts/cold_run_record.json` (written by
    `cold_machine_check.py` only on an all-green run, one entry per mode)
    names the commit that run proved; this check fails when any commit
    reachable from HEAD but not from that commit touches `_COLD1_PATHS` or
    any component's `conf/build_tools.version`.

    Two failure modes, asymmetric on purpose: NO record at all is a PASS
    with a printed note -- most clones of this repo cannot run a real
    ~10-minute Windows-only build (`cold_machine_check.py` refuses outright
    on non-Windows), so requiring a record everywhere would make this
    check permanently red on every machine that isn't the one doing
    release engineering. A STALE record -- one that exists but no longer
    covers HEAD -- is a FAIL, naming the commits that moved and the exact
    command that clears it. NS-45: once a record exists, EVERY mode in
    COLD1_REQUIRED_MODES is checked against its own entry, and a mode with
    no entry is named. (It used to check only the entry with the latest
    `timestamp_utc`, so re-recording one mode cleared the check while the
    other stayed stale and invisible.)"""
    record_path = root / "scripts" / "cold_run_record.json"
    if not record_path.is_file():
        print("COLD-1 (RQ-8): no cold-run record -- most clones cannot run the "
              "real ~10-minute Windows cold-machine check, so this is expected, "
              "not a violation.", file=sys.stderr)
        return []
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"COLD-1 (RQ-8): {record_path.relative_to(root)} is unreadable or "
                f"not valid JSON ({exc}) -- re-run "
                f"`py -3 scripts\\cold_machine_check.py`."]
    if not isinstance(record, dict) or not record:
        return []

    paths = list(_COLD1_PATHS)
    mdir = root / "modules"
    if mdir.is_dir():
        for comp_dir in sorted(mdir.iterdir()):
            pin_file = comp_dir / "conf" / "build_tools.version"
            if pin_file.is_file():
                paths.append(str(pin_file.relative_to(root)).replace(os.sep, "/"))
    # The record's own write must never be the change that invalidates the
    # record it just wrote (module docstring) -- "scripts" above is a
    # directory pathspec and would otherwise match a commit that only
    # touches scripts/cold_run_record.json itself. Exclude pathspec magic
    # (`:!path`), verified against a real git repo -- see
    # test_check_invariants_cold.py's own dedicated test for this.
    paths.append(":!scripts/cold_run_record.json")
    paths.extend(_COLD1_EXCLUDES)

    # NS-45: EVERY required mode is checked, each against its own commit.
    # Taking only the newest entry let re-recording one mode clear the check
    # while the other stayed stale and invisible.
    findings = []
    for mode in COLD1_REQUIRED_MODES:
        rerun = _COLD1_RERUN[mode]
        entry = record.get(mode)
        sha = (entry or {}).get("commit") if isinstance(entry, dict) else None
        if not sha:
            findings.append(
                f"COLD-1 (RQ-8, NS-45): no `{mode}` cold-run record -- every mode a "
                f"green tree requires ({', '.join(COLD1_REQUIRED_MODES)}) must be "
                f"proven; run `{rerun}`.")
            continue

        steps = {s.get("name"): s.get("ok") for s in entry.get("steps") or []
                 if isinstance(s, dict)}
        if steps.get(COLD1_WITH_ALL_STEP) is not True:
            findings.append(
                f"COLD-1 (RQ-8, NS-55): the `{mode}` cold-run record (commit "
                f"{sha[:8]}) has no passing `{COLD1_WITH_ALL_STEP}` step -- it "
                f"predates the --with-all proof; re-run `{rerun}`.")

        for lock_step in COLD1_LOCK_STEPS:
            if steps.get(lock_step) is not True:
                findings.append(
                    f"COLD-1 (RQ-8, NS-68): the `{mode}` cold-run record (commit "
                    f"{sha[:8]}) has no passing `{lock_step}` step -- it predates the "
                    f"lockfile proof; re-run `{rerun}`.")

        proc = subprocess.run(
            ["git", "log", "--oneline", f"{sha}..HEAD", "--", *paths],
            cwd=str(root), capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            findings.append(
                f"COLD-1 (RQ-8): `git log {sha[:8]}..HEAD` failed "
                f"({proc.stderr.strip()}) -- cannot verify the `{mode}` cold-run "
                f"record ({record_path.relative_to(root)}) still covers HEAD.")
            continue
        commits = [line for line in proc.stdout.splitlines() if line.strip()]
        if commits:
            findings.append(
                f"COLD-1 (RQ-8): build/toolchain machinery moved since the last "
                f"passing `{mode}` cold-machine check (commit {sha[:8]}) -- "
                f"{'; '.join(commits)} -- re-run `{rerun}` before trusting this tree.")
    return findings


# PYE-1 (PT-02): intent-shaped files under modules/ that deliberately belong
# to no python_envs: entry, each with the reason. Relative to ROOT.
_PYE1_UNDECLARED = {
    "modules/toolchain/pyproject.toml":
        "adas-build-tools itself -- installed into every launcher's .venv-<platform> "
        "by the build.py stub (R-BUILD-2), never a tool environment",
    "modules/viz/pyproject.toml":
        "adas_viz, a first-party package with zero dependencies; it reaches tool "
        "envs through adas-viz's Conan package (first_party:, PT-38), never "
        "through this file",
}
_PYE1_LOCK_LINE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*==[A-Za-z0-9][A-Za-z0-9.+!_-]*$")
_PYE1_INTENT_RE = re.compile(r"^(requirements.*\.txt|pyproject\.toml)$")


def _pye1_intent_closure(path: Path, seen: set[Path]) -> None:
    """`path` plus every file it pulls in with `-r`/`--requirement`."""
    path = path.resolve()
    if path in seen or not path.is_file():
        return
    seen.add(path)
    if path.suffix != ".txt":
        return
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.match(r"^\s*(?:-r|--requirement)[ =]\s*(\S+)", line)
        if m:
            _pye1_intent_closure(path.parent / m.group(1), seen)


def _pye1_candidate_files(mdir: Path) -> list[Path]:
    """Every file under each component that git would track -- committed or
    new-but-not-ignored (`ls-files --cached --others --exclude-standard`),
    so gitignored build trees and venvs are never walked (a full walk of
    modules/ took 24 s on the NTFS mount). A component git cannot list falls
    back to `_walk_files()`."""
    files: list[Path] = []
    for comp_dir in sorted(mdir.iterdir()) if mdir.is_dir() else []:
        if not comp_dir.is_dir():
            continue
        proc = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=str(comp_dir), capture_output=True, text=True, check=False)
        if proc.returncode == 0:
            files += [comp_dir / f for f in proc.stdout.split("\0") if f]
        else:
            files += _walk_files(comp_dir)
    return files


def check_pye1(root: Path = ROOT) -> list[str]:
    """PYE-1 (PT-02) -- see module docstring."""
    tc = root / "modules" / "toolchain"
    if not (tc / "adas_build_tools" / "config.py").is_file():
        return ["PYE-1 SKIPPED: modules/toolchain is not checked out"]
    sys.path.insert(0, str(tc))
    try:
        from adas_build_tools import config as bt_config
    finally:
        sys.path.pop(0)
    import yaml

    findings: list[str] = []
    covered: set[Path] = set()
    mdir = root / "modules"
    for comp_dir in sorted(mdir.iterdir()) if mdir.is_dir() else []:
        build_yml = comp_dir / "conf" / "build.yml"
        if not build_yml.is_file():
            continue
        try:
            conf = yaml.safe_load(build_yml.read_text(encoding="utf-8")) or {}
            envs = bt_config.declared_python_envs(conf, component=comp_dir.name)
        except (bt_config.PythonEnvsError, yaml.YAMLError) as exc:
            findings.append(f"PYE-1 (D1): {exc}")
            continue
        if not envs:
            continue
        gitignore = comp_dir / ".gitignore"
        lines = (gitignore.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
                 if gitignore.is_file() else [])
        if ".venv-*/" not in (line.strip() for line in lines):
            findings.append(
                f"PYE-1 (plan §5): modules/{comp_dir.name}/.gitignore lacks `.venv-*/` -- a "
                f"tool venv would make every build refuse as 'changed since cached'")
        for env, decl in envs.items():
            tag = f"PYE-1: {comp_dir.name}:{env}"
            for key in ("intent", "lock", "package"):
                rel = decl[key]
                if rel is None:
                    continue
                target = comp_dir / rel
                if not (target.is_dir() if key == "package" else target.is_file()):
                    findings.append(f"{tag} {key}: modules/{comp_dir.name}/{rel} does not exist"
                                    + (f" -- run `python scripts/lock_python_env.py "
                                       f"{comp_dir.name} {env}`" if key == "lock" else ""))
            _pye1_intent_closure(comp_dir / decl["intent"], covered)
            lock = comp_dir / decl["lock"]
            if lock.is_file():
                for n, line in enumerate(lock.read_text(encoding="utf-8", errors="ignore")
                                         .splitlines(), 1):
                    text = line.strip()
                    if text and not text.startswith("#") and not _PYE1_LOCK_LINE_RE.match(text):
                        findings.append(
                            f"{tag} lock modules/{comp_dir.name}/{decl['lock']}:{n}: "
                            f"`{text}` is not an exact name==version -- regenerate with "
                            f"`python scripts/lock_python_env.py {comp_dir.name} {env}`")

    for path in _pye1_candidate_files(mdir):
        if not _PYE1_INTENT_RE.match(path.name):
            continue
        rel = path.relative_to(root).as_posix()
        if rel in _PYE1_UNDECLARED or path.resolve() in covered:
            continue
        findings.append(
            f"PYE-1 (D1/PR-1): {rel} is an intent file no python_envs: entry declares -- "
            f"declare an env for it in its component's conf/build.yml, or list it in "
            f"_PYE1_UNDECLARED with a reason")
    return findings


def check_hpm1(root: Path = ROOT) -> list[str]:
    """HPM-1 (D14/PT-17): the host -> bundle platform mapping is defined once,
    in adas_build_tools/bundle_layout.py; its one permitted copy is the
    launcher stub (copy_files/scripts/build.py, which runs before that
    package is installed). The two literals must be equal -- compared as
    parsed dicts, never as text. Planted: tests change one side."""
    canon = root / "modules" / "toolchain" / "adas_build_tools" / "bundle_layout.py"
    stub = root / "modules" / "toolchain" / "copy_files" / "scripts" / "build.py"
    if not canon.is_file() or not stub.is_file():
        return ["HPM-1 SKIPPED: modules/toolchain is not checked out"]

    def mapping(path: Path):
        for node in _parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.Assign) and any(
                    getattr(t, "id", None) == "HOST_BUNDLE_PLATFORM" for t in node.targets):
                return ast.literal_eval(node.value)
        return None

    a, b = mapping(canon), mapping(stub)
    if a is None or b is None or a != b:
        return [f"HPM-1 (D14): HOST_BUNDLE_PLATFORM differs -- {canon.relative_to(root)} "
                f"{a!r} vs {stub.relative_to(root)} {b!r}; edit copy_files/ and run "
                f"modules/toolchain/scripts/sync_copy_files.py"]
    return []


# DLL-1 (python_tool_envs_plan.md PT-40): df's replay/bridge DLL lookup
# (modules/df/tools/carla/dll_lookup.py) holds the ONE permitted copy of the
# build's folder naming -- a tool environment has no adas_build_tools to
# import. HPM-1 style: both sides are EVALUATED for the same inputs (never
# compared as text) and must agree: workarea.py's component build folder,
# scripts/build.py's ws_folder_name() and aggregate `_bd_<module>` folder,
# and bundle_layout.py's HOST_BUNDLE_PLATFORM.
_DLL1_CASES = [(t, p, proj) for t in ("sil", "sil_viz") for p in ("vs2026", "ubuntu_gcc")
               for proj in ("base", "cus1")]


def _dll1_compare(dll, editable_output, ws_folder_name, aggregate_bd_dir, host_map) -> list[str]:
    findings = []
    for target, platform, project in _DLL1_CASES:
        want = Path(editable_output(Path("P"), target, platform))
        got = Path("P") / dll.WORKAREA_DIRNAME / dll.component_build_dirname(target, platform)
        if got != want:
            findings.append(f"component build {got} != workarea.py {want}")
        for scope, with_all in (("solo", False), ("agg", True)):
            want = ws_folder_name(target, platform, project, "df", [], with_all)
            got = dll.root_build_dirname(target, platform, project, "df", scope)
            if got != want:
                findings.append(f"root build {got} != build.py ws_folder_name() {want}")
    if dll.aggregate_subdir("df") != aggregate_bd_dir("df"):
        findings.append(f"aggregate subfolder {dll.aggregate_subdir('df')} != build.py "
                        f"{aggregate_bd_dir('df')}")
    if dll.HOST_BUNDLE_PLATFORM != host_map:
        findings.append(f"HOST_BUNDLE_PLATFORM {dll.HOST_BUNDLE_PLATFORM!r} != "
                        f"bundle_layout.py {host_map!r}")
    return [f"DLL-1 (PT-40): modules/df/tools/carla/dll_lookup.py disagrees with the build's "
            f"own naming -- {f}; make the copy equal the build (never a new rule)"
            for f in findings]


def check_dll1(root: Path = ROOT) -> list[str]:
    import importlib.util
    import tempfile
    lookup = root / "modules" / "df" / "tools" / "carla" / "dll_lookup.py"
    tc = root / "modules" / "toolchain"
    if not lookup.is_file() or not (tc / "adas_build_tools").is_dir():
        return ["DLL-1 SKIPPED: modules/df or modules/toolchain is not checked out"]
    spec = importlib.util.spec_from_file_location("_dll1_df_dll_lookup", lookup)
    dll = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dll)
    sys.path.insert(0, str(tc))
    try:
        from adas_build_tools import workarea as bt_workarea
        from adas_build_tools import bundle_layout as bt_layout
    finally:
        sys.path.pop(0)
    sys.path.insert(0, str(root / "scripts"))
    try:
        import build as root_build
    finally:
        sys.path.pop(0)

    def aggregate_bd_dir(module):
        with tempfile.TemporaryDirectory() as ws:
            root_build.generate_aggregate_cmakelists(ws, "base", "sil", set(), [module])
            text = (Path(ws) / "CMakeLists.txt").read_text(encoding="utf-8")
        match = re.search(r'add_subdirectory\("[^"]*" "([^"]+)"\)', text)
        return match.group(1) if match else None

    return _dll1_compare(dll, bt_workarea._editable_build_output, root_build.ws_folder_name,
                         aggregate_bd_dir, bt_layout.HOST_BUNDLE_PLATFORM)


# PYF-1 (python_tool_envs_plan.md D20/PT-29): no .py outside
# modules/interfaces puts ANOTHER component's folder on sys.path, or any
# generated_py folder. Judged from the syntax tree (never text): viz's
# check_python_provider_fence.py and sim's GT-6 name "generated_py" in
# strings precisely because they forbid it. The skip-list is viz's fence
# check's EXCLUDED_DIR_NAMES plus conan_workarea (build output, not source).
_PYF1_SKIP_DIRS = frozenset({
    ".git", "build", "third_party", ".venv", "venv", "__pycache__",
    ".pytest_cache", "generated_py", "node_modules", "conan_workarea",
})
_PYF1_SKIP_PREFIXES = ("build-", ".venv-")
_PYF1_EXEMPT_COMPONENT = "interfaces"
# D23: two lists.
# (a) SHIPPED code (tools, scripts, plug-ins): shrink-only, must match
#     reality (an entry whose file no longer offends is itself a finding),
#     and must be EMPTY at PT-41.
_PYF1_OFFENDERS: dict[str, str] = {
}
# (b) TESTS that deliberately exercise two components together (R-SIM-1
#     allows it for tests). Permanent and reviewed: every entry is a test
#     file, and its reason must name each component it reaches -- "a file
#     under tests/" is not a reason.
_PYF1_TEST_PAIRS: dict[str, str] = {
    "modules/vantage/tests/system/test_a2_equivalence.py":
        "ST-A2-1 equivalence: sim's EgoModel is compared against df's bsdviz "
        "baseline (docs/bsd/py), the code it replaces; skips when df is absent",
    "modules/vantage/tests/system/test_c5_relocatability.py":
        "ST-C5-1: packs a real config bundle with interfaces' own "
        "pack_config_bundle.py (interfaces owns the bundle format) and proves "
        "sim resolves it after relocation",
    "modules/vantage/tests/unit/test_a2_project.py":
        "UT-C5-4/5: hashes a bundle packed by interfaces' pack_config_bundle.py, "
        "the producer of the format sim's ProjectModel reads",
    "modules/vantage/tests/unit/test_c8_plugins.py":
        "UT-C8-1: round-trips interfaces' pack_plugin_bundle.py (build-side packer) "
        "against sim's PluginBundle resolver -- the cross-component contract itself",
    "modules/vantage/tests/unit/test_parity_wp06_plugmeta.py":
        "UT-plugmeta-01..04: bundles packed by interfaces' pack_plugin_bundle.py "
        "must be read by sim's PluginBundle -- the cross-component contract",
}

_UNKNOWN = object()


def _pyf1_components(root: Path) -> list[str]:
    """setup.py::discover_components()'s predicate, rooted at `root` so a
    planted temp tree is judged by its own components."""
    mdir = root / "modules"
    return sorted(d.name for d in mdir.iterdir()
                  if (d / "conanfile.py").exists() and (d / "conf" / "build.yml").exists()
                  ) if mdir.is_dir() else []


class _PyfResolver:
    """Statically evaluates a sys.path argument to a Path where it can:
    string literals, Path(...), `/` chains, `.parent`/`.parents[n]`,
    `.resolve()`, os.path.{abspath,realpath,dirname,join}, str()/os.fspath(),
    and names bound earlier in the same file to such expressions. Anything
    else is _UNKNOWN. Also collects every string literal reached, so an
    unresolvable expression can still be judged by the names it spells."""

    def __init__(self, file: Path, tree: ast.AST):
        self.file = file
        self.bindings: list[tuple[int, str, ast.expr]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        self.bindings.append((node.lineno, t.id, node.value))
            elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and \
                    isinstance(node.target, ast.Name) and node.value is not None:
                self.bindings.append((node.lineno, node.target.id, node.value))
            elif isinstance(node, ast.For) and isinstance(node.target, ast.Name):
                # `for _p in (A, B): sys.path.insert(0, str(_p))` -- the
                # loop variable spells whatever the iterable spells.
                self.bindings.append((node.lineno, node.target.id, node.iter))
        self.bindings.sort(key=lambda b: b[0])

    def _lookup(self, name: str, line: int) -> ast.expr | None:
        found = None
        for lineno, n, value in self.bindings:
            if n == name and lineno <= line:
                found = value
        return found

    def strings(self, node: ast.AST, line: int, depth: int = 0) -> list[str]:
        out: list[str] = []
        if depth > 20:
            return out
        for sub in ast.walk(node):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                out.append(sub.value)
            elif isinstance(sub, ast.Name):
                bound = self._lookup(sub.id, getattr(sub, "lineno", line))
                if bound is not None and bound is not node:
                    out += self.strings(bound, getattr(sub, "lineno", line), depth + 1)
        return out

    def value(self, node: ast.AST, line: int, depth: int = 0):
        if depth > 20:
            return _UNKNOWN
        ev = lambda n: self.value(n, getattr(n, "lineno", line), depth + 1)  # noqa: E731
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, (ast.Tuple, ast.List)):
            # only reached through a `for` binding: each element is judged
            return [ev(e) for e in node.elts]
        if isinstance(node, ast.Name):
            if node.id == "__file__":
                return self.file
            bound = self._lookup(node.id, line)
            return _UNKNOWN if bound is None else self.value(bound, bound.lineno, depth + 1)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            left, right = ev(node.left), ev(node.right)
            if isinstance(left, Path) and isinstance(right, (str, Path)):
                return left / right
            return _UNKNOWN
        if isinstance(node, ast.Attribute):
            base = ev(node.value)
            if isinstance(base, str):
                base = Path(base)
            if isinstance(base, Path) and node.attr == "parent":
                return base.parent
            return _UNKNOWN
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute) \
                and node.value.attr == "parents":
            base = ev(node.value.value)
            idx = node.slice
            if isinstance(base, str):
                base = Path(base)
            if isinstance(base, Path) and isinstance(idx, ast.Constant) and isinstance(idx.value, int):
                try:
                    return base.parents[idx.value]
                except IndexError:
                    return _UNKNOWN
            return _UNKNOWN
        if isinstance(node, ast.Call):
            func = node.func
            fname = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            args = [ev(a) for a in node.args]
            to_path = fname in ("str", "fspath") or (fname or "").endswith("Path")
            if to_path and len(args) == 1 and isinstance(args[0], list):
                return [Path(x) if isinstance(x, (str, Path)) else _UNKNOWN for x in args[0]]
            if (fname or "").endswith("Path") and len(args) == 1:
                return Path(args[0]) if isinstance(args[0], (str, Path)) else _UNKNOWN
            if fname in ("str", "fspath", "abspath", "realpath",
                         "normpath") and len(args) == 1:
                a = args[0]
                return Path(a) if isinstance(a, (str, Path)) else _UNKNOWN
            if fname == "dirname" and len(args) == 1 and isinstance(args[0], (str, Path)):
                return Path(args[0]).parent
            if fname == "join" and args and all(isinstance(a, (str, Path)) for a in args):
                return Path(*args)
            if fname in ("resolve", "absolute", "expanduser") and isinstance(func, ast.Attribute):
                base = ev(func.value)
                return Path(base) if isinstance(base, (str, Path)) else _UNKNOWN
        return _UNKNOWN


def _pyf1_path_args(tree: ast.AST) -> list[tuple[int, ast.expr]]:
    """Every expression added to sys.path: insert/append/extend,
    site.addsitedir, `sys.path += [...]`, `sys.path[a:b] = [...]`."""

    def is_sys_path(n: ast.AST) -> bool:
        return (isinstance(n, ast.Attribute) and n.attr == "path"
                and isinstance(n.value, ast.Name) and n.value.id == "sys")

    def elements(n: ast.expr) -> list[ast.expr]:
        return list(n.elts) if isinstance(n, (ast.List, ast.Tuple)) else [n]

    out: list[tuple[int, ast.expr]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            f = node.func
            if is_sys_path(f.value) and f.attr == "insert" and len(node.args) == 2:
                out.append((node.lineno, node.args[1]))
            elif is_sys_path(f.value) and f.attr == "append" and node.args:
                out.append((node.lineno, node.args[0]))
            elif is_sys_path(f.value) and f.attr == "extend" and node.args:
                out += [(node.lineno, e) for e in elements(node.args[0])]
            elif f.attr == "addsitedir" and isinstance(f.value, ast.Name) \
                    and f.value.id == "site" and node.args:
                out.append((node.lineno, node.args[0]))
        elif isinstance(node, ast.AugAssign) and is_sys_path(node.target):
            out += [(node.lineno, e) for e in elements(node.value)]
        elif isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Subscript) and is_sys_path(t.value) for t in node.targets):
            out += [(node.lineno, e) for e in elements(node.value)]
    return out


def _pyf1_files(root: Path) -> list[Path]:
    files = []
    for path in _pye1_candidate_files(root / "modules"):
        if path.suffix != ".py" or not path.is_file():
            continue
        parts = path.relative_to(root).parts[:-1]
        if any(p in _PYF1_SKIP_DIRS or p.startswith(_PYF1_SKIP_PREFIXES) for p in parts):
            continue
        files.append(path)
    return files


def _pyf1_judge(where: str, own: str, value: Path, mroot: Path) -> list[str]:
    """A fully resolved sys.path entry: a generated_py folder, or another
    component's folder, is a finding; anything else is not."""
    if "generated_py" in value.parts:
        return [f"PYF-1 (D20): {where} puts a generated_py folder on sys.path "
                f"({value}) -- build message classes from descriptors (D21)"]
    try:
        target = value.relative_to(mroot).parts
    except ValueError:
        return []  # outside modules/: not a component folder
    if target and target[0] != own:
        return [f"PYF-1 (D20): {where} puts another component's folder on "
                f"sys.path: modules/{'/'.join(target)} (this file belongs to "
                f"{own}) -- take it from that component's package instead"]
    return []


class _PyfResult:
    """One file's PYF-1 outcome: findings, the other components it reaches,
    and whether it could be parsed at all (D24)."""

    def __init__(self, findings=(), targets=(), unparseable=False):
        self.findings, self.targets, self.unparseable = list(findings), set(targets), unparseable


def _pyf1_file_findings(root: Path, path: Path, components: list[str]) -> "_PyfResult":
    rel = path.relative_to(root).as_posix()
    own = path.relative_to(root / "modules").parts[0]
    if own == _PYF1_EXEMPT_COMPONENT:
        return _PyfResult()
    try:
        tree = _parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError as exc:
        # D24: never a silent skip, and never "no longer offends".
        return _PyfResult([f"PYF-1 (D24): {rel} cannot be parsed by Python "
                           f"{sys.version_info.major}.{sys.version_info.minor} ({exc.msg}, line "
                           f"{exc.lineno}), so whether it borrows from a neighbour is unknown -- "
                           f"{_pyf1_rerun_hint()}"], unparseable=True)
    res = _PyfResolver(path.resolve(), tree)
    mroot = (root / "modules").resolve()
    findings = []
    for line, expr in _pyf1_path_args(tree):
        value = res.value(expr, line)
        literals = res.strings(expr, line)
        where = f"{rel}:{line}"
        values = value if isinstance(value, list) else [value]
        if len(values) > 1 or isinstance(value, list):
            # a loop over several paths: judge each resolved one, and any
            # unresolved one by the literals it spells (below)
            resolved = [v for v in values if isinstance(v, Path) and v.is_absolute()]
            for v in resolved:
                findings += _pyf1_judge(where, own, Path(os.path.normpath(v)), mroot)
            if len(resolved) == len(values):
                continue
            value = _UNKNOWN
        if isinstance(value, Path) and value.is_absolute():
            findings += _pyf1_judge(where, own, Path(os.path.normpath(value)), mroot)
            continue
        if any("generated_py" in s for s in literals):
            findings.append(f"PYF-1 (D20): {where} puts a path naming generated_py on "
                            f"sys.path (could not be fully resolved) -- build message classes "
                            f"from descriptors (D21)")
            continue
        segments = {seg for s in literals for seg in re.split(r"[\\/]", s) if seg}
        others = sorted(c for c in components if c != own and c in segments)
        if others:
            findings.append(f"PYF-1 (D20): {where} adds a sys.path entry naming component "
                            f"{', '.join(others)} (could not be fully resolved) -- take it "
                            f"from that component's package instead")
    targets = set()
    for f in findings:
        # skip "PYF-1 (Dnn): <where> " -- the file's own path is not a target
        body = f.split(" ", 3)[-1]
        targets |= set(re.findall(r"modules/([A-Za-z0-9_-]+)", body.split(" on sys.path", 1)[-1]))
        m = re.search(r"naming component (.+?) \(could not", f)
        if m:
            targets |= {c.strip() for c in m.group(1).split(",")}
        if "generated_py" in f:
            targets.add("interfaces")
    return _PyfResult(findings, targets)


def _platform_python(root: Path) -> str | None:
    """D18's platform Python for this host, from adas_build_tools."""
    tc = root / "modules" / "toolchain"
    if not (tc / "adas_build_tools" / "bundle_layout.py").is_file():
        return None
    sys.path.insert(0, str(tc))
    try:
        from adas_build_tools import bundle_layout
    finally:
        sys.path.pop(0)
    return bundle_layout.platform_python()


def _platform_python_cmd(version: str) -> list[str]:
    return ["py", f"-{version}"] if sys.platform == "win32" else [f"python{version}"]


def _pyf1_rerun_hint() -> str:
    ver = _platform_python(ROOT) or "3.12"
    return ("run it with the platform Python: `py -" + ver + r" scripts\check_invariants.py`"
            if sys.platform == "win32"
            else f"run it with the platform Python: `python{ver} scripts/check_invariants.py`")


def _is_test_file(rel: str) -> bool:
    parts = rel.split("/")
    return (any(p in ("tests", "test") for p in parts[:-1])
            or parts[-1].startswith("test_") or parts[-1] == "conftest.py")


def _older_than_platform(version: str | None) -> bool:
    if not version:
        return False
    want = tuple(int(x) for x in version.split("."))
    return sys.version_info[:len(want)] < want


def check_pyf1(root: Path = ROOT, offenders: dict[str, str] | None = None,
               test_pairs: dict[str, str] | None = None, delegate: bool = True) -> list[str]:
    """PYF-1 (PT-29, D23, D24) -- see the comment above _PYF1_SKIP_DIRS.

    D24: on an interpreter older than the platform Python, the whole check
    runs again under the platform Python when it is installed, so the result
    never depends on which Python ran it; without it, every file this
    interpreter cannot parse is a finding."""
    if (delegate and offenders is None and test_pairs is None
            and _older_than_platform(_platform_python(root))):
        cmd = _platform_python_cmd(_platform_python(root)) + [
            "-c", "import json, sys; sys.path.insert(0, sys.argv[1]); import check_invariants as c; "
                  "print(json.dumps(c.check_pyf1(c.Path(sys.argv[2]), delegate=False)))",
            str(Path(__file__).resolve().parent), str(root)]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except OSError:
            proc = None
        if proc is not None and proc.returncode == 0:
            return json.loads(proc.stdout.strip().splitlines()[-1])
    offenders = _PYF1_OFFENDERS if offenders is None else offenders
    test_pairs = _PYF1_TEST_PAIRS if test_pairs is None else test_pairs
    if not (root / "modules").is_dir():
        return ["PYF-1 SKIPPED: no modules/ folder"]
    components = _pyf1_components(root)
    findings: list[str] = []
    results: dict[str, _PyfResult] = {}
    for path in _pyf1_files(root):
        rel = path.relative_to(root).as_posix()
        res = _pyf1_file_findings(root, path, components)
        results[rel] = res
        if res.unparseable or (res.findings and rel not in offenders and rel not in test_pairs):
            findings += res.findings
    for rel in sorted(set(offenders) | set(test_pairs)):
        res = results.get(rel)
        if res is not None and res.unparseable:
            continue  # unknown, already a finding (D24) -- never "no longer offends"
        which = "_PYF1_OFFENDERS" if rel in offenders else "_PYF1_TEST_PAIRS"
        if res is None or not res.findings:
            findings.append(f"PYF-1 (D20): {rel} is on {which} but no longer offends -- remove "
                            f"its entry from scripts/check_invariants.py (the list only shrinks)")
    for rel, reason in sorted(test_pairs.items()):
        if rel in offenders:
            findings.append(f"PYF-1 (D23): {rel} is on both _PYF1_OFFENDERS and "
                            f"_PYF1_TEST_PAIRS -- keep it on one")
        if not _is_test_file(rel):
            findings.append(f"PYF-1 (D23): {rel} is on _PYF1_TEST_PAIRS but is not a test (no "
                            f"tests/ folder, not test_*.py) -- move it to _PYF1_OFFENDERS (shipped "
                            f"code must reach an empty list)")
        res = results.get(rel)
        missing = sorted(t for t in (res.targets if res else ()) if t not in (reason or ""))
        if not (reason or "").strip():
            findings.append(f"PYF-1 (D23): {rel} is on _PYF1_TEST_PAIRS without a reason -- "
                            f"write why this test must exercise both components")
        elif missing:
            findings.append(f"PYF-1 (D23): {rel}'s _PYF1_TEST_PAIRS reason does not name "
                            f"{', '.join(missing)}, which it reaches -- say why the test needs it")
    return findings


def _declared_envs_by_component(root: Path):
    """[(component, {env: decl})] through the ONE parser, or None when
    toolchain is not checked out. Parse errors are PYE-1's to report."""
    tc = root / "modules" / "toolchain"
    if not (tc / "adas_build_tools" / "config.py").is_file():
        return None, None
    sys.path.insert(0, str(tc))
    try:
        from adas_build_tools import bundle_layout, config as bt_config
    finally:
        sys.path.pop(0)
    import yaml
    out = []
    mdir = root / "modules"
    for comp_dir in sorted(mdir.iterdir()) if mdir.is_dir() else []:
        build_yml = comp_dir / "conf" / "build.yml"
        if not build_yml.is_file():
            continue
        try:
            conf = yaml.safe_load(build_yml.read_text(encoding="utf-8")) or {}
            envs = bt_config.declared_python_envs(conf, component=comp_dir.name)
        except (bt_config.PythonEnvsError, yaml.YAMLError):
            continue
        if envs:
            out.append((comp_dir.name, envs))
    return out, bundle_layout


_PYC_EXCLUDES = ('PATTERN "__pycache__" EXCLUDE', 'PATTERN "*.pyc" EXCLUDE')
_INSTALL_KEYWORDS = frozenset({
    "DESTINATION", "TYPE", "FILE_PERMISSIONS", "DIRECTORY_PERMISSIONS",
    "USE_SOURCE_PERMISSIONS", "OPTIONAL", "CONFIGURATIONS", "COMPONENT",
    "EXCLUDE_FROM_ALL", "FILES_MATCHING", "PATTERN", "REGEX", "MESSAGE_NEVER",
})


def _install_directory_calls(text: str):
    """(line, body) for every `install(DIRECTORY ...)` call in a CMake file,
    parentheses balanced, comments stripped."""
    text = re.sub(r"#[^\n]*", "", text)
    for match in re.finditer(r"\binstall\s*\(", text):
        depth, i = 1, match.end()
        while i < len(text) and depth:
            depth += {"(": 1, ")": -1}.get(text[i], 0)
            i += 1
        body = text[match.end():i - 1]
        if body.split()[:1] == ["DIRECTORY"]:
            yield text.count("\n", 0, match.start()) + 1, body


def check_pyc1(root: Path = ROOT) -> list[str]:
    """PYC-1: an install(DIRECTORY) of a Python-bearing source directory
    excludes __pycache__ and *.pyc (see the module docstring)."""
    findings = []
    cmakes = []
    # Source trees only: pruned during the walk (build output, venvs and
    # vendored code hold thousands of dirs and no install() of ours).
    skip = _PYF1_SKIP_DIRS | _PRUNE_DIRNAMES | {"_deps"}
    for dirpath, dirnames, filenames in os.walk(root / "modules"):
        dirnames[:] = sorted(d for d in dirnames
                             if d not in skip and not d.startswith(_PYF1_SKIP_PREFIXES))
        if "CMakeLists.txt" in filenames:
            cmakes.append(Path(dirpath) / "CMakeLists.txt")
    for cmake in cmakes:
        text = cmake.read_text(encoding="utf-8", errors="ignore")
        for line, body in _install_directory_calls(text):
            normalized = " ".join(body.split())
            if all(e in normalized for e in _PYC_EXCLUDES):
                continue
            for token in body.split()[1:]:
                token = token.strip('"')
                if token in _INSTALL_KEYWORDS:
                    break
                if "$" in token:  # generator expression / variable: not statically resolvable
                    continue
                src = cmake.parent / token
                if src.is_dir() and any(src.rglob("*.py")):
                    rel = cmake.relative_to(root).as_posix()
                    findings.append(
                        f"PYC-1: {rel}:{line} install(DIRECTORY {token}) packages Python files "
                        f"but does not exclude __pycache__/*.pyc. Reason: those bytes differ per "
                        f"machine and per run, so the package is not reproducible. Fix: add "
                        f"`PATTERN \"__pycache__\" EXCLUDE PATTERN \"*.pyc\" EXCLUDE` to that "
                        f"install(). Run: python scripts/check_invariants.py")
    return findings


def _package_dir_exceptions(root: Path) -> dict[str, str]:
    """PACKAGE_DIR_EXCEPTIONS from scripts/build.py, read by `ast` -- this
    module does not import build.py, and the list must not be copied here."""
    tree = ast.parse((root / "scripts" / "build.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if (isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "PACKAGE_DIR_EXCEPTIONS" for t in node.targets)):
            return ast.literal_eval(node.value)
    return {}


def check_pkg1(root: Path = ROOT) -> list[str]:
    """PKG-1 (partial_clone_correctness_plan.md D10): scripts/build.py maps a
    first-party package to its folder by convention (`adas-<x>` -> modules/<x>)
    plus PACKAGE_DIR_EXCEPTIONS. Every checked-out module's CMakeLists.txt
    project() name must map back to its own folder; a checked-out module that
    does not is a package the dispatcher would refuse or misplace."""
    exceptions = _package_dir_exceptions(root)
    findings = []
    modules = root / "modules"
    for mod in sorted(p for p in modules.iterdir() if p.is_dir()) if modules.is_dir() else []:
        cmake, conanfile = mod / "CMakeLists.txt", mod / "conanfile.py"
        if not (cmake.is_file() and conanfile.is_file()):
            continue  # not checked out, or not a package
        match = re.search(r"project\(\s*([A-Za-z0-9_\-]+)", cmake.read_text(encoding="utf-8"))
        if not match:
            continue
        name = match.group(1)
        folder = exceptions.get(name, name[len("adas-"):] if name.startswith("adas-") else None)
        if folder != mod.name:
            findings.append(
                f"PKG-1: modules/{mod.name}/CMakeLists.txt project({name}) does not map back to "
                f"modules/{mod.name}. Reason: scripts/build.py derives a package's folder as "
                f"adas-<x> -> modules/<x> plus PACKAGE_DIR_EXCEPTIONS, so the dispatcher would "
                f"refuse or misplace this package. Fix: rename the project to adas-{mod.name}, "
                f"or add \"{name}\": \"{mod.name}\" to PACKAGE_DIR_EXCEPTIONS in "
                f"scripts/build.py. Run: python scripts/check_invariants.py")
    return findings


def check_pyv1(root: Path = ROOT) -> list[str]:
    """PYV-1 (PT-30, D18): every python_envs: entry's `python:` equals the
    one Python version of each platform (bundle_layout.PLATFORM_PYTHON),
    unless the env is a declared `exception:` (D19)."""
    declared, bundle_layout = _declared_envs_by_component(root)
    if declared is None:
        return ["PYV-1 SKIPPED: modules/toolchain is not checked out"]
    findings = []
    for comp, envs in declared:
        for env, decl in envs.items():
            if decl.get("exception"):
                continue
            wrong = {p: v for p, v in bundle_layout.PLATFORM_PYTHON.items() if v != decl["python"]}
            if wrong:
                findings.append(
                    f"PYV-1 (D18): {comp}:{env} declares python: \"{decl['python']}\" but the "
                    f"platform Python is {', '.join(f'{v} on {p}' for p, v in wrong.items())} "
                    f"(modules/toolchain/adas_build_tools/bundle_layout.py) -- set python: "
                    f"\"{next(iter(wrong.values()))}\" in modules/{comp}/conf/build.yml, or "
                    f"declare the env an exception: with its reason (D19)")
    return findings


def check_pyb1(root: Path = ROOT, baseline_for=None) -> list[str]:
    """PYB-1 (PT-33, D19): every non-exception env's lock line equals the
    baseline that component uses -- the one inside the adas-build-tools
    version it PINS (read from that wheel in the Conan cache), or, for
    toolchain (D8), toolchain's own source baseline. One resolver:
    scripts/python_baseline.py."""
    declared, _ = _declared_envs_by_component(root)
    if declared is None:
        return ["PYB-1 SKIPPED: modules/toolchain is not checked out"]
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import python_baseline
    finally:
        sys.path.pop(0)
    baseline_for = baseline_for or python_baseline.baseline_for
    findings = []
    for comp, envs in declared:
        todo = {e: d for e, d in envs.items() if not d.get("exception")}
        if not todo:
            continue
        try:
            baseline, where = baseline_for(root, comp)
        except python_baseline.BaselineMissing as exc:
            findings.append(f"PYB-1 (D19): {comp}: {exc.reason} Fix: {exc.fix} Run: {exc.run}")
            continue
        for env, decl in todo.items():
            lock = root / "modules" / comp / decl["lock"]
            if not lock.is_file():
                continue  # PYE-1 reports a missing lock
            for norm_name, (name, version) in python_baseline.parse(
                    lock.read_text(encoding="utf-8", errors="ignore")).items():
                base = baseline.get(norm_name)
                if base is None:
                    findings.append(
                        f"PYB-1 (D19): {comp}:{env} locks {name}=={version}, which is not in the "
                        f"baseline of {where} -- add it to an intent file and regenerate the "
                        f"baseline (scripts/make_python_baseline.py), or declare the env an "
                        f"exception:")
                elif base[1] != version:
                    findings.append(
                        f"PYB-1 (D19): {comp}:{env} locks {name}=={version} but the baseline of "
                        f"{where} says {base[0]}=={base[1]} -- regenerate the lock: "
                        f"`python scripts/lock_python_env.py {comp} {env}`")
    return findings


# Lines SIG-1 wants printed on every run, clean or not (the waivers in force).
SIG1_NOTES: list[str] = []


def check_sig1(root: Path = ROOT) -> list[str]:
    """SIG-1 -- R-IFACE-4's shape check over every port payload (see module docstring).

    Runs modules/interfaces/scripts/check_signal_header.py in-process. Anything
    that stops it running is a finding naming the reason, never a skip."""
    SIG1_NOTES.clear()
    scripts_dir = root / "modules" / "interfaces" / "scripts"
    if not (scripts_dir / "check_signal_header.py").is_file():
        return ["SIG-1 SKIPPED: modules/interfaces is not checked out"]
    sys.path.insert(0, str(scripts_dir))
    try:
        import check_signal_header as csh
    finally:
        sys.path.pop(0)
    try:
        report = csh.run(csh.INTERFACES_ROOT / "proto", csh.discover_ports(csh.INTERFACES_ROOT),
                         csh.find_protoc(), csh.read_waivers(csh.WAIVERS_FILE))
    except csh.CheckError as exc:
        return [f"SIG-1 cannot run: {exc}"]
    SIG1_NOTES.append(f"SIG-1: {len(report.payloads_enforced)} port payload(s) checked, "
                      f"{len(report.waived) + len(report.unseen_waivers)} waived")
    SIG1_NOTES.extend(f"SIG-1{line}" for line in report.waiver_lines())
    return [f"SIG-1 {violation}" for violation in report.violations]


SHP1_NOTES: list[str] = []


def check_shp1(root: Path = ROOT) -> list[str]:
    """SHP-1 -- every compiled df function has the same artefacts in the same places
    (.claude/workflows/add_function.md, "The canonical per-function shape").

    Runs modules/df/scripts/check_function_shape.py in-process; its waivers are printed
    on every run (SHP1_NOTES). Anything that stops it running is a finding, never a skip."""
    SHP1_NOTES.clear()
    df_root = root / "modules" / "df"
    if not (df_root / "scripts" / "check_function_shape.py").is_file():
        return ["SHP-1 SKIPPED: modules/df is not checked out"]
    sys.path.insert(0, str(df_root / "scripts"))
    try:
        import check_function_shape as cfs
    finally:
        sys.path.pop(0)
    try:
        violations, lines, matrix = cfs.check(df_root)
    except Exception as exc:  # noqa: BLE001 -- a checker that cannot run must say why
        return [f"SHP-1 cannot run: {exc}"]
    SHP1_NOTES.append(f"SHP-1: {len(matrix)} function(s) checked, {len(lines)} waived")
    SHP1_NOTES.extend(lines)
    return violations


def check_uc1(root: Path = ROOT) -> list[str]:
    """UC-1 -- the use-case tags are the trace, and they are checked (modules/df/docs/ldw/LDW_Use_Case_Catalogue.md section 3
    rule 7): a `UC-nn` tag on a bench case or in a CARLA scenario names a row of the catalogue; a row marked `[x]` has a tagged
    case or scenario; and the latest by-use-case record has a section for it with no NOT RUN in it.

    Runs modules/df/scripts/check_use_cases.py in-process. Anything that stops it running is a finding, never a skip."""
    df_root = root / "modules" / "df"
    if not (df_root / "scripts" / "check_use_cases.py").is_file():
        return ["UC-1 SKIPPED: modules/df is not checked out"]
    sys.path.insert(0, str(df_root / "scripts"))
    try:
        import check_use_cases as cuc
    finally:
        sys.path.pop(0)
    try:
        return cuc.check(df_root)
    except Exception as exc:  # noqa: BLE001 -- a checker that cannot run must say why
        return [f"UC-1 cannot run: {exc}"]


def run_all(cm_root: Path = CM_ROOT) -> list[str]:
    return [
        *check_cmg1(cm_root),
        *check_cmg2(cm_root),
        *check_cpy1(),
        *check_lnc1(),
        *check_rem1(),
        *check_rem2(),
        *check_bun1(),
        *check_cold1(),
        *check_pye1(),
        *check_hpm1(),
        *check_dll1(),
        *check_pyf1(),
        *check_pyv1(),
        *check_pyb1(),
        *check_pyc1(),
        *check_pkg1(),
        *check_sig1(),
        *check_shp1(),
        *check_uc1(),
    ]


def older_interpreter_notice(root: Path = ROOT) -> list[str]:
    """D24: one Reason / Fix / Run up front when this interpreter is older
    than the platform Python (D18); the checks still run and report."""
    version = _platform_python(root)
    if not _older_than_platform(version):
        return []
    run = (f"py -{version} scripts\\check_invariants.py" if sys.platform == "win32"
           else f"python{version} scripts/check_invariants.py")
    return [f"Reason: this is Python {sys.version_info.major}.{sys.version_info.minor}, older than "
            f"the platform Python {version} (D18); files it cannot parse are re-checked under "
            f"{version} when it is installed, else reported (D24).",
            f"Fix:    run the invariants with the platform Python.",
            f"Run:    {run}"]


def _skip_for_module_not_in_superproject(finding: str, root: Path = ROOT) -> bool:
    """A `<CHECK> SKIPPED: modules/<x> ...` finding is a note, not a violation,
    when <x> is not a submodule of THIS superproject at all (vantage-dev has no
    df). A skip for a declared-but-missing module still fails, as in 1v."""
    if " SKIPPED: " not in finding:
        return False
    gm = root / ".gitmodules"
    declared = set(re.findall(r"path\s*=\s*(\S+)", gm.read_text(encoding="utf-8"))) if gm.is_file() else set()
    named = set(re.findall(r"modules/[A-Za-z0-9_\-]+", finding))
    return bool(named) and any(m not in declared for m in named)


def main(argv: list[str] | None = None) -> int:
    for line in older_interpreter_notice():
        print(line)
    findings = run_all()
    for note in [f for f in findings if _skip_for_module_not_in_superproject(f)]:
        print(note + " (not part of this superproject)")
    findings = [f for f in findings if not _skip_for_module_not_in_superproject(f)]
    for note in SIG1_NOTES + SHP1_NOTES:
        print(note)
    for finding in findings:
        print(finding)
    if findings:
        print(f"\n{len(findings)} invariant violation(s)")
        return 1
    print("CMG-1, CMG-2, CPY-1, LNC-1, REM-1, REM-2, BUN-1, COLD-1, PYE-1, HPM-1, DLL-1, PYF-1, PYV-1, PYB-1, PYC-1, PKG-1, SIG-1, SHP-1, UC-1: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
