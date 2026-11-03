Your role: read .claude/agents/vantage-builder.md and follow it.
Keep the report under 40 lines, in the §4.2 shape.

# VNT-WP-09c — gate G3: every exact case equals the fake car, and N threads equal one (`IMP-0043`, `SYT-EQO-01`, `SYT-THR-01`, vantage `c1`)

The last package of `WP-09`. It writes the gate's test file, runs it, and, if both tests pass,
ticks the rows the gate closes. **It changes no engine code**: a failing case is a finding for
the owner, reported, never fixed or weakened here. Three parts, in order: **A** the gate tests;
**B** the full suite; **C** boxes.

## Context (read these, nothing else unless a step needs it)
- Working copy `C:\ws\repo\vantage-dev`, native Windows (`vs2026`). `modules/vantage` is on
  branch **`c1`** — stay on it. Never run `git checkout`, `git switch`, `git stash`, `git reset`,
  `git rm`, `git restore`, `git add`, `git commit`, `git push`, `pkill` or `kill`.
- Rules: `.claude/rules/style.md` (file header on the new file), `testing.md`, `requirements.md`
  R-REQ-4, R-REQ-5, R-REQ-9 (the test id and case id verbatim in each test).
- Python: `modules\vantage\.venv-sim-win32\Scripts\python.exe`. Never `py -3`. Root scripts:
  `py -3.12`.
- Read: `VANTAGE_DEV_PLAN.md` §5 (gate G3); `modules/vantage/docs/VANTAGE_System_Requirements.md`
  `SYS-0039`, `SYS-0042`; `VANTAGE_Test_Spec.md` the fixture catalogue and §1 (`SYT-EQO-01`,
  `SYT-THR-01`); `VANTAGE_Implementation_Design.md` row `IMP-0043` and the `[~]` rows of Part C.
- Read for the conventions to reuse: `tests/support/engine_runs.py` (`exact_cases`, `case_params`,
  `ran`, `run_case`, `tap_case`, `Recording`, `compare_recordings`, `lab_compare`,
  `simulated_names`, `instants`) and `tests/system/test_vnt_equal_outputs.py` (its docstring's
  "step" convention, and how `SYT-EQO-02.c1` pairs a run's output with the recorded run of the same
  `measurement_counter` through the lab's comparator).
- **Facts the orchestrator established:**
  - The lab is built on this machine: `exact_cases()` gives 25 cases, every one with its setup;
    `running_example` `base` `jump` is the only one with a jump (`jump_to_ms: 1500`, `C` measured).
    Simulated-stage counts per case run from 1 to 5, so `SYT-THR-01` has 40 (case, N) pairs; a case
    with one simulated stage has none.
  - `SYT-EQO-02.c2` already passes: no exact case without a jump reports a first divergence. So
    `SYT-EQO-01` is expected to pass; the jump case is the one it adds.
  - `lab_tools.compare.equal_outputs` compares two sequences position by position with the
    header's `cycle_counter` zeroed; `compare_recordings` applies it per topic in file order.
  - A dry run of Part C's final box state: `trace_check` PASS (127, 56), 13 of 13 packages.

## Allowed changes
- `modules/vantage/tests/system/test_vnt_gate_g3.py` (new).
- `modules/vantage/tests/support/engine_runs.py`: only a helper the new file needs, added, no
  existing helper's behaviour changed.
- `modules/vantage/docs/VANTAGE_Implementation_Design.md`: Part C's boxes and the "Closed by …"
  sentences of the rows and packages it flips, nothing else.
- Everything else is read-only — `src/`, `include/` and the lab included.

## Part A — the gate tests (`IMP-0043`)
1. `tests/system/test_vnt_gate_g3.py`, with the file header and a docstring stating each choice
   below. One test per case, parametrized over lab cases with `case_params` (one parameter per
   case, or per (case, N)), each naming its test and case id verbatim and its FAIL side.
2. **`SYT-EQO-01.c1`**, over `exact_cases()`:
   - Run the case on `F-ENGINE` (`ran`), except `running_example` `base` `jump`: on `F-TAP`
     (`tap_case`) with `outputs.path` set and `jump=(500, 1500)`.
   - Compared topics: each simulated stage's data outputs and `compState` — its `pro` ports
     except `refSync`; never a `measured` stage's.
   - Pair each reproduced message with the recorded message of the same topic and the same
     `sig_header.measurement_counter`; compare each pair through `F-COMPARE`
     (`lab_compare()`'s `equal_outputs`). A reproduced message with no recorded counterpart is a
     difference.
   - Jump case: leave out reproduced messages logged at a step the tap shows badged
     `KIND_WARMING_UP` (step time = logging time in the engine-run recording); assert each
     simulated stage still has at least one compared message after the jump, so the case can fail.
     Every other case: each topic's reproduced counters equal its recorded counters, in order.
   - A difference fails naming topology, case, stage, port and step (the step convention of
     `test_vnt_equal_outputs.py`).
3. **`SYT-EQO-01.c2`**: `running_example`, scenario `no_ref_sync`, case `all_simulated`, through
   the same comparison function as `.c1`; at least one difference. FAIL: none found.
4. **`SYT-THR-01.c1`**, over every (exact case, N) with N from 2 to the case's number of simulated
   stages: run with `--threads 1` and `--threads N` (the jump case on `F-TAP` with the same jump
   both times); `compare_recordings` over every topic of either recording is empty, and the two
   event logs are identical line by line. The `--threads 1` run may be made once per case and
   shared across its N (a module-scoped cache), never shared across cases. A difference fails
   naming case, N, port and step (from `first_difference` and that message's logging time); an
   event-log difference names the first differing line of each.
5. Run the file. Report its count, seconds and every failure with what it names.
6. **If a case fails:** do not change the engine, the lab, the comparator or the case list, and add
   no skip, tolerance, exclusion or `xfail`. Stop Part A there, keep the test as specified, and
   report each failing case with its first difference, what you read in the engine to explain it,
   and your recommendation. A test whose own logic you got wrong (it would fail on equal inputs)
   you correct, and say so.

## Part B — the full suite (once, at the end)
7. Python `tests/unit tests/system` in `modules\vantage` (last 1488 passed, 0 failed, 62 skipped).
   Root: `py -3.12 scripts\check_invariants.py`;
   `py -3.12 .claude/templates/requirements/trace_check.py --set modules/vantage/docs --status`.
   No C++ build: nothing compiled changes.
8. `git -C modules/vantage status --short`; `git diff --stat` equal with and without
   `--ignore-cr-at-eol` in vantage.

## Part C — boxes (only if every case of both tests passes)
9. `IMP-0043` to `[x]`.
10. Then each `[~]` row below whose every "Closed by" test now passes — run any you have not run in
    this package and report it: set it `[x]` and delete its sentence from " Closed by" through
    "(`WP-09`)." inclusive (one leading space removed with it). `IMP-0006`, `IMP-0008`,
    `IMP-0016`, `IMP-0019`, `IMP-0034`, `IMP-0035`, `IMP-0040`, `IMP-0053`, `IMP-0056`. A row whose
    test fails or is missing stays `[~]`; say which.
11. Packages follow their rows (`C-WPROLL`): a package that becomes `[x]` (`WP-02`, `WP-04`,
    `WP-07`, `WP-09`, `WP-11`) loses its " Closed by …" sentence the same way, to the end of the
    line. Touch no other row — `IMP-0052`'s old sentence included.
12. Rerun `trace_check --status`. Expected: PASS, 127 requirements, 56 tests, 13 of 13 packages;
    `C-WPROLL`, `C-PLANMARK`, `C-ROWMARK` clean. List every box you flipped.
13. If a case failed in Part A: flip nothing, and say so.

## Exit check (run all, report output and seconds)
- `test_vnt_gate_g3.py`: passed / failed / skipped per test, seconds; each failure as step 6 says.
- The full Python suite: counts before and after, seconds; `check_invariants.py` clean;
  `trace_check` PASS and the `WP` lines.
- The diff-stat check of step 8.

## Must not
- change engine, lab, interfaces or comparator code, or any doc text beyond Part C
- decide that a difference is acceptable, or narrow what a case compares — report it instead
- add a skip, tolerance or exemption no step names
- commit or push

## Report back in this shape
1. Done / not done, in one line per part.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds (R-TEST-7).
4. Boxes ticked (row ids), and any `[~]` with what closes it.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
