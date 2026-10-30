# RCT-A3 — Counter reset vs. identity broken (contract text, owner-approved)

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev` (Windows path `C:\ws\repo\vantage-dev`);
  submodule `modules/interfaces`, branch `vantage`, clean at `c42782d`. The
  superproject has uncommitted work (`program/`, `modules/vantage/docs/`): leave it.
  Never reset, clean, stash, checkout or commit anything.
- `VANTAGE_DEV_PLAN.md` §2, row D17
- `modules/interfaces/include/adas/counter.hpp` (`counterDistance(from, to)`: signed,
  wrap-aware; negative when `to` is earlier)
- `modules/interfaces/docs/resim_contract/RCT_Implementation_Design.md` *Message
  fields* row `MeasBadge.Kind` 5 `KIND_IDENTITY_BROKEN`
- `modules/interfaces/proto/livemeas/meas_cycle.proto` (`KIND_IDENTITY_BROKEN` comment)

## The rule (owner decision, 2026-10-30, approved under D14; do not reopen)
Both counters are compared with `counterDistance` (wrap-aware), never with
"smaller than" or "restarted from 1":
- **counter reset:** `measurement_counter` and `cycle_counter` both go back
  (`counterDistance(prev, cur) < 0` for each). The sender restarted. Counted in the
  engine's event log, no badge.
- **identity broken:** `measurement_counter` goes back or repeats with new content
  while `cycle_counter` keeps counting up. Badged `KIND_IDENTITY_BROKEN`.

## Goal
The contract's `KIND_IDENTITY_BROKEN` text names the `cycle_counter` condition, and
D17 (3) states the rule once. Text only: no field number, name or type changes.

## Allowed changes
- `modules/interfaces/docs/resim_contract/RCT_Implementation_Design.md` (that one
  row's "Means" cell only; LF)
- `modules/interfaces/proto/livemeas/meas_cycle.proto` (that one comment only; LF)
- `VANTAGE_DEV_PLAN.md` (row D17 only; CRLF)
- Everything else is read-only. Keep each file's line endings.

## Steps
1. Field table, `KIND_IDENTITY_BROKEN` "Means" cell → exactly:
   `port: its measurement counter went back or repeated with new content while its sender's cycle_counter keeps counting`
2. `meas_cycle.proto`: the comment on `KIND_IDENTITY_BROKEN = 5;` → the same words.
   If the line gets too long, move the comment onto lines above the value, as
   `KIND_WARMING_UP` already does in the same enum.
3. `VANTAGE_DEV_PLAN.md` D17: replace part (3) with exactly:
   > (3) A **counter reset** is `measurement_counter` and `cycle_counter` both going
   > back (`counterDistance(prev, cur) < 0` for each): the sender restarted. **Identity
   > broken** is `measurement_counter` going back or repeating with new content while
   > `cycle_counter` keeps counting up; it is badged `KIND_IDENTITY_BROKEN`. Both
   > counters are compared only with `counterDistance`, never with "smaller than" or
   > "restarted from 1". Counter gaps, counter resets and stalled triggers are counted
   > in the engine's event log; badge kinds for them come only when a reader needs them.

   and change the row's last sentence to: "(1), (2) and the `KIND_IDENTITY_BROKEN`
   text of (3) are owner-approved contract changes under D14." Leave the rest of
   the row unchanged.

## Exit check (run all, report output and seconds)
- `python3 .claude/templates/requirements/trace_check.py --set modules/interfaces/docs/resim_contract`
  (from the vantage-dev root) → PASS, 78 requirements, no findings.
- `check_rct_schema.py --fields`, run as in `modules/interfaces/tests/python/test_rct_checks.py`
  or the script's usage (`C:\ws\venvs\rct-pytest\Scripts\python.exe` via `cmd.exe`,
  from `modules\interfaces`) → PASS.
- `grep -rn "KIND_IDENTITY_BROKEN" modules/interfaces/docs/resim_contract modules/interfaces/proto/livemeas`
  → both texts read the same.
- `git -C modules/interfaces diff --stat` → only the two files; `git diff --stat VANTAGE_DEV_PLAN.md` → one file.
- `file` on the three files → line endings as before.

## Must not
- commit, push, or change files outside "Allowed changes"
- change any field, requirement, test, design row, box or other D-row
- add features, abstractions or error handling not asked for

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked: none expected.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
