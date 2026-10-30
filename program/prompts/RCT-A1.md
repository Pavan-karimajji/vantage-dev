# RCT-A1 — "Equal outputs" leaves out cycle_counter (contract amendment, owner-approved)

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`. Never reset, clean, stash,
  checkout or commit anything. `modules/interfaces` holds other uncommitted work
  (WP-01..03): leave every file not listed under "Allowed changes" untouched.
- `VANTAGE_DEV_PLAN.md` §2 (decisions D1–D15; D14 says what the contract is)
- `modules/interfaces/docs/resim_contract/RCT_System_Requirements.md`: the
  preamble, `SYS-0003`, `SYS-0007`, `SYS-0016`
- `modules/interfaces/docs/resim_contract/RCT_Test_Spec.md`: `SYT-CTL-02`, `SYT-RSY-04`
- `modules/interfaces/docs/resim_contract/RCT_Architecture.md`: the two
  `cycle_counter` rows (own count, +1 per run, restarts with the process)
- `.claude/rules/requirements.md` (R-REQ-3, R-REQ-4, R-REQ-14)

## The problem (decided; do not reopen)
`SYS-0003` says a component's `cycle_counter` counts its own runs, +1 per run,
and a RESTART does not reset it. `SYS-0007` asks for byte-identical `dataOut`
after a mid-run RESTART and in a fresh process, but the fresh process counts
from 1, so the headers always differ and `SYS-0007` can never pass. `SYS-0016`
fails the same way whenever a re-run does not start at the recording's first
run. `SYT-CTL-02` and `SYT-RSY-04` inherit it.

**Owner decision (2026-10-30):** keep counting through RESTART (`SYS-0003`
unchanged). Define *equal outputs* once in the SYS preamble as byte-identical
except each header's `cycle_counter`, and use that term in `SYS-0007` and
`SYS-0016`. This amends the frozen contract with the owner's approval (D14).

## Goal
The SYS preamble defines *equal outputs*; `SYS-0007`, `SYS-0016`,
`SYT-CTL-02` and `SYT-RSY-04` use it; the decision is D16 in the plan; and
`trace_check` is clean.

## Allowed changes
- `modules/interfaces/docs/resim_contract/RCT_System_Requirements.md`
- `modules/interfaces/docs/resim_contract/RCT_Test_Spec.md`
- `VANTAGE_DEV_PLAN.md` (§2 only: one new row)
- Everything else is read-only. All three files use CRLF line endings: keep them.

## Steps
1. In the SYS preamble, after the **Subjects** paragraph, add one paragraph.
   Suggested wording (you may tighten it, not change its meaning):
   **Equal outputs.** Two `dataOut` sequences are *equal* when they hold the
   same number of messages and each pair is byte-identical once both headers'
   `cycle_counter` is set to 0. `cycle_counter` is left out because it counts
   the sender's runs since its process started (`SYS-0003`), and a RESTART does
   not reset it.
2. `SYS-0007` Accept: replace "byte-identical `dataOut`" with equal `dataOut`
   (citing the preamble term). Shall unchanged.
3. `SYS-0016` Accept: the same; the comparison is the re-run's `dataOut`
   against the recorded `dataOut`. Shall unchanged.
4. `SYT-CTL-02` `.c1` and `SYT-RSY-04` `.c1`: PASS reads "equal", per the
   cited Accept (do not restate the definition, R-REQ-4); FAIL reads "any byte
   differs outside `cycle_counter`" (keep `SYT-RSY-04`'s "naming topology,
   component and run").
5. Grep both documents for every other "byte-identical". Change none of them;
   list each in your report with one line on whether it compares across
   processes or across a RESTART (where the counters could differ).
6. `VANTAGE_DEV_PLAN.md` §2: add row D16, dated 2026-10-30, in the table's
   style: `cycle_counter` keeps counting through RESTART; *equal outputs*
   (SYS preamble) leave it out; amends `SYS-0007`, `SYS-0016`, `SYT-CTL-02`,
   `SYT-RSY-04`; owner-approved contract change under D14.

## Exit check (run all, report output and seconds)
- `python .claude/templates/requirements/trace_check.py --set modules/interfaces/docs/resim_contract`
  → PASS, no findings (use whichever Python runs it; say which).
- `grep -n -i "equal" modules/interfaces/docs/resim_contract/RCT_System_Requirements.md modules/interfaces/docs/resim_contract/RCT_Test_Spec.md`
- `git diff --stat` in `modules/interfaces` and in the superproject → only the
  three allowed files changed by you (the WP-01..03 files were already modified;
  confirm you did not touch them: their `git diff` is unchanged).
- `file` on the three files → still CRLF.

## Must not
- commit, push, or change files outside "Allowed changes"
- change `SYS-0003`, any Shall, any other requirement or test, or any proto
- change the meaning of any other "byte-identical" (step 5 is report-only)
- add features, abstractions or error handling not asked for

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked: none expected.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation (include step 5's list here).
