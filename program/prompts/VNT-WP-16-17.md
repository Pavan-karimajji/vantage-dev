Your role: read .claude/agents/vantage-builder.md and follow it.
Keep the report under 50 lines, in the §4.2 shape.

# VNT-WP-16-17 — the inspector `vantage-inspect`, and the supervisor with its seal, supervision cell and crash record (`WP-16`, `WP-17`; two fixes to `WP-14`/`WP-15`; vantage `c2`)

The next two C2 packages, in one prompt. **`WP-16`** builds `vantage-inspect`: `attach`, `dump`
(`--description`, `--follow`) and `check` with its five checks; it lands `RCT:IMP-0038` and
`0039`. **`WP-17`** builds the supervisor inside `simengine`: `--supervise` with a required
deadline, one worker per attempt, the five outcomes and their closed exit codes, `HoldLiveMeas` and
the seal, the *supervision cell* (no file written per component call, `D31 (3)`), the attempt
record `<run_setup>.attempts.jsonl` and the crash reproducer. Seven parts, in order: **A** three
doc edits, exactly; **B** two fixes to what `WP-14`/`WP-15` landed; **C** `WP-16`; **D** `WP-17`;
**E** tests; **F** builds and suites; **G** boxes.

**Not in this package** (orchestrator's call, recorded in the ledger): `IMP-0112` (`bridge.py`)
and the removal of `--config`/`--timeout-ms` from `simengine`. Every Python engine run goes through
`run_engine`, whose seven callers pass `config_path`/`exec_timeout_ms`; that path's fate is
decided with the launcher and batch in 8c. Until then `simengine` keeps accepting both options,
`IMP-0103` stays `[~]`, and `WP-17` closes with `IMP-0112`. The system tests (`SYT-INS-*`,
`SYT-SUP-*`), gate G4 and `LAB-53` are `WP-18`'s.

## Context (read these, nothing else unless a step needs it)
- Working copy `C:\ws\repo\vantage-dev`, native Windows (`vs2026`). `modules/vantage` is on branch
  **`c2`** (`1c2a623`, `WP-14`/`WP-15` committed) — stay on it. Never run `git checkout`,
  `git switch`, `git stash`, `git reset`, `git rm` (delete with the shell), `git restore`,
  `git add`, `git commit`, `git push`, `pkill` or `kill` (a test may kill a process it started,
  by its pid, through the platform API).
- **Owner conditions for `c2`:** every commit builds the whole of vantage and passes its full unit
  suite; a test of old behaviour that can no longer pass is corrected in the same change and named.
- Rules: `.claude/rules/style.md` (file header, `COMPONENT: VANTAGE`, minimal diffs), `naming.md`,
  `build.md` (R-BUILD-1), `testing.md`, `requirements.md` R-REQ-9.
- Python: `modules\vantage\.venv-sim-win32\Scripts\python.exe`. Never `py -3`. Root scripts:
  `py -3.12`.
- Read: `VANTAGE_DEV_PLAN.md` `D18 (3)`, `D31`; `VANTAGE_Architecture.md` §3.6, §3.7, §9, §10.1,
  §10.3, §11 (inspector and supervisor rows), §14 (open questions 5, 8);
  `VANTAGE_System_Requirements.md` §8 and §9 (`SYS-0075`..`SYS-0104`);
  `VANTAGE_Implementation_Design.md` rows `IMP-0075`, `IMP-0091`..`IMP-0113`, `IMP-0124` (after
  Part A); `VANTAGE_Test_Spec.md` `ANL-05`, `ANL-06`, `F-SRC-LM`; `modules/interfaces`:
  `cpp/livemeas/livemeas_layout.hpp`, `proto/livemeas/*.proto`, `RCT_Implementation_Design.md`
  rows `IMP-0038`, `IMP-0039`.
- **Facts the orchestrator established** (read the code before relying on them):
  - *What `WP-14`/`WP-15` left.* `src/livemeas/`: `SharedRegion` (`createOrReplace`, `open(name,
    Access)` — on Windows its `size()` is rounded up to a page, `remove` — a no-op on Windows,
    `isProcessAlive`, `currentProcessId`), `writer.cpp`, `seal.cpp` (`vantage::sealAbandoned`
    returns `SealResult`), `cycle_encoder`. `include/vantage/livemeas_writer.h`,
    `livemeas_seal.hpp`. The engine opens at `simEngineCreate`, closes in `simEngineRun`/
    `simEngineDestroy`. The description also lists each `source.<port>` an input is wired to.
    `tests/fixtures/held_probe` (`PROBE_GATE_FILE`) is built; nothing drives it yet.
  - *The supervisor today* (`src/simengine/main.cpp`): `Args` with `config_path`,
    `exec_timeout_ms`, `max_restarts`, `attempt_timeout_ms`, `worker` (`--__worker`, no value);
    supervision starts when `--restart-on-crash` > 0, the deadline defaults to 24 h;
    `BuildChildArgs`, `RunOnce` (the `ADAS_SIM_TEST_FORCE_ABORT` hook is there),
    `WriteCrashReproducer` (into `reproducers/` beside the setup, `failing_cycle = 0`, a fixed
    `stage=sut` text), `AppendManifestAttempt` (`<run_spec>.manifest.json`), `RunWithSupervision`.
    `RunIsolatedStage(stage, executable, args, timeout, stderr_capture_path)` in
    `src/simcore/module_host/isolate.cpp` returns `IsolatedRunResult{outcome, stage, exit_code,
    detail}`, `IsolatedOutcome` `kOk`/`kFail`/`kCrashed`/`kTimedOut`/`kFailedToStart`.
  - *Tests that pin today's supervisor:* `tests/integration/test_ut_exe_04_restart.cpp` (runs
    `simengine <spec> --restart-on-crash 2|3`, reads `<spec>.manifest.json`) and
    `test_ut_exe_05_exit_codes.cpp` (`--restart-on-crash 1`, one case with `--attempt-timeout-ms
    300`). Both change meaning here: correct them, and name them.
  - *Reading a recording.* `include/simcore/io.hpp` `Reader`; since `09a` topics are named after
    ports (C6), so a measured port's topic is its port name.
  - *Analysis tests.* One pytest file per check script, like
    `tests/unit/test_wp15_check_single_carrier.py`; `scripts/ci_gate.py` lists the scripts.
  - *Last counts* (`WP-14-15`): gtest 442/442; Python `tests/unit tests/system` 1560 passed,
    0 failed, 62 skipped; `check_invariants` clean.

## Part A — doc edits (exact)
Each anchor and each new text is the exact content of a fenced block (fence lines excluded);
replace the anchor text, once. If an anchor is not found exactly once, stop and report it. Both
files are LF. The orchestrator dry-ran A1–A3 and Part G's final box state: `trace_check` PASS,
229 requirements, 102 tests, no findings.

**A1** · `modules/vantage/docs/VANTAGE_System_Requirements.md` — `SYS-0080` counted every step
before a port's first value as missing, which `SYS-0062` ("a port with no sample yet is absent")
makes legitimate (the `WP-14-15` report's open question 1).

Anchor:
````
**Shall.** `check` shall report, for every port the description declares and every step, a missing value not marked omitted, enumerating ports from the description only.
````
New:
````
**Shall.** `check` shall report, for every port the description declares and every step after that port's first value, a missing value not marked omitted, enumerating ports from the description only.
````

**A2** · `modules/vantage/docs/VANTAGE_Implementation_Design.md` — `IMP-0095` to match.

Anchor:
````
`src/inspector/check.cpp::checkPorts` — for every port of the description and every step, a finding when there is neither a value nor an `omitted` mark; the ports come from the description, with no name in the source.
````
New:
````
`src/inspector/check.cpp::checkPorts` — for every port of the description and every step after that port's first value, a finding when there is neither a value nor an `omitted` mark (a port never given a value, as a stage input read through its producer's port, gives none); the ports come from the description, with no name in the source.
````

**A3** · same file — `IMP-0109` two words shorter, so Part G's closing sentence keeps it within
the 60-word cap. Same meaning.

Anchor:
````
for the supervisor once the worker has ended, which then removes it.
````
New:
````
for the supervisor after the worker's end, then removes it.
````

## Part B — two fixes to `WP-14`/`WP-15` (from the orchestrator's review)
1. **A finished live measurement is not "held".** `writer.cpp`'s `HeldByLiveWriter` refuses a name
   whenever the old region's `writerPid` is alive, even when that writer has closed it (`status`
   finished). On Windows, a reader still attached to a finished run keeps the region, so a second
   engine run by the same live process (an in-process host, a test) is refused with
   `kLiveMeasNameHeld`. Held means: magic valid, `status` not finished, `writerPid` alive. gtest
   citing `IMP-0072`: open, close, keep a reader mapping, open again in the same process → OK and
   a new `runId`.
2. **No per-step lookups.** `Runner::StepOnce`'s report builder recomputes, at every step, the set
   of overridden ports from `recorded_topics_` and each port's bulk flag by scanning every stage's
   ports and inputs. Compute both once (when the sink is set, or at construction) and look them up.
   Behaviour unchanged: `test_livemeas_engine.cpp` passes as it is.

## Part C — `WP-16`, the inspector (`IMP-0091`..`IMP-0102`)
Decided here, so you do not stop on them:
3. **Target** (`IMP-0101`): `src/inspector/CMakeLists.txt`, executable `vantage-inspect`, added in
   `src/CMakeLists.txt`; installed to `bin` as `simengine` is. It links the layout header,
   `livemeas` (for `SharedRegion`, package-internal), the protobuf runtime, the `adas.livemeas`
   classes of `adas-interfaces`, and `simcore` only for its `io` reader (`--recording`); it calls no
   component-host code. *"No generated bindings"* (`SYS-0078`) means nothing generated is looked up
   at run time: the `adas.livemeas` classes compiled into the binary are fine; every **port
   payload** is decoded only through the description's `descriptor_set` (`DynamicDecoder`).
4. **Attach** (`RCT:IMP-0038`, `IMP-0092`): maps both segments read-only through `SharedRegion`;
   `checkAttach`; a layout mismatch exits 6 naming both versions and reads no cycle. **Sizes come
   from `MeasStatus`'s geometry and `dataSegmentSize`/`bulkSegmentSize`, never from the mapping**
   (report's open question 2); a mapping smaller than they say is "cannot attach", exit 6.
   `writerGone`: `status` running, the pid dead, and the heartbeat unchanged across two reads 200 ms
   apart; the line is `writer gone at step N`, N the step of the newest cycle read (or the last
   heartbeat count when no cycle can be read — say which you used).
5. **Read** (`RCT:IMP-0039`, `IMP-0093`, `IMP-0094`): `tryCopySlot` on each slot, a torn copy read
   again (at most a small fixed number of times, then counted as skipped); cycles in step order.
   One `dump` line per value: step, port name, run position among that port's values in the step,
   origin, `age_ns`, and the decoded payload in protobuf text format on one line; `omitted` and
   bulk references printed as such. `--follow` reads until `status` is finished or the writer is
   gone, and prints `N steps skipped` when `writeSequence` has passed what it could still read.
6. **Check** (`IMP-0095`..`IMP-0100`, after A2): reads to the end like `--follow`, then runs the
   five checks over the cycles it holds, one finding per line, exit 1 on any, 0 on none.
   `checkRuns` identifies a stage's runs by the values on its `control` port. `checkAgainstRecording`
   compares each value of a port whose origin is not `simulated` or `overridden` with the
   recording's newest message on that port's topic at or before the step's simulation time, on
   `measurement_counter` and bytes. A step lost to lapping is a `checkSteps` finding.
7. **Exit codes** (`IMP-0091`): `InspectExit` 0, 1, 2 (usage), 6 (cannot attach: no such name, a
   layout mismatch, a region too small), each non-zero end with one line naming the cause.
8. **`check_inspector_items.py`** (`IMP-0102`): as the row says, plus its line in `ci_gate.py`.

## Part D — `WP-17`, the supervisor (`IMP-0075`, `IMP-0103`..`IMP-0111`, `IMP-0113`, `IMP-0124`)
9. **Arguments** (`IMP-0103`, partly): `--supervise` starts supervision (no longer
   `--restart-on-crash` > 0); `--supervise` without `--attempt-timeout-ms` exits 2 naming it, starts
   no worker; `--restart-on-crash` or `--attempt-timeout-ms` without `--supervise` exits 2 naming
   it; the 24 h default goes. The worker flag becomes `--__worker <cell-name>`. `--config` and
   `--timeout-ms` stay for now (see the top).
10. **Supervision cell** (`IMP-0109`, `IMP-0124`): the layout once in `include/simcore/abi/simcore.h`
    — a magic, the stage count, the last completed step and a has-step flag (each 8-byte aligned,
    written with atomic stores), then one byte per stage in run-setup order. `simEngineSetSupervisionCell(engine,
    base, length)` validates magic, length and stage count against the setup and returns a
    `SimExitCode`; `Runner::SetSupervisionCell`. `RunStage` stores 1 in its stage's byte right before
    `Component::Exec` and 0 right after (also on an exception or a timeout return); `StepOnce`
    stores the step number at the end of each step, after the report is handed on. No cell: no
    store. `src/simengine/supervision_cell.{hpp,cpp}::SupervisionCell` on `SharedRegion`, named
    from the supervisor's pid and the attempt number; the worker opens it from the flag and hands it
    to the engine before the first step; the supervisor reads `stagesInCall` and `lastCompletedStep`
    after the worker's end, then removes it. `SIMCORE_ABI_VERSION` stays 5 (one C2 bump).
11. **Supervisor** (`IMP-0104`..`IMP-0107`, `IMP-0075`): `RunIsolatedStage` gains an optional
    `poll(pid)` called at each wait step (existing callers unchanged); `ClassifyWorkerEnd`;
    `RunWithSupervision` per `IMP-0106`; `ReadLiveMeasName` reads `outputs.livemeas.name` from the
    setup file (no live measurement named: nothing to hold or seal); `HoldLiveMeas` from `poll`
    maps it read-write once its magic is valid and keeps the mapping to the supervisor's end;
    `SealAfterWorker` after a crash or timeout calls `sealAbandoned` with `crash` (3) or `timeout`
    (4) once the pid is gone; never after a pass or a fail.
12. **Records** (`IMP-0108`, `IMP-0110`, `IMP-0111`): `AppendManifestAttempt` writes one JSON
    object per line to `<run_setup>.attempts.jsonl` — `attempt`, `outcome` (`ok`/`fail`/`crash`/
    `timeout`/`failed_to_start`), `exit_code` or `signal`, `last`, `stages` (a list, or the string
    `unknown`). `ReproducerInput` gains `stages` and `run_id`, `failing_cycle` optional;
    `WriteCrashReproducer` fills them from the cell and the setup's `run_id`, after a crash only.
13. **`check_supervisor_boundary.py`** (`IMP-0113`): as the row says, plus its line in `ci_gate.py`.

## Part E — tests
Each test names its row (`IMP-00nn`) or analysis case (`ANL-0n .cN`) verbatim.
14. **Inspector** (gtest, `tests/unit/test_inspector.cpp`, building live measurements in-process
    with the writer API): `formatStatus` fields; `writerGone` false while the writer's pid lives and
    true for a dead pid (a status written with a dead pid stands in); a ring of 2 slots read after 5
    steps reports the skipped steps; each of the five checks: one planted flaw → exactly its finding,
    the clean measurement → none (`checkPorts`: a port dropped from one middle step is a finding, a
    port before its first value and a port never given a value are not); `dump` decodes a payload
    through `descriptor_set` only. Then the executable (a gtest or pytest that runs it): an unknown
    verb exits 2; `attach` of a name nobody holds exits 6; a layout version mismatch exits 6 naming
    both (write a status with `layoutVersion + 1`).
15. **Supervisor** (integration, the real `simengine`, echo-stub setups as `test_ut_exe_04/05` use):
    `--supervise` without a deadline → exit 2, no worker; a pass → 0 and one `attempts.jsonl` line;
    `ADAS_SIM_TEST_FORCE_ABORT` with `--restart-on-crash 1` → exit 8, two lines, both `crash`, the
    second `last`, `stages` `unknown`, a reproducer with `run_id` and no step; the echo stub's hang
    hook with a 300 ms deadline → exit 7, `stages` naming the hung stage (the cell, `IMP-0124`); a
    clean failure with `--restart-on-crash 2` → one attempt, its own code. **The seal** (`held_probe`
    added to an echo-stub setup with `outputs.livemeas`): hold the run, map the live measurement
    from the test, copy both segments, kill the worker by its `writerPid`, wait for the supervisor:
    exit 8, `status` finished, `outcome` crash, and the data segment differs from the copy only in
    those two fields; a passing supervised run is left `pass` by the supervisor. Correct
    `test_ut_exe_04_restart.cpp` and `test_ut_exe_05_exit_codes.cpp` to the new flags and file
    name, and name every case you change.
16. **Cell** (gtest): `SupervisionCell` create/open round trip; through the C ABI on an echo-stub
    run with a cell, the last completed step equals the run's last step and every stage byte is 0
    after the run.
17. **Analysis** (pytest): `tests/unit/test_wp16_check_inspector_items.py` (`ANL-05 .c1`, `.c2`)
    and `tests/unit/test_wp17_check_supervisor_boundary.py` (`ANL-06 .c1`..`.c3`), each with
    `--selftest`.
18. **Part B**: the `IMP-0072` gtest of step 1.

## Part F — builds and suites (once, at the end)
19. `modules\vantage`: `build.bat -t sil -p vs2026`, `-t gtest -p vs2026`, `-t package -p vs2026`
    (as in `WP-14-15`: if the package build only exports because vantage is editable, check the
    install tree holds `bin/vantage-inspect` and `bin/simengine`); gtest (last 442/442; report before
    and after); Python `tests/unit tests/system` (last 1560 passed, 62 skipped). Root:
    `py -3.12 scripts\check_invariants.py`; `check_inspector_items.py`, `check_supervisor_boundary.py`
    and `check_single_carrier.py`, each with and without `--selftest`;
    `py -3.12 .claude/templates/requirements/trace_check.py --set modules/vantage/docs --status`.
20. `git -C modules/vantage status --short`; `git -C modules/vantage diff --stat` equal with and
    without `--ignore-cr-at-eol`.

## Part G — boxes (only for rows whose work landed and whose Part E tests pass)
21. `[x]`: `IMP-0102` (`ANL-05`), `IMP-0113` (`ANL-06`).
22. `[~]`, appending ` Closed by `WP-18`.` at the end of the row's design text (just before the
    ` | ` that opens its tests column): `IMP-0075`, `IMP-0091`..`IMP-0101`, `IMP-0104`..`IMP-0111`,
    `IMP-0124`.
23. `IMP-0103`: `[~]`, appending ` Closed by `IMP-0112`.` the same way. `IMP-0112` stays `[ ]`.
24. Package lines: `WP-16` `- [~]` with ` Closed by its rows' tests passing (`WP-18`).` appended;
    `WP-17` `- [~]` with ` Closed by its rows' tests passing (`WP-18`) and `IMP-0112`.` appended.
25. A row whose work did not land, or whose test fails, stays `[ ]` (or `[~]` saying what is
    missing). Expected when all lands: `trace_check` PASS, 229 requirements, 102 tests;
    `packages: 13 done, 4 started, 1 open, of 18`; `design rows: 78 done, 35 started, 11 open, of
    124`. List every row you flip.

## Exit check (run all, report output and seconds)
- Each command of steps 19, 20 and 25: pass/fail, seconds, counts before and after.
- Each new test by name; each corrected test by name with its reason.

## Must not
- change the contract (`modules/interfaces`), the lab, or any doc text beyond A1–A3 and Part G
- touch `bridge.py` or drop `--config`/`--timeout-ms` (8c, with `IMP-0112`)
- write a file per component call or per step in the worker for supervision; add a field to the
  live measurement; add a name to `livemeas_seal.hpp`
- write a `SYT-*` system test or the G4 file (`WP-18`)
- add a skip, tolerance or exemption no step names
- decide anything the rows leave open — report it with your recommendation

## Report back in this shape
1. Done / not done, in one line per part.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds (R-TEST-7).
4. Boxes ticked (row ids), and any `[~]` with what closes it.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
