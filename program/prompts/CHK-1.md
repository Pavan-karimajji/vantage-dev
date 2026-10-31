# CHK-1 — the register check proves carried rows are placed in the Vantage set

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`. Never commit, and never run `git checkout`,
  `git stash`, `git reset`, `pkill` or `kill`: if a step seems to need one, stop and report.
  Another worker is writing `modules/vantage/docs/` now (the Vantage set, and the register's
  Targets); touch no document.
- Owner decision (2026-10-31): every `carried` register row is re-pointed, part by part in step 8,
  from Target `VNT` to the `VNT:SYS-nnnn` rows that state it; the check proves it.
- `modules/vantage/scripts/check_migration_register.py` (how it reads the RCT set, `load_rct`,
  and how it checks a Target, `check_target`), `modules/vantage/tests/unit/test_check_migration_register.py`,
  the register's §2.1 and §5; `modules/vantage/docs/layers.yaml` and
  `VANTAGE_System_Requirements.md` may not exist yet (the other worker is creating them)

## Goal
The check resolves every `VNT:<UID>` Target against the Vantage set, reports on every run how
many carried UIDs still say bare `VNT`, and, with one flag, fails on any; each new rule has a
planted case.

## Allowed changes
- `modules/vantage/scripts/check_migration_register.py`, `modules/vantage/tests/unit/test_check_migration_register.py`.
- Everything else is read-only.

## Steps
1. Read the Vantage set's SYS UIDs from `modules/vantage/docs/` the way `load_rct` reads the RCT
   set (the SYS document `layers.yaml` names; the same row pattern), injectable for tests.
2. New finding `C-PLACE`: a `carried` Target `VNT:<UID>` whose UID is not in the Vantage set (or
   the set does not exist yet). Only `VNT:SYS-nnnn` is a valid placement.
3. Every run prints one line: carried UIDs placed, still bare `VNT`, and how many of the latter by
   register section. Not a finding.
4. `--require-placed`: any carried UID still bare `VNT` is a `C-PLACE` finding (used once step 8c
   is done).
5. Tests and `--selftest` cases, each planted: a `VNT:SYS` UID that exists passes; one that does
   not fails `C-PLACE`; a bare `VNT` passes without the flag and fails with it. Nothing else in
   the script's behaviour changes.

## Exit check (run all, report output and seconds)
- `python3 -m pytest modules/vantage/tests/unit/test_check_migration_register.py -q` → all pass.
- `python3 modules/vantage/scripts/check_migration_register.py --selftest` → every planted case
  caught (more than today's 11).
- `python3 modules/vantage/scripts/check_migration_register.py | tail -4` → the new placement line
  and, as long as no Target is re-pointed, 0 findings.

## Must not
- commit, push, or change files outside "Allowed changes"; touch any document
- add features, options or error handling not asked for

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked: none expected.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
