Your role: read .claude/agents/vantage-builder.md and follow it.
Keep the report under 40 lines, in the §4.2 shape.

# VNT-WP-09b-2 — C1: the system tests of input selection, the engine step, threads and equal outputs (`IMP-0046`..`IMP-0048`), and run pairing by counter (`IMP-0033`, vantage `c1`)

The second half of `09b` (`09b-1` landed `SYT-RUN`, `SYT-ORC`; vantage `c1` `4c12393`). Four parts,
in order: **A** two doc edits, exactly; **B** one engine fix the owner asked for; **C** the three
test files; **D** builds, suites, boxes. Gate G3 (`IMP-0043`, `SYT-EQO-01`, `SYT-THR-01`) is `09c`.

## Context (read these, nothing else unless a step needs it)
- Working copy `C:\ws\repo\vantage-dev`, native Windows (`vs2026`). `modules/vantage` is on
  branch **`c1`** — stay on it. Never run `git checkout`, `git switch`, `git stash`, `git reset`,
  `git rm`, `git restore`, `git add`, `git commit`, `git push`, `pkill` or `kill`.
- **Owner conditions for `c1`:** every commit builds the whole of vantage and passes its full unit
  suite; a test of the old behaviour that can no longer pass is corrected in the same change, and
  you name it.
- Rules: `.claude/rules/style.md` (file header on every new file, minimal diffs), `testing.md`,
  `requirements.md` R-REQ-4 (a test cites an `Accept` by UID, never restates it), R-REQ-5 (a case
  passes or fails, its FAIL side as written), R-REQ-9 (the test id and case id appear verbatim in
  the test implementing it).
- Python: `modules\vantage\.venv-sim-win32\Scripts\python.exe`; the lab's,
  `modules\vantage-lab\.venv-lab-win32\Scripts\python.exe`. Never `py -3`. Root scripts: `py -3.12`.
- Read: `VANTAGE_Test_Spec.md` — the fixture catalogue, §4 `SEL`, §5 `STP`, §6 `THR`, §7 `EQO`
  whole; `VANTAGE_Implementation_Design.md` rows `IMP-0046`, `IMP-0047`, `IMP-0048` (**build exactly
  these**), `IMP-0032`, `IMP-0033` (after Part A), `IMP-0040`..`IMP-0042`, `IMP-0055`; the `Accept` of
  each `SYS` row a test serves (`VANTAGE_System_Requirements.md`); `VANTAGE_Architecture.md` §6 and
  §7 *Where equal outputs apply* (after Part A); `VANTAGE_Lab_Design.md` §6.
- Support already built — reuse it, never copy it: `tests/support/engine_runs.py` (engine and
  `step_tap` runs, `Recording`, `compare_recordings`, `point_at_recording`, `stage_of`,
  `library_with_bundle`), `tests/support/lab_cases.py` (`lab_case`, `edit_setup`,
  `edit_recording`), `tests/support/step_tap.cpp`, `tests/fixtures/exec_probe/` (`F-PROBE`),
  `tests/support/recordings.py`; `F-COMPARE` is the lab's `lab_tools.compare.equal_outputs`.
  `tests/system/test_vnt_orchestrator.py` shows the house shape. The lab outputs of every
  topology are generated on this machine (`modules/vantage-lab/lab/`).
- **Fact the orchestrator established** (read the code before relying on it): the run's outputs are
  paired with the recording by instant — `Runner::FinishTicket` (`cycle_loop.cpp`) calls
  `impl.reference.AtTime(output.port, now_ns)`. So a run that waited compares with nothing or with
  another run's output, and two runs of one stage in one step (`IMP-0061`) compare with the same
  recorded output. `RecordedReference::Find(port, counter)` and `ReadAhead::Find` already look up by
  `measurement_counter`. The owner's instruction: pair by `measurement_counter`, not by step.

## Part A — doc edits (exact)
Every edit below is decided. Each anchor and each new text is the exact content of a fenced block
(the fence lines themselves excluded). Apply each by exact-string replacement, keeping each file's
line endings (both LF). If an anchor is not found exactly once, stop and report it; never adjust
the text to make a check pass. The orchestrator has dry-run both edits: `trace_check` PASS, 114
requirements, 52 tests, no findings, and PASS again in the final box state of step 11.

**E1** · `modules/vantage/docs/VANTAGE_Architecture.md` · replace the anchor with the new text.

Anchor:
````
output and `compState` with the recording's. It zeroes both headers'
````
New text:
````
output and `compState` with the recorded output of the same port and
`measurement_counter`, never by instant: a run that waited, or the second run of a
stage in one step, is compared with its own recorded run. The recorded output is
looked up among the arrived messages, then in the read-ahead; none found, the
output is not compared. It zeroes both headers'
````

**E2** · `modules/vantage/docs/VANTAGE_Implementation_Design.md` · replace the anchor with the new text.

Anchor:
````
`src/simcore/runner/divergence.cpp::DivergenceLatch::Observe` — keyed by step; skips RESTART runs;
````
New text:
````
`src/simcore/runner/divergence.cpp::DivergenceLatch::Observe` — given each output with its port's recorded output of the same `measurement_counter`, arrived or read ahead, never by instant (none: not compared); skips RESTART runs;
````

## Part B — pairing by counter (`IMP-0033` as amended, `ARCH §7` *Where equal outputs apply*)
1. In `Runner::FinishTicket`, each committed output is compared with the recorded output of the
   same port whose `measurement_counter` equals the output's own (`ReadSignalHeader`): first among
   the arrived recorded messages (`RecordedReference::Find`), then in the read-ahead
   (`ReadAhead::Find`, held to the readiness limit). None found, or an output whose counter is
   unknown (0): not compared, as today for a port the recording lacks. The same pairing feeds
   `KIND_WARMING_UP` (`IMP-0032`). If `RecordedReference::AtTime` is left with no caller, remove
   it and name it.
2. gtests (owner's planted case), each citing `IMP-0033`: (a) a stage that runs twice in one step
   with both outputs equal to their recorded runs → no `first_divergence`; (b) the first of the
   two runs differs → `first_divergence` on that stage and port; (c) only the second differs →
   reported the same way; (d) a run that waited for a sample and ran steps after its recorded run
   is compared with its own recorded output → no divergence when equal, reported when not. A
   correct pair must never be reported as divergent.

## Part C — the three test files
3. `IMP-0046`: `tests/system/test_vnt_selection.py` — `SYT-SEL-01` to `SYT-SEL-13`.
4. `IMP-0047`: `tests/system/test_vnt_step.py` — `SYT-STP-01` to `SYT-STP-06`.
5. `IMP-0048`: `tests/system/test_vnt_equal_outputs.py` — `SYT-THR-02`, `SYT-THR-03`,
   `SYT-EQO-02` to `SYT-EQO-04`.
6. One test per case `.cN`, each naming its test and case id verbatim (`SYT-SEL-12.c2`), its
   assertion message naming the FAIL side the spec states. A case over every lab case is
   parametrized, each parameter a lab case. A helper two files need goes in
   `tests/support/engine_runs.py`, never in a second copy.
7. **A skip is only for a lab output that is missing, or a case that needs the supervisor
   (`hang`, `crash`, part 8b)**, with a printed reason naming what is missing. Never `xfail`, never
   a weakened or dropped assertion, never a tolerance the spec does not give. A step the spec
   leaves open (how to find "the middle" run, which `B` refSync entry to edit) is chosen so the
   case can fail, and named in the report.
8. **A failing case is a finding, not yours to hide.** If the engine is wrong and the fix lies
   inside an existing design row's text (name the row), make it with a unit test and say so. If
   the fix needs a decision a row does not state, or the spec itself is wrong, leave the case
   failing, stop working on it, and report it with file, case, what was seen and your
   recommendation.

## Part D — builds, suites, boxes (once, at the end)
9. `modules\vantage`: `build.bat -t sil -p vs2026`, `-t gtest` (last 428/428), `-t package`;
   Python `tests/unit tests/system` (last 1295 passed, 85 skipped). Root:
   `py -3.12 scripts\check_invariants.py`;
   `py -3.12 .claude/templates/requirements/trace_check.py --set modules/vantage/docs --status`.
10. Report per new test file: cases passed / failed / skipped, each failure and skip with its id.
11. Boxes, only for rows whose cases all pass: `IMP-0046`, `IMP-0047`, `IMP-0048` to `[x]` (a file
    with a failing or skipped case stays `[~]`, gaining at its end, before the test column,
    "Closed by `<those case ids>` passing."). Then every `[~]` row whose "Closed by" names only
    tests that now all pass goes to `[x]`, its "Closed by …" sentence removed; a row naming
    `SYT-THR-01`, `SYT-EQO-01`, `G3` or any test not yet written stays `[~]` unchanged. If every
    case passes, the orchestrator's dry run expects these rows to flip: `IMP-0005`, `0009`, `0010`,
    `0017`, `0020`, `0021`, `0022`, `0023`, `0026`, `0027`, `0029`, `0030`, `0031`, `0032`, `0033`,
    `0036`, `0060`, `0041`, `0042`, and the three files; and `WP-01`, `WP-05`, `WP-06` by the
    rollup (their "Closed by" removed). `C-WPROLL` and `C-PLANMARK` clean. List every row you flip.

## Exit check (run all, report output and seconds)
- Each build command and suite: pass/fail, seconds, counts before and after; each corrected test
  by name.
- Each new gtest by name; whether `AtTime` was removed.
- Per new test file: cases passed / failed / skipped, each failure and skip with its id and reason.
- Each engine fix of step 8 with its row and unit test.
- `check_invariants.py` clean; `trace_check` PASS and the `WP` lines.
- `git -C modules/vantage status --short`; `git diff --stat` equal with and without
  `--ignore-cr-at-eol`.

## Must not
- change any doc text beyond Part A and step 11's boxes and "Closed by" sentences, the contract
  (`modules/interfaces`), or anything under `modules/vantage-lab`
- write `SYT-EQO-01`, `SYT-THR-01` or the G3 gate (`09c`); touch the engine's manifest keys, the
  refSync search bound or the live measurement (the producer-keys package)
- add a skip, tolerance or exemption no step names
- decide anything the rows leave open — report it with your recommendation

## Report back in this shape
1. Done / not done, in one line per part.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds (R-TEST-7).
4. Boxes ticked (row ids), and any `[~]` with what closes it.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
