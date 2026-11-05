Your role: read .claude/agents/vantage-builder.md and follow it.
Keep the report under 70 lines, in the §4.2 shape.

# VNT-WP-23-26 — configuration (the bundle folder key, the load-time checks, wiring order), batch on the supervisor, diagnostics (`--plan-only`, the divergence grace and field), determinism (vantage `c2`)

The second 8c build session: four packages, **60 design rows**, in build order. **`WP-23`**
configuration (24 rows: the engine's bundle and source checks, the `config_bundle_path` key that
replaces `_stage_bundles`, the launcher's load-time checks, wiring order over declaration order so
`feedback` launches); **`WP-24`** the batch on the supervisor (8 rows; `orchestrate/worker.py` goes);
**`WP-25`** diagnostics (22 rows: run report, error parity, `divergence_grace_steps`, the first
differing field, `simengine --plan-only` and the launcher's dry run printing it); **`WP-26`**
determinism (6 rows). It is a long session on purpose: work package by package, keep the suite green
at the end of each, and stop only for a real decision.

## Context (read these, nothing else unless a step needs it)
- Working copy `C:\ws\repo\vantage-dev`, **native Windows** (PowerShell or cmd, never WSL), `vs2026`.
  `modules/vantage` on **`c2`** (`c3e2f70`), `modules/vantage-lab` on **`main`** — stay on them. Never
  run `git checkout`, `git switch`, `git stash`, `git reset`, `git rm` (delete with the shell),
  `git restore`, `git add`, `git commit`, `git push`, `pkill` or `kill`.
- **Owner conditions for `c2`:** every commit builds the whole of vantage and passes its full unit
  suite; a test of old behaviour that can no longer pass is corrected or deleted in the same change,
  and you name it.
- Rules: `.claude/rules/style.md` (file header on every new file, `COMPONENT: VANTAGE`, minimal
  diffs), `naming.md`, `testing.md`, `requirements.md` R-REQ-4/5/9/10, `sim.md` R-SIM-19, R-SIM-24.
- Python: `modules\vantage\.venv-sim-win32\Scripts\python.exe`. Root scripts: `py -3.12`.
- **Tests:** while working, run the files you touch and their importers (R-TEST-1). The full gate is
  the parallel runner: `python.exe scripts\run_tests.py --python tests/unit tests/system` (≈67 s) and
  `--gtest` (≈2 s). A test that starts an engine run gets its setup through
  `tests/support/lab_cases.py::edit_setup` (or writes its own), never `case.setup` straight to the
  engine — that keeps the runner's per-worker live measurement names. A new test that cannot run in
  parallel goes in the runner's `SERIAL` list with a one-line reason, never skipped.
- Read: `VANTAGE_DEV_PLAN.md` `D29`, `D31`, **`D32`**; `VANTAGE_Architecture.md` §2.2, §2.3, §5, §9,
  §11; `VANTAGE_System_Requirements.md` areas `CFG`, `BAT`, `DIA`, `DET`, `EQO` and `SYS-0001`,
  `SYS-0200`..`SYS-0207`; `VANTAGE_Implementation_Design.md` packages `WP-23`..`WP-26` and their rows
  (`IMP-0154`..`IMP-0194`, `IMP-0218`, `IMP-0220`, `IMP-0222`..`IMP-0238`); `VANTAGE_Test_Spec.md` the
  `CFG`, `BAT`, `DIA`, `DET` tests, `SYT-EQO-07`, `SYT-LCH-06`, `SYT-LCH-08`, `SYT-LCH-09`, `ANL-10`
  and the fixtures they name (`F-BUNDLE-EDIT` among them).
- **Decided** (so you do not stop on them):
  - `--plan-only` with `--supervise` prints the plan and exits 0 before any worker starts
    (`IMP-0233` as written); no usage error.
  - `divergence_grace_steps` has no value anywhere in code or in a lab setup (`⊘`); a test that needs
    a grace writes its own value into its own setup copy and says so.
  - The batch's deadline (`attempt_timeout_ms`) is a required argument with no default; a test passes
    its own.
- **Facts the orchestrator established** (read the code before relying on them):
  - `kDefaultGraceTicks` is in `include/simcore/runner.hpp` (lines ≈127–162, `DivergenceLatch`'s
    default argument and member), not in `divergence.cpp`; `IMP-0186` deletes it there.
  - New files: `src/adas_sim/orchestrate/attempts.py`, `src/simcore/diagnostics/run_report.cpp`,
    and the test files `test_vnt_config.py`, `test_vnt_batch.py`, `test_vnt_diagnostics.py`,
    `test_vnt_determinism.py`. Every other file the rows name exists today; read it before changing it.
  - `engine/bridge.py::_stage_bundles` (added in `WP-20`) copies each simulated stage's library folder
    into `<setup>.bundles/<stage>/` so a bundle sits beside it; `IMP-0227` deletes it.
    `sim resim --config` and `sim check --config` keep their option; the folder reaches the engine
    through `config_bundle_path` instead.
  - `graph/pipeline.py::_validate_wiring` (≈line 563) refuses a producer declared at or after its
    consumer; `IMP-0162` orders by wiring instead (`SYS-0206`). The Python `Pipeline.tick` runner
    (≈line 1061, "stages in declaration order") is retired in `WP-28`; if a test of it breaks because
    of the new order, say which and how you kept it.
  - `tests/system/test_si15_orchestrate.py` counts `run_engine(` call sites; `IMP-0177` deletes
    `orchestrate/worker.py`, so its count changes — correct it and name it.
  - Last counts (`VNT-WP-19-22`): gtest 482 passed / 2 skipped of 484; Python 1819 passed /
    62 skipped (collected 1881); `check_invariants` clean.

## Part A — `WP-23` configuration (`IMP-0154`..`IMP-0170`, `IMP-0222`..`IMP-0228`)
1. Order inside the package, so nothing is red between steps: the C++ key and its use (`IMP-0223`,
   `IMP-0224`, then `IMP-0154`, `IMP-0222`, `IMP-0165`, `IMP-0166`, `IMP-0164`, `IMP-0169`); then
   the Python writers (`IMP-0225`, `IMP-0226`, `IMP-0227` — `_stage_bundles` goes, no library copied);
   then the launcher-side checks (`IMP-0155`..`IMP-0163`, `IMP-0167`, `IMP-0168`); then `IMP-0228`
   and `test_vnt_config.py` (`IMP-0170`, `SYT-CFG-01`..`12`).
2. `IMP-0155`: one hash function — if `interfaces`' `pack_config_bundle.py::bundle_sha256` and
   Vantage's differ, the engine's (`CheckBundleHashes`) must agree with the pack step's; report which
   one you made the reference. A change inside `modules/interfaces` is a stop (it is the contract repo).

## Part B — `WP-24` batch on the supervisor (`IMP-0171`..`IMP-0178`)
3. As the rows say. The batch reads `<setup>.attempts.jsonl` (`IMP-0172`) and no longer reads
   `progress.json`; the C++ `Checkpoint` and `checkpoint.path` stay (`D32 (7)`). `orchestrate/worker.py`
   and its tests go (`IMP-0177`; name each test file). `orchestrate/progress.py`/`reopen.py`: if
   nothing imports them after this package, say so — they are deleted in `WP-28`, not here.

## Part C — `WP-25` diagnostics (`IMP-0179`..`IMP-0188`, `IMP-0218`, `IMP-0220`, `IMP-0229`..`IMP-0238`)
4. As the rows say. `IMP-0231`: a gtest or Python test that pins the `first_divergence` entry's exact
   text is corrected in the same change (name it); the manifest's `divergence` string is unchanged.
   `IMP-0233`: `--plan-only` opens no recording, loads no library and writes no file — the test proves
   each (`SYT-DIA-09`). `IMP-0236`: the dry run starts the engine for the plan only; `SYT-LCH-08.c1`
   counts engine runs (`IMP-0237`).

## Part D — `WP-26` determinism (`IMP-0189`..`IMP-0194`)
5. As the rows say (`R-SIM-24`): same-process and fresh-process are exact and fail; rebuilt-binary and
   other-machine are measured and never fail; a pair differing in more than one dimension says so.
   An axis this machine cannot produce (another machine) is tested with a manifest the test writes,
   and says so.

## Part E — gate and boxes (once, at the end)
6. `build.bat -t sil -p vs2026`, `-t gtest -p vs2026`, `-t package -p vs2026` (install tree check if it
   only exports); `run_tests.py --gtest`; `run_tests.py --python tests/unit tests/system` twice (counts,
   skip list unchanged except tests you name; both runs green); vantage-lab unit tests; `py -3.12
   scripts\check_invariants.py`; every new or changed check script with and without `--selftest`.
7. Boxes, only for rows whose tests pass: every row of `WP-23`..`WP-26` `[ ]` → `[x]` and the four
   package lines `- [ ]` → `- [x]`. Expected: `trace_check` PASS, 445 requirements, 162 tests,
   `packages: 26 done, 0 started, 2 open, of 28`, `design rows: 215 done, 0 started, 23 open, of 238`.
   A row whose work did not land stays `[ ]` (or `[~]` saying what closes it); list it, and the
   package line follows its rows (`C-WPROLL`).
8. `git diff --stat` in vantage and vantage-lab, each equal with and without `--ignore-cr-at-eol`.

## Fix it yourself, or stop
- **Fix yourself** (and name it in the report): a defect in code you wrote here, a test of the old
  behaviour your change makes obsolete, a word-cap or anchor slip in a box edit, a missing include.
- **Stop that item and report** (with what you saw and your recommendation): anything that needs a
  requirement, an Accept, a design row's file or symbol, the run setup schema beyond the two `D32`
  keys, the contract (`modules/interfaces`) or the architecture to change; a C1/C2 behaviour change;
  a test that fails for a reason outside this session's rows. Carry on with the other packages.

## Must not
- change any doc text beyond Part E's boxes
- give `divergence_grace_steps` or the batch deadline a default anywhere
- add a skip, tolerance, retry or `xfail` no step names
- commit or push

## Report back in this shape
1. Done / not done, one line per part.
2. Files changed, one line each (group deletions; name every deleted or corrected test).
3. Exit check output: each command, pass/fail, seconds (R-TEST-7).
4. Boxes ticked (row ids and package lines), and any row left with what closes it.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
