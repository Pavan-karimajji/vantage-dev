#!/usr/bin/env python3
"""ADAS 1V Superproject  -  developer machine setup (setup.md).

Bootstraps a fresh machine to the point where `python scripts/build.py df -t
gtest -p vs2026` works: toolchain checks, git submodules, Conan, and the
adas-interfaces/adas-mathlib/adas-shared-config dependency problem (there is
no Artifactory and no Jenkins yet, so those three either come from a shared
Conan server or get built locally, from this checkout, package mode).

Usage:
    setup.bat                    # full setup (Windows launcher, forwards here)
    python scripts/setup.py      # same, any OS
    python scripts/setup.py --dry-run       # print what would happen, change nothing
    python scripts/setup.py --yes           # don't prompt before installing pip packages
    python scripts/setup.py --no-submodules # skip `git submodule update --init`
    python scripts/setup.py --full-verify   # also pre-build perception-core/df's Conan deps
    python scripts/setup.py --role server   # bootstrap a *team* Conan server on this machine

Every step is idempotent  -  safe to re-run after fixing whatever it reported.
Full explanation of every step: setup.md at the repo root.
"""
import argparse
import importlib
import importlib.util
import json
import os
import re
import shutil
import signal
import socket
import site
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

try:
    import check_conan_resolution
    # STEP 1 (cache_first_no_server_plan.md, NS-11 remainder): `--prepare`
    # reuses build.py's own forward_closure()/topo_sort()/first_party_requires()
    # (imported, never a second graph walk - see prepare_first_party_deps()'s
    # own docstring). build.py needs PyYAML too (load_module_conf()), so it
    # shares this same ImportError guard rather than a second one.
    import build as adas_build
except ImportError:
    # PyYAML (imported by check_conan_resolution/build) is not installed yet.
    # Only `--offline` can proceed: its wheels step installs it and
    # re-imports (OF-04).
    if "--offline" not in sys.argv:
        raise
    check_conan_resolution = None
    adas_build = None
import conan_server_guard
# WP-1/NS-01 (cache_first_no_server_plan.md): TEAM_SERVER_FILE and
# read_team_server_url() moved to conan_home_resolution.py so setup.py,
# build.py and check_conan_resolution.py share the one placeholder
# detection; imported here rather than redefined (`setup.TEAM_SERVER_FILE`/
# `setup.read_team_server_url` still resolve for existing test mocks - an
# import binds the name in this module's own namespace same as a def would).
from submodule_init import (SubmoduleInitError, init_submodules_for, possibly_uninitialised,
                            uninitialised_submodules)
from conan_home_resolution import (TEAM_SERVER_FILE, active_conan_home, compute_module_fingerprint, setup_command,
                                    create_and_record_module, load_lockfiles, profile_args,
                                    read_prepared_modules, read_team_server_url,
                                    record_is_outdated_format, record_prepared_module,
                                    remotes_enabled)

ROOT = Path(__file__).resolve().parent.parent
# RD-13 (remove_develop_mode_plan.md): where `--offline` with no BUNDLE_DIR
# looks - matches scripts/make_offline_bundle.py's own default --out
# (DEFAULT_OUT there), so the two tools agree with no flag needed on either
# side. Gitignored (.gitignore); never committed (D3).
DEFAULT_OFFLINE_BUNDLE_DIR = ROOT / "misc" / "offline_bundle"
MIN_CMAKE = (3, 22)
REMOTE_LOGIN_TIMEOUT_S = 20
SERVER_CONNECT_TIMEOUT_S = 2


class StepFailed(Exception):
    def __init__(self, reason, fix, run=None):
        super().__init__(reason)
        self.reason = reason
        self.fix = fix
        self.run = run  # the one runnable command, when there is one (D11)


def banner(text):
    print()
    print("=" * 70)
    print(text)
    print("=" * 70)


def run(cmd, cwd=None, check=True, capture=False, timeout=None, merge_stderr=True):
    kwargs = {"cwd": cwd, "shell": False}
    if capture:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.STDOUT if merge_stderr else subprocess.DEVNULL
        kwargs["text"] = True
    if timeout is not None:
        kwargs["timeout"] = timeout
    result = subprocess.run(cmd, **kwargs)
    if check and result.returncode != 0:
        out = result.stdout if capture else ""
        raise subprocess.CalledProcessError(result.returncode, cmd, output=out)
    return result


def on_path(exe):
    return shutil.which(exe) is not None


def step(ctx, name, fn):
    print(f"\n--- {name} ---")
    try:
        outcome = fn(ctx)
    except StepFailed as e:
        banner(f"[FAILED] {name}")
        print(f"Reason: {e.reason}")
        print(f"Fix:    {e.fix}")
        if getattr(e, "run", None):
            print(f"Run:    {e.run}")
        # D14/PT-21: nothing printed on Linux names setup.bat.
        print("Then re-run:  " + ("setup.bat        (or: python scripts/setup.py)"
                                  if os.name == "nt" else "python3 scripts/setup.py"))
        print("=" * 70)
        sys.exit(1)
    if outcome == "skip":
        print(f"[SKIP] {name}  -  already satisfied")
    else:
        print(f"[OK]   {name}")


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

CONAN_TLS_CHECK_HOST = "center2.conan.io"
CONAN_TLS_CHECK_PORT = 443
CONAN_TLS_CHECK_TIMEOUT_S = 10
# Signatures of "the network itself can't get past TLS interception" -
# distinct from every other reason a pip install can fail (network down
# entirely, PyPI itself down, a typo'd package name, ...).
_PIP_CERT_ERROR_MARKERS = (
    "CERTIFICATE_VERIFY_FAILED",
    "SSLCertVerificationError",
    "self-signed certificate",
    "SSLError",
    "certificate verify failed",
)


def _tls_handshake_ok(host, port, timeout=CONAN_TLS_CHECK_TIMEOUT_S):
    """A real TLS handshake, not just a TCP connect - proves Python's
    trust store (post-pip-system-certs, the OS store) actually accepts
    this host's certificate, which a bare socket connect can't tell you.
    """
    import ssl
    context = ssl.create_default_context()
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=host):
                return True
    except (OSError, ssl.SSLError):
        return False


def ensure_https_trust(ctx):
    """WP-04 (conan_environment_plan.md section 2.5): on a corporate-
    managed machine behind TLS-inspecting network security software
    (Netskope, or any other proxy that re-signs HTTPS with its own
    injected root CA), Python's bundled certifi list doesn't trust that
    CA even though the OS already does (IT pushes it to the system
    store) - conancenter becomes unreachable outright
    (SSLCertVerificationError: self-signed certificate in certificate
    chain). pip-system-certs makes Python defer to the OS certificate
    store instead, which is harmless everywhere it's already fine -
    installed unconditionally, both roles, every developer, the same
    "just part of setup" treatment Conan/PyYAML already get, not a
    conditional branch someone has to know to ask for.

    Runs for BOTH --role dev and --role server, early  -  before any step
    that needs conancenter.

    NS-45 (cache_first_no_server_plan.md, RQ-1): with remotes OFF this step
    is BEST-EFFORT, never fatal. Its whole purpose is making PyPI and
    conancenter reachable through TLS interception; a remotes-off run is not
    supposed to reach either, and on a genuinely disconnected machine the
    pip install below fails for the most ordinary reason there is (no
    network). Failing the whole run there would make `setup.bat` impossible
    to complete offline - the exact thing RQ-1 requires. If a later step
    really does need pip, that step fails and names what it needs (RQ-9).
    `getattr` default True: any caller that predates ctx.remotes_enabled
    keeps today's fatal behaviour.
    """
    remotes_on = getattr(ctx, "remotes_enabled", True)
    if ctx.dry_run:
        print("[dry-run] would run: pip install --user pip-system-certs")
        if remotes_on:
            print(f"[dry-run] would verify: TLS handshake to "
                  f"{CONAN_TLS_CHECK_HOST}:{CONAN_TLS_CHECK_PORT}")
        else:
            print("[dry-run] would SKIP the TLS handshake check (remotes off, "
                  "NS-45)")
        return "skip"

    result = run([sys.executable, "-m", "pip", "install", "--user", "pip-system-certs"],
                 capture=True, check=False)
    if result.returncode != 0:
        output = result.stdout or ""
        if not remotes_on:
            # NS-45: best-effort with remotes off (see docstring).
            print("WARNING: pip install of pip-system-certs failed, and remotes "
                  "are off  -  NOT fatal (NS-45): nothing in a remotes-off run "
                  "is meant to reach PyPI or conancenter. If a later step does "
                  "need pip, it will fail naming exactly what it needs. "
                  "Output:\n" + output)
            return
        if any(marker.lower() in output.lower() for marker in _PIP_CERT_ERROR_MARKERS):
            # CE-08: the specific, distinct case - pip itself can't reach
            # PyPI, almost certainly the same TLS interception one level
            # up. No TLS-handshake verification below: nothing installed
            # to verify.
            raise StepFailed(
                "pip itself cannot reach PyPI, likely the same certificate "
                "issue one level up  -  pip-system-certs can't install "
                "itself to fix Conan's trust store if pip can't even "
                "download it.",
                "This needs your IT team's help (this machine's network "
                "security software appears to be intercepting HTTPS before "
                "pip can verify PyPI's certificate) - not something this "
                "script can fix unattended.",
            )
        raise StepFailed(
            "pip install of pip-system-certs failed.",
            "Check your pip/network configuration and re-run. Output:\n"
            + output,
        )

    if not remotes_on:
        # NS-45: no remote will be contacted this run, so a 10s handshake
        # timeout to center2.conan.io buys nothing but a delay.
        print("Remotes are off  -  skipping the conancenter TLS handshake check "
              "(nothing this run contacts it, NS-45).")
        return

    if _tls_handshake_ok(CONAN_TLS_CHECK_HOST, CONAN_TLS_CHECK_PORT):
        print(f"TLS handshake to {CONAN_TLS_CHECK_HOST}:{CONAN_TLS_CHECK_PORT} "
              "succeeded.")
    else:
        print(f"WARNING: TLS handshake to {CONAN_TLS_CHECK_HOST}:"
              f"{CONAN_TLS_CHECK_PORT} still failed after installing "
              "pip-system-certs  -  conancenter may still be unreachable "
              "from this machine for a different reason (network/firewall, "
              "not certificate trust).")


def _shebang_from_posix_script(data):
    """Pure parse, no I/O, no os.name check (CE-30, conan_environment_
    plan.md - kept separate from _resolve_console_script_interpreter()
    below so its logic is directly unit-testable without touching the
    real OS or the real filesystem, and without the trap that function's
    own docstring warns about: `os` is a process-wide singleton module,
    so patching `os.name` in a test to exercise "the other platform's"
    branch also changes what `pathlib.Path` itself thinks the platform
    is, and breaks on the "wrong" one - `NotImplementedError: cannot
    instantiate 'PosixPath' on your system`, hit live writing this).

    A POSIX console script is a plain text file whose first line is a
    shebang (`#!/path/to/python[3]` or `#!/usr/bin/env python3`) - read
    directly, last whitespace-separated token (tolerates the `env` form
    defensively, even though a venv/pip console-script shebang is
    normally a direct interpreter path, never `env`). Returns None if
    the first line isn't a shebang at all."""
    first_line = data.split(b"\n", 1)[0]
    if not first_line.startswith(b"#!"):
        return None
    text = first_line[2:].strip().decode("utf-8", errors="replace")
    parts = text.split()
    return parts[-1] if parts else None


def _shebang_from_windows_launcher(data):
    """Pure parse, no I/O (CE-30) - see _shebang_from_posix_script()'s
    own docstring for why this is a separate, directly-testable
    function.

    pip/distlib's console-script `.exe` launcher on Windows embeds the
    build-time interpreter path as a plain "#!<path>\\r\\n" text line
    immediately before the appended zip archive holding `__main__.py` -
    confirmed live against a real pip-installed `conan.exe`
    (2026-09-23). Read as latin-1 (never raises on arbitrary binary
    bytes, and keeps a 1:1 mapping to file offsets) and take the LAST
    "#!" occurrence in the file: the genuine shebang sits right before
    the zip's `PK` signature near the end of the file - an unrelated
    "#!" byte sequence can occur earlier, inside the compiled launcher
    stub's own padded/interleaved resource strings (confirmed live: a
    false match inside wide-char "PATHEXT" text at a much earlier
    offset than the real one). Returns None if no "#!" occurs at all."""
    text = data.decode("latin-1")
    idx = text.rfind("#!")
    if idx == -1:
        return None
    end = text.find("\r\n", idx)
    if end == -1:
        end = text.find("\n", idx)
    if end == -1:
        return None
    return text[idx + 2:end].strip()


def _resolve_console_script_interpreter(script_path):
    """CE-30 (conan_environment_plan.md): best-effort - the Python
    interpreter a pip-installed console script (here, always `conan`)
    actually runs under. `ensure_https_trust()` above only ever proved
    `sys.executable`'s OWN interpreter trusts conancenter's certificate -
    on a machine where `conan` already existed on PATH before this run
    (a pre-existing, e.g. corporate-imaged, Python install - the real
    second-corporate-PC failure this fixes: "TLS handshake ... succeeded"
    / "[OK] HTTPS trust" printed, then every `conan create` failed with
    SSLCertVerificationError), that other interpreter was never touched
    and the "succeeded" line proved nothing about it.

    Dispatches on the real, live `os.name` to one of the two pure
    parsers above (see their own docstrings for the POSIX-shebang vs.
    Windows-embedded-shebang shapes).

    Returns None (never raises) if the script can't be found/read,
    carries no recognizable shebang, or the recovered path doesn't
    actually exist on disk - "fall back to reporting it" (CE-30's own
    words for this exact case), never a guess."""
    if script_path is None:
        return None
    try:
        data = Path(script_path).read_bytes()
    except OSError:
        return None

    candidate = (_shebang_from_windows_launcher(data) if os.name == "nt"
                 else _shebang_from_posix_script(data))

    if not candidate:
        return None
    try:
        if not Path(candidate).exists():
            return None
    except OSError:
        return None
    return candidate


def _same_interpreter(a, b):
    """Best-effort 'is this the same Python installation' comparison for
    CE-30 - resolved to an absolute real path first (so a symlink or a
    relative launch never reads as a false difference), case-insensitive
    on Windows (its filesystem paths are). Falls back to a plain
    case-normalized string compare if either path can't be resolved
    (e.g. a mocked/nonexistent path in a test) rather than raising."""
    try:
        ra, rb = Path(a).resolve(), Path(b).resolve()
    except OSError:
        ra, rb = Path(a), Path(b)
    if os.name == "nt":
        return str(ra).lower() == str(rb).lower()
    return ra == rb


CONAN_TLS_VERIFY_REF = "zlib"


def ensure_conan_interpreter_trusts_https(ctx):
    """CE-30 (conan_environment_plan.md): closes the gap `ensure_https_
    trust()` left open - real evidence from a second corporate PC,
    2026-09-23: setup printed "TLS handshake to center2.conan.io:443
    succeeded" and "[OK] HTTPS trust", then every `conan create` failed
    with SSLCertVerificationError against center2.conan.io. Root cause:
    `ensure_https_trust()` installs `pip-system-certs` into `sys.
    executable` and verifies with a raw `sys.executable` TLS handshake -
    on a machine where `conan` already existed on PATH belonging to a
    DIFFERENT interpreter (this machine's pre-existing, corporate-imaged
    Python), that install and that verification prove nothing about the
    interpreter `conan` itself actually runs under.

    Runs STRICTLY AFTER `check_or_install_conan` in `main()`'s own step
    order (WP-04's sequence, unlike `ensure_https_trust()` above, which
    stays early since it also protects earlier steps' own pip installs
    on Linux, e.g. `_check_cmake_linux()`) - `conan` is guaranteed to be
    on PATH by the time this runs, or `check_or_install_conan` already
    raised `StepFailed` and aborted the whole run before reaching here.

    Resolves conan's own interpreter (`shutil.which("conan")` +
    `_resolve_console_script_interpreter()`); if it differs from `sys.
    executable`, installs `pip-system-certs` into THAT interpreter too.
    Verifies through Conan itself (`conan search <ref> -r conancenter`),
    never a raw Python TLS handshake - the raw handshake is exactly what
    "proved nothing" on the real corporate PC. Reports both interpreters
    in the step output unconditionally, pass or fail.

    NS-45 (cache_first_no_server_plan.md, RQ-1/RQ-5): skipped outright when
    remotes are off. This step's only job is proving conan's interpreter can
    verify `conancenter`'s certificate - and with remotes off, conancenter is
    disabled (sync_remote_enablement()) and never contacted, so the
    `conan search zlib -r conancenter` below would fail on a disconnected
    machine and abort a run that has no business touching the internet. That
    failure is precisely why a plain `setup.bat` could not complete with the
    network down."""
    if not getattr(ctx, "remotes_enabled", True):
        print("Remotes are off  -  conancenter is disabled and never contacted, "
              "so there is no remote certificate to verify (NS-45).")
        return "skip"

    conan_path = shutil.which("conan")
    if conan_path is None:
        # check_or_install_conan() already ran, immediately before this
        # step (main()'s own order) - it would have raised StepFailed and
        # aborted the whole run if conan genuinely couldn't be made
        # available. Reaching here with no conan on PATH is not a real
        # machine state, only a test double exercising this function in
        # isolation.
        return "skip"

    conan_interp = _resolve_console_script_interpreter(conan_path)
    report_lines = [
        f"conan:                                  {conan_path}",
        f"conan's own interpreter:                {conan_interp or '(could not be determined)'}",
        f"setup.py's interpreter (sys.executable): {sys.executable}",
    ]

    needs_second_install = conan_interp is not None and not _same_interpreter(
        conan_interp, sys.executable)

    if ctx.dry_run:
        print("\n".join(report_lines))
        if needs_second_install:
            print(f"[dry-run] would run: {conan_interp} -m pip install "
                  "--user pip-system-certs")
        print(f"[dry-run] would verify: conan search {CONAN_TLS_VERIFY_REF} "
              "-r conancenter")
        return "skip"

    if needs_second_install:
        result = run([conan_interp, "-m", "pip", "install", "--user",
                       "pip-system-certs"], capture=True, check=False)
        if result.returncode != 0:
            print("\n".join(report_lines))
            raise StepFailed(
                f"pip-system-certs could not be installed into conan's own "
                f"interpreter ({conan_interp}), which is different from "
                f"the interpreter running setup.py ({sys.executable}) - "
                "conan will keep using its unpatched certificate trust "
                "store no matter what setup.py's own interpreter trusts.",
                f'Run by hand: "{conan_interp}" -m pip install --user '
                "pip-system-certs, then re-run this script. Output:\n"
                + (result.stdout or ""),
            )
        report_lines.append(
            f"pip-system-certs installed into {conan_interp} too (differs "
            "from sys.executable).")
    elif conan_interp is not None:
        report_lines.append(
            "conan's interpreter is the same as sys.executable - already "
            "covered by the HTTPS trust step above.")
    else:
        report_lines.append(
            "conan's interpreter could not be determined - the second "
            "install above was skipped; verifying through conan itself "
            "below regardless.")

    verify = run(["conan", "search", CONAN_TLS_VERIFY_REF, "-r", "conancenter"],
                 capture=True, check=False)
    if verify.returncode != 0:
        output = verify.stdout or ""
        print("\n".join(report_lines))
        if any(marker.lower() in output.lower() for marker in _PIP_CERT_ERROR_MARKERS):
            raise StepFailed(
                f"`conan search {CONAN_TLS_VERIFY_REF} -r conancenter` "
                "still fails with a certificate error - conan's own "
                "interpreter "
                + (f"({conan_interp})" if conan_interp else
                   "(could not be determined)")
                + " does not trust this network's TLS-interception "
                "certificate.",
                (f'Run by hand: "{conan_interp}" -m pip install --user '
                 "pip-system-certs, then re-run this script."
                 if conan_interp else
                 "Find which Python `conan` itself runs under (e.g. read "
                 "its shebang/launcher by hand) and run: <that python> -m "
                 "pip install --user pip-system-certs, then re-run this "
                 "script.")
                + "\nOutput:\n" + output,
            )
        raise StepFailed(
            f"`conan search {CONAN_TLS_VERIFY_REF} -r conancenter` failed "
            "for a reason other than a certificate error.",
            "Check your network/conancenter reachability and re-run. Output:\n"
            + output,
        )

    report_lines.append(
        f"conan search {CONAN_TLS_VERIFY_REF} -r conancenter: OK")
    print("\n".join(report_lines))


def check_git(ctx):
    if on_path("git"):
        return "skip"
    raise StepFailed(
        "git is not on PATH. This repo is a git-submodule architecture "
        "(one repo per component, R-GIT-1)  -  git is required just to fetch "
        "the component repos.",
        "Install Git for Windows from https://git-scm.com/download/win "
        "(accept the default PATH option).",
    )


# CE-11 (conan_environment_plan.md §4.1): real, required Ubuntu/
# WSL system dev packages this repo's own build depends on that a real
# WSL session found missing one at a time, across three separate builds -
# each surfacing only as a cryptic CMake/ensurepip error deep into an
# unrelated build. libx11-dev/libgl1-mesa-dev: viz's GLFW/X11/OpenGL
# rendering stack (find_package(X11)/find_package(OpenGL REQUIRED) in its
# CMakeLists.txt). python3-venv: the bootstrap stub's own .venv creation
# (imp_design.md section 2.4) - ensurepip needs it, and there is no other
# way to create a venv on Debian/Ubuntu's own Python.
REQUIRED_LINUX_PACKAGES = ("libx11-dev", "libgl1-mesa-dev", "python3-venv")

# CE-23: a few of these apt names are thin meta-packages whose real
# content ships under a versioned name, so `dpkg -s <meta>` can report
# "not installed" on a machine where the capability is fully present and
# working. Ubuntu 22.04 is exactly this case for `python3-venv`: only
# `python3.10-venv` is installed, and `python3 -m venv` works. Checking
# the NAME rather than the CAPABILITY turned that into a hard stop during
# CE-20's Linux cold-machine run, which had to be worked around with a
# temporary dpkg shim just to get past it (§5.3) - i.e. the "zero
# manual steps" bar was missed on a machine that needed nothing.
#
# A package listed here is satisfied if EITHER dpkg knows it OR its probe
# succeeds. Only packages with a meaningful runtime probe appear; the
# others (libx11-dev, libgl1-mesa-dev - headers, nothing to execute) keep
# the dpkg-only behaviour they have always had.
_LINUX_PACKAGE_CAPABILITY_PROBES = {
    "python3-venv": [sys.executable, "-m", "venv", "--help"],
}


def _linux_package_present(pkg):
    """True if `pkg` is installed by name, OR - for a thin meta-package
    whose real content ships versioned - if its capability probe actually
    works (CE-23, see `_LINUX_PACKAGE_CAPABILITY_PROBES` above). Name
    first, since it is cheap and is the common case; the probe only runs
    for the packages that have one, and only once the name has failed.
    Never the other way round: a probe that passes while the package is
    genuinely absent is not a case that exists here, but a name check
    that fails on a working machine demonstrably is."""
    if run(["dpkg", "-s", pkg], capture=True, check=False).returncode == 0:
        return True
    probe = _LINUX_PACKAGE_CAPABILITY_PROBES.get(pkg)
    if probe is None:
        return False
    return run(probe, capture=True, check=False).returncode == 0


def check_linux_system_packages(ctx):
    """CE-11 (conan_environment_plan.md §4.1): checked up front,
    all at once, with ONE consolidated `sudo apt install` fix command -
    never run by this script itself. `sudo` is exactly the kind of
    unattended, elevated, shared-system change setup.py's own established
    discipline (bootstrap_team_server()'s firewall-rule step) already
    refuses to run on a developer's behalf.

    Windows-only equivalent doesn't exist (these are Ubuntu/apt package
    names) - os.name != "nt" only, same guard check_visual_studio() uses
    the other way around.
    """
    if os.name != "nt":
        missing = [
            pkg for pkg in REQUIRED_LINUX_PACKAGES
            if not _linux_package_present(pkg)
        ]
        if missing:
            raise StepFailed(
                f"Missing required system package(s): {', '.join(missing)}  -  "
                "each one otherwise surfaces only as a cryptic CMake/"
                "ensurepip error deep into an unrelated build (viz's GLFW/"
                "X11/OpenGL rendering stack, or the bootstrap stub's own "
                ".venv creation).",
                "sudo apt install -y " + " ".join(missing),
            )
    return "skip"


# CE-12 (conan_environment_plan.md §4.2): Conan's CMakeToolchain
# unconditionally writes CMakePresets.json/CMakeUserPresets.json with
# schema "version": 4 (needed for the "include" key CMakeUserPresets.json
# uses to pull in the generated file) - a schema CMake itself has only
# understood since 3.23 (cmake-presets(7): schema 1->CMake 3.19,
# 2->3.20, 3->3.21, 4->3.23). Found live under WSL: this Ubuntu 22.04
# image's system cmake was 3.22.1, one minor version short, surfacing
# only as `CMake Error: ... Unrecognized "version" field` deep into an
# otherwise-fine build - not the more lenient MIN_CMAKE (3.22) above,
# which Windows still uses (no presets-schema concern was ever found
# there).
MIN_CMAKE_FOR_CONAN_PRESETS = (3, 23)


def _cmake_version_on_path():
    """(major, minor) of whatever `cmake` currently resolves to on PATH,
    or None if it isn't on PATH / its --version output can't be parsed.
    """
    if not on_path("cmake"):
        return None
    result = run(["cmake", "--version"], capture=True, check=False)
    if result.returncode != 0 or not result.stdout:
        return None
    ver = result.stdout.splitlines()[0].split()[-1]
    try:
        major, minor = (int(x) for x in ver.split(".")[:2])
    except ValueError:
        return None
    return major, minor


def check_cmake(ctx):
    if os.name != "nt":
        return _check_cmake_linux(ctx)

    if not on_path("cmake"):
        raise StepFailed(
            "cmake is not on PATH. Every component's build.bat calls it.",
            "Install CMake from https://cmake.org/download/ "
            "(check 'Add CMake to the system PATH').",
        )
    out = run(["cmake", "--version"], capture=True).stdout.splitlines()[0]
    ver = out.split()[-1]
    major, minor = (int(x) for x in ver.split(".")[:2])
    if (major, minor) < MIN_CMAKE:
        raise StepFailed(
            f"cmake {ver} found, but {MIN_CMAKE[0]}.{MIN_CMAKE[1]}+ is required.",
            "Install a newer CMake from https://cmake.org/download/.",
        )
    return "skip"


def _check_cmake_linux(ctx):
    """CE-12 (conan_environment_plan.md §4.2): a modern CMake is
    one `pip install --user cmake` away on Linux, no elevation needed -
    so a too-old (or missing) system cmake here is fixed automatically,
    unlike Windows' manual-install-link message above (no equivalent
    no-sudo shortcut exists there). Checked against
    MIN_CMAKE_FOR_CONAN_PRESETS (3.23), not Windows' more lenient
    MIN_CMAKE (3.22) - see that constant's own comment for why.
    """
    version = _cmake_version_on_path()
    if version is not None and version >= MIN_CMAKE_FOR_CONAN_PRESETS:
        return "skip"

    reason = ("cmake is not on PATH" if version is None else
              f"cmake {version[0]}.{version[1]} found, but Conan's "
              "generated CMakePresets schema needs "
              f"{MIN_CMAKE_FOR_CONAN_PRESETS[0]}.{MIN_CMAKE_FOR_CONAN_PRESETS[1]}+")
    print(f"{reason}  -  installing a modern one via pip (no sudo needed)...")

    if ctx.dry_run:
        print("[dry-run] would run: pip install --user cmake")
        return "skip"

    try:
        run([sys.executable, "-m", "pip", "install", "--user", "cmake"])
    except subprocess.CalledProcessError:
        raise StepFailed(
            "pip install of cmake failed.",
            "Check your pip/network configuration and re-run, or install "
            f"CMake {MIN_CMAKE_FOR_CONAN_PRESETS[0]}.{MIN_CMAKE_FOR_CONAN_PRESETS[1]}+ "
            "yourself from https://cmake.org/download/.",
        )

    new_version = _cmake_version_on_path()
    if new_version is None or new_version < MIN_CMAKE_FOR_CONAN_PRESETS:
        raise StepFailed(
            "cmake was installed via pip, but a resolvable cmake "
            f">= {MIN_CMAKE_FOR_CONAN_PRESETS[0]}.{MIN_CMAKE_FOR_CONAN_PRESETS[1]} "
            "still isn't on PATH in THIS shell - a non-login shell's PATH "
            "may not include ~/.local/bin yet (the same issue "
            "_find_conan_server_exe() already works around for "
            "conan_server).",
            "Open a new login shell (or `source ~/.profile`) so "
            "~/.local/bin comes before /usr/bin on PATH, then re-run.",
        )
    print(f"cmake {new_version[0]}.{new_version[1]} now resolves on PATH.")


def check_visual_studio(ctx):
    if os.name != "nt":
        print("Non-Windows host  -  skipping the Visual Studio check "
              "(see setup.md section Linux for the ubuntu_gcc path).")
        return "skip"
    vswhere = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) \
        / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    if not vswhere.exists():
        raise StepFailed(
            "vswhere.exe not found  -  no Visual Studio installation detected. "
            "The build uses the 'Visual Studio 18 2026' CMake generator, "
            "toolset v145.",
            "Install Visual Studio 2026 Build Tools with the 'Desktop "
            "development with C++' workload (includes the MSVC v145 "
            "toolset and the Windows SDK  -  the latter also supplies "
            "OpenGL32.lib/GDI for the viz module, no separate GLEW/OpenGL "
            "SDK install needed). There is no automated install for this "
            "one  -  it's a multi-GB interactive installer.",
        )
    result = run(
        [str(vswhere), "-latest", "-products", "*",
         "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
         "-property", "installationPath"],
        capture=True, check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise StepFailed(
            "Visual Studio is installed but the 'Desktop development with "
            "C++' workload (VC.Tools.x86.x64) was not detected.",
            "Open the Visual Studio Installer, modify your installation, "
            "and add the 'Desktop development with C++' workload.",
        )
    return "skip"


def init_toolchain_and(mods, dry_run=False):
    """D0/D4 (partial_clone_correctness_plan.md W5): initialise modules/toolchain
    - build machinery every root command reads - plus `mods`, each only if git
    reports it not initialised. Never the rest of the repo. Raises StepFailed."""
    candidates = possibly_uninitialised(["toolchain"] + list(mods), ROOT)  # no git call if all present
    wanted = [m for m in candidates if m in uninitialised_submodules(ROOT)] if candidates else []
    if not wanted:
        return []
    try:
        return init_submodules_for(wanted, root=ROOT, dry_run=dry_run)
    except SubmoduleInitError as exc:
        raise StepFailed(exc.lines[0].removeprefix("ERROR: "),
                         "check the submodule out by hand, then re-run.",
                         exc.lines[-1].removeprefix("Run: "))


def init_submodules(ctx):
    if ctx.no_submodules:
        # A partial clone: leave every module as it is, except toolchain (D0),
        # without which setup cannot even find this host's offline bundle.
        if init_toolchain_and([], dry_run=ctx.dry_run):
            return None
        print("--no-submodules passed  -  leaving module checkout as-is "
              "(modules/toolchain is checked out).")
        return "skip"
    marker = ROOT / "modules" / "interfaces" / "CMakeLists.txt"
    if marker.exists():
        return "skip"
    if ctx.dry_run:
        print("[dry-run] would run: git submodule update --init --recursive")
        return "skip"
    try:
        run(["git", "submodule", "update", "--init", "--recursive"], cwd=ROOT)
    except subprocess.CalledProcessError:
        raise StepFailed(
            "git submodule update --init --recursive failed.",
            "Check your git remote access to every submodule URL in "
            ".gitmodules, then re-run.",
        )


def check_or_install_conan(ctx):
    if on_path("conan"):
        return "skip"
    if ctx.dry_run:
        print("[dry-run] would run: pip install --user \"conan>=2,<3\"")
        return "skip"
    if not ctx.yes and not ask_yes_no("Conan 2 was not found. Install it now via pip?"):
        raise StepFailed(
            "Conan 2 is required and was declined.",
            "Install it yourself (pip install --user \"conan>=2,<3\") or "
            "re-run with --yes, then re-run this script.",
        )
    try:
        run([sys.executable, "-m", "pip", "install", "--user", "conan>=2,<3"])
    except subprocess.CalledProcessError:
        raise StepFailed("pip install of Conan failed.",
                          "Check your pip/network configuration and re-run.")
    if on_path("conan"):
        return
    persisted = persist_user_scripts_dir_to_path() if os.name == "nt" else False
    if persisted:
        print("Persisted the pip user Scripts directory to your permanent user "
              "PATH  -  brand-new terminals will find conan automatically. "
              "This terminal (and any other already-open one) needs a restart "
              "to pick it up.")
    raise StepFailed(
        "Conan installed but its Scripts directory isn't on PATH in THIS terminal yet.",
        "Open a NEW terminal and re-run this script."
        + ("" if persisted else " If it still isn't found, add Python's user "
           "Scripts directory to PATH manually  -  run "
           "`python -m site --user-base` to find it."),
    )


def persist_user_scripts_dir_to_path():
    """Windows only: add pip's --user Scripts directory to HKCU\\Environment\\Path
    so future terminals find a freshly pip-installed console script (conan,
    here) without the user having to do it by hand. Ported from the retired
    install_dependencies.bat, which did the same via `reg add` + a
    WM_SETTINGCHANGE broadcast; done here with winreg/ctypes instead of
    shelling out to an encoded PowerShell one-liner. Best-effort: any failure
    just falls back to the "open a new terminal" message.
    """
    import sysconfig
    try:
        import winreg
    except ImportError:
        return False
    scripts_dir = sysconfig.get_path("scripts", "nt_user")
    if not scripts_dir or not Path(scripts_dir, "conan.exe").exists():
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                             winreg.KEY_READ | winreg.KEY_WRITE) as key:
            try:
                current, kind = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                current, kind = "", winreg.REG_EXPAND_SZ
            if scripts_dir.lower() in current.lower():
                return True  # already persisted, nothing to do
            new_value = f"{current};{scripts_dir}" if current else scripts_dir
            winreg.SetValueEx(key, "Path", 0, kind or winreg.REG_EXPAND_SZ, new_value)
    except OSError:
        return False

    try:
        import ctypes
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x1A
        SMTO_ABORTIFHUNG = 0x0002
        result = ctypes.c_ulong()
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment",
            SMTO_ABORTIFHUNG, 5000, ctypes.byref(result))
    except Exception:
        pass  # cosmetic only - the registry write above is what matters
    return True


def ensure_conan_profile(ctx):
    conan_home = os.environ.get("CONAN_HOME")
    if conan_home:
        base = Path(conan_home)
    else:
        home = Path(os.environ.get("USERPROFILE" if os.name == "nt" else "HOME", "~")).expanduser()
        base = home / ".conan2"
    profile = base / "profiles" / "default"
    if profile.exists():
        return "skip"
    if ctx.dry_run:
        print("[dry-run] would run: conan profile detect --force")
        return "skip"
    try:
        run(["conan", "profile", "detect", "--force"])
    except subprocess.CalledProcessError:
        raise StepFailed(
            "conan profile detect failed.",
            "Make sure a C++ compiler is actually installed (see the "
            "Visual Studio step above), then re-run.",
        )


NON_INTERACTIVE_LINE = "core:non_interactive = True"


def set_non_interactive(conf_path):
    """CE-28: make `core:non_interactive = True` the active setting in one
    global.conf, so an expired remote login raises at once instead of asking
    for a password. Idempotent: an existing (uncommented) core:non_interactive
    line is rewritten in place, never duplicated; every other line - including
    the commented `# core:non_interactive` template - is left alone. Returns
    True if the file changed."""
    conf_path = Path(conf_path)
    text = conf_path.read_text(encoding="utf-8") if conf_path.exists() else ""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"\s*core:non_interactive\s*=", line):
            if line.strip() == NON_INTERACTIVE_LINE:
                return False
            lines[i] = NON_INTERACTIVE_LINE
            break
    else:
        lines.append(NON_INTERACTIVE_LINE)
    conf_path.parent.mkdir(parents=True, exist_ok=True)
    conf_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def ensure_non_interactive_login(ctx):
    """CE-28: the CONAN_HOME setup.py manages gets core:non_interactive =
    True. Adas builds are never meant to prompt; the delegate path runs
    each component's own pinned adas_build_tools, which this setting
    covers without touching that package."""
    changed = []
    for home in (_standard_conan_home(),):
        conf = home / "global.conf"
        if ctx.dry_run:
            print(f"[dry-run] would ensure `{NON_INTERACTIVE_LINE}` in {conf}")
        elif set_non_interactive(conf):
            changed.append(str(conf))
    if changed:
        print("core:non_interactive = True written to: " + "; ".join(changed))
        return None
    return "skip"


def check_or_install_pyyaml(ctx):
    try:
        import yaml  # noqa: F401
        return "skip"
    except ImportError:
        pass
    if ctx.dry_run:
        print("[dry-run] would run: pip install --user pyyaml")
        return "skip"
    try:
        run([sys.executable, "-m", "pip", "install", "--user", "pyyaml"])
    except subprocess.CalledProcessError:
        raise StepFailed("pip install of PyYAML failed (needed by build.py).",
                          "Check your pip/network configuration and re-run.")


def discover_components():
    """Every modules/<x> with BOTH conanfile.py and conf/build.yml  -  i.e. a
    real, build.py-wired component today. Placeholder submodules (isp,
    perception-lane, planning, platform-services  -  cloned but not yet wired
    into the build) are deliberately excluded; they need nothing but
    `git submodule update --init`, already done in init_submodules().
    """
    mdir = ROOT / "modules"
    if not mdir.is_dir():
        return []
    return sorted(
        d.name for d in mdir.iterdir()
        if (d / "conanfile.py").exists() and (d / "conf" / "build.yml").exists()
    )


def remove_own_editable_registrations(ctx, comps, editables_text):
    """CE-16 (conan_environment_plan.md §5.1): `--mode package` must
    leave no editable registration behind for any of our own components -
    including one left over from an earlier `--mode develop` run (the
    default, and the only mode that ever existed before this), or one a
    developer added by hand. Conan's own rule is "editable always wins
    over a remote for the same reference" (docs/conan_server_remote.md
    section 3), so a single leftover registration would silently keep
    resolving that one component from this checkout even after switching
    modes - exactly the false confidence CE-17's standalone-clone proof
    exists to rule out. Path-based removal (`conan editable remove .` from
    inside the component's own directory), matching already_editable()'s
    own path-based matching rather than reconstructing a package
    reference. Returns the list of component names that had a
    registration removed (empty if none did)."""
    removed = []
    for name in comps:
        if not already_editable(editables_text, name):
            continue
        mod_dir = ROOT / "modules" / name
        if ctx.dry_run:
            print(f"[dry-run] {name}: would run: conan editable remove .  "
                  "(mode=package: removing pre-existing editable registration)")
            removed.append(name)
            continue
        try:
            run(["conan", "editable", "remove", "."], cwd=mod_dir)
        except subprocess.CalledProcessError:
            raise StepFailed(
                f"conan editable remove failed for {name} - mode=package must "
                "leave no editable registration behind.",
                f"Inspect the error above from inside modules/{name} and re-run.",
            )
        removed.append(name)
    return removed


def configure_conan_dependencies(ctx):
    """RD-03 (remove_develop_mode_plan.md): package mode is the only mode -
    this function no longer prepares a develop CONAN_HOME or registers any
    component editable (WP-23's develop-cache retargeting, and RP-07's
    --register-editables opt-in before it, are both gone). It still:
    discovers components, registers/logs in to the team Conan server if
    one is configured, and removes any editable registration left over
    from before this removal (CE-16's own guarantee, still needed -
    "editable always wins over a remote for the same reference" would
    otherwise silently keep resolving a stale editable even on a machine
    that has since upgraded past develop mode)."""
    comps = discover_components()
    if not comps:
        raise StepFailed(
            "No components with a conanfile.py + conf/build.yml were found "
            "under modules/  -  submodules likely aren't checked out.",
            "Re-run init_submodules (drop --no-submodules) and re-run.",
        )

    # WP-2/NS-02 (cache_first_no_server_plan.md D1/D2): with remotes off,
    # setup makes zero `conan remote add`/`conan remote login` calls -
    # register_team_remote() is never reached at all, whatever
    # team_conan_server.txt says.
    if not getattr(ctx, "remotes_enabled", True):
        print("Remotes off - not registering/logging in to any Conan "
              "remote. Resolution depends on this machine's own Conan "
              "cache (see 'Cache preparation' above/below).")
    else:
        server_url = read_team_server_url()
        if server_url:
            print(f"Team Conan server configured: {server_url}")
            register_team_remote(ctx, server_url)
        else:
            print("No team Conan server configured "
                  f"({TEAM_SERVER_FILE.relative_to(ROOT)} is still a placeholder) - "
                  "resolution will depend on whatever remotes are already "
                  "registered on this machine. 'Conan package resolution "
                  "completeness' below will report exactly what's missing.")

    # CE-16: package mode never registers our own components editable - the
    # whole point is exercising the server -> cache -> consume path a fresh
    # machine depends on. Any pre-existing registration (e.g. left over from
    # a pre-removal --mode develop run) is actively removed, not just left
    # alone.
    editables = existing_editables(ctx)
    removed = remove_own_editable_registrations(ctx, comps, editables)
    if removed:
        print(f"Removed pre-existing editable registration(s) for: "
              f"{', '.join(removed)}")
    print("No editable registrations made  -  every adas-* component this "
          "machine needs resolves from adas-local (Cache or Download), "
          "never from this checkout.")

    # NS-22(c) (cache_first_no_server_plan.md, redo of CE-35(b)): the
    # above only ever removes a registration pointing at THIS checkout's
    # own modules/<name> - a stray one pointing at a DIFFERENT checkout
    # entirely (the real second-corporate-PC bug: interfaces/mathlib/sim/
    # shared_config resolving Editable from a stale sibling checkout, no
    # warning at all) is invisible to it. Reported here, never removed -
    # removal is --clean-develop-leftovers's job only.
    _report_stray_editables(ctx, comps)


def _report_stray_editables(ctx, comps):
    """NS-22(c): warns about every editable registration still present in
    this machine's active Conan home after configure_conan_dependencies()
    has already removed this checkout's own (remove_own_editable_
    registrations(), above) - i.e. anything left is, by construction, not
    one of ours. Filtered by path rather than trusting that construction
    blindly, so a bug in the removal pass is reported rather than hidden
    by this step too. Read-only: never calls conan editable remove."""
    own_needles = [str((ROOT / "modules" / name).resolve()).lower() for name in comps]
    stray = {
        ref: path for ref, path in _all_editables(_active_conan_home()).items()
        if path and not any(needle in path.lower() for needle in own_needles)
    }
    for ref, path in sorted(stray.items()):
        print(f"WARNING: {ref} is still registered editable at {path}  -  "
              "it will silently win over any package resolved from the "
              "cache or a remote for the same reference (Conan's own "
              "rule: editable always wins). Clean it up with: python "
              "scripts/setup.py --clean-develop-leftovers --yes")


def register_team_remote(ctx, url):
    """Returns True if the remote is registered AND logged in - i.e. safe to
    rely on for downloading the base three instead of building them locally.

    NS-21 (cache_first_no_server_plan.md, redo of CE-36): checks network-
    level reachability BEFORE ever touching the remote. Real evidence, a
    second corporate PC, 2026-09-23: "ERROR: Package 'protobuf/3.21.12'
    not resolved ... 127.0.0.1:9300 ... actively refused it" during
    `conan install --update`, well after this function had already run
    and left adas-local registered - unreachable at THIS moment, but
    nothing here noticed. Unreachable now: a pre-existing registration is
    disabled (`conan remote disable adas-local`), printed with the exact
    one-line command to reverse it once the server is back; a not-yet-
    registered one is simply never added. Either way this function
    returns False and no login is even attempted - a login-level failure
    after a CONFIRMED-reachable port (the try/except below) is a
    genuinely different fault (auth, not connectivity), unaffected by
    this check.
    """
    if ctx.dry_run:
        print(f"[dry-run] would run: conan remote add adas-local {url}")
        print("[dry-run] would run: conan remote login adas-local demo -p demo")
        return False

    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 9300
    if not _port_reachable(port, host=host):
        existing_before = run(["conan", "remote", "list"], capture=True, check=False).stdout or ""
        if "adas-local" in existing_before:
            run(["conan", "remote", "disable", "adas-local"], check=False)
            print(f"WARNING: adas-local ({url}) is not reachable right now  -  "
                  "disabled the existing registration rather than leave a "
                  "known-dead remote enabled for every later `conan install` "
                  "to hit (CE-36). Re-enable once the server is back with: "
                  "conan remote enable adas-local")
        else:
            print(f"WARNING: adas-local ({url}) is not reachable right now  -  "
                  "not registering it in this known-broken state (CE-36).")
        return False

    existing = run(["conan", "remote", "list"], capture=True, check=False).stdout
    if "adas-local" not in existing:
        try:
            run(["conan", "remote", "add", "adas-local", url])
        except subprocess.CalledProcessError:
            raise StepFailed(
                f"conan remote add failed for {url}.",
                "Check the URL in scripts/team_conan_server.txt and that "
                "the server is reachable on your network.",
            )
    try:
        login = run(["conan", "remote", "login", "adas-local", "demo", "-p", "demo"],
                    check=False, timeout=REMOTE_LOGIN_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        print(f"WARNING: conan remote login to {url} did not respond within "
              f"{REMOTE_LOGIN_TIMEOUT_S}s  -  server is down or unreachable "
              "from this network. Continuing without it: root builds "
              "(package mode) build interfaces/mathlib/shared_config from "
              "this checkout.")
        return False
    if login.returncode != 0:
        print("WARNING: conan remote login failed  -  server unreachable or "
              "credentials changed. Continuing without it: root builds "
              "(package mode) build interfaces/mathlib/shared_config from "
              "this checkout.")
        return False
    return True


def existing_editables(ctx):
    if ctx.dry_run:
        return {}
    result = run(["conan", "editable", "list"], capture=True, check=False)
    return result.stdout or ""


def already_editable(editables_text, name):
    # conanfile.py's package name doesn't always match the folder name
    # (sil_host -> adas-sil, perception-core -> adas-perception-core), so
    # match on the checkout path instead of guessing the package reference.
    needle = str((ROOT / "modules" / name).resolve()).lower()
    return needle in (editables_text or "").lower()


def _all_editables(home):
    """NS-22(b)/(c) (cache_first_no_server_plan.md, redo of CE-35): every
    editable registration visible from `home` - `{ref: path}`, parsed from
    `conan editable list --format=json` - whatever path each one points
    at, unlike already_editable()'s own this-checkout-only text match.
    This is what makes a stray registration from a DIFFERENT checkout
    (the real second-corporate-PC bug: a package-mode aggregate in
    `D:\\1v-superproject` resolving interfaces/mathlib/sim/shared_config
    Editable from `D:\\df\\1v-superproject`) visible at all - `conan
    editable list`'s plain-text output isn't reliably parseable for the
    target path, `--format=json` is. A crafted subprocess env, never
    os.environ itself, so the ambient CONAN_HOME is never disturbed.
    Empty dict on any failure (conan missing, malformed output, non-zero
    exit) - a detection helper, never raises."""
    env = dict(os.environ)
    env["CONAN_HOME"] = str(home)
    try:
        result = subprocess.run(["conan", "editable", "list", "--format=json"],
                                env=env, capture_output=True, text=True, check=False)
    except OSError:
        return {}
    if result.returncode != 0:
        return {}
    try:
        data = json.loads(result.stdout or "{}")
    except (ValueError, TypeError):
        return {}
    return {ref: info.get("path") for ref, info in data.items()}


def _dev_conan_home():
    """RD-04 (remove_develop_mode_plan.md): where a pre-removal develop
    CONAN_HOME would have lived, absent ADAS_CONAN_HOME_DEV - read-only,
    purely to find leftover state. No longer resolved via
    conan_home_resolution.py (its own copy, default_dev_conan_home(), was
    removed along with develop mode itself, RD-03) - reimplemented here
    verbatim since this is the one remaining, deliberately narrow reason
    to still know where it used to live."""
    override = os.environ.get("ADAS_CONAN_HOME_DEV")
    return Path(override) if override else Path.home() / ".conan2-dev"


def find_develop_leftovers():
    """RD-04 / NS-22(b) (cache_first_no_server_plan.md, redo of CE-35): what
    a one-shot cleanup would remove - the develop CONAN_HOME directory
    itself (if it still exists on disk), and EVERY editable registration
    visible in either that develop home or this machine's ACTIVE home
    (_active_conan_home(), not _standard_conan_home() - CE-35's own
    incidental fix: an explicit CONAN_HOME override must be respected
    here, or detection silently examines the wrong home), whatever ref or
    path each one is. No longer filtered to this checkout's own
    components (discover_components() isn't read at all here any more) -
    NS-22(b)'s whole point is that a stray registration from a DIFFERENT
    checkout entirely (the real second-corporate-PC bug) must be found
    too, not just our own. Read-only, removes nothing - the caller
    decides whether to act on what this finds."""
    dev_home = _dev_conan_home()
    findings = {
        "dev_home": dev_home if dev_home.is_dir() else None,
        "editables": {},  # {home_label: {ref: path}}
    }
    for label, home in (("develop", dev_home), ("package", _active_conan_home())):
        if not home.is_dir():
            continue
        present = _all_editables(home)
        if present:
            findings["editables"][label] = present
    return findings


def cleanup_develop_leftovers(ctx):
    """D4 / RD-04 / NS-22(b) (cache_first_no_server_plan.md, redo of
    CE-35): a one-shot, printed, confirm-first cleanup of a pre-removal
    machine's leftover develop CONAN_HOME and EVERY editable registration
    this tool can see, in either the develop or the active Conan home,
    whatever path each one points at - the guard against the exact
    failure that cost a second corporate PC a build (a package-mode
    aggregate silently resolving interfaces/mathlib/sim/shared_config
    Editable from a completely different, stale checkout). Prints exactly
    what it would remove; removes ONLY with --yes. Removal is by
    reference (`conan editable remove --refs <ref>`), never by `cd`-ing
    into the registered path - that path may belong to a different
    checkout entirely, never something this tool should treat as a
    directory of its own. Never touches the user's real ~/.conan2-dev (or
    ADAS_CONAN_HOME_DEV override) without that explicit confirmation, and
    never reachable from the ordinary setup flow - only
    --clean-develop-leftovers."""
    findings = find_develop_leftovers()

    if findings["dev_home"] is None and not findings["editables"]:
        print("Nothing to clean up: no develop CONAN_HOME directory found, "
              "and no editable registration was found in the develop or "
              "active Conan home.")
        return

    print("Found leftover develop-mode state:")
    if findings["dev_home"] is not None:
        print(f"  - develop CONAN_HOME directory: {findings['dev_home']}")
    for label, present in findings["editables"].items():
        for ref, path in present.items():
            print(f"  - editable registration in the {label} cache: "
                  f"{ref} -> {path}")

    if not ctx.yes:
        print("\nRun again with --yes to remove the above. Nothing was changed.")
        return

    if findings["dev_home"] is not None:
        print(f"Removing {findings['dev_home']} ...")
        shutil.rmtree(findings["dev_home"])
    for label, present in findings["editables"].items():
        home = _dev_conan_home() if label == "develop" else _active_conan_home()
        env = dict(os.environ)
        env["CONAN_HOME"] = str(home)
        for ref, path in present.items():
            print(f"  conan editable remove --refs {ref} (in {label} cache, was: {path})")
            subprocess.run(["conan", "editable", "remove", "--refs", ref],
                           env=env, check=False)
    print("Done.")


def _stash_resolution_summary(ctx):
    """NS-23 (cache_first_no_server_plan.md, redo of CE-37): the ONE place
    that computes the value print_environment_summary() reports for
    "Packages resolvable" - called from ensure_resolution_complete()'s two
    success points (plain PASS, and after the RD-12 auto-publish). Both
    mean the same thing: every ref discover_required_refs() found is now
    resolvable, so resolved == total always - no second per-ref check_
    resolvable() walk needed, which is exactly the walk that used to be
    able to disagree with what this step already proved (the real bug:
    "[OK] ... All required adas-* refs are resolvable" immediately
    followed by "Packages resolvable: 2/7" in the same run)."""
    total = len(check_conan_resolution.discover_required_refs())
    if total == 0:
        ctx.resolution_summary = "0/0  (no adas-* refs declared)"
    else:
        ctx.resolution_summary = f"{total}/{total}"


def ensure_resolution_complete(ctx):
    """WP-02 (conan_environment_plan.md section 2.2): wires the already-
    built, already-proven checker (imp_design.md §6 WP-13,
    scripts/check_conan_resolution.py) into the normal setup flow, right
    after configure_conan_dependencies()  -  so "a component's package
    was never published to this machine's adas-local" stops being a bug
    someone notices from a failed build days later (the real sil_viz
    incident) and becomes a gap this step closes on the spot, for any
    component whose source is checked out here.

    Imported directly, not run as a subprocess  -  both scripts live at
    scripts/, and check_conan_resolution.main() is already a plain
    function returning an exit code, nothing to gain from a subprocess
    hop. This function does not re-implement or re-verify the checker's
    own detect-and-fix logic (already proven, WP-13's own DRT-11)  -  it
    only calls it.

    RD-03 (remove_develop_mode_plan.md): package mode is the only mode - a
    still-MISSING ref is always a hard StepFailed naming exactly which
    ref(s) the server lacks, UNLESS RD-12 (below) auto-published them.
    There is no local source to publish FROM on a genuinely fresh machine
    in the first place (a fresh machine's whole point is having nothing
    checked out but the one component it cloned), and publishing from
    *this* run's local cache would prove nothing about a genuinely cold
    machine (§5.3's own lesson: a build succeeding here was never evidence
    the artifacts exist elsewhere) - the developer must learn that gap at
    setup time, not at first build.

    RD-12 (remove_develop_mode_plan.md, 2026-09-22): the paragraph above is
    about a machine's local Conan CACHE, which is a different thing from
    THIS machine's own adas-local SERVER (`scripts/team_conan_server.txt`
    pointed at loopback, `_adas_local_is_local_server()`). A server on this
    machine that lacks our first-party refs is not "a genuinely cold
    machine's cache" - it is this developer's own, empty server, and
    publishing this checkout's source onto it is exactly `RD-09`'s own
    manual two-step (`setup.bat` fail -> `check_conan_resolution.py
    --publish-missing` by hand -> `setup.bat` again), automated. A REAL
    team server (any non-loopback host) never gets this treatment -
    publishing one developer's checkout to a server other people share is
    not setup's job, so that case still falls straight through to the
    verify-only StepFailed below, unchanged.

    CE-32 (conan_environment_plan.md): the loopback-server failure text
    used to say "setup.py never publishes from this machine's local
    cache" - true of the non-loopback branch below, but ACTIVELY FALSE
    of this one: RD-12 just tried exactly that publish, right above, and
    it still failed. This repo's own committed scripts/team_conan_
    server.txt always points at loopback (RD-12's own docstring), so
    this is the common branch, not the rare one - real evidence, a
    second corporate PC, 2026-09-23: the misleading old message hid the
    real cause (adas-local wasn't reachable at all, CE-31's own bug) and
    named a remedy (re-run --publish-missing by hand) that does nothing
    to fix "the server isn't running" or "conancenter isn't reachable
    for a third-party build dependency the publish needed". Split into
    two distinct messages below, one per branch, naming the real causes
    and remedies - including `setup.bat --offline` - instead.
    """
    platform = "vs2026" if os.name == "nt" else "ubuntu_gcc"
    # WP-2/NS-03: forward setup's own remotes decision explicitly (already
    # computed+printed once in main()) rather than let check_conan_
    # resolution.py re-derive it from team_conan_server.txt a second time -
    # the two must never disagree, and forwarding is what guarantees that.
    remotes_flag = ["--remotes", "on" if getattr(ctx, "remotes_enabled", True) else "off"]

    if ctx.dry_run:
        print("[dry-run] would run: python scripts/check_conan_resolution.py "
              f"--platform {platform} {' '.join(remotes_flag)}   (cache "
              "first; verify-only against a remote when remotes are on, "
              "never publish from this machine's cache; --publish-missing "
              "only if adas-local is this machine's own loopback server, "
              "RD-12, and only with remotes on)")
        return "skip"
    exit_code = check_conan_resolution.main(["--platform", platform, *remotes_flag])
    if exit_code == 0:
        _stash_resolution_summary(ctx)
        return
    if not getattr(ctx, "remotes_enabled", True):
        raise StepFailed(
            "One or more adas-* packages are not resolvable from this "
            "machine's Conan cache, and remotes are off (WP-1/NS-01) - "
            "setup.py never contacts a remote or publishes with remotes "
            "off (see the MISSING lines above for exactly which ref(s)).",
            "Re-run setup.bat (its cache-fill preparation step restores "
            "what it can from misc/offline_bundle/ when that folder "
            "exists), or point scripts/team_conan_server.txt at a real "
            "server, or pass --remotes on for one run.",
        )
    if _adas_local_is_local_server():
        print("adas-local resolves to this machine (loopback) - publishing "
              "the missing ref(s) from this checkout's own source instead "
              "of failing (RD-12)...")
        # NS-21 (cache_first_no_server_plan.md): real bug found running
        # cold_machine_check.py --with-server for real, 2026-09-23 - this
        # call used to omit --remotes entirely, so check_conan_
        # resolution.py re-derived remotes_enabled() from scratch and, for
        # THIS repo's own committed loopback team_conan_server.txt,
        # NS-24/D1a made that come back "off" - defeating the publish
        # this very branch exists to attempt (`_adas_local_is_local_
        # server()` already proved a loopback server IS configured,
        # regardless of what the freshly-rederived default would say).
        # remotes_flag was computed above specifically to avoid a second,
        # disagreeing derivation (WP-2/NS-03's own reasoning) - forwarded
        # here too, not just on the plain verify-only call above.
        exit_code = check_conan_resolution.main(
            ["--platform", platform, "--publish-missing", *remotes_flag])
        if exit_code == 0:
            # NS-23: same stash as the plain success path above - this
            # publish just made every discovered ref resolvable too.
            _stash_resolution_summary(ctx)
            return
        raise StepFailed(
            "adas-local resolves to this machine's own loopback server, "
            "and setup.py just tried to publish the missing ref(s) from "
            "this checkout onto it (RD-12, see the MISSING/publish output "
            "above) - that attempt still failed. The real cause is almost "
            "always one of: adas-local itself isn't actually reachable/"
            "running on this machine (check the 'Conan server on-demand "
            "persistence' step's own output above), or conancenter isn't "
            "reachable to build a third-party dependency the publish "
            "needed (protobuf, yaml-cpp, zlib, ...) - check the 'HTTPS "
            "trust' steps' own output above.",
            "Re-run setup.bat once the server is reachable (CE-31: this "
            "script now installs and starts conan_server itself when it's "
            "missing, rather than skipping it) and conancenter is "
            "reachable (see the HTTPS trust steps above), or use `setup.bat "
            "--offline` to build from a pre-fetched bundle instead of the "
            "network (offline_setup_plan.md). If neither applies, re-run "
            "`python scripts/check_conan_resolution.py --publish-missing "
            "--remotes on` directly to see the full, uncaptured error "
            "(NS-24/D1a: a loopback team_conan_server.txt needs the "
            "explicit override, same as this step now passes internally).",
        )
    raise StepFailed(
        "One or more adas-* packages are not resolvable, and adas-local "
        "does not resolve to this machine (scripts/team_conan_server.txt "
        "points elsewhere, or is unconfigured) - setup.py never publishes "
        "this checkout's source onto a server it doesn't own.",
        "Publish the missing ref(s) to that server from a machine that "
        "has their source checked out (`python scripts/"
        "check_conan_resolution.py --publish-missing`), or point "
        "scripts/team_conan_server.txt at a server that already has "
        "them, or use `setup.bat --offline` (offline_setup_plan.md) to "
        "build from a pre-fetched bundle instead, then re-run setup.bat.",
    )


def _adas_local_is_local_server():
    """RD-12: True iff `scripts/team_conan_server.txt` resolves adas-local
    to a loopback host - THIS machine's own server, safe for setup.py to
    publish this checkout's source onto. False for a real team server (any
    other host) and when no team server is configured at all (there is
    then nothing this function can confirm is safe to write to - the
    conservative, unchanged verify-only path)."""
    url = read_team_server_url()
    if url is None:
        return False
    return urlparse(url).hostname in ("127.0.0.1", "localhost", "::1")


def verify_roster(ctx):
    if ctx.dry_run:
        print("[dry-run] would run: python scripts/build.py config")
        return "skip"
    try:
        run([sys.executable, "scripts/build.py", "config"], cwd=ROOT)
    except subprocess.CalledProcessError:
        raise StepFailed(
            "python scripts/build.py config failed  -  this is a read-only "
            "listing, so a failure here means the module/target/platform "
            "roster itself can't even be derived.",
            "Re-run with the full traceback (drop capture) and check that "
            "every modules/*/conf/build.yml is present and valid YAML.",
        )


# --full-verify: pre-fetch/build every third-party Conan dependency (not just
# register the first-party editables) for the two components most people
# start with, so a real build is one command away instead of stalling on a
# first-time `conan install --build=missing`. Ported from the retired
# install_dependencies.bat rather than generalized to every component -
# everyone else builds what they need via scripts/build.py directly (section 7).
FULL_VERIFY_TARGETS = {
    "perception-core": ["standalone", "sil", "gtest"],
    "df": ["sil", "gtest"],
}


def full_verify(ctx):
    if not ctx.full_verify:
        return "skip"
    if os.name != "nt":
        print("--full-verify's vs2026 output folders are Windows-specific  -  skipping.")
        return "skip"
    for name, targets in FULL_VERIFY_TARGETS.items():
        mod_dir = ROOT / "modules" / name
        if not (mod_dir / "conanfile.py").exists():
            print(f"{name}: not checked out, skipping its dependency install.")
            continue
        for target in targets:
            out_dir = mod_dir / "conan_workarea" / f"build-{target}-vs2026"
            if ctx.dry_run:
                print(f"[dry-run] would run: conan install {mod_dir} "
                      f"--output-folder {out_dir} --build=missing -s build_type=Release")
                continue
            print(f"{name} ({target}): installing Conan dependencies (Release)...")
            try:
                run(["conan", "install", str(mod_dir), "--output-folder", str(out_dir),
                     "--build=missing", "-s", "build_type=Release"])
            except subprocess.CalledProcessError:
                raise StepFailed(
                    f"conan install failed for {name} ({target}).",
                    f"Re-run `conan install {mod_dir} --output-folder {out_dir} "
                    f"--build=missing -s build_type=Release` directly to see the "
                    f"full output, fix the reported error, and re-run setup.",
                )


def _find_conan_server_exe():
    """Resolves the real conan_server executable path without hardcoding
    it (conan_environment_plan.md CE-01). PATH first, the common case;
    falls back to the pip `--user` Scripts directory  -  the same
    fallback persist_user_scripts_dir_to_path() already needs for
    conan.exe, because a `pip install --user conan_server` (bootstrap_team_
    server()'s own install step) lands its Scripts directory in a place
    that isn't guaranteed to already be on PATH. Returns None if it can't
    be found either way.

    CE-09/WSL hardening (found live, 2026-09-10): the pip `--user`
    fallback was Windows-only (`nt_user` scheme) with no POSIX
    equivalent, so under WSL/Linux, any non-login shell (confirmed live:
    a plain `bash -c`, as opposed to `bash -lc`  -  Ubuntu's PATH-editing
    stanza for `~/.local/bin` lives in `~/.profile`, sourced only for
    login shells) would see `shutil.which("conan_server")` fail even
    though `pip install --user conan_server` genuinely installed it,
    wrongly reporting "not installed". Fixed with the symmetric POSIX
    fallback (`sysconfig.get_path("scripts", "posix_user")`, confirmed
    live to resolve to `~/.local/bin`, matching where `pip install --user`
    actually placed it  -  the *default* posix scheme resolves to
    `/usr/local/bin` instead, the wrong, system-wide location).
    """
    found = shutil.which("conan_server")
    if found:
        return found
    import sysconfig
    scheme = "nt_user" if os.name == "nt" else "posix_user"
    exe_name = "conan_server.exe" if os.name == "nt" else "conan_server"
    candidate = Path(sysconfig.get_path("scripts", scheme)) / exe_name
    if candidate.exists():
        return str(candidate)
    return None


def _port_reachable(port, host="127.0.0.1", timeout=SERVER_CONNECT_TIMEOUT_S):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        try:
            s.connect((host, port))
            return True
        except OSError:
            return False


def _ensure_section_line(text, section, needed_line):
    """NS-21 (cache_first_no_server_plan.md, redo of CE-34): the single
    shared implementation both ensure_server_running() (below) and
    cold_machine_check.py's own scratch-server bring-up now call - moved
    here from cold_machine_check.py, where it started life (found live
    writing that script for real, 2026-09-22, two copies had already
    begun to matter). Real bug this exists for: a fresh `conan_server
    --migrate` template already ships BOTH `[write_permissions]` and
    `[users]` headers, populated with commented-out EXAMPLE rules only -
    a naive `if "[write_permissions]" not in text` check never fires
    against this, so the actual active rule a server needs never gets
    written, and every publish fails with `Permission denied for user:
    'demo'` even though login itself succeeds. Ensures `needed_line` is
    present as an ACTIVE (non-comment) line directly under `[section]`,
    regardless of what commented content is already there; appends the
    section from scratch if the header itself is missing. Never deletes
    or otherwise touches existing content."""
    lines = text.splitlines()
    header_idx = None
    next_idx = len(lines)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if header_idx is None and stripped == f"[{section}]":
            header_idx = i
            continue
        if header_idx is not None and stripped.startswith("[") and stripped.endswith("]"):
            next_idx = i
            break
    if header_idx is None:
        lines.append("")
        lines.append(f"[{section}]")
        lines.append(needed_line)
        return "\n".join(lines) + "\n"
    for line in lines[header_idx + 1:next_idx]:
        if line.strip() == needed_line:
            return "\n".join(lines) + "\n"
    lines.insert(header_idx + 1, needed_line)
    return "\n".join(lines) + "\n"


def _server_conf_permission_fix(text):
    """CE-34 (conan_environment_plan.md): forces the three ACTIVE lines a
    working conan_server needs - `*/*@*/*: *` under `[read_permissions]`,
    `*/*@*/*: demo` under `[write_permissions]`, `demo: demo` under
    `[users]` - the same throwaway `demo`/`demo` credential
    register_team_remote() always logs in as. A fresh, `--migrate`d
    server.conf ships only commented-out example rules for these, so
    every request is denied by default until this runs once."""
    text = _ensure_section_line(text, "read_permissions", "*/*@*/*: *")
    text = _ensure_section_line(text, "write_permissions", "*/*@*/*: demo")
    text = _ensure_section_line(text, "users", "demo: demo")
    return text


def ensure_server_conf_permissions(conf_path):
    """NS-21 (cache_first_no_server_plan.md, redo of CE-34): the single
    shared implementation both ensure_server_running() (below) and
    cold_machine_check.py's own scratch-server bring-up call - one
    implementation, never a second, driftable copy. Backs up to `.bak`
    before writing, and ONLY writes/backs up when something actually
    changed - an already-correct file is left byte-identical, no backup
    created. Returns True iff the file was rewritten; False for a
    missing file (nothing to fix) or one that was already correct."""
    conf_path = Path(conf_path)
    if not conf_path.is_file():
        return False
    original = conf_path.read_text(encoding="utf-8")
    fixed = _server_conf_permission_fix(original)
    if fixed == original:
        return False
    backup_path = conf_path.parent / f"{conf_path.name}.bak"
    backup_path.write_text(original, encoding="utf-8")
    conf_path.write_text(fixed, encoding="utf-8")
    return True


def _find_listening_pid(port):
    """CE-34: best-effort PID-by-port lookup, used only to decide whether
    an already-running conan_server can be found and restarted after its
    server.conf permissions were just fixed in place. Platform-
    appropriate command (Windows: `netstat -ano`; POSIX: `ss -ltnp`);
    never raises - a missing/failing command just means "couldn't find
    it", which the caller reports as a WARNING, never a crash."""
    cmd = ["netstat", "-ano"] if os.name == "nt" else ["ss", "-ltnp"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except OSError:
        return None
    if result.returncode != 0:
        return None
    needle = f":{port}"
    for line in (result.stdout or "").splitlines():
        if needle not in line:
            continue
        if os.name == "nt":
            if "LISTENING" not in line:
                continue
            parts = line.split()
            try:
                return int(parts[-1])
            except (ValueError, IndexError):
                continue
        else:
            if "LISTEN" not in line:
                continue
            match = re.search(r"pid=(\d+)", line)
            if match:
                return int(match.group(1))
    return None


def _kill_pid_tree(pid):
    """CE-34: stops an already-running conan_server (found by
    _find_listening_pid(), above) found by bare PID - not a Popen handle
    this process itself created (RD-14/cold_machine_check.py's own
    _terminate_process_tree() covers that, different case: a process THIS
    run launched). `taskkill /F /T /PID` on Windows kills the whole
    process tree, matching _terminate_process_tree()'s own reasoning
    (conan_server can sit behind a wrapper/launcher process); SIGTERM on
    POSIX. Returns True iff the kill command itself reported success - a
    caller still re-checks reachability rather than trusting this
    blindly."""
    if os.name == "nt":
        result = subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                                capture_output=True, text=True, check=False)
        return result.returncode == 0
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return False
    return True


def ensure_server_running(ctx):
    """On-demand server persistence (conan_environment_plan.md section 2.1)
    -  replaces the abandoned register_server_startup_task() Scheduled Task
    design (see the plan's own Status header for why `onlogon` task
    creation was dropped). Not "restart at logon"  -  "be running whenever
    something needs you": a plain socket check, and a detached launch only
    if nothing answers.

    Runs for --role dev only (called from main()). --role server's own
    bootstrap_team_server() flow is a deliberate one-time,
    printed-not-executed setup sequence for a server.conf that doesn't
    exist yet on a genuinely first-time run  -  nothing to "ensure
    running" until that manual flow has happened once.

    Also stashes ctx.server_recovery_status ("up" / "launched" /
    "unavailable" / "would_launch_dry_run") as a side channel for
    print_environment_summary()'s own Auto-recovery line (WP-03,
    conan_environment_plan.md CE-04) to read later in the same run.
    Deliberately NOT a change to this function's own return value, which
    step()'s [SKIP]/[OK] banner already depends on (CE-01/CE-02, already
    tested, out of WP-03's own scope to touch) - "what happened this run"
    is history only this function observes, and a fresh reachability
    check at print time could never answer "was it launched a moment
    ago", only "is it up right now".

    CE-31 (conan_environment_plan.md): a missing conan_server used to be
    reported (return "skip") and left un-launched - step()'s own banner
    then printed "[SKIP] ... already satisfied", which is actively false:
    nothing was satisfied, nothing was launched. Real evidence, a second
    corporate PC, 2026-09-23: "adas-local isn't reachable ... conan_server
    isn't installed ... nothing to launch" followed immediately by
    "[SKIP] ... already satisfied" - exactly this. conan_server absent is
    now installed (`pip install --user conan_server`, unconditional - the
    same "just part of setup" treatment ensure_https_trust() already gives
    pip-system-certs, never a conditional branch someone has to know to
    ask for) and then launched as before. An install failure is a hard
    StepFailed naming the fix, including the honest alternative for a
    machine that genuinely does not want to run its own local server:
    point scripts/team_conan_server.txt at a real server, or use
    `setup.bat --offline`.
    """
    # WP-2/NS-02 (cache_first_no_server_plan.md D1/D2): with remotes off,
    # setup makes zero calls toward a server - never reaches for it, never
    # installs conan_server, never launches one. Checked first, before the
    # port lookup below, so a remotes-off run touches neither the network
    # nor the filesystem here at all.
    if not getattr(ctx, "remotes_enabled", True):
        print("Remotes off - skipping conan_server reachability/install/"
              "launch entirely (no team Conan server is configured).")
        return "skip"

    server_dir = os.environ.get("ADAS_CONAN_SERVER_DIR", r"C:\ws\conan_server_data")
    # Reuses conan_server_guard.py's own port lookup (the same server.conf
    # it reads port from to decide whether to refuse a second instance)
    # rather than a second, independent parse of the same file.
    port = conan_server_guard._read_configured_port(server_dir)
    conf_path = Path(server_dir) / "server.conf"

    if _port_reachable(port):
        return _fix_permissions_of_running_server(ctx, conf_path, port)

    conan_server_exe = _find_conan_server_exe()

    if conan_server_exe is None:
        if ctx.dry_run:
            print(f"adas-local isn't reachable on 127.0.0.1:{port}, and "
                  "conan_server isn't installed/resolvable on this machine "
                  "either.")
            print("[dry-run] would run: pip install --user conan_server")
            ctx.server_recovery_status = "would_launch_dry_run"
            return "skip"

        print(f"adas-local isn't reachable on 127.0.0.1:{port}, and "
              "conan_server isn't installed/resolvable on this machine "
              "either  -  installing it (pip install --user "
              "conan_server)...")
        result = run([sys.executable, "-m", "pip", "install", "--user", "conan_server"],
                     capture=True, check=False)
        if result.returncode != 0:
            ctx.server_recovery_status = "unavailable"
            raise StepFailed(
                "pip install of conan_server failed - CE-31 "
                "(conan_environment_plan.md): a missing conan_server is no "
                "longer treated as 'nothing to do', since a working "
                "adas-local depends on a real local server existing "
                "somewhere.",
                "Check your pip/network configuration and re-run. If this "
                "machine genuinely does not want to run its own local "
                "server: point scripts/team_conan_server.txt at a real, "
                "reachable server instead, or use `setup.bat --offline` "
                "(offline_setup_plan.md) to build from a pre-fetched "
                "bundle instead of a server at all.\nOutput:\n"
                + (result.stdout or ""),
            )

        conan_server_exe = _find_conan_server_exe()
        if conan_server_exe is None:
            ctx.server_recovery_status = "unavailable"
            raise StepFailed(
                "conan_server installed via pip but still isn't "
                "resolvable on this machine (its pip --user Scripts "
                "directory may not be on PATH in THIS terminal yet - the "
                "same PATH-refresh gap check_or_install_conan()'s own "
                "message describes for conan itself).",
                "Open a NEW terminal and re-run this script. If it still "
                "isn't found, add Python's user Scripts directory to PATH "
                "manually (run `python -m site --user-base` to find it), "
                "or point scripts/team_conan_server.txt at a real server "
                "instead, or use `setup.bat --offline`.",
            )
        print(f"conan_server installed: {conan_server_exe}")

    # conan_server_exe is guaranteed non-None from here (found originally
    # above, or just installed).
    _ensure_server_conf_before_first_launch(ctx, conan_server_exe, server_dir, conf_path)

    guard_script = Path(__file__).resolve().parent / "conan_server_guard.py"
    cmd = [sys.executable, str(guard_script), conan_server_exe, "--server_dir", server_dir]

    if ctx.dry_run:
        print(f"[dry-run] would launch (detached): {' '.join(cmd)}")
        ctx.server_recovery_status = "would_launch_dry_run"
        return "skip"

    _launch_conan_server_detached(cmd, server_dir, port)
    print(f"adas-local wasn't reachable on 127.0.0.1:{port}  -  launched "
          f"conan_server detached (log: {Path(server_dir) / 'conan_server_launch.log'}).")
    ctx.server_recovery_status = "launched"


def _launch_conan_server_detached(cmd, server_dir, port):
    """The Popen dance both the fresh-launch and the restart-after-a-
    permission-fix paths in ensure_server_running() need, extracted so
    neither duplicates the platform-specific detach flags.

    Real bug found running cold_machine_check.py --with-server for real,
    2026-09-23: launching detached and returning immediately (the
    original behaviour) left a race - the very next setup.py step,
    register_team_remote(), ran its own _port_reachable() check moments
    later and found the port not bound yet (conan_server hadn't finished
    starting), so CE-36's new reachability gate (correctly, given what it
    saw) treated a server that was ABOUT to be up as permanently
    unreachable and never registered it. Never a problem before this
    session: cold_machine_check.py used to launch the scratch server
    itself and wait for it, well before ever invoking setup.bat - NS-21
    moved that launch INTO setup.bat, so setup.bat must now do its own
    waiting too. Bounded (10s, matching the wait loop cold_machine_
    check.py's own former direct-launch code used) - a server that still
    isn't up after that is a real problem the NEXT step's own
    reachability check will correctly report, not silently hidden here."""
    log_path = Path(server_dir) / "conan_server_launch.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    popen_kwargs = {"stderr": subprocess.STDOUT}
    if os.name == "nt":
        popen_kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
    else:
        popen_kwargs["start_new_session"] = True
    # The child inherits its own duplicated copy of the fd at Popen() time,
    # so the parent's handle is safe to close right after  -  it must not
    # stay open for the rest of this (long-running, multi-step) process.
    with open(log_path, "ab") as log_file:
        subprocess.Popen(cmd, stdout=log_file, **popen_kwargs)
    for _ in range(50):
        if _port_reachable(port):
            break
        time.sleep(0.2)


def _ensure_server_conf_before_first_launch(ctx, conan_server_exe, server_dir, conf_path):
    """NS-21 (cache_first_no_server_plan.md, redo of CE-34): a genuinely
    fresh bring-up (server.conf doesn't exist yet at all) needs `--migrate`
    run once before there's a file to fix. Real corporate-PC bug: a
    freshly `--migrate`d server.conf ships with only commented-out
    permission rules, so the FIRST launch already served denied-by-default
    requests - fixed here, before that first launch, rather than
    discovered later as a failed upload. A pre-existing conf (however it
    got there) is fixed in place without a --migrate call."""
    if not conf_path.exists():
        if ctx.dry_run:
            print(f"[dry-run] would run: {conan_server_exe} --server_dir "
                  f"{server_dir} --migrate   (CE-34: server.conf doesn't "
                  "exist yet)")
            return
        migrate = run([conan_server_exe, "--server_dir", str(server_dir), "--migrate"],
                     capture=True, check=False)
        if migrate.returncode != 0:
            raise StepFailed(
                f"conan_server --migrate failed (exit code {migrate.returncode}) - "
                "CE-34 (conan_environment_plan.md): server.conf could not be "
                "created before the first launch.",
                "Re-run with the output above; it's the real conan_server "
                "--migrate error (disk space, permissions on "
                f"{server_dir}, ...).\nOutput:\n" + (migrate.stdout or ""),
            )
    if ctx.dry_run:
        return
    ensure_server_conf_permissions(conf_path)


def _fix_permissions_of_running_server(ctx, conf_path, port):
    """NS-21 (cache_first_no_server_plan.md, redo of CE-34): the server is
    ALREADY reachable - if its server.conf still carries only commented-
    out permission rules (written by a version of this script before this
    row existed, or edited by hand), the running instance is serving that
    BROKEN config right now; fixing the file on disk alone does nothing
    until the process re-reads it. A real change therefore forces a
    restart (find-by-port, kill, relaunch with the SAME command this
    function's caller would have used for a fresh launch) - reported
    honestly with a WARNING, never silently, if the restart itself can't
    be carried out (the fix is still applied to disk either way, so the
    NEXT manual/automatic restart picks it up)."""
    if not conf_path.exists():
        # Reachable with no local server.conf at all - this port belongs
        # to a server whose config lives somewhere this run doesn't know
        # about (e.g. ADAS_CONAN_SERVER_DIR pointed elsewhere for THIS
        # server). Nothing local to fix.
        ctx.server_recovery_status = "up"
        return "skip"

    original = conf_path.read_text(encoding="utf-8")
    would_change = _server_conf_permission_fix(original) != original

    if ctx.dry_run:
        if would_change:
            print(f"[dry-run] CE-34: {conf_path} still carries only "
                  "commented-out permission rules - would fix them and "
                  "would restart conan_server so the fix takes effect.")
        ctx.server_recovery_status = "up"
        return "skip"

    if not ensure_server_conf_permissions(conf_path):
        ctx.server_recovery_status = "up"
        return "skip"

    conan_server_exe = _find_conan_server_exe()
    pid = _find_listening_pid(port)
    if pid is None or conan_server_exe is None:
        print(f"WARNING: fixed {conf_path}'s permissions, but couldn't find "
              f"the process listening on port {port} to restart it - the "
              "already-running server is still serving the OLD, broken "
              "permissions. Please restart it by hand (or re-run this "
              "script) for the fix to take effect.")
        ctx.server_recovery_status = "restart_failed"
        return "skip"

    _kill_pid_tree(pid)
    time.sleep(0.5)  # let the OS release the port before rebinding it
    guard_script = Path(__file__).resolve().parent / "conan_server_guard.py"
    server_dir = str(conf_path.parent)
    cmd = [sys.executable, str(guard_script), conan_server_exe, "--server_dir", server_dir]
    _launch_conan_server_detached(cmd, server_dir, port)
    print(f"{conf_path} carried only commented-out permission rules  -  "
          "fixed them and restarted the already-running conan_server "
          f"(was pid {pid}) so the fix takes effect.")
    ctx.server_recovery_status = "restarted"


def _standard_conan_home():
    # Mirrors ensure_conan_profile()'s own "no CONAN_HOME override" default
    # computation elsewhere in this file - not imported from there since
    # that function returns a profile path, not the bare home dir, and
    # duplicating two lines beats coupling two unrelated steps together.
    # Deliberately ALWAYS the fixed default, override or not -
    # print_environment_summary() uses this specifically to DETECT an
    # explicit CONAN_HOME override (its own "Cache, explicit override:"
    # line), which only works if this never follows one itself. Anything
    # that needs the home Conan is ACTUALLY using calls
    # _active_conan_home() below instead.
    home = Path(os.environ.get("USERPROFILE" if os.name == "nt" else "HOME", "~")).expanduser()
    return home / ".conan2"


def _active_conan_home():
    """NS-22(b) (cache_first_no_server_plan.md, redo of CE-35, incidental
    fix): unlike _standard_conan_home() above (deliberately always the
    fixed default), this respects an explicit CONAN_HOME override when
    one is set. find_develop_leftovers()/cleanup_develop_leftovers()'s own
    stray-editable detection must examine the home Conan is ACTUALLY
    using - calling _standard_conan_home() directly there would silently
    examine the wrong home on any machine (including this file's own
    scratch-CONAN_HOME test harness) running with an explicit override,
    and CE-35's own detection could then never find what it was built to
    find."""
    override = os.environ.get("CONAN_HOME")
    return Path(override) if override else _standard_conan_home()


def _auto_recovery_line(ctx):
    status = getattr(ctx, "server_recovery_status", None)
    if status == "up":
        return "on-demand (ensure_server_running, this run: was already up)"
    if status == "launched":
        return "on-demand (ensure_server_running, this run: was down, launched it)"
    if status == "would_launch_dry_run":
        return "on-demand (ensure_server_running, this run: --dry-run, would have launched it)"
    if status == "unavailable":
        return ("on-demand (ensure_server_running, this run: down, conan_server "
                "not installed/resolvable  -  nothing launched)")
    if status == "restarted":
        return ("on-demand (ensure_server_running, this run: was up with broken "
                "server.conf permissions, CE-34  -  fixed and restarted it)")
    if status == "restart_failed":
        return ("on-demand (ensure_server_running, this run: was up with broken "
                "server.conf permissions, CE-34  -  fixed the file but couldn't "
                "restart the process; restart it by hand)")
    # None: ensure_server_running() never ran this session (--role server,
    # whose bootstrap_team_server() flow deliberately doesn't call it -
    # see that function's own docstring).
    return "on-demand (ensure_server_running only runs for --role dev  -  not run this session)"


def print_environment_summary(ctx):
    """SS2.3 (conan_environment_plan.md): one consolidated block, always,
    the LAST thing every run does, for BOTH --role dev and --role server,
    --dry-run included  -  this is pure reporting with no side effects, so
    it is exempt from the dry-run-skips-real-work pattern every other
    step uses. Answers "is my Conan setup actually fine" from one place,
    without needing to know CONAN_HOME / scripts/team_conan_server.txt /
    whether adas-local is even running right now are three separate
    things to check (section 1 point 3's own diagnosis-friction note from
    the real sil_viz incident).

    Called directly from main(), NOT wrapped in step()  -  a report has no
    pass/fail outcome for step()'s [SKIP]/[OK]/StepFailed banner machinery
    to represent, and "[SKIP] ... already satisfied" would be a nonsense
    thing to print about a summary that just ran.

    Every line is freshly, independently re-derived right here, at print
    time  -  never a value carried over from an earlier step, which could
    be stale by the time this, the LAST thing in the run, executes (a
    component could be published, or the server could die, in between).
    The one exception is the Auto-recovery line - see _auto_recovery_
    line()'s own docstring note on why "what happened this run" cannot be
    re-derived fresh.
    """
    lines = ["Conan environment summary"]

    # --- Cache (CONAN_HOME) ---
    # RD-03 (remove_develop_mode_plan.md): one cache, package mode only -
    # WP-23's develop/package split is gone, so this reports the single
    # real, fixed path (never `conan config home`'s live answer, which by
    # this point in the process could reflect an explicit override).
    default_home = _standard_conan_home()
    explicit = os.environ.get("CONAN_HOME")
    lines.append(f"  Cache:                     {default_home}")
    if explicit and Path(explicit).resolve() != default_home.resolve():
        lines.append(f"  Cache, explicit override:  {explicit}   "
                     f"(CONAN_HOME set in this shell - always respected, never overridden)")

    # --- Local server (adas-local) ---
    # NS-28: with remotes off the remote is not used, so it is not probed
    # (same rule as NS-23: report the run's own decision, no second probe).
    url = read_team_server_url()
    if getattr(ctx, "remotes_enabled", True) is False:
        lines.append("  Local server (adas-local): not used (remotes off - "
                     f"{getattr(ctx, 'remotes_reason', 'remotes are off')})")
    elif url is None:
        lines.append(f"  Local server (adas-local): not configured "
                      f"({TEAM_SERVER_FILE.relative_to(ROOT)} is a placeholder)")
    else:
        parsed = urlparse(url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 9300
        reachable = _port_reachable(port, host=host)
        users_result = run(["conan", "remote", "list-users", "--format=json"],
                            capture=True, check=False)
        logged_in = False
        if users_result.returncode == 0:
            try:
                for entry in json.loads(users_result.stdout or "[]"):
                    if entry.get("name") == "adas-local" and entry.get("authenticated"):
                        logged_in = True
                        break
            except (ValueError, TypeError):
                pass
        status_bits = "reachable" if reachable else "NOT reachable"
        if reachable and logged_in:
            status_bits += ", logged in"
        lines.append(f"  Local server (adas-local): {url}  [{status_bits}]")

    # --- Auto-recovery ---
    lines.append(f"  Auto-recovery:             {_auto_recovery_line(ctx)}")

    # --- Packages resolvable ---
    # NS-23 (cache_first_no_server_plan.md, redo of CE-37): this used to
    # independently re-derive resolvability here, under whatever CONAN_HOME/
    # editables state happened to be active by the time the summary
    # printed - a second, differently-shadowed code path from the one
    # ensure_resolution_complete() had already run moments earlier in this
    # same call to main(), so the two could (and did, live) disagree:
    # "[OK] ... All required adas-* refs are resolvable" immediately
    # followed by "Packages resolvable: 2/7 - MISSING: ...". Now: purely
    # reports what that step already computed and stashed on
    # ctx.resolution_summary - never a second derivation.
    resolution_summary = getattr(ctx, "resolution_summary", None)
    if resolution_summary is not None:
        lines.append(f"  Packages resolvable:       {resolution_summary}")
    elif getattr(ctx, "role", "dev") != "dev":
        lines.append("  Packages resolvable:       not verified this run "
                     "(ensure_resolution_complete only runs for --role dev)")
    elif getattr(ctx, "dry_run", False):
        lines.append("  Packages resolvable:       not verified this run (--dry-run)")
    else:
        # ensure_resolution_complete() failing raises StepFailed, which
        # step() turns into sys.exit(1) before this function is ever
        # reached - so role == "dev", not --dry-run, and still unset
        # should not happen in practice. Reported honestly rather than
        # silently, in case that assumption is ever wrong.
        lines.append("  Packages resolvable:       not verified this run (unknown reason)")

    print()
    print("\n".join(lines))


def bootstrap_team_server(ctx):
    """--role server: get conan_server itself installed and initialised on
    THIS machine so it can act as the team's shared remote. Network-facing
    steps that need Administrator elevation (firewall rule), or that touch
    state that doesn't exist yet (first-time --migrate init, editing
    server.conf), are printed, never executed  -  exactly the kind of
    hard-to-reverse, shared-state change this script does not take
    unattended. ensure_server_running() (conan_environment_plan.md section
    2.1) is deliberately NOT called from this flow, unlike --role dev's own
    step  -  it needs a server.conf that doesn't exist until step 1 below
    has been run by hand at least once.
    """
    banner("Bootstrapping a team Conan server on this machine")
    try:
        import conans.server  # noqa: F401
        print("[SKIP] conan_server already installed")
    except ImportError:
        if ctx.dry_run:
            print("[dry-run] would run: pip install --user conan_server")
        else:
            run([sys.executable, "-m", "pip", "install", "--user", "conan_server"])
            print("[OK] conan_server installed")

    server_dir = os.environ.get("ADAS_CONAN_SERVER_DIR", r"C:\ws\conan_server_data")
    print(f"""
Next steps (manual  -  these touch shared/system state on purpose):

1. First-time init:
     conan_server --server_dir "{server_dir}" --migrate

2. Edit {server_dir}\\server.conf:
     [server]
     port: 9300
     host_name: <this machine's real LAN/VPN IP on the corporate network>
     [write_permissions]
     */*@*/*: demo
   (Full reference: docs/conan_server_remote.md section 2.)

3. Run it (foreground, to confirm it starts):
     python scripts/conan_server_guard.py conan_server --server_dir "{server_dir}"

4. Allow it through the firewall (Administrator PowerShell):
     netsh advfirewall firewall add rule name="conan_server_9300" dir=in action=allow protocol=TCP localport=9300

5. Ongoing persistence: once this is running, ensure_server_running()
   (conan_environment_plan.md section 2.1) will relaunch it on demand
   any time it's found down  -  but only from something that actually
   calls it, and this bootstrap flow doesn't (see its own docstring). If
   this machine also runs `setup.bat` (the default --role dev) for its
   own development work, that's covered for free from then on. A
   machine that is ONLY a server host has no automatic recovery yet  -
   wiring ensure_server_running() into scripts/build.py too is a
   natural, separate follow-up (see the plan's section 3), not this
   flow's job.

6. Publish adas-interfaces / adas-mathlib / adas-shared-config to it -
   docs/conan_server_remote.md section 3.

7. Put the real URL (http://<ip>:9300) into scripts/team_conan_server.txt so
   every teammate's plain `setup.bat` picks it up automatically.
""")


def ask_yes_no(prompt):
    try:
        return input(f"{prompt} [Y/N]: ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Offline mode (OF-04, offline_setup_plan.md D5) - a corporate PC whose TLS
# interception breaks pip and conancenter: nothing below makes a network call.
# ---------------------------------------------------------------------------


def _bundle_layout():
    """D14: adas_build_tools.bundle_layout (standard library only, so this
    works before PyYAML is installed) from this checkout's modules/toolchain
    -- the one definition of the host -> platform mapping and the per-
    platform bundle subfolder."""
    # Code, not checkout data: always this script's own checkout (tests
    # re-point ROOT at a scratch tree).
    tc = Path(__file__).resolve().parent.parent / "modules" / "toolchain"
    if not (tc / "adas_build_tools" / "bundle_layout.py").is_file():
        raise StepFailed("modules/toolchain is not checked out; it defines where this "
                         "host's offline bundle lives (D14).",
                         "check the toolchain submodule out, then re-run setup.",
                         "git submodule update --init modules/toolchain")
    sys.path.insert(0, str(tc))
    try:
        from adas_build_tools import bundle_layout
    finally:
        sys.path.pop(0)
    return bundle_layout


def complete_prepared_python_envs(ctx):
    """PT-38: `--prepare <m>` just put <m>'s first-party packages into the
    cache, so it finishes <m>'s own Python tool environments that were
    WAITING for them (setup runs before --prepare on a fresh machine). This
    is what makes the `Run: ... --prepare <m> ...` line setup prints for a
    waiting environment actually complete it. Only <m>'s envs, only when
    the prepared platform is this host's (the packages are host binaries)."""
    if ctx.platform != offline_platform():
        print(f"{ctx.platform} is not this host's platform ({offline_platform()}) - "
              "its Python tool environments are completed on that host.")
        return "skip"
    ctx.only_components = {ctx.prepare}
    try:
        return ensure_python_tool_envs(ctx)
    finally:
        ctx.only_components = None


def offline_platform():
    """The bundle platform this machine builds (matches make_offline_bundle.py
    --platform and scripts/build.py's own native default). D14: from the one
    mapping in adas_build_tools.bundle_layout."""
    return _bundle_layout().host_bundle_platform()


def host_bundle_dir(folder):
    """D14/PT-17: this host's bundle subfolder of `folder` (the top
    misc/offline_bundle/ or an explicit platform subfolder), or None when
    absent. A flat pre-D14 bundle is refused, never used."""
    layout = _bundle_layout()
    sub, flat = layout.resolve_bundle_dir(folder)
    if flat is not None:
        raise StepFailed(
            f"{flat} holds an offline bundle in the old flat layout; bundles now live in "
            f"one subfolder per platform ({Path(flat) / layout.host_bundle_platform()}).",
            "move it into its platform subfolder, then re-run setup.",
            layout.flat_layout_move_command(flat))
    return sub


def load_offline_bundle(bundle_dir):
    """OF-04: (manifest dict, archive Path, wheels Path) of `bundle_dir`, or a
    named StepFailed if it is not a bundle made by make_offline_bundle.py.
    D14: `bundle_dir` may be the top folder; this host's subfolder is used."""
    import make_offline_bundle as mob
    bundle = host_bundle_dir(bundle_dir) or Path(bundle_dir)
    manifest_file = bundle / "bundle_manifest.txt"
    if not manifest_file.is_file():
        raise StepFailed(f"{bundle} has no bundle_manifest.txt.",
                         "Pass the folder written by scripts/make_offline_bundle.py.")
    archives = sorted(bundle.glob("adas_offline_*.tgz"))
    if len(archives) != 1:
        raise StepFailed(f"expected exactly one adas_offline_*.tgz in {bundle}, found {len(archives)}.",
                         "Keep one bundle archive per folder.")
    if not (bundle / "wheels").is_dir():
        raise StepFailed(f"{bundle} has no wheels/ folder.",
                         "Re-make the bundle without --no-wheels.")
    return mob.parse_manifest(manifest_file.read_text(encoding="utf-8")), archives[0], bundle / "wheels"


def check_offline_bundle(ctx):
    """OF-04: refuse a bundle made for another platform."""
    manifest, _, _ = load_offline_bundle(ctx.offline)
    here = offline_platform()
    if manifest["platform"] != here:
        raise StepFailed(
            f"the bundle is for platform {manifest['platform']!r} but this machine builds {here!r}.",
            f"Ask for a bundle made with `make_offline_bundle.py --platform {here}`.")
    print(f"Bundle: platform {manifest['platform']}, made {manifest['date']} at "
          f"{(manifest['source_commit'] or 'unknown')[:8]}, {len(manifest['refs'])} recipes, "
          f"{len(manifest['wheels'])} wheels.")


def install_offline_wheels(ctx):
    """OF-04 / D5: conan + PyYAML from the bundle's wheels, `pip --no-index`."""
    import make_offline_bundle as mob
    _, _, wheels = load_offline_bundle(ctx.offline)
    if on_path("conan") and importlib.util.find_spec("yaml") is not None:
        return "skip"
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)  # pip refuses --user in a venv
    cmd = [sys.executable, "-m", "pip", "install", *([] if in_venv else ["--user"]), "--no-index",
           "--find-links", str(wheels), *mob.WHEEL_REQUIREMENTS]
    if ctx.dry_run:
        print(f"[dry-run] would run: {' '.join(cmd)}")
        return "skip"
    try:
        run(cmd)
    except subprocess.CalledProcessError:
        raise StepFailed("pip install --no-index from the bundle's wheels failed.",
                         "Check the bundle was made with the same Python version as this machine.")
    global check_conan_resolution
    importlib.invalidate_caches()
    if not in_venv:
        site.addsitedir(site.getusersitepackages())  # a first-ever --user install creates it
    import check_conan_resolution  # noqa: F811 - PyYAML is importable now
    if in_venv:  # the venv's own Scripts/bin holds conan; make it visible to this run
        os.environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")
    if not on_path("conan"):
        if os.name == "nt" and not in_venv:
            persist_user_scripts_dir_to_path()
        raise StepFailed("Conan installed but its Scripts directory isn't on PATH in THIS terminal yet.",
                         "Open a NEW terminal and re-run this script.")


def _relpath_label(path, root=None):
    """`path` relative to `root` (default ROOT) for a print/error message,
    or `path` itself if it isn't actually under `root` - a test's patched-
    in path being the normal reason, same defensive pattern conan_home_
    resolution.remotes_enabled() already uses for TEAM_SERVER_FILE."""
    root = ROOT if root is None else root
    try:
        return path.relative_to(root)
    except ValueError:
        return path


def _ref_cached(ref):
    """WP-2/NS-11 (cache_first_no_server_plan.md): True iff `ref` (bare
    `name/version`) has a recipe in THIS machine's own Conan cache -
    `conan list <ref> --format=json`, no `-r` (defaults to the local cache
    under the fixed key "Local Cache", the same convention check_conan_
    resolution.py's own cache-first check uses, NS-03).

    Deliberately NOT this file's own `run(..., capture=True)` (real bug,
    found running this for real, 2026-09-23): that helper merges stderr
    into stdout (`stderr=subprocess.STDOUT`), and `conan list --format=
    json` prints its informational "Found N pkg/version recipes..." line
    to STDERR - merged in, it lands ahead of the JSON and breaks
    `json.loads()` every time, silently (caught by the `except` below,
    so this always returned False). subprocess.run() called directly
    here, stdout/stderr genuinely separate, matches check_conan_
    resolution.py's own `_run()` for exactly this reason."""
    try:
        proc = subprocess.run(["conan", "list", ref, "--format=json"],
                              capture_output=True, text=True, check=False)
    except OSError:
        return False
    if proc.returncode != 0:
        return False
    try:
        data = json.loads(proc.stdout)
    except (ValueError, TypeError):
        return False
    cache_data = data.get("Local Cache")
    return isinstance(cache_data, dict) and ref in cache_data


def restore_missing_refs_from_bundle(bundle_dir, needed_refs):
    """WP-3/NS-04 (cache_first_no_server_plan.md D2): restore whatever this
    machine's own Conan cache is missing, from `bundle_dir` (a folder
    written by scripts/make_offline_bundle.py) - used automatically
    wherever this is called, no `--offline` flag required. Returns the
    subset of considered refs actually restored; prints one line per ref
    either way. A wrong-platform bundle is refused outright (existing
    OF-04 contract, unchanged). A ref that is in neither this cache nor
    the bundle's own manifest is reported, never fatal by itself - the
    caller decides whether that leftover blocks the run.

    NS-41: `needed_refs` (the caller's direct-requires derivation) is only
    a FLOOR, never the ceiling, on what gets considered - unioned here
    with the bundle's own manifest `refs` list, because `conan cache
    restore <archive>` below is a WHOLE-ARCHIVE unpack: every ref the
    bundle carries lands in the cache in one call, whether or not the
    caller thought to ask about it. Before this fix the decision (and the
    report) used `needed_refs` alone, so a machine with every DIRECT ref
    cached but a TRANSITIVE one missing (zlib behind protobuf) never
    restored, and never even mentioned zlib - the restore ran anyway (once
    triggered by something else needing it) and silently fixed the gap,
    which is how the previous accidental PASS hid for four runs. Deriving
    the candidate set from the manifest itself, not from a caller's guess
    at what's needed, is what makes the decision match what the archive
    can actually supply."""
    manifest, archive, _ = load_offline_bundle(bundle_dir)
    here = offline_platform()
    if manifest["platform"] != here:
        raise StepFailed(
            f"the bundle is for platform {manifest['platform']!r} but this machine builds {here!r}.",
            f"Ask for a bundle made with `make_offline_bundle.py --platform {here}`.")

    candidates = sorted(set(needed_refs) | set(manifest["refs"]))
    to_restore = []
    for ref in candidates:
        if _ref_cached(ref):
            print(f"{ref}: already cached - bundle restore skipped.")
        elif ref not in manifest["refs"]:
            print(f"{ref}: not in {bundle_dir}'s bundle_manifest.txt - reported, "
                  "not restored (the bundle may predate this pin).")
        else:
            to_restore.append(ref)

    restored = set()
    if to_restore:
        run(["conan", "cache", "restore", str(archive)])
        for ref in to_restore:
            if _ref_cached(ref):
                restored.add(ref)
                print(f"{ref}: restored from the bundle.")
            else:
                print(f"{ref}: still not in the cache after restoring the "
                      "bundle (unexpected - its own manifest listed it).")
    return restored


def _prepare_dependency_closure(module, project):
    """STEP 1 (cache_first_no_server_plan.md, NS-11 remainder): `module`'s
    first-party dependency closure, in dependency-first build order -
    reuses build.py's own package_to_module_map()/forward_closure()/
    topo_sort() (imported as `adas_build`, never re-walked here) so this
    never drifts from the one graph-walk build.py already proves correct
    (AB-01..AB-07). `module` itself is excluded from the result."""
    pkg_map = adas_build.package_to_module_map()
    closure = adas_build.forward_closure({module}, project, pkg_map) - {module}
    return adas_build.topo_sort(closure, project, pkg_map)


def refresh_root_locks(ctx, created):
    """NS-63 (cache_first_no_server_plan.md §5, LK-D3): `--prepare` is the
    deliberate act of putting a checkout's first-party packages into the cache,
    so it is one of the only two things (the other is `--update-lock`) allowed
    to move a lock: the root locks of this (module, target, platform, project)
    key - the module's own, which root solo builds use, and every aggregate
    lock - adopt the revision of each package created just now, and the old ->
    new revision is printed. A lock that does not exist yet is left for the
    first build to create. A standalone clone elsewhere keeps its own lock, so
    it keeps the revision it was built with and is told about the newer one."""
    lockfiles = load_lockfiles()
    if lockfiles is None:
        return
    cached = lockfiles.cache_revisions()
    if created:
        _adopt_created_revisions(ctx, created, lockfiles, cached)
    _refresh_stale_module_locks(ctx, lockfiles, cached)


def _refresh_stale_module_locks(ctx, lockfiles, cached):
    """LK-D10: every existing lock of the prepared module - any target, platform
    or project, and its aggregates - adopts the newer cached revision of each
    first-party pin, so `--prepare` leaves no stale lock behind. Third-party
    pins are never touched."""
    if cached is None:
        return
    for path in lockfiles.module_lock_paths(ROOT, ctx.prepare):
        try:
            moved = lockfiles.refresh_stale_first_party(path, cached)
        except (OSError, ValueError, lockfiles.LockError) as exc:
            print(f"  {path}: could not be refreshed ({exc}); "
                  "re-resolve it with the build's --update-lock.")
            continue
        for ref, old, new in moved:
            print(f"  {lockfiles.refresh_message(path.stem, ref, old, new)}")


def _adopt_created_revisions(ctx, created, lockfiles, cached):
    refs = [f"{adas_build.module_package_name(m)}/{adas_build.module_version(m)}" for m in created]
    newest = lockfiles.newest_revisions(refs, cached)
    if not newest:
        return
    home = active_conan_home()
    for ref, (rrev, _ts) in newest.items():
        lockfiles.record_origin(home, ref, rrev, ROOT)
    paths = lockfiles.root_lock_paths(ROOT, ctx.prepare, ctx.target, ctx.platform, ctx.project)
    if not paths:
        print(f"\nNo lock exists yet for {ctx.prepare} -t {ctx.target} -p {ctx.platform} "
              f"-P {ctx.project}; the first build creates it.")
        return
    print("\nLocks:")
    for path in paths:
        try:
            moved = lockfiles.refresh_pins(path, newest)
        except (OSError, ValueError) as exc:
            print(f"  {path}: could not be refreshed ({exc}); "
                  "re-resolve it with the build's --update-lock.")
            continue
        shown = os.path.relpath(path, ROOT)
        if not moved:
            print(f"  {shown}: already current")
        for ref, old, new in moved:
            print(f"  {shown}: {lockfiles.format_change(ref, old, new)}")


def prepare_first_party_deps(ctx):
    """`setup.py --prepare <module> -t <target> -p <platform> [-P <project>]`
    (D4b, NS-11's remainder - cache_first_no_server_plan.md STEP 1): the
    supported way to compile a module's first-party C++ dependencies into
    this machine's Conan cache via `conan create`, in dependency order
    (interfaces before sim before viz, etc. - _prepare_dependency_closure()).
    Nothing is compiled without this flag - an ordinary `setup.bat` run
    never calls this function (D4b: "compiling is asked for").

    Idempotent: a dependency is skipped only when (a) a binary matching the
    requested platform's pinned profile settings is cached AND (b) its
    recorded source fingerprint equals the checkout's now (NS-28); a
    cached binary with no record, or a moved source, is rebuilt and
    re-recorded. Check (a) is (check_conan_resolution._cache_matches_profile() -
    the SAME cache-first "can this machine resolve it" check the main
    "Conan package resolution completeness" step already uses, reused
    rather than a second, divergent notion of "cached"). NOTE this checks
    Conan `settings` only, not the `project=` option - the same limitation
    _cache_matches_profile() already has everywhere else it's used in this
    repo; a module built once for one project is reported cached for a
    different project too. Documented here rather than silently differing
    from the rest of the codebase's own convention.

    Every `conan create` carries `-nr`/`--no-remote`, unconditionally,
    matching prepare_conan_cache()'s own real-bug fix (2026-09-23): this
    step's whole job is cache-fill from the checkout, never a remote - so
    it makes zero remote calls whether remotes are on or off."""
    if adas_build.load_module_conf(ctx.prepare) is None:
        raise StepFailed(
            f"'{ctx.prepare}' is not a buildable module - no modules/{ctx.prepare}/"
            "conf/build.yml.",
            "Check the module name against `python scripts/build.py config`.")
    if not adas_build.module_declares(ctx.prepare, ctx.project, ctx.target, ctx.platform):
        raise StepFailed(
            f"'{ctx.prepare}' does not declare target={ctx.target} platform={ctx.platform} "
            f"for project={ctx.project} in its own conf/build.yml.",
            "Check `python scripts/build.py config` for what this module actually builds.")

    # W3 (partial_clone_correctness_plan.md): here the closure is the work
    # list, so a dependency that is not checked out is initialised - never
    # skipped into "nothing to prepare". Repeated, because a newly checked-out
    # module can declare more dependencies.
    while True:
        absent = adas_build.absent_first_party_refs(
            adas_build.forward_closure({ctx.prepare}, ctx.project,
                                       adas_build.package_to_module_map()), ctx.project)
        if not absent:
            break
        try:
            initialised = init_submodules_for(sorted(absent), root=ROOT, dry_run=ctx.dry_run)
        except SubmoduleInitError as exc:
            raise StepFailed(exc.lines[0].removeprefix("ERROR: "),
                             "check the dependencies out, then re-run --prepare",
                             exc.lines[-1].removeprefix("Run: "))
        if ctx.dry_run:
            print("(more dependencies may appear once these are checked out)")
            return "skip"
        if not initialised:  # no progress: never loop on a graph git cannot change
            raise StepFailed(f"{', '.join(sorted(absent))} still not checked out after "
                             "git submodule update.",
                             "check the dependencies out by hand, then re-run --prepare",
                             "git submodule update --init " + " ".join(
                                 f"modules/{m}" for m in sorted(absent)))

    ordered = _prepare_dependency_closure(ctx.prepare, ctx.project)
    if not ordered:
        print(f"{ctx.prepare} has no first-party dependencies for project={ctx.project} - "
              "nothing to prepare.")
        return "skip"

    if ctx.dry_run:
        for mod in ordered:
            pkg = adas_build.module_package_name(mod) or mod
            print(f"[dry-run] would check the cache for {pkg} against the {ctx.platform} "
                  f"profile; `conan create modules/{mod}` if missing")
        return "skip"

    profile_settings = check_conan_resolution.pinned_profile_settings(ctx.platform)
    build_type = "Debug" if ctx.platform.endswith("_debug") else "Release"
    profile_flags = profile_args(ctx.platform)

    created = []
    skipped = []
    failed = []
    for mod in ordered:
        pkg_name = adas_build.module_package_name(mod)
        version = adas_build.module_version(mod)
        if not pkg_name or not version:
            print(f"{mod}: could not determine its Conan package name/version - skipping.")
            failed.append(mod)
            continue
        ref = f"{pkg_name}/{version}"
        mod_dir = ROOT / "modules" / mod
        cached = (profile_settings is not None
                  and check_conan_resolution._cache_matches_profile(ref, profile_settings))
        if cached:
            # NS-28: "a binary exists" is not "this binary is from this source"
            # - build.py's stale_cache_refs() asks the second question, so the
            # skip must ask it too or the refusal's own advice is a dead end.
            entry = (read_prepared_modules(ROOT) or {}).get(mod)
            if entry is None:
                print(f"{mod} ({ref}): cached for {ctx.platform} but no freshness record - "
                      "rebuilding once so it can be trusted.")
            elif record_is_outdated_format(entry):
                # NS-52: an older fingerprint format cannot be compared - say
                # so, rather than claiming the developer's source changed.
                print(f"{mod} ({ref}): cached for {ctx.platform} but its freshness record "
                      "is in an older fingerprint format (NS-51) - rebuilding once to "
                      "re-record it.")
            else:
                fp = compute_module_fingerprint(mod_dir)
                if fp["git"] == entry.get("git") and fp["dirty"] == entry.get("dirty"):
                    head = (fp["git"] or "")[:8]
                    print(f"{mod} ({ref}): already cached and unchanged since it was built "
                          f"(HEAD {head}) - conan create skipped.")
                    skipped.append(mod)
                    continue
                print(f"{mod} ({ref}): cached for {ctx.platform} but its source changed since "
                      f"it was built (HEAD {(entry.get('git') or '')[:8]} -> "
                      f"{(fp['git'] or '')[:8]}) - rebuilding.")
        else:
            print(f"{mod} ({ref}): not cached for {ctx.platform} - running "
                  f"conan create modules/{mod} (project={ctx.project}) ...")
        # A (2026-09-25): the create-and-record pair moved into
        # conan_home_resolution.create_and_record_module() so build.py can call
        # the SAME implementation for a pure-data module the user explicitly
        # named (D4). Behaviour here is unchanged: same argv, same post-create
        # cache verification, and the record (NS-05a/D4a) is still written only
        # on success and never on an "already cached" skip above.
        if create_and_record_module(
                mod, mod_dir, ref, ctx.project, build_type, profile_flags, ROOT,
                target=ctx.target, platform=ctx.platform,
                verify_cached=(None if profile_settings is None else
                               (lambda r=ref: check_conan_resolution._cache_matches_profile(
                                   r, profile_settings))),
                runner=lambda cmd: run(cmd, capture=True, check=False),
                # Resolved at call time from this module's globals, so the
                # existing tests that patch setup.record_prepared_module keep
                # intercepting it after the extraction above.
                recorder=lambda *a, **kw: record_prepared_module(*a, **kw)):
            created.append(mod)
        else:
            failed.append(mod)

    if failed:
        raise StepFailed(
            f"failed to prepare the following first-party dependenc"
            f"{'y' if len(failed) == 1 else 'ies'} of {ctx.prepare}: {', '.join(failed)}.",
            "Check the `conan create` output above for the real error in that "
            "module's own checkout, then re-run --prepare.")

    if created:
        print(f"\nCreated: {', '.join(created)}")
    if skipped:
        print(f"Already cached: {', '.join(skipped)}")
    refresh_root_locks(ctx, created)
    print(f"{ctx.prepare}'s first-party dependency closure is ready in the Conan cache "
          f"for project={ctx.project}, platform={ctx.platform}.")


def prepare_conan_cache(ctx):
    """WP-2/NS-11 (cache_first_no_server_plan.md D2/D4b) - setup OWNS
    preparation: fills THIS machine's own Conan cache with exactly what a
    fresh machine needs before anything else is resolvable, in order:
      1. `conan export modules/toolchain` - only if the pinned adas-
         toolchain ref isn't already cached (a plain recipe copy: no
         network, no compiler).
      2. `conan create modules/toolchain/conan_package` - only if the
         pinned adas-build-tools ref isn't already cached (D7: this one
         DOES build something - a pure-Python wheel, made offline-safe by
         NS-13).
      3. Restore anything still missing from misc/offline_bundle/ (WP-3/
         NS-04), automatically, when that folder exists.
      4. Create conan_workarea/ if it doesn't exist yet.
    Nothing else is compiled here (D4b) - a first-party module's own
    dependencies are `--prepare <module> -t <target> -p <platform>`'s job,
    asked for explicitly, never a side effect of an ordinary run.

    Every `conan export`/`conan create` below passes `-nr`/`--no-remote`
    (real bug, found running this for real on this machine, 2026-09-23):
    this step's whole job is cache-fill from the checkout (D2), never a
    remote - but Conan itself still queries every currently ENABLED
    remote during `--build=missing` graph computation regardless of what
    this script's own remotes_enabled() decided, if that remote happens
    to already be registered on the machine (as adas-local commonly is,
    independent of team_conan_server.txt's placeholder/URL content).
    Without `-nr`, a remotes-off run with a pre-existing, expired-login
    adas-local registration failed right here with a raw Conan auth
    error instead of ever reaching the cache/bundle/local-source path
    this step exists to provide.

    A pinned ref still missing after 1-3 is offered one more explicit,
    local-source build attempt gated by `--build-missing-from-source`
    (default off - a genuinely offline default run should never guess at
    starting a build nobody asked for); still missing after that (or with
    the flag left off) is a StepFailed naming the ref and setup.bat."""
    toolchain_refs = sorted(check_conan_resolution.discover_python_requires_refs())
    build_tools_refs = sorted(check_conan_resolution.discover_build_tools_refs())
    toolchain_dir = ROOT / "modules" / "toolchain"
    build_tools_pkg_dir = toolchain_dir / "conan_package"
    # D14: this host's subfolder only (a flat old-layout bundle is refused).
    bundle_dir = host_bundle_dir(DEFAULT_OFFLINE_BUNDLE_DIR) \
        or DEFAULT_OFFLINE_BUNDLE_DIR / offline_platform()

    if ctx.dry_run:
        for ref in toolchain_refs:
            print(f"[dry-run] would check the cache for {ref}; "
                  f"`conan export {toolchain_dir}` if missing")
        for ref in build_tools_refs:
            print(f"[dry-run] would check the cache for {ref}; "
                  f"`conan create {build_tools_pkg_dir}` if missing")
        if bundle_dir.is_dir():
            print(f"[dry-run] would restore any still-missing ref(s) from {bundle_dir}")
        else:
            print(f"[dry-run] {bundle_dir} not present - nothing to restore from")
        print("[dry-run] would create conan_workarea/ if absent")
        return "skip"

    still_missing = []

    for ref in toolchain_refs:
        if _ref_cached(ref):
            print(f"{ref}: already cached - conan export skipped.")
            continue
        if not (toolchain_dir / "conanfile.py").is_file():
            print(f"{ref}: not cached, and modules/toolchain isn't checked out here.")
            still_missing.append(ref)
            continue
        print(f"{ref}: not cached - running conan export {toolchain_dir} ...")
        result = run(["conan", "export", str(toolchain_dir), "-nr"], capture=True, check=False)
        if result.returncode != 0 or not _ref_cached(ref):
            print(f"{ref}: conan export failed:\n{result.stdout}")
            still_missing.append(ref)
        else:
            # NS-05a (D4a, STEP 3): "the export/create in prepare_conan_cache"
            # is the other place this file exports a first-party module's
            # checkout into the cache - recorded the same way STEP 1's
            # --prepare does. toolchain has no target/platform/project axis
            # of its own (a python_requires recipe), so those fields stay None.
            record_prepared_module(ROOT, "toolchain", ref, str(toolchain_dir))

    for ref in build_tools_refs:
        if _ref_cached(ref):
            print(f"{ref}: already cached - conan create skipped.")
            continue
        if not (build_tools_pkg_dir / "conanfile.py").is_file():
            print(f"{ref}: not cached, and modules/toolchain isn't checked out here.")
            still_missing.append(ref)
            continue
        print(f"{ref}: not cached - running conan create {build_tools_pkg_dir} ...")
        result = run(["conan", "create", str(build_tools_pkg_dir), "--build=missing", "-nr"],
                     capture=True, check=False)
        if result.returncode != 0 or not _ref_cached(ref):
            print(f"{ref}: conan create failed:\n{result.stdout}")
            still_missing.append(ref)

    if bundle_dir.is_dir():
        # NS-40: restore EVERY ref this cache must hold that is absent - the
        # third-party libraries too, not only the pins that failed above.
        # Derived by make_offline_bundle.derive_pins(), the one derivation the
        # bundle itself is built from (never a hard-coded list).
        #
        # NS-41: `derive_pins()` only walks DIRECT requires:/tool_requires:
        # in conf/build.yml, so a transitive dep (zlib behind protobuf) was
        # never in `needed` and, worse, this call was previously GATED on
        # `needed` itself having an absent member - a machine with every
        # direct ref cached but a transitive one missing never even reached
        # `restore_missing_refs_from_bundle()`, though `conan cache restore`
        # is a whole-archive unpack that would have supplied it. The call is
        # now unconditional whenever a bundle is present; the function
        # itself derives what may need restoring from its own manifest's ref
        # list (what the archive can actually supply) unioned with `needed`,
        # intersected against what this cache lacks - not from `needed`
        # alone.
        import make_offline_bundle as mob
        needed = sorted(set(mob.all_pin_refs(mob.derive_pins(ROOT)))
                        | set(toolchain_refs) | set(build_tools_refs))
        restored = restore_missing_refs_from_bundle(bundle_dir, needed)
        still_missing = [ref for ref in still_missing if ref not in restored]
    else:
        print(f"{_relpath_label(bundle_dir)} not present - nothing to restore "
              "from (WP-3/NS-04: used automatically when present, no --offline "
              "flag needed).")

    if still_missing and getattr(ctx, "build_missing_from_source", False):
        retry_refs = list(still_missing)
        still_missing = []
        for ref in retry_refs:
            pkg_dir = toolchain_dir if ref in toolchain_refs else build_tools_pkg_dir
            cmd = (["conan", "export", str(toolchain_dir), "-nr"] if ref in toolchain_refs
                   else ["conan", "create", str(build_tools_pkg_dir), "--build=missing", "-nr"])
            print(f"{ref}: --build-missing-from-source - retrying from {pkg_dir} ...")
            result = run(cmd, capture=True, check=False)
            if result.returncode != 0 or not _ref_cached(ref):
                still_missing.append(ref)

    workarea = ROOT / "conan_workarea"
    if not workarea.is_dir():
        workarea.mkdir(parents=True, exist_ok=True)
        print(f"Created {_relpath_label(workarea)}/")

    if still_missing:
        raise StepFailed(
            "The following pinned ref(s) are neither in this machine's Conan "
            f"cache nor in {_relpath_label(bundle_dir)}: "
            f"{', '.join(sorted(set(still_missing)))}.",
            "Restore misc/offline_bundle/ from a machine that has them "
            "(scripts/make_offline_bundle.py), check out modules/toolchain "
            "so setup can export/build it locally, or re-run setup.bat with "
            "--build-missing-from-source once the source is here. Then "
            "re-run setup.bat.",
        )


def check_offline_pins(ctx):
    """OF-04: refuse a bundle that lacks a ref this checkout pins."""
    import make_offline_bundle as mob
    manifest, _, _ = load_offline_bundle(ctx.offline)
    missing = mob.missing_pins(manifest, mob.derive_pins(ROOT))
    if missing:
        raise StepFailed(
            f"the bundle is missing pinned ref(s) this checkout needs: {', '.join(missing)}.",
            "Ask for a fresh bundle (`scripts/make_offline_bundle.py`) made from this commit.")


def _remote_listing():
    """`conan remote list --format=json` -> [{"name":..,"disabled":bool}, ..].
    Separate and tiny so the step below is directly unit-testable, and so a
    malformed/failed listing degrades to "no remotes known" rather than
    raising - a machine with no remotes at all is exactly the state this
    tooling is trying to reach."""
    listing = run(["conan", "remote", "list", "--format=json"],
                  capture=True, check=False)
    if listing.returncode != 0:
        return []
    try:
        entries = json.loads(listing.stdout or "[]")
    except (ValueError, TypeError):
        return []
    if not isinstance(entries, list):
        return []
    entries = [e for e in entries if isinstance(e, dict) and e.get("name")]
    # Conan 2 prints `"enabled": bool`, not `"disabled"`; normalise to the
    # `disabled` key every caller below reads. Reading `disabled` directly
    # made a disabled remote report `STILL ENABLED` (found 2026-09-28).
    for e in entries:
        if "enabled" in e:
            e["disabled"] = not e["enabled"]
    return entries


# NS-45: the two remotes this tooling owns and may therefore re-enable. Any
# other remote a developer added by hand is disabled with remotes off (D1 -
# "no remotes at all") but never re-enabled by us: we did not create it, so
# we do not get to decide it should come back. NS-57: we do not stay silent
# about it either - the remotes-on summary names each one still disabled and
# the command that restores it, so RQ-3's "no leftover machine state" is
# answered for their remotes too, by telling rather than by acting.
_OWNED_REMOTES = ("conancenter", "adas-local")


def sync_remote_enablement(ctx):
    """NS-45 (cache_first_no_server_plan.md D1, RQ-1/RQ-5): `remotes off`
    must mean EVERY remote off, not just `adas-local`.

    The gap this closes, found by the user running a plain `setup.bat`
    against a genuinely empty cache (2026-09-25): `remotes_enabled()` only
    ever governed `adas-local`, but **Conan 2 re-creates `conancenter`,
    ENABLED, in every fresh home it makes**. So a cold machine with remotes
    off silently downloaded lz4/zlib/protobuf from the internet instead of
    from `misc/offline_bundle/` - and every cold-machine PASS to date ran on
    a machine WITH working internet, so nothing caught it. D1's own words are
    "no usable team server -> no remotes at all"; this function is that
    sentence, implemented.

    Symmetric on purpose. With remotes ON it RE-ENABLES the remotes this
    tooling owns (`_OWNED_REMOTES`), because a `disabled` flag written into
    remotes.json by an earlier remotes-off run is exactly the leftover
    machine state RQ-3 forbids: without this, one `setup.bat` with remotes
    off would silently leave every later `--remotes on` run unable to
    download, with nothing on the command line explaining why.

    NS-57 (RV-8): both branches re-query the listing after acting and print
    what Conan now reports, so the summary is an observation, not an
    assertion; and remotes-on names every still-disabled remote outside
    `_OWNED_REMOTES` with `conan remote enable <name>`, deliberately without
    running it.
    """
    remotes_on = getattr(ctx, "remotes_enabled", True)
    if ctx.dry_run:
        if remotes_on:
            print("[dry-run] would run: conan remote enable <each of "
                  f"{', '.join(_OWNED_REMOTES)} that exists and is disabled>")
        else:
            print('[dry-run] would run: conan remote disable "*"  '
                  "(D1: no team server -> no remotes at all, conancenter "
                  "included)")
        return "skip"

    entries = _remote_listing()
    names = [e["name"] for e in entries]

    if not remotes_on:
        if not names:
            print("No Conan remotes are defined  -  nothing to disable.")
            return
        enabled = [e["name"] for e in entries if not e.get("disabled")]
        if not enabled:
            print(f"Every Conan remote is already disabled ({', '.join(names)})"
                  "  -  nothing to do.")
            return "skip"
        run(["conan", "remote", "disable", "*"])
        after = _remote_listing()
        still_enabled = [e["name"] for e in after if not e.get("disabled")]
        print("Remotes off (D1)  -  disabled every Conan remote, so nothing in "
              "this run can reach the network. Conan now reports:")
        for e in after:
            print(f"  {e['name']}: {'disabled' if e.get('disabled') else 'STILL ENABLED'}")
        if still_enabled:
            print(f"WARNING: {', '.join(still_enabled)} still enabled after "
                  '`conan remote disable "*"` - this run may reach the network.')
        print("Third-party packages therefore come from the Conan cache or "
              "misc/offline_bundle/ only (RQ-1/RQ-6).")
        return

    re_enabled = [e["name"] for e in entries
                  if e["name"] in _OWNED_REMOTES and e.get("disabled")]
    if not re_enabled:
        print(f"Remotes on  -  {', '.join(names) or 'no remotes defined'}; "
              "none of this tooling's own remotes needed re-enabling.")
        _report_foreign_disabled(entries)
        return "skip"
    for name in re_enabled:
        run(["conan", "remote", "enable", name])
    after = _remote_listing()
    state = {e["name"]: e.get("disabled") for e in after}
    print("Remotes on  -  re-enabled what an earlier remotes-off run had "
          "disabled (RQ-3: no leftover machine state deciding this). Conan now reports:")
    for name in re_enabled:
        print(f"  {name}: {'STILL DISABLED' if state.get(name, True) else 'enabled'}")
    _report_foreign_disabled(after)


def _report_foreign_disabled(entries):
    """NS-57: name each disabled remote this tooling does not own, and the one
    command that restores it. Never runs that command (see _OWNED_REMOTES)."""
    foreign = sorted(e["name"] for e in entries
                     if e.get("disabled") and e["name"] not in _OWNED_REMOTES)
    if not foreign:
        return
    print(f"Still disabled, and not ours to re-enable: {', '.join(foreign)}. "
          "If an earlier remotes-off run disabled it and you want it back:")
    for name in foreign:
        print(f"  conan remote enable {name}")


def restore_offline_cache(ctx):
    """OF-04 / D5: `conan cache restore`, then leave EVERY remote disabled.
    adas-local stays DEFINED but disabled (OF-01/OF-02): the tooling looks for
    it by name and re-adds an absent one, and an enabled-but-unreachable
    remote makes `conan install --update` fatal."""
    manifest, archive, _ = load_offline_bundle(ctx.offline)
    if ctx.dry_run:
        print(f"[dry-run] would run: conan cache restore {archive}")
        print("[dry-run] would run: conan remote add adas-local <team server url>  (only if not defined)")
        print('[dry-run] would run: conan remote disable "*"')
        return "skip"
    try:
        run(["conan", "cache", "restore", str(archive)])
        # stderr is discarded, never merged: a stray warning on a real machine's
        # ambient Python (e.g. an outdated urllib3/chardet pairing) must never
        # land inside the stdout this parses as JSON (found live, WSL, 2026-10-04).
        listing = run(["conan", "remote", "list", "--format=json"], capture=True,
                      check=False, merge_stderr=False)
        try:
            names = [r.get("name") for r in json.loads(listing.stdout)]
        except (ValueError, AttributeError):
            names = []
        url = read_team_server_url()
        if "adas-local" not in names and url:
            run(["conan", "remote", "add", "adas-local", url])
        run(["conan", "remote", "disable", "*"])
    except subprocess.CalledProcessError:
        raise StepFailed("restoring the bundle into the Conan cache failed.",
                         "Re-run; if it persists, re-make the bundle.")
    print("Restored into the Conan cache (all remotes disabled):")
    for ref, rev in sorted(manifest["refs"].items()):
        print(f"  {ref}#{rev[:8]}")


# PT-07 (python_tool_envs_plan.md D8): the ONE component allowed to have
# its Python tool environments run from source rather than through its own
# launcher. modules/toolchain IS adas-build-tools, so it cannot pin a
# released copy of itself (no scripts/setup.py, no conf/build_tools.version);
# its envs run `python -m adas_build_tools.setup_cli` from its own checkout.
# Any OTHER launcher-less component declaring python_envs: is refused by
# name -- never run from source (PR-2: setup names no component otherwise).
_ENVS_FROM_SOURCE = "toolchain"


def _python_env_lines(output):
    """The per-env summary block a component's `--python-envs-only` run
    prints: every line after its '--- Python tool environments ---' header,
    minus its own [OK]/[FAIL] total (the root prints its own)."""
    lines, inside = [], False
    for line in output.splitlines():
        if line.startswith("--- Python tool environments ---"):
            inside = True
            continue
        if inside and line.strip() and not re.match(r"^\[(OK|FAIL)\]", line):
            lines.append(line)
    return lines


def ensure_python_tool_envs(ctx):
    """PT-07 (D8): for each discover_components() component that declares
    python_envs:, run that component's own setup with --python-envs-only --
    each component thereby uses the adas-build-tools version it pins, and
    root and standalone setup cannot disagree. Names no component (PR-2)
    except the one documented source-run exception above."""
    tc = ROOT / "modules" / "toolchain"
    if not (tc / "adas_build_tools" / "config.py").is_file():
        return "skip"
    sys.path.insert(0, str(tc))
    try:
        from adas_build_tools.config import PythonEnvsError, declared_python_envs
    finally:
        sys.path.pop(0)
    import yaml

    forwarded = ["--python-envs-only"]
    for name in getattr(ctx, "python_env", None) or []:
        forwarded += ["--python-env", name]
    remotes = getattr(ctx, "remotes", None)
    if getattr(ctx, "offline", None):
        remotes = "off"
    if remotes:
        forwarded += ["--remotes", remotes]

    declaring, failed = [], []
    only = getattr(ctx, "only_components", None)
    for comp in discover_components():
        if only is not None and comp not in only:
            continue
        comp_dir = ROOT / "modules" / comp
        try:
            conf = yaml.safe_load((comp_dir / "conf" / "build.yml").read_text(encoding="utf-8")) or {}
            envs = declared_python_envs(conf, component=comp)
        except (PythonEnvsError, yaml.YAMLError) as exc:
            raise StepFailed(str(exc), "correct the declaration in that conf/build.yml.")
        if envs:
            declaring.append((comp, comp_dir))

    known = {comp for comp, _ in declaring}
    stray = [n for n in getattr(ctx, "python_env", None) or []
             if n != "all" and n.split(":", 1)[0] not in known]
    if stray:
        raise StepFailed(f"--python-env {', '.join(stray)}: no checked-out component "
                         f"declaring python_envs: has that name (declaring: "
                         f"{', '.join(sorted(known)) or 'none'}).",
                         "name <component>:<env> as declared in its conf/build.yml, or `all`.")
    if not declaring:
        print("No checked-out component declares python_envs:.")
        return "skip"

    for comp, comp_dir in declaring:
        env = None
        if (comp_dir / "scripts" / "setup.py").is_file():
            cmd = [sys.executable, str(comp_dir / "scripts" / "setup.py"), *forwarded]
        elif comp == _ENVS_FROM_SOURCE:
            cmd = [sys.executable, "-m", "adas_build_tools.setup_cli", *forwarded]
            env = dict(os.environ, PYTHONPATH=str(comp_dir))
        else:
            print(f"{comp}: REFUSED -- declares python_envs: but has no scripts/setup.py "
                  f"launcher; only {_ENVS_FROM_SOURCE} may run its envs from source (D8).")
            failed.append(comp)
            continue
        if ctx.dry_run:
            print(f"[dry-run] would run (in modules/{comp}): {' '.join(cmd[1:])}")
            continue
        proc = subprocess.run(cmd, cwd=str(comp_dir), env=env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        lines = _python_env_lines(proc.stdout)
        for line in lines:
            print(line)
        if proc.returncode != 0:
            if not lines:  # failed before its env step: show why
                print((proc.stdout + proc.stderr).strip()[-1500:])
            failed.append(comp)
    if failed:
        raise StepFailed(f"Python tool environments refused for: {', '.join(failed)} "
                         f"(Reason / Fix / Run above).",
                         "follow the Run: line printed for each refused environment.")


def offline_setup(ctx):
    """OF-04: the whole `--offline <dir>` run - local checks and installs only."""
    # NS-33: this is the OFFLINE step list. The normal path's is the longer
    # one further down in main() (search "Linux system packages"); main()
    # hands off to this function when --offline is given, so exactly one of
    # the two runs. Deliberately two lists, not one - see NS-33 in
    # cache_first_no_server_plan.md.
    step(ctx, "Offline bundle (platform check)", check_offline_bundle)
    step(ctx, "Git", check_git)
    step(ctx, "Visual Studio / C++ toolchain", check_visual_studio)
    step(ctx, "Conan + PyYAML from the bundle's wheels (pip --no-index)", install_offline_wheels)
    step(ctx, "Offline bundle (pinned refs present)", check_offline_pins)
    step(ctx, "Conan default profile", ensure_conan_profile)
    step(ctx, "Conan non-interactive login (expired adas-local login fails by name)",
         ensure_non_interactive_login)
    step(ctx, "Restore the bundle into the Conan cache; disable every remote", restore_offline_cache)
    # PT-07: after the cache holds each component's pinned adas-build-tools.
    step(ctx, "Python tool environments", ensure_python_tool_envs)
    banner("Offline setup complete")
    print("Next:  python scripts/build.py df -t sil -p " + offline_platform())


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true",
                         help="Print what would happen; change nothing.")
    parser.add_argument("--yes", "-y", action="store_true",
                         help="Don't prompt before installing pip packages.")
    parser.add_argument("--no-submodules", action="store_true",
                         help="Skip git submodule update --init.")
    parser.add_argument("--offline", metavar="BUNDLE_DIR", nargs="?",
                         const=str(DEFAULT_OFFLINE_BUNDLE_DIR),
                         help="OF-04 (offline_setup_plan.md): set up from a bundle made by "
                              "scripts/make_offline_bundle.py - wheels via pip --no-index, "
                              "`conan cache restore`, every remote disabled; makes no network "
                              "call. For corporate PCs where TLS interception breaks pip and "
                              "conancenter. Only with --role dev. RD-13 (remove_develop_mode_"
                              f"plan.md): with no BUNDLE_DIR, looks in {DEFAULT_OFFLINE_BUNDLE_DIR} "
                              "(scripts/make_offline_bundle.py's own default --out).")
    parser.add_argument("--full-verify", action="store_true",
                         help="Also pre-build perception-core/df's Conan "
                              "dependencies at the end (conan install "
                              "--build=missing for each).")
    parser.add_argument("--clean-develop-leftovers", action="store_true",
                         help="D4/RD-04 (remove_develop_mode_plan.md): detect a leftover "
                              "develop CONAN_HOME directory and any of this checkout's own "
                              "editable registrations (develop or default cache); prints what "
                              "it would remove, removes only with --yes too. Standalone - "
                              "runs nothing else.")
    parser.add_argument("--role", choices=["dev", "server"], default="dev",
                         help="'dev' (default): set up this machine to build. "
                              "'server': bootstrap a shared team Conan server "
                              "instead (see setup.md section 5.4).")
    parser.add_argument("--mode", choices=["develop", "package"], default="package",
                         help="RD-03 (remove_develop_mode_plan.md): 'package' (default, and "
                              "the only supported mode) - every adas-* component this machine "
                              "needs resolves from adas-local (Cache or Download), never from "
                              "an editable registration. 'develop' is accepted only so it can "
                              "be refused with a clear message; it is retained as a choice, "
                              "kept only to give that refusal - never to succeed.")
    parser.add_argument("--remotes", choices=["on", "off"], default=None,
                         help="WP-1/NS-01 (cache_first_no_server_plan.md D1): override "
                              "scripts/team_conan_server.txt for this run only. Default: "
                              "decided by that file (placeholder -> off, a real URL -> on).")
    parser.add_argument("--python-env", action="append", default=[], metavar="<m>:<env>|all",
                         help="PT-07 (python_tool_envs_plan.md D7): also create this optional "
                              "Python tool environment (repeatable; `all` = every declared "
                              "one). Default environments are always created.")
    parser.add_argument("--build-missing-from-source", action="store_true",
                         help="WP-2/NS-11 (cache_first_no_server_plan.md D4b): if the "
                              "adas-toolchain/adas-build-tools pin is in neither this "
                              "machine's Conan cache nor misc/offline_bundle/, retry "
                              "building it from modules/toolchain's own checkout. Off by "
                              "default - a non-interactive run never starts a build "
                              "nobody asked for.")
    parser.add_argument("--prepare", metavar="MODULE",
                         help="STEP 1 (cache_first_no_server_plan.md, NS-11 remainder / D4b): "
                              "compile MODULE's first-party dependency closure into this "
                              "machine's Conan cache via `conan create`, in dependency order. "
                              "Needs -t/--target and -p/--platform. Nothing is compiled without "
                              "this flag - an ordinary setup run never does this. Standalone - "
                              "runs nothing else.")
    parser.add_argument("-t", "--target", default=None,
                         help="Target --prepare validates MODULE declares (e.g. sil). "
                              "Required with --prepare; ignored otherwise.")
    parser.add_argument("-p", "--platform", default=None,
                         help="Platform --prepare builds MODULE's dependencies for "
                              "(e.g. vs2026). Required with --prepare; ignored otherwise.")
    parser.add_argument("-P", "--project", default="base",
                         help="Project --prepare builds MODULE's dependencies for "
                              "(default: base). Used only with --prepare.")
    ctx = parser.parse_args()

    # WP-1/NS-01: computed and printed exactly once, here, before any step
    # runs - every later use of "is a team server configured" reads
    # ctx.remotes_enabled instead of re-deriving and re-printing it.
    cli_override = {"on": True, "off": False, None: None}[ctx.remotes]
    ctx.remotes_enabled, ctx.remotes_reason = remotes_enabled(cli_override=cli_override)
    print(f"Remotes: {'on' if ctx.remotes_enabled else 'off'} ({ctx.remotes_reason})")

    if ctx.mode == "develop":
        # RD-03 (remove_develop_mode_plan.md): develop mode is removed - was
        # a deprecation warning (RD-02), now a hard refusal.
        sys.exit("ERROR: --mode develop was removed. See remove_develop_mode_plan.md "
                  "(package mode is the only mode).")

    if ctx.clean_develop_leftovers:
        cleanup_develop_leftovers(ctx)
        return

    if ctx.prepare:
        if not ctx.target or not ctx.platform:
            sys.exit("ERROR: --prepare requires -t/--target and -p/--platform.")
        if adas_build is None:
            sys.exit("ERROR: --prepare needs PyYAML (build.py's own dependency) - "
                      f"run {setup_command()} --no-submodules once first (without "
                      "--no-submodules it checks out every module).")
        # W5: in a fresh clone, toolchain and the module being prepared for are
        # checked out first - the module's own conf/build.yml is what names the
        # dependencies to prepare. Its dependencies follow in
        # prepare_first_party_deps().
        try:
            initialised = init_toolchain_and([ctx.prepare], dry_run=ctx.dry_run)
        except StepFailed as exc:
            sys.exit(f"ERROR: {exc.reason}\nRun:    {exc.run}")
        if ctx.dry_run and initialised:
            print("(--dry-run: re-run without it to check these out and see the rest of the plan)")
            return
        adas_build.require_toolchain_checkout()
        banner(f"Preparing {ctx.prepare}'s first-party dependencies "
               f"(project={ctx.project} target={ctx.target} platform={ctx.platform})")
        if ctx.dry_run:
            print("(--dry-run: nothing on this machine will actually change)")
        step(ctx, f"First-party dependency closure for {ctx.prepare}", prepare_first_party_deps)
        step(ctx, f"Python tool environments for {ctx.prepare}", complete_prepared_python_envs)
        return

    banner("ADAS 1V Superproject  -  developer machine setup")
    if ctx.dry_run:
        print("(--dry-run: nothing on this machine will actually change)")

    if ctx.offline:
        if ctx.role == "server":
            sys.exit("ERROR: --offline is for --role dev only.")
        offline_setup(ctx)
        return

    step(ctx, "HTTPS trust (corporate TLS-interception compatibility)", ensure_https_trust)

    if ctx.role == "server":
        bootstrap_team_server(ctx)
        print_environment_summary(ctx)
        return

    # NS-33: this is the NORMAL step list (online, role dev). The --offline
    # run never reaches it - main() returns into offline_setup() above, which
    # has its own shorter list (search "Offline bundle (platform check)").
    # Deliberately two lists, not one: see NS-33 in cache_first_no_server_plan.md.
    step(ctx, "Git", check_git)
    step(ctx, "Linux system packages (libx11-dev/libgl1-mesa-dev/python3-venv)",
         check_linux_system_packages)
    step(ctx, "CMake", check_cmake)
    step(ctx, "Visual Studio / C++ toolchain", check_visual_studio)
    step(ctx, "Git submodules", init_submodules)
    step(ctx, "Conan 2.x", check_or_install_conan)
    # NS-45: runs as early as conan itself is guaranteed present, and BEFORE
    # any step that could resolve a package - with remotes off this is what
    # makes "no remotes at all" true of conancenter too, which Conan 2
    # re-creates enabled in every fresh home (D1, RQ-1/RQ-5).
    step(ctx, "Conan remotes match the switch (D1: remotes off = no remotes at all)",
         sync_remote_enablement)
    step(ctx, "Conan's own interpreter trusts HTTPS (CE-30)",
         ensure_conan_interpreter_trusts_https)
    step(ctx, "Conan default profile", ensure_conan_profile)
    step(ctx, "Conan non-interactive login (expired adas-local login fails by name)",
         ensure_non_interactive_login)
    step(ctx, "PyYAML", check_or_install_pyyaml)
    # WP-2/NS-11 (cache_first_no_server_plan.md D2/D4b): cache preparation
    # runs before anything that depends on adas-toolchain/adas-build-tools
    # being resolvable, and before the server on-demand step below - with
    # remotes off there is no server to depend on in the first place, and
    # with remotes on, a cache this step already filled means one less
    # thing the server ever needs to be asked for.
    step(ctx, "Cache preparation (adas-toolchain, adas-build-tools, offline bundle)",
         prepare_conan_cache)
    # Real gap found running this cold on Windows (2026-09-16): this step used
    # to run AFTER configure_conan_dependencies. On a machine where adas-local
    # is down and at least one of interfaces/mathlib/shared_config is pinned
    # to a bare Conan version (R-BUILD-2's Conan-based install mechanism,
    # e.g. mathlib's conf/build_tools.version), configure_conan_dependencies
    # needs adas-local reachable to resolve adas-build-tools and fails first
    # -- step() aborts the whole run right there, so ensure_server_running()
    # (the only thing that could have brought the server up) never executes.
    # Moved ahead of configure_conan_dependencies so the on-demand mechanism
    # gets a chance to run before anything that depends on the server it
    # starts. No dependency runs the other way: ensure_server_running() only
    # needs conan_server_guard (module-level import) and a socket/subprocess
    # call, never the Conan client itself.
    step(ctx, "Conan server on-demand persistence", ensure_server_running)
    step(ctx, "adas-interfaces / adas-mathlib / adas-shared-config", configure_conan_dependencies)
    step(ctx, "Conan package resolution completeness", ensure_resolution_complete)
    step(ctx, "Module/target/platform roster (read-only sanity check)", verify_roster)
    step(ctx, "Full dependency install (--full-verify)", full_verify)
    # PT-07 (python_tool_envs_plan.md D8): after "Cache preparation" -- each
    # component's launcher needs its pinned adas-build-tools in the cache --
    # and last, so a refused tool environment never blocks the C++ setup.
    step(ctx, "Python tool environments", ensure_python_tool_envs)

    banner("Setup complete")
    print("Next:")
    print("  python scripts/setup.py --prepare df -t sil -p vs2026 -P base   # compile df's first-party deps into the cache")
    print("  python scripts/build.py df -t sil -p vs2026")
    print("  python scripts/build.py df -t gtest -p vs2026")
    print("  python scripts/build.py config     # see every module x target x platform x project")
    print("Full reference: setup.md")

    print_environment_summary(ctx)


if __name__ == "__main__":
    main()
