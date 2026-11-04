Your role: read .claude/agents/vantage-builder.md and follow it.
Keep the report under 40 lines, in the §4.2 shape.

# VNT-TEST-1 — the test suites in parallel, nothing skipped (vantage `c2`)

`VNT-CLEAN-1` and its reader fix are committed (vantage `c2` `556ea45`); the working copy is clean.
This package makes the full gate take about a minute instead of six, with not one test left out.

## Context
- Working copy `C:\wsepoantage-dev`, native Windows (`vs2026`). `modules/vantage` on **`c2`** —
  stay on it. Never run `git checkout`, `git switch`, `git stash`, `git reset`, `git rm`,
  `git restore`, `git add`, `git commit`, `git push`, `pkill` or `kill`.
- **Run everything natively on Windows (PowerShell or cmd), not from WSL**: the full suite took
  1713 s from WSL and 349 s natively on the same tree.
- Python: `modulesantage\.venv-sim-win32\Scripts\python.exe`. Root scripts: `py -3.12`.
- Rules: `.claude/rules/testing.md` (R-TEST-1..7), `style.md` (file header on a new file).

## Steps
Measured on this machine (24 logical cores), natively: Python `tests/unit tests/system` 1772 passed,
62 skipped in **352 s**, a long tail of 1–3 s engine runs (one test, `RCT:SYT-LMS-03`, is 60 s by the
contract and stays 60 s); gtest ≈ 50–90 s; the five G4 files ≈ 200–360 s. The suites are
single-process today; nothing in them is slow on its own. Decided:
3. **One runner, no new package.** `scripts/run_tests.py` (vantage, file header, `COMPONENT:
   VANTAGE`): `--workers N` (default: logical cores, at most 16), `--python <paths…>` and/or `--gtest`.
   - *Python:* collect node ids once (`pytest --collect-only -q`), deal them to N `pytest` processes
     (each with `-p no:cacheprovider`, its own `--basetemp`, its own `--junitxml`), longest first from
     `conan_workarea/test_durations.json` (written by the runner after each run, git-ignored; on a
     first run, by file order). Aggregate passed / failed / skipped / errors and print each failure's
     node id and the skip reasons; exit 1 on any failure or error, or when the collected and run
     counts differ.
   - *gtest:* run `simcore_tests.exe` as N shards (`GTEST_TOTAL_SHARDS`, `GTEST_SHARD_INDEX`), aggregate,
     same exit rule.
   - Prints the wall seconds and the sum of per-worker seconds.
   No `pytest-xdist` (it is not in the pinned environment, and adding it is a toolchain release,
   `D25`/R-TEST-5).
4. **Isolation, so parallel equals serial.** Every worker gets `VANTAGE_TEST_WORKER=<n>`. Things that
   are shared today and must not be:
   - *live measurement names* — the lab names a case's live measurement `lab_<topology>_<scenario>_<case>`
     (`lab_tools/setup_writer.py::livemeas_name`), so two workers running one case collide
     (`kLiveMeasNameHeld`). Where the tests copy a setup (`tests/support/lab_cases.py::edit_setup`, and
     any other helper that hands a lab setup to the engine — find them), append `_w<n>` to
     `outputs.livemeas.name` when `VANTAGE_TEST_WORKER` is set. Unset, nothing changes.
   - *fixed temporary paths, fixed file names next to shared inputs, any other process-wide name* the
     suites use: find them by running in parallel; give each a per-worker or per-test path. gtest:
     the integration tests' `TempPath("…")` names, when two shards can meet.
   Fix only isolation; no test's assertion changes. A test that cannot be isolated: report it with
   the reason and keep it in a serial tail the runner runs after the parallel part (`--serial` list in
   the runner, each entry with a one-line reason) — never skipped.
5. **Proof:** the parallel run's passed/skipped/failed counts equal the serial run's exactly; three
   parallel runs in a row are green; report wall seconds for each against the serial baseline.
6. One sentence in `modules/vantage/README.md` (or its test section) naming the runner. No rule file
   changes.

## Exit check (run all natively, report output and seconds)
7. `build.bat -t gtest -p vs2026`; gtest serially once (last 484/484) and through
   `run_tests.py --gtest` (same count).
8. Python: `run_tests.py --python tests/unit tests/system` three times — each 1772 passed, 62 skipped,
   0 failed (the last serial run, 349 s, is the baseline); the five G4 files and
   `tests/system/test_vnt_read_problem.py` through the runner (169 passed, none skipped).
9. `py -3.12 scripts\check_invariants.py`; `git -C modules/vantage diff --stat` equal with and without
   `--ignore-cr-at-eol`; `git status --short` (the durations file is not listed).

## Must not
- leave a test out of the parallel run except through the reported serial tail; skip, retry,
  `xfail`, or change a test's pass criterion
- add a Python package to the environment, or change `.claude/` rules
- change engine behaviour
- commit or push

## Report back in this shape
1. Done / not done.
2. Files changed, one line each (group the isolation fixes).
3. Exit check output: each command, pass/fail, seconds — serial vs parallel on one line each.
4. The serial tail, each test with its reason (expected: empty or very short).
5. Deviations, each with the reason.
6. Open questions, each with your recommendation.
