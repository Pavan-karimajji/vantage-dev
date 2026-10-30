"""scripts/tests/test_check_invariants_dll.py

DLL-1 (python_tool_envs_plan.md PT-40): df's replay/bridge DLL lookup keeps
the ONE permitted copy of the build's folder naming; check_invariants
evaluates it against workarea.py / build.py / bundle_layout.py for the same
inputs. Planted: each naming function of the copy changed in turn -> a
finding naming it.

Run:
    py -3.12 -m unittest scripts.tests.test_check_invariants_dll
"""
import importlib.util
import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_invariants as ci  # noqa: E402

LOOKUP = ci.ROOT / "modules" / "df" / "tools" / "carla" / "dll_lookup.py"


def _load_copy():
    spec = importlib.util.spec_from_file_location("_t_dll_lookup", LOOKUP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Dll1Tests(unittest.TestCase):

    def setUp(self):
        if not LOOKUP.is_file():
            self.skipTest("modules/df is not checked out")

    def test_real_tree_is_clean(self):
        self.assertEqual(ci.check_dll1(), [])

    def _compare_with(self, **overrides):
        real = _load_copy()
        fake = types.SimpleNamespace(**{k: getattr(real, k) for k in (
            "WORKAREA_DIRNAME", "component_build_dirname", "root_build_dirname",
            "aggregate_subdir", "HOST_BUNDLE_PLATFORM")})
        for key, value in overrides.items():
            setattr(fake, key, value)
        return ci._dll1_compare(
            fake,
            lambda folder, t, p: Path(folder) / "conan_workarea" / f"build-{t}-{p}",
            lambda t, p, proj, prim, mods, with_all:
                f"build-{t}-{p}-{proj}-{prim}-pkg-{'agg' if (with_all or mods) else 'solo'}",
            lambda mod: f"_bd_{mod}",
            {"win32": "vs2026", "linux": "ubuntu_gcc"})

    def test_equal_copy_has_no_finding(self):
        self.assertEqual(self._compare_with(), [])

    def test_planted_component_folder_changed(self):
        out = self._compare_with(component_build_dirname=lambda t, p: f"build-{p}-{t}")
        self.assertTrue(out and all("DLL-1" in f for f in out))
        self.assertIn("workarea.py", out[0])

    def test_planted_root_folder_changed(self):
        out = self._compare_with(
            root_build_dirname=lambda t, p, proj, prim, scope: f"build-{t}-{p}-{proj}-{prim}-{scope}")
        self.assertTrue(any("ws_folder_name" in f for f in out))

    def test_planted_aggregate_subdir_changed(self):
        out = self._compare_with(aggregate_subdir=lambda m: f"_build_{m}")
        self.assertTrue(any("aggregate subfolder" in f for f in out))

    def test_planted_host_map_changed(self):
        out = self._compare_with(HOST_BUNDLE_PLATFORM={"win32": "vs2022", "linux": "ubuntu_gcc"})
        self.assertTrue(any("HOST_BUNDLE_PLATFORM" in f for f in out))


if __name__ == "__main__":
    unittest.main()
