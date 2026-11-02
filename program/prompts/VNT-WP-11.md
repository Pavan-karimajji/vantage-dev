Your role: read .claude/agents/vantage-builder.md and follow it.
Keep the report under 40 lines, in the §4.2 shape.

# VNT-WP-11 — C1: the `measurement_counter` wrap in the engine (vantage branch `c1`, `D24`)

## Context (read these, nothing else unless a step needs it)
- Working copy `C:\ws\repo\vantage-dev`, native Windows (`vs2026`). `modules/vantage` is on
  branch **`c1`** — stay on it. Never run `git checkout`, `git switch`, `git stash`, `git reset`,
  `git rm`, `git restore`, `git add`, `git commit`, `git push`, `pkill` or `kill`.
- **Owner conditions for `c1`:** every commit builds the whole of vantage and passes its full unit
  suite.
- `VANTAGE_DEV_PLAN.md` §2 `D24` (1)–(3).
- `modules/vantage/docs/VANTAGE_Implementation_Design.md`: package `WP-11`, rows `IMP-0053` to
  `IMP-0056` (**build exactly these**); `VANTAGE_System_Requirements.md` `SYS-0049`, `SYS-0050`,
  `SYS-0051`, `SYS-0031`; `VANTAGE_Test_Spec.md` `SYT-SEL-12`, `SYT-SEL-13`, `SYT-ORC-12`, fixture
  `F-TICK`; `VANTAGE_Architecture.md` §3.4 (identity check) and §6 step 3 (counter fallback).
- Code: `include/simcore/bus.hpp`, `src/simcore/bus/identity.cpp`,
  `src/simcore/runner/select_inputs.cpp`, `src/simcore/orchestrator/control.cpp`; tests
  `tests/unit/test_ut_bus_identity.cpp`, `tests/unit/test_run_select_inputs.cpp`,
  `tests/unit/test_orc_control.cpp`, `tests/CMakeLists.txt`.
- Rules: `.claude/rules/style.md` (file header on the new file, minimal diffs), `naming.md`,
  `architecture.md`, `testing.md`. Counters are compared only through `counterDistance`
  (`SYS-0031`): no `==`, `<`, `>` … on a counter value, only on a distance.
- Python: only in vantage's own environment, `modules\vantage\.venv-sim-win32\Scripts\python.exe`.
  Never `py -3`.

## Goal
One function, `simcore::bus::MeasurementCounterDistance`, is Vantage's distance on
`measurement_counter` and counts `0xFFFFFFFF` → 1 as one step; the identity check and the counter
fallback's gap both use it, `counterDistance` is untouched; a clock-started stage's controls run
1 … `0xFFFFFFFF`, 1; `tests/support/control_tick` exists. `c1` builds and its suites pass.

## Allowed changes
- `modules/vantage`: the four source files above, the three unit-test files above,
  `tests/support/control_tick.cpp` (new), `tests/CMakeLists.txt`.
- `modules/vantage/docs/VANTAGE_Implementation_Design.md`: the boxes of `IMP-0053`..`IMP-0056`
  and `WP-11` only.
- Generated, untracked: build folders.

## Steps
1. `IMP-0053`: declare `MeasurementCounterDistance(std::uint32_t from, std::uint32_t to)` in
   `bus.hpp` (beside the identity types), define it in `identity.cpp` by the row's formula, and
   take `Observe`'s `measurement_distance` from it. Unit tests: `0xFFFFFFFF`→1 is 1, 1→`0xFFFFFFFF`
   is −1, `0xFFFFFFFE`→2 is 3, `0xFFFFFFFE`→`0xFFFFFFFF` is 1, 5→9 is 4, equal is 0; `Observe` over
   … `0xFFFFFFFE`, `0xFFFFFFFF`, 1, 2 gives no gap, reset or broken, and `0xFFFFFFFF` → 2 is a gap
   with one missed.
2. `IMP-0056`: `SelectInputs`'s counter fallback takes its gap from it. Unit test: samples
   `0xFFFFFFFE` and 3 held, wanted 2 → found `0xFFFFFFFE`, gap 3; within at `fallback_max_gap` 3,
   beyond at 2.
3. `IMP-0054`: `ControlWriter::HeaderOf`'s clock counter is (k mod `0xFFFFFFFF`) + 1. Unit test:
   ticks 0, 1, `0xFFFFFFFE`, `0xFFFFFFFF`, `0x100000000` → 1, 2, `0xFFFFFFFF`, 1, 2.
4. `IMP-0055`: `tests/support/control_tick.cpp` as the row says, registered in
   `tests/CMakeLists.txt`. Run it with a 1 ms period for the five ticks of step 3; report each line.
5. Planted: with each of steps 1–3 in turn put back to `counterDistance` / `k + 1`, the new tests
   fail — plant, run, restore, say so for each.
6. Builds and suites: `build.bat -t sil -p vs2026`, `-t gtest` (C++ suite, last 388/388),
   `-t package` in `modules\vantage`; Python `tests/unit tests/system` in its own environment
   (last 1113 passed, 87 skipped); `py -3.12 scripts\check_invariants.py` at the root;
   `trace_check --set modules/vantage/docs --status`.
7. Boxes: each of `IMP-0053`..`IMP-0056` `[~]` once its code and unit test pass (each row already
   names what closes it, in `WP-09`); `WP-11` as the rollup gives.

## Exit check (run all, report output and seconds)
- Each build command: pass/fail, seconds. C++ and Python counts before and after.
- The five `control_tick` lines.
- `check_invariants.py` clean (findings verbatim); `trace_check` PASS, the `WP-11` line.
- `git -C modules/vantage status --short`; `git diff --stat` equal with and without
  `--ignore-cr-at-eol`.
- `git -C modules/vantage diff -- src include` in full (it is small).

## Must not
- change `counterDistance`, anything under `modules/interfaces`, or how `cycle_counter` is read
- change any other counter comparison (`sample_buffer.cpp`, `read_ahead.cpp`, `orchestrator.cpp`,
  `run_stage.cpp` stay as they are)
- write the `SYT` tests (`WP-09` writes them) or tick a row `[x]`
- decide anything the rows leave open — report it with your recommendation

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds (R-TEST-7).
4. Boxes ticked (row ids), and any `[~]` with what closes it.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
