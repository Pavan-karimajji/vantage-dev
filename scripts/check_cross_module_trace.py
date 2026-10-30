#!/usr/bin/env python3
# Copyright (c) LT EPS. All Rights Reserved.
# Proprietary and Confidential.
# @author Pavan Karimajji

"""Cross-module trace link checker -- `VZ-21`, specified by
`modules/viz/docs/VIZ_Sync_Plan_v0.1.md` §6.3.

    python scripts/check_cross_module_trace.py            # full check
    python scripts/check_cross_module_trace.py --defined  # every UID, per module
    python scripts/check_cross_module_trace.py --refs     # every qualified reference

**The gap this closes.** Each module's own `trace_check.py` closes
`CN -> SYS -> SW -> IMP -> WP -> test` *inside that module*, and all three are
green. None of them can see a link that leaves its repository. When 56 `SW`
requirements move from sim to viz (`SM-04`, `SM-05`), their `SYS` parents are
dispositioned separately -- and the moment a `SIM:SYS` row is edited, the
`VIZ:SW` rows tracing to it drift **while both repos' own checkers stay green**.
That is exactly `R-REQ-11`'s stated failure mode -- *"the two halves drift while
each document passes inspection on its own"* -- with a repo boundary making it
invisible rather than merely easy to miss.

**Why this lives at the superproject root and not in a module.** `R-BUILD-4`:
root `scripts/` is cross-component only. A cross-module check living inside one
module is that module's opinion about the other two. It is also written with
**no dependency on the sync plan's checkboxes**, which is what lets it outlive
that document -- §6.6 deletes the sync plan when the migration completes, and
the links it checks are permanent.

**Scope, and why it is not wider.** The check runs over modules that HAVE a
V-model document set -- three of thirteen. The other ten are reported
`NO-DOCUMENT-SET`, as information, never as findings. Checking ten modules that
cannot participate produces noise, and noise trains people to stop reading the
output, which costs more than the coverage buys.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# A module participates when it has a V-model document set. The prefix is its
# COMPONENT: token (R-NAME-6), and the sync plan's §6.3 fixes the vocabulary.
DOC_SETS: dict[str, Path] = {
    "SIM": ROOT / "modules/sim/docs/v2",
    "DF": ROOT / "modules/df/docs/viz",
    "VIZ": ROOT / "modules/viz/docs",
}

# Every module in .gitmodules, so the report can say "no document set" rather
# than silently covering three and implying it covered thirteen.
ALL_MODULES = (
    "interfaces", "isp", "perception-core", "perception-lane", "planning",
    "vdy", "df", "platform-services", "sil_host", "shared_config", "mathlib",
    "sim", "viz",
)

# Documents that cite UIDs but define none of their own.
EXTRA_SOURCES = [ROOT / "modules/viz/docs/VIZ_Sync_Plan_v0.1.md"]

LAYERS = ("CN", "SYS", "SW", "IMP")
UID = r"(?:CN|SYS|SW|IMP)-\d{4}"

# Three definition shapes, because the document sets genuinely use three and a
# checker that knew fewer would report a real UID as BROKEN. First two found by
# this check's own first run, 2026-08-18; the third found 2026-08-30 triaging
# 56 "SIM:SW-*"/"SIM:SYS-*" BROKEN findings that were all real, defined UIDs.
#
#   df   `**`CN-0033`** · `P0` · `R1` — headline`      prose-anchored
#   sim  `| 4.1.14 | CN-0287 | headline | … |`         table-anchored
#   sim  `| `SYS-0132` | The player knows no module | `VIZ:SYS-0061` … |`
#                                                       backtick-table-anchored
#
# The third shape is sim's R-REQ-2 disposition tables (`| \`UID\` | Was |
# Replaced by |`) and its Implementation Design tracker (`| \`IMP-nnnn\` |
# \`SW-nnnn\` | \`WP-nn\` | … |`) -- both put the UID in the row's own first
# column, backtick-wrapped, unlike either shape above. Every one of the 56
# findings was a `SM-01`/`SM-04` disposition entry: real, defined, retired
# UIDs the checker simply could not see -- not a dangling link.
#
# Normalising the documents to one shape would be the tidier fix and is not
# this tool's call to make -- it would edit two baselined sets to suit a
# checker, which is the wrong direction.
DEFINE_PROSE_RE = re.compile(rf"^\*\*`({UID})`\*\*")
DEFINE_TABLE_RE = re.compile(rf"^\|\s*[\d.]+\s*\|\s*({UID})\s*\|")
DEFINE_BACKTICK_TABLE_RE = re.compile(rf"^\|\s*`({UID})`\s*\|")
# A retired range recorded per R-REQ-2 (`| CN-0054 … CN-0062 | superseded by … |`).
# These still resolve: a dangling trace link must land on an explanation rather
# than on nothing, which is the whole point of a disposition entry.
DEFINE_RANGE_RE = re.compile(rf"^\|\s*({UID})\s*(?:…|\.\.\.|\.\.)\s*({UID})\s*\|")

QUALIFIED_RE = re.compile(r"\b(SIM|DF|VIZ|RECIO):((?:CN|SYS|SW|IMP)-[0-9n]{4})\b")

# `VIZ:SW-nnnn` is a deliberate placeholder: §7 says the viz set is authored by
# VZ-20 and its UIDs are allocated then. Resolving it now would be inventing a
# number, which R-REQ-2 forbids more strongly than it forbids a placeholder.
PLACEHOLDER = "nnnn"


def defined_uids() -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for mod, d in DOC_SETS.items():
        if not d.exists():
            continue
        found: set[str] = set()
        for f in sorted(d.glob("*.md")):
            for line in f.read_text(encoding="utf-8", errors="ignore").split("\n"):
                for rx in (DEFINE_PROSE_RE, DEFINE_TABLE_RE, DEFINE_BACKTICK_TABLE_RE):
                    m = rx.match(line)
                    if m:
                        found.add(m.group(1))
                        break
                mr = DEFINE_RANGE_RE.match(line)
                if mr:
                    lo, hi = mr.group(1), mr.group(2)
                    layer = lo.rsplit("-", 1)[0]
                    if hi.rsplit("-", 1)[0] == layer:
                        a, b = int(lo.rsplit("-", 1)[1]), int(hi.rsplit("-", 1)[1])
                        if 0 <= b - a <= 200:  # a range, not a coincidence
                            found.update(f"{layer}-{n:04d}" for n in range(a, b + 1))
        if found:
            out[mod] = found
    return out


def qualified_refs() -> dict[tuple[str, str], list[str]]:
    """(module, uid) -> the files citing it."""
    refs: dict[tuple[str, str], list[str]] = defaultdict(list)
    sources: list[Path] = list(EXTRA_SOURCES)
    for d in DOC_SETS.values():
        if d.exists():
            sources += sorted(d.glob("*.md"))
    for f in sources:
        if not f.exists():
            continue
        for mod, uid in QUALIFIED_RE.findall(f.read_text(encoding="utf-8",
                                                         errors="ignore")):
            refs[(mod, uid)].append(str(f.relative_to(ROOT)))
    return refs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--defined", action="store_true")
    ap.add_argument("--refs", action="store_true")
    args = ap.parse_args()

    defined = defined_uids()
    refs = qualified_refs()

    if args.defined:
        for mod in sorted(DOC_SETS):
            uids = defined.get(mod, set())
            print(f"{mod:<6} {len(uids):>4} UIDs"
                  f"{'' if uids else '   (no document set yet)'}")
            for layer in LAYERS:
                n = sum(1 for u in uids if u.startswith(layer + "-"))
                if n:
                    print(f"         {layer:<4} {n}")
        return 0

    if args.refs:
        for (mod, uid), files in sorted(refs.items()):
            print(f"  {mod}:{uid}  <- {', '.join(sorted(set(files)))}")
        return 0

    findings: list[str] = []
    info: list[str] = []
    checked = placeholders = 0

    for (mod, uid), files in sorted(refs.items()):
        if uid.endswith(PLACEHOLDER):
            placeholders += 1
            continue
        if mod not in DOC_SETS or mod not in defined:
            info.append(f"NO-DOCUMENT-SET  {mod}:{uid} cited by "
                        f"{', '.join(sorted(set(files)))} -- {mod} has no "
                        f"V-model set yet, so the link cannot be checked")
            continue
        checked += 1
        if uid not in defined[mod]:
            findings.append(f"BROKEN           {mod}:{uid} cited by "
                            f"{', '.join(sorted(set(files)))} -- no such UID in "
                            f"{DOC_SETS[mod].relative_to(ROOT)}")

    for m in ALL_MODULES:
        tok = {"sim": "SIM", "df": "DF", "viz": "VIZ"}.get(m)
        if tok is None or tok not in defined:
            info.append(f"NO-DOCUMENT-SET  module {m!r} has no V-model document "
                        f"set -- not a finding")

    total_defined = sum(len(v) for v in defined.values())
    print(f"  scanned: {len(defined)}/{len(ALL_MODULES)} modules with a document "
          f"set, {total_defined} UIDs defined, {len(refs)} qualified references "
          f"({checked} checkable, {placeholders} placeholders)")

    # Scan honesty (sim's risk R-9): nothing scanned is SKIPPED and non-zero,
    # never PASS. A cross-module checker that found no documents would otherwise
    # report success on a broken checkout.
    if not defined:
        print("check_cross_module_trace: SKIPPED -- no document set found. "
              "A check that scanned nothing has not passed.", file=sys.stderr)
        return 2

    if findings:
        print(f"\ncheck_cross_module_trace: FAIL -- {len(findings)} finding(s):",
              file=sys.stderr)
        for f in findings:
            print(f"  {f}", file=sys.stderr)
        return 1

    shown = [i for i in info if not i.endswith("not a finding")]
    if shown:
        print(f"\n  information ({len(shown)}):")
        for i in shown[:10]:
            print(f"    {i}")
    print("  PASS -- every checkable cross-module reference resolves.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
