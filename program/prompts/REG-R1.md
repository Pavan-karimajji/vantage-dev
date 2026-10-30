# REG-R1 — the register may dispose a whole sim v2 section with one range row (D15)

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`. Never reset, clean, stash, checkout or
  commit anything. Other workers edit other files now; touch only the allowed ones.
- `VANTAGE_DEV_PLAN.md` §2 D15 (amended 2026-10-31: section ranges)
- `modules/vantage/docs/VANTAGE_Migration_Register.md` §2.1, §4 (preamble), §5
- `modules/vantage/scripts/check_migration_register.py` (`load_set`, `Context`,
  `parse_register`, `run_checks`, `planted_cases`, `selftest`)
- `modules/vantage/tests/unit/test_check_migration_register.py`
- `.claude/rules/requirements.md` R-REQ-9 (every check ships a planted violation)

## Goal
A row table may hold a **section row**: one disposition for every live row of one kind
in one sim v2 section. The script expands it to its rows, so every universe row is
still disposed exactly once: an overlap is `C-DUPLICATE`, a gap is `C-MISSING`, and a
section row that does not cover exactly one whole section is `C-RANGE`.

## Allowed changes
- the three files under `modules/vantage/` named above. Everything else is read-only.

## Definitions (use these exactly)
- **Section of a row:** the nearest Markdown heading above the row in its source sim v2
  document. Its **label** is `§<number>` when the heading text starts with a section
  number (`5`, `5.1`, `3.4a`, an optional trailing dot), else the heading text itself
  (for example `PART C — CONSTRAINTS`). `load_set` records it per UID.
- **Whole section `§N`:** every live universe row of the given set and kind whose
  section number is `N` or starts with `N.` (subsections included). For an unnumbered
  label, the rows directly under that heading.
- **Section row:** its UID cell holds one or more comma-separated terms, each a range
  `SIM:SYS-0040..0063` (same set and kind at both ends, low ≤ high) or a single UID;
  the cell has at least one range. It expands to the universe rows inside its terms.
  Its Why starts with the section label followed by ` — ` and the reason, for example
  `§13 — run configuration is the run setup now (ARCH §4)`. Disposition and Target
  follow the ordinary rules for its word.

## Steps
1. `load_set`: record each UID's section (number or heading text). Keep the current
   return shape usable: add a third mapping or a field on `Context`, your choice, and
   keep tests injectable.
2. Parse section rows. Expand them before every other row check, so `C-MISSING`,
   `C-DUPLICATE`, `C-UNKNOWN` (scope) and the per-section counts treat expanded rows as
   listed rows.
3. New finding `C-RANGE <cell>: <what>` when: a range is malformed or reversed; a term
   names an `IMP` kind (implementation rows still inherit, D15); a term expands to no
   universe row; the Why does not start with a section label; or the expanded rows are
   not exactly the whole section of that label (name the first missing or extra UID).
4. `IMP` inheritance: an `SW` row disposed by a section row counts as disposed by that
   word, exactly like a listed row.
5. Selftest: plant one `C-RANGE` case; the selftest count rises by one.
6. Tests (each with a small in-memory universe that has two sections, one of them with
   non-contiguous UIDs): a correct section row passes and its `IMP` rows inherit; a
   **planted overlap** (a section row plus a single row for one of its UIDs, and two
   section rows sharing a UID) fails with `C-DUPLICATE`; a **planted gap** (a section row
   missing one row of its section) fails with `C-RANGE` and `C-MISSING`; a section row
   reaching into another section fails `C-RANGE`; an `IMP` range fails `C-RANGE`; a Why
   without a label fails `C-RANGE`.
7. Register: §2.1 gets one short paragraph defining a section row (the definitions
   above, in plain words, with one example line); §5 gets the `C-RANGE` row in the
   findings table. No other wording changes.

## Exit check (run all, report output and seconds)
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev\modules\vantage && python -m pytest tests\unit\test_check_migration_register.py -q"` → all pass.
- `python3 modules/vantage/scripts/check_migration_register.py --selftest` → all caught, one more than before (9 → 10).
- `python3 modules/vantage/scripts/check_migration_register.py | grep -v C-MISSING` → the
  per-section summary, no other finding.
- `python3 modules/vantage/scripts/check_headers.py` → clean.

## Must not
- commit, push, or change files outside "Allowed changes"
- change any other check, word, format or register row
- add options or checks not asked for

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked: none expected.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
