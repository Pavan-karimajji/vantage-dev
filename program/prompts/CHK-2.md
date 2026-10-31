# CHK-2 — the requirement checker rolls up any `<PREFIX>-WP-nn` build order

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`. Never commit, and never run `git checkout`,
  `git stash`, `git reset`, `pkill` or `kill`: if a step seems to need one, stop and report.
  Another worker edits `modules/vantage/docs/` (not `layers.yaml`) now.
- Owner decision (2026-10-31): the checker's rollup pattern is made general — a package id
  `<PREFIX>-WP-<n>` for any prefix, not lab-only — so it back-ports to 1v at migration as a plain
  improvement; recorded in `.claude/IMPORTED.md`.
- `.claude/rules/requirements.md` R-REQ-6a and R-REQ-17 (the rollup, `C-ROLLUP-EMPTY`),
  `.claude/templates/requirements/trace_check.py` (how a `context:` entry with `rollup: true` finds
  its packages and rows, and its `--selftest`), `.claude/IMPORTED.md`
- The case that forced it: `modules/vantage/docs/VANTAGE_Lab_Design.md` §9 (`LAB-WP-nn`,
  `LAB-nn`); `modules/vantage/docs/layers.yaml` (the comment where `rollup: true` was left out)

## Goal
A `rollup: true` document whose packages are `<PREFIX>-WP-<n>` rolls up like `WP-<n>`; the lab
design is declared with `rollup: true` and `--status` shows its packages.

## Allowed changes
- `.claude/templates/requirements/trace_check.py` (the package-id pattern only, and one
  `--selftest` planted case), its test file in `.claude/templates/requirements/` if one covers the
  rollup; `.claude/IMPORTED.md` (one *Local changes* row, the file's line endings kept).
- `modules/vantage/docs/layers.yaml`: `rollup: true` on the lab design's `context:` entry, and
  the comment that explains its absence removed.
- Everything else is read-only.

## Steps
1. Widen the package-id pattern so `<PREFIX>-WP-<n>` (any uppercase prefix) is a package exactly
   like `WP-<n>`; rows stay matched as today. Nothing else in the checker changes.
2. Add a planted `--selftest` case: a `<PREFIX>-WP-<n>` package whose box disagrees with its rows
   fails `C-WPROLL`.
3. Append to `IMPORTED.md` *Local changes*:
   `| 2026-10-31 | `templates/requirements/trace_check.py` | Rollup package ids generalised to `<PREFIX>-WP-<n>` (any prefix) | back-port to 1v at migration (a plain improvement) |`
4. Declare `rollup: true` on the lab design in `modules/vantage/docs/layers.yaml`.

## Exit check (run all, report output and seconds)
- `python3 .claude/templates/requirements/trace_check.py --selftest` → every planted case caught
  (one more than before).
- `trace_check.py --set modules/vantage/docs` → PASS and `--status` showing `LAB-WP-01`..`10`
  (the lab design's packages) rolled up; `--set modules/interfaces/docs/resim_contract` → PASS;
  `--set .claude/templates/requirements/example` → PASS (no other set changes).
- `git status --short` → only the allowed files (others may be another worker's: list them).

## Must not
- commit, push, or change files outside "Allowed changes"
- change any other check or the meaning of an existing id

## Report back
Done / not done; files changed; the exit check with seconds; deviations; open questions with your
recommendation.
