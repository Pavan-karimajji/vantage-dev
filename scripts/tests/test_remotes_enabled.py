"""
scripts/tests/test_remotes_enabled.py

WP-1/NS-01 (cache_first_no_server_plan.md D1) - conan_home_resolution.
remotes_enabled(): the one switch setup.py, build.py and
check_conan_resolution.py all ask instead of each re-deriving "are remotes
on" by hand. Covers the four-level precedence (env override > CLI override
> team_conan_server.txt > default-off), the "malformed/empty file is OFF,
never a URL" contract (read_team_server_url()'s own guarantee, exercised
here through remotes_enabled()), and the "each entry point prints the
state exactly once" property for all three importers.

Run:
    py -m unittest discover -s scripts/tests
    (from the superproject root)
"""
import contextlib
import io
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import conan_home_resolution as chr_  # noqa: E402 - path must be set up first
import setup  # noqa: E402
import build  # noqa: E402
import check_conan_resolution as ccr  # noqa: E402


class RemotesEnabledPrecedenceTests(unittest.TestCase):
    """The four precedence levels, isolated from the real
    scripts/team_conan_server.txt and the real environment - every case
    passes its own `env` dict and mocks read_team_server_url() so this
    suite never depends on what's actually in the file on disk right now."""

    def test_placeholder_file_is_off(self):
        with mock.patch.object(chr_, "read_team_server_url", return_value=None):
            enabled, reason = chr_.remotes_enabled(env={})
        self.assertFalse(enabled)
        self.assertIn("placeholder", reason)

    def test_real_url_is_on(self):
        with mock.patch.object(chr_, "read_team_server_url",
                                return_value="http://10.0.0.5:9300"):
            enabled, reason = chr_.remotes_enabled(env={})
        self.assertTrue(enabled)
        self.assertIn("10.0.0.5:9300", reason)

    def test_cli_override_beats_file_on(self):
        with mock.patch.object(chr_, "read_team_server_url", return_value=None):
            enabled, reason = chr_.remotes_enabled(cli_override=True, env={})
        self.assertTrue(enabled)
        self.assertIn("CLI override", reason)

    def test_cli_override_beats_file_off(self):
        with mock.patch.object(chr_, "read_team_server_url",
                                return_value="http://10.0.0.5:9300"):
            enabled, reason = chr_.remotes_enabled(cli_override=False, env={})
        self.assertFalse(enabled)
        self.assertIn("CLI override", reason)

    def test_env_override_beats_cli_and_file_on(self):
        env = {chr_.REMOTES_ENV_VAR: "on"}
        with mock.patch.object(chr_, "read_team_server_url", return_value=None):
            enabled, reason = chr_.remotes_enabled(cli_override=False, env=env)
        self.assertTrue(enabled)
        self.assertIn("env override", reason)

    def test_env_override_beats_cli_and_file_off(self):
        env = {chr_.REMOTES_ENV_VAR: "off"}
        with mock.patch.object(chr_, "read_team_server_url",
                                return_value="http://10.0.0.5:9300"):
            enabled, reason = chr_.remotes_enabled(cli_override=True, env=env)
        self.assertFalse(enabled)
        self.assertIn("env override", reason)

    def test_env_override_case_insensitive(self):
        env = {chr_.REMOTES_ENV_VAR: "ON"}
        with mock.patch.object(chr_, "read_team_server_url", return_value=None):
            enabled, _ = chr_.remotes_enabled(env=env)
        self.assertTrue(enabled)

    def test_env_override_garbage_falls_through(self):
        env = {chr_.REMOTES_ENV_VAR: "definitely-not-on-or-off"}
        with mock.patch.object(chr_, "read_team_server_url", return_value=None):
            enabled, reason = chr_.remotes_enabled(cli_override=True, env=env)
        # falls through past the unrecognized env value to the CLI override
        self.assertTrue(enabled)
        self.assertIn("CLI override", reason)

    def test_no_override_no_file_default_off(self):
        with mock.patch.object(chr_, "read_team_server_url", return_value=None):
            enabled, reason = chr_.remotes_enabled(env={})
        self.assertFalse(enabled)


class LoopbackIsOffTests(unittest.TestCase):
    """NS-24/D1a (cache_first_no_server_plan.md) - a loopback/localhost URL
    in team_conan_server.txt must read as remotes OFF, with the reason
    naming the loopback finding, not as an ON team server. A real,
    reachable, non-loopback host is unaffected."""

    def test_127_0_0_1_is_off(self):
        with mock.patch.object(chr_, "read_team_server_url",
                                return_value="http://127.0.0.1:9300"):
            enabled, reason = chr_.remotes_enabled(env={})
        self.assertFalse(enabled)
        self.assertIn("loopback", reason)

    def test_localhost_is_off(self):
        with mock.patch.object(chr_, "read_team_server_url",
                                return_value="http://localhost:9300"):
            enabled, reason = chr_.remotes_enabled(env={})
        self.assertFalse(enabled)
        self.assertIn("loopback", reason)

    def test_ipv6_loopback_is_off(self):
        with mock.patch.object(chr_, "read_team_server_url",
                                return_value="http://[::1]:9300"):
            enabled, reason = chr_.remotes_enabled(env={})
        self.assertFalse(enabled)
        self.assertIn("loopback", reason)

    def test_real_host_is_unaffected(self):
        with mock.patch.object(chr_, "read_team_server_url",
                                return_value="http://10.0.0.5:9300"):
            enabled, reason = chr_.remotes_enabled(env={})
        self.assertTrue(enabled)
        self.assertNotIn("loopback", reason)

    def test_empty_or_comment_only_file_is_off_not_loopback_reason(self):
        # Regression guard: an empty/comment-only file must still take the
        # "placeholder" path (read_team_server_url() returns None), never
        # accidentally match the loopback branch.
        with mock.patch.object(chr_, "read_team_server_url", return_value=None):
            enabled, reason = chr_.remotes_enabled(env={})
        self.assertFalse(enabled)
        self.assertIn("placeholder", reason)
        self.assertNotIn("loopback", reason)

    def test_cli_override_beats_loopback(self):
        # --remotes on must still win even when the file is loopback -
        # loopback detection sits at the same precedence level as any
        # other URL, below CLI/env override.
        with mock.patch.object(chr_, "read_team_server_url",
                                return_value="http://127.0.0.1:9300"):
            enabled, reason = chr_.remotes_enabled(cli_override=True, env={})
        self.assertTrue(enabled)
        self.assertIn("CLI override", reason)


class MalformedFileIsOffTests(unittest.TestCase):
    """Planted-violation criterion (WP-1 §2b): an empty or malformed
    team_conan_server.txt must resolve to OFF, never to some accidental
    truthy URL. Exercises read_team_server_url() directly (the shared
    placeholder detector) rather than mocking it, so a regression in the
    parsing itself - not just in remotes_enabled()'s use of it - is
    caught."""

    def _with_file_contents(self, text):
        import tempfile
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8")
        tmp.write(text)
        tmp.close()
        return Path(tmp.name)

    def test_empty_file_is_off(self):
        path = self._with_file_contents("")
        try:
            with mock.patch.object(chr_, "TEAM_SERVER_FILE", path):
                enabled, _ = chr_.remotes_enabled(env={})
            self.assertFalse(enabled)
        finally:
            path.unlink()

    def test_comment_only_file_is_off(self):
        path = self._with_file_contents(
            "# scripts/team_conan_server.txt\n"
            "# PLACEHOLDER - point this at your team's Conan server\n")
        try:
            with mock.patch.object(chr_, "TEAM_SERVER_FILE", path):
                enabled, _ = chr_.remotes_enabled(env={})
            self.assertFalse(enabled)
        finally:
            path.unlink()

    def test_malformed_non_url_text_is_off(self):
        path = self._with_file_contents("not-a-url-at-all\nnor is this\n")
        try:
            with mock.patch.object(chr_, "TEAM_SERVER_FILE", path):
                enabled, _ = chr_.remotes_enabled(env={})
            self.assertFalse(enabled)
        finally:
            path.unlink()

    def test_missing_file_is_off(self):
        missing = ROOT / "scripts" / "does_not_exist_team_conan_server.txt"
        self.assertFalse(missing.exists())
        with mock.patch.object(chr_, "TEAM_SERVER_FILE", missing):
            enabled, _ = chr_.remotes_enabled(env={})
        self.assertFalse(enabled)


class AdasLocalUrlNeverDecidesWhetherTests(unittest.TestCase):
    """NS-35 (cache_first_no_server_plan.md, RQ-3/RQ-5): this root copy
    never took ADAS_LOCAL_URL as a decision input (only
    adas_build_tools.conan_ops's copy did, fixed by the same commit as this
    test). Pinned two ways: the switch's inputs are exactly
    REMOTES_ENV_VAR/cli_override/team_conan_server.txt, and the source
    never reads the ADAS_LOCAL_URL environment variable at all."""

    def test_adas_local_url_in_environment_has_no_effect(self):
        with mock.patch.object(chr_, "read_team_server_url", return_value=None), \
                mock.patch.dict(os.environ, {"ADAS_LOCAL_URL": "https://real-team-server.example.com:9300"}):
            enabled, reason = chr_.remotes_enabled(env={})
        self.assertFalse(enabled)
        self.assertIn("placeholder", reason)

    def test_source_never_reads_adas_local_url(self):
        import inspect
        source = inspect.getsource(chr_)
        self.assertNotIn("ADAS_LOCAL_URL", source)


class PrintedOncePerEntryPointTests(unittest.TestCase):
    """WP-1 §2b: 'every entry point prints the state and the reason exactly
    once per run.' Each of setup.py/build.py/check_conan_resolution.py is
    driven far enough to pass the print point, with everything after it
    mocked/short-circuited so the assertion is purely about how many times
    the 'Remotes:' line appears."""

    def _remotes_line_count(self, stdout_text):
        return sum(1 for line in stdout_text.splitlines()
                    if line.startswith("Remotes: "))

    def test_setup_py_prints_once(self):
        buf = io.StringIO()
        argv = ["setup.py", "--dry-run", "--clean-develop-leftovers"]
        with mock.patch.object(sys, "argv", argv), \
                mock.patch.object(setup, "cleanup_develop_leftovers"), \
                mock.patch.dict(os.environ, {}, clear=False), \
                contextlib.redirect_stdout(buf):
            setup.main()
        self.assertEqual(1, self._remotes_line_count(buf.getvalue()))

    def test_build_py_deps_command_skips_remotes_print(self):
        # `deps` is hand-parsed and returns before the shared argparse
        # block - documented choice (report): a discovery command, not a
        # build, so it does not touch remotes at all.
        buf = io.StringIO()
        argv = ["build.py", "deps", "df"]
        with mock.patch.object(sys, "argv", argv), \
                mock.patch.object(build, "print_deps"), \
                contextlib.redirect_stdout(buf):
            build.main()
        self.assertEqual(0, self._remotes_line_count(buf.getvalue()))

    def test_build_py_prints_once_on_unknown_project_exit(self):
        # Cheapest real path through main()'s shared argparse block that
        # still reaches the print-once point before exiting.
        buf = io.StringIO()
        argv = ["build.py", "df", "-t", "sil", "-p", "vs2026",
                "-P", "definitely-not-a-real-project"]
        with mock.patch.object(sys, "argv", argv), \
                mock.patch.object(build, "all_projects", return_value=["base"]), \
                contextlib.redirect_stdout(buf), \
                self.assertRaises(SystemExit):
            build.main()
        self.assertEqual(1, self._remotes_line_count(buf.getvalue()))

    def test_check_conan_resolution_prints_once(self):
        buf = io.StringIO()
        with mock.patch.object(ccr, "discover_required_refs", return_value=[]), \
                contextlib.redirect_stdout(buf):
            ccr.main([])
        self.assertEqual(1, self._remotes_line_count(buf.getvalue()))


if __name__ == "__main__":
    unittest.main()
