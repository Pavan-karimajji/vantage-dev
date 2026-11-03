Your role: read .claude/agents/vantage-builder.md and follow it.
Keep the report under 40 lines, in the §4.2 shape.

# VNT-WP-09b-2-R1 — the owner's corrections to the `09b-2` findings (`D28`): drills that diverge, the step-starting messages, identity broken on a planted recording, warming up judged by the car's copy (`IMP-0062`), and `SYT-EQO-05` (vantage `c1`, vantage-lab `main`)

The rework of `VNT-WP-09b-2`. Its changes are in the working copy, uncommitted: **build on them,
never revert them.** They left 9 cases failing (`SYT-SEL-01.c1` and `SYT-EQO-02.c2` on
`missing_sample` and `missing_run`, `SYT-SEL-10.c1`, `SYT-STP-01.c1`, `.c2`, `SYT-STP-05.c2`,
`SYT-EQO-04.c1`); the owner decided each (`D28`, edit E1). Six parts, in order: **A** the doc
edits, exactly; **B** the lab catalogue; **C** the warming-up rule in the engine; **D** the tests;
**E** builds and suites; **F** boxes.

## Context (read these, nothing else unless a step needs it)
- Working copy `C:\ws\repo\vantage-dev`, native Windows (`vs2026`). `modules/vantage` is on
  branch **`c1`**, `modules/vantage-lab` on **`main`** — stay on them. Never run `git checkout`,
  `git switch`, `git stash`, `git reset`, `git rm`, `git restore`, `git add`, `git commit`,
  `git push`, `pkill` or `kill`.
- **Owner conditions for `c1`:** every commit builds the whole of vantage and passes its full unit
  suite; a test of the old behaviour that can no longer pass is corrected in the same change, and
  you name it.
- Rules: `.claude/rules/style.md` (file header on every new file, minimal diffs), `testing.md`,
  `requirements.md` R-REQ-4, R-REQ-5, R-REQ-9 (the test id and case id verbatim in the test).
- Python: `modules\vantage\.venv-sim-win32\Scripts\python.exe`; the lab's,
  `modules\vantage-lab\.venv-lab-win32\Scripts\python.exe`. Never `py -3`. Root scripts: `py -3.12`.
- Read, after Part A: `VANTAGE_DEV_PLAN.md` `D28`; `VANTAGE_Architecture.md` §6's outcome table
  and §7 (*What "tick" now means*, *Jump*); `VANTAGE_Test_Spec.md` `SYT-SEL-08`, `SYT-SEL-09`,
  `SYT-SEL-10`, `SYT-STP-01`, `SYT-STP-05`, `SYT-EQO-04`, `SYT-EQO-05`; the `Accept` of `SYS-0027`,
  `SYS-0029`, `SYS-0032`, `SYS-0036`, `SYS-0054`; `VANTAGE_Implementation_Design.md` rows
  `IMP-0021`, `IMP-0062`; the tests you wrote in `09b-2`.
- **Facts the orchestrator established** (read the code before relying on them):
  - *Drills.* On `F-TAP` with `outputs.path`, `missing_sample`'s `first_divergence` is `B` `out`
    at step 77 (500 ms), the step of `B`'s run 12, the first run whose recorded refSync names a
    dropped `Y` (20), which carries `KIND_FALLBACK` on `B.in_Y`; `missing_run`'s is `E` `out` at
    step 117 (750 ms), `E`'s run 25 (wants `Y` 30), `KIND_FALLBACK` on `E.in_Y`. Both line up.
  - *Steps.* `Runner::Construct` (`cycle_loop.cpp`) makes a port a **queue** port (it starts a
    step) when it is a source port some stage reads, a `pro` port of a `measured` stage (an
    `off` stage declares nothing), or the `control` of a `simulate` stage; a `simulate` stage's `pro` ports and its
    `refSync` are **reference**; `Runner::TopUp` drops an instant with no queue message. The
    recorded refSync is looked up (`RecordedRefSync`, `ReadAhead::SearchRefSync`), never waited
    for. That is the closed list of `ARCH §7` (E3).
  - *Identity broken.* `running_example` `base` with `source.X`'s `measurement_counter` lowered
    by 5 from its 100th sample on (`cycle_counter` unchanged), run `all_simulated` on `F-TAP`:
    `KIND_IDENTITY_BROKEN` `{source.X: 1}`, first at the 1000 ms step (the 100th sample's), no
    other subject, no `counter_gap` or `counter_reset`.
  - *Warming up.* `Orchestrator::NextRunnable` (`orchestrator.cpp`) sets
    `ticket.warming_up = ticket.restart && <stage has recorded outputs> &&
    ticket.trigger_time_ns != options_.first_reception_ns` — the old `ARCH §6` row, which badges
    `A`, `B`, `D`, `E` on `cut_c`. The lab car writes RESTART on each component's first run.
    `Ticket` carries `trigger_port` (empty for a clock) and `trigger_payload` (the recorded
    control, or the trigger sample). `first_reception_ns` has other callers (`control.cpp`).
  - *`SYT-SEL-08`.* In `base`, `E`'s run 5 (control at 150 ms) names `Y` 6, logged at
    151.51 ms: a run before a sample's logging time may be handed it, hence `D28 (5)`.

## Part A — doc edits (exact)
Every edit below is decided. Each anchor and each new text is the exact content of a fenced block
(the fence lines themselves excluded). Apply them **in order** (E14's anchor is E13's new text),
each by exact-string replacement, keeping each file's line endings (all LF). If an anchor is not
found exactly once, stop and report it; never adjust the text to make a check pass. The
orchestrator has dry-run all 22: `trace_check` PASS, 116 requirements, 53 tests, no findings,
and PASS again in the final box state of step 13.

**E1** · `VANTAGE_DEV_PLAN.md` · insert the new text as new line(s) directly after the line holding the anchor.

Anchor:
````
| D27 | **A run's refSync is searched to its stage's next control (`SYT-ORC-07.c3`).**
````
New text:
````
| D28 | **The `09b-2` findings (owner, 2026-11-03).** (1) `missing_sample` and `missing_run` expect `diverges`: the car used samples the recording lacks. Their first divergence is not before the first run that lost an input, and that run carries `KIND_FALLBACK` (`SYS-0054`). (2) A step is made only where a step-starting message arrives or a clock ticks; the step-starting messages are a closed list taken from the engine (`ARCH §7`). A recorded `refSync`'s arrival is not a step: a run looks its `refSync` up ahead (`D27`) and never waits for it. Amends `SYS-0032`. (3) Identity broken (`SYS-0029`) is proven on a planted recording whose `source.X` `measurement_counter` goes back; `renumber` is described as what it shows, an output not copying its control's counter (`SYT-ORC-05`). (4) `D17 (4)` made exact: *started mid-recording* means the car's copy of the stage was not fresh at the stage's first run after the start or a jump. Only the car's recorded control of that run shows it fresh, by carrying RESTART: the control the run replays, or, for a run started by a trigger sample, the stage's recorded control of the same `measurement_counter`. Where the recording cannot say (a clock-started run, or no such control), the stage is badged. (5) `SYS-0027` names the runs whose recorded entry names a removed sample, not the runs before the first remaining sample's logging time: a car run may read a sample logged after its control. | 2026-11-03 |
````

**E2** · `modules/vantage/docs/VANTAGE_Architecture.md` · replace the anchor with the new text.

Anchor:
````
| the stage's first run after the start or a jump is not at the recording's start, and the recording holds the stage's outputs |
````
New text:
````
| the stage's first run after the start or a jump, unless the car's recorded control of that run carries RESTART (`D28 (4)`; a clock-started run has none), and the recording holds the stage's outputs |
````

**E3** · `modules/vantage/docs/VANTAGE_Architecture.md` · replace the anchor with the new text.

Anchor:
````
place everywhere. A step exists for every instant at which any event is processed,
including instants at which only measured samples arrive, so a reader sees every
recorded value at its own instant.
````
New text:
````
place everywhere. A step exists for every instant at which a step-starting message
arrives or a clock ticks. The step-starting messages are a closed list, the recorded
messages the engine buffers: a `source` sample some stage's input reads; each output
the run setup declares for a `measured` stage (its data outputs, `refSync`,
`compState`); a `simulate` stage's recorded `control`, whatever its trigger. Nothing
else starts a step. A `simulate` stage's recorded data outputs, `refSync` and
`compState` are reference, read by *Where equal outputs apply* and by input
selection; a run looks its recorded `refSync` up ahead (`D27`) and never waits for
it, so a `refSync`'s arrival is not a step. Nor is a topic the run setup does not
declare, or a `measured` or `off` stage's `control` (`D28 (2)`). So a reader sees
every value the engine consumed at its own instant.
````

**E4** · `modules/vantage/docs/VANTAGE_Architecture.md` · replace the anchor with the new text.

Anchor:
````
components warm up, and `KIND_WARMING_UP` is raised on a stage only when the
recording holds the stage's outputs.
````
New text:
````
components warm up, and `KIND_WARMING_UP` is raised on a stage only when the
recording holds the stage's outputs and does not show the car's copy fresh there
(§6, `D28 (4)`).
````

**E5** · `modules/vantage/docs/VANTAGE_System_Requirements.md` · replace the anchor with the new text.

Anchor:
````
Priority split: 25 `P0`, 28 `P1`, 0 `P2`; all `R1`.
````
New text:
````
Priority split: 25 `P0`, 29 `P1`, 0 `P2`; all `R1`.
````

**E6** · `modules/vantage/docs/VANTAGE_System_Requirements.md` · replace the anchor with the new text.

Anchor:
````
**Accept.** With the first five `source.Y` samples removed from `running_example`'s `base` recording, every run before the first remaining one has re-run entry 0 for `Y`; a non-zero entry fails.
````
New text:
````
**Accept.** With the first five `source.Y` samples removed from `running_example`'s `base` recording, every run whose recorded entry for `Y` names a removed sample has re-run entry 0 for `Y`; a non-zero entry fails.
````

**E7** · `modules/vantage/docs/VANTAGE_System_Requirements.md` · replace the anchor with the new text.

Anchor:
````
**Accept.** On `data_triggered` `renumber`, the badge is raised on `T`'s output port as `VANTAGE_Lab_Design.md` §6.2 expects; in every exact case it is never raised.
````
New text:
````
**Accept.** On `running_example` `base` with `source.X`'s `measurement_counter` lowered by 5 from its 100th sample on, its `cycle_counter` unchanged, the badge is raised once, on `source.X` and no other port; in every exact case it is never raised.
````

**E8** · `modules/vantage/docs/VANTAGE_System_Requirements.md` · replace the anchor with the new text.

Anchor:
````
**`SYS-0032`** · `P0` · `R1` — One engine step per instant at which anything happens
**Shall.** The engine shall make one engine step for each instant at which a recorded message arrives or a clock ticks, numbered from 0 without a gap.
**Accept.** On `running_example` `cut_c`, the steps are the recording's distinct reception times, numbered consecutively from 0; with `E` started by a 7 ms clock instead, each tick instant adds its step.
````
New text:
````
**`SYS-0032`** · `P0` · `R1` — One engine step per instant a step-starting message arrives or a clock ticks
**Shall.** The engine shall make one step per instant at which a step-starting message (`ARCH §7`) arrives or a clock ticks, numbered from 0 without a gap.
**Accept.** On `running_example` `cut_c`, the steps are its step-starting messages' distinct reception times, numbered from 0 without a gap; with `E` on a 7 ms clock instead, each tick instant adds its step.
````

**E9** · `modules/vantage/docs/VANTAGE_System_Requirements.md` · insert one blank line, then the new text, directly after the line holding the anchor.

Anchor:
````
**Verify.** T · `SYT-EQO-02`   **Trace.** —
````
New text:
````
**`SYS-0054`** · `P1` · `R1` — A lost input's divergence comes no earlier than the run that lost it
**Shall.** The engine shall report no divergence before the first run that lost an input the recording lacks.
**Accept.** On `missing_sample` and `missing_run` the first divergence is reported at or after the first run whose recorded refSync names a dropped sample, and that run carries `KIND_FALLBACK` on that input.
**Binds.** `eventLog`, `stepRecord`
**Verify.** T · `SYT-EQO-05`   **Trace.** —
````

**E10** · `modules/vantage/docs/VANTAGE_Test_Spec.md` · replace the anchor with the new text.

Anchor:
````
run `all_simulated`; read the re-run entries for `Y` of every run before the first remaining `source.Y` sample.
````
New text:
````
run `all_simulated`; read the re-run entry for `Y` of every run whose recorded entry for `Y` names a removed sample.
````

**E11** · `modules/vantage/docs/VANTAGE_Test_Spec.md` · replace the anchor with the new text.

Anchor:
````
**`SYT-SEL-10`** · T · fixture `F-CAT`, `F-TAP` — Identity broken is badged
**Serves.** `SYS-0029`
**Steps.** Run `data_triggered` `renumber` `by_data` and every exact case; read every `KIND_IDENTITY_BROKEN` badge.
- `.c1` **PASS:** `renumber`: raised on `T`'s output port, per `SYS-0029` Accept. **FAIL:** not raised, or raised on another port.
````
New text:
````
**`SYT-SEL-10`** · T · fixture `F-CAT`, `F-REC-EDIT`, `F-TAP` — Identity broken is badged
**Serves.** `SYS-0029`
**Steps.** In `running_example`'s `base` recording lower `source.X`'s `measurement_counter` by 5 from its 100th sample on, its `cycle_counter` unchanged; run `all_simulated` on it on `F-TAP`. Run every exact case on `F-TAP`. Read every `KIND_IDENTITY_BROKEN` badge.
- `.c1` **PASS:** edited: one badge, on `source.X` at the step of its 100th sample, per `SYS-0029` Accept. **FAIL:** none, more than one, another step, or a badge on any other port (a downstream stage's input or output).
````

**E12** · `modules/vantage/docs/VANTAGE_Test_Spec.md` · replace the anchor with the new text.

Anchor:
````
**Steps.** Run `running_example` `cut_c` on `F-TAP`; list the recording's distinct reception times. Then set `E`'s trigger empty and `clock_period_ns` to 7 ms, and run again.
````
New text:
````
**Steps.** Run `running_example` `cut_c` on `F-TAP`; list the distinct reception times of the recording's step-starting messages (`VANTAGE_Architecture.md` §7): here `source.X`, `source.Y`, `source.Z`, `C`'s `out`, `refSync` and `compState`, and the `control` of `A`, `B`, `D` and `E`. Then set `E`'s trigger empty and `clock_period_ns` to 7 ms, and run again.
````

**E13** · `modules/vantage/docs/VANTAGE_Test_Spec.md` · replace the anchor with the new text.

Anchor:
````
- `.c1` **PASS:** as `SYS-0045` Accept, `no_ref_sync`'s step count equal to the recording's distinct reception times. **FAIL:** a fail outcome, or fewer steps.
````
New text:
````
- `.c1` **PASS:** as `SYS-0045` Accept, `no_ref_sync`'s step count equal to the number of distinct reception times of its recording's step-starting messages (`VANTAGE_Architecture.md` §7). **FAIL:** a fail outcome, or another number of steps.
````

**E14** · `modules/vantage/docs/VANTAGE_Test_Spec.md` · insert one blank line, then the new text, directly after the line holding the anchor.

Anchor:
````
- `.c1` **PASS:** as `SYS-0045` Accept, `no_ref_sync`'s step count equal to the number of distinct reception times of its recording's step-starting messages (`VANTAGE_Architecture.md` §7). **FAIL:** a fail outcome, or another number of steps.
````
New text:
````
**`SYT-EQO-05`** · T · fixture `F-CASE`, `F-TAP` — A lost input's divergence comes no earlier than the loss
**Serves.** `SYS-0054`
**Steps.** Run `running_example` `missing_sample` and `missing_run` `all_simulated` on `F-TAP` with `outputs.path` set. In each, find the run of `B` or `E` at the earliest step whose recorded refSync names a dropped `source.Y` sample; read the event log's `first_divergence` entry and that step's badges.
- `.c1` **PASS:** in each, as `SYS-0054` Accept. **FAIL:** no entry, an entry at an earlier step, or no `KIND_FALLBACK` on that run's `in_Y` at its step.
````

**E15** · `modules/vantage/docs/VANTAGE_Lab_Design.md` · replace the anchor with the new text.

Anchor:
````
| `all_simulated` | fallback by counter, inside `fallback_max_gap` (3 missing) |
````
New text:
````
| `all_simulated` | `expect: diverges`: fallback by counter, inside `fallback_max_gap` (3 missing); the first divergence is not before the first run that lost an input, which carries `KIND_FALLBACK` (`SYS-0054`) |
````

**E16** · `modules/vantage/docs/VANTAGE_Lab_Design.md` · replace the anchor with the new text.

Anchor:
````
| `all_simulated` | gap beyond `fallback_max_gap`: the time rule picks |
````
New text:
````
| `all_simulated` | `expect: diverges`: gap beyond `fallback_max_gap`: the time rule picks; the first divergence as for `missing_sample` |
````

**E17** · `modules/vantage/docs/VANTAGE_Lab_Design.md` · replace the anchor with the new text.

Anchor:
````
| `by_data` | identity broken on `T`'s output |
````
New text:
````
| `by_data` | `expect: diverges`: `T`'s outputs carry its run count, an output not copying its control's counter (`RCT:SYS-0001`); the engine's check of that break is `SYT-ORC-05`, on `renumber_lib`. Never identity broken (`D17 (3)`): a run count never goes back |
````

**E18** · `modules/vantage/docs/VANTAGE_Implementation_Design.md` · replace the anchor with the new text.

Anchor:
````
and seeks the reader; the step number continues; each stage whose outputs the recording holds is warming up from its next run.
````
New text:
````
and seeks the reader; the step number continues; each stage's next run is judged warming up as `IMP-0062` says.
````

**E19** · `modules/vantage/docs/VANTAGE_Implementation_Design.md` · insert the new text as new line(s) directly after the line holding the anchor.

Anchor:
````
| `[~]` | `IMP-0021` |
````
New text:
````
| `[ ]` | `IMP-0062` | `SYS-0036` | `WP-04` | `EXTEND` | `src/simcore/orchestrator/orchestrator.cpp::Orchestrator::NextRunnable` — a stage's first run after the start or a jump is warming up when the recording holds the stage's outputs, unless the car's recorded control of that run is RESTART: the one it replays, or for a trigger-sample run the stage's recorded control of the same `measurement_counter`; a clock-started run always is (`D28 (4)`). | `SYT-STP-05` |
````

**E20** · `modules/vantage/docs/VANTAGE_Implementation_Design.md` · replace the anchor with the new text.

Anchor:
````
| `[~]` | `IMP-0033` | `SYS-0043`, `SYS-0045` |
````
New text:
````
| `[~]` | `IMP-0033` | `SYS-0043`, `SYS-0045`, `SYS-0054` |
````

**E21** · `modules/vantage/docs/VANTAGE_Implementation_Design.md` · replace the anchor with the new text.

Anchor:
````
never changes the outcome. Closed by `SYT-EQO-02`, `SYT-EQO-04` passing (`WP-09`). | `SYT-EQO-02`, `SYT-EQO-04` |
````
New text:
````
never changes the outcome. Closed by `SYT-EQO-02`, `SYT-EQO-04`, `SYT-EQO-05` passing (`WP-09`). | `SYT-EQO-02`, `SYT-EQO-04`, `SYT-EQO-05` |
````

**E22** · `modules/vantage/docs/VANTAGE_Implementation_Design.md` · replace the anchor with the new text.

Anchor:
````
| `[~]` | `IMP-0048` | `SYS-0040`, `SYS-0041`, `SYS-0043`, `SYS-0044`, `SYS-0045` | `WP-09` | `NEW` | `tests/system/test_vnt_equal_outputs.py` — `SYT-THR-02`, `SYT-THR-03` and `SYT-EQO-02` to `SYT-EQO-04`. Closed by `SYT-EQO-02.c2`, `SYT-EQO-04.c1` passing. | `SYT-THR-02`, `SYT-THR-03`, `SYT-EQO-02`, `SYT-EQO-03`, `SYT-EQO-04` |
````
New text:
````
| `[~]` | `IMP-0048` | `SYS-0040`, `SYS-0041`, `SYS-0043`, `SYS-0044`, `SYS-0045`, `SYS-0054` | `WP-09` | `NEW` | `tests/system/test_vnt_equal_outputs.py` — `SYT-THR-02`, `SYT-THR-03` and `SYT-EQO-02` to `SYT-EQO-05`. Closed by `SYT-EQO-02.c2`, `SYT-EQO-04.c1`, `SYT-EQO-05.c1` passing. | `SYT-THR-02`, `SYT-THR-03`, `SYT-EQO-02`, `SYT-EQO-03`, `SYT-EQO-04`, `SYT-EQO-05` |
````

## Part B — the lab catalogue (`D28 (1)`)
1. `modules/vantage-lab/catalogue/running_example.yaml`: give `missing_sample` and `missing_run`
   the line `    expect: diverges` directly under their `- name:` line, as `no_ref_sync` has it.
   Nothing else in the lab changes; no recording is regenerated (`expect` is not written into
   any lab output — check that, and report it).
2. Correct `tests/test_car_drills.py::test_lab52_the_running_example_has_the_drills_of_section_6_2`,
   whose expect set pins the old values, and name it.

## Part C — warming up judged by the car's copy (`IMP-0062`, `D28 (4)`, `ARCH §6` as amended)
3. In `Orchestrator::NextRunnable`, replace the `first_reception_ns` comparison: a stage's first
   run after the start or a jump (`ticket.restart`), when the recording holds the stage's outputs,
   is warming up unless the car's recorded control of that run carries `op_mode` RESTART — for a
   run started by a recorded control, the control it replays (`trigger_payload`); for a run
   started by a trigger sample, the stage's recorded `control` with the run's
   `measurement_counter`, arrived or in the read-ahead (held to the readiness limit). A
   clock-started run, or a trigger-sample run whose recorded control is not found, is warming up.
   If the orchestrator cannot reach the recorded controls for the trigger-sample case without a
   decision no row states, stop that branch and report it.
4. gtests, each citing `IMP-0062`: (a) at the start, a run replaying a recorded RESTART control:
   no badge; (b) at the start, a replayed RUN control (a recording that starts mid-drive): badged;
   (c) the owner's case: a clock-started stage whose outputs the recording holds, at the start:
   badged; (d) a trigger-sample run whose recorded control of the same counter is RESTART: no
   badge; the same with no such control: badged; (e) after a jump onto a RUN control: badged;
   (f) a stage whose outputs the recording lacks: never badged. A test of the old rule that can no
   longer pass is corrected and named.

## Part D — the tests (`IMP-0046`..`IMP-0048`)
5. `SYT-SEL-01.c1` and `SYT-EQO-02.c2` change no code: the exact cases come from the catalogue
   (`exact_cases()`). `SYT-SEL-09` names its cases in its steps, so it now runs `missing_sample`
   and `missing_run` explicitly beside the exact cases (`_BADGE_CASES` takes them from
   `exact_cases()` today).
6. `SYT-SEL-08`: its docstring and comment say the steps as amended (E10); the check is unchanged.
7. `SYT-SEL-10.c1` as amended (E11), its edit helper beside `_restart_x`; a badge on any subject
   other than `source.X` fails, naming it.
8. `SYT-STP-01.c1`, `.c2` and `SYT-EQO-04.c1`: the step-starting instants are derived from the run
   setup and the recording by `ARCH §7`'s closed list, in one helper in
   `tests/support/engine_runs.py`; `SYT-STP-01.c1` also requires that, on `cut_c`, the topics the
   helper chose are exactly those its steps list, so the helper can fail.
9. `SYT-STP-05.c2` runs unchanged and must now pass after Part C.
10. `SYT-EQO-05.c1` in `tests/system/test_vnt_equal_outputs.py`, parametrized over the two drills.
11. A failing case is a finding: if the engine is wrong and the fix lies inside a design row's
    text (name the row), make it with a unit test; otherwise leave it failing and report it with
    what was seen and your recommendation. No skip beyond `09b-2`'s, no tolerance, no `xfail`.

## Part E — builds and suites (once, at the end)
12. `modules\vantage`: `build.bat -t sil -p vs2026`, `-t gtest` (last 432/432), `-t package`;
    Python `tests/unit tests/system` (last 1456 passed, 9 failed, 85 skipped). `modules\vantage-lab`:
    its suite on the lab Python (last 278 passed, 18 skipped). Root:
    `py -3.12 scripts\check_invariants.py`;
    `py -3.12 .claude/templates/requirements/trace_check.py --set modules/vantage/docs --status`.

## Part F — boxes
13. Only for rows whose cases all pass, each "Closed by …" sentence removed: `IMP-0062` to `[x]`
    when its gtests and `SYT-STP-05` pass; then every `[~]` row whose "Closed by" names only tests
    that now all pass. A row naming `SYT-THR-01`, `SYT-EQO-01`, `ANL-01`, `ANL-02`, `G3` or a test
    not yet written stays `[~]` unchanged. If every case passes, the orchestrator's dry run expects
    exactly these to flip: `IMP-0009`, `0017`, `0020`, `0021`, `0023`, `0026`, `0029`, `0030`,
    `0032`, `0033`, `0041`, `0046`, `0047`, `0048`, `0062`, and `WP-05`, `WP-06` by the rollup.
    `C-WPROLL`, `C-PLANMARK` and `C-ROWMARK` clean. List every row you flip.

## Exit check (run all, report output and seconds)
- Each build command and suite: pass/fail, seconds, counts before and after; each corrected test
  by name (vantage and lab).
- Each new gtest by name; per test file, cases passed / failed / skipped, each failure and skip
  with its id and reason.
- `check_invariants.py` clean; `trace_check` PASS and the `WP` lines.
- `git -C modules/vantage status --short`, `git -C modules/vantage-lab status --short`;
  `git diff --stat` equal with and without `--ignore-cr-at-eol` in both and at the root.

## Must not
- change any doc text beyond Part A and step 13's boxes and "Closed by" sentences, the contract
  (`modules/interfaces`), or anything under `modules/vantage-lab` beyond Part B
- write `SYT-EQO-01`, `SYT-THR-01` or the G3 gate (`09c`); touch the engine's manifest keys, the
  refSync search bound or the live measurement (the producer-keys package)
- add a skip, tolerance or exemption no step names
- decide anything the rows leave open — report it with your recommendation

## Report back in this shape
1. Done / not done, in one line per part.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds (R-TEST-7).
4. Boxes ticked (row ids), and any `[~]` with what closes it.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
