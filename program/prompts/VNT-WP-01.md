# WP-01 — C1: the run setup loader and writer (vantage branch `c1`)

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`; `modules/vantage` is on branch **`c1`** — stay on
  it. Never commit, and never run `git checkout`, `git switch`, `git stash`, `git reset`, `pkill`
  or `kill`: if a step seems to need one, stop and report. Another worker edits
  `modules/vantage-lab` now; touch nothing there.
- **Owner conditions for `c1`** (2026-10-31): every commit on `c1` builds the whole of vantage
  and passes its full unit suite. A test of the old path that can no longer pass is removed in
  the same commit, naming the register row that retires or replaces its subject. The branch is
  never left broken between packages.
- `modules/vantage/docs/VANTAGE_Implementation_Design.md` — `WP-01`'s rows: `IMP-0001`..`0005`,
  `IMP-0049` and the setup writer row `8a-R2` adds; `VANTAGE_System_Requirements.md` (the rows
  they serve); `VANTAGE_Architecture.md` §2.3, §4, §11; `VANTAGE_Migration_Register.md` §3 (the
  code table: what is replaced, corrected, retired) and its rows for the old run setup keys
- `.claude/rules/build.md`, `testing.md`, `style.md`, `naming.md`, `architecture.md`;
  `program/VANTAGE_PROGRAM.md` §5 (a package that changes what vantage ships runs its real
  package build)

## Goal
`LoadRunSpec` reads schema `adas.sim.runspec/2.0` with the keys of 6a §2.3 and refuses the
retired, unknown and `⊘`-missing ones; `simengine` takes one setup and `--threads`/
`--wait-for-attach`; Vantage's Python setup writer writes only the new keys; all of vantage
builds and its full unit suite passes on `c1`.

## Step 0 — inventory first, then stop and report
Before editing anything, list:
1. every source file (C++ and Python) that reads or writes a key or field `WP-01` removes or
   renames (`grid_step_ns`, `order`, `delay_steps`, `sampling`, `on_missing`, `period_ns`), with
   what `WP-01` must do to it to keep the build green — the **smallest** change, adding no new
   behaviour to code a later C1 package replaces (`WP-03`..`WP-05`);
2. every test that uses one of them, split into (a) **updated** — still a valid test once the key
   is renamed or the setup rewritten in the new schema; (b) **removed** — tests a behaviour the
   register retires or replaces (name the register row for each); (c) **moved later** — tests
   behaviour a later C1 package rebuilds, which can stay green until then;
3. whether `simengine` still runs a lab case end to end after `WP-01` (yes / no, and why).
Report this inventory and **stop**. The orchestrator answers before you edit.

## After the go-ahead
4. Land the rows: `runspec.hpp` fields (`IMP-0001`), the refusals (`IMP-0002`, `0003`, `0049`),
   the schema constant (`IMP-0004`), `main`'s options (`IMP-0005`), the setup writer row. Unit
   tests for each in `tests/unit/` (file names in the existing style; name them in the report).
5. Apply the inventory as approved: updated tests updated; removed tests removed, each named with
   its register row in the report (the commit message carries the list).
6. Builds and suites: the whole of vantage (`-t sil`, `-t gtest`, `-t package`, vs2026, the
   standard build) and its full unit suite (C++ `simcore_tests` and the Python `tests/unit`, on
   Windows Python); `python scripts/check_invariants.py` at the root.
7. Boxes: a row's box goes `[~]` "closed by `SYT-…` passing (`WP-09`)" — its `SYT` tests are
   system tests built in `WP-09`; it goes `[x]` only then.

## Exit check (run all, report output and seconds)
- The three builds; the C++ and Python unit suites (counts before and after, seconds).
- `python3 .claude/templates/requirements/trace_check.py --set modules/vantage/docs` → PASS.
- `git -C modules/vantage branch --show-current` → `c1`; `git -C modules/vantage status --short`
  → only files the inventory named.

## Must not
- commit, push, or change files outside the inventory the orchestrator approves
- add behaviour to code a later C1 package replaces; skip or mark a test "expected fail" instead
  of updating or removing it

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes set (row ids and their `closed by`).
5. Tests removed, each with its register row; tests updated, as a count with one example.
6. Deviations and open questions, each with your recommendation.
