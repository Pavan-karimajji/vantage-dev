Your role: read .claude/agents/vantage-builder.md and follow it.
Keep the report under 40 lines, in the §4.2 shape.

# VNT-WP-09a — C1: one recording writer (`RCT:WP-13`), then the test support of `WP-09` (vantage `c1`)

`WP-09` needs `RCT:WP-13` (the design's package graph) and is too large for one session, so it is
split: **09a** (this) — `RCT:WP-13` and the three support tools; **09b** — the system test files;
**09c** — gate G3. Two parts here; do A completely, then B. If A stops on something you cannot
resolve, report it and still do B, which does not depend on A.

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
  it), `.claude/rules/sim.md` R-SIM-11 (no sibling checkout *required*).
- Python: vantage's own environment, `modules\vantage\.venv-sim-win32\Scripts\python.exe`; the
  lab's, `modules\vantage-lab\.venv-lab-win32\Scripts\python.exe`. Never `py -3`. Root scripts:
  `py -3.12`.

## Part A — `RCT:WP-13`: one recording writer
**Read:** `modules/interfaces/docs/resim_contract/RCT_Implementation_Design.md` row `IMP-0048`
(package `WP-13`), and `IMP-0043` (the `interfaces` writer, `src/adas_recording/writer.py`);
`RCT_Test_Spec.md` `SYT-REC-03` (`.c3`), `SYT-REC-04`, `ANL-06` (`.c2`), fixtures `F-WRITER`,
`F-ENGINE-REC`, `F-LAB`, `F-SRC-PY`; `RCT_Architecture.md` §6a; `VANTAGE_Architecture.md` §11
*Recording I/O*; `modules/interfaces/scripts/check_one_recording_writer.py`, `check_recording.py`.
Users of the writer to remove, today: `src/adas_sim/io/mcap.py` (`McapWriter`),
`src/adas_sim/engine/bridge.py`, and tests `tests/system/test_a4_recordings.py`,
`test_c6_determinism_cli.py`, `tests/unit/test_a4_legacy.py`, `test_a4_mcap.py`, `test_b2_tick.py`,
`test_c8_plugins.py`, `test_si15_orchestrate.py` — grep again.

1. `IMP-0048` as written: `McapWriter` leaves `mcap.py`; every Vantage Python path that writes a
   recording goes through `IMP-0043`'s writer; the engine's C++ writer keeps `§6a` and reads no
   clock; Vantage's reader reads both writers' recordings. **How Vantage's environment finds
   `adas_recording`** — follow how the lab finds it if that fits R-SIM-11; if it needs a choice the
   row leaves open (a dependency, a path, a package), stop Part A and report the options with
   your recommendation.
2. Tests, citing the ids verbatim: `ANL-06` `.c2` in vantage's unit suite (the check over
   vantage's `src/`); `SYT-REC-03` `.c3` and `SYT-REC-04` `.c1`..`.c3` in `tests/system/` (name
   the file), on a lab recording and an engine-run recording (`F-ENGINE-REC`: `simengine` on a lab
   case with `outputs.path` set). A test whose lab output is missing skips with a printed reason.
3. Box: `RCT:IMP-0048` `[x]` when its tests pass; `RCT` `WP-13` as the rollup gives
   (`trace_check --set modules/interfaces/docs/resim_contract --status`).

## Part B — `WP-09`'s test support (`IMP-0040`, `IMP-0041`, `IMP-0042`)
**Read:** `modules/vantage/docs/VANTAGE_Implementation_Design.md` rows `IMP-0040`..`IMP-0042`
(**build exactly these**); `VANTAGE_Test_Spec.md` fixture catalogue (`F-CAT`, `F-CASE`,
`F-SETUP-EDIT`, `F-REC-EDIT`, `F-TAP`, `F-PROBE`); `VANTAGE_Lab_Design.md` §6 (the lab cases,
where the lab build puts them, `index.json`).

4. `IMP-0040`: `tests/support/lab_cases.py` — `lab_case`, `edit_setup`, `edit_recording` as the row
   says; finds a case's setup, recording and libraries in the lab build; `edit_recording` writes
   through the `interfaces` writer; skips with a printed reason when the lab is not built.
   `pytest` unit tests for it (finding a case, one setup edit, one recording edit, the skip).
5. `IMP-0041`: `tests/support/step_tap.cpp` as the row says (one JSON line per step: step, time,
   badges; `--threads N`; `--jump-at-ms F --jump-to-ms T`), registered in `tests/CMakeLists.txt`.
   Run it on `running_example` `cut_c` and once with a jump; report the first 3 lines of each.
6. `IMP-0042`: `tests/fixtures/exec_probe/exec_probe.cpp` as the row says, built by the standard
   build. Run `simengine` on `diamond` `all_simulated` with the probe as every stage (separate
   copies), `--threads 1` and `--threads 2`; report the thread ids seen in each call log.
7. Boxes: `IMP-0040`..`IMP-0042` `[~]`, each row gaining at its end, before the test column,
   "Closed by `<its test column's ids>` passing (`WP-09`)."; `WP-09` as the rollup gives, with a
   "Closed by" clause if `C-PLANMARK` asks for one.

## Builds, suites (once, at the end)
8. `build.bat -t sil -p vs2026`, `-t gtest` (last 415/415), `-t package` in `modules\vantage`;
   Python `tests/unit tests/system` in its own environment (last 1151 passed, 87 skipped);
   interfaces' Python suite in the environment its earlier packages used (say which), if Part A
   changed anything there; `py -3.12 scripts\check_invariants.py` at the root; `trace_check
   --status` on both `modules/vantage/docs` and `modules/interfaces/docs/resim_contract`.

## Exit check (run all, report output and seconds)
- Each build command: pass/fail, seconds; counts before and after, each test removed or corrected
  by name.
- Steps 5 and 6 output as asked; the `ANL-06` and `SYT-REC-*` results.
- `check_invariants.py` clean; both `trace_check` PASS, the `RCT WP-13` and `VNT WP-09` lines.
- `git status --short` in `modules/vantage` and `modules/interfaces`; each `git diff --stat` equal
  with and without `--ignore-cr-at-eol`.

## Must not
- write the system test files of `IMP-0043`..`IMP-0048` (`09b`, `09c`)
- change the `interfaces` writer's behaviour or the contract text; change `modules/vantage-lab`
- add a second Python recording writer anywhere, or a code default for a run-setup value
- decide anything the rows leave open — report it with your recommendation

## Report back in this shape
1. Done / not done, in one line per part.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds (R-TEST-7).
4. Boxes ticked (row ids), and any `[~]` with what closes it.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
