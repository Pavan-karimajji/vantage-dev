# VG-1 — vantage .gitignore: keep the study-notes rule, drop the name

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`; submodule `modules/vantage`.
  Never reset, clean, stash, checkout or commit.
- `modules/vantage/.gitignore`, lines ~110-120: a comment and the rule
  `/misc/<name>_bench/` for a git-ignored study-notes folder.

## Goal (owner decision)
The rule still ignores that folder (at migration `vantage` replaces sim inside
1v, where the folder exists on disk; without the rule it could be committed by
accident), but neither the rule nor its comment names it or any tool.

## Allowed changes
- `modules/vantage/.gitignore` only: that rule and the comment lines directly
  above it that belong to it.

## Steps
1. Replace the rule with `/misc/*_bench/`.
2. Reword its comment in plain English: local study notes and experiments, never
   committed; name no tool, no folder name, no company. Keep it to 1-3 lines, and
   drop any reference to a README inside the ignored folder.
3. Keep the file's line endings.

## Exit check (run all, report output)
- `git -C modules/vantage diff .gitignore` → shown in full.
- `git -C modules/vantage check-ignore -v misc/x_bench/a.md` → matched by the new rule
  (a path check only; create nothing).
- `grep -n -i "bench" modules/vantage/.gitignore` → only the new rule and its comment.
- `git -C modules/vantage status --short` → only `.gitignore`.

## Must not
- commit, push, or change any other line or file
- name the old folder, any tool, or any company in the file, the report text
  included (say "the old name")

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail.
4. Boxes ticked: none expected.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
