# RCT-A4 — The seal, "engine run", the fallback by counter (text only, owner-approved); D18

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev` (Windows path `C:\ws\repo\vantage-dev`);
  submodule `modules/interfaces`, branch `vantage`, with the uncommitted RCT-A3
  change (`RCT_Implementation_Design.md`, `meas_cycle.proto`): keep it. The
  superproject has uncommitted work: keep it. Another worker edits
  `modules/vantage/docs/VANTAGE_Architecture.md` now: do not touch it.
  Never reset, clean, stash, checkout or commit anything.
- `VANTAGE_DEV_PLAN.md` §1 item 2 and §2 (D14, D17)
- `modules/interfaces/docs/resim_contract/RCT_Architecture.md` §0 (the C1..C5 table
  and the names table), §4 (the bullet "The whole header of each sample read"),
  §6 (the parts table and the sentence naming the writer), §7 (the C5 row)
- `modules/interfaces/docs/resim_contract/RCT_Implementation_Design.md` *Message
  fields* rows `MeasDescription` 2 `stages` and `MeasBadge` 3 `count`
- `modules/interfaces/docs/resim_contract/RCT_System_Requirements.md` (read only)

## Owner decisions (2026-10-30; do not reopen)
1. **Fallback by counter.** When a recorded refSync entry names a sample that is
   not found, the input falls back by counter: the newest sample whose
   `measurement_counter` is not after the wanted one, by `counterDistance`, badged
   `KIND_FALLBACK`. The time rule ("newest not after the trigger time") stays only
   for a stage with no recorded refSync.
2. **A component-under-test break is logged, not badged.** A simulated output that
   does not copy its control's `measurement_counter` (a `SYS-0001` break) goes to
   the engine's event log (stage, port, step) and the engine run goes on.
   `KIND_IDENTITY_BROKEN` keeps exactly the D17 (3) meaning.
3. **The seal (D14, approved).** The live measurement is written only by the writer
   library. Its seal call, used by the supervisor after the worker is confirmed
   dead, writes `outcome` and `status` and nothing else.
4. **Run-setup keys.** `sampling` and `on_missing` are refused at load if present.
5. **"Engine run".** "Run" keeps the contract meaning: one run of one component.
   The whole execution is an **engine run**: one outcome, one run id, one live
   measurement per engine run.

## Goal
The RCT documents say decision 3, use "engine run" for the whole execution in the
live measurement rows, and describe the fallback per decision 1; D18 records all
five decisions. Text only: no field number, name or type, no SYS row changes.

## Allowed changes
- `modules/interfaces/docs/resim_contract/RCT_Architecture.md` (CRLF) — the places in steps 1–3
- `modules/interfaces/docs/resim_contract/RCT_Implementation_Design.md` (LF) — the two cells in step 4
- `VANTAGE_DEV_PLAN.md` (CRLF) — §1 item 2 and one new §2 row
- Everything else is read-only. Keep each file's line endings.

## Steps
1. **Seal (decision 3).** In `RCT_Architecture.md`:
   - §6, the sentence saying the live measurement is written by one live measurement
     writer: add that it is written only by the writer library, and that the
     library's seal call, used by the supervisor after the worker is confirmed dead,
     writes `outcome` and `status` and nothing else.
   - §7, the C5 row's "Writes" cell: "Vantage's live measurement writer library only
     (its seal call: the supervisor, after the worker is confirmed dead; `outcome`
     and `status` only)".
   - §0: if a row there names who writes the live measurement, align it in a few words.
2. **"Engine run" (decision 5).** In `RCT_Architecture.md` §0 and §6, every place
   where "run" means the whole Vantage execution becomes "engine run". At least:
   C5 row ("a reader of a run … while the run goes on"), the names-table rows for
   live measurement ("one per Vantage run"), `MeasStatus`, `MeasDescription`
   ("one per run"), and the §6 parts-table rows for `MeasStatus` (run id, "per engine
   start") and `MeasDescription` ("once per run"), and "without touching the run"
   in §6. "Run" meaning one component run stays as it is.
3. **Fallback (decision 1).** `RCT_Architecture.md` §4, the bullet "The whole header
   of each sample read": "the time serves the fallback rule ("newest not after the
   trigger time")" becomes: a named sample that is not found falls back by counter
   (the newest sample whose `measurement_counter` is not after the wanted one); the
   time serves only the rule for a stage with no recorded refSync ("newest not after
   the trigger time"). Keep the rest of the bullet.
4. **Design cells (decision 5).** `RCT_Implementation_Design.md`: `MeasDescription` 2
   `stages` → "every stage of the engine run"; `MeasBadge` 3 `count` → "how often
   since the engine run started".
5. **Plan §1 item 2.** Replace "(the refSync the car wrote, else "newest not after my
   trigger time", badged)" with: (the refSync the car wrote; a named sample not found
   → the newest sample not after that number; a stage with no refSync → "newest not
   after my trigger time"; each fallback badged).
6. **D18.** `VANTAGE_DEV_PLAN.md` §2, after D17, dated 2026-10-30, in the table's style:
   > **Fallback by counter; breaks by the component under test; the seal; engine
   > run.** (1) A recorded refSync entry whose sample is not found falls back by
   > counter on that input: the newest sample whose `measurement_counter` is not
   > after the wanted one (`counterDistance`), badged `KIND_FALLBACK`. The time rule
   > ("newest not after the trigger time") is only for a stage with no recorded
   > refSync. (2) A simulated output that does not copy its control's
   > `measurement_counter` (a `SYS-0001` break by the component under test) goes to
   > the engine's event log (stage, port, step) and the engine run goes on;
   > `KIND_IDENTITY_BROKEN` keeps the D17 (3) meaning. (3) The live measurement is
   > written only by the writer library; its seal call, used by the supervisor after
   > the worker is confirmed dead, writes `outcome` and `status` and nothing else.
   > (4) The run-setup keys `sampling` and `on_missing` are refused at load.
   > (5) A **run** is one run of one component (the contract's meaning); the whole
   > execution is an **engine run**: one outcome, one run id, one live measurement.
   > (2) and (3) are owner-approved under D14.
7. Grep `RCT_System_Requirements.md` and `RCT_Test_Spec.md` for every place where
   "run" means the whole engine run (for example `SYS-0028`'s headline "a new run")
   and for the time fallback. **Change none**; list each hit in your report.

## Exit check (run all, report output and seconds)
- `python3 .claude/templates/requirements/trace_check.py --set modules/interfaces/docs/resim_contract`
  (from the vantage-dev root) → PASS, 78 requirements, no findings.
- `check_rct_schema.py --fields`, run as in `modules/interfaces/tests/python/test_rct_checks.py`
  or the script's usage (`C:\ws\venvs\rct-pytest\Scripts\python.exe` via `cmd.exe`,
  from `modules\interfaces`) → PASS.
- `grep -n -i "per run\|Vantage run\|the run goes on\|touching the run\|engine start" modules/interfaces/docs/resim_contract/RCT_Architecture.md`
  → report each hit with one line on why it is right.
- `git -C modules/interfaces diff --stat` → `RCT_Architecture.md`, `RCT_Implementation_Design.md`,
  `meas_cycle.proto` (the last from RCT-A3) only; `git diff --stat VANTAGE_DEV_PLAN.md` → one file.
- `file` on the three edited files → line endings as before.

## Must not
- commit, push, or change files outside "Allowed changes"
- change any SYS row, test, field number, name or type, design row or box
- add features, abstractions or error handling not asked for

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked: none expected.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation (include step 7's list).
