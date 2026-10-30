# PRE-G1b — Remove a study-notes folder name, split writing step 6, record D15

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`. It holds uncommitted work: never
  reset, clean, stash or checkout anything.
- `VANTAGE_DEV_PLAN.md` §2 (decision table), §4 (*The lab*), §6 (writing order),
  §8 (sources)

## Goal
The plan names no 1v study-notes folder (its name carries a reference tool's
name, which must not appear in tracked files), writing step 6 is split into the
five steps the owner approved, and the owner's register decision is D15.

## Allowed changes
- `VANTAGE_DEV_PLAN.md` only. It uses CRLF line endings: keep them.
- Everything else is read-only.

## Steps
1. **§4, *The lab*.** The bullet "The fake car reuses the executable model
   already written" continues with a backticked 1v path in parentheses, then
   "as its timing logic." Replace the parenthesis (backticked path and the words
   "in 1v, study notes") with "(in 1v's git-ignored sim study notes)". The bullet
   keeps its other words.
2. **§8, *Sources*.** Replace the whole "Evidence" bullet (two lines, starting
   "- Evidence (study notes, git-ignored in 1v):") with exactly:
   "- Evidence: the sync-and-scheduling notes, the experiments and the scheduler
   executable model, in 1v's git-ignored sim study notes."
3. **§6, writing order.** Replace row `| 6 | …` with these five rows, and change
   the "Depends on" cell of row 7 from `5, 6` to `5, 6a` and of row 8 from
   `6, 7` to `6a–6e, 7`:
   ```
   | 6a | `VANTAGE_Architecture.md` (frozen before 6b) | 5 |
   | 6b | `VANTAGE_Migration_Register.md` part 1: sim code reused / replaced / corrected / new; the disposition words; the register check script (D15) | 6a |
   | 6c | Register: disposition of every sim v2 SYS row | 6b |
   | 6d | Register: disposition of every sim v2 SW row (two worker packages) | 6b |
   | 6e | Register: disposition of every row of the sim v2 parity set | 6b |
   ```
4. **§2.** Add as the last row of the decision table, one line like the others:
   "| D15 | **The migration register disposes every sim v2 row exactly once.** An
   implementation (IMP) row inherits the disposition of the SW rows it serves;
   only exceptions are listed. A check script computes the inheritance and fails
   on any sim v2 UID that is missing or listed twice. | 2026-10-30 |"

## Exit check (run all, report output and seconds)
- `grep -n -i "bench" VANTAGE_DEV_PLAN.md` → no line refers to a 1v study-notes
  folder (report every hit and why it is fine).
- `grep -n "^| 6\|^| 7 \|^| 8 \|^| D15" VANTAGE_DEV_PLAN.md` → the five 6x rows,
  rows 7 and 8 with their new dependencies, D15.
- `git diff --stat` → only `VANTAGE_DEV_PLAN.md` changed by you (already
  modified before you started: `VANTAGE_DEV_PLAN.md` itself,
  `program/ORCHESTRATION_LEDGER.md`, `program/prompts/`, `modules/interfaces`).
- `file VANTAGE_DEV_PLAN.md` → still CRLF.

## Must not
- commit, push, or change files outside "Allowed changes"
- reword, reorder or "improve" any other text
- write any reference tool, reference repository or company name, or any path
  into the study notes, into any file
- decide anything not stated here — report it instead

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked: none expected.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
