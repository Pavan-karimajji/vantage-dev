Your role: read .claude/agents/vantage-builder.md and follow it.
Keep the report under 40 lines, in the §4.2 shape.

# VNT-WP-13 — producer keys and the `09b` known limits (`D29`, `WP-13`, `IMP-0063`..`IMP-0070`, vantage `c1`)

One package before gate G3 (`09c`). It puts the engine's own keys back into the engine-run
recording's `manifest` (they left with the Python writer in `09a`, and `--pin-builds` and the
determinism report read them), records the first divergence there, re-enables the tests that
would have caught that, and closes three limits the owner named (`D29`). Five parts, in order:
**A** the doc edits, exactly; **B** the engine and reader rows; **C** the tests; **D** builds and
suites; **E** boxes. **Not in this package:** two runs of one stage in one step in the live
measurement — that waits for an owner decision.

## Context (read these, nothing else unless a step needs it)
- Working copy `C:\ws\repo\vantage-dev`, native Windows (`vs2026`). `modules/vantage` is on
  branch **`c1`** — stay on it. Never run `git checkout`, `git switch`, `git stash`, `git reset`,
  `git rm`, `git restore`, `git add`, `git commit`, `git push`, `pkill` or `kill`.
- **Owner conditions for `c1`:** every commit builds the whole of vantage and passes its full unit
  suite; a test of the old behaviour that can no longer pass is corrected in the same change, and
  you name it.
- Rules: `.claude/rules/style.md` (file header on every new file, minimal diffs), `testing.md`,
  `requirements.md` R-REQ-4, R-REQ-5, R-REQ-9 (the test id and case id verbatim in the test).
- Python: `modules\vantage\.venv-sim-win32\Scripts\python.exe`. Never `py -3`. Root scripts:
  `py -3.12`.
- Read, after Part A: `VANTAGE_DEV_PLAN.md` `D27`, `D29`; `VANTAGE_Architecture.md` §6 step 1;
  `VANTAGE_System_Requirements.md` `SYS-0055`, `SYS-0056`, `SYS-0057`; `VANTAGE_Test_Spec.md`
  `SYT-RUN-12`, `SYT-ORC-13`, `SYT-EQO-06` and the fixture catalogue; `VANTAGE_Implementation_Design.md`
  rows `IMP-0060`, `IMP-0061`, `IMP-0063`..`IMP-0070`; `RCT_Architecture.md` §6a (the `manifest`
  item) and `RCT_Test_Spec.md` `SYT-REC-03` in `modules/interfaces/docs/resim_contract/`.
- **Facts the orchestrator established** (read the code before relying on them):
  - *Readers.* `adas_sim.io.base.manifest_from_dict` reads top-level `run_id`, `host`,
    `process_nonce`, `run_spec_sha256`, `divergence` and each `components[]` entry's
    `library_sha256`, `build_id`, `config_bundle_sha256`. `runspec/manifest.py::verify_pinned_builds`
    (`--pin-builds`) compares `components[].library_sha256` with `Pipeline.component_build_shas()`
    (the SHA-256 of each library file's bytes) and calls a missing one *unpinnable*.
    `diagnostics/determinism.py::derive_axis` compares `host`, `process_nonce` and each
    component's three hashes. No Python reader takes a bundle hash from the `config_bundle` block
    today — hence `IMP-0068`.
  - *Engine.* `simEngineCreate` (`src/simcore/abi/simcore.cpp`) writes `manifest` once, at create,
    from `ManifestYaml` (components with `build_id` and `name`, `manifest_version`,
    `record_policies`, `run_kind`, `source_kind`). The run setup carries `run_id` and `spec_sha256`
    (`RunSpec`). The recording holds no event log, so the divergence goes into `manifest`.
  - *Limit 1.* `select_inputs.cpp::RecordedRefSync` looks first in the arrived refSyncs
    (`RecordedReference::Find`) with no bound; `RecordedReference::Add` keeps each payload's
    reception time.
  - *Limit 2.* `Runner::WriteStep` writes a post-mutation input topic once per step, from
    `impl.delivered` — the later run's value when a stage runs twice in the step.
  - *Timeout.* `Component::Exec` hands `ExecTimeout::Run` a lambda that captures `inner`,
    `inputs` and `input_meta` by reference — the caller's frame, gone after a timeout.
  - *`RCT:SYT-REC-03.c3`.* Its steps hand the engine's writer `F-ENGINE-REC`'s messages and
    metadata a second time; Vantage implements it as two engine runs compared byte for byte
    (`tests/system/test_vnt_wp13_recordings.py::test_syt_rec_03_c3_two_engine_runs_are_byte_identical`),
    which a per-process `process_nonce` breaks — hence `IMP-0069`.
  - *Skipped tests.* 15 tests skip with "no built echo_stub found": their candidates
    (`_ECHO_STUB_CANDIDATES_WINDOWS` in `tests/system/test_d15b_engine_bridge.py`, and the same
    path spelled in other files) look under `modules/vantage/build-gtest-vs2026/`, while the build
    is under `modules/vantage/conan_workarea/build-gtest-vs2026/`. With the stub at the old path,
    those files gave 39 passed, 7 failed, 3 skipped (df recordings absent): `test_c3_check.py` (2),
    `test_d7_batch.py` (2), `test_d15b_cli_resim.py::test_sim_resim_cli_runs_a_real_stage_through_simengine`,
    `test_d7_batch_isolation.py` (2). Causes seen: an input recording written with no
    `source_kind` (refused since `09a`, `RCT:IMP-0052`), and a topic looked up as `/sut/outputs`
    where the engine now writes `sut.outputs` (C6 port names); the batch ones' cause not read.
    `test_d7_pin_builds_cli.py` and `test_e3_determinism_measured.py` need `modules/df`, absent
    here; `SYT-RUN-12` covers what they check.

## Part A — doc edits (exact)
Every edit below is decided. Each anchor and each new text is the exact content of a fenced block
(the fence lines themselves excluded). Apply them in order, each by exact-string replacement,
keeping each file's line endings (all LF). Kind "after" inserts whole new lines after the **whole
line** holding the anchor, never inside it. If an anchor is not found exactly once, stop and report
it; never adjust the text to make a check pass. The orchestrator has dry-run all 12:
`trace_check` PASS, 127 requirements, 56 tests, no findings, and PASS again in the final box state
of step 15.

**E1** · `VANTAGE_DEV_PLAN.md` · insert the new text as new line(s) directly after the line holding the anchor.

Anchor:
````
| D28 | **The `09b-2` findings (owner, 2026-11-03).**
````
New text:
````
| D29 | **Producer keys and the `09b` known limits (owner, 2026-11-02 and 2026-11-03).** (1) Before the merge, the engine writes beside C6's `manifest` keys its own: `run_id`, `host`, `process_nonce`, `run_spec_sha256` and each simulated stage's `library_sha256`; never the bundle hashes, which stay in `config_bundle`, where Vantage's reader takes them. The first divergence goes into `manifest` as `divergence`, since the recording holds no event log. No contract change: C6 allows a producer's own keys. (2) After a timeout, the stuck call's inputs, outputs and library are never freed: at most one leak per process, which refuses later runs. (3) A refSync already received matches only if received before its stage's next recorded `control` (`D27`). (4) A stage run twice in one step leaves both runs' overridden inputs in the recording (`R-SIM-6`, `R-SIM-15`). (5) A run's outputs stay in port-name order. | 2026-11-03 |
````

**E2** · `modules/vantage/docs/VANTAGE_Architecture.md` · replace the anchor with the new text.

Anchor:
````
   the stage's next recorded `control` (`D27`); a stage the recording holds no
   `control` of is searched to the readiness limit. Not found, the run takes the time
   rule (step 4).
````
New text:
````
   the stage's next recorded `control` (`D27`); a stage the recording holds no
   `control` of is searched to the readiness limit. The bound holds for the arrived
   messages too: a refSync received after that `control` is not taken (`D29 (3)`).
   Not found, the run takes the time rule (step 4).
````

**E3** · `modules/vantage/docs/VANTAGE_System_Requirements.md` · replace the anchor with the new text.

Anchor:
````
Priority split: 25 `P0`, 29 `P1`, 0 `P2`; all `R1`.
````
New text:
````
Priority split: 25 `P0`, 32 `P1`, 0 `P2`; all `R1`.
````

**E4** · `modules/vantage/docs/VANTAGE_System_Requirements.md` · insert one blank line, then the new text, directly after the line holding the anchor.

Anchor:
````
**Verify.** T · `SYT-RUN-11`   **Trace.** —
````
New text:
````
**`SYS-0055`** · `P1` · `R1` — The engine-run recording names the run, process, setup and libraries that made it
**Shall.** An engine run shall write in its recording's `manifest` its `run_id`, `host`, `process_nonce`, `run_spec_sha256` and each simulated stage's `library_sha256` (`R-SIM-6`, `D29 (1)`).
**Accept.** On `running_example` `cut_c` each `library_sha256` is the SHA-256 of the library loaded and `run_spec_sha256` the setup's `spec_sha256`; a second run's `manifest` differs only in `process_nonce`.
**Binds.** `runRecording`
**Verify.** T · `SYT-RUN-12`   **Trace.** —
````

**E5** · `modules/vantage/docs/VANTAGE_System_Requirements.md` · replace the anchor with the new text.

Anchor:
````
**Binds.** `control`, `stageOut`, `runRecording`
**Verify.** T · `SYT-ORC-04`   **Trace.** —
````
New text:
````
**Binds.** `control`, `stageOut`, `runRecording`
**Verify.** T · `SYT-ORC-04`   **Trace.** —

**`SYS-0057`** · `P1` · `R1` — Every run's overridden inputs are recorded
**Shall.** An engine run shall record each run's overridden inputs as that run was handed them, a stage run twice in one step leaving both (`R-SIM-15`, `D29 (4)`).
**Accept.** In `running_example` `all_simulated` with `buffer_depth` 1 on every port and an override on `source.Y`, `B`'s `in_Y` topic holds one message per `B` control, each with the counter its run's re-run refSync names.
**Binds.** `stageIn`, `runRecording`
**Verify.** T · `SYT-ORC-13`   **Trace.** —
````

**E6** · `modules/vantage/docs/VANTAGE_System_Requirements.md` · insert one blank line, then the new text, directly after the line holding the anchor.

Anchor:
````
**Verify.** T · `SYT-EQO-05`   **Trace.** —
````
New text:
````
**`SYS-0056`** · `P1` · `R1` — The engine-run recording states its first divergence
**Shall.** An engine run shall write in its recording's `manifest` a `divergence`: the first divergence's step, stage and port; `none` when outputs were compared and none diverged; else `unknown`.
**Accept.** On `no_ref_sync` it names the event log's `first_divergence` entry; on `cut_c` it is `none`; on `cut_c` with the simulated stages' outputs removed from the recording, `unknown`.
**Binds.** `runRecording`, `eventLog`
**Verify.** T · `SYT-EQO-06`   **Trace.** —
````

**E7** · `modules/vantage/docs/VANTAGE_Test_Spec.md` · insert one blank line, then the new text, directly after the line holding the anchor.

Anchor:
````
- `.c2` **PASS:** each stage's `bundle.sha256` text equals the setup's hash for it. **FAIL:** any differs.
````
New text:
````
**`SYT-RUN-12`** · T · fixture `F-CASE`, `F-ENGINE`, `F-RUN-CONFIG`, `F-REC-EDIT` — An engine-run recording names what made it
**Serves.** `SYS-0055`
**Steps.** Run `running_example` `cut_c` on `F-ENGINE` twice; read both recordings' `manifest` through Vantage's recording reader, each simulated stage's library file and the setup. Run `F-RUN-CONFIG` with `sim resim --save`; then run `sim resim --pin-builds` with it on the saved recording, on a copy whose `manifest` gives its stage another `library_sha256`, and on a copy that gives none.
- `.c1` **PASS:** `run_id` and `run_spec_sha256` are the setup's `run_id` and `spec_sha256`, `host` this machine's name, `process_nonce` not empty, and each simulated stage's `library_sha256` the SHA-256 of its library file, per `SYS-0055` Accept. **FAIL:** a key missing, empty or with another value, or a component entry for `C`.
- `.c2` **PASS:** the two manifests differ only in `process_nonce`, and `adas_sim.diagnostics.determinism.derive_axis` gives `fresh_process` for them. **FAIL:** another difference, equal nonces, or another axis.
- `.c3` **PASS:** `--pin-builds` passes on the saved recording, refuses the changed copy as a mismatch and the stripped copy as unpinnable. **FAIL:** a refusal of the saved recording, or a pass on either copy.
````

**E8** · `modules/vantage/docs/VANTAGE_Test_Spec.md` · insert one blank line, then the new text, directly after the line holding the anchor.

Anchor:
````
- `.c1` **PASS:** 1, 2, `0xFFFFFFFF`, 1 and 2, per `SYS-0050` Accept. **FAIL:** a 0, or `0xFFFFFFFF` followed by anything but 1.
````
New text:
````
**`SYT-ORC-13`** · T · fixture `F-CASE`, `F-SETUP-EDIT`, `F-ENGINE` — Every run's overridden input is recorded
**Serves.** `SYS-0057`
**Steps.** Run `running_example` `all_simulated` with `buffer_depth` 1 on every port and one declared override on `source.Y` that leaves its `sig_header` unchanged; read `B`'s `control` and re-run `refSync` messages and its `in_Y` topic in the engine-run recording.
- `.c1` **PASS:** as `SYS-0057` Accept, and at least one step holds two `B` runs. **FAIL:** a count other than the controls', a message carrying another run's counter, or no step with two `B` runs, so the case could not fail.
````

**E9** · `modules/vantage/docs/VANTAGE_Test_Spec.md` · insert one blank line, then the new text, directly after the line holding the anchor.

Anchor:
````
- `.c1` **PASS:** in each, as `SYS-0054` Accept. **FAIL:** no entry, an entry at an earlier step, or no `KIND_FALLBACK` on that run's `in_Y` at its step.
````
New text:
````
**`SYT-EQO-06`** · T · fixture `F-CASE`, `F-REC-EDIT`, `F-ENGINE` — The engine-run recording states its first divergence
**Serves.** `SYS-0056`
**Steps.** Run `running_example` `no_ref_sync` and `cut_c` on `F-ENGINE`; then `cut_c` on a copy of its recording with every topic of `A`, `B`, `D` and `E` except their `control` removed. Read each engine-run recording's `manifest` `divergence` and each event log's `first_divergence` entry.
- `.c1` **PASS:** as `SYS-0056` Accept, `no_ref_sync`'s value naming the entry's step, stage and port. **FAIL:** another value, `none` or `unknown` where an entry exists, or `none` where no output was compared.
````

**E10** · `modules/vantage/docs/VANTAGE_Implementation_Design.md` · insert the new text as new line(s) directly after the line holding the anchor.

Anchor:
````
- [x] **WP-12** — The engine-run recording's config bundle ·
````
New text:
````
- [ ] **WP-13** — Producer keys and the `09b` known limits (`D29`) · Before gate G3 and the merge: `--pin-builds` and the determinism report on `main` read these keys today, so their absence would land as a regression.
````

**E11** · `modules/vantage/docs/VANTAGE_Implementation_Design.md` · replace the anchor with the new text.

Anchor:
````
    WP12 --> WP09
````
New text:
````
    WP12 --> WP13["WP-13<br/>producer keys"]
    WP13 --> WP09
````

**E12** · `modules/vantage/docs/VANTAGE_Implementation_Design.md` · insert the new text as new line(s) directly after the line holding the anchor.

Anchor:
````
| `[x]` | `IMP-0059` |
````
New text:
````
| `[ ]` | `IMP-0063` | `SYS-0055` | `WP-13` | `EXTEND` | `src/simcore/abi/simcore.cpp::ManifestYaml`, `simEngineCreate` — beside C6's keys: `run_id` and `run_spec_sha256` (the setup's `run_id` and `spec_sha256`), `host`, `process_nonce` (random, drawn once per process) and each simulated stage's `library_sha256` (the SHA-256 of the library file loaded), named as `adas_sim.io.base.manifest_from_dict` reads them. | `SYT-RUN-12` |
| `[ ]` | `IMP-0064` | `SYS-0056` | `WP-13` | `EXTEND` | `src/simcore/abi/simcore.cpp`, `src/simcore/runner/cycle_loop.cpp::Runner` — the `manifest` block is written once, when the recording closes, for every outcome that closes it, with `divergence`: `step=<n> stage=<s> port=<p>` of the latched first divergence, `none` when an output was compared and none diverged, else `unknown`. | `SYT-EQO-06` |
| `[ ]` | `IMP-0065` | `SYS-0020` | `WP-13` | `EXTEND` | `src/simcore/runner/select_inputs.cpp::RecordedRefSync` — an arrived refSync matches only if it was received before the stage's next recorded `control` after this run's (`D27`, `D29 (3)`); one received later is not found, so the run takes the time rule. | `SYT-SEL-01` |
| `[ ]` | `IMP-0066` | `SYS-0057` | `WP-13` | `EXTEND` | `src/simcore/runner/cycle_loop.cpp::Runner::WriteStep` — after each run's outputs (`IMP-0061`), that run's overridden input topics, from what that run was handed; a stage run twice in one step leaves both. | `SYT-ORC-13` |
| `[ ]` | `IMP-0067` | `SYS-0040` | `WP-13` | `EXTEND` | `src/simcore/module_host/component.cpp::Component::Exec` — under a timeout the call's inputs, input metadata and result live in state its task shares, never in the caller's frame, so a call returning after its timeout writes only there; a timed-out component's library is never unloaded (`IMP-0060`, `D29 (2)`). | `SYT-THR-02` |
| `[ ]` | `IMP-0068` | `SYS-0055` | `WP-13` | `EXTEND` | `src/adas_sim/io/mcap.py::McapReader.meta` — a component whose `manifest` entry has no `config_bundle_sha256` takes it from the `config_bundle` block's `<stage>/bundle.sha256`, so `derive_axis`, the evidence chain and `sim doctor` read the bundle hash where the engine writes it (`D29 (1)`). | `SYT-RUN-12` |
| `[ ]` | `IMP-0069` | `SYS-0055` | `WP-13` | `NEW` | `tests/support/rewrite_recording.cpp::main` — reads a recording through the engine's reader and writes its messages and metadata again through the engine's writer, so `RCT:SYT-REC-03.c3` compares two writer calls with the same arguments, not two engine runs, whose `process_nonce` differs. | `SYT-RUN-12` |
| `[ ]` | `IMP-0070` | `SYS-0055`, `SYS-0056`, `SYS-0057` | `WP-13` | `NEW` | `tests/system/test_vnt_producer_keys.py` — `SYT-RUN-12`, `SYT-ORC-13` and `SYT-EQO-06`, on the helpers of `tests/support/engine_runs.py`. | `SYT-RUN-12`, `SYT-ORC-13`, `SYT-EQO-06` |
````

## Part B — the engine and the reader
1. `IMP-0063`: `ManifestYaml` gains the five keys, sorted with the others. `process_nonce` is
   random hex drawn once per process (two engine runs in one host process share it, two processes
   never do); `host` is the name Python's `socket.gethostname()` returns on the same machine;
   `library_sha256` is lowercase hex of the library file's bytes. Update the comment that says two
   runs write the same text.
2. `IMP-0064`: `manifest` moves from create to close, written once, for every outcome that closes
   the recording (completed, failed, timeout). `divergence` is `step=<n> stage=<s> port=<p>` from
   the latch, `none` when at least one output was compared and none diverged, else `unknown`. If an
   outcome closes the recording on a path that cannot reach the latch, or a reader needs `manifest`
   before close, stop this item and report it.
3. `IMP-0065`: `RecordedRefSync` takes an arrived refSync only if it was received before the
   stage's next recorded `control` after this run's (the read-ahead side already stops there). A
   stage with no recorded `control` is unchanged. gtests citing `IMP-0065`: (a) the owner's planted
   case — run k held behind an earlier parked run of its stage, its refSync received after control
   k+1 → the time rule with `KIND_FALLBACK` on every input, never a match; (b) the same refSync
   received before control k+1 → matched.
4. `IMP-0066`: in `WriteStep`, after each run's outputs, that run's overridden input topics from
   what it was handed; the per-step write of those topics goes. gtest citing `IMP-0066`: a stage run
   twice in one step under an override leaves two messages on its overridden input topic, each its
   own run's value, each after that run's outputs.
5. `IMP-0067`: the task owns its inputs, input metadata and result (shared with `Exec`, never a
   reference into `Exec`'s frame); after a timeout the component's library is not unloaded. gtest
   citing `IMP-0067`: a call that blocks past the timeout and is then released returns into live
   state — the test process goes on, and the shared state is still held when the late call
   finishes. If this needs a buffer-ownership redesign beyond that shared state, stop, leave the
   row `[ ]`, and report it as a known limit with what it would take.
6. `IMP-0068`: `McapReader.meta()` fills each component's empty `config_bundle_sha256` from the
   block's `<stage>/bundle.sha256` (the file's text, stripped). Unit tests citing `IMP-0068`:
   filled from the block; a manifest value kept; no block, left empty.
7. `IMP-0069`: `tests/support/rewrite_recording.cpp`, built and found as `step_tap` is. Correct
   `test_syt_rec_03_c3_two_engine_runs_are_byte_identical` to `RCT:SYT-REC-03`'s steps: rewrite the
   engine-run recording with the tool twice and compare those two files with each other and with
   the engine's own; rename it to say so, and name it. Any other test comparing two engine runs'
   files byte for byte: report it, do not change it.

## Part C — the tests
8. `tests/system/test_vnt_producer_keys.py` (`IMP-0070`): `SYT-RUN-12.c1`..`.c3`, `SYT-ORC-13.c1`,
   `SYT-EQO-06.c1`, one test per case, each naming its test and case id verbatim and its FAIL side.
   `F-RUN-CONFIG` is the echo-stub pipeline `tests/system/test_vnt_run_config.py` already runs; the
   two manifest copies of `SYT-RUN-12.c3` go through `edit_recording`.
9. Re-enable the 15 skipped tests: make every echo-stub candidate look in
   `conan_workarea/build-gtest-vs2026/tests/Release/` (one definition the files import, not a new
   copy per file). For each of the 7 that then fail, correct the test where it pins behaviour
   `09a` changed (an input recording now states `source_kind`; topics are named after ports) and
   name it with the cause. A failure with any other cause: leave that test failing, stop working on
   it, and report it with what was seen and your recommendation. No skip, tolerance or `xfail`.

## Part D — builds and suites (once, at the end)
10. `modules\vantage`: `build.bat -t sil -p vs2026`, `-t gtest` (last 439/439), `-t package`;
    Python `tests/unit tests/system` (last 1457 passed, 85 skipped). Root:
    `py -3.12 scripts\check_invariants.py`;
    `py -3.12 .claude/templates/requirements/trace_check.py --set modules/vantage/docs --status`.
11. Report per changed or new test file: passed / failed / skipped, each failure and skip with its
    id; the skip count before and after.
12. `git -C modules/vantage status --short`; `git diff --stat` equal with and without
    `--ignore-cr-at-eol` in vantage and at the root.

## Part E — boxes
13. Only for rows whose cases all pass: each of `IMP-0063`..`IMP-0070` to `[x]`; a row whose case
    fails, or stopped by its step, stays `[ ]`, or `[~]` with "Closed by …" when work landed.
14. `WP-13` follows its rows (`C-WPROLL`).
15. If every case passes, the orchestrator's dry run expects all eight rows and `WP-13` `[x]`, 8 of
    13 packages done. `C-WPROLL`, `C-PLANMARK` and `C-ROWMARK` clean. List every row you flip.

## Exit check (run all, report output and seconds)
- Each build command and suite: pass/fail, seconds, counts before and after; each corrected test
  by name with its cause.
- Each new gtest and unit test by name.
- `check_invariants.py` clean; `trace_check` PASS and the `WP` lines.

## Must not
- change any doc text beyond Part A and Part E's boxes, the contract (`modules/interfaces`), or
  anything under `modules/vantage-lab`
- touch the live measurement (`SetLiveMeasurement`, `MeasCycle` values), or write `SYT-EQO-01`,
  `SYT-THR-01` or the G3 gate (`09c`)
- put a bundle hash into `manifest`; change the order of a run's outputs (`D29 (5)`)
- add a skip, tolerance or exemption no step names
- decide anything the rows leave open — report it with your recommendation

## Report back in this shape
1. Done / not done, in one line per part.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds (R-TEST-7).
4. Boxes ticked (row ids), and any `[~]` with what closes it.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
