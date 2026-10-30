# Copyright (c) LT EPS. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SUPERPROJECT
# @file test_bundle_machinery_from_checkout.py
# @brief make_offline_bundle builds missing machinery from the checkout, never a download.
# @author Pavan Karimajji

"""Found 2026-09-29 on a fresh Conan cache: `make_offline_bundle.py
--platform vs2026` tried `conan download adas-toolchain/1.0.5 -r adas-local`
and died with "Remote 'adas-local' doesn't exist". The machinery pins are made
from this checkout by setup's own cache preparation (D2 of
cache_first_no_server_plan.md); the bundle now calls that one implementation.

Run (from the superproject root):
    python -m unittest scripts.tests.test_bundle_machinery_from_checkout
"""
import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import make_offline_bundle as mob  # noqa: E402

PINS = {"third_party": ["protobuf/3.21.12"], "third_party_tool": [],
        "toolchain": ["adas-toolchain/1.0.5"], "build_tools": ["adas-build-tools/1.0.33"]}


class _Stop(Exception):
    """Raised by the mocked third-party resolve: the machinery step is done."""


class BundleMachineryTests(unittest.TestCase):

    def _run(self, cached_before, cached_after=None):
        """Runs make_bundle up to the third-party resolve. `cached_*` is the
        set of refs _have_in_cache reports before / after the fill."""
        state = {"filled": False}
        after = cached_after if cached_after is not None else cached_before

        def have(ref, with_packages):
            return ref in (after if state["filled"] else cached_before)

        def fill():
            state["filled"] = True

        conan_calls = []
        with mock.patch.object(mob, "derive_pins", return_value=PINS), \
             mock.patch.object(mob, "_profile_settings", return_value={"os": "Windows"}), \
             mock.patch.object(mob, "_have_in_cache", side_effect=have), \
             mock.patch.object(mob, "_fill_machinery_from_checkout", side_effect=fill) as fill_mock, \
             mock.patch.object(mob, "_conan", side_effect=lambda *a, **k: conan_calls.append(a)), \
             mock.patch.object(mob, "_transitive_refs", side_effect=_Stop), \
             mock.patch("pathlib.Path.mkdir"), \
             contextlib.redirect_stdout(io.StringIO()):
            try:
                mob.make_bundle("vs2026", Path("C:/nowhere/offline_bundle"), wheels_dir=False)
                outcome = "finished"
            except _Stop:
                outcome = "reached third-party resolve"
            except SystemExit as exc:
                outcome = str(exc.code)
        return outcome, fill_mock, conan_calls

    def test_missing_machinery_is_built_from_the_checkout_never_downloaded(self):
        outcome, fill, calls = self._run(cached_before=set(),
                                         cached_after={"adas-toolchain/1.0.5",
                                                       "adas-build-tools/1.0.33"})
        self.assertEqual(outcome, "reached third-party resolve")
        fill.assert_called_once()
        self.assertFalse([c for c in calls if "download" in c], calls)

    def test_machinery_already_cached_is_not_rebuilt(self):
        outcome, fill, _ = self._run(cached_before={"adas-toolchain/1.0.5",
                                                    "adas-build-tools/1.0.33"})
        self.assertEqual(outcome, "reached third-party resolve")
        fill.assert_not_called()

    def test_still_missing_after_the_fill_is_reason_fix_run_before_the_long_resolve(self):
        outcome, _, calls = self._run(cached_before=set(), cached_after={"adas-toolchain/1.0.5"})
        lines = outcome.splitlines()
        self.assertEqual([l.split(":")[0] for l in lines], ["Reason", "Fix", "Run"], outcome)
        self.assertIn("adas-build-tools/1.0.33", lines[0])
        self.assertIn("scripts/setup.py", lines[2])
        self.assertNotIn("<", outcome)
        self.assertNotIn("adas-local", outcome)
        self.assertFalse([c for c in calls if "download" in c], calls)

    def test_no_adas_local_remote_left_in_the_bundle_tool(self):
        self.assertFalse(hasattr(mob, "DEFAULT_REMOTE"),
                         "the bundle never downloads machinery from a server (D2)")


if __name__ == "__main__":
    unittest.main()
