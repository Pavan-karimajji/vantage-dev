#!/usr/bin/env python3
# Copyright (c) LT EPS. All Rights Reserved.
# Proprietary and Confidential.
# @author Pavan Karimajji

"""What does this repo want me to do next -- minus the cross-repo gate table.

    python scripts/next.py

**What this used to be.** `VZ-21`, specified by `modules/viz/docs/
VIZ_Sync_Plan_v0.1.md` §6.4: a cross-repo work-order dispatcher reading that
plan's own §2 (43 rows) and §3 (8 phase gates) to answer "what does the
migration need from this module next", joined to each module's own plan by a
greppable `SYNC:<row>` back-reference.

**Why that is gone.** The migration it dispatched closed 2026-08-29 (`B1`,
`modules/sim/misc/MOVEMENT_B_PLAN.md`), and the sync plan retired its own §2
and §3 per its own §6.6 -- there is no gate table left to read, and there
never will be again for this migration. This script used to hard-import
`modules/viz/docs/py/sync_check.py` to parse that table; with the table gone
the import had nothing left to serve, and `sync_check.py` itself is deleted
alongside this rewrite (see that file's own former docstring for the history).

**What survives, per the sync plan's own §6.6** ("`next.py` minus its gate
table, because 'what does this repo want me to do next' outlives this
particular migration"): each of the three modules with a V-model document set
already answers its own version of that question, from its own Implementation
Plan, via its own `trace_check.py --status`. This script just runs all three
side by side, so answering it for all of them is still one command rather
than three.

**Root `scripts/` is still the right home** (`R-BUILD-4`): running one command
across three modules is not any one module's opinion about the other two,
even once that command stops being a dispatcher.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Work orders quote requirement-doc prose verbatim, which uses non-ASCII glyphs
# (arrows, bullets) freely -- a Windows console's default cp1252 stdout can't
# encode those and raises on print(), so this is reconfigured unconditionally
# rather than only where a glyph happens to appear.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

# name -> (that module's trace_check.py, the cwd to run it from, its own
# Implementation Plan -- the df/viz fallback below reads this directly)
MODULES = {
    "sim": (ROOT / "modules/sim/docs/v2/py/trace_check.py", ROOT / "modules/sim",
            ROOT / "modules/sim/docs/v2/SIM_Implementation_Plan_v0.1.md"),
    "df": (ROOT / "modules/df/docs/viz/py/trace_check.py", ROOT / "modules/df",
           ROOT / "modules/df/docs/viz/df_viz_Implementation_Plan_v0.1.md"),
    "viz": (ROOT / "modules/viz/docs/py/trace_check.py", ROOT / "modules/viz",
            ROOT / "modules/viz/docs/VIZ_Implementation_Plan_v0.1.md"),
}


def module_status(script: Path, cwd: Path, plan: Path) -> tuple[bool, str]:
    """Pass/fail from the module's own ordinary trace_check.py run (does its
    document set close CN -> SYS -> SW -> IMP -> WP -> test?), plus what it
    says is next: `--status`'s own resume pointer where the module's tool
    supports it (sim only), else the plan's own idiom -- the lowest-numbered
    unticked box (df, viz). A missing script is SKIPPED, not PASSED, per
    sim's own risk R-9."""
    if not script.exists():
        return False, f"SKIPPED  {script.relative_to(ROOT)} does not exist yet"
    r = subprocess.run([sys.executable, str(script)], cwd=cwd,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    if r.returncode != 0:
        detail = (r.stderr or r.stdout).strip().split("\n")
        return False, "FAIL\n" + "\n".join(f"    {ln}" for ln in detail[:12])

    rs = subprocess.run([sys.executable, str(script), "--status"], cwd=cwd,
                        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    out = rs.stdout or ""
    m = re.search(r"next untouched package\s+(\S+)", out)
    if not m:
        m = re.search(r"finish these first.*?\n\s+(\S+)", out, re.DOTALL)
    if m:
        return True, f"PASS -- next: {m.group(1)}"
    nxt = "? (plan not found)"
    if plan.exists():
        nxt = "none -- every box ticked"
        for line in plan.read_text(encoding="utf-8").split("\n"):
            if line.startswith("- [ ]"):
                nxt = line[5:].strip()[:60]
                break
    return True, f"PASS -- next: {nxt}"


def main() -> int:
    red = False
    for name, (script, cwd, plan) in MODULES.items():
        ok, detail = module_status(script, cwd, plan)
        red = red or not ok
        print(f"  {name:<5} {detail}")
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
