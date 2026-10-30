"""
scripts/tests/test_profile_path_agreement.py

Prompt 35 item 1: the aggregate conan install (scripts/build.py's
run_aggregate_build()) now resolves --profile:host/--profile:build via
scripts/conan_home_resolution.py's own project_profile_path()/profile_args(),
a second copy of adas_build_tools.conan_ops.project_profile_path() -- the
same R-BUILD-1/6 two-copy split test_conan_home_resolution_matrix.py already
guards for resolve_conan_home_and_mode(), forced for the same reason: the
pip-installed copy lives in adas_build_tools, which the aggregator (running
in the superproject's own Python) never installs.

Run:
    py -m unittest discover -s scripts/tests
    (from the superproject root)
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import conan_home_resolution as superproject_impl  # noqa: E402 - path must be set up first

# Same sibling-source import test_conan_home_resolution_matrix.py already
# uses: the checked-out source under modules/toolchain/, never a pip-installed
# .venv copy (which may not exist on the machine running this suite, and
# would test a stale published version rather than this checkout's own).
sys.path.insert(0, str(ROOT / "modules" / "toolchain"))
import adas_build_tools.conan_ops as _conan_ops  # noqa: E402 - path must be set up first

# vs2026/ubuntu_gcc are the two platforms actually shipping a profile as of
# this writing; a made-up third platform exercises the "no profile shipped
# yet" fallback both copies must agree on.
_PLATFORM_CASES = ("vs2026", "ubuntu_gcc", "not_a_real_platform")


def _run_matrix(impl_a, impl_b):
    """Returns [(platform, result_a, result_b)] for every platform where the
    two copies disagree on whether a profile exists, and - when both agree
    a profile exists - whether the two paths' file CONTENTS agree (paths
    themselves legitimately differ: one via importlib.resources, one via a
    direct ROOT-relative path; both resolve the identical checked-out
    profile file since modules/toolchain is a submodule of this same repo)."""
    mismatches = []
    for platform in _PLATFORM_CASES:
        result_a = impl_a(platform)
        result_b = impl_b(platform)
        if (result_a is None) != (result_b is None):
            mismatches.append((platform, result_a, result_b))
            continue
        if result_a is not None:
            content_a = Path(result_a).read_bytes()
            content_b = Path(result_b).read_bytes()
            if content_a != content_b:
                mismatches.append((platform, result_a, result_b))
    return mismatches


class ProfilePathAgreementTests(unittest.TestCase):
    """The two remaining implementations of "which Conan profile does
    `platform` pin" must agree on every platform - a real disagreement here
    means the aggregate and the per-component path build against different
    declared compiler settings, silently, which is exactly the divergence
    _profile_args()/project_profile_path() exist to prevent."""

    def test_both_implementations_agree_on_every_platform(self):
        mismatches = _run_matrix(
            superproject_impl.project_profile_path,
            _conan_ops.project_profile_path,
        )
        self.assertEqual(
            mismatches, [],
            f"{len(mismatches)} of {len(_PLATFORM_CASES)} platforms disagree "
            "between scripts/conan_home_resolution.py and "
            "adas_build_tools.conan_ops - see the tuples above "
            "(platform, result_a, result_b).")

    def test_matrix_actually_catches_a_planted_disagreement(self):
        """R-REQ-9: a check nobody has seen fail is a check nobody should
        believe. Plants a broken copy that claims no platform ever ships a
        profile, and proves _run_matrix() reports it rather than trusting
        that it would."""

        def broken_always_none(_platform):
            return None

        mismatches = _run_matrix(superproject_impl.project_profile_path, broken_always_none)
        self.assertGreater(
            len(mismatches), 0,
            "planted violation (claims no profile ever shipped) was not "
            "caught - the matrix comparison itself is broken, not just "
            "failing to find a real bug.")


if __name__ == "__main__":
    unittest.main()
