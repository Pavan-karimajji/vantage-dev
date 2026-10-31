# DR-1 rework 1 — the two leftovers

## Allowed changes
- `modules/interfaces/docs/resim_contract/RCT_Implementation_Design.md` line 41 (*Blocked, and
  by what*): "the component description file" becomes "the topology file" (D20, `Q-L5`).
- `modules/vantage/docs/VANTAGE_Lab_Design.md` §8: the *CMake* row lists `CMakePresets.json`;
  the *Build stub* row lists `requirements.lock`. Nothing else.

## Exit check
- `grep -n "description file" modules/interfaces/docs/resim_contract/RCT_Implementation_Design.md` → none.
- `python3 .claude/templates/requirements/trace_check.py --set modules/interfaces/docs/resim_contract` → PASS.
- `git -C modules/interfaces diff --stat`; `git -C modules/vantage diff --stat` → only these files.

## Must not
- commit, push, or change anything else.

## Report back
Done / not done; files changed; exit check output with seconds.
