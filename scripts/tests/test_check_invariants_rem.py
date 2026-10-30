"""
scripts/tests/test_check_invariants_rem.py

Regression tests for REM-1/REM-2 (scripts/check_invariants.py, NS-36 --
cache_first_no_server_plan.md, RQ-3/RQ-5). §0 says a change contradicting
one of the frozen requirements is a regression, but nothing failed when
one landed (found by a real review, 2026-09-24, checking the tree instead
of trusting this plan's own self-report). These two checks are that
enforcement; this file is the "planted violation, watched it fail,
restored, watched it pass" proof each carries (R-REQ-9).

Isolated from the real tree with a tempfile fixture (same pattern as
test_check_invariants.py's own LNC-1 suite) -- REM-1/REM-2 walk `root`,
so a small synthetic tree under a temp dir exercises the same logic
without ever touching the real scripts/ or modules/toolchain/.

Run:
    py -m unittest discover -s scripts/tests
    (from the superproject root)
"""

import os
import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import check_invariants  # noqa: E402 - path must be set up first


_GOOD_SWITCH = textwrap.dedent('''\
    import os

    REMOTES_ENV_VAR = "ADAS_REMOTES_ENABLED"


    def _is_loopback_url(url):
        from urllib.parse import urlsplit
        host = urlsplit(url).hostname
        return host is not None and host.lower() in ("127.0.0.1", "localhost", "::1")


    def _team_server_url():
        return None


    def remotes_enabled(cli_override=None, env=None):
        """The switch: env override, then cli_override, then the file."""
        env = os.environ if env is None else env
        raw = env.get(REMOTES_ENV_VAR)
        if raw is not None:
            return raw.strip().lower() in ("on", "1", "true", "yes"), "env override"
        if cli_override is not None:
            return cli_override, "cli override"
        url = _team_server_url()
        if url:
            if _is_loopback_url(url):
                return False, f"{url} is a loopback address, not a team server"
            return True, f"team server configured: {url}"
        return False, "no team Conan server configured"
    ''')


class _SwitchTreeFixture(unittest.TestCase):
    """Builds a synthetic tree with exactly the three declared switch files
    (module docstring's `_SWITCH_FILES`), each starting from the known-good
    body above, and patches `check_invariants._SWITCH_FILES`/ROOT-relative
    resolution to walk it."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="rem_invariant_")
        self.root = Path(self._tmp)
        self._write_all(_GOOD_SWITCH)

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _write_all(self, body_text):
        for rel in check_invariants._SWITCH_FILES:
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body_text, encoding="utf-8")

    def _write_one(self, rel, body_text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body_text, encoding="utf-8")


class CheckRem1Tests(_SwitchTreeFixture):

    def test_passes_when_all_three_agree(self):
        self.assertEqual(check_invariants.check_rem1(self.root), [])

    def test_planted_adas_local_url_in_body_is_caught(self):
        mutated = _GOOD_SWITCH.replace(
            "url = _team_server_url()",
            "url = _team_server_url() or ADAS_LOCAL_URL",
        )
        self.assertNotEqual(mutated, _GOOD_SWITCH)
        self._write_one("modules/toolchain/adas_build_tools/conan_ops.py", mutated)
        findings = check_invariants.check_rem1(self.root)
        self.assertTrue(any("ADAS_LOCAL_URL" in f and "conan_ops.py" in f for f in findings), findings)
        self.assertTrue(any(f.startswith("REM-1 (RQ-3/RQ-5):") for f in findings))

    def test_planted_env_var_mismatch_is_caught(self):
        mutated = _GOOD_SWITCH.replace(
            'REMOTES_ENV_VAR = "ADAS_REMOTES_ENABLED"',
            'REMOTES_ENV_VAR = "SOME_OTHER_NAME"',
        )
        self._write_one("scripts/conan_home_resolution.py", mutated)
        findings = check_invariants.check_rem1(self.root)
        self.assertTrue(any("SOME_OTHER_NAME" in f for f in findings), findings)

    def test_planted_missing_loopback_host_is_caught(self):
        mutated = _GOOD_SWITCH.replace(
            'host.lower() in ("127.0.0.1", "localhost", "::1")',
            'host.lower() in ("127.0.0.1", "::1")',  # "localhost" dropped
        )
        self._write_one("modules/toolchain/copy_files/scripts/build.py", mutated)
        findings = check_invariants.check_rem1(self.root)
        self.assertTrue(any("localhost" in f for f in findings), findings)

    def test_planted_undeclared_copy_is_caught(self):
        stray = self.root / "modules" / "sim" / "scripts" / "sneaky_switch.py"
        stray.parent.mkdir(parents=True, exist_ok=True)
        stray.write_text(_GOOD_SWITCH, encoding="utf-8")
        findings = check_invariants.check_rem1(self.root)
        self.assertTrue(
            any("sneaky_switch.py" in f and "not declared" in f for f in findings), findings)

    def test_planted_missing_declared_copy_is_caught(self):
        (self.root / "scripts" / "conan_home_resolution.py").unlink()
        findings = check_invariants.check_rem1(self.root)
        self.assertTrue(
            any("conan_home_resolution.py" in f and "no longer defines" in f for f in findings),
            findings)

    def test_cpy1_guarded_per_component_copies_are_not_double_flagged(self):
        # Every component's own scripts/build.py is a byte-identical copy
        # of copy_files/scripts/build.py, already held identical by CPY-1
        # -- REM-1 must not report each one as an independent, undeclared
        # switch copy.
        for name in ("df", "mathlib"):
            self._write_one(f"modules/{name}/scripts/build.py", _GOOD_SWITCH)
        findings = check_invariants.check_rem1(self.root)
        self.assertEqual(findings, [])


class CheckRem2Tests(_SwitchTreeFixture):

    def test_passes_on_a_clean_tree(self):
        self.assertEqual(check_invariants.check_rem2(self.root), [])

    def test_planted_second_env_var_is_caught(self):
        mutated = _GOOD_SWITCH + (
            '\n_SNEAKY = os.environ.get("ADAS_REMOTES_FORCE")\n'
        )
        self._write_one("modules/toolchain/adas_build_tools/conan_ops.py", mutated)
        findings = check_invariants.check_rem2(self.root)
        self.assertTrue(any("ADAS_REMOTES_FORCE" in f for f in findings), findings)
        self.assertTrue(any(f.startswith("REM-2 (RQ-3/RQ-5):") for f in findings))

    def test_the_declared_name_itself_never_flags(self):
        findings = check_invariants.check_rem2(self.root)
        self.assertFalse(any("ADAS_REMOTES_ENABLED" in f for f in findings), findings)


if __name__ == "__main__":
    unittest.main()
