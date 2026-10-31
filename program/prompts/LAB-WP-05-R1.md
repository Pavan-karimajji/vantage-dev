# LAB-WP-05 rework 1 — the loader test expects the three running-example scenarios

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`. Never reset, clean, stash, checkout or
  commit anything.
- `modules/vantage-lab/tests/unit/test_topology.py`, `test_lab07_running_example_loads_clean`
- `modules/vantage-lab/catalogue/running_example.yaml` now holds scenarios `base`, `restart`,
  `fault` (LAB-33, landed by LAB-WP-05).

## Goal
The full lab test run is green: the assertion lists the scenarios the file now holds.

## Allowed changes
- `modules/vantage-lab/tests/unit/test_topology.py`, the one assertion only.

## Steps
1. Change `assert [s.name for s in topology.scenarios] == ["base"]` to `assert [s.name for s in topology.scenarios] == ["base", "restart", "fault"]`. The next line (resim cases of `scenarios[0]`) stays as it is.

## Exit check (run all, report output and seconds)
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev\modules\vantage-lab && python -m pytest tests -q"` → all pass (83 expected).
- `git -C modules/vantage-lab diff --stat tests/unit/test_topology.py` → 1 insertion, 1 deletion.

## Must not
- commit, push, or change anything else

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked: none expected.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
