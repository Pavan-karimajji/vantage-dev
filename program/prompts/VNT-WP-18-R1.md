Your role: read .claude/agents/vantage-builder.md and follow it.
Keep the report under 40 lines, in the §4.2 shape.

# VNT-WP-18-R1 — gate G4: a simulated stage's `control` shows only the controls its runs got; a real mid-run failure for `SYT-LMW-12`; then the last boxes (vantage `c2`)

The rework of `VNT-WP-18`. Its work is in the working copy, uncommitted, in `modules/vantage`,
`modules/vantage-lab` and `modules/interfaces`: **build on it, never revert it.** Two cases failed,
and both are decided here:

1. **`SYT-INS-09.c2` / strict `checkRuns` on `late_consumer` `all_simulated`.** At a step where
   `Q`'s *recorded* control arrives but `Q`'s run is deferred to the next step, the live measurement
   shows that recorded control on `Q.control` with age 0, so `checkRuns` counts a run with no fresh
   `refSync`/`compState`. The defect is in the step report, not in the check: the function never got
   that message — its run, one step later, gets the control the engine writes (its own
   `cycle_counter`, sticker OK, `D17 (1)`). `R-SIM-26`: *what the function gets is what viz shows*.
   **Decided:** a simulated stage's `control`, `refSync` and output ports show only what its runs
   wrote, one value per run in run order, and between runs the last of them held with its age; a
   recorded arrival on one of those ports is never shown. Before the stage's first run the port is
   absent. `checkRuns` stays strict. Measured stages are unchanged.
2. **`SYT-LMW-12.c1`.** A recording cut mid-message is read to its last whole message and the run
   passes, so it cannot make `fail`. **Decided:** the failure is a component call returning an error
   (`Component::Exec` fails on a non-success return, `component.cpp`): `held_probe` gains
   `PROBE_FAIL_AT_CALL: n`, and `SYT-LMW-12` runs `cut_c` with it set to 3. (Silent truncation of a
   cut recording is noted for the clean-up package; do not change the reader.)

Four parts, in order: **A** five doc edits, exactly; **B** the two code changes and their tests;
**C** the runs; **D** the last boxes.

## Context (read these, nothing else unless a step needs it)
- Working copy `C:\ws\repo\vantage-dev`, native Windows (`vs2026`). `modules/vantage` on **`c2`**,
  `modules/vantage-lab` on **`main`**, `modules/interfaces` on **`vantage`** — stay on them. Never run
  `git checkout`, `git switch`, `git stash`, `git reset`, `git rm`, `git restore`, `git add`,
  `git commit`, `git push`, `pkill` or `kill`.
- Python: `modules\vantage\.venv-sim-win32\Scripts\python.exe`. Root scripts: `py -3.12`.
- Read: `program/prompts/VNT-WP-18.md` (its Part F and its Must-not list still hold);
  `src/simcore/runner/cycle_loop.cpp` `Runner::StepOnce`'s report builder (`per_run_ports`,
  `held_writes`, the sets `WP-16-17` moved into `SetLiveMeasurement`); `tests/fixtures/held_probe`.

## Part A — doc edits (exact)
All LF. Replace each anchor once; if one is not found exactly once, stop and report it. The
orchestrator dry-ran A1–A5 on a copy of the working tree with Part D's final boxes: `trace_check`
PASS, 229 requirements, 102 tests, `packages: 17 done, 1 started, 0 open, of 18`, `design rows: 122
done, 1 started, 1 open, of 124`.

**A1** · `modules/vantage/docs/VANTAGE_System_Requirements.md` · replace the anchor text with the new text.

Anchor:
````
**Accept.** On `running_example` `cut_c`, on a copy of its recording cut mid-message, and on `hang`
````
New:
````
**Accept.** On `running_example` `cut_c`, on it with `held_probe` failing its third call, and on `hang`
````

**A2** · `modules/vantage/docs/VANTAGE_Test_Spec.md` · replace the anchor text with the new text.

Anchor:
````
**`SYT-LMW-12`** · T · fixture `F-LM-HELD`, `F-REC-EDIT`, `F-SETUP-EDIT`, `F-INSPECT` — The worker's own outcomes
````
New:
````
**`SYT-LMW-12`** · T · fixture `F-LM-HELD`, `F-SETUP-EDIT`, `F-INSPECT` — The worker's own outcomes
````

**A3** · `modules/vantage/docs/VANTAGE_Test_Spec.md` · replace the anchor text with the new text.

Anchor:
````
**Steps.** Run `running_example` `cut_c`; run it on a copy of its recording cut mid-message; run `hang`
````
New:
````
**Steps.** Run `running_example` `cut_c`; run it with `held_probe`'s `PROBE_FAIL_AT_CALL: 3`; run `hang`
````

**A4** · `modules/vantage/docs/VANTAGE_Implementation_Design.md` · replace the anchor text with the new text.

Anchor:
````
its first call returns only once the file its bundle key `PROBE_GATE_FILE` names exists.
````
New:
````
its first call returns only once the file its bundle key `PROBE_GATE_FILE` names exists; `PROBE_FAIL_AT_CALL: n` makes call n return an error.
````

**A5** · `modules/vantage/docs/VANTAGE_Implementation_Design.md` · replace the anchor text with the new text.

Anchor:
````
`src/simcore/runner/cycle_loop.cpp::Runner::StepOnce` — builds the `StepReport`: every declared port's newest sample with `age_ns` (simulation time since arrival), and each run's `control`, `refSync`, outputs and overridden inputs in run order; origin is the recording's tag, `simulated` or `overridden`; every badge with a count above 0.
````
New:
````
`src/simcore/runner/cycle_loop.cpp::Runner::StepOnce` — builds the `StepReport`: every declared port's newest sample with `age_ns`; a simulated stage's `control`, `refSync` and outputs only as its runs wrote them, in run order, held between runs, never a recorded arrival (`R-SIM-26`); each run's overridden inputs; origin the recording's tag, `simulated` or `overridden`; every badge above 0.
````

## Part B — the two changes
1. **Step report** (`IMP-0080`, after A5). For each port that is a simulated stage's `control`,
   `refSync` or output (compute the set once, with the bulk and overridden sets): this step's runs'
   writes in run order; else the engine's last write to it, held, with `age_ns` from that write's
   time, origin `simulated`; else absent. Never the bus sample there. Every other port as today.
   gtest citing `IMP-0080`: a stage whose recorded control arrives one step before its run (readiness
   held, as in `late_consumer`) has no `control` value at the arrival step and one fresh value at the
   run's step, equal to the control the engine handed the run.
2. **`held_probe`** (`IMP-0088`, after A4): `PROBE_FAIL_AT_CALL: n` (optional bundle key) makes the
   n-th `adasExec` call return an error status; absent, nothing changes. `SYT-LMW-12` per A3 (drop its
   use of a cut recording).

## Part C — the runs (once, at the end)
3. The five G4 files on their own: `tests/system/test_vnt_gate_g4.py`, `test_vnt_lms.py`,
   `test_vnt_live_measurement.py`, `test_vnt_inspector.py`, `test_vnt_supervisor.py` — expected no
   failure and **no skip** (G4 green). If a case still fails: stop, report it with what was seen; no
   change to C1 behaviour, a requirement, an Accept or a pass criterion beyond A1–A5.
4. `build.bat -t sil -p vs2026`, `-t gtest -p vs2026`; gtest (last 478/478, plus your new one);
   Python `tests/unit tests/system` (last 1738 passed, 2 failed, 62 skipped; expected 0 failed, the
   same 62 skips, none in a G4 file); vantage-lab unit tests; `py -3.12 scripts\check_invariants.py`.

## Part D — the last boxes (only if step 3 is green)
5. `modules/vantage/docs/VANTAGE_Implementation_Design.md`: `IMP-0071`, `IMP-0074`, `IMP-0083`,
   `IMP-0098` `[~]` → `[x]`, deleting ` Closed by `WP-18`.` with its leading space; `IMP-0120`,
   `IMP-0121` `[ ]` → `[x]`; package lines `WP-14`, `WP-15`, `WP-16` `- [~]` → `- [x]`, deleting
   ` Closed by its rows' tests passing (`WP-18`).`; `WP-18` `- [~]` → `- [x]`, deleting ` Closed by
   `SYT-LMW-12` and `SYT-INS-09` passing.`. `IMP-0080` and `IMP-0088` stay `[x]`. `WP-17`,
   `IMP-0103`, `IMP-0112` unchanged.
6. `py -3.12 .claude/templates/requirements/trace_check.py --set modules/vantage/docs --status` and
   `--set modules/interfaces/docs/resim_contract --status`. Expected: vantage as in Part A's note,
   `VANTAGE_Lab_Design.md` 67/67; RCT PASS, `packages: 10 done, 3 started, 0 open, of 13`.
7. `git diff --stat` in vantage, vantage-lab and interfaces, each equal with and without
   `--ignore-cr-at-eol`.

## Exit check (run all, report output and seconds)
- Steps 3, 4, 6 and 7, with counts and seconds; **G4 green: yes / no** on its own line.

## Must not
- change any doc text beyond A1–A5 and Part D's boxes
- change C1 behaviour (orchestrator, selection, step, equal outputs), the recording reader, a
  requirement or a pass criterion beyond A1–A5; relax `checkRuns`
- add a skip, tolerance, retry or `xfail`
- commit or push

## Report back in this shape
1. Done / not done, in one line per part; G4 green: yes / no.
2. Files changed, one line each.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
