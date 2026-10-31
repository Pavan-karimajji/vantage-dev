# PRG-1 — the package-build rule in the review checklist

## Context
- Working copy: `/mnt/c/ws/repo/vantage-dev`. Never commit, and never run `git checkout`,
  `git stash`, `git reset`, `pkill` or `kill`. Touch only the allowed file.
- Owner decision (2026-10-31): a package that changes what a component ships runs that
  component's package build in its exit check.

## Allowed changes
- `program/VANTAGE_PROGRAM.md` §5, the *Scope and process* list only.

## Steps
After the line `- [ ] Every exit-check command was run and passed, with output shown.` add exactly:
`- [ ] A package that changes what a component ships (its installed files, its package layout, its recipe inputs) ran that component's real package build (`-t package`) in its exit check; an editable build or the tests alone do not prove it.`
Keep the file's line endings.

## Exit check
- `grep -n 'real package build' program/VANTAGE_PROGRAM.md` → the one new line.
- `git diff --stat` → only `program/VANTAGE_PROGRAM.md` (plus files already modified before you
  started; list `git status --short` first).

## Report back
Done / not done; the exit check output.
