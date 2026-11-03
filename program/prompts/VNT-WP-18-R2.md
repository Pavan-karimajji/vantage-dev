Your role: read .claude/agents/vantage-builder.md and follow it.
Keep the report under 30 lines, in the §4.2 shape.

# VNT-WP-18-R2 — gate G4: the supervised reader attaches before the run goes on (`SYT-SUP-07` is racy); then the full gate once (vantage `c2`, vantage-lab `main`)

The second rework of `VNT-WP-18`. R1's work is in the working copy, uncommitted: **build on it,
never revert it.** The orchestrator reran the five G4 files: 167 passed, **1 failed** —
`test_syt_sup_07_the_seal` (`SYT-SUP-07.c1`): exit 8 but `sealed_outcome=None`. Rerun alone, that
test and its neighbours failed 1 time in 5. Cause: `run_under_supervisor` starts
`lm_reader --until-finished` and the supervisor together; on `crash` the worker can die and be sealed
before the reader has mapped the name, and the seal removes the name. The test spec already says how
to make it deterministic: `F-SUPERVISED` runs **with `F-LM-HELD`'s attached reader** — the run is held
until the reader is attached.

## Context
- Working copy `C:\ws\repo\vantage-dev`, native Windows. Branches: vantage `c2`, vantage-lab `main`,
  interfaces `vantage` — stay on them. Never run `git checkout`, `git switch`, `git stash`,
  `git reset`, `git rm`, `git restore`, `git add`, `git commit`, `git push`, `pkill` or `kill`.
- Python: `modules\vantage\.venv-sim-win32\Scripts\python.exe`. Root scripts: `py -3.12`.
- Code: `modules/vantage-lab/src/lab_tools/supervise.py::run_under_supervisor`;
  `modules/vantage/tests/system/test_vnt_supervisor.py::_supervised`;
  `modules/vantage/tests/support/livemeas_runs.py` (`held_library`, `add_held_stage`);
  `tests/support/lm_reader.cpp` (`--until-finished` already prints `attached` when mapped).

## Steps
1. `run_under_supervisor` gains `gate_file: Path | None = None`. With a reader and a gate file: start
   the reader, start the supervisor (`Popen`), wait until the reader prints `attached` (bounded by the
   same budget it already uses), then create the gate file, then wait for both as today. Without a
   gate file, unchanged. The lab still imports nothing of Vantage. Extend the lab's
   `tests/unit/test_supervise.py` for the new argument (argument handling only).
2. `_supervised(..., reader=True)` (every caller that wants the sealed outcome) adds the held stage
   (`held_library` + `add_held_stage`, as `F-LM-HELD` does) with a gate file in the run's folder, and
   passes that gate file. `reader=False` callers are unchanged.
3. No other change: no retry, no sleep, no longer timeout, no change to a pass criterion.

## Exit check (run all, report output and seconds)
4. `test_vnt_supervisor.py` **five times in a row**: each run 0 failed.
5. The five G4 files once: `test_vnt_gate_g4.py`, `test_vnt_lms.py`, `test_vnt_live_measurement.py`,
   `test_vnt_inspector.py`, `test_vnt_supervisor.py` — 0 failed, 0 skipped. **G4 green: yes / no.**
6. The full gate once: `build.bat -t sil -p vs2026`, `-t gtest -p vs2026` (gtest count), Python
   `tests/unit tests/system` (passed / failed / skipped, and that no skip is in a G4 file), the
   vantage-lab unit tests, `py -3.12 scripts\check_invariants.py`, both `trace_check --status`
   (expected vantage 17 done / 1 started of 18, 122 / 1 / 1 of 124, lab 67/67; RCT 10 / 3 / 0 of 13).
7. `git diff --stat` in vantage, vantage-lab and interfaces, each equal with and without
   `--ignore-cr-at-eol`.

## Must not
- change any doc or box; change engine, inspector or supervisor code
- add a skip, retry, sleep, longer timeout or `xfail`
- commit or push

## Report back in this shape
1. Done / not done; G4 green: yes / no.
2. Files changed, one line each.
3. Exit check output: each command, pass/fail, seconds — the five supervisor runs on one line each.
4. Deviations, each with the reason.
5. Open questions, each with your recommendation.
