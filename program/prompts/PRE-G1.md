# PRE-G1 — Fix two design faults and record owner decisions before the contract is frozen

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev` (a git superproject; `modules/interfaces`
  is a submodule on branch `vantage`). It holds uncommitted work: never reset,
  clean, stash or checkout anything.
- `VANTAGE_DEV_PLAN.md` §2 (decision table) and §4 (Plan A bullets)
- `modules/interfaces/docs/resim_contract/RCT_Implementation_Design.md`: the
  *Order, and why* section, the *Message fields* intro paragraph, rows `IMP-0005`
  to `IMP-0007`
- `.claude/rules/requirements.md` (R-REQ-2: a UID is allocated once, in creation
  order, never reused; R-REQ-14: design rows in present or future tense)

## Goal
The Implementation Design builds package by package (WP-01 no longer needs files
that WP-02 creates), it states two owner choices that are today only implied, and
the dev plan records the owner's decision on what counts as a contract change
and no longer repeats the live-measurement content that RCT owns.

## Allowed changes
- `modules/interfaces/docs/resim_contract/RCT_Implementation_Design.md`
- `VANTAGE_DEV_PLAN.md`
- Everything else is read-only. Both files use CRLF line endings: keep them.

## Steps
1. **Split the build wiring row.** In `RCT_Implementation_Design.md`, row
   `IMP-0005`: change "the four new `.proto` files added to the one list" to
   "the two new `adas.common` `.proto` files added to the one list". Leave the
   rest of the row as it is.
2. **Add row `IMP-0040`** directly after row `IMP-0007` (keep rows grouped by
   package), exactly:
   ``| `[ ]` | `IMP-0040` | `SYS-0032` | `WP-02` | `EXTEND` | `CMakeLists.txt::adas_generate_protos` — the two `adas.livemeas` `.proto` files added to the same list, so `WP-01` builds without them. | `ANL-01` |``
3. In the first paragraph of the design, change "At 39 rows" to "At 40 rows".
   Change no other count.
4. **Record choice (b).** At the end of the *Order, and why* section, after the
   paragraph that ends "…close **G4** (`VANTAGE_DEV_PLAN.md` §5).", add this
   paragraph:
   "**No shared control writer in `interfaces`.** The fake car (`WP-07`) and
   Vantage (`WP-08`) each write control messages with their own code. The fake
   car is the independent check Vantage is compared with, so the two never share
   the code under test."
5. **Record choice (c).** In the *Message fields* intro paragraph, after the
   sentence "Enum values are listed as rows with type `value`.", add:
   "Enum values in `adas.livemeas` carry their enum's prefix (`VERB_CONST`, not
   `CONST`), so no value collides with a platform macro."
6. **Add decision D14** as the last row of the table in `VANTAGE_DEV_PLAN.md` §2,
   exactly:
   "| D14 | **What the contract is, after gate G1:** the messages, their fields,
   the live measurement layout and the RCT SYS rows. A change to any of these
   goes to the owner first. Filling in the file path of a lab or Vantage design
   row is a design-row edit, not a contract change. | 2026-10-30 |"
   (one table row, on one line like the others).
7. **Cut the repeated list in plan §4.** Replace the whole bullet that starts
   "- **Live measurement layout** (D13): the shared-memory contract…" and ends
   "never inline in a `MeasCycle`." (its sub-bullets included) with exactly:
   "- **Live measurement layout** (D13): the shared-memory contract between
   Vantage and any reader, one layout header in `interfaces` (`cpp/livemeas/`,
   package `adas.livemeas`). It carries everything viz shows today. Its parts
   and why: `RCT_Architecture.md` §6; every field and the layout:
   `RCT_Implementation_Design.md`."
   Wrap it at about the width of the surrounding lines.

## Exit check (run all, report output and seconds)
- `cd /mnt/c/ws/repo/vantage-dev && python3 .claude/templates/requirements/trace_check.py --set modules/interfaces/docs/resim_contract`
  → PASS with 76 requirements and no findings.
- same command with `--status` → WP-02 shows `0/3` rows, design rows `of 40`.
- `git -C modules/interfaces diff --stat` and `git diff --stat` → only the two
  allowed files changed beyond what was already modified before you started
  (`RCT_Architecture.md`, `RCT_System_Requirements.md`, `RCT_Test_Spec.md`,
  `layers.yaml`, `program/ORCHESTRATION_LEDGER.md`, `program/prompts/` and the
  untracked design file were already uncommitted: do not touch them).
- `file VANTAGE_DEV_PLAN.md modules/interfaces/docs/resim_contract/RCT_Implementation_Design.md`
  → line endings unchanged from before your edit (check before and after).

## Must not
- commit, push, or change files outside "Allowed changes"
- reword, reorder or "improve" any other text in either file
- change any field table, any other row, `layers.yaml` or the budgets
- name any company, reference tool or reference repository in any file
- decide anything not stated here — report it instead

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked: none expected.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
