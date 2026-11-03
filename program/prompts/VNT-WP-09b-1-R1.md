Your role: read .claude/agents/vantage-builder.md and follow it.
Keep the report under 40 lines, in the §4.2 shape.

# VNT-WP-09b-1-R1 — rework of 09b-1: four engine fixes, `D27`, and two corrected tests (`IMP-0044`, `IMP-0045`, vantage `c1`)

This continues `VNT-WP-09b-1` in the **same working tree**: its uncommitted files
(`tests/system/test_vnt_run_setup.py`, `tests/system/test_vnt_orchestrator.py`,
`tests/support/engine_runs.py`, `lab_cases.py`, `foreign_mcap.py`, the design document's boxes)
stay and are built on. The owner has decided every open question (`program/ORCHESTRATION_LEDGER.md`,
the 2026-11-03 entries; `VANTAGE_DEV_PLAN.md` `D27` after Part A). Three parts, in order: **A** the
doc edits, exactly; **B** the engine and test changes; **C** builds, suites, boxes. If B stops on
something you cannot resolve, report it with what you did finish.

## Context (read these, nothing else unless a step needs it)
- Working copy `C:\ws\repo\vantage-dev`, native Windows (`vs2026`). `modules/vantage` is on
  branch **`c1`** — stay on it. Never run `git checkout`, `git switch`, `git stash`, `git reset`,
  `git rm`, `git restore`, `git add`, `git commit`, `git push`, `pkill` or `kill`.
- **Owner conditions for `c1`:** every commit builds the whole of vantage and passes its full unit
  suite; a test of the old behaviour that can no longer pass is corrected in the same change, and
  you name it.
- Rules: `.claude/rules/style.md` (file header on every new file, minimal diffs), `testing.md`,
  `requirements.md` R-REQ-4, R-REQ-5, R-REQ-9; `.claude/rules/sim.md` R-SIM-6.
- Python: `modules\vantage\.venv-sim-win32\Scripts\python.exe`; the lab's,
  `modules\vantage-lab\.venv-lab-win32\Scripts\python.exe`. Never `py -3`. Root scripts: `py -3.12`.
- Read: `VANTAGE_Architecture.md` §6 and §7 (after Part A); `VANTAGE_Implementation_Design.md`
  rows `IMP-0026`, `IMP-0044`, `IMP-0045`, `IMP-0050`, `IMP-0061` (after Part A);
  `RCT_Implementation_Design.md` `IMP-0033`; `VANTAGE_Test_Spec.md` `SYT-RUN-06`, `SYT-ORC-02`..`08`,
  `SYT-ORC-11`; `VANTAGE_System_Requirements.md` `SYS-0006`, `SYS-0012`, `SYS-0014`, `SYS-0015`,
  `SYS-0053`.
- Facts the orchestrator established (read the code before relying on them):
  - `src/simcore/runner/select_inputs.cpp` computes `input.eviction_miss` but parks a ticket on a
    `simulate` producer whether or not the named sample was evicted.
  - `Runner::WriteStep` (`cycle_loop.cpp`) writes, per step, the newest sample of each touched
    topic, in the topic list's order, which holds every `pro` topic before every `req` topic: a
    stage's `control` lands after its own outputs, and a stage that runs twice in one step (a
    parked ticket released, `ARCH §7`, or `EndStep`'s forced last step) keeps one message per topic.
  - `RecordedRefSync` already matches the recorded refSync by `measurement_counter`; the read-ahead
    is filled to `readiness_limit_steps` + 1 instants (`cycle_loop.cpp`), so a limit of 0 hides a
    refSync the lab car logs after its control (up to 8 ms later in `late_consumer`, Q's jitter).
  - `stalled_trigger` is given the producer's port (`source.X`); `eviction_miss` and
    `fallback_beyond_gap` are given the stage's own (`input.port`).

## Part A — doc edits (exact)
Every edit below is decided. Each anchor and each new text is the exact content of a fenced block
(the fence lines themselves excluded). Apply each by exact-string replacement or insertion,
keeping each file's line endings (`VANTAGE_DEV_PLAN.md` is CRLF in the working tree, the rest
LF). If an anchor is not found exactly once, stop and report it; never adjust the text to make a
check pass. The orchestrator has dry-run all 21 edits on a copy of the current working tree:
`trace_check` gives PASS, 114 requirements, 52 tests, no findings, and PASS again in the final box
state of step 12. Boxes are set in Part C, not here.

**E1** · `VANTAGE_DEV_PLAN.md` · insert the new text as new line(s) directly after the line holding the anchor.

Anchor:
````
| D26 | **Config bundle in a recording.**
````
New text:
````
| D27 | **A run's refSync is searched to its stage's next control (`SYT-ORC-07.c3`).** The engine takes the recorded `refSync` whose `measurement_counter` equals the run's control's (C1 copies it), never the first `refSync` after the control: a car run that overruns logs its `refSync` after the next control, and matching by position would hand run k+1's record to run k unnoticed. The search reads ahead past the readiness limit and stops at the stage's next recorded `control`; a stage the recording holds no `control` of stops at the readiness limit. Not found by then, the run takes the time rule with `KIND_FALLBACK` on every input. The readiness limit bounds only how long a run waits for a named sample, so a limit of 0 still finds each run's `refSync`; `SYS-0015` is unchanged. Supersedes `ARCH` open question 11's "the read-ahead is the readiness limit". | 2026-11-03 |
````

**E2** · `modules/vantage/docs/VANTAGE_Architecture.md` · replace the anchor with the new text.

Anchor:
````
only for a stage with no recorded refSync, or beyond the counter fallback's maximum gap (§6)
````
New text:
````
only for a run whose recorded refSync is not found (`D27`), or beyond the counter fallback's maximum gap (§6)
````

**E3** · `modules/vantage/docs/VANTAGE_Architecture.md` · replace the anchor with the new text.

Anchor:
````
| read-ahead | the recording is read this many steps beyond the instant being processed, so a sample or refSync logged later than the control that names it can be found |
````
New text:
````
| read-ahead | the recording is read up to the readiness limit, in steps, beyond the instant being processed, so a sample logged later than the control that names it can be found; a run's refSync is searched further, to its stage's next recorded `control` (`D27`) |
````

**E4** · `modules/vantage/docs/VANTAGE_Architecture.md` · replace the anchor with the new text.

Anchor:
````
   `measurement_counter` equals the control's. The sample whose
````
New text:
````
   `measurement_counter` equals the control's, never the first one after the control.
   It is searched in the arrived messages, then ahead, past the readiness limit, up to
   the stage's next recorded `control` (`D27`); a stage the recording holds no
   `control` of is searched to the readiness limit. Not found, the run takes the time
   rule (step 4). The sample whose
````

**E5** · `modules/vantage/docs/VANTAGE_Architecture.md` · replace the anchor with the new text.

Anchor:
````
4. **Time rule.** Only for a stage with no recorded refSync, or beyond the maximum
````
New text:
````
4. **Time rule.** Only for a run whose recorded refSync is not found (step 1), or beyond the maximum
````

**E6** · `modules/vantage/docs/VANTAGE_Architecture.md` · replace the anchor with the new text.

Anchor:
````
| the stage has no recorded refSync at all | `KIND_FALLBACK` on every input, every run, time rule used | per engine run |
````
New text:
````
| the run's recorded refSync is not found (step 1); for a stage with none at all, every run | `KIND_FALLBACK` on every input, time rule used | per engine run |
````

**E7** · `modules/vantage/docs/VANTAGE_Architecture.md` · replace the anchor with the new text.

Anchor:
````
| the read-ahead is the readiness limit, in steps; confirm on the first car recording |
````
New text:
````
| a sample is read ahead to the readiness limit, in steps; a run's refSync to its stage's next recorded `control`, matched by counter (`D27`); confirm on the first car recording |
````

**E8** · `modules/vantage/docs/VANTAGE_System_Requirements.md` · replace the anchor with the new text.

Anchor:
````
Priority split: 24 `P0`, 28 `P1`,
````
New text:
````
Priority split: 25 `P0`, 28 `P1`,
````

**E9** · `modules/vantage/docs/VANTAGE_System_Requirements.md` · insert one blank line, then the new text, directly after the line holding the anchor.

Anchor:
````
**Verify.** T · `SYT-ORC-12`   **Trace.** —
````
New text:
````
**`SYS-0053`** · `P0` · `R1` — Every run's control and outputs are recorded
**Shall.** An engine run shall write every run's `control` and outputs to its recording, none dropped or overwritten (`R-SIM-6`).
**Accept.** In every exact case and in `running_example` `all_simulated` with `buffer_depth` 1 on every port, each simulated stage's `compState` messages in the engine-run recording carry consecutive `cycle_counter`s and equal its controls in number.
**Binds.** `control`, `stageOut`, `runRecording`
**Verify.** T · `SYT-ORC-04`   **Trace.** —
````

**E10** · `modules/vantage/docs/VANTAGE_System_Requirements.md` · replace the anchor with the new text.

Anchor:
````
| T | 49 |
````
New text:
````
| T | 50 |
````

**E11** · `modules/vantage/docs/VANTAGE_Test_Spec.md` · replace the anchor with the new text.

Anchor:
````
**`SYT-ORC-02`** · T · fixture `F-CASE`, `F-ENGINE` —
````
New text:
````
**`SYT-ORC-02`** · T · fixture `F-CASE`, `F-SETUP-EDIT`, `F-ENGINE` —
````

**E12** · `modules/vantage/docs/VANTAGE_Test_Spec.md` · replace the anchor with the new text.

Anchor:
````
**Steps.** Run `loop_no_edge`; then `feedback` `all_simulated`.
````
New text:
````
**Steps.** Run `loop_no_edge`: the lab writes no run setup for a topology it refuses, so the test copies `feedback` `all_simulated`'s, drops `A`'s `previous_cycle` mark and points every library path at `loop_no_edge`'s build (the same stages, inputs and periods). Then run `feedback` `all_simulated`.
````

**E13** · `modules/vantage/docs/VANTAGE_Test_Spec.md` · replace the anchor with the new text.

Anchor:
````
**Serves.** `SYS-0012`
**Steps.** For every exact case count each simulated stage's controls in the engine-run recording and in the recording; on `data_triggered` `by_data`, count `T`'s controls and the `in_X` samples.
````
New text:
````
**Serves.** `SYS-0012`, `SYS-0053`
**Steps.** For every exact case count each simulated stage's controls in the engine-run recording and in the recording; on `data_triggered` `by_data`, count `T`'s controls and the `in_X` samples. In every exact case and in `running_example` `all_simulated` with `buffer_depth` 1 on every port, read each simulated stage's `compState` messages in the engine-run recording.
````

**E14** · `modules/vantage/docs/VANTAGE_Test_Spec.md` · insert the new text as new line(s) directly after the line holding the anchor.

Anchor:
````
- `.c2` **PASS:** `by_data`: one `T` control per `in_X` sample. **FAIL:** another count.
````
New text:
````
- `.c3` **PASS:** each stage's `compState` `cycle_counter`s are consecutive and as many as its controls, per `SYS-0053` Accept. **FAIL:** a gap, or another count.
````

**E15** · `modules/vantage/docs/VANTAGE_Test_Spec.md` · replace the anchor with the new text.

Anchor:
````
just after a `Q` control whose recorded refSync names a `P` sample logged after it;
````
New text:
````
just after a `Q` control whose recorded refSync names a `P` sample logged after it, keeping that run's own refSync (the car logs it after the control);
````

**E16** · `modules/vantage/docs/VANTAGE_Implementation_Design.md` · replace the anchor with the new text.

Anchor:
````
up to `readiness_limit_steps` steps past the instant processed; `Find` searches by `measurement_counter`;
````
New text:
````
up to `readiness_limit_steps` steps past the instant processed, and for a run's refSync to its stage's next recorded `control` (`D27`); `Find` searches by `measurement_counter`;
````

**E17** · `modules/vantage/docs/VANTAGE_Implementation_Design.md` · replace the anchor with the new text.

Anchor:
````
starts no run and adds one `stalled_trigger` entry; other bytes
````
New text:
````
starts no run and adds one `stalled_trigger` entry naming the stage and its own trigger port; other bytes
````

**E18** · `modules/vantage/docs/VANTAGE_Implementation_Design.md` · replace the whole line holding the anchor with the new text.

Anchor:
````
| `IMP-0044` |
````
New text:
````
| `[~]` | `IMP-0044` | `SYS-0001`, `SYS-0002`, `SYS-0003`, `SYS-0004`, `SYS-0005`, `SYS-0006`, `SYS-0007`, `SYS-0008`, `SYS-0046`, `SYS-0052` | `WP-09` | `NEW` | `tests/system/test_vnt_run_setup.py` — `SYT-RUN-01` to `SYT-RUN-09` and `SYT-RUN-11` (`SYT-RUN-10` is `IMP-0052`'s); `tests/support/engine_runs.py`, the engine and recording helpers it shares with `IMP-0045`. Closed by `SYT-RUN-06.c1` passing. | `SYT-RUN-01`, `SYT-RUN-02`, `SYT-RUN-03`, `SYT-RUN-04`, `SYT-RUN-05`, `SYT-RUN-06`, `SYT-RUN-07`, `SYT-RUN-08`, `SYT-RUN-09`, `SYT-RUN-11` |
````

**E19** · `modules/vantage/docs/VANTAGE_Implementation_Design.md` · replace the whole line holding the anchor with the new text.

Anchor:
````
| `IMP-0045` |
````
New text:
````
| `[~]` | `IMP-0045` | `SYS-0009`, `SYS-0010`, `SYS-0011`, `SYS-0012`, `SYS-0013`, `SYS-0014`, `SYS-0015`, `SYS-0016`, `SYS-0018`, `SYS-0019`, `SYS-0047`, `SYS-0050`, `SYS-0053` | `WP-09` | `NEW` | `tests/system/test_vnt_orchestrator.py` — `SYT-ORC-01` to `SYT-ORC-12`. Closed by `SYT-ORC-02.c1`, `SYT-ORC-03.c1`, `SYT-ORC-04.c3`, `SYT-ORC-06.c1`, `SYT-ORC-07.c3`, `SYT-ORC-11.c1` passing. | `SYT-ORC-01`, `SYT-ORC-02`, `SYT-ORC-03`, `SYT-ORC-04`, `SYT-ORC-05`, `SYT-ORC-06`, `SYT-ORC-07`, `SYT-ORC-08`, `SYT-ORC-09`, `SYT-ORC-10`, `SYT-ORC-11`, `SYT-ORC-12` |
````

**E20** · `modules/vantage/docs/VANTAGE_Implementation_Design.md` · insert the new text as new line(s) directly after the line holding the anchor.

Anchor:
````
| `IMP-0031` |
````
New text:
````
| `[ ]` | `IMP-0061` | `SYS-0014`, `SYS-0053` | `WP-05` | `EXTEND` | `src/simcore/runner/cycle_loop.cpp::Runner::WriteStep` — writes each run committed in the step, in commit order: its `control`, then each output it committed, from that run's own values, so a stage run twice in one step leaves both runs' messages; then the step's other recorded topics in topic order. | `SYT-ORC-04`, `SYT-ORC-06` |
````

**E21** · `modules/vantage/docs/VANTAGE_Implementation_Design.md` · replace the anchor with the new text.

Anchor:
````
Closed by `SYT-ORC-01`, `SYT-ORC-04`, `SYT-ORC-05`, `SYT-ORC-07`, `SYT-ORC-09`
````
New text:
````
Closed by `SYT-ORC-01`, `SYT-ORC-04`, `SYT-ORC-05`, `SYT-ORC-06`, `SYT-ORC-07`, `SYT-ORC-09`
````

## Part B — engine and tests
1. **Evicted sample** (`SYT-RUN-06.c1`; `RCT:IMP-0033`, `ARCH §6`'s table: "not in the recording,
   evicted, or never made" gives `KIND_FALLBACK`): in `select_inputs.cpp`, a named sample of a
   `simulate` producer that the buffer reports evicted goes to the counter fallback at once with
   `KIND_FALLBACK`; only a sample not yet committed makes the ticket wait. gtest: depth 1, the
   named sample evicted → fallback in that run, no park; not yet committed → still parks.
2. **Missing runs** (`IMP-0061`, `SYS-0053`; the owner: a defect to fix, not only explain). First,
   with step 1's fix held back, find where 13 of `B`'s 74 runs go in `SYT-RUN-06`'s depth-1 run,
   and state the cause in the report with the evidence (file, function, what you saw). Then fix
   `Runner::WriteStep` as `IMP-0061` says: each committed run, in commit order, its `control`,
   then each output it committed, from that run's own values. gtest: a stage that runs twice in
   one step leaves both runs' `control` and outputs in the recording, each `control` before its
   own outputs. If the cause is one `IMP-0061` does not describe, stop this item and report it
   with the cause. Do not change the live measurement; report what `MeasCycle` carries for a
   stage that ran twice in one step, and whether a post-mutation input topic of such a stage keeps
   both runs.
3. **`D27`** (`IMP-0026` as amended, `ARCH §6` step 1): a run's recorded refSync is matched by
   `measurement_counter` only, as `RecordedRefSync` does, and searched ahead past the readiness
   limit until the first recorded `control` of that stage with another `measurement_counter`, or
   the recording's end; a stage whose recording has no `<stage>.control` topic is searched to the
   readiness limit. Not found: the time rule with `KIND_FALLBACK` on every input (the existing
   path). Every other look-up (the named sample, the counter fallback) still reads ahead only to
   the readiness limit; the time rule never reads ahead. gtests, citing `D27`: (a) limit 0, a
   refSync logged three instants after its control is found and used; (b) the overrun, planted:
   run k's refSync logged after control k+1 → run k takes the time rule with `KIND_FALLBACK`, run
   k+1 takes its own refSync, run k never gets k+1's record; (c) no `control` topic → the search
   stops at the readiness limit.
4. **`stalled_trigger`** (`SYT-ORC-11.c1`, `IMP-0050` as amended): the entry's `port` is the
   stage's own trigger port (`in_X`). Correct the unit test that pins `port=source.in_x`
   (`tests/unit/test_orc_steps.cpp`) to the stage's port name, and name it.
5. **`SYT-ORC-03.c1`:** the load error for a `control` trigger the recording lacks names the topic
   as `T.control`, the spelling of recordings and run setups (`PortNameOfTopic`); the test requires
   exactly that and drops the `/T/control` alternative.
6. **`SYT-ORC-06.c1`:** the test checks `SYS-0014`'s Accept as written: per stage, the controls in
   trigger order, and each control followed by its own `out`, `refSync` and `compState` (same
   `measurement_counter`) before the next control. Step 2's fix makes the engine write it so.
7. **`SYT-ORC-02.c1`:** as the amended steps say — `feedback` `all_simulated`'s setup with `A`'s
   `previous_cycle` mark dropped and every library path pointing at `loop_no_edge`'s build
   (`modules/vantage-lab/conan_workarea/build-sil-vs2026/lab/loop_no_edge/`); a library missing
   there skips with a printed reason. Update the file docstring that names the old skip.
8. **`SYT-ORC-04.c3`:** as the amended steps say, in `test_vnt_orchestrator.py`.
9. `SYT-RUN-06.c1`, `SYT-ORC-07.c3` and `SYT-ORC-11.c1` run unchanged and must now pass. A case
   that still fails is a finding: leave it failing and report it with what was seen and your
   recommendation; never weaken it. No skip beyond step 7's, no tolerance, no `xfail`.

## Part C — builds, suites, boxes (once, at the end)
10. `modules\vantage`: `build.bat -t sil -p vs2026`, `-t gtest` (last 423/423), `-t package`;
    Python `tests/unit tests/system` (last 1263 passed, 3 failed, 86 skipped). Root:
    `py -3.12 scripts\check_invariants.py`;
    `py -3.12 .claude/templates/requirements/trace_check.py --set modules/vantage/docs --status`.
11. Report per new test file: cases passed / failed / skipped, each failure and skip with its id.
12. Boxes, only for rows whose cases all pass: `IMP-0044`, `IMP-0045`, `IMP-0061` to `[x]` (the
    first two lose their "Closed by" sentence); then every `[~]` row whose "Closed by" names only
    tests that now all pass goes to `[x]`, its "Closed by …" sentence removed (the orchestrator
    expects `IMP-0001`, `IMP-0007`, `IMP-0012`, `IMP-0050`, `IMP-0051`, and `WP-03` by the
    rollup); a row that names a test of `09b-2` or `09c` stays `[~]` unchanged. A row whose case
    still fails stays `[~]` naming it. `C-WPROLL` and `C-PLANMARK` clean. List every row you flip.

## Exit check (run all, report output and seconds)
- Each build command and suite: pass/fail, seconds, counts before and after; each corrected unit
  test by name.
- The cause of the missing runs (step 2), and the `MeasCycle` and post-mutation answers.
- Each new gtest by name and the row it serves.
- `check_invariants.py` clean; `trace_check` PASS and the `WP` lines.
- `git -C modules/vantage status --short`; `git diff --stat` equal with and without
  `--ignore-cr-at-eol`, in `modules/vantage` and at the root.

## Must not
- change any doc text beyond Part A and step 12's boxes and "Closed by" sentences, the contract
  (`modules/interfaces`), or anything under `modules/vantage-lab`
- write the `09b-2` or `09c` tests, touch the engine's manifest keys (a later package), or change
  the live measurement
- add a skip, tolerance or exemption no step names
- decide anything the rows leave open — report it with your recommendation

## Report back in this shape
1. Done / not done, in one line per part.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds (R-TEST-7).
4. Boxes ticked (row ids), and any `[~]` with what closes it.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
