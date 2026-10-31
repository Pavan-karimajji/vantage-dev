# VNT-WP-02 — C1: sample buffers, the header at the door, identity checks (vantage branch `c1`)

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`; `modules/vantage` is on branch **`c1`** — stay on
  it. Never commit, and never run `git checkout`, `git switch`, `git stash`, `git reset`, `pkill`
  or `kill`. Another worker changes `modules/vantage`'s `conf/build.yml`, `pyproject.toml` and
  `requirements.lock` now (its environment); touch none of those.
- **Owner conditions for `c1`:** every commit builds the whole of vantage and passes its full
  unit suite; a test of the old path that can no longer pass is removed in the same commit, naming
  the register row; the engine-running system tests listed in `c327be2`'s commit message may stay
  red, **every other test stays green**.
- `modules/vantage/docs/VANTAGE_Implementation_Design.md` — `WP-02`'s rows `IMP-0006`..`IMP-0010`;
  the `SYS` rows they serve; `VANTAGE_Architecture.md` §3.4, §6, §11 (*Sample buffers*, *Header
  read at the door*, *Identity checks*); `VANTAGE_Migration_Register.md` §3 (`src/simcore/bus/`,
  `bus/cycle.cpp` replaced by `bus/identity.cpp`, `bus/header.cpp`); `D17 (3)`
- `modules/interfaces/include/adas/counter.hpp` (`counterDistance`, `RCT:SYS-0005`)
- `.claude/rules/*` as for `VNT-WP-01`; `program/VANTAGE_PROGRAM.md` §5

## Goal
Every sample entering a port's buffer has its header read once by reflection; each port keeps at
most `buffer_depth` samples and can be searched by counter and by time; per-port identity is
tracked with `counterDistance` only; the old cycle reconstructor is gone; `c1` builds and its
unit suite passes.

## Step 0 — inventory first, then stop and report
List: every file that uses `CycleReconstructor`, `PortBus` or the bus's current per-port storage,
with the smallest change `WP-02` makes to each (no new behaviour in code `WP-03`..`WP-05`
replace); every test that uses them, split into updated / removed (with its register row) /
unchanged; and where `IdentityTracker` and the counter event-log entries report before `WP-04`'s
event log exists (`IMP-0023`). Then stop: the orchestrator answers before you edit.

## After the go-ahead
1. Land `IMP-0006`..`IMP-0010` with unit tests in `tests/unit/` (one file per new source, named in
   the existing style), including `counterDistance` wrap cases and planted comparisons.
2. Builds: the whole of vantage (`-t sil`, `-t gtest`, `-t package`, vs2026, the standard build);
   the C++ and Python unit suites; one `tests/system` run, reporting the expected-red list and
   every other test passing; root `check_invariants.py`.
3. Boxes `[~]`, each "closed by <its `SYT` tests> passing (`WP-09`)".

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds, counts before and after.
4. Boxes set.
5. Tests removed (with register rows) and updated (count, one example).
6. Deviations and open questions, each with your recommendation.
