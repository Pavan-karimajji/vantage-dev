Your role: read .claude/agents/vantage-builder.md and follow it.
Keep the report under 40 lines, in the §4.2 shape.

# VNT-WP-13-R1 — the `WP-13` rework: the batch tests' run setup, the refSync bound whatever the `control` buffer depth (`IMP-0065`), and the `SYT-ORC-13` steps (vantage `c1`)

The rework of `VNT-WP-13`. Its changes are in the working copy, uncommitted: **build on them,
never revert them.** It left 4 tests failing, and the orchestrator's review found one hole in
`IMP-0065`. Five parts, in order: **A** the doc edits, exactly; **B** the `IMP-0065` bound;
**C** the batch tests; **D** builds and suites; **E** boxes.

## Context (read these, nothing else unless a step needs it)
- Working copy `C:\ws\repo\vantage-dev`, native Windows (`vs2026`). `modules/vantage` is on
  branch **`c1`** — stay on it. Never run `git checkout`, `git switch`, `git stash`, `git reset`,
  `git rm`, `git restore`, `git add`, `git commit`, `git push`, `pkill` or `kill`.
- **Owner conditions for `c1`:** every commit builds the whole of vantage and passes its full unit
  suite; a test of the old behaviour that can no longer pass is corrected in the same change, and
  you name it.
- Rules: `.claude/rules/style.md` (minimal diffs), `testing.md`, `requirements.md` R-REQ-5,
  R-REQ-9 (the row id verbatim in each new test's name).
- Python: `modules\vantage\.venv-sim-win32\Scripts\python.exe`. Never `py -3`. Root scripts:
  `py -3.12`.
- Read, after Part A: `VANTAGE_DEV_PLAN.md` `D27`, `D29`; `VANTAGE_Architecture.md` §6 step 1;
  `VANTAGE_Implementation_Design.md` row `IMP-0065`; `VANTAGE_Test_Spec.md` `SYT-RUN-06` (a port
  keeps at most `buffer_depth` samples).
- **Facts the orchestrator established** (read the code before relying on them):
  - *The hole in `IMP-0065`.* `select_inputs.cpp::NextControlNs` finds the run's own control in
    the stage's `control` sample buffer (`context.bus->Buffer("<stage>.control")`) and takes the
    sample after it. That buffer keeps `buffer_depth` samples (`cycle_loop.cpp` declares the
    control port with `port.buffer_depth`; `SampleBuffer` evicts the oldest). At depth 1 — or
    whenever `buffer_depth` later controls have arrived — the run's own control is gone, so
    `NextControlNs` returns nothing and `RecordedRefSync` takes an arrived refSync with no bound.
    That is exactly the owner's case (a run held behind an earlier waiting run while its next
    control arrives), and `SYT-ORC-13`'s own setup (`buffer_depth` 1 on every port). The two
    `IMP_0065` gtests use depth 8, so neither can see it.
  - *"At or before".* `VNT-WP-13` implemented the bound as "received at or before" the next
    control (`received_ns > next_control` refuses). The owner accepted it; edits E1, E2 put it in
    `D29 (3)` and the row. Keep that comparison.
  - *The batch tests.* `tests/unit/test_d7_batch.py::_echo_pipeline` and the pipelines written in
    `tests/system/test_d7_batch_isolation.py` (`echo_pipeline.yaml`, and `unresolvable.yaml`) declare
    no `run_setup:` block, no `trigger` and no `buffer_depth`, so the launcher refuses them
    ("expected a value for 'run_setup.readiness_limit_steps'", `SYS-0048`). The pattern that loads
    is `tests/system/test_vnt_run_config.py`'s config and `test_vnt_producer_keys.py::_echo_resim`'s
    pipeline: `run_setup: {readiness_limit_steps, fallback_max_gap}` and, per stage,
    `trigger: ''`, `buffer_depth: {'*': <n>}`. Failing now (rerun by the orchestrator, 31 s):
    `test_d7_batch.py::test_ok_recording_runs_the_real_pipeline_end_to_end`,
    `::test_recording_order_is_preserved_regardless_of_completion_order`,
    `test_d7_batch_isolation.py::test_batch_over_20_recordings_one_report_failure_does_not_abort`,
    `::test_batch_of_20_with_one_crash_one_hang_exit_code_reflects_failure`.

## Allowed changes
- `VANTAGE_DEV_PLAN.md`, `modules/vantage/docs/VANTAGE_Implementation_Design.md`,
  `modules/vantage/docs/VANTAGE_Test_Spec.md`: Part A's edits only (plus Part E's box, if any).
- `modules/vantage/src/simcore/runner/select_inputs.cpp`, `read_ahead.cpp`, `cycle_loop.cpp`,
  `modules/vantage/include/simcore/runner.hpp`, and any other file under `src/simcore/runner/` the
  `IMP-0065` fix needs.
- `modules/vantage/tests/unit/test_run_select_inputs.cpp` (and `test_run_step.cpp` only if a
  runner-level gtest is the one that can show the hole).
- `modules/vantage/tests/unit/test_d7_batch.py`, `modules/vantage/tests/system/test_d7_batch_isolation.py`.
- Everything else is read-only.

## Part A — doc edits (exact)
Every edit below is decided. Each anchor and each new text is the exact content of a fenced block
(the fence lines themselves excluded). Apply them in order, each by exact-string replacement.
Keep each file's line endings: `VANTAGE_DEV_PLAN.md` is CRLF in the working copy, the three
`modules/vantage/docs` files are LF. If an anchor is not found exactly once, stop and report it;
never adjust the text to make a check pass. The orchestrator has dry-run all six on a copy of the
working tree: `trace_check` PASS, 127 requirements, 56 tests, no findings.

**E1** · `VANTAGE_DEV_PLAN.md` · replace the anchor with the new text.

Anchor:
````
(3) A refSync already received matches only if received before its stage's next recorded `control` (`D27`).
````
New text:
````
(3) A refSync already received matches only if received at or before its stage's next recorded `control` (`D27`): the match is by `measurement_counter`, so a refSync logged at the next control's instant can only be this run's, and a strict "before" would drop it when two controls fall in one step.
````

**E2** · `modules/vantage/docs/VANTAGE_Implementation_Design.md` · replace the anchor with the new text.

Anchor:
````
an arrived refSync matches only if it was received before the stage's next recorded `control` after this run's (`D27`, `D29 (3)`); one received later is not found, so the run takes the time rule.
````
New text:
````
an arrived refSync matches only if it was received at or before the stage's next recorded `control` after this run's (`D27`, `D29 (3)`), whatever the `control` port's `buffer_depth`: the bound never depends on either control still being in the stage's sample buffer; one received later is not found, so the run takes the time rule.
````

**E3** · `modules/vantage/docs/VANTAGE_Implementation_Design.md` · replace the anchor with the new text.

Anchor:
````
under a timeout the call's inputs, input metadata and result live in state its task shares
````
New text:
````
under a timeout the call's inputs, input metadata, output buffers and result live in state its task shares
````

**E4** · `modules/vantage/docs/VANTAGE_Test_Spec.md` · replace the anchor with the new text.

Anchor:
````
| `F-REC-EDIT` | An `F-CASE` recording rewritten by the test through the Python writer in `interfaces` with the one edit its steps name: a split into files, messages removed or changed, a cut (`edit_recording`) |
````
New text:
````
| `F-REC-EDIT` | An `F-CASE` or `F-RUN-CONFIG` recording rewritten by the test through the Python writer in `interfaces` with the one edit its steps name: a split into files, messages removed or changed, a message's logging time moved, a `manifest` key changed or removed, a cut (`edit_recording`) |
````

**E5** · `modules/vantage/docs/VANTAGE_Test_Spec.md` · replace the anchor with the new text.

Anchor:
````
**`SYT-ORC-13`** · T · fixture `F-CASE`, `F-SETUP-EDIT`, `F-ENGINE` — Every run's overridden input is recorded
````
New text:
````
**`SYT-ORC-13`** · T · fixture `F-CASE`, `F-SETUP-EDIT`, `F-REC-EDIT`, `F-ENGINE` — Every run's overridden input is recorded
````

**E6** · `modules/vantage/docs/VANTAGE_Test_Spec.md` · replace the anchor with the new text.

Anchor:
````
that leaves its `sig_header` unchanged; read `B`'s `control` and re-run `refSync` messages
````
New text:
````
that leaves its `sig_header` unchanged, on a copy of its recording whose `B` controls are taken in pairs, the first of each pair logged at the instant of the second, so a step holds two `B` runs; read `B`'s `control` and re-run `refSync` messages
````

`tests/system/test_vnt_producer_keys.py::test_syt_orc_13_c1_…` already does what E6 says (its
`pair_controls` edit); leave it unchanged.

## Part B — the `IMP-0065` bound whatever the `control` buffer depth
1. First add the gtests, in `test_run_select_inputs.cpp`, each name citing `IMP_0065`, on the
   existing `RunHeldBehindAParkedRun` rig with `B.control` declared at depth **1** (a parameter of
   the rig; the two existing tests keep depth 8):
   (a) the refSync received after control 101 (300 ns) → the time rule, `fallback` true, counter 11;
   (b) the refSync received at control 101's instant (200 ns) → matched, `fallback` false, counter 10
   (the "at or before" edge). Run them on the current code and report (a) failing — if it passes,
   stop and report what you saw: the hole is not where the facts say.
2. Fix `RecordedRefSync`/`NextControlNs` so the bound holds whatever the `control` port's
   `buffer_depth` (E2). **The sample buffers keep at most `buffer_depth` samples (`SYT-RUN-06`):
   never deepen the `control` buffer or keep evicted samples in it.** Where the reception time of
   the run's next recorded control is kept instead is yours to choose (for example beside the run's
   ticket, or a per-stage record of recorded controls' reception times by counter, pruned once no
   run needs it); say which in the report. A stage with no recorded `control` is unchanged; a
   clock-started run is unchanged. Two controls at one instant (the `SYT-ORC-13` recording) must
   still let a refSync received at that instant match.
3. Rerun the four `IMP_0065` gtests, `test_run_select_inputs.cpp`'s others and
   `tests/system/test_vnt_producer_keys.py` (R-TEST-1).

## Part C — the batch tests (owner-approved correction)
4. Give every echo pipeline in `test_d7_batch.py` and `test_d7_batch_isolation.py` a `run_setup:`
   block (`readiness_limit_steps`, `fallback_max_gap`) and, per stage, `trigger: ''` and
   `buffer_depth: {'*': <n>}`, as `test_vnt_producer_keys.py::_echo_resim` does — `unresolvable.yaml`
   included, so its failure is the missing library, not the refused setup. One helper per file if the
   file writes the same pipeline twice; no new shared module.
5. Run both files. For every test in them that expects a non-`ok` outcome (`fail`, `crash`,
   `timeout`, a refused pipeline), read the outcome's error text and confirm it is the cause the test
   is about, not the run-setup refusal; report any that is not, with the text. Name each corrected
   test with its cause ("pipeline declared no run setup, `SYS-0048`").
6. A failure with any other cause: leave that test failing, stop working on it, report what was
   seen and your recommendation. No skip, tolerance or `xfail`.

## Part D — builds and suites (once, at the end)
7. `modules\vantage`: `build.bat -t sil -p vs2026`, `-t gtest` (last 443/443), `-t package`;
   Python `tests/unit tests/system` (last 1484 passed, 4 failed, 62 skipped). Root:
   `py -3.12 scripts\check_invariants.py`;
   `py -3.12 .claude/templates/requirements/trace_check.py --set modules/vantage/docs --status`.
8. Report per changed test file: passed / failed / skipped, each failure and skip with its id; the
   suite's skip count before and after (62 expected unchanged).
9. `git -C modules/vantage status --short`; `git diff --stat` equal with and without
   `--ignore-cr-at-eol` in vantage and at the root.

## Part E — boxes
10. `IMP-0065` stays `[x]` only if all four `IMP_0065` gtests and `SYT-SEL-01` pass; otherwise set it
    `[~]` with "Closed by …" naming what fails, and `WP-13` follows (`C-WPROLL`). Flip no other box.
    Expected: no box changes, `WP-13` `[x]`, 8 of 13 packages.

## Exit check (run all, report output and seconds)
- Each build command and suite: pass/fail, seconds, counts before and after; each corrected test
  by name with its cause.
- Each new gtest by name, and (a)'s failure on the code before the fix.
- `check_invariants.py` clean; `trace_check` PASS and the `WP` lines.

## Must not
- change any doc text beyond Part A and Part E's box, the contract (`modules/interfaces`), or
  anything under `modules/vantage-lab`
- touch the live measurement, the order of a run's outputs (`D29 (5)`), or anything else
  `VNT-WP-13` landed that this prompt does not name
- deepen a sample buffer, or change `SampleBuffer`/`PortBus` eviction
- add a skip, tolerance or exemption no step names
- decide anything the rows leave open — report it with your recommendation

## Report back in this shape
1. Done / not done, in one line per part.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds (R-TEST-7).
4. Boxes ticked (row ids), and any `[~]` with what closes it.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
