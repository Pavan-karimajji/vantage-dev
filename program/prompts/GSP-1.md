# GSP-1 — stop pytest from collecting test_gen_sil_ports.py

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev` (Windows path `C:\ws\repo\vantage-dev`);
  submodule `modules/interfaces`, branch `vantage`, with uncommitted work from
  other packages: keep it. Never reset, clean, stash, checkout or commit.
- `modules/interfaces/tests/python/test_gen_sil_ports.py` (a standalone script:
  "Run directly"; its `test_*` functions take a `tmp` path its own `main` passes)
- `.claude/rules/style.md` (R-STYLE-2, minimal diff)

## Goal
`pytest tests/python` no longer collects this file (today it reports 9 setup
errors, "fixture 'tmp' not found"), and running it directly still passes 9/9.
The smallest change that does this, as its own commit later (owner decision).

## Allowed changes
- `modules/interfaces/tests/python/test_gen_sil_ports.py` only.

## Steps
1. Add, just below the imports, a module-level `__test__ = False` with a one-line
   comment saying why (a standalone script, run directly; pytest must not collect
   it). Change nothing else.

## Exit check (run all, report output and seconds)
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev\modules\interfaces && C:\ws\venvs\rct-pytest\Scripts\python.exe -m pytest tests\python -q"`
  → no errors; report the counts (the file must not appear).
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev\modules\interfaces\tests\python && C:\ws\venvs\rct-pytest\Scripts\python.exe test_gen_sil_ports.py"` → "All 9 test functions passed."
- `git -C modules/interfaces diff tests/python/test_gen_sil_ports.py` → shown in full.

## Must not
- commit, push, or change any other file
- rename the tests or the `tmp` parameter, add a fixture, or add a pytest config

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked: none expected.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
