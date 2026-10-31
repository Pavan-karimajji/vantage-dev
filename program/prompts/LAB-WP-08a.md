# LAB-WP-08 (part 1) — camera, drill verbs, recording edits and drill scenarios

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`. Never reset, clean, stash, checkout or
  commit anything. Other workers may edit other files; touch only the allowed ones.
- `modules/vantage/docs/VANTAGE_Lab_Design.md` (frozen): §5.4 (image sources, `big_frame`),
  §5.5 (verbs `renumber`, `counter_jump`, `drop_sample`, `drop_ref_sync`; why faults are made
  at the source), §6.1 (`camera`), §6.2 (the drill table and `expect`), §6.3 (`F-CAM`), §7
  (`fallback_max_gap`, `MeasBulk` geometry), §9 rows `LAB-49`..`LAB-52` of package `LAB-WP-08`
- `modules/vantage/docs/VANTAGE_Architecture.md` §12 (what the lab must give Vantage: the drills)
- `modules/interfaces/docs/resim_contract/RCT_Test_Spec.md` for `SYT-*` ids these rows serve
  (`RCT:SYS-0001`, `RCT:SYS-0029`, `RCT:SYS-0031`, `RCT:SYS-0016`) — most pass only on Vantage;
  here the lab makes the recordings and shows each drill's effect is in the recording
- What exists: car (`parse_car_script` refuses unbuilt verbs), recorder, reference re-run,
  `tests/test_catalogue.py`, catalogue files from LAB-WP-02..07

## Goal
`LAB-49`..`LAB-52` are built: the `camera` topology records `adas.lab.LabImage` frames
(one `big_frame`); `renumber` and `counter_jump` and the recording edits `drop_sample` and
`drop_ref_sync` exist; the drill scenarios and the `hang`/`crash` cases of §6.2 are in the
running example file. `LAB-53` (supervised run) is **not** in this part: it needs Vantage's
`simengine --supervise`, which does not exist yet.

## Allowed changes
- In `modules/vantage-lab`: the files of rows `LAB-49`..`LAB-52` (`catalogue/camera.yaml`,
  `src/lab_tools/car.py` image `SourceTask` with `big_frame`, `renumber`, `counter_jump`,
  `src/lab_tools/recorder.py::apply_recording_edits`, the drill scenarios and cases in
  `catalogue/running_example.yaml`), their entries in `catalogue/provisional.yaml`, a new
  `tests/test_car_drills.py`, and `tests/test_catalogue.py` / `tests/unit/test_topology.py`
  only where a new scenario or `expect: diverges` needs the existing tests to read it (say
  each change).
- Boxes in `modules/vantage/docs/VANTAGE_Lab_Design.md`: `LAB-49`..`LAB-52` only after their
  checks pass. **`LAB-WP-08` stays `[~]`, closed by `LAB-53`** (write that `closed by` text if
  the checker needs one). RCT boxes only for rows whose every listed test now passes.
- Everything else is read-only.

## Steps
1. `LAB-49` image source and `camera.yaml` (64 x 48, 50 ms; `pixels[i] = (counter + i) mod 256`;
   one `big_frame`).
2. `LAB-50` `renumber` (a component's outputs carry its own run count as
   `measurement_counter`) and `counter_jump`.
3. `LAB-51` `apply_recording_edits`: `drop_sample`, `drop_ref_sync: all` — applied when the
   recording is written; the bus still had the sample.
4. `LAB-52` the drill scenarios of §6.2 and the `hang`/`crash` cases (`config:` sets
   `LAB_B_HANG_AFTER_RUNS` / `LAB_B_CRASH_AFTER_RUNS` = 5 in a bundle variant).
5. Tests, one per drill: the effect is in the recording (the dropped samples are absent and a
   `refSync` still names them; no `refSync` topic; `A`'s outputs renumbered; the counter jump;
   the big frame's size); the reference re-run's result per §6.2's *Expected* column where the
   lab can judge it (`no_ref_sync` counts mismatches; `missing_sample` within
   `fallback_max_gap`); `hang`/`crash` only prove the bundle variant carries the key (running
   them needs the supervisor, `LAB-53`).

## Exit check (run all, report output and seconds)
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev\modules\vantage-lab && py -3.12 scripts\build.py -P base -t sil -p vs2026"` → builds; list topologies.
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev\modules\vantage-lab && python -m pytest tests -q"` → all pass; list each drill test.
- `python3 .claude/templates/requirements/trace_check.py --set modules/interfaces/docs/resim_contract` → PASS.
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev && python scripts\check_invariants.py"` → clean.

## Must not
- commit, push, or change files outside "Allowed changes"
- build `LAB-53` or call any Vantage binary
- add a verb beyond the four this part needs; weaken a test so it passes

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked (row ids) and any `[~]` with its `closed by` condition.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
