Your role: read .claude/agents/vantage-builder.md and follow it.
Keep the report under 40 lines, in the §4.2 shape.

# VNT-WP-06-08 — C1: equal outputs and the first divergence (`WP-06`), then the source checks (`WP-08`) (vantage branch `c1`)

Two packages in one session, owner's request. Do part A completely, then part B. Each part has its
own boxes. If part A is stopped by something you cannot resolve, report it and still do part B,
because B does not depend on A.

## Context (read these, nothing else unless a step needs it)
- Working copy `C:\ws\repo\vantage-dev`, native Windows (`vs2026`). `modules/vantage` is on
  branch **`c1`** — stay on it. Never run `git checkout`, `git switch`, `git stash`, `git reset`,
  `git rm`, `git restore`, `git add`, `git commit`, `git push`, `pkill` or `kill`.
- **Owner conditions for `c1`:** every commit builds the whole of vantage and passes its full unit
  suite; a test of the old path that can no longer pass is removed in the same change, and you
  name it.
- `modules/vantage/docs/VANTAGE_Implementation_Design.md`: packages `WP-06` and `WP-08`; rows
  `IMP-0032`, `IMP-0033` (A), `IMP-0006`'s note on `NewestSourceTimeNotAfter` (A), `IMP-0037`,
  `IMP-0038`, `IMP-0039` (B). **Build exactly these rows.**
- `VANTAGE_System_Requirements.md`: `SYS-0036`, `SYS-0043`, `SYS-0044`, `SYS-0045` (A);
  `SYS-0017`, `SYS-0031`, `SYS-0038` (B). `VANTAGE_Test_Spec.md`: `SYT-STP-05`, `SYT-EQO-02`..`04`
  (A, written in `WP-09` — not here); `ANL-01`, `ANL-02`, `ANL-03` (B — the checks themselves).
- `VANTAGE_Architecture.md` §7 *Where equal outputs apply* (and the `KIND_WARMING_UP` row of the
  badge table), §11 (code layout row "Runner: equal outputs").
- Code: `src/simcore/runner/divergence.cpp`, `include/simcore/runner.hpp` (`DivergenceLatch`),
  `src/simcore/runner/cycle_loop.cpp` (where the latch observes and where `KIND_WARMING_UP` is
  raised and cleared), `src/simcore/bus/sample_buffer.cpp`, `include/simcore/bus.hpp`;
  `scripts/check_time_units.py` and `tests/unit/test_a1_check_time_units.py` (the pattern for B).
- Rules: `.claude/rules/style.md` (file header on every new file, minimal diffs), `naming.md`,
  `architecture.md`, `testing.md`, `requirements.md` R-REQ-9 (every `A` check ships a planted
  case; the test id appears verbatim in the check that implements it).
- Python: only in vantage's own environment, `modules\vantage\.venv-sim-win32\Scripts\python.exe`.
  Never `py -3`. Root scripts: `py -3.12`.

## Part A — `WP-06`: equal outputs and the first divergence
**Goal.** `EqualOutputs` decides whether a simulated output equals the recorded one as `ARCH §7`
says; `DivergenceLatch` is keyed by step, skips RESTART runs, latches and logs the first unequal
step, stage and port once, and never changes the outcome; warming up ends at a stage's first
equal output; `NewestSourceTimeNotAfter` is gone.

1. `IMP-0032`: `divergence.cpp::EqualOutputs` — both headers' `cycle_counter` zeroed before
   comparing; a `refSync` payload compared only on each entry's `measurement_counter` and
   `source_timestamp_us`; every other byte compared exactly. Use the payload's descriptor the way
   the bus already reads headers; no other payload field is interpreted.
2. `IMP-0033`: `DivergenceLatch::Observe` takes the step (not a tick index), is not called for a
   RESTART run, compares through `EqualOutputs`, latches the first difference and writes one
   `first_divergence` event log entry (step, stage, port). The engine run's outcome and exit code do
   not depend on it. Keep the names of fields that Python reads from the outcome
   (`src/adas_sim/io/base.py`, `orchestrate/batch.py`) unless a row says otherwise; if one must
   change, change its readers in the same change and say so.
3. Warming up: `KIND_WARMING_UP` on a stage ends at the first step whose outputs are equal by
   `EqualOutputs` (`IMP-0032`'s last clause), not by byte equality.
4. Remove `SampleBuffer::NewestSourceTimeNotAfter` (declaration, definition) and its unit tests in
   `tests/unit/test_ut_bus_sample_buffer.cpp` and `test_ut_bus_signal_header.cpp`; first show
   (grep) nothing else calls it. Edit `IMP-0006`'s text: replace
   "`NewestSourceTimeNotAfter` exists until `WP-06` removes it, the per-sample time rule having
   replaced it" with "`NewestSourceTimeNotAfter` is removed (`WP-06`), the per-sample time rule
   having replaced it". Its box stays `[~]`.
5. Unit tests (gtest, beside the existing divergence tests in `tests/unit/test_ut_run_core.cpp`
   or a new `tests/unit/test_run_divergence.cpp`, your choice, name it): two outputs differing
   only in `cycle_counter` are equal; a `refSync` differing only in a header field other than
   counter and time is equal, and differing in one entry's `source_timestamp_us` is not; a
   RESTART run is never observed; the latch keeps the first difference and logs once; a stage's
   warming up ends at its first equal output. Plant: make `EqualOutputs` plain byte equality and
   show which tests fail; restore; say so.

## Part B — `WP-08`: the source checks
**Goal.** `ANL-01`, `ANL-02`, `ANL-03` run as scripts over the tree, each with a `--selftest` that
plants exactly the violations the test spec names and proves each is reported with file and line.

6. `IMP-0037`: `scripts/check_engine_decisions.py [--root <dir>] [--selftest]` as the row says;
   `--selftest` plants `ANL-01` `.c2` (a `std::chrono::steady_clock::now()` in
   `src/simcore/orchestrator/orchestrator.cpp`) and `.c3` (a `ParseFromArray` in
   `src/simcore/runner/select_inputs.cpp`) in a temporary copy.
7. `IMP-0038`: `scripts/check_counter_compare.py [--root <dir>] [--selftest]` as the row says.
   An operand that is the result of `counterDistance(…)` or `MeasurementCounterDistance(…)` is a
   distance, not a counter — comparing it is allowed. `--selftest` plants `ANL-02` `.c2` (`<` in
   `src/simcore/bus/sample_buffer.cpp`) and `.c3` (`==` in
   `src/simcore/orchestrator/orchestrator.cpp`).
8. `IMP-0039`: confirm `check_time_units.py`'s roots hold `src/simcore/orchestrator/`; run it and
   its planted test (`ANL-03` `.c2` plants `double step_time = 0;` in
   `src/simcore/orchestrator/event_queue.cpp`). No change unless the row is untrue — then report.
9. A unit test per new script in `tests/unit/` following `test_a1_check_time_units.py`: the clean
   run and each planted case, citing `ANL-01` / `ANL-02` and their case ids verbatim.
10. Run both new scripts over the real tree. **A real finding is not yours to clear:** report each
   with file, line and your recommendation; do not change engine code for it and do not add an
   exemption no row names.

## Builds, suites, boxes (once, at the end)
11. `build.bat -t sil -p vs2026`, `-t gtest` (C++ suite, last 393/393), `-t package` in
   `modules\vantage`; Python `tests/unit tests/system` in its own environment (last 1113 passed,
   87 skipped); `py -3.12 scripts\check_invariants.py` at the root;
   `py -3.12 .claude/templates/requirements/trace_check.py --set modules/vantage/docs --status`.
12. Boxes. Part A: `IMP-0032`, `IMP-0033` `[~]` once code and unit tests pass, each row gaining
   at its end, before the test column, "Closed by `<its test column's ids>` passing (`WP-09`)." —
   the form the `WP-05` rows use. Part B: `IMP-0037`, `IMP-0038`, `IMP-0039` `[x]` when the
   script's run over the tree is clean and its planted cases are caught; `[~]` with "closed by
   <the finding being resolved>" when a real finding remains. Package boxes as the rollup gives
   (`C-WPROLL` must be clean).

## Exit check (run all, report output and seconds)
- Each build command: pass/fail, seconds; C++ and Python counts before and after, and each test
  removed by name.
- Each new script: the clean run's output and exit code; `--selftest` output.
- `check_invariants.py` clean (findings verbatim); `trace_check` PASS, the `WP-06`, `WP-08` lines.
- `git -C modules/vantage status --short`; `git diff --stat` equal with and without
  `--ignore-cr-at-eol`.

## Must not
- write the `SYT-*` tests (`WP-09`), touch threads (`WP-07`), or change `counterDistance`,
  `MeasurementCounterDistance` or anything under `modules/interfaces`
- wire the new scripts into `ci_gate.py` or `check_invariants.py` (no row says so — recommend it
  if you think it should)
- decide anything the rows leave open — report it with your recommendation

## Report back in this shape
1. Done / not done, in one line per part.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds (R-TEST-7).
4. Boxes ticked (row ids), and any `[~]` with what closes it.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
