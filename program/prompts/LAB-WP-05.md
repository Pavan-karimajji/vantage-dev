# LAB-WP-05 — running example scenarios: restart, fault, calibration

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`. Never reset, clean, stash, checkout or
  commit anything. Other workers may edit other files; touch only the allowed ones.
- `modules/vantage/docs/VANTAGE_Lab_Design.md` (frozen): §5.3 (control table), §5.5 (verbs
  `restart`, `silent`, `invalid`), §6.2 (scenarios `restart` and `fault`, their worked
  numbers), §6.3 (`F-LAB-RESTART`, `F-LAB-FAULT`, `F-LAB-CAL`), §7, §9 rows of package
  `LAB-WP-05`: `LAB-31`..`LAB-35`
- `modules/interfaces/docs/resim_contract/RCT_Test_Spec.md`: `SYT-CTL-07`, `SYT-CST-01`..
  `SYT-CST-05` (cases, PASS and FAIL sides); `RCT_System_Requirements.md` for the `Accept`
  clauses they cite (cite by UID, R-REQ-4)
- `modules/interfaces/docs/resim_contract/RCT_Implementation_Design.md` rows `IMP-0030`
  (scripted restart) and every row whose `Tests` include the tests above
- `.claude/rules/requirements.md` R-REQ-4, R-REQ-5, R-REQ-9; `testing.md`; `style.md`
- What exists: the car and recorder (`LAB-WP-04`), the harness (`LAB-WP-03`), the generator,
  `catalogue/running_example.yaml` (`base`), `catalogue/provisional.yaml`

## Goal
The car honours `car.restart`, `car.silent` and `car.invalid`; scenarios `restart` and `fault`
are in the running example file exactly as §6.2 gives them; `bundle_variant` makes a
calibration variant of a built bundle (`F-LAB-CAL`); and `SYT-CTL-07`, `SYT-CST-01`..`05`
pass on the lab.

## Allowed changes
- In `modules/vantage-lab`: the files of rows `LAB-31`..`LAB-35` (`src/lab_tools/car.py`
  `ControlWriter` and `SourceTask` changes, `catalogue/running_example.yaml` scenarios,
  `src/lab_tools/bundles.py`, `tests/test_car_scenarios.py`).
- Boxes in `modules/vantage/docs/VANTAGE_Lab_Design.md`: `LAB-31`..`LAB-35`, `LAB-WP-05`,
  only after their checks pass. Boxes in `RCT_Implementation_Design.md` for rows whose every
  listed test now passes (and the package rollup the checker then demands); nothing else there.
- Everything else is read-only. If a test fails because of the template, generator,
  harness or interfaces, stop and report the failing case with its output.

## Steps
1. `LAB-31` scripted restart from `car.restart` (the text of `RCT:IMP-0030`).
2. `LAB-32` `silent` and `invalid` windows at the source (§5.5: a silent source's counter
   does not advance).
3. `LAB-33` the two scenarios, verbatim from §6.2.
4. `LAB-34` `bundle_variant`: copy a bundle, set or remove keys, repack with a new
   `bundle.sha256`; the copy never touches the build tree's own bundle.
5. `LAB-35` tests: one pytest test per case, id in the name (R-REQ-9); read the first run of
   each window and the recovery, not run counts (§6.2: jitter makes counts ±1).
6. Tick only what passed.

## Exit check (run all, report output and seconds)
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev\modules\vantage-lab && python -m pytest tests -q"` → all pass; list each `SYT` case with pass/fail.
- The `fault` run: the first ERROR run of `B` (time, reason), the first RUNNING run after
  recovery (time), and the number of trusted runs between them.
- `python3 .claude/templates/requirements/trace_check.py --set modules/interfaces/docs/resim_contract` and `--status` → PASS; report which rows moved.
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev && python scripts\check_invariants.py"` → clean.

## Must not
- commit, push, or change files outside "Allowed changes"
- add a scenario verb beyond the three this package needs
- weaken a test so it passes

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked (row ids) and any `[~]` with its `closed by` condition.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
