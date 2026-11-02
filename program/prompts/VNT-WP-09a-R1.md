Your role: read .claude/agents/vantage-builder.md and follow it.
Keep the report under 40 lines, in the §4.2 shape.

# VNT-WP-09a-R1 — C1: one recording writer and the `config_bundle` block (`RCT:WP-13`, `WP-12`, `D26`), the call thread (`WP-07`)

This resumes Part A of `VNT-WP-09a`, which stopped on three questions the owner has now
answered (`program/ORCHESTRATION_LEDGER.md`, the two 2026-11-02 OWNER entries, and
`VANTAGE_DEV_PLAN.md` §2 `D26`). Four parts, in order: **A** the doc edits, exactly; **B** the
`interfaces` code; **C** the `vantage` code; **D** builds, suites, boxes. If C stops on something
you cannot resolve, report it with what you did finish.

## Context (read these, nothing else unless a step needs it)
- Working copy `C:\ws\repo\vantage-dev`, native Windows (`vs2026`). `modules/vantage` is on
  branch **`c1`**, `modules/interfaces` on **`vantage`** — stay on them. Never run `git checkout`,
  `git switch`, `git stash`, `git reset`, `git rm`, `git restore`, `git add`, `git commit`,
  `git push`, `pkill` or `kill`.
- **Owner conditions for `c1`:** every commit builds the whole of vantage and passes its full unit
  suite; a test of the old path that can no longer pass is removed or corrected in the same
  change, and you name it.
- Rules: `.claude/rules/style.md` (file header on every new file, minimal diffs), `naming.md`,
  `testing.md`, `requirements.md` R-REQ-9 (a test id appears verbatim in the test implementing
  it), `.claude/rules/sim.md` R-SIM-6, R-SIM-11, R-SIM-19, `.claude/rules/build.md` R-BUILD-7 (a
  build refreshes a lock's first-party pin to a newer revision in the cache).
- Python: vantage's own environment, `modules\vantage\.venv-sim-win32\Scripts\python.exe`; the
  `interfaces` Python suite in the environment its earlier packages used (say which). Never
  `py -3`. Root scripts: `py -3.12`.
- Read: `RCT_Architecture.md` §6a; `RCT_Implementation_Design.md` `IMP-0043`..`IMP-0052` and
  `WP-13`; `RCT_Test_Spec.md` `SYT-REC-03`..`05`, `ANL-06`, fixtures `F-WRITER`, `F-ENGINE-REC`,
  `F-LAB`, `F-SRC-PY`; `VANTAGE_Implementation_Design.md` `IMP-0059`, `IMP-0060`, `WP-12`, `WP-07`;
  `VANTAGE_Architecture.md` §8, §11 *Recording I/O*; `modules/interfaces/scripts/check_recording.py`,
  `pack_config_bundle.py`, `check_one_recording_writer.py`; `src/adas_recording/writer.py`.
- Facts already established by the orchestrator: the engine's C++ writer
  (`src/simcore/io/codecs/mcap.cpp` `McapWriter`) writes only `topic_provenance` today — no
  `manifest`, and its `WriteMeta` has no caller; `simEngineCreate` initialises each simulated stage
  with `config_path` or `NULL` (`config/` beside the library); the lab's run setups carry
  `limits.exec_timeout_ms` 250, so today every call runs on a fresh thread (`RunWithTimeout`); the
  lab finds `adas_recording` through `${adas-interfaces_PACKAGE_FOLDER_RELEASE}/python`
  (`modules/vantage-lab/src/platform/lab_sil/lab_components.cmake`).

## Part A — doc edits (exact)
Every edit below is decided. Each anchor and each new text is the exact content of a fenced block
(the fence lines themselves excluded). Apply each by exact-string replacement or insertion,
keeping each file's line endings (`RCT_System_Requirements.md` and the contract's `layers.yaml`
are CRLF in the working tree, the rest LF). If an anchor is not found exactly once, stop and report it; never adjust the text to
make a check pass. The orchestrator has dry-run all 26 edits on a copy: `trace_check` gives PASS,
96 requirements, 42 tests on `modules/interfaces/docs/resim_contract` and PASS, 112 requirements,
52 tests on `modules/vantage/docs`, no findings, no budget note. Boxes are set in Part D, not here.

**R1 — `modules/interfaces/docs/resim_contract/RCT_Architecture.md`.** Directly after the line that contains

```
| metadata `topic_provenance` | topic → origin, from the closed list
```

insert (no blank line):

```
| metadata `config_bundle` | optional: each stage's config bundle folder, one key per file, `<stage>/<relative path>` → that file's exact text, `<stage>/bundle.sha256` among them; absent when no stage had one; a stage name holds no `/` | a recording renders and re-runs where no build exists, and a reader can check it holds the bundle the run used (`R-SIM-6`, `R-SIM-3a`); kept as files because `bundle.sha256` is computed over the relative paths and file texts (`bundle_sha256`, `scripts/pack_config_bundle.py`); optional, because a car or simulator recording has none |
```

**R2 — `modules/interfaces/docs/resim_contract/RCT_Architecture.md`.** Directly after the line that contains

```
  differ in bytes, and a lab recording would no longer be the known right answer.
```

insert (no blank line):

```
- *The bundle as one YAML document, or with a separate hash key.* `bundle.sha256` is computed
  over files, so a merged document could not be checked without a second rule to split it, and
  a second hash key would be one more value to keep equal to the file.
```

**R3 — `modules/interfaces/docs/resim_contract/RCT_System_Requirements.md`.** Replace

```
Priority split: 30 `P0`, 13 `P1`,
```

with

```
Priority split: 30 `P0`, 14 `P1`,
```

**R4 — `modules/interfaces/docs/resim_contract/RCT_System_Requirements.md`.** Replace

```
and both metadata blocks; a refusal or a difference fails.
```

with

```
and every metadata block it holds; a refusal or a difference fails.
```

**R5 — `modules/interfaces/docs/resim_contract/RCT_System_Requirements.md`.** After the line that contains

```
**Verify.** A · `ANL-06`   **Trace.** —
```

insert one blank line and then:

```
**`SYS-0044`** · `P1` · `R1` — An embedded config bundle matches its own `bundle.sha256`
**Shall.** A recording's optional `config_bundle` block shall hold, per stage it names, that stage's bundle files, its `bundle.sha256` among them and matching them.
**Accept.** `check_recording.py`, recomputing each stage's hash with `bundle_sha256`, passes a recording without the block or with every stage matching, and reports a mismatch or a stage with files but no `bundle.sha256`.
**Binds.** `control`, `dataIn`, `dataOut`, `refSync`, `compState`
**Verify.** T · `SYT-REC-04`, `SYT-REC-05`   **Trace.** —
```

**R6 — `modules/interfaces/docs/resim_contract/RCT_System_Requirements.md`.** Replace

```
| T | 37 |
```

with

```
| T | 38 |
```

**R7 — `modules/interfaces/docs/resim_contract/RCT_Test_Spec.md`.** Replace

```
**Serves.** `SYS-0037`, `SYS-0038`, `SYS-0039`, `SYS-0041`, `SYS-0042`
```

with

```
**Serves.** `SYS-0037`, `SYS-0038`, `SYS-0039`, `SYS-0041`, `SYS-0042`, `SYS-0044`
```

**R8 — `modules/interfaces/docs/resim_contract/RCT_Test_Spec.md`.** Replace

```
compare every message and both metadata blocks with what `check_recording.py` reads
```

with

```
compare every message and every metadata block with what `check_recording.py` reads
```

**R9 — `modules/interfaces/docs/resim_contract/RCT_Test_Spec.md`.** Replace

```
no finding on the engine-run recording, per the Accepts of `SYS-0037`, `SYS-0038` and `SYS-0041`.
```

with

```
no finding on the engine-run recording, per the Accepts of `SYS-0037`, `SYS-0038`, `SYS-0041` and `SYS-0044`.
```

**R10 — `modules/interfaces/docs/resim_contract/RCT_Test_Spec.md`.** After the line that contains

```
- `.c3` **PASS:** Vantage's reader opens both files and returns everything unchanged, per `SYS-0042` Accept.
```

insert one blank line and then:

```
**`SYT-REC-05`** · T · fixture `F-WRITER` — An embedded config bundle is checked against its hash
**Serves.** `SYS-0044`
**Steps.** Pack a bundle with `pack_config_bundle.py` from three small files, one in a subfolder. Call the Python writer once with no `config_bundle`, then three times with that bundle as stage `A`'s block: as packed; with one file's text changed by one character; without `A/bundle.sha256`. Run `check_recording.py` on each file.
- `.c1` **PASS:** no finding on the file without the block or on the packed bundle, per `SYS-0044` Accept. **FAIL:** any finding.
- `.c2` **PASS:** the changed text gives one finding naming stage `A`. **FAIL:** no finding.
- `.c3` **PASS:** the missing `bundle.sha256` gives one finding naming stage `A`. **FAIL:** no finding.
```

**R11 — `modules/interfaces/docs/resim_contract/RCT_Implementation_Design.md`.** Directly after the line that contains

```
| `[ ]` | `IMP-0048` |
```

insert (no blank line):

```
| `[ ]` | `IMP-0049` | `SYS-0044` | `WP-13` | `EXTEND` | `src/adas_recording/writer.py::McapRecorder` — an optional `config_bundle` argument, key `<stage>/<relative path>` → that file's exact text, written as metadata `config_bundle` in sorted key order when given and absent otherwise; a key with an empty stage or path is refused before the file opens. | `SYT-REC-05` |
| `[ ]` | `IMP-0050` | `SYS-0044` | `WP-13` | `EXTEND` | `scripts/check_recording.py` — when `config_bundle` is present, per stage (a key's part before its first `/`): the stage's files written as they are to a temporary folder and hashed by `pack_config_bundle.bundle_sha256`, the one hash code, then compared with the stage's `bundle.sha256` text; a mismatch, or files without `bundle.sha256`, is one finding naming the stage. | `SYT-REC-04`, `SYT-REC-05` |
| `[ ]` | `IMP-0051` | `SYS-0043` | `WP-13` | `NEW` | `vantage`: each target's build writes `adas_recording.path` beside its `simengine`, naming the `python/` folder of the `adas-interfaces` package in that target's own lock; `src/adas_sim/io/recording_writer.py` reads the file beside the `simengine` it runs and imports `adas_recording` from there. A missing file or folder is an error naming the build to run; no sibling path, no search. | `ANL-06` |
| `[ ]` | `IMP-0052` | `SYS-0037`, `SYS-0041` | `WP-13` | `EXTEND` | `vantage` engine's writer, its `manifest` (`VANTAGE_Architecture.md` §11) — `run_kind: resim`; `source_kind`, and the origin of every topic the run did not compute, from the input recording; `components` the simulated stages with their `build_id`; each port's `record` policy from the run setup; never `created_utc`. An input that does not state one is refused at load, naming it; no default. | `SYT-REC-04` |
```

**R12 — `modules/interfaces/docs/resim_contract/RCT_Implementation_Design.md`.** Replace

```
Holds the engine's writer and Vantage's reader to the same conventions.
```

with

```
Holds the engine's writer and Vantage's reader to the same conventions; the optional `config_bundle` block lands in the Python writer and the check with its first producer, the engine (`D26`).
```

**V1 — `modules/vantage/docs/VANTAGE_System_Requirements.md`.** Replace

```
Priority split: 24 `P0`, 26 `P1`,
```

with

```
Priority split: 24 `P0`, 28 `P1`,
```

**V2 — `modules/vantage/docs/VANTAGE_System_Requirements.md`.** After the line that contains

```
**Verify.** T · `SYT-RUN-10`   **Trace.** —
```

insert one blank line and then:

```
**`SYS-0052`** · `P1` · `R1` — An engine-run recording embeds each simulated stage's config bundle
**Shall.** An engine run shall write into its recording's `config_bundle` block (`RCT:SYS-0044`) the bundle folder each simulated stage was initialised with (`R-SIM-6`).
**Accept.** On `running_example` `cut_c` the block names exactly the simulated stages, holds each one's files with their text as on disk, and each stage's `bundle.sha256` equals the setup's `config_bundle_sha256` for it; anything else fails.
**Binds.** `runSetup`, `runRecording`
**Verify.** T · `SYT-RUN-11`   **Trace.** —
```

**V3 — `modules/vantage/docs/VANTAGE_System_Requirements.md`.** Replace

```
| T | 47 |
```

with

```
| T | 49 |
```

**V4 — `modules/vantage/docs/VANTAGE_Test_Spec.md`.** After the line that contains

```
- `.c2` **PASS:** each of the three paths writes a setup carrying exactly the configured values.
```

insert one blank line and then:

```
**`SYT-RUN-11`** · T · fixture `F-CASE`, `F-ENGINE` — An engine-run recording embeds the simulated stages' bundles
**Serves.** `SYS-0052`
**Steps.** Run `running_example` `cut_c` on `F-ENGINE`. Read the engine-run recording's `config_bundle` block, each stage's bundle folder (`config/` beside its library) and each stage's `config_bundle_sha256` in the setup.
- `.c1` **PASS:** the block names exactly the simulated stages, each with its folder's files and text, per `SYS-0052` Accept. **FAIL:** a stage missing or extra (`C` is `measured`), or a file missing, extra or different.
- `.c2` **PASS:** each stage's `bundle.sha256` text equals the setup's hash for it. **FAIL:** any differs.
```

**V5 — `modules/vantage/docs/VANTAGE_Implementation_Design.md`.** Directly after the line that contains

```
- [x] **WP-08** — Source checks · Scan the code `WP-02` to `WP-05` write.
```

insert (no blank line):

```
- [ ] **WP-12** — The engine-run recording's config bundle · Lands with `RCT:WP-13`, whose engine writer it extends; `WP-09`'s `SYT-RUN-11` reads it.
```

**V6 — `modules/vantage/docs/VANTAGE_Implementation_Design.md`.** Directly after the line that contains

```
    RCT13["RCT:WP-13<br/>engine recording"] --> WP09
```

insert (no blank line):

```
    RCT13 --> WP12["WP-12<br/>bundle block"]
    WP12 --> WP09
```

**V7 — `modules/vantage/docs/VANTAGE_Implementation_Design.md`.** Replace the whole line that starts with

```
| `[ ]` | `IMP-0044` |
```

with

```
| `[ ]` | `IMP-0044` | `SYS-0001`, `SYS-0002`, `SYS-0003`, `SYS-0004`, `SYS-0005`, `SYS-0006`, `SYS-0007`, `SYS-0008`, `SYS-0046`, `SYS-0048`, `SYS-0052` | `WP-09` | `NEW` | `tests/system/test_vnt_run_setup.py` — `SYT-RUN-01` to `SYT-RUN-11`. | `SYT-RUN-01`, `SYT-RUN-02`, `SYT-RUN-03`, `SYT-RUN-04`, `SYT-RUN-05`, `SYT-RUN-06`, `SYT-RUN-07`, `SYT-RUN-08`, `SYT-RUN-09`, `SYT-RUN-10`, `SYT-RUN-11` |
```

**V8 — `modules/vantage/docs/VANTAGE_Implementation_Design.md`.** Directly after the line that contains

```
| `[x]` | `IMP-0039` |
```

insert (no blank line):

```
| `[ ]` | `IMP-0059` | `SYS-0052` | `WP-12` | `EXTEND` | `src/simcore/abi/simcore.cpp::simEngineCreate`, `src/simcore/io/codecs/mcap.cpp::McapWriter` — with `outputs.path` set, each simulated stage's bundle folder (`config_path` when given, else `config/` beside its library) is read after its `Init` and written once by `WriteMeta` as `config_bundle`, `<stage>/<relative POSIX path>` → each file's exact text (`RCT:SYS-0044`). | `SYT-RUN-11` |
```

**V9 — `modules/vantage/docs/VANTAGE_Implementation_Design.md`.** Directly after the line that contains

```
| `[~]` | `IMP-0036` |
```

insert (no blank line):

```
| `[ ]` | `IMP-0060` | `SYS-0040` | `WP-07` | `EXTEND` | `src/simcore/module_host/exec_timeout.cpp::ExecTimeout` — under `limits.exec_timeout_ms` each caller (the orchestrator at `threads` 1, each worker above) hands its calls to its own long-lived call thread, with a timed wait. A timeout ends the engine run with outcome `timeout` (`R-SIM-19`) and abandons that thread; the process then refuses every later engine run, saying to restart it. | `SYT-THR-02` |
```

**R13 — `modules/interfaces/docs/resim_contract/layers.yaml`.** Replace

```
    budget: 43
```

with

```
    budget: 44
```

**R14 — `modules/interfaces/docs/resim_contract/layers.yaml`.** Replace

```
    budget: 48
```

with

```
    budget: 54
```

**R15 — `modules/interfaces/docs/resim_contract/layers.yaml`.** Replace

```
# R-REQ-13. Seven contract areas (HDR, CTL, RSY, CST, LMS, VER, REC) x 13 = 91
# = 43 (SYS) + 48 (IMP).
```

with

```
# R-REQ-13. Seven contract areas (HDR, CTL, RSY, CST, LMS, VER, REC) x 14 = 98
# = 44 (SYS) + 54 (IMP).
```

**R16 — `modules/interfaces/docs/resim_contract/layers.yaml`.** Replace

```
  per_unit: 13
  total: 91
```

with

```
  per_unit: 14
  total: 98
```

**R17 — `modules/interfaces/docs/resim_contract/layers.yaml`.** Directly after the line that contains

```
      its packaging in interfaces; the lab's recorder; Vantage's writing).
```

insert (no blank line):

```
  - date: 2026-11-02
    change: "per_unit 13 -> 14 (total 91 -> 98); SYS 43 -> 44, IMP 48 -> 54"
    why: >-
      D26 adds the optional config_bundle block to C6: one SYS row (SYS-0044,
      the block matches its own bundle.sha256) and two IMP rows (the Python
      writer's argument, the conformance check). Two D14 fixes found while
      building WP-13 add two more IMP rows: how Vantage's Python finds the
      interfaces writer (IMP-0051, the path file), and the engine's writer
      writing C6's manifest (IMP-0052). The D24 wrap reworded SYS-0004 and
      added no contract row. Two IMP rows of room are left because the basis
      moves in steps of seven.
```

## Part B — `interfaces` (`RCT:IMP-0049`, `RCT:IMP-0050`)
1. `IMP-0049`: `McapRecorder`'s optional `config_bundle` argument, as the row says. A call without
   it writes a file byte-identical to today's (`SYT-REC-03` `.c1` keeps passing).
2. `IMP-0050`: `check_recording.py` checks `config_bundle` as the row says, importing
   `bundle_sha256` from `pack_config_bundle.py` beside it (both ship in the package's `scripts/`);
   files written with their text unchanged (`newline=""`). No second hash code anywhere. Update
   the script's docstring list of conventions.
3. `SYT-REC-05` `.c1`..`.c3` in `tests/python/` (name the file), citing the ids verbatim.
4. Rebuild the package: `build.bat -t package -p vs2026` in `modules\interfaces`; report the new
   `adas-interfaces/1.1.0` revision. Vantage's next build picks it up (R-BUILD-7); do **not**
   rebuild `vantage-lab`.

## Part C — `vantage`
5. `RCT:IMP-0051`: each target's build writes `adas_recording.path` (one line, the folder) into
   the folder its `simengine` executable is built to, from the `adas-interfaces` package folder
   that target's CMake was given from its own lock — never one file at `conan_workarea/` root,
   since each target has its own lock and the last build would win. `src/adas_sim/io/
   recording_writer.py` (new) reads the file beside the `simengine` the Python side runs (the one
   `bridge.py` resolves), puts the folder on `sys.path` and returns the writer; a missing file, or
   a folder without `adas_recording/writer.py`, raises an error naming the build to run. No
   sibling path, no second candidate list, no environment variable.
6. `RCT:IMP-0048`, Vantage's Python side: `McapWriter` and the `.mcap` writer registration leave
   `src/adas_sim/io/mcap.py` (the reader stays); `sim convert` no longer writes `.mcap`;
   `bridge.py`'s `overwrite_manifest_meta`, `backfill_schema_bytes` and its merged-write path go
   (the engine now writes its own `manifest` and `config_bundle`, steps 7 and 8);
   `sources/recorder.py` (`sim record`) writes `.mcap` through `recording_writer.py` (provenance as
   the writer requires; a `plugin_bundles` block is no longer written — it waits for the viewer
   phase). Grep for every other user. A function this leaves unused goes too; name each.
7. `RCT:IMP-0052`: the engine's writer writes `manifest` as the row says, before the first
   message, no clock read, and never a `created_utc` (the engine has no logging time, and one
   would break C6's byte-identical rule, `SYT-REC-03` `.c3`). An input that does not state `source_kind` or a carried topic's origin
   makes `simEngineCreate` refuse `outputs.path` naming the input and the missing item.
8. `IMP-0059`: the `config_bundle` block as the row says. gtest: an engine run on a stub chain
   with a two-file bundle (one in a subfolder) gives exactly those keys and texts; a `measured`
   stage gives none; no `outputs.path`, no block.
9. `IMP-0060`: the call thread as the row says; the exit code on a timeout is `kSimExitTimeout`.
   After a timeout, every later `simEngineCreate` or run in that process is refused with an error
   saying to restart the process: the stuck thread is still inside the component's library, and a
   second run could load it alongside (batch already runs one process per recording). gtest: with
   a timeout set and one thread, a test component sees one thread id over many calls; a call that
   blocks past the timeout ends the run with the timeout outcome; a second engine created in the
   same process afterwards is refused with that error. `SYT-THR-02`'s steps stay as written (the lab setups
   keep their 250 ms).
10. Tests in `tests/system/` (name the file), citing the ids verbatim: `SYT-REC-03` `.c3`
    (`simengine` twice on `running_example` `cut_c` with `outputs.path`, files byte-identical) and
    `SYT-REC-04` `.c1`..`.c3`, on the lab's `base.mcap` and that engine-run recording;
    `check_recording.py` and `check_one_recording_writer.py` are taken from the package the path
    file names (`scripts/` beside `python/`). Vantage's recording reader is the C++ `Reader`
    (`include/simcore/io.hpp`); if a Python test can reach it only through a new executable, add
    it under `tests/support/` as `step_tap` is, and name it. `ANL-06` `.c2` in `tests/unit/`
    (the check over vantage's `src/`). A test whose lab output is missing skips with a printed
    reason.

## Part D — builds, suites, boxes (once, at the end)
11. `modules\interfaces`: `build.bat -t gtest -p vs2026` and its Python suite `tests/python`.
    `modules\vantage`: `build.bat -t sil -p vs2026`, `-t gtest` (last 415/415), `-t package`;
    Python `tests/unit tests/system` (last 1158 passed, 87 skipped). Root:
    `py -3.12 scripts\check_invariants.py`; `trace_check --status` on both doc sets.
12. Boxes. `RCT:IMP-0048`..`IMP-0052` `[x]` when their tests pass; `RCT` `WP-13` as the rollup
    gives. `IMP-0059` and `IMP-0060` `[~]`, each row gaining at its end, before the test column,
    "Closed by `SYT-RUN-11` passing (`WP-09`)." and "Closed by `SYT-THR-02` passing (`WP-09`)."
    respectively; `WP-12` `[~]`, its line gaining at its end " Closed by `SYT-RUN-11` passing
    (`WP-09`)." (`SYT-RUN-11` itself is written in `09b`). The orchestrator dry-ran this final
    state: both checks PASS, `RCT WP-13` `[x]` 5/5, `VNT WP-12` `[~]` 0/1, `VNT WP-07` `[~]` 0/4.

## Exit check (run all, report output and seconds)
- Each build command and suite: pass/fail, seconds; counts before and after, each test removed or
  corrected by name.
- The new `adas-interfaces` revision, and each lock file that changed.
- `SYT-REC-03` `.c3`, `SYT-REC-04`, `SYT-REC-05`, `ANL-06` `.c2` results; the `config_bundle` keys
  of the `cut_c` engine-run recording (`A`, `B`, `D`, `E`, never `C`) and its `manifest` text;
  where each target's `adas_recording.path` was written, and its line.
- `check_invariants.py` clean; both `trace_check` PASS, the `RCT WP-13`, `VNT WP-07`, `VNT WP-12`
  lines.
- `git status --short` in `modules/vantage` and `modules/interfaces`; each `git diff --stat` equal
  with and without `--ignore-cr-at-eol`.

## Must not
- change any doc text beyond Part A and the boxes of step 12, or `VANTAGE_DEV_PLAN.md`
- change `modules/vantage-lab`, rebuild it, or edit its lock
- add a second Python recording writer, a Python reader for `config_bundle`, a `plugin_bundles`
  block, or a code default for a run-setup or provenance value
- move `bundle_sha256` (a later clean-up package does that), or write the `09b` system test files
  (`SYT-RUN-*`, `SYT-THR-*`, …)
- decide anything the rows leave open — report it with your recommendation

## Report back in this shape
1. Done / not done, in one line per part.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds (R-TEST-7).
4. Boxes ticked (row ids), and any `[~]` with what closes it.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
