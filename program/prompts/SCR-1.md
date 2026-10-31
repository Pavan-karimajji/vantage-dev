# SCR-1 — remove the two screening agents from vantage-dev

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`. Never reset, clean, stash, checkout or
  commit anything. Touch only the allowed files.
- Owner decision (2026-10-31): the screening agents leave this workspace; screening runs
  from 1v-superproject. Git history is kept as it is.
- `.claude/IMPORTED.md` (the record of what this `.claude/` holds and every local change)
- `.claude/routing.md`, `program/VANTAGE_PROGRAM.md` §1

## Goal
`.claude/agents/threat-screening.md` and `.claude/agents/ip-provenance-scan.md` no longer
exist in the working copy; no tracked file outside `program/ORCHESTRATION_LEDGER.md` and
`program/prompts/` names either agent, except the `.gitignore` lines, which stay; the
removal is recorded in `.claude/IMPORTED.md`.

## Allowed changes
- Delete `.claude/agents/threat-screening.md` and `.claude/agents/ip-provenance-scan.md`
  (plain `rm`; do not run `git rm`).
- `.claude/routing.md`: delete the one table row that starts `| **Before any push** |`.
- `.claude/IMPORTED.md`:
  - in the *Imported* table, the `agents/` row's Files cell becomes `low-effort-worker`;
  - append one row at the bottom of the *Local changes* table, exactly:
    `| 2026-10-31 | `agents/threat-screening.md`, `agents/ip-provenance-scan.md` | Removed: screening runs from 1v-superproject, not from this workspace (owner decision) | none (1v keeps them) |`
- `program/VANTAGE_PROGRAM.md` §1: the sentence
  `The imported agents (`low-effort-worker`, `threat-screening`, `ip-provenance-scan`) are not program workers.`
  becomes `The imported agent `low-effort-worker` is not a program worker.` Keep the line
  wrapping of the paragraph around it; change nothing else.
- Everything else is read-only, `.gitignore` included.

## Steps
1. Delete the two files.
2. Make the three edits above, exactly as written.
3. Run the exit check.

## Exit check (run all, report output and seconds)
- `ls .claude/agents/` → `low-effort-worker.md`, `vantage-builder.md`,
  `vantage-mechanic.md`, `vantage-planner.md` only.
- `grep -rn -E 'threat-screening|ip-provenance-scan' --exclude-dir=.git --exclude-dir=modules . | grep -v -E '^\./program/(ORCHESTRATION_LEDGER\.md|prompts/)|^\./\.gitignore:'`
  → only the new `IMPORTED.md` row.
- `git status --short` and `git diff --stat` → the two deletions and the three edited files,
  nothing else.

## Must not
- commit, push, stage, or change files outside "Allowed changes"
- edit `.gitignore` or any other agent file
- reword anything beyond the exact edits above

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked: none expected.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
