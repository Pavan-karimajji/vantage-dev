Your role: read .claude/agents/vantage-builder.md and follow it.
Keep the report under 60 lines, in the §4.2 shape.

# VNT-WP-18 — the C2 system tests and gate G4; the lab's supervised run (`LAB-53`); the boxes of `WP-14`..`WP-18`, `RCT:WP-02`/`03`/`09`/`10` and `LAB-WP-08` (vantage `c2`, vantage-lab `main`)

The last C2 package. It writes the test tools of `WP-18` (`IMP-0114`..`IMP-0118`), the system tests
of the live measurement, the inspector and the supervisor (`SYT-LMW-01`..`16`, `SYT-INS-01`..`12`,
`SYT-SUP-01`..`15`), the contract's `RCT:SYT-LMS-01`..`09` on Vantage, and the gate file of **G4**
(`VANTAGE_Test_Spec.md` §1a). It also writes the lab's last row, `LAB-53`
(`lab_tools/supervise.py`), and closes the boxes when everything passes. Six parts, in order:
**A** two doc edits, exactly; **B** three fixes from the orchestrator's review of `WP-16-17`; **C**
the test tools and `LAB-53`; **D** the system tests and G4; **E** builds and suites; **F** boxes.

Not here: `IMP-0112` and dropping `--config`/`--timeout-ms` (8c; `WP-17` stays `[~]`), `RCT:WP-08`
and `RCT:IMP-0023` (the clean-up package).

## Context (read these, nothing else unless a step needs it)
- Working copy `C:\ws\repo\vantage-dev`, native Windows (`vs2026`). `modules/vantage` on branch
  **`c2`** (`59484f5`), `modules/vantage-lab` on **`main`**, `modules/interfaces` on **`vantage`** —
  stay on them. Never run `git checkout`, `git switch`, `git stash`, `git reset`, `git rm`,
  `git restore`, `git add`, `git commit`, `git push`, `pkill` or `kill` (a test may end a process it
  started, by pid, through the platform API).
- **Owner conditions for `c2`:** every commit builds the whole of vantage and passes its full unit
  suite; a test of old behaviour that can no longer pass is corrected in the same change and named.
- Rules: `.claude/rules/style.md`, `testing.md`, `requirements.md` R-REQ-4/5/9 (test id and case id
  verbatim in each test; the FAIL side asserted), `rules/sim.md` (both override notes).
- Python: `modules\vantage\.venv-sim-win32\Scripts\python.exe`. Never `py -3`. Root scripts:
  `py -3.12`.
- Read: `VANTAGE_DEV_PLAN.md` `D29 (4)`, `D30`, `D31`; `VANTAGE_Architecture.md` §9, §10;
  `VANTAGE_System_Requirements.md` §7–§9; `VANTAGE_Test_Spec.md` the fixture catalogue, §1a, §8,
  §9, §10, `ANL-04`..`06`; `VANTAGE_Implementation_Design.md` rows `IMP-0114`..`IMP-0123`;
  `VANTAGE_Lab_Design.md` §6.2, §6.3, `LAB-53`; `modules/interfaces/docs/resim_contract/RCT_Test_Spec.md`
  `SYT-LMS-01`..`09` and the fixtures `F-LM`, `F-LM-TWICE`, `F-LM-STRESS`, `F-CAM`, `F-WRITER`.
- **Facts the orchestrator established** (read the code before relying on them):
  - *Every lab setup already names a live measurement*: `lab_tools/setup_writer.py` writes
    `outputs.livemeas` (`livemeas_name(topology, scenario, case)`, geometry from
    `catalogue/provisional.yaml`: 8 cycle slots of 16384 bytes, 4 bulk slots of 8192); a case may
    override `livemeas` keys. So every G3 run opens one; `F-LM-HELD` needs a ring that holds the
    whole run (take the step count from `F-TAP` on the same setup).
  - *Helpers to reuse*: `tests/support/engine_runs.py` (`run_case`, `run_tap`, `tap_case`,
    `compare_recordings`, `exact_cases`, `catalogue`, `case_change`, `point_at_recording`,
    `stage_of`, `port_of`, a skip with a printed reason when a tool or the lab is missing) and the
    recording-edit helper `test_vnt_producer_keys.py` uses (`F-REC-EDIT`).
  - *What C2 built*: `vantage-inspect` (`attach`, `dump [--description] [--follow]`,
    `check [--recording]`, exits 0/1/2/6), `simengine --supervise --attempt-timeout-ms N
    [--restart-on-crash N]` (exit 0, the worker's own code, 6, 7, 8; `<run_setup>.attempts.jsonl`;
    `reproducers/` beside the setup), `tests/fixtures/held_probe` (`PROBE_GATE_FILE`), the writer API
    in `include/vantage/livemeas_writer.h` (a test tool may link `livemeas`), `SharedRegion` in
    `src/livemeas/`. On POSIX the name is removed at close and at seal; on Windows it lives while a
    handle is open — so **a reader attaches before the end** (`D31 (5)`): every live-measurement test
    runs on `F-LM-HELD`, or keeps a reader attached from before the end.
  - *Lab cases*: `running_example` `base` `hang` and `crash` (`LAB_B_HANG_AFTER_RUNS: 5`,
    `LAB_B_CRASH_AFTER_RUNS: 5` — `B` is the stage), `cut_c`, `all_simulated`, `jump`;
    `missing_sample`; the `camera` topology (`bulk: [source.Cam]`; the oversize case leaves `bulk`
    empty and has `big_frame` 65536 bytes at counter 20).
  - *Last counts* (`WP-16-17`): gtest 478/478; Python `tests/unit tests/system` 1572 passed,
    0 failed, 62 skipped; `check_invariants` clean.

## Part A — doc edits (exact)
`modules/vantage/docs/VANTAGE_Implementation_Design.md` (LF). Replace each anchor once; if one is
not found exactly once, stop and report it. The orchestrator dry-ran both with Part F's final box
state in all three sets: every `trace_check` PASS.

**A1** — `IMP-0124` names where the stage byte is set (the `WP-16-17` report: the engine's call path
is `Runner::ExecTicket`, not `RunStage`).

Anchor:
````
`RunStage` sets its stage's byte before `Component::Exec` and clears it after
````
New:
````
`Runner::ExecTicket` sets its stage's byte before `Component::Exec` and clears it after
````

**A2** — `IMP-0114` gains the reader mode `LAB-53` needs (step 7).

Anchor:
````
`F-READER`: `--stall`, `--kill-after N`, `--layout-version V`, `--write-byte`, on the layout header alone.
````
New:
````
`F-READER`: `--stall`, `--kill-after N`, `--layout-version V`, `--write-byte`, `--until-finished` (attaches once the name appears, prints the final outcome), on the layout header alone.
````

## Part B — three fixes (from the review of `WP-16-17`)
1. **`checkRuns` is strict** (`IMP-0097`, `SYS-0082`). A stage's run in a step needs a value written
   in that step (`age_ns` 0) on `control`, `refSync` and `compState`, one per run; a value carried
   from an earlier step does not count for any run (it is what a run that published nothing leaves).
   Replace the `carried` rule. If a clean lab topology then gives a `checkRuns` finding in
   `SYT-INS-06.c1`, do not relax the rule: report the case, step, stage and port with what the
   recording holds there.
2. **`--follow` reports skips at the end too** (`IMP-0094`): steps skipped in the last read before
   the end are printed as `N steps skipped` before `dump`/`check` exits.
3. The two words of A1 in the code comment of `Runner::ExecTicket`, if it names `RunStage`.

## Part C — the test tools and `LAB-53`
Decided here:
4. `tests/support/lm_reader.cpp` (`IMP-0114`, `F-READER`) on `livemeas_layout.hpp` and
   `SharedRegion`: `--stall` attaches and reads nothing until killed; `--kill-after N` reads N cycles
   then waits to be killed; `--layout-version V` refuses a measurement of another version as a real
   reader does (exit 6 naming both); `--write-byte` attempts one write into its read-only mapping
   (`RCT:SYT-LMS-05`: the reader faults, the writer goes on); `--until-finished <name>` polls for the
   name every 1 ms, maps it, waits until `status` is finished, prints `outcome=<n>` and exits 0 (exit
   6 if it never attached before its own timeout argument).
5. `tests/support/lm_flawed.cpp` (`IMP-0115`, `F-FLAWED-LM`): `--source <name> --target <name>
   --flaw <one of --drop-port, --skip-step, --drop-ref-sync, --alter-byte, --lower-badge> [args]`:
   follows a held source live measurement to its end, then writes the target through the three writer
   calls — the source's description and every cycle, with that one flaw (or none) — and waits for a
   gate file before `liveMeasClose`, so a test attaches `check` to the target first.
6. `tests/support/lm_stress.cpp` (`IMP-0116`, `F-STRESS`), `tests/support/isolate_stage.cpp`
   (`IMP-0117`, `F-ISOLATE`), `tests/support/livemeas_runs.py` (`IMP-0118`: `held_run` starts a case
   on `F-LM-HELD`, waits for the name, attaches what the test asks for, releases the gate;
   `inspect(verb, …)` runs `vantage-inspect` and returns output and exit code) — as the rows say.
7. **`LAB-53`** in `modules/vantage-lab`: `src/lab_tools/supervise.py::run_under_supervisor(setup,
   *, simengine, attempt_timeout_ms, restart_on_crash=0, reader=None)` starts `simengine <setup>
   --supervise --attempt-timeout-ms N [--restart-on-crash N]`; when `reader` (a path to an
   `F-READER`) is given and the setup names a live measurement, it starts `reader --until-finished
   <name>` first; returns the exit code, the attempt records it read from `<setup>.attempts.jsonl`,
   and the sealed outcome the reader printed (`None` without a reader). File header and the lab's own
   style; a unit test in the lab's tests for argument building and record parsing only (no engine
   needed). The lab never imports Vantage.

## Part D — the system tests and gate G4
Each test function names its test id and case id verbatim (`SYT-LMW-07.c1`), cites the Accept it
checks, and asserts the case's FAIL side. A test whose lab output or tool is missing skips with the
reason printed; **none of the gate's tests may skip** in your final run.
8. `tests/system/test_vnt_lms.py` (`IMP-0119`): `RCT:SYT-LMS-01`..`09` on Vantage (`F-LM` =
   `F-LM-HELD`, `F-LM-STRESS` = `F-STRESS`, `F-CAM` the `camera` topology), `RCT:SYT-LMS-02.c2` on
   `F-LM-TWICE` (built with the recording-edit helper: `B`'s controls in pairs, the first logged at
   the second's instant). `SYT-LMS-03`'s 60 s is the contract's number: keep it.
9. `tests/system/test_vnt_live_measurement.py` (`IMP-0120`): `SYT-LMW-01`..`16`.
10. `tests/system/test_vnt_inspector.py` (`IMP-0121`): `SYT-INS-01`..`05`, `07`..`12`.
11. `tests/system/test_vnt_supervisor.py` (`IMP-0122`): `SYT-SUP-01`..`15`; `F-SUPERVISED` is
    `run_under_supervisor` with `F-LM-HELD`'s held reader; `SYT-SUP-14` on `F-ISOLATE`.
12. `tests/system/test_vnt_gate_g4.py` (`IMP-0123`): `SYT-INS-06.c1` (every topology's first exact
    case, `check --recording`, no finding) and `.c2`. **G4 is green** when this file and the four
    files of steps 8–11 pass with no failure and no skip. Say so in the file's docstring.
13. **When a test fails:** a defect in C2 code (`src/livemeas`, `src/inspector`, `src/simengine`,
    the live-measurement and supervision-cell parts of `src/simcore`) may be fixed here, each fix
    named with the case that found it. Never change C1 behaviour (orchestrator, selection, step,
    equal outputs), a requirement, an Accept, or a test's pass criterion to make a case pass — stop
    that case and report it with what was seen.

## Part E — builds and suites (once, at the end)
14. `modules\vantage`: `build.bat -t sil -p vs2026`, `-t gtest -p vs2026`, `-t package -p vs2026`
    (install tree check as before if it only exports); gtest (last 478/478); Python `tests/unit
    tests/system` (last 1572 passed, 62 skipped) — report the skip list and that no G4 test is in it.
    The G4 files on their own, with seconds. `modules\vantage-lab`: its unit tests. Root:
    `py -3.12 scripts\check_invariants.py`; `py -3.12 .claude/templates/requirements/trace_check.py
    --set modules/vantage/docs --status` and `--set modules/interfaces/docs/resim_contract --status`.
15. `git -C modules/vantage status --short`, and `git diff --stat` in vantage, vantage-lab and
    interfaces, each equal with and without `--ignore-cr-at-eol`.

## Part F — boxes (only when step 14 passes with G4 green)
16. `VANTAGE_Implementation_Design.md`: every `[~]` row whose design text ends ` Closed by `WP-18`.`
    → `[x]`, deleting that sentence with its one leading space; `IMP-0114`..`IMP-0123` → `[x]`;
    package lines `WP-14`, `WP-15`, `WP-16`, `WP-18` → `- [x]`, deleting ` Closed by its rows' tests
    passing (`WP-18`).` where present. `WP-17`, `IMP-0103` and `IMP-0112` stay as they are.
17. `VANTAGE_Lab_Design.md`: `LAB-53` → `[x]`; `LAB-WP-08` → `- [x]`, deleting ` Closed by `LAB-53`
    (`supervise.py`) and the supervised `hang` and `crash` cases passing.`.
18. `modules/interfaces/docs/resim_contract/RCT_Implementation_Design.md`: rows `IMP-0034`..`IMP-0039`
    → `[x]`; every `[~]` row ending ` Closed by `SYT-LMS` passing (`WP-09`/`WP-10`).` or
    ` Closed by `SYT-LMS` passing.` → `[x]`, deleting that sentence with its leading space; package
    lines `WP-02`, `WP-03`, `WP-09`, `WP-10` → `- [x]`, deleting ` Closed by its rows' tests
    passing.` where present. Nothing else in that file.
19. Expected (the orchestrator's dry run): vantage `trace_check` PASS, 229 requirements, 102 tests,
    `packages: 17 done, 1 started, 0 open, of 18`, `design rows: 122 done, 1 started, 1 open, of
    124`, `VANTAGE_Lab_Design.md` 67/67; RCT PASS, 96 requirements, 42 tests, `packages: 10 done,
    3 started, 0 open, of 13`. If a case failed, its rows stay `[~]` and you list them.

## Exit check (run all, report output and seconds)
- Steps 14, 15 and 19, each with counts and seconds; the G4 files' result on its own line.
- Each new test file with its count; each fix of Part B and step 13 with its finding case.

## Must not
- change any doc text beyond A1, A2 and Part F's boxes; touch `bridge.py`, `--config`/`--timeout-ms`
- change C1 behaviour, a requirement, an Accept or a pass criterion (step 13)
- add a skip, tolerance, retry or `xfail` no step names; a gate test that skips is not green
- commit or push

## Report back in this shape
1. Done / not done, in one line per part; **G4 green: yes / no**.
2. Files changed, one line each (group the test files).
3. Exit check output: each command, pass/fail, seconds (R-TEST-7).
4. Boxes ticked (row ids and package lines), and any `[~]` left with what closes it.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
