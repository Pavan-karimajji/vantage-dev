# LAB-WP-07 — the other topologies, one file each

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`. Never reset, clean, stash, checkout or
  commit anything. Other workers may edit other files; touch only the allowed ones.
- `modules/vantage/docs/VANTAGE_Lab_Design.md` (frozen): §3 (loader checks, `trigger`,
  `previous_cycle`, the `refused_at_load` exemption), §5.2 (input-triggered starts),
  §5.3 (`previous_cycle` picking), §6.1 (the topology table, resim case keys, `expect`),
  §9 rows of package `LAB-WP-07`: `LAB-41`..`LAB-48`
- `modules/interfaces/docs/resim_contract/RCT_Test_Spec.md`: `SYT-RSY-04`, `SYT-CTL-04`
  (for `data_triggered`; it passes only on Vantage — make the recording, do not test it here)
- What exists: generator, car (input-triggered starts implemented, untested), recorder,
  `setup_writer.py`, `compare.py`, `reference.py`, `tests/test_catalogue.py` (runs
  `SYT-RSY-04` on every catalogue file present) — from LAB-WP-02..06

## Goal
The eight catalogue files of §6.1 after `running_example` exist, each with a `base` scenario
whose resim cases make its corner case; each builds, the car records it byte-identically per
seed, and `SYT-RSY-04` passes on every resim case of every file except `loop_no_edge`, which
the loader accepts only with `expect: refused_at_load`.

## Allowed changes
- In `modules/vantage-lab`: `catalogue/fan_out.yaml`, `diamond.yaml`, `rates_not_multiple.yaml`,
  `feedback.yaml`, `measured_middle.yaml`, `late_consumer.yaml`, `data_triggered.yaml`,
  `loop_no_edge.yaml` (rows `LAB-41`..`LAB-48`); their calibration entries in
  `catalogue/provisional.yaml`; tests for input-triggered starts and `previous_cycle` in a new
  `tests/test_car_topologies.py`; `tests/test_catalogue.py` only to make it skip
  `refused_at_load` files with a printed reason and assert the loader's refusal instead.
- Boxes in `modules/vantage/docs/VANTAGE_Lab_Design.md`: `LAB-41`..`LAB-48`, `LAB-WP-07`, only
  after their checks pass. RCT boxes only for rows whose every listed test now passes.
- Everything else is read-only. If a file needs a car, generator or loader change, stop and
  report it with the failing output.

## Steps
1. One file per row, numbers exactly as §6.1's table gives them; `seed` and `duration_ms`
   chosen so each corner case actually happens in the run (say how you checked).
2. `late_consumer`: show in a test that `Q`'s control is logged before `P`'s sample and `Q`
   reads it (rule 6); `feedback`: `A` reads `B`'s previous-cycle output; `data_triggered`: `T`'s
   runs follow `in_X` samples one to one; `rates_not_multiple`: no common grid needed.
3. `measured_middle`: its resim case marks `M` measured and `A`, `B` simulated.
4. `loop_no_edge`: `expect: refused_at_load`; without that word the loader refuses it.
5. Tick only what passed.

## Exit check (run all, report output and seconds)
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev\modules\vantage-lab && py -3.12 scripts\build.py -P base -t sil -p vs2026"` → builds every topology's libraries; list library counts per topology.
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev\modules\vantage-lab && python -m pytest tests -q"` → all pass; list each topology's `SYT-RSY-04` cases.
- `python3 .claude/templates/requirements/trace_check.py --set modules/interfaces/docs/resim_contract` → PASS.
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev && python scripts\check_invariants.py"` → clean.

## Must not
- commit, push, or change files outside "Allowed changes"
- add a scenario verb or a topology key the design does not have
- weaken a test so it passes

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked (row ids) and any `[~]` with its `closed by` condition.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
