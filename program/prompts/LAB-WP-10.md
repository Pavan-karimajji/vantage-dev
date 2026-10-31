# LAB-WP-10 — lab cases for C1: coprime periods, a renumbering component, a repeated trigger

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`. Never commit, and never run `git checkout`,
  `git switch`, `git stash`, `git reset`, `pkill` or `kill`. Another worker builds C1 in
  `modules/vantage` (branch `c1`) now; of that folder you may touch only the lab design's boxes.
- `modules/vantage/docs/VANTAGE_Lab_Design.md` §5.5, §6.1, §6.2, §7, §9 rows `LAB-57`..`LAB-63`
  (`LAB-WP-10`) — what this lands; `VANTAGE_DEV_PLAN.md` D20 (amended: eight recording verbs)
- `modules/vantage/docs/VANTAGE_Test_Spec.md` fixtures `F-RENUMBER-LIB` and the cases
  `SYT-ORC-05`, `SYT-ORC-11` use (read only)
- The lab: `catalogue/`, `template/lab_sil.cpp.in`, `template/lab_component.hpp.in`,
  `src/lab_tools/recorder.py`, `generate.py`, the lab's tests

## Goal
The seven rows of `LAB-WP-10` are built and each case is shown to happen; plus one fix left by
decision 3: a malformed `LAB_<C>_START_COUNT` is reported as malformed, not "missing".

## Allowed changes
- `modules/vantage-lab`: the files the seven rows name, their tests, and `template/lab_sil.cpp.in`'s
  `LAB_<C>_START_COUNT` error message.
- `modules/vantage/docs/VANTAGE_Lab_Design.md`: the boxes of `LAB-57`..`LAB-63` and `LAB-WP-10` only.
- Everything else is read-only.

## Steps
1. Build the rows as written: `coprime_periods` (7/11/13 ms, `cut_a`, `all_simulated`) and its
   provisional values; `LAB_<C>_RENUMBER` (absent = 0; data outputs' `measurement_counter` shifted
   modulo 2³²; `refSync` and `compState` keep the control's); `renumber_lib` / `shifted` with
   `LAB_A_RENUMBER: 1`; the recording verb `repeat_sample` (byte-identical, 1 ms after, stated in
   `manifest`); `repeat_trigger` / `by_data`.
2. Show each case happens, in a test that cites its row: the coprime case runs every stage on its
   own period with no common divisor; `shifted`'s `A` outputs carry the control counter + 1 while
   `refSync`/`compState` carry the control's; `repeat_trigger`'s recording holds the repeated
   `source.X` sample twice, byte-identical. A planted case each where the row allows one.
3. The `START_COUNT` message: a present but malformed value names the key and says malformed.
4. Real lab build (vs2026, the standard build) and the lab's whole suite; tick the boxes whose
   tests pass.

## Exit check (run all, report output and seconds)
- The lab build; the lab suite on Windows Python (counts, seconds).
- `python3 .claude/templates/requirements/trace_check.py --set modules/vantage/docs --status` →
  PASS, `LAB-WP-10` as the boxes say.
- `git -C modules/vantage-lab status --short`; `git -C modules/vantage status --short` (list only;
  other files are the C1 worker's).

## Must not
- commit, push, or change files outside "Allowed changes"
- add a verb, key or option beyond the rows

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked (row ids).
5. Deviations, each with the reason.
6. Open questions, each with your recommendation.
