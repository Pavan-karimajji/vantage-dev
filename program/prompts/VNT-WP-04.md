# VNT-WP-04 — C1: events, steps, readiness, jump, the event log (vantage branch `c1`)

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`; `modules/vantage` is on branch **`c1`** — stay on
  it. Never commit, and never run `git checkout`, `git switch`, `git stash`, `git reset`,
  `git rm`, `git restore`, `pkill` or `kill`.
- **Owner conditions for `c1`:** every commit builds the whole of vantage and passes its full
  unit suite; a test of the old path that can no longer pass is removed in the same commit, naming
  the register row; the engine-running system tests listed in `c327be2`'s commit message may stay
  red, **every other test stays green**.
- `modules/vantage/docs/VANTAGE_Implementation_Design.md` — `WP-04`'s rows `IMP-0016`..`IMP-0025`
  and `IMP-0050`; the `SYS` rows they serve; `VANTAGE_Architecture.md` §3.2, §5, §6, §7, §8, §9,
  §11 (*Orchestrator: events and steps*, *readiness*); `D17`, `D18`;
  `VANTAGE_Migration_Register.md` §3 (`scheduler/`, `scheduler/reconcile.cpp`, `events.hpp`)
- What `c1` holds now: `RunSpec` 2.0 and its loader (`WP-01`); `SampleBuffer`, `ReadSignalHeader`
  (0 = unknown), `IdentityTracker`, `PortBus::DeclarePort` (`WP-02`); `BuildGraph`, `Rank`,
  `PlanText` and forward declarations of `EventQueue`, `Orchestrator`, `Readiness`, `EventLog` in
  `include/simcore/orchestrator.hpp` (`WP-03`). The old `Scheduler` (grid 0, setup order) still
  drives the runner's cycle loop, which `WP-05` replaces with `StepOnce`.
- `.claude/rules/*` as before; `program/VANTAGE_PROGRAM.md` §5

## Goal
The orchestrator's parts exist and are unit-tested: the event queue's order, a step's begin,
dispatch by rank with one open run per stage, commit, end and the recording's end, the jump,
readiness with its limit, the stalled trigger, and the event log with its closed entry kinds; the
old due-test scheduler leaves when nothing needs it; `c1` builds and its unit suite passes.

## Step 0 — inventory first, then stop and report
1. Every user of `Scheduler`, `IsDue`, `Advance`, `ReconcileModuleFlag` and `simcore::Event`
   (C++ and Python), with the smallest change `WP-04` makes to each.
2. **The gap between `WP-04` and `WP-05`:** the runner's cycle loop still runs on `Scheduler`. Say
   exactly how `c1` stays green if `IMP-0024`/`IMP-0025` delete it now, and offer the options you
   see — for example (a) the orchestrator built and unit-tested beside the old loop, and the
   scheduler's deletion moved into `WP-05` with the loop that uses it; (b) the runner switched to
   the orchestrator here. Recommend one; the orchestrator decides.
3. Every test that uses the parts that go, split into updated / removed (register row) / moved.
4. The event log's file and line format (`IMP-0023`): where it writes in an engine run, and which
   existing `event=` values and new `entry=` kinds it carries.
5. The stalled trigger (`IMP-0050`): where the payload bytes of the sample that last started a run
   are kept for the comparison.
Then stop: the orchestrator answers before you edit.

## After the go-ahead
1. Land the rows as answered, with unit tests per new source in `tests/unit/` (existing style):
   event order ties, ranks within a step, one open run per stage, readiness parking and expiry
   (limit 0 and above), the recording's end, a jump (step numbers continue, no old sample seen),
   a stalled trigger (same bytes at `counterDistance` 0) against identity broken (new bytes), every
   event-log entry kind; planted cases where a naive version would pass.
2. Builds: the whole of vantage (`-t sil`, `-t gtest`, `-t package`, vs2026); the C++ and Python
   unit suites (counts before and after); one `tests/system` run (the `c327be2` expected-red list
   may skip or fail as before; every other test passes); root `check_invariants.py`.
3. Boxes `[~]`, each "closed by <its `SYT` tests> passing (`WP-09`)".

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds, counts before and after.
4. Boxes set.
5. Tests removed (with register rows) and updated (count, one example).
6. Deviations and open questions, each with your recommendation.
