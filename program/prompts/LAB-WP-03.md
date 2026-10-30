# LAB-WP-03 — ABI loader and contract harness: six contract tests pass on a lab library

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`. Never reset, clean, stash, checkout or
  commit anything. Other workers may edit other files; touch only the allowed ones.
- `modules/vantage/docs/VANTAGE_Lab_Design.md` (frozen): §2 (harness row), §4.3
  (`index.json`), §6.3 row `F-HARN`, §6.4, §8 (ABI loader, harness, tests), §9 rows of
  package `LAB-WP-03`: `LAB-19`..`LAB-22`
- `modules/interfaces/docs/resim_contract/RCT_Test_Spec.md`: `SYT-HDR-03`, `SYT-CTL-01`,
  `SYT-CTL-02`, `SYT-RSY-02`, `SYT-RSY-03`, `SYT-CST-06` (their cases `.cN`, PASS and FAIL
  sides) and the fixture catalogue; `RCT_System_Requirements.md` rows they cite (read the
  `Accept` clauses; never restate them in a test, cite by UID, R-REQ-4)
- `modules/interfaces/docs/resim_contract/RCT_Implementation_Design.md`: `IMP-0013`..
  `IMP-0015`, `IMP-0042`, `IMP-0022`..`IMP-0028` (their `Tests` column; which close here)
- `modules/interfaces/include/adas/adas_sil_abi.h` (the generic ABI the loader binds)
- `.claude/rules/requirements.md` R-REQ-4, R-REQ-5, R-REQ-9; `testing.md`; `style.md`
- What LAB-WP-02 built: the running example's libraries and `index.json` in the lab's
  sil build tree; `src/lab_tools/` (topology, generator)

## Goal
`LabLibrary` loads any lab library through `ctypes` and the generic ABI, `MessageFactory`
builds message classes from the library's own descriptor set (no generated Python
bindings, R-SIM-11), and `tests/harness/test_contract_harness.py` passes the six tests
above against the running example's `B` (and `A` where one input is enough), each test id
in its test name and each case `.cN` its own test.

## Allowed changes
- In `modules/vantage-lab`: the files of rows `LAB-19`..`LAB-22` (and `tests/harness/__init__.py`
  or a `conftest.py` if pytest needs one there).
- Boxes in `modules/vantage/docs/VANTAGE_Lab_Design.md`: `LAB-19`..`LAB-22` and `LAB-WP-03`,
  only after their checks pass.
- Boxes in `modules/interfaces/docs/resim_contract/RCT_Implementation_Design.md`: a row whose
  every listed test now passes on a lab library may go `[x]`; a row with only some of its
  tests passing stays `[~]` with its existing `closed by` text. Change nothing else there.
- Everything else is read-only (no change to the template, generator or interfaces code;
  if a test fails because of them, stop and report the failing case with its output).

## Steps
1. `LAB-19` `abi.py`: `LabLibrary.load(path)`, `manifest()`, `init(config_dir)`, `exec(port_set)`,
   `shutdown()`; `AdasPort`/`AdasPortSet` mirror `adas_sil_abi.h` exactly. Paths come from
   `index.json`, never guessed.
2. `LAB-20` `messages.py`: `MessageFactory` from the manifest's `FileDescriptorSet`.
3. `LAB-21` `lab_harness.py::LabHarness` — scripted `CycleControl`s (counter, time, op mode),
   hand-made `LabSample`s (sticker, counter, time, value), withheld inputs; one call to
   `exec` per control; returns every output decoded. A fresh process per run for
   `SYT-CTL-02` (subprocess), as `F-HARN` says.
4. `LAB-22` the six tests, one pytest test per case, named `test_SYT_<AREA>_<nn>_c<N>_...`
   so the id is greppable (R-REQ-9), each citing the `SYS` UID it serves in its docstring.
5. Tick only what passed (see Allowed changes).

## Exit check (run all, report output and seconds)
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev\modules\vantage-lab && python -m pytest tests\harness tests\unit -q"` → all pass; list each `SYT` case with pass/fail.
- `grep -rn "SYT-HDR-03\|SYT-CTL-01\|SYT-CTL-02\|SYT-RSY-02\|SYT-RSY-03\|SYT-CST-06\|SYT_HDR_03\|SYT_CTL_01\|SYT_CTL_02\|SYT_RSY_02\|SYT_RSY_03\|SYT_CST_06" modules/vantage-lab/tests/harness | wc -l` → at least one hit per id.
- `python3 .claude/templates/requirements/trace_check.py --set modules/interfaces/docs/resim_contract` and `--status` → PASS; report which rows moved.
- `git -C modules/vantage-lab status --short`; `git -C modules/interfaces status --short` → list.

## Must not
- commit, push, or change files outside "Allowed changes"
- weaken a test so it passes; a case that cannot fail is not a case (R-REQ-5)
- import generated protobuf bindings or `adas_sim`

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked (row ids) and any `[~]` with its `closed by` condition.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
