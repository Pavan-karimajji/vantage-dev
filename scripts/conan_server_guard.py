"""
scripts/conan_server_guard.py

Bug #14 fix (plan.md item 13, docs/conan_server_remote.md §8): refuses to
start a second conan_server instance on a port that's already bound. On
Windows, two processes can bind the same TCP port simultaneously with zero
error or warning - confirmed live via netstat showing both PIDs LISTENING
on 0.0.0.0:9300 at once, with request routing between them uncharacterized.
The real risk: the ConanServerAdas Scheduled Task (docs/conan_server_remote.md
§7 item 4) already auto-starts conan_server on every login with no visible
"already running" indicator, so a manual start on top of it is easy to do
by accident.

Use exactly like conan_server itself, but pass the real conan_server.exe
path as the first argument - this wrapper reads the port out of
<server_dir>/server.conf (the same file conan_server itself reads it from;
port is not a CLI flag), checks it, then execs the real conan_server
unchanged:

    py scripts/conan_server_guard.py "<path to conan_server.exe>" --server_dir "C:\\ws\\conan_server_data"

To make the Scheduled Task use this guard instead of calling conan_server.exe
directly, redo the schtasks /create from docs/conan_server_remote.md §7 item 4
with this script prepended to the /tr command (Administrator PowerShell,
same as the original setup - not run automatically by this script/session).
"""

import configparser
import os
import socket
import subprocess
import sys

DEFAULT_PORT = 9300


def _port_in_use(port, host="0.0.0.0"):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def _extract_server_dir(args):
    for i, arg in enumerate(args):
        if arg == "--server_dir" and i + 1 < len(args):
            return args[i + 1]
    return None


def _read_configured_port(server_dir):
    """Reads [server]/port from <server_dir>/server.conf - the same file
    conan_server itself reads it from (port is not a CLI flag). Falls back
    to DEFAULT_PORT if the dir/file/key isn't there yet (first-ever run,
    before --migrate has created it)."""
    if not server_dir:
        return DEFAULT_PORT
    conf_path = os.path.join(server_dir, "server.conf")
    if not os.path.isfile(conf_path):
        return DEFAULT_PORT
    parser = configparser.ConfigParser()
    try:
        parser.read(conf_path, encoding="utf-8")
        return parser.getint("server", "port")
    except (configparser.Error, ValueError):
        return DEFAULT_PORT


def main():
    if len(sys.argv) < 2:
        print("usage: conan_server_guard.py <conan_server executable path> [conan_server args...]",
              file=sys.stderr)
        sys.exit(2)

    conan_server_exe, rest = sys.argv[1], sys.argv[2:]
    port = _read_configured_port(_extract_server_dir(rest))

    if _port_in_use(port):
        print(
            f"[conan_server_guard] Port {port} is already in use - another "
            f"conan_server instance appears to be running already (e.g. the "
            f"ConanServerAdas Scheduled Task, which auto-starts on every "
            f"login). Refusing to start a second one - two instances "
            f"binding the same port silently coexist on Windows with "
            f"uncharacterized request routing between them (see "
            f"docs/conan_server_remote.md §8, Bug #14).",
            file=sys.stderr,
        )
        sys.exit(1)

    sys.exit(subprocess.call([conan_server_exe] + rest))


if __name__ == "__main__":
    main()
