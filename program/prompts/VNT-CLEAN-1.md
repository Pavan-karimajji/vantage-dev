Your role: read .claude/agents/vantage-builder.md and follow it.
Keep the report under 50 lines, in the §4.2 shape.

# VNT-CLEAN-1 — the contract's control tests on Vantage (closing `RCT:WP-06`..`08`), `control_arrivals` bounded, a cut recording fails instead of passing, the supervisor tests faster (vantage `c2`, after the G4 merge)

The clean-up package after gate G4: four items the ledger carried, one prompt. **Relay only after
the owner's `c2` → `main` merge at G4** — this work lands on `c2` on top of it. Five parts, in
order: **A** the contract's control and refSync tests on Vantage; **B** `control_arrivals`; **C**
recording read problems; **D** the supervisor test file's speed; **E** gate and boxes.

## Context (read these, nothing else unless a step needs it)
- Working copy `C:\ws\repo\vantage-dev`, native Windows (`vs2026`). `modules/vantage` on **`c2`**,
  `modules/interfaces` on **`vantage`**, `modules/vantage-lab` on **`main`** — stay on them. Never run
  `git checkout`, `git switch`, `git stash`, `git reset`, `git rm`, `git restore`, `git add`,
  `git commit`, `git push`, `pkill` or `kill`.
- **Owner conditions for `c2`:** every commit builds the whole of vantage and passes its full unit
  suite; a test of old behaviour that can no longer pass is corrected in the same change and named.
- Rules: `.claude/rules/style.md`, `testing.md`, `requirements.md` R-REQ-4/5/9.
- Python: `modules\vantage\.venv-sim-win32\Scripts\python.exe`. Root scripts: `py -3.12`.
- Read: `VANTAGE_DEV_PLAN.md` `D17 (1)`, `D27`, `D28 (4)`, `D29 (3)`;
  `modules/interfaces/docs/resim_contract/RCT_Test_Spec.md` §2 (`SYT-CTL-01`..`07`), §3
  (`SYT-RSY-04`) and its fixtures `F-LAB`, `F-LAB-JUMP`, `F-LAB-RESTART`, `F-LAB-FAULT`,
  `F-CATALOGUE`; `RCT_Implementation_Design.md` rows `IMP-0023`, `IMP-0030`, `IMP-0032`, `IMP-0033`
  and packages `WP-06`..`WP-08`; `modules/vantage-lab/catalogue/running_example.yaml` (scenarios
  `base`, `restart`, `fault`; cases `cut_c`, `jump`), `data_triggered.yaml` (`by_control`,
  `by_data`).
- **Facts the orchestrator established** (read the code before relying on them):
  - *No Vantage test names the contract's control tests.* `RCT:SYT-CTL-03`..`07` and `RCT:SYT-RSY-04`
    appear in no file under `modules/vantage/tests` (only a comment in `tests/unit/test_orc_control.cpp`).
    `SYT-CTL-02` is the lab's (`vantage-lab/tests/harness/test_contract_harness.py`). So `RCT:IMP-0023`
    (`WP-06`, needs `SYT-CTL-02` and `-03`), `IMP-0030` (`WP-07`), `IMP-0032`, `IMP-0033` (`WP-08`)
    are open, and RCT shows 10 of 13 packages done.
  - *`control_arrivals`* (`src/simcore/runner/cycle_loop.cpp` `Impl::control_arrivals`, appended in
    `StepOnce` ~line 1012, trimmed only in `PrepareTicket` ~line 707 when a dispatched run's counter
    matches, cleared by `Seek`); `select_inputs.cpp::NextControlNs` scans the whole deque per refSync
    lookup. A clock-started stage whose recording holds its controls never matches, so its list grows
    for the whole recording (ledger, `WP-13` owner check).
  - *Read problems are dropped.* `src/simcore/io/codecs/mcap.cpp`: `on_problem_` is
    `[](const mcap::Status&) {}` (~line 414), passed to `readMessages`. A recording cut mid-message
    near its end is read to its last whole message and the engine run **passes** (the `WP-18` report);
    one cut at 30 % is refused at load (summary fallback scan).
  - *Supervisor tests.* `tests/system/test_vnt_supervisor.py::_supervised` defaults to `reader=True`,
    which since `WP-18-R2` adds the held stage to every case that takes the default: the file went
    from ≈69 s to ≈123 s. Only the cases that read `sealed_outcome` need it (`SYT-SUP-07`).
  - *Last counts* (G4 commit `9e9234b`): gtest all pass; Python `tests/unit tests/system` 1740
    passed, 0 failed, 62 skipped; the five G4 files 168 passed; vantage-lab unit tests 41.

## Part A — the contract's control and refSync tests on Vantage
1. New `tests/system/test_vnt_rct_control.py`: `RCT:SYT-CTL-03`, `-04`, `-05`, `-06`, `-07` and
   `RCT:SYT-RSY-04` on Vantage, each case id verbatim (`RCT:SYT-CTL-06.c2`), citing the RCT Accept,
   asserting the FAIL side, on the engine-run recording (`tests/support/engine_runs.py`):
   - `F-LAB-JUMP` = `running_example` `base` `jump`; `F-LAB` = `base` `cut_c`;
     `F-LAB-RESTART` = `restart` `replay`; `F-LAB-FAULT` = `fault` `replay` against `base` with the same
     setup; `F-CATALOGUE` = every topology's exact cases.
   - `SYT-CTL-04.c1` with recorded controls, `.c2` with data triggers (`data_triggered` `by_data`, or a
     case whose setup triggers by data; say which).
   - `SYT-RSY-04`: for each topology, every simulated component's outputs equal the recording's from
     its first RUN run (`F-COMPARE`, the G3 comparator), naming topology, component and run on failure.
2. **These test C1 behaviour.** A case that fails is reported with what was seen; **no engine
   change** in this package. A fixture the lab cannot make: report it with what is missing.
3. Run the lab's `SYT-CTL-02` (`vantage-lab/tests/harness/test_contract_harness.py`) and report it.

## Part B — `control_arrivals` bounded
4. Keep per stage only what a waiting run can still need: drop arrivals older than the oldest run
   still pending for that stage (or, with none pending, all but the newest), and find a run's own
   control by counter without scanning the whole list (an index from counter to position, or a
   search from the front that stops at the first match — say which). Behaviour unchanged: every
   existing `IMP_0065` gtest and `test_vnt_selection.py`, `test_vnt_orchestrator.py` pass as they are.
5. gtest citing `IMP-0065`: a clock-triggered stage whose recording holds its controls — after a
   whole recording the list holds at most a small fixed number of entries (state the bound you
   assert); and a refSync lookup still finds the next control as before.

## Part C — a recording read problem ends the engine run
6. `on_problem_` keeps the first problem; the reader's next read returns
   `Result::Fail(Error{Kind::Input, …})` naming the file and the problem, so the engine run ends with
   exit 5 (`kSimExitInput`) and the live measurement closes `fail`. A recording that reads cleanly is
   unchanged. If `AllowFallbackScan` at open hides a problem the read then meets, the read still
   fails.
7. Tests: a gtest on the reader (a copy cut mid-message near its end → the read fails with
   `Kind::Input`); a system test (`cut_c` on such a copy through `simengine` → exit 5, error naming the
   file). Any existing test that relied on a cut recording passing: correct it and name it.

## Part D — supervisor tests only hold where they need to
8. `_supervised`'s default becomes `reader=False`; pass `reader=True` only where a case reads
   `sealed_outcome` or needs the attached reader. No pass criterion changes. Report the file's
   seconds before and after.

## Part E — gate and boxes (once, at the end)
9. `build.bat -t sil -p vs2026`, `-t gtest -p vs2026`; gtest; Python `tests/unit tests/system`
   (counts and the skip list); the five G4 files (still 168 passed, none skipped); vantage-lab unit
   tests; `py -3.12 scripts\check_invariants.py`.
10. **Only if every Part A case and `SYT-CTL-02` pass**, in
    `modules/interfaces/docs/resim_contract/RCT_Implementation_Design.md`: `IMP-0023` `[ ]` → `[x]`;
    `IMP-0030`, `IMP-0032`, `IMP-0033` `[~]` → `[x]`, deleting each row's closing sentence (from
    ` Closed by` through its final `.`, with the one space before it); package lines `WP-06`, `WP-07`,
    `WP-08` `- [~]` → `- [x]`, deleting from ` Closed by` (or ` Blocked`) only the closing sentence;
    nothing else. Then `py -3.12 .claude/templates/requirements/trace_check.py --set
    modules/interfaces/docs/resim_contract --status` → PASS, expected `packages: 13 done, 0 started,
    0 open, of 13`. A case that failed leaves its rows as they are; list them.
11. `py -3.12 .claude/templates/requirements/trace_check.py --set modules/vantage/docs --status`
    (unchanged: 17 done / 1 started). `git diff --stat` in vantage and interfaces, each equal with and
    without `--ignore-cr-at-eol`.

## Exit check (run all, report output and seconds)
- Steps 9–11 with counts and seconds; each new test by name; each corrected test with its reason.

## Must not
- change C1 behaviour beyond Part B's bounded list and Part C's read failure; change a requirement,
  an Accept or a pass criterion; touch `bridge.py` or `--config`/`--timeout-ms` (8c)
- change any doc text but step 10's boxes
- add a skip, tolerance, retry or `xfail`
- commit or push

## Report back in this shape
1. Done / not done, in one line per part.
2. Files changed, one line each.
3. Exit check output: each command, pass/fail, seconds (R-TEST-7).
4. Boxes ticked, and any row left with what closes it.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
