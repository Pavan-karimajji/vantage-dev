Your role: read .claude/agents/vantage-builder.md and follow it.
Keep the report under 40 lines, in the §4.2 shape.

# VNT-WP-07 — C1: threads (vantage branch `c1`)

## Context (read these, nothing else unless a step needs it)
- Working copy `C:\ws\repo\vantage-dev`, native Windows (`vs2026`). `modules/vantage` is on
  branch **`c1`** — stay on it. Never run `git checkout`, `git switch`, `git stash`, `git reset`,
  `git rm`, `git restore`, `git add`, `git commit`, `git push`, `pkill` or `kill`.
- **Owner conditions for `c1`:** every commit builds the whole of vantage and passes its full unit
  suite; a test of the old path that can no longer pass is removed in the same change, and you
  name it.
- `modules/vantage/docs/VANTAGE_Implementation_Design.md`: package `WP-07`, rows `IMP-0034`,
  `IMP-0035`, `IMP-0036` — **build exactly these**. `VANTAGE_System_Requirements.md` `SYS-0039`,
  `SYS-0040`, `SYS-0041`; `VANTAGE_Test_Spec.md` `SYT-THR-01`..`03` (written in `WP-09`, not here).
- **`VANTAGE_Architecture.md` §8 is the design** — what may run side by side, the five facts that
  make N threads equal to one, what is never shared. Read it whole before writing code.
- Code: `include/simcore/runner.hpp` (`RunnerOptions`), `src/simcore/runner/cycle_loop.cpp`
  (`Runner::StepOnce`, `Runner::RunTicket`), `src/simcore/runner/run_stage.cpp`,
  `src/simengine/main.cpp` (`--threads` is parsed already and "takes effect in `WP-07`"), and
  however `simEngineCreate` passes options to the runner.
- Rules: `.claude/rules/style.md` (file header on any new file, minimal diffs), `naming.md`,
  `architecture.md` (R-ARCH-2: threads live in the engine, never in `src/component/**`),
  `testing.md`.
- Python: only in vantage's own environment, `modules\vantage\.venv-sim-win32\Scripts\python.exe`.
  Never `py -3`. Root scripts: `py -3.12`.
- Lab outputs built on this machine: `modules/vantage-lab/lab/<topology>/` (recordings, run
  setups, libraries; `index.json`).

## Goal
`--threads N` (default 1, never from the run setup) runs the tickets of one rank that have no
wiring between them on worker threads that only call `Component::Exec` on inputs fixed before
dispatch; a barrier ends each rank; results commit in stage declaration order; two stages from
one library path never run at once. One thread and N threads give byte-identical engine runs.

## Steps
1. `IMP-0034`: `RunnerOptions::threads`, default 1; set only from `--threads` (simengine and the
   C-API create path); the run setup never sets it (grep the loader to show it).
2. `IMP-0035`: in `StepOnce`, per rank: select every runnable ticket's inputs on the orchestrator
   thread (as now), then dispatch the ones with no wiring between them to workers, each calling
   only `Component::Exec` on its copied inputs into its own output buffers; barrier; then commit,
   the divergence latch, overrides, badges, the event log and the writer, all on the orchestrator
   thread, in stage declaration order. `threads == 1` takes the same code path with no worker
   (not a second loop — `ANL-SW-17`'s "one loop"). The exec timeout and a failing `Exec` keep
   their current behaviour and outcome.
3. `IMP-0036`: two tickets whose stages come from the same library path never run at the same
   time; the later waits for the earlier's call to return. Decide which tickets share a path from
   the run setup, once, at load.
4. Unit tests (gtest): default is one thread (thread ids seen by a test component); with N > 1 two
   independent stages of one rank overlap; two stages of one path never overlap; commit order is
   declaration order whatever order the workers finish in (a component that sleeps longer for the
   first stage); a wired pair in one rank is never run side by side. Plant: commit in finish
   order, and drop the same-path guard — show which tests fail; restore; say so.
5. Evidence on the lab (this is not `SYT-THR-01`, which `WP-09` writes): run `simengine` on
   `running_example` `cut_c` and `all_simulated`, `diamond` `all_simulated` and `fan_out`
   `all_simulated`, each with `--threads 1` and `--threads 3`, `outputs.path` set; report for each
   pair whether the two recordings are byte-identical and whether the event logs are identical
   (compare with `lab_tools.compare.equal_outputs` from the lab's own environment if the bytes
   differ). If the engine cannot run a lab setup here, say why and skip that case.
6. Builds and suites: `build.bat -t sil -p vs2026`, `-t gtest` (C++ suite, last 401/401),
   `-t package` in `modules\vantage`; Python `tests/unit tests/system` in its own environment
   (last 1136 passed, 87 skipped); `py -3.12 scripts\check_invariants.py` at the root;
   `py -3.12 .claude/templates/requirements/trace_check.py --set modules/vantage/docs --status`.
7. Boxes: each of `IMP-0034`..`IMP-0036` `[~]` once its code and unit tests pass, the row gaining
   at its end, before the test column, "Closed by `<its test column's ids>` passing (`WP-09`)."
   (the form the `WP-05` rows use); `WP-07` as the rollup gives, with a "Closed by" clause like
   `WP-06`'s so `C-PLANMARK` is clean.

## Exit check (run all, report output and seconds)
- Each build command: pass/fail, seconds; C++ and Python counts before and after, each test
  removed by name.
- Step 5's table: case, threads 1 vs 3, recordings identical (yes/no), event logs identical.
- `check_invariants.py` clean (findings verbatim); `trace_check` PASS, the `WP-07` line.
- `git -C modules/vantage status --short`; `git diff --stat` equal with and without
  `--ignore-cr-at-eol`.

## Must not
- touch `src/simcore/runner/select_inputs.cpp`, `src/simcore/orchestrator/control.cpp`, the
  source-check scripts, or the `SYS-0017`/`SYS-0031` wording — a rework package after this one
  changes those
- read a sample buffer, the event queue, the mutator or the writer from a worker thread
- add a thread count to the run setup, or a second step loop
- write the `SYT-*` tests or the exec probe (`WP-09`)
- decide anything the rows leave open — report it with your recommendation

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds (R-TEST-7).
4. Boxes ticked (row ids), and any `[~]` with what closes it.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
