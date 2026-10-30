# RCT-A5 — SYS-0028 says "engine run"; D18 (1) states the maximum-gap exception (owner-approved)

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`; submodule `modules/interfaces`, branch
  `vantage`, with the uncommitted RCT-A3 and RCT-A4 changes: keep them. The
  superproject has uncommitted work: keep it. Another worker edits
  `modules/vantage/docs/VANTAGE_Architecture.md` now: do not touch it.
  Never reset, clean, stash, checkout or commit anything.
- `VANTAGE_DEV_PLAN.md` §2 rows D17, D18
- `modules/interfaces/docs/resim_contract/RCT_System_Requirements.md` `SYS-0028`
- `modules/interfaces/docs/resim_contract/RCT_Architecture.md` §4, the bullet "The
  whole header of each sample read"

## Owner decisions (2026-10-30; do not reopen)
1. **Maximum gap.** The run-setup key `fallback_max_gap` (counter steps, compared with
   `counterDistance`), value `⊘`, provisional value from the lab design. Beyond the
   gap the counter fallback takes nothing: the time rule picks the sample,
   `KIND_FALLBACK` is raised, and the engine's event log records stage, port, wanted
   counter, found counter and gap. D18 (1) states this exception once.
2. **`SYS-0028`** (D14, text only): "a new engine run" and "each engine run a new run id".

## Allowed changes
- `VANTAGE_DEV_PLAN.md` (row D18 only; CRLF)
- `modules/interfaces/docs/resim_contract/RCT_System_Requirements.md` (`SYS-0028`
  headline and Shall only; CRLF)
- `modules/interfaces/docs/resim_contract/RCT_Architecture.md` (that one bullet; CRLF)
- Everything else is read-only. Keep line endings.

## Steps
1. **D18 (1).** Replace the sentence "The time rule ("newest not after the trigger
   time") is only for a stage with no recorded refSync." with exactly:
   > The time rule ("newest not after the trigger time") is only for a stage with no
   > recorded refSync, with one exception: beyond `fallback_max_gap` (a run-setup key,
   > counter steps by `counterDistance`, value ⊘, provisional value from the lab
   > design) the counter fallback takes nothing, the time rule picks the sample,
   > `KIND_FALLBACK` is raised, and the event log records stage, port, wanted counter,
   > found counter and gap.
2. **D18 last sentence** → "(2), (3) and the `SYS-0028` wording of (5) are
   owner-approved under D14."
3. **`SYS-0028`.** Headline → `MeasStatus shows a live writer and a new engine run`.
   Shall → `The writer shall advance the MeasStatus heartbeat every step and give each
   engine run a new run id.` (keep the back-ticks around `MeasStatus`). Accept,
   Binds, Verify, Trace unchanged.
4. **`RCT_Architecture.md` §4 bullet.** "the time serves only the rule for a stage
   with no recorded refSync ("newest not after the trigger time")" → "the time serves
   only the time rule ("newest not after the trigger time"): for a stage with no
   recorded refSync, or beyond the counter fallback's maximum gap". Keep the rest.

## Exit check (run all, report output and seconds)
- `python3 .claude/templates/requirements/trace_check.py --set modules/interfaces/docs/resim_contract`
  (from the vantage-dev root) → PASS, 78 requirements, no findings.
- `grep -n "SYS-0028" -A2 modules/interfaces/docs/resim_contract/RCT_System_Requirements.md` → show it.
- `git -C modules/interfaces diff --stat` → the RCT-A3/A4 files plus `RCT_System_Requirements.md`.
- `file` on the three edited files → CRLF as before.

## Must not
- commit, push, or change files outside "Allowed changes"
- change any other requirement, test, field, design row or D-row
- add features, abstractions or error handling not asked for

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked: none expected.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
