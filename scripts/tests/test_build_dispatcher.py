"""scripts/tests/test_build_dispatcher.py

Unit tests for scripts/build.py's WP-20 changes (conan_environment_plan.md
§7 CE-24): the conan_workarea/ rename and the aggregate folder name
redesign for parseability. Pure unittest, no real conan/cmake/subprocess
calls.

Run:
    py -m unittest discover -s scripts/tests
    (from the superproject root)
"""
import contextlib
import io
import json
import os
import sys
import unittest
import unittest.mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import build as build_dispatcher  # noqa: E402 - path must be set up first
import conan_home_resolution as chr_  # noqa: E402


class WsFolderNameParseableTests(unittest.TestCase):
    """§7 CE-24 / AB-03 / RP-04: the root folder name is seven FIXED fields,
    splittable by position with no prior knowledge of module names, last
    field `solo` (delegate) or `agg` (aggregate, any tick list), no hash."""

    def _fields(self, name):
        return name.split("-", 6)

    def test_solo_scope_when_no_with_flags(self):
        name = build_dispatcher.ws_folder_name(
            "sil", "vs2026", "base", "df", with_mods=None, with_all=False)
        fields = self._fields(name)
        self.assertEqual(fields, ["build", "sil", "vs2026", "base", "df", "pkg", "solo"])

    def test_all_scope_is_agg(self):
        name = build_dispatcher.ws_folder_name(
            "sil", "vs2026", "base", "df", with_mods=None, with_all=True)
        self.assertEqual(self._fields(name)[-1], "agg")

    def test_with_scope_is_agg_whatever_the_tick_list(self):
        """RP-04: PASS - one module or five, the name is the same seven
        fields ending `agg`, so a different tick list reuses the folder.
        FAIL (superseded AB-03 naming): `with<N>-<hash>` left one folder per
        tick list ever tried."""
        name_one = build_dispatcher.ws_folder_name(
            "sil", "vs2026", "base", "df", with_mods=["mathlib"], with_all=False)
        name_many = build_dispatcher.ws_folder_name(
            "sil", "vs2026", "base", "df",
            with_mods=["mathlib", "interfaces", "shared_config", "viz", "sim"], with_all=False)
        self.assertEqual(name_one, name_many)
        self.assertEqual(self._fields(name_one),
                         ["build", "sil", "vs2026", "base", "df", "pkg", "agg"])
        self.assertNotRegex(name_one, r"[0-9a-f]{8}|with\d")

    def test_planted_violation_solo_and_agg_are_different_folders(self):
        solo = build_dispatcher.ws_folder_name(
            "sil", "vs2026", "base", "df", with_mods=None, with_all=False)
        agg = build_dispatcher.ws_folder_name(
            "sil", "vs2026", "base", "df", with_mods=["viz"], with_all=False)
        self.assertNotEqual(solo, agg)

    def test_project_and_platform_prevent_collision(self):
        """plan.md items 13/14's own reason for including project/platform
        at all - base df and cus1 df, or vs2026 df and ubuntu_gcc df, must
        never collide onto one folder."""
        base_name = build_dispatcher.ws_folder_name(
            "sil", "vs2026", "base", "df", with_mods=None, with_all=False)
        cus1_name = build_dispatcher.ws_folder_name(
            "sil", "vs2026", "cus1", "df", with_mods=None, with_all=False)
        wsl_name = build_dispatcher.ws_folder_name(
            "sil", "ubuntu_gcc", "base", "df", with_mods=None, with_all=False)
        self.assertNotEqual(base_name, cus1_name)
        self.assertNotEqual(base_name, wsl_name)


class WsFolderNameModeFieldTests(unittest.TestCase):
    """AB-03 / D5 / NS-32: <mode> is a fixed field, the literal `pkg`, before
    <scope> - develop mode is gone, so there is no `dev` to select."""

    def _name(self):
        return build_dispatcher.ws_folder_name(
            "sil", "vs2026", "base", "df", with_mods=["mathlib"], with_all=False)

    def test_mode_field_is_the_fixed_literal_pkg(self):
        self.assertEqual(self._name().split("-", 6)[5], "pkg")

    def test_planted_violation_legacy_six_field_name_has_no_mode_field(self):
        legacy = "build-sil-vs2026-base-df-with1-0274021b"
        self.assertNotIn(legacy.split("-", 6)[5], ("dev", "pkg"))
        self.assertNotIn(legacy.split("-", 6)[6], ("solo", "agg"))
        self.assertIn(self._name().split("-", 6)[5], ("dev", "pkg"))


class DelegateBuildDirTests(unittest.TestCase):
    """AB-11 / RD-03 (remove_develop_mode_plan.md): package mode is the
    only mode - a root delegate always relocates the build dir and logs
    centrally, named after it."""

    def _run(self, no_log=False, module="df"):
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "modules", module, "scripts"))
            open(os.path.join(root, "modules", module, "scripts", "build.py"), "w").close()
            logs = os.path.join(root, "conan_workarea", "logs")
            os.makedirs(logs)
            seen = {}

            def fake_run(cmd, cwd=None):
                seen["cmd"] = cmd
                name = os.path.basename(cmd[cmd.index("--build-dir") + 1])
                log_dir = cmd[cmd.index("--log-dir") + 1]
                os.makedirs(cmd[cmd.index("--build-dir") + 1], exist_ok=True)
                os.makedirs(log_dir, exist_ok=True)
                open(os.path.join(log_dir, name + ".log"), "w").close()
                return unittest.mock.Mock(returncode=0)

            patch = unittest.mock.patch.object
            with patch(build_dispatcher, "ROOT", root), \
                    patch(build_dispatcher, "apply_conan_home"), \
                    patch(build_dispatcher, "package_to_module_map", return_value={}), \
                    patch(build_dispatcher, "forward_closure", return_value={module}), \
                    patch(build_dispatcher.subprocess, "run", side_effect=fake_run):
                ok = build_dispatcher.run_delegate(module, "base", "sil", "vs2026", False, no_log)
            return ok, seen["cmd"], sorted(os.listdir(logs)), root

    def _child_env(self, remotes_state):
        """NS-46: the env the delegate child is launched with (None = inherited)."""
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "modules", "df", "scripts"))
            open(os.path.join(root, "modules", "df", "scripts", "build.py"), "w").close()
            os.makedirs(os.path.join(root, "conan_workarea", "logs"))
            seen = {}

            def fake_run(cmd, cwd=None, env=None):
                seen["env"] = env
                return unittest.mock.Mock(returncode=0)

            patch = unittest.mock.patch.object
            with patch(build_dispatcher, "ROOT", root), \
                    patch(build_dispatcher, "apply_conan_home"), \
                    patch(build_dispatcher, "package_to_module_map", return_value={}), \
                    patch(build_dispatcher, "forward_closure", return_value={"df"}), \
                    patch(build_dispatcher.subprocess, "run", side_effect=fake_run):
                build_dispatcher.run_delegate("df", "base", "sil", "vs2026", False, True,
                                              remotes_state=remotes_state)
            return seen["env"]

    def test_delegate_forwards_the_resolved_remotes_switch(self):
        """NS-46 (RQ-5): the child decides remotes exactly as the root did.
        Planted: drop the env forwarding and both assertions fail."""
        self.assertEqual(self._child_env(False)["ADAS_REMOTES_ENABLED"], "off")
        self.assertEqual(self._child_env(True)["ADAS_REMOTES_ENABLED"], "on")
        self.assertIsNone(self._child_env(None))

    def test_main_passes_its_switch_to_the_delegate(self):
        patch = unittest.mock.patch
        with patch.object(build_dispatcher.sys, "argv",
                          ["build.py", "df", "-t", "sil", "-p", "vs2026", "--remotes", "off"]), \
                patch.object(build_dispatcher, "all_projects", return_value=["base"]), \
                patch.object(build_dispatcher, "is_valid_module", return_value=True), patch.object(build_dispatcher, "absent_first_party_refs", return_value={}), \
                patch.object(build_dispatcher, "run_delegate", return_value=True) as dele, \
                patch("sys.stdout", io.StringIO()):
            with self.assertRaises(SystemExit):
                build_dispatcher.main()
        self.assertIs(dele.call_args.kwargs.get("remotes_state"), False)

    def test_package_mode_keeps_the_relocated_build_dir_and_log_name(self):
        _, cmd, logs, root = self._run()
        self.assertEqual(cmd[cmd.index("--build-dir") + 1],
                         os.path.join(root, "conan_workarea", "build-sil-vs2026-base-df-pkg-solo"))
        self.assertEqual(logs, ["build-sil-vs2026-base-df-pkg-solo.log"])

    def test_planted_violation_two_modules_same_target_platform_never_share_a_build_dir(self):
        _, cmd_a, _, _ = self._run(module="df")
        _, cmd_b, _, _ = self._run(module="mathlib")
        dir_a = cmd_a[cmd_a.index("--build-dir") + 1]
        dir_b = cmd_b[cmd_b.index("--build-dir") + 1]
        self.assertNotEqual(dir_a, dir_b)

    def test_package_delegate_writes_manifest_into_conan_workarea(self):
        """RP-05: a package delegate leaves ws_manifest.txt (with: (none))
        in its relocated build folder, never under modules/."""
        import tempfile
        with tempfile.TemporaryDirectory() as r2:
            os.makedirs(os.path.join(r2, "modules", "df", "scripts"))
            open(os.path.join(r2, "modules", "df", "scripts", "build.py"), "w").close()
            os.makedirs(os.path.join(r2, "conan_workarea", "logs"))
            with unittest.mock.patch.object(build_dispatcher, "ROOT", r2),                     unittest.mock.patch.object(build_dispatcher, "apply_conan_home"),                     unittest.mock.patch.object(build_dispatcher, "package_to_module_map", return_value={}),                     unittest.mock.patch.object(build_dispatcher, "forward_closure", return_value={"df"}),                     unittest.mock.patch.object(build_dispatcher.subprocess, "run",
                                               side_effect=lambda cmd, cwd=None: (
                                                   os.makedirs(cmd[cmd.index("--build-dir") + 1], exist_ok=True),
                                                   unittest.mock.Mock(returncode=0))[1]):
                build_dispatcher.run_delegate("df", "base", "sil", "vs2026", False, True)
            with open(os.path.join(r2, "conan_workarea", "build-sil-vs2026-base-df-pkg-solo",
                                   "ws_manifest.txt"), encoding="utf-8") as f:
                text = f.read()
            self.assertIn("with: (none)", text)
            self.assertIn("mode: package", text)
            self.assertIn("scope: solo", text)
            self.assertFalse(os.path.exists(os.path.join(r2, "modules", "df", "conan_workarea")))


class ConanWorkareaRenameTests(unittest.TestCase):
    """§7 CE-24: ws/ is renamed to conan_workarea/, not aliased."""

    def test_delegate_build_dir_uses_conan_workarea(self):
        # A temporary directory as the root: where this checkout happens to live (a `ws` folder in its
        # own path, as under C:\ws\) must not decide whether the build dir is under conan_workarea.
        import tempfile
        with tempfile.TemporaryDirectory() as root, \
                unittest.mock.patch.object(build_dispatcher, "ROOT", root):
            path = build_dispatcher.delegate_build_dir("df", "base", "sil", "vs2026")
            self.assertIn(os.path.join("conan_workarea", "build-sil-vs2026-base-df-pkg-solo"), path)
            self.assertTrue(path.startswith(root), path)
            self.assertNotIn(f"{os.sep}ws{os.sep}", path[len(root):])

    def test_ws_logs_dir_uses_conan_workarea(self):
        path = build_dispatcher.ws_logs_dir()
        self.assertIn(os.path.join("conan_workarea", "logs"), path)


def _conf(requires=None, ptype="shared-library"):
    return {"recipe": {"type": ptype},
            "variants": {"base": {"requires": list(requires or [])}}}


class _FakeRepo(unittest.TestCase):
    """Mock module confs + versions: no real Conan, no real modules."""

    CONFS = {}
    VERSIONS = {}

    def setUp(self):
        import copy
        self.CONFS = copy.deepcopy(type(self).CONFS)  # tests mutate; never leak
        self.VERSIONS = dict(type(self).VERSIONS)
        self.pkg_map = {f"adas-{m}": m for m in self.CONFS}
        for target, fake in (
                ("load_module_conf", lambda mod: self.CONFS.get(mod)),
                ("module_version", lambda mod: self.VERSIONS.get(mod)),
                ("module_package_name", lambda mod: f"adas-{mod}" if mod in self.CONFS else None)):
            patcher = unittest.mock.patch.object(build_dispatcher, target, side_effect=fake)
            patcher.start()
            self.addCleanup(patcher.stop)


class ModuleVersionTests(unittest.TestCase):
    """AB-06 / D3: the same source base_recipe.py's set_version() reads."""

    def _version_in(self, cmake, version_file=None):
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            mod_dir = os.path.join(root, "modules", "m")
            os.makedirs(mod_dir)
            with open(os.path.join(mod_dir, "CMakeLists.txt"), "w") as f:
                f.write(cmake)
            if version_file is not None:
                with open(os.path.join(mod_dir, "VERSION"), "w") as f:
                    f.write(version_file)
            with unittest.mock.patch.object(build_dispatcher, "ROOT", root), \
                    unittest.mock.patch.object(build_dispatcher, "module_package_name",
                                               return_value="adas-m"):
                return build_dispatcher.module_version("m")

    def test_reads_cmake_project_version(self):
        self.assertEqual(self._version_in("project(adas-m VERSION 1.2.3 LANGUAGES CXX)"), "1.2.3")

    def test_falls_back_to_version_file(self):
        self.assertEqual(self._version_in("project(adas-m LANGUAGES CXX)", "0.4.0\n"), "0.4.0")

    def test_planted_violation_no_version_anywhere_is_none_not_a_guess(self):
        self.assertIsNone(self._version_in("project(adas-m LANGUAGES CXX)"))


class VersionAgreementViolationsTests(_FakeRepo):
    """AB-07: requested versions identical across requesters and equal to the
    checkout's module_version()."""

    CONFS = {
        "df": _conf(["adas-mathlib/1.2.0", "adas-sim/0.1.0"]),
        "sim": _conf(["adas-mathlib/1.1.0"]),
        "mathlib": _conf(),
    }
    VERSIONS = {"df": "0.1.0", "sim": "0.1.0", "mathlib": "1.2.0"}

    def _check(self, closure=("df", "sim", "mathlib")):
        return build_dispatcher.version_agreement_violations(set(closure), "base", self.pkg_map)

    def test_planted_diamond_df_1_2_0_vs_sim_1_1_0_is_refused(self):
        """df->mathlib 1.2.0 and sim->mathlib 1.1.0: sim's request matches
        neither the other requester nor the checkout (1.2.0)."""
        bad = self._check()
        self.assertIn(("adas-mathlib", "sim", "1.1.0", "1.2.0"), bad)
        # the disagreement is reported from both ends (df sees sim's 1.1.0)
        self.assertIn(("adas-mathlib", "df", "1.2.0", "1.1.0"), bad)

    def test_planted_requester_disagreement_when_checkout_matches_neither_names_both(self):
        self.VERSIONS["mathlib"] = "9.9.9"
        bad = self._check()
        self.assertEqual({v[1] for v in bad if v[0] == "adas-mathlib"}, {"df", "sim"})

    def test_agreeing_versions_pass(self):
        self.CONFS["sim"] = _conf(["adas-mathlib/1.2.0"])
        self.assertEqual(self._check(), [])

    def test_agreeing_but_stale_vs_checkout_is_refused(self):
        self.CONFS["sim"] = _conf(["adas-mathlib/1.2.0"])
        self.VERSIONS["mathlib"] = "1.3.0"
        self.assertEqual(len(self._check()), 2)

    def test_third_party_refs_are_ignored(self):
        self.CONFS["df"] = _conf(["adas-mathlib/1.2.0", "protobuf/3.21.12"])
        self.CONFS["sim"] = _conf(["adas-mathlib/1.2.0", "protobuf/4.0.0"])
        self.assertEqual(self._check(), [])


class ReverseRebuildViolationsTests(_FakeRepo):
    """AB-05 / D2: rebuilt => its users rebuilt; --with Y never forces Y's deps;
    pure-data modules exempt as X."""

    CONFS = {
        "df": _conf(["adas-viz/1.0.0", "adas-mathlib/1.0.0", "adas-shared-config/1.0.0"]),
        "viz": _conf(["adas-mathlib/1.0.0"]),
        "mathlib": _conf(),
        "shared-config": _conf(ptype="unknown"),
    }
    CLOSURE = {"df", "viz", "mathlib", "shared-config"}

    def _check(self, total):
        return build_dispatcher.reverse_rebuild_violations(
            set(total), self.CLOSURE, "base", self.pkg_map)

    def test_planted_with_mathlib_but_user_viz_not_rebuilt_is_refused(self):
        self.assertEqual(self._check({"df", "mathlib"}), [("mathlib", "viz")])

    def test_with_mathlib_and_viz_passes(self):
        self.assertEqual(self._check({"df", "mathlib", "viz"}), [])

    def test_with_viz_alone_does_not_force_its_dependency(self):
        self.assertEqual(self._check({"df", "viz"}), [])

    def test_pure_data_module_is_exempt_as_rebuilt(self):
        self.assertEqual(self._check({"df", "shared-config"}), [])

    def test_solo_primary_never_violates(self):
        self.assertEqual(self._check({"df"}), [])

    def test_rebuild_closure_grows_total_to_include_every_user(self):
        got = build_dispatcher.rebuild_closure({"df", "mathlib"}, self.CLOSURE, "base", self.pkg_map)
        self.assertEqual(got, {"df", "mathlib", "viz"})

    def test_rebuild_closure_leaves_a_consistent_set_alone(self):
        got = build_dispatcher.rebuild_closure({"df", "viz"}, self.CLOSURE, "base", self.pkg_map)
        self.assertEqual(got, {"df", "viz"})


def _node(ref, binary, recipe="Cache"):
    return {"ref": ref + "#rev0", "binary": binary, "recipe": recipe}


def _graph(*nodes):
    graph = {"0": {"ref": "", "recipe": "Consumer"}}
    graph.update({str(i + 1): n for i, n in enumerate(nodes)})
    return {"graph": {"nodes": graph}}


class AggregateModulePlanTests(_FakeRepo):
    """AB-01 / RD-03 (remove_develop_mode_plan.md): header kind per module
    from compiled_intree / pkg_only - the editable_only bucket is gone,
    "editable" is now detected only via a real (possibly hand-registered)
    Conan registration."""

    CONFS = {"df": _conf(), "mathlib": _conf(), "shared-config": _conf(ptype="unknown")}
    VERSIONS = {"df": "0.1.0", "mathlib": "1.2.0", "shared-config": "2.0.0"}
    CLOSURE = {"df", "mathlib", "shared-config"}

    REGISTERED = {"adas-mathlib/1.2.0": os.path.join("C:", "co", "modules", "mathlib", "conanfile.py"),
                  "adas-shared-config/2.0.0": os.path.join("C:", "co", "modules", "shared-config",
                                                           "conanfile.py")}

    def _plan(self, intree, pkg, registrations=None):
        return build_dispatcher.aggregate_module_plan(
            self.CLOSURE, set(intree), set(pkg),
            self.REGISTERED if registrations is None else registrations)

    def test_kinds_and_paths(self):
        plan = self._plan({"df"}, {"mathlib", "shared-config"})
        self.assertEqual(plan["df"]["kind"], "in-tree")
        self.assertEqual(plan["df"]["path"], os.path.join("modules", "df"))
        self.assertEqual(plan["df"]["version"], "0.1.0")
        self.assertEqual(plan["shared-config"]["kind"], "editable")
        self.assertEqual(plan["mathlib"]["kind"], "editable")
        self.assertEqual(plan["mathlib"]["path"], os.path.join("C:", "co", "modules", "mathlib"))

    def test_planted_violation_pkg_only_not_registered_says_package(self):
        # A team-server machine: base components NOT registered.
        plan = self._plan({"df"}, {"mathlib", "shared-config"}, registrations={})
        self.assertEqual(plan["mathlib"]["kind"], "package")
        self.assertEqual(plan["mathlib"]["path"], "(conan cache)")

    def test_registration_at_a_different_version_does_not_count(self):
        plan = self._plan({"df"}, {"mathlib", "shared-config"},
                          registrations={"adas-mathlib/9.9.9": "x"})
        self.assertEqual(plan["mathlib"]["kind"], "package")

    def test_missing_version_is_printed_unknown_never_guessed(self):
        del self.VERSIONS["mathlib"]
        plan = self._plan({"df"}, {"mathlib", "shared-config"})
        self.assertEqual(plan["mathlib"]["version"], "unknown")

    def test_lines_are_aligned_one_per_module(self):
        plan = self._plan({"df"}, {"mathlib", "shared-config"})
        order = ["mathlib", "shared-config", "df"]
        lines = build_dispatcher.format_module_plan(plan, order)
        self.assertEqual(len(lines), 3)
        self.assertEqual(len({line.index(plan[m]["version"]) for line, m in zip(lines, order)}), 1)


class ResolvedKindMismatchTests(unittest.TestCase):
    """AB-02: resolved binary kind per first-party node vs the header."""

    pkg_map = {"adas-df": "df", "adas-mathlib": "mathlib", "adas-viz": "viz"}

    def _plan(self, **kinds):
        return {m: {"kind": k, "version": "1", "path": "p"} for m, k in kinds.items()}

    def _check(self, graph, plan):
        return build_dispatcher.resolved_kind_mismatches(graph, plan, self.pkg_map, "df")

    def test_matching_graph_passes(self):
        graph = _graph(_node("adas-mathlib/1.2.0", "Editable"), _node("protobuf/3.21", "Cache"),
                       _node("adas-viz/1.0.0", "Download"))
        resolved, bad = self._check(graph, self._plan(df="in-tree", mathlib="editable", viz="package"))
        self.assertEqual(bad, [])
        self.assertEqual(resolved, {"mathlib": "editable", "viz": "package"})

    def test_built_binary_counts_as_package(self):
        _, bad = self._check(_graph(_node("adas-viz/1.0.0", "Build")),
                             self._plan(df="in-tree", viz="package"))
        self.assertEqual(bad, [])

    def test_planted_violation_pkg_only_expected_editable_resolved_cache(self):
        _, bad = self._check(_graph(_node("adas-mathlib/1.2.0", "Cache")),
                             self._plan(df="in-tree", mathlib="editable"))
        self.assertEqual(bad, [("mathlib", "editable", "package")])

    def test_planted_violation_in_tree_module_appears_as_a_node(self):
        _, bad = self._check(_graph(_node("adas-viz/1.0.0", "Editable")),
                             self._plan(df="in-tree", viz="in-tree"))
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0][0], "viz")

    def test_planted_violation_expected_module_missing_from_graph(self):
        _, bad = self._check(_graph(), self._plan(df="in-tree", mathlib="editable"))
        self.assertEqual(bad, [("mathlib", "editable", "absent")])

    def test_primary_absent_from_graph_is_not_a_mismatch(self):
        _, bad = self._check(_graph(), self._plan(df="editable"))
        self.assertEqual(bad, [])

    def test_shared_parser_skips_consumer_and_strips_revision(self):
        nodes = build_dispatcher.aggregate_graph_nodes(_graph(_node("adas-mathlib/1.2.0", "Editable")))
        self.assertEqual([ref for ref, _ in nodes], ["adas-mathlib/1.2.0"])


class FirstPartyPackageModeEditableViolationsTests(unittest.TestCase):
    """CE-35(c) (conan_environment_plan.md): a first-party ref resolving
    Editable in package mode is a policy violation even when it exactly
    matches what the header already predicted - AB-01/AB-02
    (ResolvedKindMismatchTests above) only ever checks "did the header
    guess right", never "should this be allowed at all". Real evidence,
    a second corporate PC, 2026-09-23: interfaces/mathlib/sim/shared_
    config all resolved Editable, pointing at a DIFFERENT, stale
    checkout (D:\\df\\1v-superproject) - both plan and resolved agreed, so
    the AB-02 mismatch check found nothing to flag."""

    def setUp(self):
        patcher = unittest.mock.patch.object(
            build_dispatcher, "module_package_name", lambda mod: f"adas-{mod}")
        patcher.start()
        self.addCleanup(patcher.stop)

    def _plan(self, **kinds):
        return {m: {"kind": k, "version": "1.0.0", "path": f"({m} path)"}
                for m, k in kinds.items()}

    def test_planted_violation_editable_in_package_mode_is_flagged(self):
        """PASS: a module whose resolved kind is 'editable' under
        mode='package' is reported. FAIL: silently allowed through -
        exactly the real bug (AB-01/AB-02 found no disagreement, so
        nothing stopped the build)."""
        resolved = {"mathlib": "editable"}
        plan = self._plan(mathlib="editable")
        registrations = {"adas-mathlib/1.0.0": r"D:\df\1v-superproject\modules\mathlib"}

        violations = build_dispatcher.first_party_package_mode_editable_violations(
            resolved, plan, registrations, "package")

        self.assertEqual(violations, [
            ("mathlib", "adas-mathlib/1.0.0", r"D:\df\1v-superproject\modules\mathlib"),
        ])

    def test_package_kind_is_never_flagged(self):
        resolved = {"mathlib": "package"}
        plan = self._plan(mathlib="package")
        violations = build_dispatcher.first_party_package_mode_editable_violations(
            resolved, plan, {}, "package")
        self.assertEqual(violations, [])

    def test_in_tree_module_is_never_flagged_even_if_resolved_says_editable(self):
        """An in-tree module is never a real Conan node with a genuine
        'editable' resolution in the sense this check cares about - the
        plan's own 'in-tree' kind always wins (matches resolved_kind_
        mismatches()'s own in-tree handling one function up)."""
        resolved = {"df": "editable"}  # would only happen from a bad graph
        plan = self._plan(df="in-tree")
        violations = build_dispatcher.first_party_package_mode_editable_violations(
            resolved, plan, {}, "package")
        self.assertEqual(violations, [])

    def test_only_package_mode_is_checked(self):
        """A hypothetical non-package mode (there is currently only one
        real mode, RD-03) is never checked - this function's own name
        and docstring are explicit about that."""
        resolved = {"mathlib": "editable"}
        plan = self._plan(mathlib="editable")
        violations = build_dispatcher.first_party_package_mode_editable_violations(
            resolved, plan, {}, "develop")
        self.assertEqual(violations, [])

    def test_missing_registration_falls_back_to_the_plan_path(self):
        """registrations (the live `conan editable list`) might disagree
        in timing with plan (computed slightly earlier) - never crash,
        fall back to whatever the plan already recorded."""
        resolved = {"mathlib": "editable"}
        plan = self._plan(mathlib="editable")
        violations = build_dispatcher.first_party_package_mode_editable_violations(
            resolved, plan, {}, "package")
        self.assertEqual(violations, [("mathlib", "adas-mathlib/1.0.0", "(mathlib path)")])


class PathOutsideRootTests(unittest.TestCase):
    """CE-35(c): the stale-copy case (a registration pointing at a
    DIFFERENT checkout entirely) gets a more specific warning line."""

    def test_path_under_root_is_not_outside(self):
        root = build_dispatcher.ROOT
        with unittest.mock.patch.object(build_dispatcher, "ROOT", root):
            self.assertFalse(build_dispatcher._path_outside_root(
                os.path.join(root, "modules", "mathlib")))

    def test_path_under_a_different_checkout_is_outside(self):
        """Real evidence's own shape (D:\\df\\1v-superproject vs. this
        run's D:\\1v-superproject) - a different drive on Windows also
        makes os.path.commonpath() raise ValueError, the exact case this
        function's own try/except exists for; proven not to propagate,
        and to resolve to True (outside), not just 'did not crash'."""
        with unittest.mock.patch.object(build_dispatcher, "ROOT", r"C:\adas\1v-superproject"):
            self.assertTrue(build_dispatcher._path_outside_root(
                r"D:\df\1v-superproject\modules\mathlib"))


class EditableListParseTests(unittest.TestCase):
    """AB-01: parse failure of the editable list is an error, never a guess."""

    def test_parses_ref_to_path_and_strips_revision(self):
        out = json.dumps({"adas-mathlib/1.0.0#abc": {"path": "C:/m/conanfile.py", "output_folder": None}})
        self.assertEqual(build_dispatcher.parse_editable_list(out),
                         {"adas-mathlib/1.0.0": "C:/m/conanfile.py"})

    def test_empty_object_is_a_valid_empty_registration_set(self):
        self.assertEqual(build_dispatcher.parse_editable_list("{}"), {})

    def test_planted_violation_unparseable_or_wrong_shape_raises(self):
        for bad in ("", "not json", "[]", '{"adas-x/1": "path"}'):
            with self.assertRaises(ValueError, msg=bad):
                build_dispatcher.parse_editable_list(bad)

    def test_planted_violation_conan_failure_raises_even_with_plausible_stdout(self):
        # A non-zero exit whose stdout happens to be valid JSON ("{}") must NOT
        # be read as "nothing registered".
        for stdout in ("", "{}"):
            failed = unittest.mock.Mock(returncode=1, stdout=stdout, stderr="boom")
            with unittest.mock.patch.object(build_dispatcher.subprocess, "run", return_value=failed):
                with self.assertRaises(ValueError, msg=repr(stdout)):
                    build_dispatcher.read_editable_registrations()

    def test_zero_exit_returns_the_parsed_registrations(self):
        ok = unittest.mock.Mock(returncode=0, stderr="",
                                stdout=json.dumps({"adas-a/1.0.0": {"path": "P"}}))
        with unittest.mock.patch.object(build_dispatcher.subprocess, "run", return_value=ok):
            self.assertEqual(build_dispatcher.read_editable_registrations(), {"adas-a/1.0.0": "P"})


def _editable_node(ref, libdirs, libs, binary="Editable"):
    node = _node(ref, binary)
    node["package_folder"] = "C:/modules/x"
    node["cpp_info"] = {"root": {"libdirs": libdirs, "libs": libs}}
    return node


class UsedTargetsTests(unittest.TestCase):
    """AB-13: used/ links an editable's build output, not its repo root."""

    def test_planted_violation_compiled_editable_must_not_link_to_the_module_root(self):
        node = _editable_node("adas-mathlib/1.0.0", ["C:/m/build/Release"], ["adas-mathlib"])
        got = build_dispatcher.aggregate_used_targets(_graph(node))
        self.assertEqual(got, {"adas-mathlib-1.0.0": "C:/m/build/Release"})
        self.assertNotEqual(got["adas-mathlib-1.0.0"], node["package_folder"])

    def test_data_editable_keeps_the_module_folder(self):
        node = _editable_node("adas-shared-config/1.0.0", [], [])
        self.assertEqual(build_dispatcher.aggregate_used_targets(_graph(node)),
                         {"adas-shared-config-1.0.0": "C:/modules/x"})

    def test_cache_node_is_unchanged_even_with_libdirs(self):
        node = _editable_node("adas-viz/1.0.0", ["lib"], ["adas-viz"], binary="Cache")
        self.assertEqual(build_dispatcher.aggregate_used_targets(_graph(node)),
                         {"adas-viz-1.0.0": "C:/modules/x"})

    def test_first_libdir_is_linked_and_the_rest_are_logged(self):
        node = _editable_node("adas-mathlib/1.0.0", ["A", "B"], ["adas-mathlib"])
        with unittest.mock.patch.object(build_dispatcher, "log") as log:
            got = build_dispatcher.aggregate_used_targets(_graph(node))
        self.assertEqual(got["adas-mathlib-1.0.0"], "A")
        self.assertIn("B", log.call_args[0][0])

    def test_node_without_any_folder_is_skipped(self):
        node = _node("adas-x/1.0.0", "Cache")
        self.assertEqual(build_dispatcher.aggregate_used_targets(_graph(node)), {})


class ResolvedTableTests(unittest.TestCase):
    """AB-02: the resolved table prints each node's real package_folder."""

    pkg_map = {"adas-df": "df", "adas-mathlib": "mathlib"}

    def test_folders_come_from_the_graph_and_in_tree_shows_its_module_dir(self):
        node = _node("adas-mathlib/1.2.0", "Editable")
        node["package_folder"] = "C:/build/mathlib/pkg"
        graph = _graph(node)
        folders = build_dispatcher.resolved_package_folders(graph, self.pkg_map)
        self.assertEqual(folders, {"mathlib": "C:/build/mathlib/pkg"})
        plan = {"mathlib": {"kind": "editable", "path": "p"},
                "df": {"kind": "in-tree", "path": os.path.join("modules", "df")}}
        lines = build_dispatcher.format_resolved_table(
            plan, {"mathlib": "editable"}, folders, ["mathlib", "df"])
        self.assertIn("C:/build/mathlib/pkg", lines[0])
        self.assertIn("in-tree (modules/df)", lines[1])

    def test_missing_package_folder_is_stated_not_blank(self):
        lines = build_dispatcher.format_resolved_table(
            {"mathlib": {"kind": "package", "path": "p"}}, {"mathlib": "package"}, {}, ["mathlib"])
        self.assertIn("no package_folder reported", lines[0])


    def test_table_shows_editable_libdirs_not_the_module_root(self):
        plan = {"mathlib": {"kind": "editable", "path": "p"}}
        graph = _graph(_editable_node("adas-mathlib/1.0.0", ["C:/b/Release"], ["adas-mathlib"]))
        lines = build_dispatcher.format_resolved_table(
            plan, {"mathlib": "editable"},
            build_dispatcher.resolved_package_folders(graph, self.pkg_map), ["mathlib"],
            build_dispatcher.resolved_lib_dirs(graph, self.pkg_map))
        self.assertIn("libdirs: C:/b/Release", lines[0])
        self.assertNotIn("C:/modules/x", lines[0])

class AggregateRunHeaderAndGraphTests(_FakeRepo):
    """End-to-end through run_aggregate_build with conan mocked out: the header
    reads the registrations (AB-01) and a missing graph is fatal (AB-02)."""

    CONFS = {"df": _conf(["adas-mathlib/1.0.0"]), "mathlib": _conf()}
    VERSIONS = {"df": "1.0.0", "mathlib": "1.0.0"}

    def _run(self, registrations=None, graph="none", editable_error=None, mode="develop",
             with_mods=None, remotes_state=True):
        import tempfile
        node = _node("adas-mathlib/1.0.0", "Cache")
        node["package_folder"] = "C:/cache/mathlib"
        patch = unittest.mock.patch.object
        with tempfile.TemporaryDirectory() as root, \
                patch(build_dispatcher, "ROOT", root), \
                patch(build_dispatcher, "is_valid_module", return_value=True), patch(build_dispatcher, "absent_first_party_refs", return_value={}), \
                patch(build_dispatcher, "module_package_type", return_value="shared-library"), \
                patch(build_dispatcher, "package_to_module_map", return_value=self.pkg_map), \
                patch(build_dispatcher, "apply_conan_home"), \
                patch(build_dispatcher, "missing_toolchain_pin", return_value=[]), \
                patch(build_dispatcher, "missing_cache_refs", return_value=[]), \
                patch(build_dispatcher, "stale_cache_refs", return_value=([], [])), \
                patch(build_dispatcher, "generate_aggregate_conanfile"), \
                patch(build_dispatcher, "generate_aggregate_cmakelists"), \
                patch(build_dispatcher, "refresh_aggregate_used_shortcuts"), \
                patch(build_dispatcher, "run_logged", return_value=0) as run_logged, \
                patch(build_dispatcher, "read_editable_registrations",
                      side_effect=editable_error, return_value=registrations or {}), \
                patch(build_dispatcher, "run_install_logged",
                      side_effect=lambda *a, **k: (0, graphs[graph])):
            libdir = os.path.join(root, "mlib")
            os.makedirs(libdir)
            if graph == "built":
                for name in ("adas-mathlib.lib", "libadas-mathlib.a"):
                    open(os.path.join(libdir, name), "w").close()
            graphs = {"none": None, "ok": _graph(node),
                      "unbuilt": _graph(_editable_node("adas-mathlib/1.0.0", [libdir], ["adas-mathlib"])),
                      "built": _graph(_editable_node("adas-mathlib/1.0.0", [libdir], ["adas-mathlib"]))}
            code = None
            try:
                build_dispatcher.run_aggregate_build(
                    "base", "df", "sil", "vs2026", with_mods or [], False, False, False,
                    mode=mode, remotes_state=remotes_state)
            except SystemExit as exc:
                code = exc.code
            logdir = os.path.join(root, "conan_workarea", "logs")
            with open(os.path.join(logdir, os.listdir(logdir)[0]), encoding="utf-8") as f:
                return code, f.read(), run_logged

    def test_planted_violation_develop_mode_unregistered_pkg_only_header_says_package(self):
        code, text, _ = self._run(registrations={}, graph="ok")
        self.assertIn("mathlib  1.0.0  package", text)
        self.assertNotIn("expected", text.split("conan install")[0])
        self.assertIsNone(code)

    def test_registered_pkg_only_header_says_editable_and_mismatch_with_cache_graph_fails(self):
        code, text, _ = self._run(
            registrations={"adas-mathlib/1.0.0": os.path.join("C:", "co", "mathlib", "conanfile.py")},
            graph="ok")
        self.assertIn("mathlib  1.0.0  editable", text)
        self.assertEqual(code, 1)
        self.assertIn("header said editable, conan resolved package", text)

    def test_planted_violation_package_mode_end_to_end_refuses_a_correctly_predicted_editable(self):
        """CE-35(c) (conan_environment_plan.md): the real regression, run
        end-to-end through run_aggregate_build() itself, not just the
        pure function - header AND graph BOTH agree "editable" (so AB-02's
        own mismatch check, exercised by the test just above, finds
        NOTHING to flag) under mode="package". PASS: refused anyway,
        naming the ref, its path, and the `conan editable remove` fix.
        FAIL: proceeds to cmake configure - the exact real corporate-PC
        bug (viz compiled against a stale sim editable with no error at
        all)."""
        stray_path = os.path.join("D:", "df", "1v-superproject", "modules", "mathlib")
        code, text, run_logged = self._run(
            registrations={"adas-mathlib/1.0.0": stray_path},
            graph="built", mode="package")
        self.assertEqual(code, 1)
        self.assertIn("resolved as a Conan Editable registration in package mode", text)
        self.assertIn("adas-mathlib/1.0.0", text)
        self.assertIn(stray_path, text)
        self.assertIn("conan editable remove --refs adas-mathlib/1.0.0", text)
        self.assertIn("OUTSIDE this checkout's root", text)
        run_logged.assert_not_called()  # cmake configure never reached

    def test_ns16_proof_refusal_stops_a_never_built_editable_before_the_ab10_check(self):
        """NS-16 (cache_first_no_server_plan.md), the deletion proof for
        unbuilt_editable_violations() (AB-10/AB-14): in package mode - the
        only mode build.py's main() lets through - a first-party ref that
        resolves Editable is refused by CE-35(c) (NS-22(a)) even when its
        library is ALSO missing, and the AB-10 "never built" message never
        appears. Both remotes states, both graph shapes: the outcome does
        not depend on whether the library exists (the refusal has no
        such test), nor on remotes (the aggregate path has no branch on
        them there)."""
        for remotes_state in (True, False):
            for graph in ("unbuilt", "built"):
                with self.subTest(remotes_state=remotes_state, graph=graph):
                    code, text, run_logged = self._run(
                        registrations=self.REG, graph=graph, mode="package",
                        remotes_state=remotes_state)
                    self.assertEqual(code, 1)
                    self.assertIn("resolved as a Conan Editable registration in package mode",
                                  text)
                    self.assertIn("(CE-35)", text)
                    self.assertNotIn("never built", text)
                    self.assertNotIn("AB-10", text)
                    run_logged.assert_not_called()

    def test_ns16_proof_an_in_tree_module_resolving_editable_is_stopped_even_earlier(self):
        """NS-16: the one exemption the refusal has (a module built in-tree)
        cannot reach AB-10 either - resolved_kind_mismatches() (AB-02)
        already exits, because an in-tree module must not be a graph node
        at all."""
        code, text, run_logged = self._run(
            registrations=self.REG, graph="unbuilt", mode="package", with_mods=["mathlib"])
        self.assertEqual(code, 1)
        self.assertIn("header said in-tree (no graph node), conan resolved editable", text)
        self.assertNotIn("never built", text)
        run_logged.assert_not_called()

    def test_planted_violation_graph_none_after_successful_install_exits_1(self):
        code, text, run_logged = self._run(graph="none")
        self.assertEqual(code, 1)
        self.assertIn("ERROR: conan install succeeded but its dependency graph", text)
        run_logged.assert_not_called()  # cmake configure never reached

    def test_planted_violation_editable_list_failure_exits_1_before_header(self):
        code, text, _ = self._run(editable_error=ValueError("boom"))
        self.assertEqual(code, 1)
        self.assertIn("cannot read the editable registrations", text)
        self.assertNotIn("first-party modules", text)

    REG = {"adas-mathlib/1.0.0": os.path.join("C:", "co", "mathlib", "conanfile.py")}

    def test_resolved_table_prints_the_real_package_folder(self):
        _, text, _ = self._run(graph="ok")
        self.assertIn("C:/cache/mathlib", text)
        self.assertIn("in-tree (modules/df)", text)


class AuthFailureMessageTests(unittest.TestCase):
    """CE-28: an expired adas-local login is named, with its CONAN_HOME."""

    REAL = ("ERROR: Package 'adas-shared-config/1.0.0' not resolved: adas-shared-config/1.0.0: "
            "Cannot load recipe.\nError loading conanfile at 'x\\conanfile.py': Cannot resolve "
            "python_requires 'adas-toolchain/1.0.4': Conan interactive mode disabled. "
            "[Remote: adas-local]. Required by 'adas-aggregate/0.0.0'")

    def test_planted_real_output_names_the_remote_and_the_home(self):
        msg = build_dispatcher.auth_failure_message(self.REAL, "C:\\h\\.conan2-dev")
        self.assertEqual(msg, "adas-local login expired - run: conan remote login adas-local "
                              "demo -p demo (CONAN_HOME=C:\\h\\.conan2-dev)")

    def test_pre_setting_eof_prompt_failure_is_recognised_too(self):
        out = "ERROR: ... EOF when reading a line. [Remote: adas-local]. Required by 'x'"
        self.assertIn("adas-local login expired", build_dispatcher.auth_failure_message(out, None))
        self.assertIn("CONAN_HOME=Conan default", build_dispatcher.auth_failure_message(out, None))

    def test_a_non_auth_failure_is_not_reported_as_one(self):
        self.assertIsNone(build_dispatcher.auth_failure_message(
            "ERROR: Package 'x/1' not resolved: Not found [Remote: adas-local]", "h"))

    def test_other_remote_gets_a_generic_login_hint(self):
        msg = build_dispatcher.auth_failure_message(
            "Conan interactive mode disabled. [Remote: other]", "h")
        self.assertIn("conan remote login other <user>", msg)

    def test_failed_install_logs_the_message(self):
        proc = unittest.mock.Mock(returncode=1, communicate=lambda: ("", self.REAL))
        with unittest.mock.patch.object(build_dispatcher.subprocess, "Popen", return_value=proc), \
                unittest.mock.patch.object(build_dispatcher, "log") as log:
            rc, graph = build_dispatcher.run_install_logged(["conan", "install"], ".")
        self.assertEqual((rc, graph), (1, None))
        self.assertTrue(any("adas-local login expired" in c.args[0] for c in log.call_args_list))


class RebuildUsersTests(_FakeRepo):
    """AB-12: `deps --rebuild-users` reports the modules each dep forces,
    from the SAME rule AB-05 enforces; the default output is unchanged."""

    CONFS = {
        "df": _conf(["adas-viz/1.0.0", "adas-sim/1.0.0", "adas-interfaces/1.0.0",
                     "adas-shared-config/1.0.0"]),
        "sim": _conf(["adas-interfaces/1.0.0"]),
        "viz": _conf(["adas-interfaces/1.0.0"]),
        "interfaces": _conf(),
        "shared-config": _conf(ptype="unknown"),
    }
    VERSIONS = {m: "1.0.0" for m in CONFS}

    def setUp(self):
        super().setUp()
        patcher = unittest.mock.patch.object(build_dispatcher, "package_to_module_map",
                                             return_value=self.pkg_map)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = unittest.mock.patch.object(build_dispatcher, "is_valid_module", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = unittest.mock.patch.object(build_dispatcher, "absent_first_party_refs", return_value={})
        patcher.start()
        self.addCleanup(patcher.stop)

    def _print(self, rebuild):
        import io
        buf = io.StringIO()
        with unittest.mock.patch("sys.stdout", buf):
            build_dispatcher.print_deps("df", "base", rebuild)
        return buf.getvalue().splitlines()

    def test_planted_interfaces_forces_sim_and_viz(self):
        self.assertEqual(build_dispatcher.rebuild_users_map("df", "base")["interfaces"],
                         ["sim", "viz"])

    def test_data_dependency_lists_no_users_and_leaves_have_none(self):
        users = build_dispatcher.rebuild_users_map("df", "base")
        self.assertEqual(users["shared-config"], [])
        self.assertEqual(users["sim"], [])

    def test_users_agree_with_what_ab05_would_accept(self):
        closure = {"df", "sim", "viz", "interfaces", "shared-config"}
        for dep, users in build_dispatcher.rebuild_users_map("df", "base").items():
            total = {"df", dep, *users}
            self.assertEqual(build_dispatcher.reverse_rebuild_violations(
                total, closure, "base", self.pkg_map), [], dep)

    def test_default_output_has_no_users_suffix(self):
        self.assertTrue(all("users:" not in l for l in self._print(False)))
        self.assertIn("shared-config [data]", self._print(False))

    def test_flag_appends_users_only_where_there_are_some(self):
        lines = self._print(True)
        self.assertIn("interfaces  users: sim viz", lines)
        self.assertIn("sim", lines)
        self.assertIn("shared-config [data]", lines)


class WsManifestTests(_FakeRepo):
    """AB-04: ws_manifest.txt decodes the folder name."""

    CONFS = {"df": _conf(), "mathlib": _conf()}
    VERSIONS = {"df": "0.1.0", "mathlib": "1.2.0"}

    def _text(self, with_mods=("viz", "mathlib"), with_all=False, mode="package"):
        plan = build_dispatcher.aggregate_module_plan(
            {"df", "mathlib"}, {"df"}, {"mathlib"},
            {"adas-mathlib/1.2.0": os.path.join("C:", "co", "mathlib", "conanfile.py")})
        return build_dispatcher.ws_manifest_text(
            "sil", "vs2026", "base", "df", list(with_mods), with_all, mode, plan, ["mathlib", "df"])

    def test_key_value_lines_with_sorted_with_list_and_scope_hash(self):
        text = self._text()
        lines = dict(l.split(": ", 1) for l in text.splitlines() if not l.startswith("module:"))
        self.assertEqual(lines["primary"], "df")
        self.assertEqual(lines["mode"], "package")
        self.assertEqual(lines["with"], "mathlib viz")
        self.assertEqual(lines["scope"], "agg")
        self.assertIn("module: mathlib 1.2.0 editable", text)

    def test_with_all_is_reported(self):
        self.assertIn("with: (all)", self._text(with_all=True))


class RefusedBuildLeavesLogTests(_FakeRepo):
    """AB-08 item 5: a guard refusal is logged, writes a log file, and touches
    neither CONAN_HOME nor the workspace."""

    CONFS = {"df": _conf(["adas-viz/1.0.0", "adas-mathlib/1.0.0"]),
             "viz": _conf(["adas-mathlib/1.0.0"]), "mathlib": _conf()}
    VERSIONS = {"df": "1.0.0", "viz": "1.0.0", "mathlib": "1.0.0"}

    def test_planted_reverse_rebuild_violation_refuses_with_a_log_and_no_workspace(self):
        import tempfile
        with tempfile.TemporaryDirectory() as root, \
                unittest.mock.patch.object(build_dispatcher, "ROOT", root), \
                unittest.mock.patch.object(build_dispatcher, "is_valid_module", return_value=True), unittest.mock.patch.object(build_dispatcher, "absent_first_party_refs", return_value={}), \
                unittest.mock.patch.object(build_dispatcher, "package_to_module_map",
                                           return_value=self.pkg_map), \
                unittest.mock.patch.object(build_dispatcher, "apply_conan_home") as apply_home:
            with self.assertRaises(SystemExit) as cm:
                build_dispatcher.run_aggregate_build(
                    "base", "df", "sil", "vs2026", ["mathlib"], False, False, False, mode="develop")
            self.assertEqual(cm.exception.code, 1)
            apply_home.assert_not_called()
            logs = os.listdir(os.path.join(root, "conan_workarea", "logs"))
            self.assertEqual(len(logs), 1)
            with open(os.path.join(root, "conan_workarea", "logs", logs[0]), encoding="utf-8") as f:
                text = f.read()
            self.assertIn("would NOT be rebuilt", text)
            self.assertIn("--with mathlib viz", text)
            self.assertEqual(os.listdir(os.path.join(root, "conan_workarea")), ["logs"])


class StaleBuildDirTests(unittest.TestCase):
    """RP-06 (D6): an aggregate deletes `_bd_<m>/` for modules not in-tree this
    run, and nothing else."""

    def _seed(self, ws):
        for d in ("_bd_df", "_bd_interfaces", "_bd_sim", "CMakeFiles", "used"):
            os.makedirs(os.path.join(ws, d))
        open(os.path.join(ws, "_bd_notadir"), "w").close()
        open(os.path.join(ws, "ws_manifest.txt"), "w").close()

    def test_planted_violation_still_in_tree_module_is_not_removed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as ws:
            self._seed(ws)
            removed = build_dispatcher.remove_stale_build_dirs(ws, {"df", "sim"})
            self.assertEqual(removed, ["interfaces"])
            self.assertEqual(sorted(os.listdir(ws)),
                             ["CMakeFiles", "_bd_df", "_bd_notadir", "_bd_sim", "used", "ws_manifest.txt"])

    def test_removal_is_logged_by_name_and_happens_before_cmake_configure(self):
        import tempfile
        seen = {}
        pkg_map = {"adas-df": "df"}
        patch = unittest.mock.patch.object
        with tempfile.TemporaryDirectory() as root:
            ws = os.path.join(root, "conan_workarea",
                              build_dispatcher.ws_folder_name("sil", "vs2026", "base", "df", None, False))
            os.makedirs(ws)
            self._seed(ws)

            def fake_run_logged(cmd, cwd=None):
                if cmd[0] == "cmake" and "-S" in cmd:
                    seen["stale_at_configure"] = os.path.isdir(os.path.join(ws, "_bd_interfaces"))
                return 0

            with patch(build_dispatcher, "ROOT", root),                     patch(build_dispatcher, "is_valid_module", return_value=True), patch(build_dispatcher, "absent_first_party_refs", return_value={}),                     patch(build_dispatcher, "module_package_type", return_value="shared-library"),                     patch(build_dispatcher, "package_to_module_map", return_value=pkg_map),                     patch(build_dispatcher, "forward_closure", return_value={"df"}),                     patch(build_dispatcher, "module_version", return_value="1.0.0"),                     patch(build_dispatcher, "module_package_name", return_value="adas-df"),                     patch(build_dispatcher, "apply_conan_home"),                     patch(build_dispatcher, "generate_aggregate_conanfile"),                     patch(build_dispatcher, "generate_aggregate_cmakelists"),                     patch(build_dispatcher, "refresh_aggregate_used_shortcuts"),                     patch(build_dispatcher, "read_editable_registrations", return_value={}),                     patch(build_dispatcher, "run_logged", side_effect=fake_run_logged),                     patch(build_dispatcher, "run_install_logged", return_value=(0, _graph())):
                build_dispatcher.run_aggregate_build("base", "df", "sil", "vs2026", [], False, False, False,
                                                     mode="package")
            logdir = os.path.join(root, "conan_workarea", "logs")
            with open(os.path.join(logdir, os.listdir(logdir)[0]), encoding="utf-8") as f:
                text = f.read()
        self.assertFalse(seen["stale_at_configure"])
        self.assertIn("removing stale _bd_interfaces/", text)
        self.assertIn("removing stale _bd_sim/", text)
        self.assertNotIn("removing stale _bd_df/", text)


class RootDefaultModeTests(_FakeRepo):
    """RP-02 / RP-03 (root_build_package_mode_plan.md D2, D4): package is the
    root default for delegate and aggregate; package mode never registers an
    editable, a data module in --with is a re-exported package."""

    CONFS = {"df": _conf(["adas-shared_config/1.0.0"]), "shared_config": _conf(ptype="data")}
    VERSIONS = {"df": "1.0.0", "shared_config": "1.0.0"}

    def _main(self, argv):
        patch = unittest.mock.patch.object
        with patch(build_dispatcher.sys, "argv", ["build.py"] + argv),                 patch(build_dispatcher, "all_projects", return_value=["base"]),                 patch(build_dispatcher, "is_valid_module", return_value=True), patch(build_dispatcher, "absent_first_party_refs", return_value={}),                 patch(build_dispatcher, "validate_with_module"),                 patch(build_dispatcher, "run_aggregate_build") as agg,                 patch(build_dispatcher, "run_delegate", return_value=True) as dele:
            try:
                build_dispatcher.main()
            except SystemExit:
                pass
        return agg, dele

    def test_default_mode_constant_is_package(self):
        self.assertEqual(build_dispatcher.ROOT_DEFAULT_MODE, "package")

    def test_planted_violation_delegate_and_aggregate_default_to_package(self):
        agg, dele = self._main(["df", "-t", "sil", "-p", "vs2026"])
        self.assertEqual(len(dele.call_args[0]), 6)  # NS-32: no mode argument any more
        agg, _ = self._main(["df", "-t", "sil", "-p", "vs2026", "--with", "shared_config"])
        # NS-05 (cache_first_no_server_plan.md STEP 2): run_aggregate_build()
        # gained a trailing remotes_state positional (args.remotes_enabled) -
        # mode is now second-to-last, not last.
        self.assertEqual(agg.call_args[0][-2], "package")

    def test_explicit_develop_is_refused(self):
        """RD-03 (remove_develop_mode_plan.md): main() refuses --mode
        develop before ever reaching run_aggregate_build."""
        agg, _ = self._main(["df", "-t", "sil", "-p", "vs2026", "--with", "x", "--mode", "develop"])
        agg.assert_not_called()

    def _aggregate(self, mode, with_mods=("shared_config",), with_all=False,
                   missing_pin=(), data_packager=None):
        """`data_packager`, when given, replaces package_named_data_modules()
        so a test can observe whether (and in what order) it was reached."""
        import tempfile
        import contextlib
        node = _node("adas-shared_config/1.0.0", "Cache")
        node["package_folder"] = "C:/cache/sc"
        pkg_map = {"adas-df": "df", "adas-shared_config": "shared_config"}
        patch = unittest.mock.patch.object
        with tempfile.TemporaryDirectory() as root,                 patch(build_dispatcher, "ROOT", root),                 patch(build_dispatcher, "is_valid_module", return_value=True), patch(build_dispatcher, "absent_first_party_refs", return_value={}),                 patch(build_dispatcher, "module_package_type",
                      side_effect=lambda m: "data" if m == "shared_config" else "shared-library"),                 patch(build_dispatcher, "package_to_module_map", return_value=pkg_map),                 patch(build_dispatcher, "apply_conan_home"),                 patch(build_dispatcher, "missing_toolchain_pin", return_value=list(missing_pin)) as pin_check,                 patch(build_dispatcher, "missing_cache_refs", return_value=[]) as ref_check,                 patch(build_dispatcher, "generate_aggregate_conanfile"),                 patch(build_dispatcher, "generate_aggregate_cmakelists"),                 patch(build_dispatcher, "refresh_aggregate_used_shortcuts"),                 patch(build_dispatcher, "run_logged", return_value=0),                 patch(build_dispatcher, "read_editable_registrations", return_value={}),                 patch(build_dispatcher, "create_and_record_module", return_value=True) as data_pkg,                 patch(build_dispatcher, "stale_cache_refs", return_value=([], [])),                 patch(build_dispatcher, "run_install_logged", return_value=(0, _graph(node))), \
                (patch(build_dispatcher, "package_named_data_modules", side_effect=data_packager)
                 if data_packager is not None else contextlib.nullcontext()):
            try:
                build_dispatcher.run_aggregate_build(
                    "base", "df", "sil", "vs2026", list(with_mods) or None, with_all,
                    False, False, mode=mode)
            except SystemExit:
                pass
            logdir = os.path.join(root, "conan_workarea", "logs")
            with open(os.path.join(logdir, os.listdir(logdir)[0]), encoding="utf-8") as f:
                return pin_check, ref_check, data_pkg, f.read()

    def test_planted_violation_package_mode_never_registers_editable(self):
        """RD-03: register_editable() itself is gone - a data-only --with
        module is resolved as a Conan package, never auto-registered editable.

        UPDATED 2026-09-25 for A's intentional behaviour change (found by a
        user running --with-all on a cold machine). This test used to assert
        that a data-only `--with` module "is always pkg_only" and that BOTH
        read-only guards were consulted for it. That is no longer true, and
        was the defect: D4 says build.py builds whatever --with names, so a
        NAMED data module is now packaged from the checkout
        (package_named_data_modules()) instead of being demanded from the
        cache. What is unchanged, and still asserted: it resolves as a
        package, never as an editable registration.
        """
        pin_check, ref_check, data_pkg, text = self._aggregate("package")
        self.assertIn("shared_config  1.0.0  package", text)
        # It went through the named-data path, which found it cached and
        # unchanged and so correctly did NOT re-create it (the doubles above
        # report no missing ref, no stale source, no absent record).
        self.assertIn("data package, already cached and unchanged", text,
                      "a --with-named data module is handled by build.py now (D4), "
                      "not demanded from the cache by the pkg_only guard")
        self.assertFalse(data_pkg.called,
                         "nothing changed, so a repeat build must pay nothing")
        # ...and it asked the same cache question the guard used to ask...
        self.assertEqual(sorted(ref_check.call_args[0][0]), ["shared_config"])
        # ...and (NS-48, RV-1) the toolchain-pin guard IS consulted, with the
        # named data module in its set. pkg_only is empty here, but
        # package_named_data_modules() runs `conan create`, whose recipe is a
        # python_requires stub needing adas-toolchain/<pin> itself - so
        # "only modules resolved FROM the cache need the pin" is false for the
        # named-data path. The previous version of this line asserted the
        # guard was NOT consulted, and so held RV-1 in place.
        self.assertIsNotNone(pin_check.call_args,
                             "the pin guard must run even when pkg_only is empty")
        self.assertIn("shared_config", pin_check.call_args[0][0])
        self.assertNotIn("editable", text.lower())

    def _pin_order(self, **kwargs):
        """NS-47 (RV-1): the pin check refuses BEFORE any data module is
        packaged. Returns (pin_check, packager_calls, log_text)."""
        calls = []
        pin_check, _ref, _pkg, text = self._aggregate(
            "package", missing_pin=["adas-toolchain/9.9.9"],
            data_packager=lambda *a, **kw: calls.append(a) or [], **kwargs)
        return pin_check, calls, text

    def test_with_all_cold_pin_refuses_before_packaging(self):
        pin_check, calls, text = self._pin_order(with_mods=(), with_all=True)
        self.assertIn("adas-toolchain/9.9.9 is not in this machine's Conan cache", text)
        self.assertIn(f"run {build_dispatcher.setup_command()}", text)
        self.assertEqual(calls, [], "ordering is the assertion: no conan create may "
                                    "run once the pin is known to be missing")
        self.assertIn("shared_config", pin_check.call_args[0][0])

    def test_with_named_data_cold_pin_refuses_before_packaging(self):
        """--with shared_config produces a different pkg_only than --with-all
        (nothing, vs the rest of the closure), so it is asserted separately."""
        pin_check, calls, text = self._pin_order(with_mods=("shared_config",))
        self.assertIn(f"run {build_dispatcher.setup_command()}", text)
        self.assertEqual(calls, [])
        self.assertIn("shared_config", pin_check.call_args[0][0])


class ModeRefusalTest(unittest.TestCase):
    """RD-03 (remove_develop_mode_plan.md): --mode develop is refused with
    a one-line message naming the plan (was RD-02's deprecation warning;
    now a hard refusal, exit code 1). package mode (the default) is never
    refused. is_valid_module patched False so a non-refused run exits
    right after, before any real build machinery runs."""

    def _run(self, argv):
        buf = io.StringIO()
        patch = unittest.mock.patch
        with patch.object(build_dispatcher, "is_valid_module", return_value=False),                 patch("sys.argv", ["build.py"] + argv),                 patch("sys.stderr", buf):
            with self.assertRaises(SystemExit) as ctx_mgr:
                build_dispatcher.main()
        return ctx_mgr.exception, buf.getvalue()

    def test_mode_develop_is_refused_with_a_message_naming_the_plan(self):
        exc, text = self._run(["df", "-t", "sil", "-p", "vs2026", "--mode", "develop"])
        self.assertEqual(exc.code, 1)
        self.assertIn("remove_develop_mode_plan.md", text)
        self.assertIn("removed", text.lower())

    def test_planted_violation_package_mode_is_not_refused(self):
        # Both exit 1 - is_valid_module=False's own refusal, not --mode's -
        # distinguished by the message, never mentioning the plan here.
        _, text = self._run(["df", "-t", "sil", "-p", "vs2026", "--mode", "package"])
        self.assertNotIn("remove_develop_mode_plan.md", text)

    def test_planted_violation_default_mode_is_not_refused(self):
        _, text = self._run(["df", "-t", "sil", "-p", "vs2026"])
        self.assertNotIn("remove_develop_mode_plan.md", text)


class BuildOnlyNoPreparationTests(_FakeRepo):
    """NS-05 (cache_first_no_server_plan.md D4, STEP 2 - §2b's own WP-4
    criteria): build.py builds, and nothing else.
      - export_first_party_deps()/ensure_toolchain_exported() are
        deleted (NS-34) - asserted by absence below;
        the read-only missing_toolchain_pin()/missing_cache_refs() are
        what's actually consulted now.
      - a first-party ref missing from the cache and not being built here
        STOPS the build, naming the ref and `setup.bat`/`--prepare`.
      - the aggregate's own `conan install` never carries --update, and
        carries -nr only when remotes are off (command-list assertions,
        never output-text assertions, per the plan's own WP-2 test
        convention)."""

    CONFS = {"df": _conf(["adas-mathlib/1.0.0"]), "mathlib": _conf()}
    VERSIONS = {"df": "1.0.0", "mathlib": "1.0.0"}

    def _delegate(self, missing_refs=(), missing_pin=(), forward=None):
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "modules", "df", "scripts"))
            open(os.path.join(root, "modules", "df", "scripts", "build.py"), "w").close()
            os.makedirs(os.path.join(root, "conan_workarea", "logs"))
            patch = unittest.mock.patch.object
            with patch(build_dispatcher, "ROOT", root), \
                    patch(build_dispatcher, "apply_conan_home"), \
                    patch(build_dispatcher, "absent_first_party_refs", return_value={}), \
                    patch(build_dispatcher, "package_to_module_map", return_value=self.pkg_map), \
                    patch(build_dispatcher, "forward_closure",
                          return_value=forward if forward is not None else {"df", "mathlib"}), \
                    patch(build_dispatcher, "missing_toolchain_pin",
                          return_value=list(missing_pin)) as pin_check, \
                    patch(build_dispatcher, "missing_cache_refs",
                          return_value=list(missing_refs)) as ref_check, \
                    patch(build_dispatcher, "stale_cache_refs", return_value=([], [])), \
                    patch(build_dispatcher.subprocess, "run",
                          return_value=unittest.mock.Mock(returncode=0)) as sub_run:
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    ok = build_dispatcher.run_delegate(
                        "df", "base", "sil", "vs2026", False, True)
            return ok, buf.getvalue(), pin_check, ref_check, sub_run

    def test_delegate_never_calls_the_removed_preflight_functions(self):
        ok, _, pin_check, ref_check, sub_run = self._delegate()
        self.assertTrue(ok)
        self.assertFalse(hasattr(build_dispatcher, "ensure_toolchain_exported"))
        self.assertFalse(hasattr(build_dispatcher, "export_first_party_deps"))
        pin_check.assert_called_once()
        ref_check.assert_called_once()
        sub_run.assert_called_once()

    def test_planted_violation_missing_first_party_ref_stops_before_subprocess(self):
        """§2b WP-4: 'a third-party ref missing from the cache stops the
        build naming the ref and setup.bat' - same shape for a first-party
        one here (NS-05's own row text: 'Any ref that is not in the cache
        and is not being built here stops the build, naming the ref and
        setup.bat'). PASS: refused, names the ref and --prepare, never
        starts the child process. FAIL: proceeds to build against a
        dependency that was never actually there."""
        ok, text, _, _, sub_run = self._delegate(
            missing_refs=[("mathlib", "adas-mathlib/1.0.0")])
        self.assertFalse(ok)
        self.assertIn("adas-mathlib/1.0.0", text)
        self.assertIn("setup.py --prepare df", text)
        sub_run.assert_not_called()

    def test_planted_violation_missing_toolchain_pin_stops_before_subprocess(self):
        ok, text, _, _, sub_run = self._delegate(missing_pin=["adas-toolchain/1.0.5"])
        self.assertFalse(ok)
        self.assertIn("adas-toolchain/1.0.5", text)
        self.assertIn(build_dispatcher.setup_command(), text)
        sub_run.assert_not_called()

    def _aggregate_install_cmd(self, remotes_state, missing_refs=()):
        import tempfile
        node = _node("adas-mathlib/1.0.0", "Cache")
        node["package_folder"] = "C:/cache/mathlib"
        patch = unittest.mock.patch.object
        with tempfile.TemporaryDirectory() as root, \
                patch(build_dispatcher, "ROOT", root), \
                patch(build_dispatcher, "is_valid_module", return_value=True), patch(build_dispatcher, "absent_first_party_refs", return_value={}), \
                patch(build_dispatcher, "module_package_type", return_value="shared-library"), \
                patch(build_dispatcher, "package_to_module_map", return_value=self.pkg_map), \
                patch(build_dispatcher, "apply_conan_home"), \
                patch(build_dispatcher, "missing_toolchain_pin", return_value=[]), \
                patch(build_dispatcher, "missing_cache_refs",
                      return_value=list(missing_refs)), \
                patch(build_dispatcher, "stale_cache_refs", return_value=([], [])), \
                patch(build_dispatcher, "generate_aggregate_conanfile"), \
                patch(build_dispatcher, "generate_aggregate_cmakelists"), \
                patch(build_dispatcher, "refresh_aggregate_used_shortcuts"), \
                patch(build_dispatcher, "run_logged", return_value=0), \
                patch(build_dispatcher, "read_editable_registrations", return_value={}), \
                patch(build_dispatcher, "run_install_logged",
                      return_value=(0, _graph(node))) as install_logged:
            try:
                build_dispatcher.run_aggregate_build(
                    "base", "df", "sil", "vs2026", [], False, False, False,
                    mode="package", remotes_state=remotes_state)
            except SystemExit:
                pass
            return install_logged

    def test_aggregate_conan_install_never_carries_update(self):
        """§2b WP-4: 'root build makes no ... --update (assert on the
        command list)'."""
        install_logged = self._aggregate_install_cmd(remotes_state=True)
        self.assertTrue(install_logged.called)
        cmd = install_logged.call_args[0][0]
        self.assertNotIn("--update", cmd)

    def test_aggregate_conan_install_carries_no_remote_flag_when_remotes_off(self):
        install_logged = self._aggregate_install_cmd(remotes_state=False)
        cmd = install_logged.call_args[0][0]
        self.assertIn("-nr", cmd)

    def test_aggregate_conan_install_omits_no_remote_flag_when_remotes_on(self):
        install_logged = self._aggregate_install_cmd(remotes_state=True)
        cmd = install_logged.call_args[0][0]
        self.assertNotIn("-nr", cmd)

    def test_planted_violation_aggregate_missing_pkg_only_ref_stops_before_install(self):
        install_logged = self._aggregate_install_cmd(
            remotes_state=True, missing_refs=[("mathlib", "adas-mathlib/1.0.0")])
        install_logged.assert_not_called()


class StaleCacheRefsTests(unittest.TestCase):
    """NS-05a (cache_first_no_server_plan.md D4a, STEP 3): stale_cache_refs()
    itself - pure function, read_prepared_modules()/compute_module_
    fingerprint() mocked, no real git/filesystem calls."""

    def test_missing_prepared_modules_json_warns_never_refuses(self):
        """§2b: 'missing json -> warns and proceeds'."""
        with unittest.mock.patch.object(build_dispatcher, "read_prepared_modules",
                                        return_value=None):
            stale, unrecorded = build_dispatcher.stale_cache_refs({"vantage"})
        self.assertEqual(stale, [])
        self.assertEqual(unrecorded, ["vantage"])

    def test_module_missing_from_recorded_data_is_unrecorded_not_stale(self):
        """A machine prepared before this mechanism existed has a real
        prepared_modules.json that simply doesn't mention this module yet -
        same 'warn, never refuse' treatment as the whole file being absent."""
        with unittest.mock.patch.object(build_dispatcher, "read_prepared_modules",
                                        return_value={}):
            stale, unrecorded = build_dispatcher.stale_cache_refs({"vantage"})
        self.assertEqual(stale, [])
        self.assertEqual(unrecorded, ["vantage"])

    def test_planted_violation_changed_git_head_is_stale(self):
        """§2b: 'touch a file in modules/sim -> a df build refuses naming
        both values' - simulated here as a HEAD change; the real-file
        version is the STEP 5 real-run proof."""
        recorded = {"vantage": {"ref": "adas-vantage/0.1.0", "git": "abc123", "dirty": "d1",
                            "fp_version": chr_.FINGERPRINT_VERSION}}
        with unittest.mock.patch.object(build_dispatcher, "read_prepared_modules",
                                        return_value=recorded), \
                unittest.mock.patch.object(build_dispatcher, "compute_module_fingerprint",
                                           return_value={"git": "def456", "dirty": "d1"}):
            stale, unrecorded = build_dispatcher.stale_cache_refs({"vantage"})
        self.assertEqual(stale, [("vantage", "abc123", "def456")])
        self.assertEqual(unrecorded, [])

    def test_planted_violation_dirty_change_alone_is_also_stale(self):
        """An uncommitted edit (same HEAD, different working-tree hash)
        must count as changed too - D4a's own 'the checked-out source has
        moved on' is about the working tree, not only committed history."""
        recorded = {"vantage": {"ref": "adas-vantage/0.1.0", "git": "abc123", "dirty": "d1",
                            "fp_version": chr_.FINGERPRINT_VERSION}}
        with unittest.mock.patch.object(build_dispatcher, "read_prepared_modules",
                                        return_value=recorded), \
                unittest.mock.patch.object(build_dispatcher, "compute_module_fingerprint",
                                           return_value={"git": "abc123", "dirty": "d2"}):
            stale, unrecorded = build_dispatcher.stale_cache_refs({"vantage"})
        self.assertEqual(stale, [("vantage", "abc123", "abc123")])

    def test_unchanged_fingerprint_is_neither_stale_nor_unrecorded(self):
        """§2b: 'revert -> it proceeds'."""
        recorded = {"vantage": {"ref": "adas-vantage/0.1.0", "git": "abc123", "dirty": "d1",
                            "fp_version": chr_.FINGERPRINT_VERSION}}
        with unittest.mock.patch.object(build_dispatcher, "read_prepared_modules",
                                        return_value=recorded), \
                unittest.mock.patch.object(build_dispatcher, "compute_module_fingerprint",
                                           return_value={"git": "abc123", "dirty": "d1"}):
            stale, unrecorded = build_dispatcher.stale_cache_refs({"vantage"})
        self.assertEqual(stale, [])
        self.assertEqual(unrecorded, [])

    def test_outdated_format_record_is_its_own_bucket_not_stale(self):
        """NS-52: a record with no fp_version (format 1, porcelain-only
        `dirty`) cannot be compared against a format-2 fingerprint. It must
        land in outdated_format_refs(), and NOT in `stale` - calling it stale
        would tell the developer their source changed when it did not."""
        for entry in ({"ref": "adas-vantage/0.1.0", "git": "abc123", "dirty": "d1"},
                      {"ref": "adas-vantage/0.1.0", "git": "abc123", "dirty": "d1",
                       "fp_version": 1}):
            with unittest.mock.patch.object(build_dispatcher, "read_prepared_modules",
                                            return_value={"vantage": entry}), \
                    unittest.mock.patch.object(build_dispatcher, "compute_module_fingerprint",
                                               return_value={"git": "abc123", "dirty": "d2"}):
                stale, unrecorded = build_dispatcher.stale_cache_refs({"vantage"})
                outdated = build_dispatcher.outdated_format_refs({"vantage"})
            self.assertEqual((stale, unrecorded, outdated), ([], [], ["vantage"]), entry)

    def test_outdated_format_refusal_says_format_not_source(self):
        """NS-52: the refusal text names the format change and --prepare, and
        never claims the source changed."""
        with unittest.mock.patch.object(build_dispatcher, "module_package_name",
                                        return_value="adas-sim"), \
                unittest.mock.patch.object(build_dispatcher, "module_version",
                                           return_value="0.1.0"):
            text = build_dispatcher.outdated_format_message("vantage", "df", "sil", "vs2026", "base")
        self.assertIn("fingerprint format", text)
        self.assertIn("--prepare df -t sil -p vs2026 -P base", text)
        self.assertNotIn("changed since it was cached", text)

    def _stale_msg(self, old, new):
        return build_dispatcher.stale_cache_message(
            "interfaces", "df", "sil", "vs2026", "base", old, new)

    def test_stale_message_commit_moved_offers_prepare_only(self):
        text = self._stale_msg("47a93bd6aaaa", "7090200abbbb")
        self.assertIn("47a93bd6 -> 7090200a", text)
        self.assertIn("python scripts/setup.py --prepare df -t sil -p vs2026 -P base", text)
        self.assertNotIn("--with", text)
        self.assertIn("moved its commit", text)

    def test_stale_message_same_commit_offers_with_before_prepare(self):
        for sha in ("47a93bd6aaaa", None):
            text = self._stale_msg(sha, sha)
            with_cmd = "python scripts/build.py df -t sil -p vs2026 -P base --with interfaces"
            self.assertIn(with_cmd, text)
            self.assertIn("--prepare df -t sil -p vs2026 -P base", text)
            self.assertLess(text.index("--with"), text.index("--prepare"))

    def test_stale_message_same_commit_shows_no_arrow(self):
        # "HEAD d88481a2 -> d88481a2" read as if something moved; it did not.
        text = self._stale_msg("d88481a2aaaa", "d88481a2aaaa")
        self.assertIn("(HEAD d88481a2, unchanged)", text)
        self.assertNotIn("->", text)

    def test_stale_message_one_sided_commit_claims_no_cause(self):
        text = self._stale_msg(None, "7090200abbbb")
        self.assertIn("--with interfaces", text)
        self.assertIn("--prepare df", text)
        self.assertIn("cause is unknown", text)
        self.assertNotIn("moved its commit", text)
        self.assertNotIn("uncommitted", text)

    def test_both_refusal_sites_use_the_shared_builder(self):
        """The two sites cannot drift: neither keeps its own f-string."""
        src = (build_dispatcher.__file__ and
               open(build_dispatcher.__file__, encoding="utf-8").read())
        self.assertEqual(src.count("log(stale_cache_message("), 2)
        self.assertEqual(src.count('f"ERROR: {dep} changed since it was cached "'), 0)

    def test_planted_violation_writer_carries_fp_version(self):
        """NS-52, planted: drop fp_version from record_prepared_module() and
        every record it writes reads back as outdated - this fails."""
        import tempfile
        import conan_home_resolution as chr_
        with tempfile.TemporaryDirectory() as tmp:
            chr_.record_prepared_module(tmp, "vantage", "adas-vantage/0.1.0", tmp)
            entry = chr_.read_prepared_modules(tmp)["vantage"]
        self.assertEqual(entry.get("fp_version"), chr_.FINGERPRINT_VERSION)
        self.assertFalse(chr_.record_is_outdated_format(entry))


class StaleCacheRefusalIntegrationTests(_FakeRepo):
    """NS-05a end-to-end through run_delegate()/run_aggregate_build(), with
    stale_cache_refs() itself mocked (StaleCacheRefsTests above already
    covers its own logic in isolation)."""

    CONFS = {"df": _conf(["adas-sim/0.1.0"]), "sim": _conf()}
    VERSIONS = {"df": "1.0.0", "sim": "0.1.0"}

    def _delegate(self, stale=(), unrecorded=()):
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "modules", "df", "scripts"))
            open(os.path.join(root, "modules", "df", "scripts", "build.py"), "w").close()
            os.makedirs(os.path.join(root, "conan_workarea", "logs"))
            patch = unittest.mock.patch.object
            with patch(build_dispatcher, "ROOT", root), \
                    patch(build_dispatcher, "apply_conan_home"), \
                    patch(build_dispatcher, "absent_first_party_refs", return_value={}), \
                    patch(build_dispatcher, "package_to_module_map", return_value=self.pkg_map), \
                    patch(build_dispatcher, "forward_closure", return_value={"df", "sim"}), \
                    patch(build_dispatcher, "missing_toolchain_pin", return_value=[]), \
                    patch(build_dispatcher, "missing_cache_refs", return_value=[]), \
                    patch(build_dispatcher, "stale_cache_refs",
                          return_value=(list(stale), list(unrecorded))) as stale_check, \
                    patch(build_dispatcher.subprocess, "run",
                          return_value=unittest.mock.Mock(returncode=0)) as sub_run:
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    ok = build_dispatcher.run_delegate(
                        "df", "base", "sil", "vs2026", False, True)
            return ok, buf.getvalue(), stale_check, sub_run

    def test_planted_violation_stale_dependency_refuses_naming_both_revisions(self):
        ok, text, _, sub_run = self._delegate(stale=[("sim", "abc123", "def456")])
        self.assertFalse(ok)
        self.assertIn("sim changed since it was cached", text)
        self.assertIn("abc123", text)
        self.assertIn("def456", text)
        self.assertIn("setup.py --prepare df", text)
        sub_run.assert_not_called()

    def test_unstale_dependency_proceeds(self):
        ok, _, _, sub_run = self._delegate(stale=[])
        self.assertTrue(ok)
        sub_run.assert_called_once()

    def test_no_record_refuses_naming_ref_and_prepare_command(self):
        """NS-37 (RQ-4, cache_first_no_server_plan.md): NS-05a's grace
        period for a missing freshness record is over -- a first-party ref
        resolved from the cache with no record now refuses exactly like a
        stale one, never proceeds with a warning."""
        ok, text, _, sub_run = self._delegate(stale=[], unrecorded=["sim"])
        self.assertFalse(ok)
        self.assertIn("sim", text)
        self.assertIn("adas-sim/0.1.0", text)
        self.assertIn("no recorded freshness fingerprint", text)
        self.assertIn("NS-37/RQ-4", text)
        self.assertIn("setup.py --prepare df", text)
        sub_run.assert_not_called()

    def test_several_unrecorded_refs_print_the_recovery_command_once(self):
        # Deleting the superproject's conan_workarea/ drops every record at
        # once; the one command that re-records them all is printed once.
        ok, text, _, _ = self._delegate(stale=[], unrecorded=["interfaces", "sim", "viz"])
        self.assertFalse(ok)
        self.assertEqual(text.count("--prepare df"), 1)
        for dep in ("interfaces", "sim", "viz"):
            self.assertIn(f"{dep} (", text)
        self.assertIn("to build and record them", text)

    def test_stale_check_only_examines_deps_not_the_primary_module_itself(self):
        _, _, stale_check, _ = self._delegate()
        stale_check.assert_called_once_with({"sim"})

    def test_with_named_module_is_excluded_from_the_stale_check(self):
        """§2b: 'a module being built here (--with sim) is never checked'."""
        import tempfile
        patch = unittest.mock.patch.object
        with tempfile.TemporaryDirectory() as root, \
                patch(build_dispatcher, "ROOT", root), \
                patch(build_dispatcher, "is_valid_module", return_value=True), patch(build_dispatcher, "absent_first_party_refs", return_value={}), \
                patch(build_dispatcher, "module_package_type", return_value="shared-library"), \
                patch(build_dispatcher, "package_to_module_map", return_value=self.pkg_map), \
                patch(build_dispatcher, "apply_conan_home"), \
                patch(build_dispatcher, "missing_toolchain_pin", return_value=[]), \
                patch(build_dispatcher, "missing_cache_refs", return_value=[]), \
                patch(build_dispatcher, "stale_cache_refs", return_value=([], [])) as stale_check, \
                patch(build_dispatcher, "generate_aggregate_conanfile"), \
                patch(build_dispatcher, "generate_aggregate_cmakelists"), \
                patch(build_dispatcher, "refresh_aggregate_used_shortcuts"), \
                patch(build_dispatcher, "run_logged", return_value=0), \
                patch(build_dispatcher, "read_editable_registrations", return_value={}), \
                patch(build_dispatcher, "run_install_logged", return_value=(0, _graph())):
            build_dispatcher.run_aggregate_build(
                "base", "df", "sil", "vs2026", ["sim"], False, False, False, mode="package")
        stale_check.assert_not_called()


class RequireToolchainCheckoutTests(unittest.TestCase):
    """W0 / D0 (partial_clone_correctness_plan.md): modules/toolchain is always
    checked out; its absence refuses before any conan call."""

    def _main(self, root):
        patch = unittest.mock.patch
        out = io.StringIO()
        with patch.object(build_dispatcher, "ROOT", root),                 patch.object(build_dispatcher.sys, "argv",
                             ["build.py", "df", "-t", "sil", "-p", "vs2026", "--remotes", "off"]),                 patch.object(build_dispatcher, "all_projects", return_value=["base"]),                 patch.object(build_dispatcher, "is_valid_module", return_value=True), patch.object(build_dispatcher, "absent_first_party_refs", return_value={}),                 patch.object(build_dispatcher, "run_delegate", return_value=True) as dele,                 patch("sys.stdout", out):
            with self.assertRaises(SystemExit) as cm:
                build_dispatcher.main()
        return cm.exception.code, out.getvalue(), dele

    def test_absent_toolchain_refuses_with_init_command_before_dispatch(self):
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "modules", "toolchain"))  # empty = uninitialised
            code, text, dele = self._main(root)
        self.assertEqual(code, 1)
        self.assertIn("git submodule update --init modules/toolchain", text)
        dele.assert_not_called()

    def test_present_toolchain_dispatches_as_before(self):
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "modules", "toolchain"))
            with open(os.path.join(root, "modules", "toolchain", "VERSION"), "w") as f:
                f.write("1.0.6")
            code, text, dele = self._main(root)
        self.assertEqual(code, 0)
        dele.assert_called_once()

    def _pin_refusal_text(self, platform):
        with unittest.mock.patch.object(build_dispatcher.sys, "platform", platform):
            return self._pin_text()

    def _pin_text(self):
        # the aggregate pin refusal (RootDefaultModeTests._pin_order) is the
        # same message the delegate prints; drive the delegate here.
        import tempfile
        patch = unittest.mock.patch.object
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "modules", "df", "scripts"))
            open(os.path.join(root, "modules", "df", "scripts", "build.py"), "w").close()
            with patch(build_dispatcher, "ROOT", root),                     patch(build_dispatcher, "apply_conan_home"),                     patch(build_dispatcher, "package_to_module_map", return_value={}),                     patch(build_dispatcher, "forward_closure", return_value={"df"}),                     patch(build_dispatcher, "missing_toolchain_pin",
                          return_value=["adas-toolchain/9.9.9"]),                     patch(build_dispatcher, "missing_cache_refs", return_value=[]),                     contextlib.redirect_stdout(out):
                build_dispatcher.run_delegate("df", "base", "sil", "vs2026", False, True)
        return out.getvalue()

    def test_pin_refusal_names_setup_per_platform_and_no_submodules(self):
        # The partial-clone-safe form leads; it is not a parenthesis (F3).
        linux = self._pin_refusal_text("linux")
        self.assertIn("run python3 scripts/setup.py --no-submodules", linux)
        self.assertNotIn("setup.bat", linux)  # P4.3
        win = self._pin_refusal_text("win32")
        self.assertIn("run setup.bat --no-submodules", win)

    def test_setup_command_per_platform(self):
        for platform, expected in (("win32", "setup.bat"), ("linux", "python3 scripts/setup.py")):
            with unittest.mock.patch.object(chr_.sys, "platform", platform):
                self.assertEqual(chr_.setup_command(), expected)



class _PartialCloneRoot(_FakeRepo):
    """A scratch ROOT holding only `df` and `toolchain` as checked-out
    modules; `interfaces`/`mathlib` exist as EMPTY folders (an uninitialised
    submodule). df requires them."""

    CONFS = {"df": _conf(["adas-interfaces/1.0.0", "adas-mathlib/1.0.0", "protobuf/3.21.12"])}
    VERSIONS = {"df": "1.0.0"}

    def setUp(self):
        super().setUp()
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = tmp.name
        for folder in ("df", "interfaces", "mathlib", "toolchain"):
            os.makedirs(os.path.join(self.root, "modules", folder))
        os.makedirs(os.path.join(self.root, "modules", "df", "scripts"))
        open(os.path.join(self.root, "modules", "df", "scripts", "build.py"), "w").close()
        with open(os.path.join(self.root, "modules", "toolchain", "VERSION"), "w") as f:
            f.write("1.0.6")
        os.makedirs(os.path.join(self.root, "conan_workarea", "logs"))
        patcher = unittest.mock.patch.object(build_dispatcher, "ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = unittest.mock.patch.object(build_dispatcher, "is_valid_module",
                                              side_effect=lambda mod: mod in self.CONFS)
        patcher.start()
        self.addCleanup(patcher.stop)


class ModuleForPackageTests(_PartialCloneRoot):

    def test_convention_and_exception(self):
        os.makedirs(os.path.join(self.root, "modules", "shared_config"))
        self.assertEqual(build_dispatcher.module_for_package("adas-interfaces"), "interfaces")
        self.assertEqual(build_dispatcher.module_for_package("adas-shared-config"), "shared_config")

    def test_third_party_is_none(self):
        self.assertIsNone(build_dispatcher.module_for_package("protobuf"))

    def test_first_party_name_with_no_folder_refuses_naming_the_package(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            build_dispatcher.module_for_package("adas-nosuch")
        self.assertIn("adas-nosuch", out.getvalue())
        self.assertIn("PACKAGE_DIR_EXCEPTIONS", out.getvalue())


class AbsentFirstPartyRefsTests(_PartialCloneRoot):

    def test_absent_dependencies_are_collected_as_refs(self):
        self.assertEqual(build_dispatcher.absent_first_party_refs({"df"}, "base"),
                         {"interfaces": "adas-interfaces/1.0.0", "mathlib": "adas-mathlib/1.0.0"})

    def test_present_dependency_is_not_absent(self):
        self.CONFS["interfaces"] = _conf()
        self.assertEqual(build_dispatcher.absent_first_party_refs({"df"}, "base"),
                         {"mathlib": "adas-mathlib/1.0.0"})


class AbsentDepGateTests(_PartialCloneRoot):
    """D9: in the cache -> silent; not cached -> refusal, whatever the remotes
    switch says (NS-07: the component build refuses an uncached first-party
    dependency and nothing downloads one)."""

    ABSENT = {"interfaces": "adas-interfaces/1.0.0"}

    def _gate(self, cached, platform="win32"):
        patch = unittest.mock.patch.object
        with patch(build_dispatcher.check_conan_resolution, "pinned_profile_settings",
                   return_value={"os": "Windows"}), \
                patch(build_dispatcher.check_conan_resolution, "_cache_matches_profile",
                      return_value=cached), \
                patch(build_dispatcher.sys, "platform", platform):
            return build_dispatcher.absent_dep_problems(
                self.ABSENT, "df", "sil", "vs2026", "base")

    def test_cached_is_silent(self):
        self.assertEqual(self._gate(True), [])

    def test_not_cached_refuses_with_the_followable_route(self):
        errors = self._gate(False)
        self.assertEqual(len(errors), 1)
        self.assertIn("adas-interfaces/1.0.0", errors[0])
        self.assertIn("git submodule update --init modules/interfaces", errors[0])
        self.assertIn("python scripts/setup.py --prepare df -t sil -p vs2026 -P base", errors[0])
        self.assertNotIn("--remotes", errors[0])

    def test_refusal_names_the_platform_correct_setup_command(self):
        errors = self._gate(False, platform="linux")
        self.assertIn("python3 scripts/setup.py --prepare df", errors[0])

    def _delegate(self, remotes_state, cached):
        patch = unittest.mock.patch.object
        out = io.StringIO()
        with patch(build_dispatcher, "apply_conan_home"), \
                patch(build_dispatcher, "package_to_module_map",
                      return_value={"adas-df": "df"}), \
                patch(build_dispatcher, "missing_toolchain_pin", return_value=[]), \
                patch(build_dispatcher, "stale_cache_refs", return_value=([], [])), \
                patch(build_dispatcher.check_conan_resolution, "pinned_profile_settings",
                      return_value={"os": "Windows"}), \
                patch(build_dispatcher.check_conan_resolution, "_cache_matches_profile",
                      return_value=cached), \
                patch(build_dispatcher.subprocess, "run",
                      return_value=unittest.mock.Mock(returncode=0)) as sub_run, \
                contextlib.redirect_stdout(out):
            ok = build_dispatcher.run_delegate("df", "base", "sil", "vs2026", False, True,
                                               remotes_state=remotes_state)
        return ok, out.getvalue(), sub_run

    def test_delegate_partial_clone_dependencies_cached_proceeds(self):
        ok, text, sub_run = self._delegate(False, cached=True)
        self.assertTrue(ok)
        self.assertNotIn("ERROR", text)
        sub_run.assert_called_once()

    def test_delegate_not_cached_refuses_before_subprocess_remotes_off(self):
        ok, text, sub_run = self._delegate(False, cached=False)
        self.assertFalse(ok)
        self.assertIn("git submodule update --init modules/interfaces", text)
        sub_run.assert_not_called()

    def test_delegate_not_cached_still_refuses_with_remotes_on(self):
        ok, text, sub_run = self._delegate(True, cached=False)
        self.assertFalse(ok)
        self.assertNotIn("NOTE", text)
        self.assertIn("git submodule update --init modules/interfaces", text)
        sub_run.assert_not_called()


class FullCheckoutTransitiveFreshnessTests(_FakeRepo):
    """D2 regression guard: with every module present, a change in `sim`
    (reached only through viz) must still reach the delegate's freshness
    check, and a changed present dependency must still refuse."""

    CONFS = {"df": _conf(["adas-viz/1.0.0"]), "viz": _conf(["adas-sim/0.1.0"]),
             "sim": _conf()}
    VERSIONS = {"df": "1.0.0", "viz": "1.0.0", "sim": "0.1.0"}

    def _delegate(self, stale):
        import tempfile
        patch = unittest.mock.patch.object
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as root:
            for folder in self.CONFS:
                os.makedirs(os.path.join(root, "modules", folder, "scripts"))
            open(os.path.join(root, "modules", "df", "scripts", "build.py"), "w").close()
            os.makedirs(os.path.join(root, "conan_workarea", "logs"))
            with patch(build_dispatcher, "ROOT", root), \
                    patch(build_dispatcher, "is_valid_module",
                          side_effect=lambda m: m in self.CONFS), \
                    patch(build_dispatcher, "apply_conan_home"), \
                    patch(build_dispatcher, "package_to_module_map", return_value=self.pkg_map), \
                    patch(build_dispatcher, "missing_toolchain_pin", return_value=[]), \
                    patch(build_dispatcher, "missing_cache_refs", return_value=[]), \
                    patch(build_dispatcher, "stale_cache_refs",
                          return_value=(stale, [])) as stale_check, \
                    patch(build_dispatcher.subprocess, "run",
                          return_value=unittest.mock.Mock(returncode=0)) as sub_run, \
                    contextlib.redirect_stdout(out):
                ok = build_dispatcher.run_delegate("df", "base", "sil", "vs2026", False, True)
        return ok, out.getvalue(), stale_check, sub_run

    def test_sim_behind_viz_is_still_checked(self):
        _, _, stale_check, _ = self._delegate([])
        self.assertEqual(set(stale_check.call_args[0][0]), {"viz", "sim"})

    def test_a_changed_transitive_dependency_refuses(self):
        ok, text, _, sub_run = self._delegate([("sim", "aaaa1111", "bbbb2222")])
        self.assertFalse(ok)
        self.assertIn("sim", text)
        sub_run.assert_not_called()


class StaleCacheRefsAbsentModuleTests(_PartialCloneRoot):
    """W2 / D1: no source, no claim - an absent module is in neither list,
    even with no prepared_modules.json (F5)."""

    def test_absent_module_with_no_record_file_is_neither_stale_nor_unrecorded(self):
        with unittest.mock.patch.object(build_dispatcher, "read_prepared_modules",
                                         return_value=None):
            self.assertEqual(build_dispatcher.stale_cache_refs(["interfaces", "mathlib"]),
                             ([], []))

    def test_planted_inverse_a_present_module_with_no_record_is_unrecorded(self):
        with unittest.mock.patch.object(build_dispatcher, "read_prepared_modules",
                                         return_value=None):
            self.assertEqual(build_dispatcher.stale_cache_refs(["interfaces", "df"]),
                             ([], ["df"]))


class WithAbsentDependencyTests(_PartialCloneRoot):

    def _fake_init(self, calls):
        """Stands in for init_submodules_for: 'checks out' each module (it
        becomes valid and declares nothing further)."""
        def fake(mods, **kwargs):
            calls.append((list(mods), kwargs))
            for mod in mods:
                self.CONFS[mod] = _conf()
            return list(mods)
        return fake

    class _Stop(Exception):
        pass

    def test_with_all_initialises_the_closure_then_continues(self):
        calls = []
        patch = unittest.mock.patch.object
        with patch(build_dispatcher, "package_to_module_map",
                   side_effect=lambda: {f"adas-{m}": m for m in self.CONFS}), \
                patch(build_dispatcher, "init_submodules_for", side_effect=self._fake_init(calls)), \
                patch(build_dispatcher, "partition_aggregate_modules",
                      side_effect=self._Stop), \
                self.assertRaises(self._Stop):
            build_dispatcher.run_aggregate_build("base", "df", "sil", "vs2026", [], True,
                                                 False, False)
        self.assertEqual([c[0] for c in calls], [["interfaces", "mathlib"]])

    def test_with_all_with_remotes_off_still_initialises_the_closure(self):
        # The Conan remotes switch is not a git switch: on a machine where it
        # is always off, --with-all must still check its closure out.
        calls = []
        patch = unittest.mock.patch.object
        with patch(build_dispatcher, "package_to_module_map",
                   side_effect=lambda: {f"adas-{m}": m for m in self.CONFS}), \
                patch(build_dispatcher, "init_submodules_for", side_effect=self._fake_init(calls)), \
                patch(build_dispatcher, "partition_aggregate_modules",
                      side_effect=self._Stop), \
                self.assertRaises(self._Stop):
            build_dispatcher.run_aggregate_build("base", "df", "sil", "vs2026", [], True,
                                                 False, False, remotes_state=False)
        self.assertEqual([c[0] for c in calls], [["interfaces", "mathlib"]])

    def _main(self, argv, uninitialised, calls):
        """main() with git's not-initialised list faked; stops at the
        project check so nothing past the checkout step runs."""
        patch = unittest.mock.patch.object
        with patch(build_dispatcher.sys, "argv", ["build.py"] + argv), \
                patch(build_dispatcher, "possibly_uninitialised",
                      side_effect=lambda mods, root: list(mods)), \
                patch(build_dispatcher, "uninitialised_submodules",
                      return_value=list(uninitialised)), \
                patch(build_dispatcher, "init_submodules_for", side_effect=self._fake_init(calls)), \
                patch(build_dispatcher, "all_projects", side_effect=self._Stop), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(self._Stop):
            build_dispatcher.main()

    def test_fresh_clone_delegate_checks_out_the_named_module_and_toolchain(self):
        calls = []
        self._main(["vdy", "-t", "sil", "-p", "vs2026"],
                   ["df", "interfaces", "toolchain", "vdy"], calls)
        self.assertEqual([c[0] for c in calls], [["toolchain", "vdy"]])  # never a dependency

    def test_fresh_clone_aggregate_checks_out_the_primary_first(self):
        calls = []
        self._main(["vdy", "-t", "sil", "-p", "vs2026", "--with-all"], ["vdy"], calls)
        self.assertEqual([c[0] for c in calls], [["vdy"]])

    def test_fan_out_checks_out_toolchain_only(self):
        calls = []
        self._main(["all", "-t", "sil", "-p", "vs2026"], ["df", "toolchain"], calls)
        self.assertEqual([c[0] for c in calls], [["toolchain"]])

    def test_checked_out_modules_are_never_passed_to_git(self):
        # Covers a checked-out placeholder too (no conanfile.py, but git
        # reports it initialised): it keeps today's `unknown module` error.
        calls = []
        self._main(["isp", "-t", "sil", "-p", "vs2026"], [], calls)
        self.assertEqual(calls, [])

    def test_checkout_command_initialises_module_and_toolchain_only(self):
        calls = []
        os.makedirs(os.path.join(self.root, "modules", "vdy"))
        with unittest.mock.patch.object(build_dispatcher, "possibly_uninitialised",
                                         side_effect=lambda mods, root: list(mods)), \
                unittest.mock.patch.object(build_dispatcher, "uninitialised_submodules",
                                           return_value=["toolchain", "vdy", "interfaces"]), \
                unittest.mock.patch.object(build_dispatcher, "init_submodules_for",
                                           side_effect=self._fake_init(calls)):
            build_dispatcher.checkout_modules(["vdy"])
        self.assertEqual([c[0] for c in calls], [["toolchain", "vdy"]])

    def test_checkout_command_refuses_an_unknown_name(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            build_dispatcher.checkout_modules(["nosuch"])
        self.assertIn("no such module: nosuch", out.getvalue())

    def test_config_lists_modules_not_checked_out_but_never_toolchain(self):
        out = io.StringIO()
        with unittest.mock.patch.object(build_dispatcher, "all_projects", return_value=[]), \
                unittest.mock.patch.object(build_dispatcher, "uninitialised_submodules",
                                           return_value=["df", "toolchain", "vdy"]), \
                contextlib.redirect_stdout(out):
            build_dispatcher.print_config()
        self.assertIn("not checked out: df vdy\n", out.getvalue())
        self.assertIn("build.py checkout <module...>", out.getvalue())

    def test_config_prints_no_such_line_when_everything_is_checked_out(self):
        out = io.StringIO()
        with unittest.mock.patch.object(build_dispatcher, "all_projects", return_value=[]), \
                unittest.mock.patch.object(build_dispatcher, "uninitialised_submodules",
                                           return_value=[]), \
                contextlib.redirect_stdout(out):
            build_dispatcher.print_config()
        self.assertNotIn("not checked out", out.getvalue())

    def test_main_with_initialises_only_the_named_absent_dependency(self):
        calls = []
        patch = unittest.mock.patch.object
        with patch(build_dispatcher.sys, "argv", ["build.py", "df", "-t", "sil", "-p", "vs2026",
                                                  "--with", "interfaces", "--remotes", "on"]), \
                patch(build_dispatcher, "all_projects", return_value=["base"]), \
                patch(build_dispatcher, "package_to_module_map",
                      side_effect=lambda: {f"adas-{m}": m for m in self.CONFS}), \
                patch(build_dispatcher, "init_submodules_for", side_effect=self._fake_init(calls)), \
                patch(build_dispatcher, "run_aggregate_build") as aggregate, \
                contextlib.redirect_stdout(io.StringIO()):
            build_dispatcher.main()
        self.assertEqual([c[0] for c in calls], [["interfaces"]])  # not mathlib
        aggregate.assert_called_once()

    def test_delegate_never_clones_a_dependency(self):
        with unittest.mock.patch.object(build_dispatcher, "init_submodules_for") as init:
            AbsentDepGateTests._delegate(self, False, cached=True)
        init.assert_not_called()

    def test_with_absent_dependency_says_not_checked_out(self):
        out = io.StringIO()
        with unittest.mock.patch.object(build_dispatcher, "package_to_module_map",
                                         return_value={"adas-df": "df"}), \
                contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            build_dispatcher.validate_with_module("interfaces", "df", "base")
        self.assertIn("'interfaces' is a dependency of 'df' but is not checked out", out.getvalue())
        self.assertIn("git submodule update --init modules/interfaces", out.getvalue())

    def test_with_a_name_that_is_not_a_module_keeps_the_old_message(self):
        out = io.StringIO()
        with unittest.mock.patch.object(build_dispatcher, "package_to_module_map",
                                         return_value={"adas-df": "df"}), \
                contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            build_dispatcher.validate_with_module("nosuch", "df", "base")
        self.assertIn("unknown --with module 'nosuch'", out.getvalue())


if __name__ == "__main__":
    unittest.main()
