# C6CN-R1 — the owner's answers on C6 and 6c-CN

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`. Never reset, clean, stash, checkout or commit,
  and never run `git checkout` (with or without `-p`), `git stash`, `git reset`, `pkill` or
  `kill`: if a step seems to need one, stop and report it. Touch only the allowed files.
- `VANTAGE_DEV_PLAN.md` §2 (D10, D13, D14, D18, D22)
- `modules/vantage/docs/VANTAGE_Migration_Register.md` §2.1 (words, section rows), §4.1
- `modules/vantage/scripts/check_migration_register.py` (run it; section labels come from it)
- `modules/interfaces/docs/resim_contract/RCT_Architecture.md` §6a (C6, the recording)

## Goal
The owner's 2026-10-31 answers are in the files: one clock in the rule override and in 6a,
the lab's drills declare their holes, and nine register rows say what the owner decided.

## Allowed changes
- `.claude/rules/sim.md`: one new block (step 1). `.claude/IMPORTED.md`: one new row (step 1).
  Both working copies may have CRLF endings; keep each file's endings.
- `modules/vantage/docs/VANTAGE_Architecture.md`: the one row of step 2.
- `modules/vantage/docs/VANTAGE_Lab_Design.md`: the three edits of step 3.
- `modules/vantage/docs/VANTAGE_Migration_Register.md`: the §4.1 rows of step 4.
- Everything else is read-only.

## Steps
1. **Rule override.** In `.claude/rules/sim.md`, right after the existing override block
   (the `>` lines ending `The 1v rule itself is amended at migration.`), add one blank line and
   this block:
   ```
   > **vantage-dev override 2 (D22, RCT C6).** A recording carries **one clock** per
   > message, `log_time` (`publish_time` equal to it); the instant the data describes travels
   > in each payload's header (`source_timestamp_us`, R-IFACE-4, RCT C1). There is no
   > recording-level `capture_time_ns`: every part of **R-SIM-14** about two clocks, and
   > `Capabilities.capture_time`, is **superseded here**. The 1v rule is amended at migration.
   ```
   In `.claude/IMPORTED.md`, append to the *Local changes* table:
   `| 2026-10-31 | `rules/sim.md` | Second override note: R-SIM-14's two recording clocks superseded by one clock (D22, RCT C6) | amend R-SIM-14 in 1v at migration |`
2. **6a §13.** The row that starts `| `R-SIM-14` | two clocks |` (it is cut mid-sentence)
   becomes exactly:
   `| `R-SIM-14` | two clocks | one clock: a recording keeps one time per message, `log_time`, with `publish_time` equal to it (`RCT:SYS-0039`); the measurement time travels in each payload's header (C1), so no `capture_time_ns` is kept or used to age a value; `age_ns` is simulation time since the value was last written |`
3. **Lab design.**
   - The header line naming `` (`D1`..`D20`, `` becomes `` (`D1`..`D22`, `` — nothing else
     on that line changes.
   - §5.5's `recording:` table, the `drop_ref_sync: all` row: its effect cell
     `no `refSync` topic is written` becomes
     `no `refSync` topic is written, and every `refSync` port is listed `excluded` in `record_policies``.
   - §5.6, after the sentence that ends `` `recording:` edits (section 5.5) and states them in
     `manifest`. ``, add: `A drill that drops a port's messages declares that port
     `excluded` in `record_policies`, so its hole is stated (RCT §6a).`
4. **Register §4.1.** Apply exactly; keep the table's row order by first UID:
   - `| SIM:CN-0021 | moved | RCT:SYS-0037 | every port with its record policy is in the recording (RCT:SYS-0037); rate is the period each manifest declares (R-SIM-18); group and size are retired here, left to the open ECU-logging decision (RCT §13) |`
   - Take `SIM:CN-0083` and `SIM:CN-0084` out of the §8.1 section row (its ranges become
     `SIM:CN-0078..0082, SIM:CN-0085..0086, SIM:CN-0302..0303`, its word, target and Why
     unchanged) and add:
     `| SIM:CN-0083 | retired | — | Vantage never corrects a recorded time: it matches by counter (D18) and uses the sender's time (C1) |`
     `| SIM:CN-0084 | superseded | D18, ARCH §3.4 | samples are kept per port (`buffer_depth`) and picked by counter, so arrival order needs no sync buffer |`
   - `| SIM:CN-0111 | carried | VNT | the run manifest in every artifact is Vantage's metadata on top of C6; step 8 states it |`
   - Take `SIM:CN-0222` out of the §18.2 section row (ranges `SIM:CN-0214..0221, SIM:CN-0223`,
     the rest unchanged) and add:
     `| SIM:CN-0222 | retired | — | component state is not exposed by the ABI, the state snapshot is parked (RCT P1) and R-SIM-17 allows only recompute from the start; the checkpoint is progress, not state |`
   - `| SIM:CN-0240 | carried | VNT | lineage of a derived recording is Vantage's metadata on top of C6; step 8 states it |`
   - `| SIM:CN-0304 | carried | VNT | the ingest map names each signal's port, type, origin and array shape; unit and scale are not carried (R-SIM-23, CN-0309) |`
   - `| SIM:CN-0309 | retired | — | R-SIM-23 wins: an ingest map renames and tags only; a unit conversion is an unversioned algorithm between the recording and the component |`
   - `| SIM:CN-0319 | carried | VNT | the merged output is Vantage's metadata on top of C6; step 8 states it |`
5. Run the exit check.

## Exit check (run all, report output and seconds)
- `python3 modules/vantage/scripts/check_migration_register.py | grep SIM:CN` → no output.
- `python3 modules/vantage/scripts/check_migration_register.py --selftest` → 11 caught.
- `python3 .claude/templates/requirements/trace_check.py --set modules/interfaces/docs/resim_contract`
  → PASS (unchanged by this package; proves nothing else moved).
- `grep -n -E '^\| SIM:CN-0(021|078|083|084|111|214|222|240)|^\| SIM:CN-03(04|09|19) ' modules/vantage/docs/VANTAGE_Migration_Register.md`
  → the rows as written.
- `git diff --stat` at the root and in `modules/vantage` → only the allowed files, plus the
  changes that were already there when you started (list `git status --short` before you edit).

## Must not
- commit, push, or change files outside "Allowed changes"
- reword the given texts; if a check fails because of one, report it

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked: none expected.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation.
