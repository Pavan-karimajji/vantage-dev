Your role: read .claude/agents/vantage-builder.md and follow it.
Keep the report under 40 lines, in the §4.2 shape.

# VNT-WP-09b-1 — C1: the system tests of the run setup and the orchestrator (`IMP-0044`, `IMP-0045`, vantage `c1`)

`09b` writes the system test files of `WP-09` (`IMP-0044`..`IMP-0048`) and is split in two
sessions: **09b-1** (this) — `SYT-RUN-01`..`11` and `SYT-ORC-01`..`12`; **09b-2** — `SEL`, `STP`,
`THR`, `EQO-02`..`04`. Gate G3 (`IMP-0043`) is `09c`.

## Context (read these, nothing else unless a step needs it)
- Working copy `C:\ws\repo\vantage-dev`, native Windows (`vs2026`). `modules/vantage` is on
  branch **`c1`** — stay on it. Never run `git checkout`, `git switch`, `git stash`, `git reset`,
  `git rm`, `git restore`, `git add`, `git commit`, `git push`, `pkill` or `kill`.
- **Owner conditions for `c1`:** every commit builds the whole of vantage and passes its full unit
  suite; a test of the old path that can no longer pass is removed or corrected in the same
  change, and you name it.
- Rules: `.claude/rules/style.md` (file header on every new file, minimal diffs), `testing.md`,
  `requirements.md` R-REQ-4 (a test cites an `Accept` by UID, never restates it), R-REQ-5 (a case
  passes or fails, its FAIL side as written), R-REQ-9 (the test id and case id appear verbatim in
  the test implementing it).
- Python: vantage's own environment, `modules\vantage\.venv-sim-win32\Scripts\python.exe`; the
  lab's, `modules\vantage-lab\.venv-lab-win32\Scripts\python.exe`. Never `py -3`. Root scripts:
  `py -3.12`.
- Read: `modules/vantage/docs/VANTAGE_Test_Spec.md` — the fixture catalogue, §2 `RUN` and §3 `ORC`
  whole, §9; `VANTAGE_Implementation_Design.md` rows `IMP-0044`, `IMP-0045` (**build exactly
  these**) and `IMP-0040`..`IMP-0042`, `IMP-0055` (the support you use); the `Accept` of each
  `SYS` row a test serves (`VANTAGE_System_Requirements.md`); `VANTAGE_Lab_Design.md` §6 (the lab
  cases). Support already built: `tests/support/lab_cases.py` (`lab_case`, `edit_setup`,
  `edit_recording`), `tests/support/step_tap.cpp`, `tests/fixtures/exec_probe/`,
  `tests/support/control_tick.cpp`, `tests/support/recordings.py`; `F-COMPARE` is the lab's
  `lab_tools.compare.equal_outputs`.
- **The lab is built but only partly generated:** `modules/vantage-lab/lab/` holds `running_example`
  (`base`, `counter_wrap`), `diamond` and `fan_out` only, while the libraries of all 11 catalogue
  topologies are built (`conan_workarea/build-sil-vs2026/lab/`). Lab outputs are gitignored and
  made per machine by the lab's own verbs.

## Steps
1. **Generate the lab outputs** (no lab source change): for every topology in
   `modules/vantage-lab/catalogue/` except `provisional.yaml`, in the lab's environment, from
   `modules\vantage-lab`: `python -m lab_tools car <topology>` (every scenario) then
   `python -m lab_tools setup <topology>`. A topology the lab refuses by design (a loop with no
   previous-cycle edge, a rate that is not a multiple) is reported with the lab's message, not
   worked around. Report per topology: scenarios recorded, setups written, seconds.
2. `IMP-0044`: `tests/system/test_vnt_run_setup.py` — `SYT-RUN-01` to `SYT-RUN-11`, one test per
   case `.cN`, each naming its test and case id verbatim (`SYT-RUN-05.c2`), its assertion message
   naming the FAIL side the spec states. `SYT-RUN-11` reads the `config_bundle` block through the
   C++ reader the way `tests/system/test_vnt_wp13_recordings.py` does.
3. `IMP-0045`: `tests/system/test_vnt_orchestrator.py` — `SYT-ORC-01` to `SYT-ORC-12`, the same way.
4. **A skip is only for a lab output that is missing after step 1, or a case that needs the
   supervisor (`hang`, `crash`, part 8b)**, with a printed reason naming what is missing. Never
   `xfail`, never a weakened or dropped assertion, never a tolerance the spec does not give.
5. **A failing case is a finding, not yours to hide.** If the engine is wrong and the fix lies
   inside an existing design row's text (name the row), make it with a unit test and say so. If
   the fix needs a decision a row does not state, or the spec itself is wrong, leave the case
   failing, stop working on it, and report it with file, case, what was seen and your
   recommendation.
6. `tests/support/foreign_mcap.py` (owner's condition): replace its docstring's first line
   ```
   """`ForeignMcapWriter`: test data for the READ side only -- `.mcap` files shaped the way the retired
   ```
   with
   ```
   """Legacy shapes for reader tests only: never copy this into `src/`, where `ANL-06` forbids a second writer.

   `ForeignMcapWriter`: test data for the READ side only -- `.mcap` files shaped the way the retired
   ```
7. Builds and suites, once, at the end: `build.bat -t sil -p vs2026`, `-t gtest` (last 423/423),
   `-t package` in `modules\vantage`; Python `tests/unit tests/system` (last 1170 passed, 85
   skipped); `py -3.12 scripts\check_invariants.py` at the root;
   `py -3.12 .claude/templates/requirements/trace_check.py --set modules/vantage/docs --status`.
8. Boxes: `IMP-0044` and `IMP-0045` `[x]` when every case of their file passes (no skip), else
   `[~]` with "Closed by `<the failing or skipped case ids>` passing." added at the row's end
   before the test column. **Then every other `[~]` row whose "Closed by" names only tests that now
   all pass** goes to `[x]`, its "Closed by …" sentence removed; a row that still names a test of
   `09b-2` or `09c` stays `[~]` unchanged. Package boxes as the rollup gives (`C-WPROLL`,
   `C-PLANMARK` clean). List every row you flip.

## Exit check (run all, report output and seconds)
- Step 1's table; each build command and suite: pass/fail, seconds, counts before and after.
- Per new test file: cases passed / failed / skipped, each failure and skip with its case id and
  reason.
- Each engine fix of step 5 with its row and unit test.
- `check_invariants.py` clean; `trace_check` PASS and the `WP` lines.
- `git -C modules/vantage status --short`; `git diff --stat` equal with and without
  `--ignore-cr-at-eol`.

## Must not
- change any doc text beyond step 8's boxes and "Closed by" sentences, the contract
  (`modules/interfaces`), or anything under `modules/vantage-lab` except the generated, gitignored
  `lab/` outputs of step 1
- write the `09b-2` or `09c` tests, or touch the engine's manifest keys (a later package)
- add a skip, tolerance or exemption no step names
- decide anything the rows leave open — report it with your recommendation

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds (R-TEST-7).
4. Boxes ticked (row ids), and any `[~]` with what closes it.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
