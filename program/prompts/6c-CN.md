# 6c-CN — register: dispose every live sim v2 concept row (SIM:CN)

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`. Never reset, clean, stash, checkout or
  commit anything. Touch only the allowed file; no other worker edits it now.
- `VANTAGE_DEV_PLAN.md` §2 (all decisions; D5, D13, D15, D19 especially)
- `modules/vantage/docs/VANTAGE_Migration_Register.md` (6b, frozen): §1, §2 (the words, the
  section row, inheritance), §4 preamble and §4.1, §5
- `modules/vantage/docs/VANTAGE_Architecture.md` (6a, frozen): the parts (§3), the run
  setup (§2), the rules (§4-§9), code layout (§11), rules changed (§13), rejected and parked (§14)
- `modules/interfaces/docs/resim_contract/RCT_System_Requirements.md` and
  `RCT_Implementation_Design.md` (targets of `moved`)
- The rows to dispose: `modules/vantage/docs/v2/SIM_Concept_Document_v0.3.1.md`, every
  live `CN-nnnn` row (its own superseded list in §0.4 is not in the universe)
- `modules/vantage/scripts/check_migration_register.py` (run it; read `Context.sections`
  for the exact section labels)

## Goal
Register §4.1 holds a disposition for every live `SIM:CN` row: none missing, none twice,
the checker reports no finding for any `SIM:CN` UID. `SIM:SYS` rows are left for 6c-SYS.

## How to decide (the review applies exactly this)
- One question per row: **who holds this obligation after migration?** Vantage (`carried`,
  Target `VNT`), the contract (`moved`, the `RCT:` UIDs that now state it — each must
  really state it), a decision or the frozen architecture that replaced it (`superseded`,
  `D<n>` or `ARCH §n` — the cited place must really replace it), or nobody (`retired`, with
  a Why that a reader can check).
- **D13:** viewer, scene, plug-in, evidence-panel and player rows are `superseded` by `D13`
  (moved out of this design), not `retired`: the obligation lives on in the viewer's later
  design.
- **D10 / ARCH §7:** base-grid, GCD, due-tick and tick-numbering rows are `superseded`.
- **Section rows** (register §2.1): use one when every live row of a whole section shares
  one word, target and reason. Take the label from the script (`ctx.sections`), never
  retype a heading. Never stretch a section row over a row with a different fate: list
  that section row by row instead.
- A Why is one short clause in plain English, specific to the row or section — never a
  copy of the row's text, never "not needed".
- If a row's fate is genuinely unclear from 6a, the contract and the plan, do **not**
  guess: give it your best word, and list its UID under open questions with the two
  readings.

## Allowed changes
- `modules/vantage/docs/VANTAGE_Migration_Register.md`: rows in the §4.1 table only, and the
  "To dispose" count line of §4.1 if the script's numbers differ. Everything else is
  read-only.

## Steps
1. Run the checker; note the §4.1 universe and the `SIM:CN` labels by section.
2. Section by section of the concept document, write section rows or single rows.
3. Run the checker after every few sections; fix only your own rows.

## Exit check (run all, report output and seconds)
- `python3 modules/vantage/scripts/check_migration_register.py | grep "SIM:CN"` → no output.
- `python3 modules/vantage/scripts/check_migration_register.py | grep -v C-MISSING` → the
  per-section summary only; report the §4.1 line.
- `python3 modules/vantage/scripts/check_migration_register.py --selftest` → all caught.
- A count: how many section rows, how many single rows, and how many UIDs per word.

## Must not
- commit, push, or change files outside "Allowed changes"
- touch another section's table, the words, the code table or the script
- dispose a `SIM:SYS` row

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked: none expected.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation (every unclear UID with its two readings).
