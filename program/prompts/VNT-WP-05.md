# VNT-WP-05 — C1: the runner — read-ahead, one run, the step loop (vantage branch `c1`), with `RCT:WP-08`

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`; `modules/vantage` is on branch **`c1`** — stay on
  it. Never commit, and never run `git checkout`, `git switch`, `git stash`, `git reset`,
  `git rm`, `git restore`, `pkill` or `kill`.
- **Owner conditions for `c1`:** every commit builds the whole of vantage and passes its full
  unit suite; a test of the old path that can no longer pass is removed in the same commit, naming
  the register row; the engine-running system tests listed in `c327be2`'s commit message may stay
  red (they turn green with `WP-10`), **every other test stays green**.
- `modules/vantage/docs/VANTAGE_Implementation_Design.md` — `WP-05`'s rows `IMP-0024`,
  `IMP-0026`..`IMP-0031`; the *Blocked* note (`WP-05` needs `RCT:WP-08`);
  `modules/interfaces/docs/resim_contract/RCT_Implementation_Design.md` rows `IMP-0032` (control
  writing) and `IMP-0033` (input selection), `RCT_System_Requirements.md` §2-§3 (the control and
  refSync rows they serve); `VANTAGE_Architecture.md` §3.2, §3.3, §3.4, §6, §7, §9, §10.1, §11
  (*Runner*, *Orchestrator: control writing*, *Runner: input selection*, the RCT row table);
  `D16`..`D18`
- What `c1` holds now: `RunSpec` 2.0 (`WP-01`); `SampleBuffer` (`FindByCounter`,
  `NewestCounterNotAfter`, `NewestSourceTimeNotAfter`, `NewestNotAfter`), `ReadSignalHeader`
  (0 = unknown), `IdentityTracker` (`content_differs`), `PortBus::DeclarePort` with an
  undeclared-port fallback marked for removal here (`WP-02`); `BuildGraph`, `Rank`, `PlanText`, not
  yet wired (`WP-03`); `EventQueue`, `Orchestrator` (`Jump` takes the runner's seek function;
  `readiness_expired`; `kForcedParked`), `Readiness`, in-memory `EventLog` with four runner-owned
  entry kinds not yet called (`WP-04`). The old `Scheduler` and cycle loop still drive the engine.
- Decisions carried from `WP-02`..`WP-04` (the ledger, 2026-11-01): declaration becomes mandatory
  on the engine path and source ports are declared; the time rule is composed from
  `NewestSourceTimeNotAfter` with the arrival-time fallback when either time is unknown (ARCH §6);
  the event log's file is decided here; the badges (`KIND_FALLBACK`, `KIND_READINESS_TIMEOUT`,
  `KIND_IDENTITY_BROKEN`, `KIND_COMPUTED_NOT_CONSUMED`, `KIND_WARMING_UP`) are raised here;
  the run_start boundary line stays out of the event log.
- `.claude/rules/*` as before; `program/VANTAGE_PROGRAM.md` §5

## Goal
`Runner::Construct` builds buffers, graph, orchestrator and read-ahead from the run setup alone
and prints the plan; `StepOnce` runs one engine step through the orchestrator, writing controls
(`RCT:IMP-0032`) and selecting inputs (`RCT:IMP-0033`); `simEngineSeek` jumps; the old
`Scheduler` and cycle loop are gone; `c1` builds and its unit suite passes.

## Step 0 — inventory first, then stop and report
1. The ~30 `Runner::Construct(…, Scheduler&, …)` call sites and the 5 remaining scheduler tests:
   updated / removed (register row) for each.
2. Where badges live before the live measurement exists (C2): how a test observes a step's badges
   (the step tap of the test spec, `F-TAP`, or the engine-run recording) — propose the smallest
   carrier; the live measurement writer is 8b's.
3. The event log's file in an engine run (beside `outputs.path`, in the checkpoint, or another
   place) — propose one, with the reason.
4. `IMP-0030` (`SetLiveMeasurement`): what it can do before the writer library exists (8b) —
   propose the smallest form (a sink interface the tests fill) or say it waits for 8b.
5. `simEngineSeek` and ABI version 3: every caller of the ABI (C++, Python `ctypes`, tests) and
   what changes.
6. What `simengine` does end to end on a lab case after this package, and which `tests/system`
   tests change state (the `c327be2` list stays red until `WP-10`).
Then stop: the orchestrator answers before you edit.

## After the go-ahead
1. Land `IMP-0024`, `IMP-0026`..`IMP-0031` and `RCT:IMP-0032`/`0033` as answered, with unit tests
   per new source and the runner's existing tests moved to the new loop.
2. Builds: the whole of vantage (`-t sil`, `-t gtest`, `-t package`, vs2026); the C++ and Python
   unit suites (counts before and after); one `tests/system` run; root `check_invariants.py`.
3. Boxes `[~]`, each "closed by <its `SYT` tests> passing (`WP-09`)"; the two RCT rows' boxes in
   `RCT_Implementation_Design.md` the same way (`[~]`, closed by their `SYT` tests on Vantage).

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed (both repos).
3. Exit check output: each command, pass/fail, seconds, counts before and after.
4. Boxes set.
5. Tests removed (with register rows) and updated (count, one example).
6. Deviations and open questions, each with your recommendation.
