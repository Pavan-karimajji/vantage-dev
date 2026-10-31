# LAB-WP-06 rework 1 — the reference re-run feeds simulated outputs downstream

## Context
- Your LAB-WP-06 work in `modules/vantage-lab` (`src/lab_tools/reference.py`,
  `tests/test_catalogue.py`), lab design §6.4 and `ARCH §5` (the six rules: refSync picking,
  readiness waiting in event order).

## Finding
`ReferenceResim` hands every component the **recorded** sample its refSync names, even when
the producer is simulated. A cut then changes only which components are checked, and the
run order cannot matter, so `any_cut_gives_equal_outputs` and
`any_run_order_gives_equal_outputs` cannot fail (R-REQ-5: a case that cannot fail is not a case).

## Goal
In a re-run, an input whose producer is **simulated** is fed from the outputs that producer
has produced **in this re-run**, matched by the `measurement_counter` its recorded refSync
names; an input whose producer is measured or a source is fed from the recording. A run whose
refSync names a simulated sample not produced yet **waits** (in event order, never wall time)
until it is; if nothing can make progress, that is a reported failure naming the component,
run and missing sample — never a silent fallback. `use_ref_sync=False` keeps its meaning
(newest sample not after the trigger time, from the same live-or-recorded source), and still
counts mismatches.

## Allowed changes
- `modules/vantage-lab/src/lab_tools/reference.py`, `tests/test_catalogue.py`, and
  `modules/vantage-lab/.gitignore` (add `lab/`, the verbs' default output folder).
- Everything else is read-only; boxes stay as they are if the tests still pass.

## Steps
1. Change the feed and add readiness waiting as above. `order` and `interleave` then decide
   only which runnable run goes first; equal outputs must hold for every order.
2. Tests: keep the cut and order tests and add two planted violations that only a live feed
   can catch — (a) a simulated producer whose reproduced output is mutated in the re-run
   (for example a `config` case that changes one of `A`'s keys, or a hook in the test) makes
   its consumer `B` differ too; (b) removing a simulated producer's needed run makes its
   consumer report the missing sample rather than pass.
3. Report the `use_ref_sync=False` counts again (they may change).

## Exit check (run all, report output and seconds)
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev\modules\vantage-lab && python -m pytest tests -q"` → all pass.
- `python3 .claude/templates/requirements/trace_check.py --set modules/interfaces/docs/resim_contract` → PASS.
- `git -C modules/vantage-lab status --short` → list.

## Must not
- commit, push, or change files outside "Allowed changes"; import Vantage code
- weaken a test so it passes

## Report back in this shape
1. Done / not done. 2. Files changed. 3. Exit check output with seconds. 4. Boxes.
5. Deviations. 6. Open questions.
