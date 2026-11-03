Your role: read .claude/agents/vantage-builder.md and follow it.
Keep the report under 50 lines, in the §4.2 shape.

# VNT-WP-14-15 — the live measurement writer library, and the engine writing it; the transport publisher retired (`WP-14`, `WP-15`, `IMP-0071`..`IMP-0090` but `IMP-0075`, vantage `c2`)

The first two C2 packages, in one prompt. **`WP-14`** builds the writer library `livemeas`: the
plain-C API (`liveMeasOpen`, `liveMeasStep`, `liveMeasClose`), the shared region it writes, the
`MeasCycle` encoder, bulk ports, oversize handling and the seal `sealAbandoned`. It lands the
contract rows `RCT:IMP-0034`..`0037`. **`WP-15`** makes the engine write it: the description built
from the run setup, every step handed to the writer (two runs of one stage in one step included,
`D30`), the outcome at close, and the old transport publisher deleted so the writer is the only
carrier of step values. Six parts, in order: **A** two doc edits, exactly; **B** `WP-14`; **C**
`WP-15`; **D** tests; **E** builds and suites; **F** boxes.

**Not in this package:** the inspector (`WP-16`), the supervisor, `HoldLiveMeas`, the supervision
cell and the `simengine` options (`WP-17`), the system tests `SYT-LMW-*` and gate G4 (`WP-18`).
`IMP-0075` is `WP-17`'s, not this package's. Nothing in `modules/interfaces` or `modules/vantage-lab`
changes.

## Context (read these, nothing else unless a step needs it)
- Working copy `C:\ws\repo\vantage-dev`, native Windows (`vs2026`). `modules/vantage` is on branch
  **`c2`** — stay on it. Never run `git checkout`, `git switch`, `git stash`, `git reset`, `git rm`
  (delete files with the shell), `git restore`, `git add`, `git commit`, `git push`, `pkill` or
  `kill`.
- **Owner conditions for `c2`:** every commit builds the whole of vantage and passes its full unit
  suite; a test of old behaviour that can no longer pass is corrected or deleted in the same change,
  and you name it.
- Rules: `.claude/rules/style.md` (file header on every new file, `COMPONENT: VANTAGE`, minimal
  diffs), `naming.md`, `build.md` (R-BUILD-1: per-component difference lives in `conf/build.yml`,
  never in a recipe), `testing.md`, `requirements.md` R-REQ-9 (the id verbatim in the test).
- Python: `modules\vantage\.venv-sim-win32\Scripts\python.exe`. Never `py -3`. Root scripts:
  `py -3.12`.
- Read: `VANTAGE_DEV_PLAN.md` `D17 (5)`, `D18 (3)`, `D29 (4)`, `D30`, `D31 (5)`;
  `modules/vantage/docs/VANTAGE_Architecture.md` §4 (the description mapping), §9 (who writes each
  outcome), §10.1, §10.2, §11 (the writer and description rows);
  `VANTAGE_System_Requirements.md` §7 (`SYS-0058`..`SYS-0074`, `SYS-0105`);
  `VANTAGE_Implementation_Design.md` rows `IMP-0071`..`IMP-0074`, `IMP-0076`..`IMP-0090` (after
  Part A); `VANTAGE_Test_Spec.md` `ANL-04` and the fixtures `F-LM-HELD`, `F-SRC-LM`; in
  `modules/interfaces`: `cpp/livemeas/livemeas_layout.hpp`, `proto/livemeas/*.proto`, and
  `docs/resim_contract/RCT_Implementation_Design.md`'s live measurement field tables and rows
  `IMP-0034`..`IMP-0037`.
- **Facts the orchestrator established** (read the code before relying on them):
  - *Layout.* `livemeas_layout.hpp` defines `MeasStatus` (magic, `layoutVersion`, `runId`,
    `writerPid`, atomic `status` 0 starting / 1 running / 3 finished, atomic `outcome` 0 none /
    1 pass / 2 fail / 3 crash / 4 timeout, description capacity and length, the two ring
    geometries, atomic `heartbeat`, `writeSequence`, `droppedCycles`), `CycleSlotHeader`,
    `BulkSlotHeader`, `kBulkSegmentSuffix`, the offset and size functions, `beginSlot`/`endSlot`/
    `tryCopySlot` and `checkAttach`. The writer uses these and defines no layout of its own.
  - *Messages.* `adas.livemeas.MeasCycle` (`values`, `badges`), `MeasPortValue` (`port` index,
    `payload`, `origin`, `age_ns`, `omitted`, `bulk`), `MeasBulkRef`, `MeasBadge`, and
    `MeasDescription` are compiled into `adas-interfaces` (its `CMakeLists.txt` lines 71–72);
    vantage requires `adas-interfaces/1.1.0`.
  - *Run setup.* `SpecOutputs::livemeas` (`include/simcore/runspec.hpp`) is optional; when present
    its `name` and four geometry values are all required by the loader.
  - *Step report.* `Runner::StepOnce` (`src/simcore/runner/cycle_loop.cpp`, near the end) builds a
    `StepReport` only when `live_sink_` is set: one `StepValue` per declared port with a sample (its
    newest), origin, `age_ns`, and every badge above 0. A stage run twice in a step gets one value
    today. `Runner::WriteStep` already writes each run's `control`, `refSync`, outputs and
    overridden inputs in run order (`IMP-0061`, `IMP-0066`): the per-run values `D30` needs are
    those.
  - *Step tap.* `tests/support/step_tap.cpp` installs itself with `runner->SetLiveMeasurement(&tap)`
    after `simEngineCreate`, so today it would replace a writer sink the engine installed.
  - *Transport.* `include/simcore/transport.hpp`, `transport_publisher.hpp`, `transport_shm.hpp`,
    `src/simcore/transport/inproc.cpp`, `shm.cpp` (349 lines: segment create, pid liveness, client
    attach — the code `SharedRegion` starts from); `Runner::SetTransportPublisher` and
    `transport_publisher_`; `simEngineAttachTransport` (`simcore.cpp` ~line 864, `simcore.h` line
    131). Tests on it: `tests/unit/test_transport_inproc.cpp`, `test_transport_shm.cpp`,
    `tests/integration/test_it_transport.cpp` (5 tests), `test_it_trn05_crash.cpp` (1, through
    `tests/fixtures/trn_engine_host`), and one test of `test_it11_embed_host.cpp`,
    `AttachTransportThenStepOnceDeliversRealFramesBetweenTicks` (its other five tests stay). No
    Python code calls the transport. `SIMCORE_ABI_VERSION` is 4 (`simcore.h` line 69 lists each
    version's change).
  - *Build.* `src/CMakeLists.txt` adds `simcore` and `simengine`; `conf/build.yml`'s recipe is
    `type: static-library`, `libs: [simcore]`, `root_requires` and one component `io` (read the
    comments there: a named component gets nothing implicitly from the package's requires).
  - *Analysis tests.* C1's analysis checks are tested by a pytest file per script, e.g.
    `tests/unit/test_wp08_check_engine_decisions.py` (`ANL-01` cases planted in a temporary tree),
    and run by `scripts/ci_gate.py` (its script list near line 286).
  - *Last counts* (`09c-R1`, vantage `c1` = this `c2`): gtest 445/445; Python `tests/unit
    tests/system` 1554 passed, 0 failed, 62 skipped.

## Part A — doc edits (exact)
Two edits to `modules/vantage/docs/VANTAGE_Implementation_Design.md` (LF). Each replaces the whole
line that is exactly the anchor; if it is not found exactly once, stop and report it. The
orchestrator dry-ran both, and the final box state of Part F: `trace_check` PASS, 229 requirements,
102 tests, no findings.

**E1** — `IMP-0087` also names the two transport tests the 8b row missed.

Anchor:
````
| `[ ]` | `IMP-0087` | `SYS-0074` | `WP-15` | `DROP` | `tests/unit/test_transport_inproc.cpp`, `tests/unit/test_transport_shm.cpp`, `tests/integration/test_it_transport.cpp`, `tests/fixtures/trn_engine_host` — deleted with the carrier they test; their `tests/CMakeLists.txt` entries go. | `ANL-04` |
````
New:
````
| `[ ]` | `IMP-0087` | `SYS-0074` | `WP-15` | `DROP` | `tests/unit/test_transport_inproc.cpp`, `tests/unit/test_transport_shm.cpp`, `tests/integration/test_it_transport.cpp`, `tests/integration/test_it_trn05_crash.cpp`, `tests/fixtures/trn_engine_host` and the test `It11EmbedHost.AttachTransportThenStepOnceDeliversRealFramesBetweenTicks` — deleted with the carrier they test; their `tests/CMakeLists.txt` entries go. | `ANL-04` |
````

**E2** — `IMP-0089` corrected: `simEngineCreate` (in `simcore`) calls `liveMeasOpen` (`IMP-0082`),
so `simcore` links `livemeas`; what `ARCH §10.2` forbids is the other direction.

Anchor:
````
| `[ ]` | `IMP-0089` | `SYS-0074` | `WP-15` | `EXTEND` | `src/simengine/CMakeLists.txt`, `conf/build.yml` — `simengine` links `livemeas`; `simcore` does not. | `ANL-04` |
````
New:
````
| `[ ]` | `IMP-0089` | `SYS-0074` | `WP-15` | `EXTEND` | `src/simcore/CMakeLists.txt`, `conf/build.yml` — `simcore` links `livemeas`, whose three calls the engine makes, and the package's root component requires the `livemeas` component; `livemeas` links no `simcore` target (`IMP-0077`, `ARCH §10.2`). | `ANL-04` |
````

## Part B — `WP-14`, the writer library (`IMP-0071`..`IMP-0074`, `IMP-0076`, `IMP-0077`)
Decided here, so you do not stop on them:
1. **Target** (`IMP-0077`): `src/livemeas/CMakeLists.txt`, static library `livemeas`, added in
   `src/CMakeLists.txt` before `simcore`; links `AdasInterfaces::AdasInterfaces` (the layout header
   and the generated `adas.livemeas` classes) and `protobuf::libprotobuf`, nothing of `simcore`.
   Public headers in `include/vantage/` (`livemeas_writer.h`, `livemeas_seal.hpp`). In
   `conf/build.yml`, add `livemeas` to the recipe's libraries and a component `livemeas` with its own
   `requires`, so a consumer can link the writer alone (`ARCH §10.2`). Make `include/vantage/`
   reach the package the way `include/simcore/` does. `-t package` (Part E) is the proof: the
   package holds the `livemeas` library and both headers, and `adas-vantage::livemeas` resolves. If
   the shared recipe cannot express this from `conf/build.yml` alone, stop that item and report what
   it lacks — never a private recipe (R-BUILD-1).
2. **API** (`IMP-0071`): plain C, `extern "C"`, no C++ or protobuf type in the header. A closed
   result enum (`kLiveMeasOk`, `kLiveMeasNameHeld`, `kLiveMeasBadArgument`, `kLiveMeasOpenFailed`,
   and others only if a call needs one), documented in the header. Structs: a value (port index,
   payload pointer and length, origin as the `MeasPortValue.Origin` number, `age_ns`, bulk flag) and a
   badge (kind as the `MeasBadge.Kind` number, subject as a C string, count). A port index may repeat
   in one call's array: that is how a stage's two runs arrive, in run order (`D30`). An opaque handle.
   No call throws, aborts or waits; every exception inside is caught and becomes a code.
3. **Shared region** (`IMP-0072`): `src/livemeas/shared_region.hpp` with `shared_region_posix.cpp`
   and `shared_region_windows.cpp` (the build selects one), starting from `shm.cpp`'s segment code:
   create, map read-write, map read-only, remove the name, `isProcessAlive(pid)`; `createOrReplace`
   returns `kNameHeld` when the named region's `writerPid` is alive and replaces a dead writer's.
   **Windows:** a named region lives while any handle is open (`ARCH §14` Q8), so a dead writer's
   region a reader still holds cannot be deleted: reuse it when its size fits the new geometry, else
   return `kLiveMeasOpenFailed`. Say in the report which path your tests exercised.
4. **Open** (`RCT:IMP-0034`): validates the geometry (a zero count or a slot too small for its
   header is `kLiveMeasBadArgument`); creates the data and bulk segments (`kBulkSegmentSuffix`);
   writes `MeasStatus` with `status` starting, a new random 64-bit `runId`, the own pid, the
   geometry, `descriptionCapacity` = the description's length; copies the description bytes; then
   sets `status` running.
5. **Step** (`RCT:IMP-0035`..`0037`, `IMP-0073`): builds one `MeasCycle` from the structs in the
   order given (`encodeCycle`); the slot is `writeSequence % cycleSlotCount`; `beginSlot`, header
   (step, sim time, length), the bytes, `endSlot`; `writeSequence` +1. A bulk value goes to the next
   `MeasBulk` slot first and carries its `MeasBulkRef`; a bulk payload larger than a bulk slot is
   marked `omitted`. **Oversize:** values are taken in order; a payload that would not leave the
   cycle within the slot is marked `omitted` (payload empty) and the next is tried; if the cycle
   still does not fit with every payload omitted, nothing is written and `droppedCycles` +1.
   `heartbeat` +1 on every call, written or not. No lock, no wait, no reader state.
6. **Close** (`IMP-0074`): `outcome`, then `status` finished, then the name removed (POSIX unlink;
   on Windows the name ends with the last handle), the handle freed. Readers already attached keep
   reading.
7. **Seal** (`IMP-0076`): `sealAbandoned(name, outcome)` in `include/vantage/livemeas_seal.hpp`,
   C++, returns a code: opens the region by name; only when `status` is running and `writerPid` is
   not alive, writes `outcome` then `status` finished and no other byte, then removes the name as
   close does; a live writer or a finished status: writes nothing, returns a code saying which
   (`D18 (3)`, `D31 (5)`). Nothing else is added to that header (`D31 (4)`).

## Part C — `WP-15`, the engine writes it (`IMP-0078`..`IMP-0090`)
8. **Description** (`IMP-0078`): `src/simcore/livemeas/description_builder.cpp::BuildMeasDescription(spec,
   components, topics)` as `ARCH §4` maps it and as the row says; the port order it gives is the
   port index the writer's values use. A field the row names that `MeasDescription` cannot hold:
   stop that field and report it (no contract change here).
9. **Step values** (`IMP-0079`, `IMP-0080`): `StepValue` gains `run` and `bulk` (from the port's
   `bulk` flag in the setup); `StepOnce` hands, for every declared port, its newest sample with
   `age_ns` — except each stage run in this step, whose `control`, `refSync`, outputs and overridden
   inputs come once per run, in run order, from what `WriteStep` records. A port of a stage not run
   this step keeps its one held value. `LiveMeasSink::OnStep` keeps its shape.
10. **Writer sink** (`IMP-0081`): `src/simcore/livemeas/engine_sink.cpp::LiveMeasWriterSink` maps
    port names to the description's indices, calls `liveMeasStep`, then hands the same report to a
    second sink when one is set (`SetNext`). Add the getter `Runner::LiveMeasurement()`. `step_tap`:
    when the runner already has a `LiveMeasWriterSink`, it becomes that sink's next; otherwise it is
    installed as today. So `F-TAP` keeps working with and without `outputs.livemeas` (`SYS-0072`).
11. **Open and close in the engine** (`IMP-0082`, `IMP-0083`, `IMP-0084`): `simEngineCreate`, with
    `outputs.livemeas`, builds the description and opens; a non-OK code prints exactly one line to
    standard error naming the live measurement and the code, and the engine run goes on with no sink
    (`SYS-0068`). Close: `simEngineRun` closes at its end — `pass` when it reached the end of the
    recording or slice, `timeout` on `kSimExitTimeout`, `fail` on any other error; `simEngineDestroy`
    closes a live measurement still open (a host driving `simEngineStepOnce`) with `pass` if the last
    step ended the recording, `timeout` after a call timeout, otherwise `fail`. The engine never
    writes `crash`. `simEngineSeek` neither opens nor closes.
12. **Transport retired** (`IMP-0085`..`IMP-0087`, `IMP-0089`, after E1/E2): delete the files and
    the test named in the rows (the shell, not `git rm`); `Runner::SetTransportPublisher`,
    `transport_publisher_`, the `Publish` call in `WriteStep` and `simEngineAttachTransport` go;
    `SIMCORE_ABI_VERSION` 4 → 5 with one line in `simcore.h`'s version list. Fix every comment that
    names a deleted symbol only where it would now be false; no other rewording.
13. **`held_probe`** (`IMP-0088`): `tests/fixtures/held_probe/held_probe.cpp`, a shared library on
    the generic ABI, built and placed as `exec_probe` is; ports and gate exactly as the row says;
    its manifest built like `echo_stub`'s. No test drives it yet beyond Part D's one.
14. **`check_single_carrier.py`** (`IMP-0090`): as the row says, plus its line in `ci_gate.py`'s
    script list.

## Part D — tests
Each test names the row (`IMP-00nn`) or the analysis case (`ANL-04 .cN`) it serves, verbatim.
15. `tests/unit/test_livemeas_writer.cpp` (gtest, linking `livemeas` and the layout header only):
    open → status running, description bytes and geometry as given, a new `runId` per open;
    `kLiveMeasNameHeld` while a writer lives under that name; a dead writer's name replaced (a
    status written with a dead pid stands in for a killed writer); steps decode through
    `tryCopySlot` into the values given, in order, a repeated port index kept twice in order
    (`D30`); `heartbeat` and `writeSequence` per step; a ring wrap; a bulk value lands in `MeasBulk`
    with a `MeasBulkRef` that resolves; an oversize payload omitted and the step written; a step that
    cannot fit counted in `droppedCycles`; close sets outcome then finished; `sealAbandoned` on a
    dead writer changes only `outcome` and `status` (compare the segments byte for byte), and on a
    live writer or a finished status writes nothing. A bad argument returns its code, never a crash.
16. `tests/unit/test_livemeas_engine.cpp` (gtest, through the C ABI on an echo-stub setup like the
    other C ABI tests): with `outputs.livemeas`, the description lists the setup's stages and ports
    (`IMP-0078`); every step's cycle equals the step report the tap gets (`IMP-0081`); a run whose
    name is already held prints one warning and completes (`IMP-0082`); outcome `pass` after
    `simEngineRun` (`IMP-0083`); after a seek the `runId` is unchanged and steps continue
    (`IMP-0084`); without `outputs.livemeas` nothing is created. A stage run twice in one step leaves
    two values on its per-run ports in run order (`IMP-0080`) — build the two runs with the same
    recording edit `IMP-0066`'s gtest uses.
17. `tests/unit/test_wp15_check_single_carrier.py`: `ANL-04 .c1` (clean tree), `.c2` (a planted
    `SetTransportPublisher(nullptr)` call in `src/simcore/abi/simcore.cpp`), `.c3` (a planted
    `#include "simcore/transport_shm.hpp"` in `src/simcore/runner/cycle_loop.cpp`), shaped like
    `test_wp08_check_engine_decisions.py`; and `--selftest` passes.
18. Any existing test that asserted the transport, or the step tap's sole ownership of the sink:
    corrected or deleted with the carrier, and named with the reason.

## Part E — builds and suites (once, at the end)
19. `modules\vantage`: `build.bat -t sil -p vs2026`, `-t gtest -p vs2026`, `-t package -p vs2026`
    (report what the package holds for `livemeas`); gtest (last 445/445; report before/after and the
    deleted transport tests by name); Python `tests/unit tests/system` (last 1554 passed, 62
    skipped). Root: `py -3.12 scripts\check_invariants.py`; `py -3.12 modules\vantage\scripts\check_single_carrier.py`
    and `--selftest`; `py -3.12 .claude/templates/requirements/trace_check.py --set modules/vantage/docs --status`.
20. `git -C modules/vantage status --short`; `git -C modules/vantage diff --stat` equal with and
    without `--ignore-cr-at-eol`.

## Part F — boxes (only for rows whose work landed and whose tests in Part D pass)
21. `[x]` (their whole Verify is `ANL-04`, closed here): `IMP-0077` (also needs `-t package` to
    pass), `IMP-0085`, `IMP-0086`, `IMP-0087`, `IMP-0089`, `IMP-0090`.
22. `[~]`, appending ` Closed by `WP-18`.` (one space before it) at the end of the row's design
    text, just before the ` | ` that opens its tests column: `IMP-0071`, `IMP-0072`, `IMP-0073`,
    `IMP-0074`, `IMP-0076`, `IMP-0078`, `IMP-0079`, `IMP-0080`, `IMP-0081`, `IMP-0082`, `IMP-0083`,
    `IMP-0084`, `IMP-0088`. The words matter: a longer sentence puts `IMP-0071` over the 60-word cap.
23. Package lines `WP-14` and `WP-15`: `- [ ]` → `- [~]`, and append ` Closed by its rows' tests
    passing (`WP-18`).` at the end of each line.
24. A row whose work did not land, or whose Part D test fails, stays `[ ]` (or `[~]` with what is
    missing). Expected when all lands: `trace_check` PASS, 229 requirements, 102 tests;
    `packages: 13 done, 2 started, 3 open, of 18`; `design rows: 76 done, 13 started, 35 open, of
    124`. List every row you flip.

## Exit check (run all, report output and seconds)
- Each command of steps 19–20 and 24: pass/fail, seconds, counts before and after.
- Each new test by name; each deleted or corrected test by name with its reason.

## Must not
- change the contract (`modules/interfaces`), the lab, or any doc text beyond E1, E2 and Part F
- add a public name to `include/vantage/livemeas_seal.hpp` beyond `sealAbandoned`, or a fourth
  engine call to `livemeas_writer.h`
- give a default to any `⊘` value (the geometry comes from the setup only)
- start on `WP-16`/`WP-17` work: the inspector, `--supervise`, `HoldLiveMeas`, the supervision cell,
  `--config`/`--timeout-ms`
- add a skip, tolerance or exemption no step names
- decide anything the rows leave open — report it with your recommendation

## Report back in this shape
1. Done / not done, in one line per part.
2. Files changed, one line each with what changed (group deletions).
3. Exit check output: each command, pass/fail, seconds (R-TEST-7).
4. Boxes ticked (row ids), and any `[~]` with what closes it.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
