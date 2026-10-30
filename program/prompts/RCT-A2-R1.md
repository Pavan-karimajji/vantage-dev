# RCT-A2 rework 1 — warming-up and readiness-limit wording (owner review)

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev` (Windows path `C:\ws\repo\vantage-dev`);
  submodule `modules/interfaces`, branch `vantage`, with the uncommitted RCT-A2
  change: keep it. Never reset, clean, stash, checkout or commit anything.
- `VANTAGE_DEV_PLAN.md` §2, D17 (4)
- `modules/interfaces/docs/resim_contract/RCT_Implementation_Design.md`: the
  *Message fields* rows `MeasDescription` 7 and `MeasBadge.Kind` `KIND_WARMING_UP`
- `modules/interfaces/proto/livemeas/meas_description.proto` (`readiness_limit_steps`)
- `modules/interfaces/proto/livemeas/meas_cycle.proto` (`KIND_WARMING_UP` comment)
- `modules/interfaces/docs/resim_contract/RCT_Architecture.md`: the `Q3` row

## Goal (owner review of RCT-A2; text only, no field number or name changes)
1. `KIND_WARMING_UP` means what D17 (4) says, in the field table and the proto comment.
2. `readiness_limit_steps` has one meaning for every value: 0 is a real limit
   ("never waits": fall back at once). The run setup always has a limit and the
   writer always writes it, so "not set" is dropped everywhere.

## Allowed changes
- `modules/interfaces/docs/resim_contract/RCT_Implementation_Design.md` (the two rows only, LF)
- `modules/interfaces/proto/livemeas/meas_description.proto` (the field comment only, LF)
- `modules/interfaces/proto/livemeas/meas_cycle.proto` (the `KIND_WARMING_UP` comment only)
- `modules/interfaces/docs/resim_contract/RCT_Architecture.md` (the `Q3` row only, CRLF)
- Everything else is read-only. Keep each file's line endings.

## Steps
1. Field table, `KIND_WARMING_UP` "Means" cell → exactly:
   `stage: started mid-recording; badged until its outputs first equal the recorded outputs, only when the recording holds them`
2. `meas_cycle.proto`, the trailing comment on `KIND_WARMING_UP = 2;` → the same
   words (wrap onto a comment line above the value if the line gets too long; keep
   the file's style).
3. Field table, `MeasDescription` 7 "Means" cell → exactly:
   `run setup: how many steps a run may wait for a named sample before it falls back; 0 = never waits; value ⊘ (RCT_Architecture.md Q3)`
4. `meas_description.proto`, the comment above `readiness_limit_steps` → two lines:
   `// The readiness limit: how many steps a run may wait for a named sample`
   `// before it falls back. Set by the run setup; 0 = never waits.`
5. `RCT_Architecture.md` `Q3` "Why it is open" cell → add "; 0 = never waits"
   after `MeasDescription.readiness_limit_steps`, keeping "value ⊘".

## Exit check (run all, report output and seconds)
- `python3 .claude/templates/requirements/trace_check.py --set modules/interfaces/docs/resim_contract`
  (from the vantage-dev root) → PASS, 78 requirements, no findings.
- `check_rct_schema.py --fields`, run as in RCT-A2 (`C:\ws\venvs\rct-pytest\Scripts\python.exe`
  via `cmd.exe`, from `modules\interfaces`) → PASS.
- `grep -rn "not set\|started cold" modules/interfaces/docs/resim_contract modules/interfaces/proto/livemeas` → no hits.
- `git -C modules/interfaces diff --stat` → only the RCT-A2 files plus `meas_cycle.proto`.
- `file` on the four edited files → line endings as before.

## Must not
- commit, push, or change files outside "Allowed changes"
- change any field number, name, type, requirement, test or box
- add features, abstractions or error handling not asked for

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked: none expected.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
