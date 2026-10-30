#!/usr/bin/env python3
"""WP-23 (conan_environment_plan.md §6) -- the one shared
copy of "which CONAN_HOME does this build use" for everything that runs in
the SUPERPROJECT's own Python: root scripts/build.py and scripts/setup.py.
Both used to carry an independent copy of this logic (found duplicated,
correctly, by a real review -- the previous round's own justification
"they run in different Python environments" was true of adas_build_tools
(a separately pip-installed package, still its own copy in
adas_build_tools.conan_ops) but never true of build.py/setup.py, which
already share one interpreter and one sys.path -- sibling-import, same
pattern setup.py already uses for check_conan_resolution/conan_server_guard).

Reduces the count from three independent implementations to two: this
module (superproject-local) and adas_build_tools.conan_ops's own copy
(pip-installed, genuinely a different environment, genuinely cannot import
this file). scripts/tests/test_conan_home_resolution_matrix.py is the CPY-1-
style guard that keeps the two agreeing on every input combination -- this
module existing is what makes that test possible to write at all.
"""
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# WP-1/NS-01 (cache_first_no_server_plan.md, D1): moved here from scripts/
# setup.py, verbatim, so remotes_enabled() below and setup.py's own callers
# share the ONE placeholder-detection implementation instead of a second
# one growing next to it. setup.py imports both names from here now.
TEAM_SERVER_FILE = Path(__file__).resolve().parent / "team_conan_server.txt"
# WP-1/NS-01: the test-only override, beats both the CLI flag and the file.
# Not meant for a developer's normal environment - a real machine's answer
# comes from scripts/team_conan_server.txt (D1); this exists so a test can
# force a state without touching that file or argv.
REMOTES_ENV_VAR = "ADAS_REMOTES_ENABLED"


_LOCKFILES = []


def load_lockfiles():
    """WP-13 (cache_first_no_server_plan.md §5): the toolchain checkout's
    `adas_build_tools/lockfiles.py`, loaded BY PATH so the root dispatcher and
    the component builder share one implementation of what a lock is. The file
    is standard-library only for exactly this reason; loading by path (not
    `import adas_build_tools`) means a different version installed in this
    interpreter can never shadow the checkout's. None when modules/toolchain is
    not checked out - callers then build unlocked and say so."""
    if not _LOCKFILES:
        path = ROOT / "modules" / "toolchain" / "adas_build_tools" / "lockfiles.py"
        module = None
        if path.is_file():
            spec = importlib.util.spec_from_file_location("adas_lockfiles_root", path)
            module = importlib.util.module_from_spec(spec)
            sys.modules["adas_lockfiles_root"] = module  # dataclasses look the module up here
            spec.loader.exec_module(module)
        _LOCKFILES.append(module)
    return _LOCKFILES[0]


def active_conan_home():
    """The Conan home this process's `conan` uses: CONAN_HOME when set, else
    what `conan config home` says. None when neither can be read."""
    if os.environ.get("CONAN_HOME"):
        return os.environ["CONAN_HOME"]
    try:
        proc = subprocess.run(["conan", "config", "home"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
    except OSError:
        return None
    return proc.stdout.strip() or None if proc.returncode == 0 else None


def project_profile_path(platform):
    """Superproject-local copy of adas_build_tools.conan_ops.project_profile_path()
    (prompt 35 item 1) -- same two-copy split as resolve_conan_home_and_mode()
    above, forced by the same R-BUILD-1/6 reason: the pip-installed copy lives
    in adas_build_tools, which the aggregator (running in the superproject's
    own Python, never a component .venv) does not install. This copy resolves
    the identical checked-in file by direct path instead of
    importlib.resources, since modules/toolchain is a submodule of THIS repo,
    not a separately-versioned pip package here. Returns None if no profile is
    shipped for `platform` yet, same contract as the pip-installed copy.
    scripts/tests/test_profile_path_agreement.py is the CPY-1-style guard that
    keeps the two agreeing."""
    candidate = ROOT / "modules" / "toolchain" / "adas_build_tools" / "conan_profiles" / f"{platform}.profile"
    return str(candidate) if candidate.is_file() else None


def profile_args(platform):
    """--profile:host/--profile:build flags for `platform`'s pinned Conan
    profile, or [] if none is shipped yet -- Conan then falls back to its own
    default-profile resolution. Mirrors adas_build_tools.builder._profile_args()
    (prompt 35 item 1); native (non-cross) builds only, host and build profile
    always the same file."""
    profile = project_profile_path(platform)
    if profile is None:
        return []
    return ["--profile:host", profile, "--profile:build", profile]


_LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1", "[::1]")


def _is_loopback_url(url):
    """NS-24/D1a (cache_first_no_server_plan.md) -- a URL whose host is
    this machine (127.0.0.1, localhost, ::1) is not a team server: the
    2026-09-09 per-machine-server model put a loopback address in the
    committed scripts/team_conan_server.txt on purpose, which made
    remotes_enabled() read ON on every machine and defeated this plan's
    cache-first default (found running WP-1's own real proof). Matches on
    the URL's host only, via urllib so a port number or path never
    confuses a substring check."""
    from urllib.parse import urlsplit
    host = urlsplit(url).hostname
    return host is not None and host.lower() in (
        "127.0.0.1", "localhost", "::1")


def read_team_server_url():
    """WP-1/NS-01: moved from scripts/setup.py, verbatim (D1's "reuse the
    existing placeholder detection, don't write a second notion of
    placeholder"). A line must start with http:// or https:// to count as
    a configured URL - anything else (a comment, blank lines, the shipped
    placeholder text, or a missing file entirely) means "not configured",
    the same "malformed/empty file is OFF, never a URL" contract WP-1's
    own test criteria pins down."""
    if not TEAM_SERVER_FILE.exists():
        return None
    for line in TEAM_SERVER_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("http://") or line.startswith("https://"):
            return line
    return None


def remotes_enabled(cli_override=None, env=None):
    """WP-1/NS-01 (cache_first_no_server_plan.md D1) - the ONE switch every
    entry point (setup.py, build.py, check_conan_resolution.py) asks
    instead of each re-deriving its own answer. Returns (bool enabled, str
    reason) - the reason is what each caller prints, once, so "why" never
    has to be re-explained by hand at each call site.

    Precedence, highest first:
      1. `REMOTES_ENV_VAR` in `env` ("on"/"off", case-insensitive) - a
         test-only override (see its own docstring above); beats the CLI
         flag and the file so a test never has to touch either. A value
         that isn't a recognized on/off spelling is treated as unset (this
         var is opt-in and narrowly named, so a garbage value is far more
         likely a typo in a deliberate override than something to crash
         on) and precedence falls through to the next level.
      2. `cli_override` (True/False/None) - the caller's own `--remotes
         on|off`, already parsed by ITS OWN argparse. This function never
         reads sys.argv itself - each entry point has different other
         flags, and re-parsing raw argv here would fight them.
      3. `scripts/team_conan_server.txt` via `read_team_server_url()`: a
         placeholder (or a missing/empty/malformed file) means no remotes;
         a real URL means remotes on and every existing download/publish
         path behaves as it does today.
    """
    env = os.environ if env is None else env
    raw = env.get(REMOTES_ENV_VAR)
    if raw is not None:
        value = raw.strip().lower()
        if value in ("on", "1", "true", "yes"):
            return True, f"{REMOTES_ENV_VAR}={raw!r} (env override)"
        if value in ("off", "0", "false", "no"):
            return False, f"{REMOTES_ENV_VAR}={raw!r} (env override)"
        # Not a recognized spelling - fall through to the next precedence
        # level rather than raising or silently treating it as "on".

    if cli_override is not None:
        return cli_override, f"--remotes {'on' if cli_override else 'off'} (CLI override)"

    url = read_team_server_url()
    if url:
        if _is_loopback_url(url):
            return False, (f"{url} is a loopback address, not a team "
                            f"server (NS-24/D1a) - use --remotes on if "
                            f"this machine really runs one")
        return True, f"team server configured: {url}"
    try:
        file_label = TEAM_SERVER_FILE.relative_to(ROOT)
    except ValueError:
        file_label = TEAM_SERVER_FILE  # e.g. a test's patched-in path
    return False, f"{file_label} is a placeholder - no team Conan server configured"


def resolve_conan_home_and_mode(explicit_mode, invocation):
    """Decides, ONCE, which CONAN_HOME a build uses and why - shared by
    every superproject-local caller (root scripts/build.py's delegate,
    aggregate and fan-out paths; scripts/setup.py's configure_conan_
    dependencies()). adas_build_tools.conan_ops.resolve_conan_home_and_mode()
    is the one remaining independent copy, pip-installed into each
    component's own .venv and therefore unable to import this file - the
    two are held to agreement by scripts/tests/
    test_conan_home_resolution_matrix.py, not by a shared import (which
    cannot cross that boundary), the same shape R-BUILD-1/6 already forces
    on the stub/conan_ops.py split.

    RD-03 (remove_develop_mode_plan.md): "package" is the only mode - the
    develop CONAN_HOME and its `default_dev_conan_home()` resolution are
    removed. An explicit CONAN_HOME always wins (a developer who set it
    did so deliberately); `explicit_mode` is accepted only as `None` or
    `"package"` (a caller passing `"develop"` is a bug upstream of this
    function - refusing `--mode develop` is scripts/build.py's and
    scripts/setup.py's own job, at the CLI, with a message pointing at
    the plan - this function never sees that value in real use).

    Returns `(conan_home_or_None, mode, reason)` - `conan_home_or_None` is
    what the caller should set os.environ["CONAN_HOME"] to (`None` means
    "leave CONAN_HOME alone, Conan's own default resolution is already
    correct"). `mode` is always "package", worth forwarding verbatim
    (e.g. `--mode <mode>`) to a subprocess so it never has to re-derive
    anything."""
    if explicit_mode not in (None, "package"):
        raise ValueError(
            f"unsupported mode {explicit_mode!r} - develop mode was removed "
            "(remove_develop_mode_plan.md); only 'package' is valid.")

    if "CONAN_HOME" in os.environ:
        return os.environ["CONAN_HOME"], "package", \
            "explicit CONAN_HOME already set - respected verbatim, never overridden"

    reason = ("--mode package (explicit override)" if explicit_mode == "package"
              else f"invocation={invocation} (default, package is the only mode)")
    return None, "package", reason


# What Conan prints when a remote login has expired. "interactive mode
# disabled" is the real text observed 2026-09-21 with core:non_interactive=True
# (setup.py, CE-28) - `ERROR: ... Conan interactive mode disabled. [Remote:
# adas-local]`; "EOF when reading a line" is what the same failure printed
# before that setting existed (Conan asked for a password on a closed stdin).
_AUTH_FAILURE_MARKERS = ("interactive mode disabled", "EOF when reading a line")


def auth_failure_message(conan_output, conan_home):
    """CE-28 / CE-29: conan's output (a failed `conan install`, or the "error"
    field of a `conan list --format=json` remote entry) -> the one-line "login
    expired" message naming the remote and the CONAN_HOME it applies to, or
    None when the failure is not an auth failure. Moved here from build.py so
    scripts/build.py and scripts/check_conan_resolution.py share ONE matcher."""
    lowered = conan_output.lower()
    if not any(marker.lower() in lowered for marker in _AUTH_FAILURE_MARKERS):
        return None
    match = re.search(r"\[Remote: ([^\]]+)\]", conan_output)
    remote = match.group(1) if match else "adas-local"
    login = ("conan remote login adas-local demo -p demo" if remote == "adas-local"
             else f"conan remote login {remote} <user>")
    return (f"{remote} login expired - run: {login} "
            f"(CONAN_HOME={conan_home or 'Conan default'})")


# ---------------------------------------------------------------------------
# NS-05a (cache_first_no_server_plan.md D4a, STEP 3): the stale-cache
# fingerprint setup.py records when it exports/creates a first-party module
# into the cache, and build.py recomputes and compares before taking that
# same module FROM the cache. Shared here for the same reason as everything
# else in this file: build.py and setup.py are the only two writers/readers,
# share one interpreter and one sys.path, and a second copy would be free to
# drift (R-BUILD-1/6's own reasoning, one level up from Conan machinery).
# ---------------------------------------------------------------------------

PREPARED_MODULES_FILE_NAME = "prepared_modules.json"


def prepared_modules_path(root):
    """Where setup.py records, and build.py reads, per-module fingerprints -
    conan_workarea/ (not modules/<name>/, which a --clean could wipe, and
    not CONAN_HOME, which is a cache, not a workspace record)."""
    return Path(root) / "conan_workarea" / PREPARED_MODULES_FILE_NAME


FINGERPRINT_VERSION = 3
"""NS-52: what `dirty` means. 1 (no field, pre-2026-09-26) hashed only the
`git status --porcelain` summary - names and status letters - so a second
edit to an already-modified file was invisible (RV-2). 2 hashes content
(NS-51). A record carrying anything else was written under a different
meaning of `dirty` and can be compared against nothing, so it is reported
as an outdated format, never as "your source changed". 3 (2026-10-05): the
non-git fallback no longer hashes build output (_FP_SKIP_DIRS), so a record
written under 2 - whose fallback `dirty` included it - cannot be compared."""

# Same set as _PYF1_SKIP_DIRS / _PYF1_SKIP_PREFIXES in scripts/check_invariants.py,
# copied rather than imported: that file is a standalone check script and this
# one is imported at startup by setup.py and build.py.
_FP_SKIP_DIRS = frozenset({
    ".git", "build", "third_party", ".venv", "venv", "__pycache__",
    ".pytest_cache", "generated_py", "node_modules", "conan_workarea",
})
_FP_SKIP_PREFIXES = ("build-", ".venv-")


def _git_out(module_dir, *args):
    """stdout bytes of `git -C module_dir <args>`, or None on any failure."""
    try:
        result = subprocess.run(["git", "-C", str(module_dir), *args],
                                capture_output=True, check=False)
    except OSError:
        return None
    return result.stdout if result.returncode == 0 else None


def setup_command():
    """The command that runs setup on this platform, for messages (P4.3,
    build_simply.html: nothing printed on Linux names setup.bat). Same idiom
    as make_offline_bundle.py's setup_cmd."""
    return "setup.bat" if sys.platform == "win32" else "python3 scripts/setup.py"


def setup_py_command():
    """`python scripts/setup.py` on Windows, `python3 scripts/setup.py` elsewhere
    (P4.3) - for messages that name setup.py itself rather than the launcher."""
    return "python scripts/setup.py" if sys.platform == "win32" else "python3 scripts/setup.py"


def compute_module_fingerprint(module_dir):
    """NS-05a: the two cheap, local, no-network values that answer "has this
    module's checked-out source moved on since its cached binary was built" -
    a git HEAD sha, plus a hash of the working tree's uncommitted state (so
    an uncommitted edit counts as a change too, not only a new commit -
    D4a's own "the checked-out source has moved on" is about the working
    tree, not just HEAD). `module_dir` is the path to modules/<name>.

    NS-51 (RV-2, fingerprint format 2): `dirty` hashes CONTENT, not the
    porcelain summary. Format 1 hashed `git status --porcelain` alone, which
    names a modified file but not what is in it - so editing the same file
    twice produced the same fingerprint, and the calibration edit-and-re-run
    loop (R-SIM-3a) silently shipped the previous YAML on the second edit.
    Three inputs, in this fixed order: `git status --porcelain`, `git diff
    HEAD` (tracked content, staged and unstaged), and the bytes of every
    untracked, non-ignored path (`git ls-files --others --exclude-standard`),
    sorted. A clean tree hashes to the same value it always did.

    Falls back to a sha256 over every regular file's bytes when
    `module_dir` is not a git checkout at all - shouldn't happen in this
    repo (every modules/<name> is a submodule, R-GIT-1), but a fallback
    beats a crash; `git` is `None` in that case, so a comparison against a
    real git-backed fingerprint always reads as "changed" rather than a
    false match. Returns {"git": <sha or None>, "dirty": <sha256 hex>}.

    A `module_dir` that does not exist raises FileNotFoundError (D1,
    partial_clone_correctness_plan.md): an absent module has no source to
    fingerprint, and the sha256 of nothing would read as "changed". Callers
    filter absent modules first (build.stale_cache_refs())."""
    if not os.path.isdir(str(module_dir)):
        raise FileNotFoundError(f"no module directory to fingerprint: {module_dir}")
    head = _git_out(module_dir, "rev-parse", "HEAD")
    status = _git_out(module_dir, "status", "--porcelain")
    diff = _git_out(module_dir, "diff", "HEAD", "--no-ext-diff", "--binary")
    untracked = _git_out(module_dir, "ls-files", "-z", "--others", "--exclude-standard")
    if None not in (head, status, diff, untracked):
        hasher = hashlib.sha256(status)
        if status:
            hasher.update(diff)
            for rel in sorted(p for p in untracked.decode("utf-8").split("\0") if p):
                hasher.update(rel.encode("utf-8") + b"\0")
                try:
                    with open(os.path.join(str(module_dir), rel), "rb") as f:
                        hasher.update(f.read())
                except OSError:
                    continue
        return {"git": head.decode("utf-8").strip(), "dirty": hasher.hexdigest()}
    hasher = hashlib.sha256()
    for walk_root, dirs, files in os.walk(module_dir):
        dirs[:] = sorted(d for d in dirs if d not in _FP_SKIP_DIRS
                         and not d.startswith(_FP_SKIP_PREFIXES))
        for name in sorted(files):
            try:
                with open(os.path.join(walk_root, name), "rb") as f:
                    hasher.update(f.read())
            except OSError:
                continue
    return {"git": None, "dirty": hasher.hexdigest()}


def read_prepared_modules(root):
    """NS-05a: the recorded fingerprints, or None iff the file is missing/
    unreadable entirely - the caller's own "warn, never refuse" escape
    hatch for a machine prepared before this mechanism existed (a refusal
    there would break every existing machine on upgrade)."""
    path = prepared_modules_path(root)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def record_is_outdated_format(entry):
    """NS-52: True when a prepared_modules.json entry was written under a
    different fingerprint format than compute_module_fingerprint() produces
    now - its `dirty` cannot be compared, so the honest answer is "the
    format changed, re-prepare once", never "your source changed"."""
    return entry.get("fp_version") != FINGERPRINT_VERSION


def record_prepared_module(root, module, ref, module_dir, target=None, platform=None, project=None):
    """NS-05a: called by setup.py exactly when it has just exported/created
    `module`'s own ref into the cache FOR REAL (never on an "already
    cached" skip - the binary there was NOT just built from the current
    checkout state, so recording "matches current HEAD" would be false).
    Merges into the existing file rather than overwriting it, so preparing
    one module never erases another's record."""
    path = prepared_modules_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
    fp = compute_module_fingerprint(module_dir)
    data[module] = {"ref": ref, "git": fp["git"], "dirty": fp["dirty"],
                     "fp_version": FINGERPRINT_VERSION,
                     "target": target, "platform": platform, "project": project}
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def create_and_record_module(module, module_dir, ref, project, build_type,
                              profile_flags, root, target, platform,
                              verify_cached=None, runner=None, log=print,
                              recorder=None):
    """`conan create` one module from the checkout, then record the freshness
    fingerprint of what was JUST built.

    THE single implementation, called by both:
      * setup.py --prepare      - for a whole first-party dependency closure
      * build.py (aggregate)    - for a pure-data module the user explicitly
                                  named with --with/--with-all (D4: "build.py
                                  compiles only the primary and whatever
                                  --with names")

    It lives here, in the module that already owns prepared_modules.json,
    because a second copy of "create it, then record it" is exactly how the
    two halves drift: a creator that forgets the record leaves a binary that
    build.py's NS-37 guard then refuses as unverifiable, and the refusal's
    own advice would be a dead end (the NS-28 shape, again).

    `-nr`/`--no-remote` is unconditional: this is cache-fill from the
    checkout, never a remote, whether remotes are on or off.

    `runner` and `recorder` let a caller pass its own subprocess wrapper and
    its own record function, so a caller's existing test doubles keep working
    across this extraction - the alternative was editing three NS-05a/NS-28
    guard tests to patch a different seam, and this repo stops a refactor that
    cannot leave its tests unchanged (NS-14's own rule) rather than quietly
    rewriting them. `runner` must accept an argv list and return an object
    with .returncode and .stdout. `verify_cached`, when given, is called after
    a successful create and must confirm the binary actually landed -
    `conan create` returning 0 is not by itself proof.

    Returns True when the module is in the cache AND recorded.
    """
    cmd = ["conan", "create", str(module_dir), "--build=missing",
           "-o", f"project={project}", "-s", f"build_type={build_type}",
           *profile_flags, "-nr"]
    if runner is None:
        result = subprocess.run(cmd, capture_output=True, text=True)
    else:
        result = runner(cmd)

    ok = result.returncode == 0
    if ok and verify_cached is not None:
        ok = bool(verify_cached())
    if not ok:
        # RQ-9: the failure must say WHY. The default subprocess path captures
        # stdout and stderr separately and conan writes its real error to
        # stderr, so logging stdout alone printed "conan create failed:" and
        # then nothing at all - seen for real on the first end-to-end run of
        # this function, 2026-09-25. A caller-supplied `runner` may merge the
        # two (setup.py's run(capture=True) does), hence getattr, not .stderr.
        # isinstance, not truthiness: a caller's test double may auto-create
        # a non-string .stderr attribute, and joining that raises instead of
        # reporting the failure it was called to report.
        detail = "\n".join(part for part in (getattr(result, "stdout", None),
                                             getattr(result, "stderr", None))
                           if isinstance(part, str) and part) \
            or "(no output captured from conan)"
        log(f"{module} ({ref}): conan create failed (exit {result.returncode}):\n"
            f"{detail}")
        return False

    record = record_prepared_module if recorder is None else recorder
    record(root, module, ref, str(module_dir),
           target=target, platform=platform, project=project)
    return True
