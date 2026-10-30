# PLN-1 — owner decisions of 2026-10-30/31 into the plan and the program

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`. Never reset, clean, stash, checkout or
  commit anything. Other workers edit other files now; touch only the allowed ones.
- `VANTAGE_DEV_PLAN.md` §2 (rows D8, D15, D18) and §6 (rows 6c, 6d). The file has CRLF
  line endings; keep them.
- `program/VANTAGE_PROGRAM.md` §1 (the "Which worker" table). CRLF; keep them.
- `program/CONCEPT_PAGE_DIVERGENCES.md`

## Goal
The plan and the program state the owner's decisions word for word as given below,
and the concept-page divergence file is gone.

## Allowed changes
- `VANTAGE_DEV_PLAN.md`, `program/VANTAGE_PROGRAM.md`; delete
  `program/CONCEPT_PAGE_DIVERGENCES.md` (plain delete, not `git rm`).
- Everything else is read-only.

## Steps
1. `VANTAGE_DEV_PLAN.md` row D8: replace `one orchestrator (Opus, medium) writes prompts
   for workers (Sonnet, medium/high) and reviews every result.` with `one orchestrator
   (Opus, high) writes prompts for workers and reviews every result; worker models per
   D19.` Change its date cell to `2026-10-30, amended 2026-10-31`.
2. Row D15: replace the whole decision cell with:
   `**The migration register disposes every sim v2 row exactly once.** An implementation (IMP) row inherits the disposition of the SW rows it serves; only exceptions are listed. A whole sim v2 section whose rows all share one fate may get **one** disposition, written as a UID range with the section name and the reason. A check script expands every range to its rows, computes the inheritance and fails on any sim v2 UID that is missing or disposed twice.`
   Date cell: `2026-10-30, ranges 2026-10-31`.
3. Add a row after D18:
   `| D19 | **Worker models.** Planning documents (requirement sets, design rows, test specs, architecture or contract changes) go to an Opus worker at high effort. Migration-register rows go to a Sonnet worker at high effort, and the orchestrator checks every disposition and range against the frozen architecture before accepting. Code, build and mechanical edits go to a Sonnet worker at medium or high effort. Which agent type does which kind of work: \`program/VANTAGE_PROGRAM.md\` §1. | 2026-10-31 |`
   (write the backticks plainly, without the backslashes).
4. §6 row 6c: decision cell becomes `Register: disposition of every sim v2 CN and SYS row (two worker packages: CN, SYS)`.
   Row 6d: `Register: disposition of every sim v2 SW row (two worker packages, split at SW-0188 / SW-0189)`.
5. `program/VANTAGE_PROGRAM.md` §1: replace the three body rows of the "Kind of work
   package | Agent type" table with these four:
   `| planning: requirement sets, design rows, test specs, architecture documents, contract changes (step 8 included) | \`vantage-planner\` (Opus, high) |`
   `| migration-register rows (6c-6e); the orchestrator checks every disposition and range against the frozen architecture (6a) before accepting | \`vantage-builder\` (Sonnet, high) |`
   `| building with judgment: code, debugging a failing build or test | \`vantage-builder\` (Sonnet, high) |`
   `| mechanical: an exact edit, a rename, wiring a build list, running a fixed command list | \`vantage-mechanic\` (Sonnet, medium) |`
   Then, right after the table, add one sentence as its own paragraph:
   `The model and effort in brackets are for reading; each agent's file under \`.claude/agents/\` is the one place they are set (D19).`
   (no backslashes in the file).
6. Delete `program/CONCEPT_PAGE_DIVERGENCES.md`. Then `git grep -n "CONCEPT_PAGE_DIVERGENCES"`
   and report every hit outside `program/ORCHESTRATION_LEDGER.md` and `program/prompts/`
   (do not edit them; report only).

## Exit check (run all, report output and seconds)
- `grep -n "^| D8 \|^| D15 \|^| D19 \|^| 6c \|^| 6d " VANTAGE_DEV_PLAN.md` → the new texts.
- `grep -n "vantage-planner\|vantage-builder\|vantage-mechanic\|one place they are set" program/VANTAGE_PROGRAM.md`
- `file VANTAGE_DEV_PLAN.md program/VANTAGE_PROGRAM.md` → both still `CRLF`.
- `git diff --stat` on the two files → only those lines changed.
- `test -e program/CONCEPT_PAGE_DIVERGENCES.md || echo gone` → `gone`.

## Must not
- commit, push, or change files outside "Allowed changes"
- reword anything not named above

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked: none expected.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
