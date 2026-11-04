Your role: read .claude/agents/vantage-builder.md and follow it.
Keep the report under 30 lines, in the §4.2 shape.

# VNT-CLEAN-1-R1 — only a recording that is cut off is damaged; a whole recording with no summary still reads (vantage `c2`)

The rework of `VNT-CLEAN-1`. Its work is in the working copy, uncommitted: **build on it, never
revert it.** One defect, in `src/simcore/io/codecs/mcap.cpp` `McapReader::Open`: any recording whose
summary does not parse with `ReadSummaryMethod::NoFallbackScan` is now called "cut off" and the
run ends with exit 5. But in the mcap library (`reader.inl`, `readSummarySection_`) a file with a
**valid footer** and no summary section, or no statistics record, returns
`StatusCode::MissingStatistics` — a whole file, valid mcap, which other producers may write. Only a
file whose footer cannot be read (`ReadFooter` fails: no trailing magic, a short file, an invalid
footer) is cut off.

## Context
- Working copy `C:\ws\repo\vantage-dev`, native Windows (`vs2026`). `modules/vantage` on **`c2`** —
  stay on it. Never run `git checkout`, `git switch`, `git stash`, `git reset`, `git rm`,
  `git restore`, `git add`, `git commit`, `git push`, `pkill` or `kill`.
- Python: `modules\vantage\.venv-sim-win32\Scripts\python.exe`. Root scripts: `py -3.12`.
- The mcap library's reader is in the Conan cache (`include/mcap/reader.inl`): `readSummary`,
  `readSummarySection_` (line ≈407; returns `MissingStatistics` when the summary held no statistics).

## Steps
1. In `Open`: set `open_problem_` only when the strict read fails with a status other than
   `StatusCode::MissingStatistics`; on `MissingStatistics`, read with `AllowFallbackScan` exactly as
   before `VNT-CLEAN-1`, and keep no problem. Say in one line of the comment why.
2. gtest in `tests/unit/test_ut_io_mcap_roundtrip.cpp`, beside
   `UtIo22McapRoundtrip.ARecordingCutMidMessageNearItsEndFailsTheReadWithExitCodeInput` and citing what
   it cites: a recording written by the engine's writer
   with statistics and summary turned off (`McapWriterOptions`: `noStatistics`, `noSummaryOffsets`,
   and whatever else leaves the summary empty — say which) reads every message and reports no
   problem; the existing cut-off gtest still fails with damaged input.
3. No other change.

## Exit check (run all, report output and seconds)
4. `build.bat -t gtest -p vs2026`; gtest (last 483/483, plus the new one).
5. Python `tests/system/test_vnt_read_problem.py` and the five G4 files (168 passed, none skipped).
6. Python `tests/unit tests/system` once (last 1772 passed, 62 skipped); `py -3.12 scripts\check_invariants.py`.
7. `git -C modules/vantage diff --stat` equal with and without `--ignore-cr-at-eol`.

## Must not
- change anything but step 1 and step 2's test
- add a skip, tolerance, retry or `xfail`
- commit or push

## Report back in this shape
1. Done / not done.
2. Files changed, one line each.
3. Exit check output: each command, pass/fail, seconds.
4. Deviations, each with the reason.
5. Open questions, each with your recommendation.
