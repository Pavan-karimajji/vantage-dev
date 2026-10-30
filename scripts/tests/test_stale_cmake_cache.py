"""scripts/tests/test_stale_cmake_cache.py

2026-09-29: a reused build folder kept PROTOC_PROGRAM pointing at a Conan
cache that was gone (a deleted cold-check scratch CONAN_HOME) -> "The system
cannot find the path specified" on the first .proto of the next build.
Configure now -U's every FILEPATH/PATH cache entry whose absolute path no
longer exists. Two copies (the aggregate cannot import adas_build_tools):
scripts/build.py and modules/toolchain/adas_build_tools/cmake_cache.py --
held to the same answers here. Planted: a CMakeCache.txt with gone,
alive, -NOTFOUND, relative and non-path entries.

Run:
    py -3.12 -m unittest scripts.tests.test_stale_cmake_cache
"""
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS.parent / "modules" / "toolchain"))
import build  # noqa: E402

try:
    from adas_build_tools import cmake_cache  # noqa: E402
except ImportError:  # modules/toolchain not checked out
    cmake_cache = None


class StaleCmakeCacheTests(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="stale_cmake_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        alive = self.tmp / "alive.exe"
        alive.write_text("", encoding="utf-8")
        gone = (self.tmp / "gone_conan_home" / "bin" / "protoc.exe").as_posix()
        (self.tmp / "CMakeCache.txt").write_text(
            "// comment\n"
            f"PROTOC_PROGRAM:FILEPATH={gone}\n"
            f"protobuf_DIR:PATH={Path(gone).parent.as_posix()}\n"
            f"ALIVE:FILEPATH={alive.as_posix()}\n"
            "LIB:FILEPATH=LIB-NOTFOUND\n"
            "REL:PATH=relative/dir\n"
            "EMPTY:PATH=\n"
            "CMAKE_BUILD_TYPE:STRING=/not/a/path\n", encoding="utf-8")
        self.expected = ["PROTOC_PROGRAM", "protobuf_DIR"]

    def test_aggregate_names_only_gone_absolute_paths(self):
        self.assertEqual(build.stale_cmake_cache_vars(self.tmp), self.expected)

    def test_no_cache_is_nothing(self):
        self.assertEqual(build.stale_cmake_cache_vars(self.tmp / "nope"), [])

    def test_both_copies_agree(self):
        if cmake_cache is None:
            self.skipTest("modules/toolchain is not checked out")
        self.assertEqual(cmake_cache.stale_cmake_cache_vars(self.tmp), self.expected)
        self.assertEqual(cmake_cache.unset_flags(self.tmp), [f"-U{n}" for n in self.expected])

    def test_aggregate_configure_passes_the_unsets(self):
        """The aggregate's configure step applies the unsets through
        cmake_cmd_with_unsets() before it runs (planted: an append fails)."""
        src = (SCRIPTS / "build.py").read_text(encoding="utf-8")
        block = src[src.index('log("[aggregate] cmake configure ...")'):
                    src.index('log("[aggregate] cmake build ...")')]
        self.assertIn("stale_cmake_cache_vars(ws_dir)", block)
        self.assertIn("configure_cmd = cmake_cmd_with_unsets(configure_cmd, stale)", block)
        self.assertNotRegex(block, r"configure_cmd \+= \[f\"-U")
        self.assertLess(block.index("cmake_cmd_with_unsets("), block.index("run_logged(configure_cmd"))

    def test_every_unset_before_every_define_both_copies(self):
        """Review 2026-09-29: CMake applies -D/-U in order -- an -U after
        -DFOO=new erases FOO. Stale Python3_EXECUTABLE (passed with -D) and
        PROTOC_PROGRAM (not passed): PROTOC_PROGRAM is unset, every -U comes
        before every -D, and the -D'd name is never unset."""
        cmd = ["cmake", "-S", ".", "-B", ".", "-DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake",
               "-DPython3_EXECUTABLE=C:/new/python.exe"]
        names = ["PROTOC_PROGRAM", "Python3_EXECUTABLE"]
        results = [build.cmake_cmd_with_unsets(cmd, names)]
        if cmake_cache is not None:
            results.append(cmake_cache.with_unsets(cmd, names))
        for out in results:
            u = [i for i, a in enumerate(out) if a.startswith("-U")]
            d = [i for i, a in enumerate(out) if a.startswith("-D")]
            self.assertEqual(out[0], "cmake")
            self.assertIn("-UPROTOC_PROGRAM", out)
            self.assertNotIn("-UPython3_EXECUTABLE", out)
            self.assertLess(max(u), min(d), out)
        if len(results) == 2:
            self.assertEqual(results[0], results[1])

    @unittest.skipUnless(shutil.which("cmake"), "cmake not on PATH")
    def test_real_cmake_keeps_the_define(self):
        cmake = shutil.which("cmake")
        src = self.tmp / "src"
        src.mkdir()
        (src / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.16)\nproject(p NONE)\n", encoding="utf-8")
        b = self.tmp / "b"
        gone = (self.tmp / "gone").as_posix()
        subprocess.run([cmake, "-S", str(src), "-B", str(b),
                        f"-DPython3_EXECUTABLE:FILEPATH={gone}/py.exe",
                        f"-DPROTOC_PROGRAM:FILEPATH={gone}/protoc.exe"],
                       check=True, capture_output=True)
        new = (self.tmp / "python.exe").as_posix()
        cmd = [cmake, "-S", str(src), "-B", str(b), f"-DPython3_EXECUTABLE:FILEPATH={new}"]
        subprocess.run(build.cmake_cmd_with_unsets(cmd, build.stale_cmake_cache_vars(b)),
                       check=True, capture_output=True)
        text = (b / "CMakeCache.txt").read_text(encoding="utf-8")
        self.assertIn(f"Python3_EXECUTABLE:FILEPATH={new}", text)
        self.assertNotIn("PROTOC_PROGRAM:", text)


if __name__ == "__main__":
    unittest.main()
