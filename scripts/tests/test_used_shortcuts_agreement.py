"""scripts/tests/test_used_shortcuts_agreement.py

Item 4 (prompt 35): scripts/build.py's refresh_aggregate_used_shortcuts()
now ports adas_build_tools.workarea's own junction/.lnk fallback ladder
(_create_link()/_create_windows_lnk()) rather than the previous
symlink-only version -- a second, necessarily-duplicated copy, since the
aggregate runs in the superproject's own Python and can never `import
adas_build_tools` (that package only ever lives inside a component's own
.venv). Same R-BUILD-1/6 two-copy split test_conan_home_resolution_matrix.py
and test_profile_path_agreement.py already guard for their own pairs,
forced here for the identical reason.

Run:
    py -m unittest discover -s scripts/tests
    (from the superproject root)
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import build as superproject_impl  # noqa: E402 - path must be set up first

# Same sibling-source import test_profile_path_agreement.py already uses:
# the checked-out source under modules/toolchain/, never a pip-installed
# .venv copy (which may not exist on the machine running this suite, and
# would test a stale published version rather than this checkout's own).
sys.path.insert(0, os.path.join(ROOT, "modules", "toolchain"))
import adas_build_tools.workarea as _workarea  # noqa: E402 - path must be set up first


def _create_link_result(impl_create_link, tmp_dir, label, path_type=str):
    """Exercises one _create_link() implementation against a fresh target
    directory + link path under tmp_dir, and reports what actually got
    created on disk (never trusts the return value alone -- a copy could
    return True while creating nothing, or vice versa). `path_type` matches
    each implementation's own calling convention -- str for
    scripts/build.py's os.path-style copy, pathlib.Path for
    adas_build_tools.workarea's own (it calls link_path.symlink_to(), a
    Path-only method)."""
    target = os.path.join(tmp_dir, f"{label}_target")
    os.makedirs(target, exist_ok=True)
    link_path = os.path.join(tmp_dir, f"{label}_link")

    created = impl_create_link(path_type(link_path), path_type(target))

    if os.path.islink(link_path):
        kind = "symlink"
    elif os.path.isdir(link_path):
        kind = "junction"
    elif os.path.isfile(link_path + ".lnk"):
        kind = "lnk"
    else:
        kind = "none"

    return created, kind


class UsedShortcutsAgreementTests(unittest.TestCase):
    """The two remaining implementations of "how do I link conan_workarea/
    used/<name> to a real package folder" must agree on what kind of
    shortcut this machine actually lets them create -- a real disagreement
    here means the aggregate and the per-component path behave differently
    under the exact same Developer-Mode/elevation state, silently, which is
    exactly the divergence this test exists to prevent."""

    def setUp(self):
        self._tmp_dir = tempfile.mkdtemp(prefix="used_shortcuts_agreement_")
        self.addCleanup(shutil.rmtree, self._tmp_dir, ignore_errors=True)

    def test_both_implementations_produce_the_same_kind_of_link(self):
        created_a, kind_a = _create_link_result(
            superproject_impl._create_link, self._tmp_dir, "a", path_type=str)
        created_b, kind_b = _create_link_result(
            _workarea._create_link, self._tmp_dir, "b", path_type=Path)

        self.assertEqual(
            (created_a, kind_a), (created_b, kind_b),
            f"scripts/build.py's _create_link() produced ({created_a!r}, "
            f"{kind_a!r}) but adas_build_tools.workarea's own copy produced "
            f"({created_b!r}, {kind_b!r}) for the same machine state -- the "
            "two copies have drifted.")

    def test_matrix_actually_catches_a_planted_disagreement(self):
        """R-REQ-9: a check nobody has seen fail is a check nobody should
        believe. Plants a broken copy that claims every link attempt fails
        outright, and proves this test would report it rather than trusting
        that it would."""

        def broken_always_fails(_link_path, _target_path):
            return False

        created_a, kind_a = _create_link_result(
            broken_always_fails, self._tmp_dir, "planted", path_type=str)
        created_b, kind_b = _create_link_result(
            _workarea._create_link, self._tmp_dir, "real", path_type=Path)

        self.assertNotEqual(
            (created_a, kind_a), (created_b, kind_b),
            "planted violation (claims every link attempt fails) was not "
            "distinguishable from the real implementation's result -- this "
            "test's own comparison is broken, not just failing to find a "
            "real bug.")


if __name__ == "__main__":
    unittest.main()
