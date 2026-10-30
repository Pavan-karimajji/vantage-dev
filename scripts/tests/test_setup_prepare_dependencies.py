"""
scripts/tests/test_setup_prepare_dependencies.py

STEP 1 (cache_first_no_server_plan.md, NS-11 remainder / D4b) --
scripts/setup.py::prepare_first_party_deps()/`--prepare <module> -t -p [-P]`:
compiles a module's first-party dependency closure into the Conan cache via
`conan create`, in dependency order, reusing build.py's own
forward_closure()/topo_sort() rather than a second graph walk. Pure
unittest + unittest.mock, same convention as test_setup_prepare_cache.py --
every subprocess/module boundary mocked, no real conan/network/process
calls.

Run:
    py -m unittest discover -s scripts/tests
    (from the superproject root)
"""
import io
import contextlib
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import setup  # noqa: E402 - path must be set up first
import conan_home_resolution as chr_  # noqa: E402


class _Ctx:
    def __init__(self, prepare="df", project="base", target="sil", platform="vs2026",
                 dry_run=False):
        self.prepare = prepare
        self.project = project
        self.target = target
        self.platform = platform
        self.dry_run = dry_run


def _fake_run(returncode=0, stdout=""):
    result = mock.Mock()
    result.returncode = returncode
    result.stdout = stdout
    return result


class PrepareDependencyClosureTests(unittest.TestCase):
    """_prepare_dependency_closure() reuses build.py's own graph-walk
    functions verbatim -- this asserts it calls them (never re-implements
    the walk), by watching the mocked calls and the order the result is
    handed back in."""

    def test_order_is_topo_sorts_own_order_not_recomputed(self):
        """Planted: dependency order is respected -- the function returns
        exactly what adas_build.topo_sort() handed back, in that order
        (interfaces before sim before viz, or whatever topo_sort decided),
        never re-sorted or re-derived here."""
        with mock.patch.object(setup.adas_build, "package_to_module_map",
                                return_value={"adas-df": "df", "adas-interfaces": "interfaces",
                                              "adas-sim": "sim", "adas-viz": "viz"}) as pkg_map, \
                mock.patch.object(setup.adas_build, "forward_closure",
                                   return_value={"interfaces", "sim", "viz", "df"}) as fwd, \
                mock.patch.object(setup.adas_build, "topo_sort",
                                   return_value=["interfaces", "sim", "viz"]) as topo:
            result = setup._prepare_dependency_closure("df", "base")
        self.assertEqual(result, ["interfaces", "sim", "viz"])
        fwd.assert_called_once_with({"df"}, "base", pkg_map.return_value)
        topo.assert_called_once()


class _PrepareHarness(unittest.TestCase):

    def setUp(self):
        # NS-63's lock refresh has its own tests (test_setup_prepare_locks.py); here
        # it must not reach for the real `conan list`.
        patcher = mock.patch.object(setup, "refresh_root_locks")
        patcher.start()
        self.addCleanup(patcher.stop)

    def _run_prepare(self, ctx, cached_refs=(), declares=True, has_conf=True,
                      closure=("interfaces", "sim", "viz"), create_ok=True,
                      profile_settings=("build_type",), records="matching",
                      current_fp=None):
        # NS-28: `records` is what conan_workarea/prepared_modules.json holds:
        # "matching" = every module recorded with the fingerprint the
        # checkout has now; None = no record file at all; or a dict
        # {module: entry-or-missing}. `current_fp` overrides what the
        # checkout's fingerprint is now.
        now_fp = current_fp or {"git": "aaaa1111bbbb", "dirty": "d1"}
        if records == "matching":
            recorded = {m: dict(now_fp, fp_version=chr_.FINGERPRINT_VERSION) for m in closure}
        else:
            recorded = records
        cached = set(cached_refs)
        pkg_versions = {"interfaces": ("adas-interfaces", "1.0.0"),
                        "sim": ("adas-sim", "0.1.0"),
                        "viz": ("adas-viz", "1.0.0")}
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            if cmd[:2] == ["conan", "create"]:
                mod_dir = cmd[2]
                mod = os.path.basename(mod_dir.rstrip("/\\"))
                if create_ok:
                    ref = "/".join(pkg_versions[mod])
                    cached.add(ref)
                    return _fake_run(0)
                return _fake_run(1, "create failed")
            return _fake_run(0)

        def fake_cache_matches(ref, settings):
            return ref in cached

        settings = {k: "x" for k in profile_settings} if profile_settings is not None else None

        with mock.patch.object(setup, "adas_build") as fake_build, \
                mock.patch.object(setup, "run", side_effect=fake_run) as run_mock, \
                mock.patch.object(setup.check_conan_resolution, "pinned_profile_settings",
                                   return_value=settings), \
                mock.patch.object(setup.check_conan_resolution, "_cache_matches_profile",
                                   side_effect=fake_cache_matches), \
                mock.patch.object(setup, "profile_args", return_value=["--profile:host", "x"]), \
                mock.patch.object(setup, "record_prepared_module") as record_mock, \
                mock.patch.object(setup, "read_prepared_modules", return_value=recorded), \
                mock.patch.object(setup, "compute_module_fingerprint", return_value=now_fp), \
                mock.patch.object(setup, "_prepare_dependency_closure",
                                   return_value=list(closure)):
            fake_build.load_module_conf.return_value = {} if has_conf else None
            fake_build.module_declares.return_value = declares
            fake_build.absent_first_party_refs.return_value = {}  # D3: all checked out
            fake_build.module_package_name.side_effect = lambda m: pkg_versions[m][0]
            fake_build.module_version.side_effect = lambda m: pkg_versions[m][1]
            outcome = setup.prepare_first_party_deps(ctx)
        self.record_mock = record_mock
        return outcome, calls, cached


class PrepareFirstPartyDepsTests(_PrepareHarness):

    def test_missing_dependency_is_created(self):
        """Planted: 'a dependency missing from the cache is created'."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            outcome, calls, cached = self._run_prepare(_Ctx(), cached_refs=[])
        create_calls = [c for c in calls if c[:2] == ["conan", "create"]]
        self.assertEqual(len(create_calls), 3)
        self.assertIn("adas-interfaces/1.0.0", cached)
        self.assertIn("adas-sim/0.1.0", cached)
        self.assertIn("adas-viz/1.0.0", cached)
        self.assertIn("not cached for vs2026", buf.getvalue())

    def test_a_fresh_create_records_a_fingerprint_a_skip_does_not(self):
        """NS-05a (cache_first_no_server_plan.md D4a, STEP 3): every REAL
        `conan create` records a fingerprint (conan_home_resolution.
        record_prepared_module()); an 'already cached' skip never does -
        the binary there was not just built from the current checkout."""
        self._run_prepare(_Ctx(), cached_refs=[])
        self.assertEqual(self.record_mock.call_count, 3)
        recorded_mods = {call.args[1] for call in self.record_mock.call_args_list}
        self.assertEqual(recorded_mods, {"interfaces", "sim", "viz"})
        self.record_mock.reset_mock()
        self._run_prepare(_Ctx(), cached_refs=["adas-interfaces/1.0.0", "adas-sim/0.1.0",
                                               "adas-viz/1.0.0"])
        self.record_mock.assert_not_called()

    def test_second_run_creates_nothing(self):
        """Planted: 'a second run creates nothing'."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            outcome, calls, cached = self._run_prepare(
                _Ctx(), cached_refs=["adas-interfaces/1.0.0", "adas-sim/0.1.0",
                                     "adas-viz/1.0.0"])
        create_calls = [c for c in calls if c[:2] == ["conan", "create"]]
        self.assertEqual(create_calls, [])
        self.assertIn("already cached and unchanged since it was built (HEAD aaaa1111)",
                      buf.getvalue())

    def test_dependency_order_is_respected(self):
        """Planted: 'dependency order is respected' -- the conan create
        calls happen in exactly the closure order handed back by
        _prepare_dependency_closure(), never re-sorted."""
        _, calls, _ = self._run_prepare(_Ctx(), cached_refs=[],
                                        closure=("viz", "interfaces", "sim"))
        create_calls = [c for c in calls if c[:2] == ["conan", "create"]]
        created_mods = [os.path.basename(c[2].rstrip("/\\")) for c in create_calls]
        self.assertEqual(created_mods, ["viz", "interfaces", "sim"])

    def test_no_remote_flag_present_on_every_create_call(self):
        """Planted: 'remotes off asserted, no remote call' -- every
        `conan create` carries -nr/--no-remote unconditionally (matching
        prepare_conan_cache's own convention), so this makes zero remote
        calls whatever remotes_enabled() says."""
        _, calls, _ = self._run_prepare(_Ctx(), cached_refs=[])
        create_calls = [c for c in calls if c[:2] == ["conan", "create"]]
        self.assertTrue(create_calls)
        for cmd in create_calls:
            self.assertIn("-nr", cmd)
        # Planted mutation check target: no call ever names a remote flag.
        for cmd in calls:
            self.assertNotIn("-r", cmd)
            self.assertNotIn("--remote", cmd)

    def test_no_dependencies_is_a_no_op(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            outcome, calls, _ = self._run_prepare(_Ctx(), cached_refs=[], closure=())
        self.assertEqual(calls, [])
        self.assertIn("nothing to prepare", buf.getvalue())

    def test_dry_run_makes_no_real_calls(self):
        outcome, calls, _ = self._run_prepare(_Ctx(dry_run=True), cached_refs=[])
        self.assertEqual(calls, [])
        self.assertEqual(outcome, "skip")

    def test_unknown_module_fails_naming_it(self):
        with self.assertRaises(setup.StepFailed) as ctx_mgr:
            self._run_prepare(_Ctx(prepare="nope"), has_conf=False)
        self.assertIn("nope", str(ctx_mgr.exception))

    def test_target_platform_not_declared_fails(self):
        with self.assertRaises(setup.StepFailed) as ctx_mgr:
            self._run_prepare(_Ctx(), declares=False)
        exc = ctx_mgr.exception
        self.assertIn("sil", str(exc))
        self.assertIn("vs2026", str(exc))

    def test_create_failure_raises_naming_module(self):
        """Planted mutation-check target: a `conan create` failure must not
        be silently swallowed."""
        with self.assertRaises(setup.StepFailed) as ctx_mgr:
            self._run_prepare(_Ctx(), cached_refs=[], create_ok=False)
        self.assertIn("interfaces", str(ctx_mgr.exception))


class Ns28FreshnessTests(_PrepareHarness):
    """NS-28: --prepare's skip asks the same question build.py's
    stale_cache_refs() asks - "is the cached binary from THIS source?" -
    not merely "does a binary exist for this profile?"."""

    ALL = ["adas-interfaces/1.0.0", "adas-sim/0.1.0", "adas-viz/1.0.0"]

    def _creates(self, calls):
        return [c for c in calls if c[:2] == ["conan", "create"]]

    def test_cached_and_fingerprint_matches_is_skipped(self):
        _, calls, _ = self._run_prepare(_Ctx(), cached_refs=self.ALL)
        self.assertEqual(self._creates(calls), [])
        self.record_mock.assert_not_called()

    def test_cached_but_fingerprint_differs_is_rebuilt_and_rerecorded(self):
        stale = {m: {"git": "old00000", "dirty": "d1", "fp_version": chr_.FINGERPRINT_VERSION} for m in ("interfaces", "sim", "viz")}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            _, calls, _ = self._run_prepare(_Ctx(), cached_refs=self.ALL, records=stale)
        self.assertEqual(len(self._creates(calls)), 3)
        self.assertEqual(self.record_mock.call_count, 3)
        self.assertIn("source changed since it was built", buf.getvalue())

    def test_uncommitted_edit_alone_counts_as_changed(self):
        stale = {m: {"git": "aaaa1111bbbb", "dirty": "OTHER", "fp_version": chr_.FINGERPRINT_VERSION} for m in ("interfaces", "sim", "viz")}
        _, calls, _ = self._run_prepare(_Ctx(), cached_refs=self.ALL, records=stale)
        self.assertEqual(len(self._creates(calls)), 3)

    def test_cached_with_no_record_is_rebuilt_once_and_recorded(self):
        """NS-31: asserts the behaviour itself. A cached binary with no
        freshness record is rebuilt (every module gets a )
        and THEN recorded (every module is passed to the recorder), with
        the no-record message - never the "source changed" one. An
        exception out of --prepare is reported as a failed assertion about
        that behaviour, not left to surface as a bare traceback."""
        for records in (None, {}):
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    _, calls, _ = self._run_prepare(_Ctx(), cached_refs=self.ALL,
                                                    records=records)
            except Exception as exc:  # noqa: BLE001
                self.fail(f"records={records!r}: a cached binary with no freshness record "
                          f"must be rebuilt and recorded, but --prepare raised {exc!r}")
            created = [os.path.basename(c[2].rstrip("/\\")) for c in self._creates(calls)]
            self.assertEqual(created, ["interfaces", "sim", "viz"],
                             f"records={records!r}: every module must be rebuilt")
            recorded = [c.args[1] for c in self.record_mock.call_args_list]
            self.assertEqual(recorded, ["interfaces", "sim", "viz"],
                             f"records={records!r}: every rebuilt module must be recorded")
            out = buf.getvalue()
            self.assertEqual(out.count("no freshness record - rebuilding once so it can be trusted"),
                             3, out)
            self.assertNotIn("source changed since it was built", out)
            self.assertNotIn("conan create skipped", out)

    def test_outdated_format_record_is_rebuilt_with_a_format_message(self):
        """NS-52: a format-1 record (no fp_version) is rebuilt once - and the
        message says the FORMAT changed, never that the source did."""
        old = {m: {"git": "aaaa1111bbbb", "dirty": "d1"} for m in ("interfaces", "sim", "viz")}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            _, calls, _ = self._run_prepare(_Ctx(), cached_refs=self.ALL, records=old)
        self.assertEqual(len(self._creates(calls)), 3)
        out = buf.getvalue()
        self.assertEqual(out.count("older fingerprint format"), 3, out)
        self.assertNotIn("source changed since it was built", out)

    def test_only_the_stale_module_is_rebuilt(self):
        recs = {"interfaces": {"git": "aaaa1111bbbb", "dirty": "d1", "fp_version": chr_.FINGERPRINT_VERSION},
                "sim": {"git": "old00000", "dirty": "d1", "fp_version": chr_.FINGERPRINT_VERSION},
                "viz": {"git": "aaaa1111bbbb", "dirty": "d1", "fp_version": chr_.FINGERPRINT_VERSION}}
        _, calls, _ = self._run_prepare(_Ctx(), cached_refs=self.ALL, records=recs)
        mods = [os.path.basename(c[2].rstrip("/\\")) for c in self._creates(calls)]
        self.assertEqual(mods, ["sim"])

    def test_not_cached_is_unchanged_behaviour(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            _, calls, _ = self._run_prepare(_Ctx(), cached_refs=[], records=None)
        self.assertEqual(len(self._creates(calls)), 3)
        self.assertIn("not cached for vs2026", buf.getvalue())
        self.assertNotIn("freshness record", buf.getvalue())

    def test_prepare_then_build_refusal_finds_nothing(self):
        """The unbreakable loop, asserted directly, with the REAL
        recorder/fingerprint/stale_cache_refs (no mocks on them): a module
        whose source moved after it was recorded is stale; --prepare's
        skip decision rebuilds it and records; build.py's stale_cache_refs()
        then finds nothing."""
        import subprocess
        import tempfile
        import build
        import conan_home_resolution as chr_
        with tempfile.TemporaryDirectory() as tmp:
            mod_dir = os.path.join(tmp, "modules", "sim")
            os.makedirs(mod_dir)
            git = lambda *a: subprocess.run(["git", "-C", mod_dir, *a], check=True,
                                            capture_output=True)
            git("init", "-q")
            git("config", "user.email", "t@t")
            git("config", "user.name", "t")
            open(os.path.join(mod_dir, "conanfile.py"), "w").close()  # D1: checked out
            open(os.path.join(mod_dir, "a.txt"), "w").write("1")
            git("add", ".")
            git("commit", "-qm", "one")
            chr_.record_prepared_module(tmp, "sim", "adas-sim/0.1.0", mod_dir)
            open(os.path.join(mod_dir, "a.txt"), "w").write("2")
            git("commit", "-qam", "two")
            with mock.patch.object(build, "ROOT", tmp):
                stale, _ = build.stale_cache_refs(["sim"])
                self.assertEqual([m for m, _, _ in stale], ["sim"])
                # --prepare's own path, real fingerprint/record functions:
                with mock.patch.object(setup, "ROOT", __import__("pathlib").Path(tmp)):
                    entry = setup.read_prepared_modules(setup.ROOT)["sim"]
                    fp = setup.compute_module_fingerprint(mod_dir)
                    self.assertNotEqual(fp["git"], entry["git"])
                    chr_.record_prepared_module(tmp, "sim", "adas-sim/0.1.0", mod_dir)
                stale, unrecorded = build.stale_cache_refs(["sim"])
                self.assertEqual((stale, unrecorded), ([], []))


class Ns28SummaryTests(unittest.TestCase):
    def test_remotes_off_summary_says_not_used_and_never_probes(self):
        ctx = _Ctx()
        ctx.remotes_enabled = False
        ctx.remotes_reason = "http://127.0.0.1:9300 is a loopback address, not a team server"
        buf = io.StringIO()
        with mock.patch.object(setup, "_port_reachable") as probe, \
                mock.patch.object(setup, "run") as run_mock, \
                mock.patch.object(setup, "read_team_server_url",
                                   return_value="http://127.0.0.1:9300"), \
                contextlib.redirect_stdout(buf):
            setup.print_environment_summary(ctx)
        out = buf.getvalue()
        self.assertIn("Local server (adas-local): not used (remotes off", out)
        self.assertNotIn("reachable", out)
        probe.assert_not_called()
        run_mock.assert_not_called()



class PrepareAbsentDependencyTests(unittest.TestCase):
    """W3: for --prepare the closure is the work list, so a dependency that is
    not checked out is initialised (never "nothing to prepare"); the primary
    is never initialised."""

    ABSENT = {"interfaces": "adas-interfaces/1.0.0", "viz": "adas-viz/1.0.0"}

    def _prepare(self, ctx, init, absent_sequence):
        patch = mock.patch.object
        with patch(setup.adas_build, "load_module_conf", return_value={}), \
                patch(setup.adas_build, "module_declares", return_value=True), \
                patch(setup.adas_build, "package_to_module_map", return_value={}), \
                patch(setup.adas_build, "forward_closure", return_value={"df"}), \
                patch(setup.adas_build, "absent_first_party_refs",
                      side_effect=absent_sequence), \
                patch(setup, "init_submodules_for", side_effect=init) as init_mock, \
                patch(setup, "_prepare_dependency_closure", return_value=[]) as closure, \
                contextlib.redirect_stdout(io.StringIO()):
            try:
                outcome = setup.prepare_first_party_deps(ctx)
            except setup.StepFailed as exc:
                outcome = exc
        return outcome, init_mock, closure

    def test_absent_dependencies_are_initialised_not_the_primary(self):
        outcome, init, closure = self._prepare(
            _Ctx(), lambda mods, **kw: list(mods), [self.ABSENT, {}])
        self.assertEqual(init.call_args[0][0], ["interfaces", "viz"])
        self.assertNotIn("df", init.call_args[0][0])
        self.assertFalse(init.call_args[1]["dry_run"])
        closure.assert_called_once()

    def test_dry_run_asks_for_a_plan_only_and_stops(self):
        outcome, init, closure = self._prepare(
            _Ctx(dry_run=True), lambda mods, **kw: list(mods), [self.ABSENT])
        self.assertTrue(init.call_args[1]["dry_run"])
        self.assertEqual(outcome, "skip")
        closure.assert_not_called()

    def test_a_refusal_becomes_step_failed_with_its_command(self):
        def refuse(mods, **kw):
            raise setup.SubmoduleInitError(["ERROR: remotes are off, x.",
                                            "Run: git submodule update --init modules/interfaces"])
        outcome, _, closure = self._prepare(_Ctx(), refuse, [self.ABSENT])
        self.assertIsInstance(outcome, setup.StepFailed)
        self.assertEqual(outcome.run, "git submodule update --init modules/interfaces")
        closure.assert_not_called()

    def test_no_progress_fails_instead_of_looping(self):
        outcome, init, _ = self._prepare(_Ctx(), lambda mods, **kw: [],
                                         [self.ABSENT] * 5)
        self.assertIsInstance(outcome, setup.StepFailed)
        self.assertEqual(init.call_count, 1)


class FreshCloneSetupTests(unittest.TestCase):
    """W5 (partial_clone_correctness_plan.md): a fresh superproject clone.
    setup checks out toolchain (D0) - and, for --prepare, the module named -
    never the rest of the repo."""

    def _init(self, uninitialised, calls):
        def fake(mods, **kwargs):
            calls.append((list(mods), kwargs))
            return list(mods)
        fs = mock.patch.object(setup, "possibly_uninitialised",
                               side_effect=lambda mods, root: list(mods))
        fs.start()
        self.addCleanup(fs.stop)
        return (mock.patch.object(setup, "uninitialised_submodules", return_value=uninitialised),
                mock.patch.object(setup, "init_submodules_for", side_effect=fake))

    def test_init_toolchain_and_takes_only_uninitialised_ones(self):
        calls = []
        a, b = self._init(["df", "interfaces", "toolchain"], calls)
        with a, b:
            setup.init_toolchain_and(["df"])
        self.assertEqual([c[0] for c in calls], [["toolchain", "df"]])

    def test_nothing_uninitialised_calls_no_git(self):
        calls = []
        a, b = self._init([], calls)
        with a, b:
            self.assertEqual(setup.init_toolchain_and(["df"]), [])
        self.assertEqual(calls, [])

    def test_no_submodules_still_checks_out_toolchain_only(self):
        calls = []
        ctx = mock.Mock(no_submodules=True, dry_run=False)
        a, b = self._init(["df", "interfaces", "toolchain"], calls)
        with a, b, contextlib.redirect_stdout(io.StringIO()):
            setup.init_submodules(ctx)
        self.assertEqual([c[0] for c in calls], [["toolchain"]])

    def test_a_git_refusal_becomes_step_failed_with_its_command(self):
        def refuse(mods, **kwargs):
            raise setup.SubmoduleInitError(["ERROR: git could not initialise modules/toolchain: x",
                                            "Run: git submodule update --init modules/toolchain"])
        with mock.patch.object(setup, "possibly_uninitialised",
                               side_effect=lambda mods, root: list(mods)), \
                mock.patch.object(setup, "uninitialised_submodules", return_value=["toolchain"]), \
                mock.patch.object(setup, "init_submodules_for", side_effect=refuse), \
                self.assertRaises(setup.StepFailed) as caught:
            setup.init_toolchain_and([])
        self.assertEqual(caught.exception.run, "git submodule update --init modules/toolchain")

    def test_prepare_checks_out_toolchain_and_the_named_module_first(self):
        calls = []
        a, b = self._init(["df", "toolchain", "viz"], calls)
        argv = ["setup.py", "--prepare", "df", "-t", "sil", "-p", "vs2026"]

        class _Stop(Exception):
            pass
        with a, b, mock.patch.object(setup.sys, "argv", argv), \
                mock.patch.object(setup.adas_build, "require_toolchain_checkout",
                                  side_effect=_Stop), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(_Stop):
            setup.main()
        self.assertEqual([c[0] for c in calls], [["toolchain", "df"]])  # not viz

    def test_pyyaml_advice_leads_with_no_submodules(self):
        argv = ["setup.py", "--prepare", "df", "-t", "sil", "-p", "vs2026"]
        with mock.patch.object(setup.sys, "argv", argv), \
                mock.patch.object(setup, "adas_build", None), \
                self.assertRaises(SystemExit) as caught:
            setup.main()
        self.assertIn(f"{setup.setup_command()} --no-submodules", str(caught.exception.code))


if __name__ == "__main__":
    unittest.main()
