"""
scripts/tests/test_conan_home_resolution_matrix.py

WP-23 (conan_environment_plan.md §6) reduced "which
CONAN_HOME does this build use" from three independent implementations to
two: scripts/conan_home_resolution.py (shared by root scripts/build.py and
scripts/setup.py, both superproject-local Python) and
adas_build_tools.conan_ops.resolve_conan_home_and_mode() (pip-installed
into each component's own .venv - a genuinely different environment, so it
cannot import the first). Two copies of one rule is the same shape
CPY-1 (scripts/check_invariants.py) already holds copy-distributed build
machinery to - and, same as CPY-1, "necessary duplication" is not an
exemption from having a guard; it is the reason one is needed. This is
that guard, run as an ordinary unit test rather than a CPY-1 diff (the two
copies are semantically, not textually, identical - one takes an
os.environ read, both return the same tuple shape).

Run:
    py -m unittest discover -s scripts/tests
    (from the superproject root)
"""

import itertools
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import conan_home_resolution as superproject_impl  # noqa: E402 - path must be set up first

# Imports adas_build_tools.conan_ops directly from its checked-out source
# (modules/toolchain/adas_build_tools/, the package root itself - conan_ops.py
# does `from adas_build_tools.config import ROOT`, a real intra-package import
# that needs `adas_build_tools` importable as a package, not loaded as a
# standalone module by path) - never from an installed .venv, which may not
# exist on the machine running this suite and would in any case be testing a
# stale, previously-published version rather than this checkout's own source
# (exactly the stale-pin gap conf/build_tools.version's own bump discipline
# exists to close, but this test wants the SOURCE, not a build artifact).
sys.path.insert(0, str(ROOT / "modules" / "toolchain"))
import adas_build_tools.conan_ops as _conan_ops  # noqa: E402 - path must be set up first

# The full input matrix (task's own enumeration): CONAN_HOME unset / set to
# the package home / set to the develop home / set to a third custom path;
# --mode unset / develop / package; invocation superproject / submodule.
# "Package home" and "develop home" are stand-ins (any explicit CONAN_HOME
# wins regardless of its value - the point of including two recognizable
# ones alongside a genuinely arbitrary third is to catch a bug that
# special-cased one of the well-known paths instead of treating "explicit"
# uniformly).
_CONAN_HOME_CASES = {
    "unset": None,
    "package_home": "/home/dev/.conan2",
    "develop_home": "/home/dev/.conan2-dev",
    "third_custom_path": "/mnt/z/some/other/conan/home",
}
# RD-05 (remove_develop_mode_plan.md, WP-4): both implementations now
# refuse "develop" (see test_root_refuses_develop_mode/
# test_component_refuses_develop_mode below) and default unconditionally
# to "package" regardless of invocation - the temporary narrowing RD-03
# imposed here (only `mode="package"` compared, "develop" and the unset
# default excluded because the component copy had not yet caught up) is
# gone; the unset default is back in the matrix since both sides now
# agree on it too.
_MODE_CASES = (None, "package")
_INVOCATION_CASES = ("superproject", "submodule")


def _run_matrix(impl_a, impl_b):
    """Runs both implementations across the full matrix, returning a list
    of (case, result_a, result_b) for every combination where they
    disagree on (conan_home, mode) - the `reason` string is deliberately
    excluded from comparison (the two copies word it slightly differently
    for the same decision, e.g. "call site default" vs "invocation
    default" - a wording difference is not a behavioural divergence and
    asserting it would make this test fragile for the wrong reason)."""
    mismatches = []
    for home_label, mode, invocation in itertools.product(
            _CONAN_HOME_CASES, _MODE_CASES, _INVOCATION_CASES):
        home_value = _CONAN_HOME_CASES[home_label]
        env = {} if home_value is None else {"CONAN_HOME": home_value}
        with mock.patch.dict(os.environ, env, clear=False):
            if home_value is None:
                os.environ.pop("CONAN_HOME", None)
            result_a = impl_a(mode, invocation)[:2]  # (conan_home, mode) - drop reason
            result_b = impl_b(mode, invocation)[:2]
        if result_a != result_b:
            mismatches.append(((home_label, mode, invocation), result_a, result_b))
    return mismatches


class ConanHomeResolutionMatrixTests(unittest.TestCase):
    """The two remaining implementations of WP-23's resolution rule must
    return the identical (conan_home, mode) for every combination of
    CONAN_HOME / --mode / invocation - a real disagreement here is exactly
    the "same component behaves differently depending on how it was
    launched" confusion WP-23 exists to remove, just relocated from a
    build's own inconsistency to two implementations quietly drifting."""

    def test_both_implementations_agree_on_every_combination(self):
        mismatches = _run_matrix(
            superproject_impl.resolve_conan_home_and_mode,
            _conan_ops.resolve_conan_home_and_mode,
        )
        self.assertEqual(
            mismatches, [],
            f"{len(mismatches)} of "
            f"{len(_CONAN_HOME_CASES) * len(_MODE_CASES) * len(_INVOCATION_CASES)} "
            "combinations disagree between scripts/conan_home_resolution.py "
            "and adas_build_tools.conan_ops - see the tuples above "
            "((conan_home_label, mode, invocation), result_a, result_b).")

    def test_matrix_actually_catches_a_planted_precedence_violation(self):
        """R-REQ-9: a check nobody has seen fail is a check nobody should
        believe. Plants a real violation - a broken copy that checks
        --mode BEFORE an explicit CONAN_HOME (the exact inversion WP-23's
        precedence forbids: "an explicit CONAN_HOME always wins... never
        overridden") - and proves _run_matrix() reports a mismatch against
        the real implementation, rather than trusting that it would."""

        def broken_precedence(explicit_mode, invocation):
            # Inverted on purpose: --mode checked first, CONAN_HOME second -
            # this must diverge from the real rule the moment BOTH an
            # explicit CONAN_HOME and an explicit --mode are present in the
            # same case, which the matrix always includes.
            if explicit_mode == "package":
                mode = "package"
            elif "CONAN_HOME" in os.environ:
                return os.environ["CONAN_HOME"], "n/a", "explicit CONAN_HOME (checked second - broken)"
            else:
                mode = "package"
            return None, mode, "broken"

        mismatches = _run_matrix(superproject_impl.resolve_conan_home_and_mode, broken_precedence)
        self.assertGreater(
            len(mismatches), 0,
            "planted violation (--mode checked before explicit CONAN_HOME) "
            "was not caught - the matrix comparison itself is broken, not "
            "just failing to find a real bug.")
        # The specific case that must be among the caught mismatches: an
        # explicit CONAN_HOME together with an explicit --mode. The real
        # rule returns the explicit CONAN_HOME verbatim; the broken one
        # returns the package path instead.
        cases_caught = {case for case, _, _ in mismatches}
        self.assertIn(
            ("third_custom_path", "package", "superproject"), cases_caught,
            "the planted violation's own defining case (explicit CONAN_HOME "
            "+ explicit --mode package) was not among the caught mismatches.")

    def test_root_refuses_develop_mode(self):
        """RD-03: scripts/conan_home_resolution.py's copy no longer accepts
        'develop' at all - a caller passing it is a bug upstream (refusing
        `--mode develop` is scripts/build.py's/scripts/setup.py's own job,
        at the CLI, with a message pointing at the plan)."""
        with self.assertRaises(ValueError) as ctx:
            superproject_impl.resolve_conan_home_and_mode("develop", "superproject")
        self.assertIn("remove_develop_mode_plan.md", str(ctx.exception))

    def test_component_refuses_develop_mode(self):
        """RD-05 (remove_develop_mode_plan.md, WP-4): adas_build_tools.
        conan_ops's own copy now raises for 'develop' too - the two
        implementations agree on refusal, not just on the package-mode
        answer, closing the asymmetry RD-03's own narrowing comment
        documented as temporary."""
        with self.assertRaises(ValueError) as ctx:
            _conan_ops.resolve_conan_home_and_mode("develop", "superproject")
        self.assertIn("remove_develop_mode_plan.md", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
