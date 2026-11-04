Your role: read .claude/agents/vantage-builder.md and follow it.
Keep the report under 45 lines, in the §4.2 shape.

# VNT-CLEAN-1-R1 — only a recording that is cut off is damaged; and the test suites run in parallel (vantage `c2`)

The rework of `VNT-CLEAN-1`, widened. Its work is in the working copy, uncommitted: **build on it,
never revert it.** **If Part A is already in the working copy** (an earlier run of this prompt did it:
`Open` keeps a problem only for a status other than `MissingStatistics`, and the summary-less gtest
exists), check it and go straight to Part B; report Part A as "found done". Two parts: **A** the reader defect; **B** a parallel test runner, so the full gate
takes about a minute instead of six, with not one test left out. Then **C** the exit check.

## Context
- Working copy `C:\ws\repo\vantage-dev`, native Windows (`vs2026`). `modules/vantage` on **`c2`** —
  stay on it. Never run `git checkout`, `git switch`, `git stash`, `git reset`, `git rm`,
  `git restore`, `git add`, `git commit`, `git push`, `pkill` or `kill`.
- **Run everything natively on Windows (PowerShell or cmd), not from WSL**: the last full suite took
  1713 s from WSL and 352 s natively on the same tree.
- Python: `modules\vantage\.venv-sim-win32\Scripts\python.exe`. Root scripts: `py -3.12`.
- Rules: `.claude/rules/testing.md` (R-TEST-1..7), `style.md` (file header on a new file).

## Part A — the reader defect
`src/simcore/io/codecs/mcap.cpp` `McapReader::Open` calls any recording "cut off" whose summary does
not parse with `ReadSummaryMethod::NoFallbackScan`, and the run ends with exit 5. But in the mcap
library (Conan cache, `include/mcap/reader.inl`, `readSummarySection_` ≈ line 407) a file with a
**valid footer** and no summary, or no statistics record, returns `StatusCode::MissingStatistics` — a
whole file, valid mcap, which other producers may write. Only a file whose footer cannot be read
(`ReadFooter` fails: no trailing magic, a short file, an invalid footer) is cut off.
1. In `Open`: set `open_problem_` only when the strict read fails with a status other than
   `StatusCode::MissingStatistics`; on `MissingStatistics`, read with `AllowFallbackScan` exactly as
   before `VNT-CLEAN-1`, with no problem kept. One comment line says why.
2. gtest in `tests/unit/test_ut_io_mcap_roundtrip.cpp`, beside
   `UtIo22McapRoundtrip.ARecordingCutMidMessageNearItsEndFailsTheReadWithExitCodeInput`, citing what it
   cites: a recording written by the engine's writer with statistics and summary turned off
   (`McapWriterOptions`: `noStatistics`, `noSummaryOffsets`, and whatever else leaves the summary empty
   — say which) reads every message and reports no problem; the cut-off gtest still fails.

## Part B — the suites in parallel, nothing skipped
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

## Part C — exit check (run all natively, report output and seconds)
7. `build.bat -t gtest -p vs2026`; gtest **serially once** (last 483/483 + Part A's) and through
   `run_tests.py --gtest` (same count).
8. Python: serially once `tests/unit tests/system` (last 1772 passed, 62 skipped); then `run_tests.py --python tests/unit tests/system` three times — each the same counts,
   0 failed; the five G4 files through the runner (168 passed, none skipped) and
   `tests/system/test_vnt_read_problem.py`.
9. `py -3.12 scripts\check_invariants.py`; `git -C modules/vantage diff --stat` equal with and without
   `--ignore-cr-at-eol`; `git status --short` (the durations file is not listed).

## Must not
- leave a test out of the parallel run except through the reported serial tail; skip, retry,
  `xfail`, or change a test's pass criterion
- add a Python package to the environment, or change `.claude/` rules
- change engine behaviour beyond step 1
- commit or push

## Report back in this shape
1. Done / not done, one line per part.
2. Files changed, one line each (group the isolation fixes).
3. Exit check output: each command, pass/fail, seconds — serial vs parallel on one line each.
4. The serial tail, each test with its reason (expected: empty or very short).
5. Deviations, each with the reason.
6. Open questions, each with your recommendation.
