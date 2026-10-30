"""
scripts/tests/test_aggregate_data_only_dep.py

A pure-data dependency (today: shared_config) in an AGGREGATE build.

Found 2026-09-25 by a user running the GUI's "all deps in-tree (--with-all)"
against a genuinely empty Conan cache:

    [aggregate]  shared_config 1.0.0  package  (conan cache)
    ERROR: shared_config (adas-shared-config/1.0.0) is not in this machine's
    Conan cache for platform vs2026 - run ... --prepare ...
    (or --with shared_config to build it in this aggregate instead)

Root cause: build.py folded data-only modules into `pkg_only` even when the
user had explicitly named them, so they were demanded from the cache instead
of being built. That contradicted D4's own words - "build.py compiles only the
primary and whatever --with names" - and made the refusal's suggested fix
(`--with shared_config`) impossible to act on.

Fix (A): a NAMED data module is packaged from the checkout by
package_named_data_modules(), reusing the same create-and-record function
setup.py --prepare uses. A data module NOT named still comes from the cache
and still stops the build when missing - that is the guard that keeps
build.py from touching things nobody asked for, and
test_unnamed_data_module_is_still_refused below is what holds it in place.

Pure unittest + unittest.mock - no conan, no network, no real builds.

Run:
    py -m unittest discover -s scripts/tests
"""
import os
import re
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import build as adas_build  # noqa: E402 - path must be set up first


DATA_MOD = "shared_config"
COMPILED_MOD = "mathlib"


def _package_type(mod):
    """shared_config is the repo's only pure-data module today (its own
    conf/build.yml: "no compiled artifact", package_type "unknown")."""
    return "unknown" if mod == DATA_MOD else "static-library"


class PkgOnlyExcludesNamedDataTests(unittest.TestCase):
    """The set arithmetic, after A. `pkg_only` is what must come FROM the
    cache; a named data module is built here, so it must not be in it."""

    @staticmethod
    def _sets(total, closure):
        """Calls build.partition_aggregate_modules() FOR REAL. An earlier
        version recomputed the split here and so passed against a build.py
        mutated to package un-named modules - see that function's docstring."""
        with mock.patch.object(adas_build, "module_package_type", _package_type):
            _compiled, data_only, pkg_only = adas_build.partition_aggregate_modules(
                total, closure)
        return pkg_only, data_only

    def test_with_all_builds_the_data_module_here(self):
        closure = {"df", COMPILED_MOD, DATA_MOD}
        pkg_only, data_only = self._sets(set(closure), closure)  # --with-all
        self.assertEqual(data_only, {DATA_MOD},
                         "--with-all names everything, so the data module is named")
        self.assertNotIn(DATA_MOD, pkg_only,
                         "a NAMED data module is packaged from the checkout, so it "
                         "must not also be demanded from the cache - that double "
                         "handling is the defect the user hit")

    def test_ticking_the_data_dep_by_name_builds_it_here(self):
        closure = {"df", COMPILED_MOD, DATA_MOD}
        pkg_only, data_only = self._sets({"df", DATA_MOD}, closure)
        self.assertEqual(data_only, {DATA_MOD})
        self.assertNotIn(DATA_MOD, pkg_only)

    def test_unnamed_data_module_still_comes_from_the_cache(self):
        """THE safety test. D4's real line is 'build what you named, never
        touch what you didn't'. An un-named data module must stay in pkg_only
        so the missing-cache guard still refuses it."""
        closure = {"df", COMPILED_MOD, DATA_MOD}
        pkg_only, data_only = self._sets({"df"}, closure)  # nothing ticked
        self.assertEqual(data_only, set())
        self.assertIn(DATA_MOD, pkg_only,
                      "build.py must never package a module the user did not name - "
                      "that is the silent-bug door this whole rule exists to keep shut")

    def test_data_only_is_always_a_subset_of_what_was_named(self):
        """The invariant, stated directly: whatever the kinds, nothing outside
        `total` may be built or packaged here."""
        closure = {"df", COMPILED_MOD, DATA_MOD, "sim"}
        for total in ({"df"}, {"df", DATA_MOD}, {"df", COMPILED_MOD}, set(closure)):
            _pkg_only, data_only = self._sets(set(total), closure)
            self.assertTrue(data_only <= set(total),
                            f"data_only {data_only} escaped the named set {total}")


class PackageNamedDataModulesTests(unittest.TestCase):
    """build.package_named_data_modules() - called for real."""

    def _run(self, missing=(), stale=(), unrecorded=(), outdated=(), create_ok=True):
        calls = {}

        def _create(*args, **kwargs):
            calls["create"] = (args, kwargs)
            return create_ok

        with mock.patch.object(adas_build, "module_package_name",
                               side_effect=lambda m: f"adas-{m}"), \
             mock.patch.object(adas_build, "module_version", return_value="1.0.0"), \
             mock.patch.object(adas_build, "missing_cache_refs", return_value=list(missing)), \
             mock.patch.object(adas_build, "stale_cache_refs",
                               return_value=(list(stale), list(unrecorded))), \
             mock.patch.object(adas_build, "outdated_format_refs",
                               return_value=list(outdated)), \
             mock.patch.object(adas_build.check_conan_resolution, "pinned_profile_settings",
                               return_value={"os": "Windows"}), \
             mock.patch.object(adas_build, "profile_args", return_value=["-pr", "x"]), \
             mock.patch.object(adas_build, "create_and_record_module",
                               side_effect=_create):
            failed = adas_build.package_named_data_modules(
                {DATA_MOD}, "base", "sil", "vs2026", "Release", log=lambda *a: None)
        return failed, calls

    def test_missing_from_cache_is_packaged(self):
        failed, calls = self._run(missing=[(DATA_MOD, "adas-shared_config/1.0.0")])
        self.assertEqual(failed, [])
        self.assertIn("create", calls, "a data module the user named and that is not "
                                       "cached must be packaged, not refused")

    def test_stale_source_is_repackaged(self):
        _, calls = self._run(stale=[(DATA_MOD, "aaaa", "bbbb")])
        self.assertIn("create", calls)

    def test_no_freshness_record_is_repackaged(self):
        """Closes the NS-37 trap: a package with no record would otherwise be
        refused later as unverifiable."""
        _, calls = self._run(unrecorded=[DATA_MOD])
        self.assertIn("create", calls)

    def test_outdated_format_record_is_repackaged(self):
        """NS-52: an older-format record cannot be compared, so the named data
        module is re-created (and re-recorded under the current format)."""
        _, calls = self._run(outdated=[DATA_MOD])
        self.assertIn("create", calls)

    def test_create_is_verified_against_the_cache(self):
        """NS-53 (RV-3): build.py passes the same verify_cached setup.py does."""
        _, calls = self._run(missing=[(DATA_MOD, "x")])
        _args, kwargs = calls["create"]
        self.assertTrue(callable(kwargs.get("verify_cached")),
                        "conan create returning 0 is not by itself proof")

    def test_cached_and_unchanged_is_skipped(self):
        failed, calls = self._run()
        self.assertEqual(failed, [])
        self.assertNotIn("create", calls,
                         "a repeat build must pay nothing for an unchanged data module")

    def test_a_failed_create_is_reported_not_swallowed(self):
        failed, _ = self._run(missing=[(DATA_MOD, "x")], create_ok=False)
        self.assertEqual([m for m, _ in failed], [DATA_MOD])

    def test_create_carries_the_project_and_platform_it_was_asked_for(self):
        _, calls = self._run(missing=[(DATA_MOD, "x")])
        args, kwargs = calls["create"]
        self.assertIn("base", args, "project must be passed through")
        self.assertEqual(kwargs.get("platform"), "vs2026")
        self.assertEqual(kwargs.get("target"), "sil")


class VerifyCachedEndToEndTests(unittest.TestCase):
    """NS-53 (RV-3), planted: package_named_data_modules() with the REAL
    create_and_record_module() - only the subprocess and the cache query are
    doubles. A `conan create` that exits 0 but lands no matching binary must be
    reported as a failure and must not be recorded. Remove verify_cached from
    build.py's call and this fails."""

    def test_create_exit_zero_without_a_binary_is_a_failure(self):
        import conan_home_resolution as chr_
        ok_run = mock.Mock(return_value=mock.Mock(returncode=0, stdout="", stderr=""))
        with mock.patch.object(adas_build, "module_package_name", return_value="adas-x"), \
             mock.patch.object(adas_build, "module_version", return_value="1.0.0"), \
             mock.patch.object(adas_build, "missing_cache_refs",
                               return_value=[(DATA_MOD, "adas-x/1.0.0")]), \
             mock.patch.object(adas_build, "stale_cache_refs", return_value=([], [])), \
             mock.patch.object(adas_build, "outdated_format_refs", return_value=[]), \
             mock.patch.object(adas_build, "profile_args", return_value=[]), \
             mock.patch.object(adas_build.check_conan_resolution, "pinned_profile_settings",
                               return_value={"os": "Windows"}), \
             mock.patch.object(adas_build.check_conan_resolution, "_cache_matches_profile",
                               return_value=False), \
             mock.patch.object(chr_.subprocess, "run", ok_run), \
             mock.patch.object(chr_, "record_prepared_module") as record:
            failed = adas_build.package_named_data_modules(
                {DATA_MOD}, "base", "sil", "vs2026", "Release", log=lambda *a: None)
        self.assertEqual([m for m, _ in failed], [DATA_MOD])
        record.assert_not_called()


class RefusalNamesAFixThatWorksTests(unittest.TestCase):
    """RQ-9 - the named alternative must actually work. Calls
    build.missing_cache_ref_message() for real: an earlier version of this
    class mirrored the logic inline and so passed against a deliberately
    broken implementation (the NS-31 failure mode)."""

    def _refusal_text(self, dep):
        with mock.patch.object(adas_build, "module_package_type", _package_type):
            return adas_build.missing_cache_ref_message(
                dep, f"adas-{dep}/1.0.0", "df", "sil", "vs2026", "base")

    def test_data_dep_is_offered_with_and_told_what_it_means(self):
        text = self._refusal_text(DATA_MOD)
        self.assertIn(f"--with {DATA_MOD}", text,
                      "after A this suggestion works, so it must be given")
        self.assertIn("package it from your checkout", text,
                      "say which kind of 'build here' the reader is about to get")

    def test_compiled_dep_is_offered_with_from_source(self):
        text = self._refusal_text(COMPILED_MOD)
        self.assertIn(f"--with {COMPILED_MOD}", text)
        self.assertIn("from source", text)

    def test_both_name_the_prepare_command(self):
        for dep in (DATA_MOD, COMPILED_MOD):
            self.assertIn("--prepare df -t sil -p vs2026 -P base",
                          self._refusal_text(dep),
                          f"RQ-9: {dep}'s refusal must name a command that fixes it")


class DataModuleNoticeTests(unittest.TestCase):
    """build.data_only_in_tree_notice() - informational after A."""

    def test_with_all_explains_why_the_table_says_package(self):
        notice = adas_build.data_only_in_tree_notice(
            {DATA_MOD}, True, None)
        self.assertIsNotNone(notice)
        self.assertIn(DATA_MOD, notice)
        self.assertIn("No action needed", notice,
                      "after A there is nothing for the reader to run, so the line "
                      "must not tell them to run anything")

    def test_notice_names_no_command(self):
        notice = adas_build.data_only_in_tree_notice(
            {DATA_MOD}, True, None)
        self.assertNotIn("--prepare", notice,
                         "telling the user to --prepare something the build just "
                         "handled is the stale advice A removes")

    def test_silent_when_nothing_data_only(self):
        self.assertIsNone(adas_build.data_only_in_tree_notice(
            set(), True, None))

    def test_silent_when_the_user_never_asked_for_deps_in_tree(self):
        self.assertIsNone(adas_build.data_only_in_tree_notice(
            {DATA_MOD}, False, None))


class SourceGuardsTests(unittest.TestCase):
    """The comment corrections - pinned so the false reasoning cannot return."""

    def setUp(self):
        with open(adas_build.__file__, encoding="utf-8") as fh:
            self.src = fh.read()

    def test_the_false_pkg_only_is_empty_claim_is_gone(self):
        self.assertNotIn("so pkg_only is empty and this is a no-op then", self.src,
                         "the corrected comment must not come back - it is the "
                         "reasoning that hid this defect")
        self.assertNotIn("makes pkg_only empty, so this whole block is a no-op", self.src)

    # NS-50: any line - code OR comment - that puts the named-set complement
    # and `| data_only` together. The earlier literal-assignment grep missed
    # the prose form ("pkg_only is `(closure - total) | data_only`") that sat
    # in build.py asserting the defective formula as current (RV-4).
    FOLDED = re.compile(r"\(closure - total\).*\|\s*data_only")

    @classmethod
    def folded_lines(cls, src):
        return [line for line in src.splitlines() if cls.FOLDED.search(line)]

    def test_data_only_is_not_folded_back_into_pkg_only(self):
        self.assertEqual(self.folded_lines(self.src), [],
                         "folding named data modules back into pkg_only is the "
                         "defect itself - and a comment stating it as current "
                         "is how it comes back")

    def test_planted_the_guard_sees_both_the_code_and_the_prose_form(self):
        """A guard that only ever passes has proven nothing: it must catch the
        assignment AND the comment form that RV-4 found."""
        self.assertTrue(self.folded_lines("        pkg_only = (closure - total) | data_only"))
        self.assertTrue(self.folded_lines(
            "        # then. That is FALSE. pkg_only is `(closure - total) | data_only`"))


class OneImplementationTests(unittest.TestCase):
    """R-BUILD-1: setup.py --prepare and build.py must create-and-record through
    the SAME function, or the two halves drift (a creator that forgets the
    record leaves a binary NS-37 then refuses as unverifiable)."""

    def test_both_callers_use_conan_home_resolutions_helper(self):
        import conan_home_resolution
        self.assertTrue(hasattr(conan_home_resolution, "create_and_record_module"))
        with open(os.path.join(os.path.dirname(adas_build.__file__), "setup.py"),
                  encoding="utf-8") as fh:
            setup_src = fh.read()
        self.assertIn("create_and_record_module(", setup_src)
        self.assertIn("create_and_record_module(", self.build_src())

    def build_src(self):
        with open(adas_build.__file__, encoding="utf-8") as fh:
            return fh.read()

    def test_build_py_does_not_call_conan_create_directly_for_data(self):
        src = self.build_src()
        self.assertNotIn('"conan", "create"', src,
                         "a second create implementation in build.py is exactly the "
                         "drift this extraction prevents")
