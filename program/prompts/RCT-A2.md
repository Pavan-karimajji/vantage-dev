# RCT-A2 — Recorded controls keep their op mode; the readiness limit gets a field (contract amendment, owner-approved)

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev` (Windows path `C:\ws\repo\vantage-dev`);
  submodule `modules/interfaces`, branch `vantage`, clean at `e374f4d`. The
  superproject has uncommitted work (`program/`, `modules/vantage/docs/`): leave it.
  Never reset, clean, stash, checkout or commit anything.
- `VANTAGE_DEV_PLAN.md` §2 (D1–D16; D14 says what the contract is)
- `modules/interfaces/docs/resim_contract/RCT_System_Requirements.md`: `SYS-0009`..`SYS-0012`
- `modules/interfaces/docs/resim_contract/RCT_Test_Spec.md`: the fixture catalogue, `SYT-CTL-06`, `ANL-01`
- `modules/interfaces/docs/resim_contract/RCT_Architecture.md`: the `op_mode` row
  (line 56), the "Recording has / Control message" table (line 166), the
  `MeasDescription` row (line 293), `Q3` (line 365)
- `modules/interfaces/docs/resim_contract/RCT_Implementation_Design.md`: the
  *Message fields* table for `MeasDescription` (lines 130–135), `IMP-0006`, `IMP-0032`
- `modules/interfaces/proto/livemeas/meas_description.proto`
- `.claude/rules/requirements.md` (R-REQ-3, R-REQ-4, R-REQ-5, R-REQ-10, R-REQ-14),
  `.claude/rules/naming.md` (R-NAME-4), `.claude/skills/protobuf_patterns.md`

## The problem (decided by the owner; do not reopen)
1. **Recorded controls.** The architecture says a recorded control is "handed over
   unchanged, except `op_mode = RESTART` on the first run". That contradicts
   `SYS-0010` (the scheduler writes its own count in every control) and `SYS-0011`
   (RESTART also after a jump). **Owner decision:** the SYS rows win, plus one case.
   When replaying a recorded control, Vantage copies `measurement_counter` and
   `source_timestamp_us` from it, writes its own `cycle_counter` and sticker OK,
   forces RESTART on the first run and after a jump, and otherwise passes the
   **recorded** `op_mode`, so a RESTART the car sent mid-recording is reproduced.
2. **Readiness limit.** `Q3` says the live measurement reports the readiness limit,
   but `MeasDescription` has no field for it. **Owner decision:** add
   `uint32 readiness_limit_steps = 7` to `MeasDescription`; the field table follows.

Both amend the frozen contract with the owner's approval (D14). This change also
records them, with two related owner decisions, as D17.

## Goal
`SYS-0011`, `SYT-CTL-06`, the architecture, `IMP-0032` and the field table agree
with decision 1; `MeasDescription` has field 7 in the proto, the field table and
the architecture; D17 is in the plan; the interfaces R-TEST-2 gate is green.

## Allowed changes
- `modules/interfaces/docs/resim_contract/RCT_System_Requirements.md` (`SYS-0011` only)
- `modules/interfaces/docs/resim_contract/RCT_Test_Spec.md` (catalogue + `SYT-CTL-06` only)
- `modules/interfaces/docs/resim_contract/RCT_Architecture.md` (the four places named above)
- `modules/interfaces/docs/resim_contract/RCT_Implementation_Design.md` (the
  `MeasDescription` table rows and `IMP-0032` only)
- `modules/interfaces/proto/livemeas/meas_description.proto` (one field)
- `VANTAGE_DEV_PLAN.md` (§2 only: one new row)
- Build output folders. Everything else is read-only.
- Line endings: `RCT_System_Requirements.md`, `RCT_Test_Spec.md`,
  `RCT_Architecture.md` and `VANTAGE_DEV_PLAN.md` are CRLF; the design file and
  the proto are LF. Keep each as it is.

## Steps
1. **`SYS-0011`.** Headline, Shall and Accept per decision 1; `Binds`, `Verify`,
   `Trace` unchanged. Shall + Accept ≤ 60 words, headline ≤ 90 characters (the
   checker counts both). Suggested wording (you may tighten it, not change its meaning):
   - Headline: RESTART at start and after a jump; otherwise RUN or the recorded op mode
   - **Shall.** The scheduler shall send RESTART on a component's first run and its
     first run after a jump; otherwise RUN, or the recorded `op_mode` when it
     replays recorded controls.
   - **Accept.** With one jump, each component's `op_mode` sequence is RESTART,
     RUN … RUN, RESTART, RUN … RUN; replaying a recording with a mid-run RESTART
     repeats it at that run; any other sequence fails.
2. **Fixture.** No catalogue fixture holds a recording with a mid-run RESTART. Add
   one row after `F-LAB-JUMP`: `F-LAB-RESTART` — `F-LAB` with one component
   restarted by the fake car mid-run (that run's recorded control carries RESTART),
   re-run by Vantage with recorded controls and no jump.
3. **`SYT-CTL-06`.** Fixture list becomes `F-LAB-JUMP`, `F-LAB-RESTART` (the checker
   reads a comma-separated list of back-ticked ids). Steps cover both fixtures.
   Keep `.c1` as it is (bound to `F-LAB-JUMP`). Add `.c2`: on `F-LAB-RESTART`, PASS
   — the replayed sequence has RESTART at exactly the recorded run, per `SYS-0011`
   Accept; FAIL — it is missing there, or appears anywhere else after the first run.
   Cite, do not restate (R-REQ-4). The headline may change to cover both cases.
4. **`RCT_Architecture.md`.**
   - Line 56, `op_mode` row: the "values" cell becomes RESTART on the first run and
     after a jump; otherwise RUN, or the recorded op mode when recorded controls are
     replayed.
   - Line 166: replace "handed over unchanged, except `op_mode = RESTART` on the
     first run" with decision 1 in a few words: counter and time copied, own count,
     OK, RESTART on the first run and after a jump, else the recorded `op_mode`.
   - Line 293, `MeasDescription` contents: add "the readiness limit" next to
     "the run setup's triggers and previous-cycle edges".
   - `Q3`: its "Why it is open" cell says the limit is reported in
     `MeasDescription.readiness_limit_steps`; the value stays ⊘.
5. **Field 7.** In `meas_description.proto` add, after `overrides`, in the file's
   comment style:
   ```
   // The readiness limit: how many steps a run may wait for a named sample
   // before it falls back. Set by the run setup; 0 = not set.
   uint32 readiness_limit_steps = 7;
   ```
   Add the matching row to the design's *Message fields* table after row 6:
   `| MeasDescription | 7 | readiness_limit_steps | uint32 | run setup: how many steps a run may wait for a named sample before it falls back; 0 = not set; value ⊘ (RCT_Architecture.md Q3) |`
   (same back-tick style as its neighbours). `IMP-0006` says "fields exactly as the
   table above", so leave it unchanged. Its box stays as it is.
6. **`IMP-0032`** Artifact cell: replace "a recorded control unchanged except RESTART
   on the first run and after a jump" with decision 1 in the row's style, e.g. "a
   recorded control's counter and time, own count, OK, RESTART on the first run and
   after a jump, else the recorded `op_mode`". Keep the rest of the cell. Box stays `[ ]`.
   This is a design-row edit. Do not touch `IMP-0030` (the fake car); report what it
   needs for `F-LAB-RESTART` under open questions.
7. **D17.** `VANTAGE_DEV_PLAN.md` §2: add row D17, dated 2026-10-30, after D16, in the table's style:
   > **Recorded controls and the 6a choices.** (1) Replaying a recorded control,
   > Vantage copies its `measurement_counter` and `source_timestamp_us`, writes its own
   > `cycle_counter` and sticker OK, forces RESTART on the first run and after a jump,
   > and otherwise passes the recorded `op_mode`; amends `SYS-0011`, `SYT-CTL-06`.
   > (2) The readiness limit is reported in `MeasDescription.readiness_limit_steps`
   > (field 7). (3) Counter gap, counter reset and stalled trigger are counted in the
   > engine's event log; badge kinds come only when a reader needs them. (4) *Warming
   > up* means a stage started mid-recording, badged until its outputs first equal the
   > recorded outputs, and only when the recording holds them. (5) A step at every
   > instant where any event happens; no pause for now; the live measurement writer
   > ships as a static library first. (1) and (2) are owner-approved contract changes
   > under D14.
8. Grep the four RCT documents for any other sentence that says a recorded control
   is handed over unchanged, or that RESTART happens only on the first run. Change
   none beyond the places above; list each hit in your report.

## Exit check (run all, report output and seconds) — the R-TEST-2 gate for interfaces
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev\modules\interfaces && py -3.12 scripts\build.py -t gtest -p vs2026"`
  → build and ctest pass; report the count.
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev\modules\interfaces && C:\ws\venvs\rct-pytest\Scripts\python.exe -m pytest tests\python -q"` → all pass.
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev\modules\interfaces\tests\python && C:\ws\venvs\rct-pytest\Scripts\python.exe test_gen_sil_ports.py"` → "All 9 test functions passed."
- `check_rct_schema.py` with `--fields`, `--compat 83b7fe9` and `--reserved`, each
  run the way `tests/python/test_rct_checks.py` or the script's own usage line shows
  (use `C:\ws\venvs\rct-pytest\Scripts\python.exe` via `cmd.exe`); all pass. Field 7 is
  additive, so `--compat` must still pass.
- `cmd.exe /c "cd /d C:\ws\repo\vantage-dev && py -3.12 scripts\check_invariants.py"` → clean.
- `python3 .claude/templates/requirements/trace_check.py --set modules/interfaces/docs/resim_contract`
  (from the vantage-dev root) → PASS, 78 requirements, no findings.
- `git -C modules/interfaces diff --stat` and `git diff --stat VANTAGE_DEV_PLAN.md` →
  only the allowed files.
- `file` on the six edited files → line endings as before.

## Must not
- commit, push, or change files outside "Allowed changes"
- change any other requirement, test, design row, box or proto field
- edit `IMP-0030` or anything in `modules/vantage`
- add features, abstractions or error handling not asked for

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked: none expected.
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation (include step 8's list, and what
   `IMP-0030` needs so the fake car can produce `F-LAB-RESTART`).
