# LAB-WP-06 — run setups, provisional values and the reference re-run (closes G2 without Vantage)

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`. Never reset, clean, stash, checkout or
  commit anything. Other workers may edit other files; touch only the allowed ones.
- `VANTAGE_DEV_PLAN.md` §5 (gate G2)
- `modules/vantage/docs/VANTAGE_Lab_Design.md` (frozen): §6.1 (resim case keys), §6.3
  (`F-LM`), §6.4 (the reference re-run and which tests the lab passes alone), §7 (the
  run-setup provisional values), §8, §9 rows of package `LAB-WP-06`: `LAB-36`..`LAB-40`
- `modules/vantage/docs/VANTAGE_Architecture.md` §2.3 (the run setup keys — the only keys a
  run setup may carry; `sampling` and `on_missing` are refused, D18 (4))
- `modules/interfaces/docs/resim_contract/RCT_System_Requirements.md` preamble (*equal
  outputs*, D16) and `RCT_Test_Spec.md` `SYT-RSY-04` (cases, PASS and FAIL sides)
- `modules/interfaces/docs/resim_contract/RCT_Implementation_Design.md` rows whose `Tests`
  include `SYT-RSY-04` (`IMP-0027`, `IMP-0031`, and others)
- What exists: generator (its own reader of `catalogue/provisional.yaml`'s calibration part,
  in `generate.py`), car, recorder, harness, `abi.py`, `messages.py`, scenarios `base`,
  `restart`, `fault` (after LAB-WP-05)

## Goal
For every resim case of the running example the lab writes one run setup JSON carrying only
`ARCH §2.3`'s keys and the provisional values (marked provisional); `equal_outputs` and
`ReferenceResim` re-run the lab libraries on a car recording by its refSyncs for any cut and
order and find equal outputs; with `use_ref_sync=False` mismatches are counted; and
`SYT-RSY-04` passes on every catalogue file present, closing `G2` without Vantage.

## Allowed changes
- In `modules/vantage-lab`: the files of rows `LAB-36`..`LAB-40` (`src/lab_tools/setup_writer.py`,
  `catalogue/provisional.yaml` run-setup part, `src/lab_tools/compare.py`,
  `src/lab_tools/reference.py`, `tests/test_catalogue.py`), and the `setup` and `reference`
  verbs in `src/lab_tools/__main__.py`.
- **`load_provisional` must reuse the generator's reader** of `provisional.yaml` (move it to
  `setup_writer.py` and import it from `generate.py`, or import the existing one): one file,
  one reader. Editing `generate.py` is allowed for that move only.
- Boxes in `modules/vantage/docs/VANTAGE_Lab_Design.md`: `LAB-36`..`LAB-40`, `LAB-WP-06`,
  only after their checks pass. Boxes in `RCT_Implementation_Design.md` for rows whose every
  listed test now passes (and the package rollups the checker then demands); nothing else.
- Everything else is read-only.

## Steps
1. `LAB-37` the run-setup values of §7 in `provisional.yaml`, each `status: provisional`;
   `load_provisional` (one reader, above).
2. `LAB-36` `write_run_setup`: one JSON per resim case, keys of `ARCH §2.3` only; refuses a
   case naming an unknown stage; `outputs.livemeas.name` per §7.
3. `LAB-38` `equal_outputs` per the RCT preamble (same message count, byte-identical once each
   header's `cycle_counter` is 0).
4. `LAB-39` `ReferenceResim`: for any cut (`measured` stages) and any run order, hands each
   simulated component the samples its recorded `refSync` names, calls it once per recorded
   control, compares with `equal_outputs`; `use_ref_sync=False` picks the newest sample not
   after the trigger time and counts mismatches (never asserts zero).
5. `LAB-40` `tests/test_catalogue.py`: `SYT-RSY-04` on every catalogue file and every resim
   case present (`base`: `cut_c`, `all_simulated`; `restart`; `fault`; skip `jump` with a
   printed reason: a jump is a Vantage host call), each case `.cN` its own test, id in the
   name, plus a planted violation (a mutated recorded sample must break equality).
6. Tick only what passed. State in your report whether every test of §6.4's first group now
   passes on the lab (that is gate G2).

## Exit check (run all, report output and seconds)
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev\modules\vantage-lab && python -m pytest tests -q"` → all pass; list each `SYT-RSY-04` case and the `use_ref_sync=False` mismatch counts.
- One written run setup (`base`/`cut_c`) printed in full.
- `python3 .claude/templates/requirements/trace_check.py --set modules/interfaces/docs/resim_contract` and `--status` → PASS; report which rows moved.
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev && python scripts\check_invariants.py"` → clean.

## Must not
- commit, push, or change files outside "Allowed changes"
- import `adas_sim` or any Vantage code: the reference re-run is the independent check
- write a run-setup key not in `ARCH §2.3`, or a final value where §7 says provisional
- weaken a test so it passes

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked (row ids) and any `[~]` with its `closed by` condition.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
