Your role: read .claude/agents/vantage-builder.md and follow it.
Keep the report under 60 lines, in the §4.2 shape.

# VNT-WP-19-22 — the scenario-to-recording script, one place that starts the engine (`IMP-0112`, `--config`/`--timeout-ms` gone), the launcher, the launcher window; one `adas_recording` for lab and engine (vantage `c2`, vantage-lab `main`)

The first 8c build session: four packages, 31 design rows, in build order. **`WP-19`** the
scenario-to-recording script and `sim record` (`D22`); **`WP-20`** one place starts `simengine`
(`bridge.py::run_engine` supervised with a required deadline, its seven callers moved off
`config_path`/`exec_timeout_ms`, the two `simengine` options removed — this lands C2's last row
`IMP-0112` and closes `WP-17`); **`WP-21`** the launcher; **`WP-22`** the launcher window (`D21`).
Plus **Part E**, the lab's stale recording writer. It is a long session on purpose: work package by
package, keep the suite green at the end of each, and stop only for a real decision.

## Context (read these, nothing else unless a step needs it)
- Working copy `C:\ws\repo\vantage-dev`, **native Windows** (PowerShell or cmd, never WSL), `vs2026`.
  `modules/vantage` on **`c2`** (`7e2d12d`), `modules/vantage-lab` on **`main`**, `modules/interfaces`
  on **`vantage`** — stay on them. Never run `git checkout`, `git switch`, `git stash`, `git reset`,
  `git rm` (delete with the shell), `git restore`, `git add`, `git commit`, `git push`, `pkill` or
  `kill`.
- **Owner conditions for `c2`:** every commit builds the whole of vantage and passes its full unit
  suite; a test of old behaviour that can no longer pass is corrected or deleted in the same change,
  and you name it.
- Rules: `.claude/rules/style.md` (file header on every new file, `COMPONENT: VANTAGE`, minimal
  diffs), `naming.md`, `testing.md`, `requirements.md` R-REQ-4/5/9.
- Python: `modules\vantage\.venv-sim-win32\Scripts\python.exe`. Root scripts: `py -3.12`.
- **Tests:** while working, run the files you touch and their importers (R-TEST-1). The full gate is
  the parallel runner: `python.exe scripts\run_tests.py --python tests/unit tests/system` (≈66 s) and
  `--gtest` (≈2 s). A test that starts an engine run gets its setup through
  `tests/support/lab_cases.py::edit_setup` (or writes its own), never `case.setup` straight to the
  engine — that keeps the runner's per-worker live measurement names.
- Read: `VANTAGE_DEV_PLAN.md` `D21`, `D22`, `D31`; `VANTAGE_Architecture.md` §3.1, §11 (launcher,
  run setup writer, engine start from Python, launcher window, scenario to recording);
  `VANTAGE_System_Requirements.md` areas `LCH`, `WIN`, `SCN` (§10–§12) and `SYS-0001`, `SYS-0090`;
  `VANTAGE_Implementation_Design.md` packages `WP-19`..`WP-22` and their rows (`IMP-0125`..`IMP-0153`,
  `IMP-0219`, `IMP-0221`), and `IMP-0103`, `IMP-0112`; `VANTAGE_Test_Spec.md` the `SCN`, `LCH`, `WIN`
  tests, `ANL-07`, `ANL-08`, `ANL-09` and the fixtures `F-LAUNCH`, `F-SPY`, `F-WINDOW`, `F-SCENARIO`.
- **Decided by the orchestrator (the 8c open questions, so you do not stop on them):**
  - The supervised deadline (`SYS-0090`, `SYS-0109`): `run_engine(..., supervise=True)` needs
    `attempt_timeout_ms` or raises naming it; the launcher takes it as a required argument when it
    starts supervised; there is no default anywhere.
  - Fault windows are in steps; the dry run (`IMP-0147`) prints the launcher's resolved setup — no
    engine `--plan-only` option in this session.
- **Facts the orchestrator established** (read the code before relying on them):
  - `bridge.py::run_engine(spec_path, *, config_path=None, exec_timeout_ms=0, simengine_path=None,
    search=(), output_path=None, process_timeout_s=_DEFAULT_PROCESS_TIMEOUT_S)`; callers:
    `check/runner.py:266`, `cli/resim.py:140`, `orchestrate/worker.py:204`, `engine/bridge.py:509`
    (`run_pipeline_via_engine`), `tests/support/engine_runs.py:148`,
    `tests/system/test_a5_it01_config_tree_deleted.py:135`, `tests/unit/test_si15_orchestrate.py`
    (counts `run_engine(` calls). `simEngineCreate`'s C `config_path` and `exec_timeout_ms`
    parameters stay in the ABI (`ABI_VERSION` 5); only the `simengine` options go.
  - `src/simengine/main.cpp`: `Args::config_path`, `exec_timeout_ms`, `BuildChildArgs` forwards
    both to the worker today; `--supervise` and its checks exist (`WP-17`).
  - Existing launcher files (`ARCH §11`): `src/adas_sim/launcher/model.py`, `write.py`, `classify.py`,
    `cuts.py`, `availability.py`; `runspec/emit.py`; `graph/coherence.py`; `config/layers.py`.
    `scenario/` does not exist yet. `cli/record.py` exists (deleted in `WP-19`, `IMP-0129`).
  - `scripts/check_no_graphical_toolkit.py` exists; `IMP-0152` makes it admit `tkinter` in
    `window.py` only.
  - Last counts (`VNT-TEST-1`): gtest 482 passed / 2 skipped of 484; Python 1772 passed /
    62 skipped (collected 1834); `check_invariants` clean.

## Part A — `WP-19` the scenario-to-recording script (`IMP-0125`..`IMP-0131`)
1. As the rows say. The writer is the one in `interfaces` (`adas_recording.writer.McapRecorder`,
   found by `adas_sim.io.recording_writer.recording_writer()`); a scenario recording passes
   `interfaces`' `check_recording.py`. `cli/record.py` and its tests go (name them).

## Part B — `WP-20` one engine start (`IMP-0132`..`IMP-0139`; lands `IMP-0112`)
2. Order inside the package, so nothing is red between steps: first the callers (`IMP-0134`..
   `IMP-0137`) stop passing `config_path`/`exec_timeout_ms` (what they carried goes into the setup:
   the bundle beside the library, `limits.exec_timeout_ms`); then `run_engine` (`IMP-0132`,
   `IMP-0151`'s `command_line`); then the `simengine` options (`IMP-0133`, `BuildChildArgs` too);
   then `check_one_engine_start.py` (`ANL-07`) and `test_vnt_engine_start.py`.
3. A test that passed `--config` or `--timeout-ms` (gtest or Python): corrected to the setup, and
   named.

## Part C — `WP-21` the launcher (`IMP-0140`..`IMP-0148`, `IMP-0221`)
4. As the rows say; `launch` writes the setup and starts it through `run_engine` only.

## Part D — `WP-22` the launcher window (`IMP-0149`..`IMP-0153`, `IMP-0219`)
5. `tkinter` only, every widget command one model call; `test_vnt_window.py` skips with a printed
   reason only where no display exists — on this machine it runs (say so).

## Part E — one `adas_recording` for lab and engine
6. The lab's `index.json` names an `interfaces_python` folder whose `adas_recording` is an older build
   than the one `simengine` was linked with (the engine's `adas_recording.path`): it lacks the
   `config_bundle` argument. Rebuild the lab against the current `adas-interfaces` (the standard
   build; a stale first-party lock pin is refreshed by `R-BUILD-7`/`LK-D10` — report the `lock:` line
   if one prints), and add a vantage test (`tests/unit/test_vnt_one_recording_writer.py`) that fails
   when the lab index's `interfaces_python` and the engine's `adas_recording.path` hold different
   `adas_recording/writer.py` bytes. If the lab cannot be made to agree by a rebuild, stop this part
   and report what pins it.

## Part F — gate and boxes (once, at the end)
7. `build.bat -t sil -p vs2026`, `-t gtest -p vs2026`, `-t package -p vs2026` (install tree check if it
   only exports); `run_tests.py --gtest`; `run_tests.py --python tests/unit tests/system` (counts,
   skip list unchanged except tests you name); vantage-lab unit tests; `py -3.12
   scripts\check_invariants.py`; every new check script with and without `--selftest`.
8. Boxes, only for rows whose tests pass: every row of `WP-19`..`WP-22` `[ ]` → `[x]` and the four
   package lines `- [ ]` → `- [x]`; `IMP-0112` `[ ]` → `[x]`; `IMP-0103` `[~]` → `[x]` deleting
   ` Closed by `IMP-0112`.`; `WP-17` `- [~]` → `- [x]` deleting ` Closed by its rows' tests passing
   (`WP-18`) and `IMP-0112`.`. Expected (the orchestrator's dry run): `trace_check` PASS,
   421 requirements, 156 tests, `packages: 22 done, 0 started, 6 open, of 28`, `design rows: 155 done,
   0 started, 67 open, of 222`. A row whose work did not land stays `[ ]` (or `[~]` saying what closes
   it); list it.
9. `git diff --stat` in vantage and vantage-lab, each equal with and without `--ignore-cr-at-eol`.

## Fix it yourself, or stop
- **Fix yourself** (and name it in the report): a defect in code you wrote here, a test of the old
  behaviour your change makes obsolete, a word-cap or anchor slip in a box edit, a missing include.
- **Stop that item and report** (with what you saw and your recommendation): anything that needs a
  requirement, an Accept, a design row's file or symbol, the run setup schema, the contract or the
  architecture to change; a C1/C2 behaviour change; a test that fails for a reason outside this
  session's rows. Carry on with the other packages.

## Must not
- change any doc text beyond Part F's boxes
- change engine behaviour beyond removing the two `simengine` options
- add a skip, tolerance, retry or `xfail` no step names
- commit or push

## Report back in this shape
1. Done / not done, one line per part.
2. Files changed, one line each (group deletions; name every deleted or corrected test).
3. Exit check output: each command, pass/fail, seconds (R-TEST-7).
4. Boxes ticked (row ids and package lines), and any row left with what closes it.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
