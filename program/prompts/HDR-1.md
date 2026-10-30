# HDR-1 — check_headers expects COMPONENT: VANTAGE on new files

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`. Never reset, clean, stash, checkout or
  commit anything. Other workers edit other files now; touch only the allowed ones.
- `.claude/rules/naming.md` R-NAME-5, R-NAME-6; `.claude/rules/style.md` R-STYLE-1
- `modules/vantage/scripts/check_headers.py`, `modules/vantage/tests/unit/test_a1_check_headers.py`
- `modules/vantage/docs/VANTAGE_Migration_Register.md`, the `scripts/check_headers.py` row
  in §3 (`corrected`: the token becomes `VANTAGE`)
- `modules/vantage/scripts/check_migration_register.py`, `read_seed_entries`: how the
  tree at the tag `seed-from-sim` (the sim tree as forked, D2) is read once with
  `git ls-tree -r --name-only seed-from-sim` and injected for tests.

## Goal
The header check expects `COMPONENT: VANTAGE` (R-NAME-6). A file that already existed
at `seed-from-sim` may still carry `COMPONENT: SIM` (inherited files are not mass
re-headed, the same spirit as R-NAME-5); every other file must carry `VANTAGE`. The
two current violations (`scripts/check_migration_register.py`,
`tests/unit/test_check_migration_register.py`, both headed `VANTAGE`) are gone.

## Allowed changes
- `modules/vantage/scripts/check_headers.py`
- `modules/vantage/tests/unit/test_a1_check_headers.py`
- Everything else is read-only.

## Steps
1. In both header patterns accept the token `VANTAGE`, or `SIM` only when the file's
   path relative to the vantage root is in the seed tree. Read the seed tree once per
   run with `git -C <vantage root> ls-tree -r --name-only seed-from-sim`; keep it
   injectable (a parameter with a default) so tests need no git repository.
2. If the tag is missing, print one line `check_headers: seed-from-sim tag not found;
   COMPONENT: SIM accepted nowhere` and go on with `VANTAGE` only (it fails loudly
   rather than passing silently).
3. Update the docstring and the comment near `_EXCLUDE_FILES` that say `COMPONENT: SIM`
   so they state the new rule in one sentence each. Change the file's own header only if
   it is not in the seed tree (it is, so leave it).
4. Tests: a new file headed `SIM` fails; a seed file headed `SIM` passes; a new file
   headed `VANTAGE` passes; a seed file headed `VANTAGE` passes; the planted cases use an
   injected seed list. Keep every existing test passing.

## Exit check (run all, report output and seconds)
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev\modules\vantage && C:\ws\venvs\rct-pytest\Scripts\python.exe -m pytest tests\unit\test_a1_check_headers.py -q"` → all pass.
- `python3 modules/vantage/scripts/check_headers.py` → `check_headers: clean`.
- `git -C modules/vantage status --short` → only the two allowed files modified, plus
  the untracked files already there (list them).

## Must not
- commit, push, or change files outside "Allowed changes"
- re-head any existing file; change any other check
- add options or checks not asked for

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked: none expected.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
