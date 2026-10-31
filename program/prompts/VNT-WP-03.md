# VNT-WP-03 — C1: graph, ranks and the plan (vantage branch `c1`)

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`; `modules/vantage` is on branch **`c1`** — stay on
  it. Never commit, and never run `git checkout`, `git switch`, `git stash`, `git reset`,
  `git rm`, `git restore`, `pkill` or `kill`.
- **Owner conditions for `c1`:** every commit builds the whole of vantage and passes its full
  unit suite; a test of the old path that can no longer pass is removed in the same commit, naming
  the register row; the engine-running system tests listed in `c327be2`'s commit message may stay
  red, **every other test stays green**.
- `modules/vantage/docs/VANTAGE_Implementation_Design.md` — `WP-03`'s rows `IMP-0011`..`IMP-0015`;
  the `SYS` rows they serve; `VANTAGE_Architecture.md` §2.2 (ranks), §3.2, §5 (the six rules),
  §11 (*Orchestrator: graph*, *schedule plan*); `VANTAGE_Migration_Register.md` §3
  (`include/simcore/scheduler.hpp` and `src/simcore/scheduler/` replaced, `scheduler/dump.cpp`
  replaced by `orchestrator/plan_dump.cpp`)
- What `WP-01` and `WP-02` left on `c1`: the old `Scheduler` still drives the runner with grid 0
  and the setup's order (it goes in `WP-04`/`WP-05`); `SampleBuffer`, `ReadSignalHeader`,
  `IdentityTracker` and `PortBus::DeclarePort` exist.
- `.claude/rules/*` as for `VNT-WP-01`; `program/VANTAGE_PROGRAM.md` §5

## Goal
`BuildGraph` and `Rank` make the graph from the run setup and refuse a loop without a
previous-cycle input and a stage without exactly one start; the plan prints from the setup and
the graph alone; `include/simcore/orchestrator.hpp` declares the orchestrator's parts; the old
schedule dump is gone; `c1` builds and its unit suite passes.

## Step 0 — inventory first, then stop and report
List: every user of `PredictSchedule`, `ScheduleDumpText` and the plan or schedule dump (C++,
Python, scripts, `simengine` options), with the smallest change `WP-03` makes to each; every test
that uses them, split into updated / removed (with its register row) / unchanged; how
`IMP-0013`'s "`<stage>.control` in the recording's topic index" is known at load (who opens the
index, before which step); and which parts `orchestrator.hpp` declares now as declarations only
(`EventQueue`, `Orchestrator`, `Readiness`, `EventLog` are built in `WP-04`). Then stop: the
orchestrator answers before you edit.

## After the go-ahead
1. Land `IMP-0011`..`IMP-0015` with unit tests in `tests/unit/` (one file per new source, existing
   style), including a planted loop, each way a stage can have no start or two, and ranks of the
   lab's `fan_out`, `diamond`, `feedback` shapes built in the test.
2. Builds: the whole of vantage (`-t sil`, `-t gtest`, `-t package`, vs2026, the standard build);
   the C++ and Python unit suites (counts before and after); one `tests/system` run (the
   `c327be2` expected-red list may skip or fail as before; every other test passes); root
   `check_invariants.py`.
3. Boxes `[~]`, each "closed by <its `SYT` tests> passing (`WP-09`)".

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds, counts before and after.
4. Boxes set.
5. Tests removed (with register rows) and updated (count, one example).
6. Deviations and open questions, each with your recommendation.
