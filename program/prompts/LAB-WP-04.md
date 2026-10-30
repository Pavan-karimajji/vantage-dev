# LAB-WP-04 — fake car on the running example: sources, scheduler, recorder

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`. Never reset, clean, stash, checkout or
  commit anything. Other workers may edit other files; touch only the allowed ones.
- `modules/vantage/docs/VANTAGE_Lab_Design.md` (frozen): §1, §5 (all of it: why Python, the
  task clock, one component start, sources, scenarios, the recorder), §6.1 (running
  example), §6.3 (`F-LAB`), §8, §9 rows of package `LAB-WP-04`: `LAB-23`..`LAB-30`
- `modules/interfaces/docs/resim_contract/RCT_Test_Spec.md`: `SYT-HDR-01`, `SYT-HDR-02`,
  `SYT-HDR-04`, `SYT-CTL-05`, `SYT-RSY-01` (cases, PASS and FAIL sides) and fixture `F-LAB`;
  `RCT_System_Requirements.md` for the `Accept` clauses they cite (cite by UID, R-REQ-4)
- `modules/interfaces/docs/resim_contract/RCT_Implementation_Design.md` rows `IMP-0029`..
  `IMP-0031` (what the car lands) and their `Tests`
- `.claude/rules/sim.md` R-SIM-6, R-SIM-11, R-SIM-12; `requirements.md` R-REQ-4, R-REQ-5,
  R-REQ-9; `testing.md`; `style.md` (`COMPONENT: VANTAGE_LAB`)
- What exists: `src/lab_tools/topology.py`, `generate.py`, `abi.py`, `messages.py`,
  `tests/harness/` (LAB-WP-02/03), the running example's libraries and `index.json`

## Goal
`python -m lab_tools car --topology catalogue/running_example.yaml --scenario base --out <f>`
(or the verb shape §8 gives) runs the running example for its `duration_ms` and writes one
`.mcap` per §5.6; two runs with the same seed give byte-identical files; the five contract
tests above pass on that recording.

## Allowed changes
- In `modules/vantage-lab`: the files of rows `LAB-23`..`LAB-30` (`src/lab_tools/car.py`,
  `recorder.py`, the `car` verb in `src/lab_tools/__main__.py`, `tests/test_car_running_example.py`).
  `pyproject.toml` only if a dependency is missing (report it).
- Boxes in `modules/vantage/docs/VANTAGE_Lab_Design.md`: `LAB-23`..`LAB-30`, `LAB-WP-04`,
  only after their checks pass. Boxes in `RCT_Implementation_Design.md` for `IMP-0029`..
  `IMP-0031` and any earlier `[~]` row whose every listed test now passes; nothing else there.
- Everything else is read-only (template, generator, harness, interfaces). If a test fails
  because of them, stop and report the failing case with its output.

## Steps
1. `LAB-23` `Task`: nominal tick, jitter drawn per §5.2 with `random.Random("<seed>/<name>")`,
   integer µs throughout.
2. `LAB-24` `SourceTask`; `LAB-25` `Bus`; `LAB-26` `Car.run` with the event order of §5.2
   (samples, activations, starts; declaration order within a class; input-triggered
   starts right after their sample); `LAB-27` `ControlWriter`/`Car.startComponent` (§5.3
   control table; never reads `compState`); `LAB-28` input picking, one `adasExec`, every
   output written.
3. `LAB-29` `McapRecorder` per §5.6: topics, schemas from the manifests, `log_time` in ns,
   metadata with no wall-clock time, deterministic channel numbers.
4. `LAB-30` tests, one pytest test per case, test id in the name (R-REQ-9), plus the
   byte-identical double run. Only scenario `base` exists; `car.restart` and the other verbs
   are `LAB-WP-05`/`08` (read the keys only as far as `base` needs: none).
5. Tick only what passed.

## Exit check (run all, report output and seconds)
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev\modules\vantage-lab && python -m pytest tests -q"` → all pass; list each `SYT` case with pass/fail and the double-run result.
- One car run's summary: number of messages per topic class (source, control, data out, refSync, compState) and the file size.
- `grep -rn "adas_sim\|_pb2" modules/vantage-lab/src` → no output.
- `python3 .claude/templates/requirements/trace_check.py --set modules/interfaces/docs/resim_contract` and `--status` → PASS; report which rows moved.
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev && python scripts\check_invariants.py"` → clean.

## Must not
- commit, push, or change files outside "Allowed changes"
- read a wall clock, use unseeded randomness, or let file or dict order decide event order
- import `adas_sim` or generated protobuf bindings
- weaken a test so it passes

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked (row ids) and any `[~]` with its `closed by` condition.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
