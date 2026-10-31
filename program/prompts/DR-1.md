# DR-1 — design rows follow what the lab build found (no contract change)

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`. Never reset, clean, stash, checkout or
  commit anything. Touch only the allowed files; no other worker edits them now.
- `VANTAGE_DEV_PLAN.md` §2 D14 (a design-row edit is not a contract change), D20
- `.claude/rules/requirements.md` R-REQ-3, R-REQ-4, R-REQ-6a, R-REQ-14
- `modules/vantage/docs/VANTAGE_Lab_Design.md` §4.3, §5.5, §8, §9 (rows `LAB-03`, `LAB-04`,
  `LAB-06`)
- `modules/interfaces/docs/resim_contract/RCT_Implementation_Design.md` rows `IMP-0028`,
  `IMP-0030`, the `WP-07` package line; `RCT_Test_Spec.md` `SYT-CST-02`
- What the build shows (read, do not change): `modules/vantage-lab/` — the copied files
  `sync_copy_files.py` places (`build.bat`, `build.sh`, `gui.bat`, `setup.bat`,
  `scripts/build.py`, `scripts/build_gui.py`, `scripts/setup.py`, `.clang-format`),
  `CMakePresets.json`, `requirements.lock`, `tests/unit/`; `src/lab_tools/car.py`
  `SourceTask` (windows cut on the sample's nominal time); `tests/test_car_scenarios.py`
  (how `SYT-CST-02.c2` picks the first run in the INVALID window)

## Goal
Each document says what the built lab is, once: no row promises a file list the build
contradicts, and the two contract-side texts the lab tests rely on are exact.

## Allowed changes
- `modules/vantage/docs/VANTAGE_Lab_Design.md`: the rows and sentences named below; boxes
  unchanged.
- `modules/interfaces/docs/resim_contract/RCT_Implementation_Design.md`: `IMP-0028` and
  `IMP-0030` Artifact cells, `IMP-0030`'s box, and the `WP-07` line only if the checker
  then demands it.
- `modules/interfaces/docs/resim_contract/RCT_Test_Spec.md`: the Steps of `SYT-CST-02` only.
- Everything else is read-only.

## Steps
1. Lab design `LAB-03` (and the §4.3 and §8 copied-machinery entries): the eight files the
   sync tool places, from `modules/toolchain/copy_files/` only.
2. `LAB-04` names `CMakePresets.json` (the standard build runs `cmake --preset`); `LAB-06`
   names `requirements.lock` (made by `scripts/lock_python_env.py`, never by hand). §8's
   *Tests* line adds `tests/unit/` (loader, generator, library smoke tests). No new row.
3. §5.5: one sentence — the `silent` and `invalid` windows are half-open `[from, from+for)`
   on a sample's nominal (source) time, so jitter never moves a sample across an edge.
4. `RCT:IMP-0028`: "fills the template from a component's description file" becomes "fills
   the template from a component's description in its topology file" (`Q-L5`, D20).
5. `RCT:IMP-0030`: tighten the Artifact cell, keeping every obligation, so that with the
   box `[~]` and the sentence `Closed by SYT-CTL-04 and SYT-CTL-06 passing on Vantage (WP-08).`
   it stays within the 60-word cap; set the box `[~]` (its `SYT-CTL-05` and `SYT-CTL-07` pass
   on the lab).
6. `SYT-CST-02` Steps: one sentence defining the first run in the INVALID window as the first
   run of the consumer whose `refSync` entry for the faulted input carries sticker 2 (the
   consumer reads the newest sample at its start, so a time cut would be off by jitter).
   Cases and their PASS/FAIL sides unchanged.

## Exit check (run all, report output and seconds)
- `python3 .claude/templates/requirements/trace_check.py --set modules/interfaces/docs/resim_contract` and `--status` → PASS; report `IMP-0030`'s state.
- `grep -n "description file" modules/interfaces/docs/resim_contract/RCT_Implementation_Design.md` → none.
- `grep -n "LAB-03\` \|LAB-04\` \|LAB-06\` " modules/vantage/docs/VANTAGE_Lab_Design.md` → the new texts.
- `git -C modules/interfaces diff --stat`; `git -C modules/vantage diff --stat` → only the allowed files.

## Must not
- commit, push, or change files outside "Allowed changes"
- change any SYS row, message, field, layout item, test case or its PASS/FAIL sides (D14)
- change any other box

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked (row ids) and any `[~]` with its `closed by` condition.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
