"""scripts/tests/test_check_invariants_sig.py

SIG-1 (R-IFACE-4's shape check in the always-on gate): the real tree is clean
and its waiver is printed; a payload without a header is a finding; the check
never skips silently -- no protoc, or no interfaces module, is a finding that
names the reason.

Run:
    py -3.12 -m unittest scripts.tests.test_check_invariants_sig
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_invariants as ci  # noqa: E402

INTERFACES = ci.ROOT / "modules" / "interfaces"


def _csh():
    sys.path.insert(0, str(INTERFACES / "scripts"))
    try:
        import check_signal_header
    finally:
        sys.path.pop(0)
    return check_signal_header


class Sig1Tests(unittest.TestCase):

    def setUp(self):
        if not (INTERFACES / "scripts" / "check_signal_header.py").is_file():
            self.skipTest("modules/interfaces is not checked out")
        self.csh = _csh()
        try:
            self.csh.find_protoc()
        except self.csh.CheckError as exc:
            self.skipTest(f"SIG-1 needs protoc: {exc}")

    def test_real_tree_is_clean_and_the_waiver_is_printed(self):
        self.assertEqual(ci.check_sig1(), [])
        self.assertTrue(any("waived   adas.isp.ProcessedFrame" in n and "IFQ-04" in n for n in ci.SIG1_NOTES),
                        ci.SIG1_NOTES)

    def test_planted_payload_without_a_header_is_a_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / "modules" / "interfaces" / "scripts"
            shutil.copytree(INTERFACES / "scripts", scripts, ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(INTERFACES / "proto", root / "modules" / "interfaces" / "proto")
            (root / "modules" / "interfaces" / "proto" / "plant.proto").write_text(
                'syntax = "proto3";\npackage plant;\nmessage Bare { uint32 x = 1; }\n', encoding="utf-8")
            ports = root / "modules" / "plant" / "conf" / "ports.yaml"
            ports.parent.mkdir(parents=True)
            ports.write_text("component: plant\ninputs:\n  - {name: bare, proto_type: plant.Bare, binds: bare}\n",
                             encoding="utf-8")
            sys.modules.pop("check_signal_header", None)
            try:
                findings = ci.check_sig1(root)
            finally:
                sys.modules.pop("check_signal_header", None)
            self.assertEqual(len(findings), 1, findings)
            self.assertTrue(findings[0].startswith("SIG-1 plant.Bare") and "no `sig_header`" in findings[0])

    def test_no_protoc_is_a_named_finding_never_a_skip(self):
        with mock.patch.object(self.csh, "find_protoc", side_effect=self.csh.CheckError("no working protoc: x")):
            findings = ci.check_sig1()
        self.assertEqual(findings, ["SIG-1 cannot run: no working protoc: x"])

    def test_absent_interfaces_module_is_a_named_finding_never_a_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(ci.check_sig1(Path(tmp)), ["SIG-1 SKIPPED: modules/interfaces is not checked out"])


if __name__ == "__main__":
    unittest.main()
