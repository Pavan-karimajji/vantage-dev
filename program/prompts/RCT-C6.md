# RCT-C6 — the recording contract (C6): an additive RCT area, the lab design and the plan follow

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`. Never reset, clean, stash, checkout or
  commit anything. Touch only the allowed files; no other worker edits them now.
- `VANTAGE_DEV_PLAN.md` §2 — **D22** (the decision this lands), D14, D20; §5; §6
- `.claude/rules/requirements.md` (R-REQ-1..17), `.claude/rules/interfaces.md`,
  `.claude/rules/sim.md` R-SIM-6, R-SIM-12, R-SIM-14, R-SIM-15, R-SIM-24 (read the override
  note first)
- The RCT set, `modules/interfaces/docs/resim_contract/`: `layers.yaml`,
  `RCT_Architecture.md`, `RCT_System_Requirements.md`, `RCT_Test_Spec.md`,
  `RCT_Implementation_Design.md` (frozen contract; this package is an **owner-approved
  additive change under D14**)
- `modules/vantage/docs/VANTAGE_Lab_Design.md` §2, §5.6, §8, §9, §10 (frozen step 7; the
  edits below are owner-approved)
- What exists today, read only: `modules/vantage-lab/src/lab_tools/recorder.py`
  (`McapRecorder`), how the car reads `index.json` (`src/lab_tools/car.py`, `topology.py`),
  `modules/interfaces/CMakeLists.txt` (the `install(DIRECTORY scripts/ …)` lines),
  `modules/vantage/docs/VANTAGE_Architecture.md` §2.3 (`outputs.path`) and §11 (`Recording I/O`)

## Goal
The recording conventions are contract area C6 (`REC`) of the RCT set: an architecture
section, SYS rows, tests and design rows, all additive. The lab design points to them and
plans the lab's adoption; the plan places the work. `Q-L4` is closed by C6. The checker is
clean.

## What the owner decided (apply; do not reopen)
- **One set of conventions, two writers, one conformance test.** C++: the engine's writer
  (ARCH §2.3, §11 `Recording I/O`), for an engine run's output recording. Python: the lab's
  `McapRecorder`, moved into `interfaces` with its metadata (`source_kind`, `run_kind`,
  per-topic provenance) turned into arguments; every producer uses it (the lab, the
  scenario-to-recording script, the simulator bridges, the car logger on a PC). The
  conformance test proves both writers follow the conventions and that Vantage's reader
  accepts both. No third writer.
- **Placement:** a new **§6a "C6 — the recording"** in `RCT_Architecture.md`, a new **§6a
  `REC`** in `RCT_System_Requirements.md` and in `RCT_Test_Spec.md`, so no existing section
  number changes. Nothing existing changes except the lines listed below: no message, no
  field, no layout item, no existing SYS row, no existing test. Package version stays `1.1.0`.
- **The lab finds the Python writer through `index.json`**, which the lab's build already
  writes and the car already reads: the build adds the `interfaces` package's `python/`
  folder to it.
- **Time and determinism (`R-SIM-24`):** a recording may carry a logging time, and
  comparisons are over port values, never file bytes. The writer **reads no clock**: the same
  arguments give a byte-identical file. Any logging time is metadata passed in by the caller;
  the lab passes none. A car or HIL recording keeps its real logging time.
- **Origin tags** are a closed list: `measured` / `truth` / `mocked` / `simulated` /
  `overridden` (`R-SIM-12`, `R-SIM-15`).
- **One Python writer, checked where a third one would appear:** in `vantage` or
  `vantage-lab`, not in `interfaces`. The check script ships in `interfaces` `scripts/` (so it
  travels in the package, like the other checks) and **runs in the unit suites of `vantage`
  and `vantage-lab` over their own source trees**; its planted violation is in `vantage-lab`.

## Allowed changes
- `modules/interfaces/docs/resim_contract/`: all five files, as in steps 1–5.
- `modules/vantage/docs/VANTAGE_Lab_Design.md`: step 6 only.
- `VANTAGE_DEV_PLAN.md`: step 7 only. Its working copy has CRLF line endings; keep them.
- Everything else is read-only. Write no code: the rows say where code goes.

## Steps
1. **`RCT_Architecture.md`.** Add §6a after §6: what a recording is in this contract; the
   conventions table, moved from Lab Design §5.6 and made general (topic = port name, schema
   = full name + `FileDescriptorSet`, event order with equal log times keeping file order,
   `log_time` in ns, metadata `manifest` with `source_kind`, `run_kind`, build ids and the
   caller's optional logging time, `topic_provenance` with the closed origin list; every
   declared port recorded per its `record` policy, `R-SIM-6`); the two writers and why the
   Python one lives here; the conformance test; the reader that must accept both. One line
   each in §0 (C6 among the contracts), §7 (a row for C6: who writes, who reads), §9 (C6 adds
   no proto field; it adds a Python module and two checks to the package), §12 (a new frozen
   decision `F9` for "one set of conventions, two writers, one conformance test"), and close
   `Q-L4` where the open questions are listed (cite the lab design's `Q-L4`). §13's ECU
   transport bullet stays; add that C6 is the file, not the transport.
2. **`layers.yaml`.** A seventh contract area `REC`: `budget_basis.count` 6 → 7, `total`
   78 → 91, with a dated `budget_history` entry giving the reason; the `SYS` and `IMP`
   budgets raised to the counts you land. Update the area list wherever it is written
   (the Test Spec preamble names the areas).
3. **`RCT_System_Requirements.md` §6a `REC`.** New rows, UIDs from `SYS-0037` in creation
   order, fixed anatomy (R-REQ-3), `Binds` to the declared ports, ≤ 60 words for
   Shall+Accept, headline ≤ 90 characters. One obligation each:
   - one topic per declared port, named after it (`source.<name>`, `<component>.<port>`);
   - each topic carries its schema: the full message name and the `FileDescriptorSet`;
   - message order: event order, equal log times keep file order, `log_time` in ns;
   - **the writer reads no clock: the same arguments give a byte-identical file; any logging
     time is metadata the caller passes in**;
   - provenance is stated, never defaulted: the writer refuses to write without
     `source_kind`, `run_kind` and an origin per topic from the closed list
     `measured` / `truth` / `mocked` / `simulated` / `overridden`;
   - Vantage's reader accepts every recording either writer makes.
   Split a row that carries two obligations; never merge two.
4. **`RCT_Test_Spec.md` §6a.** Fixtures you need in the catalogue (for example the source
   trees of `vantage` and `vantage-lab`; an engine-run recording of `F-LAB`). Tests, each
   citing its row's Accept by UID, cases with their FAIL side (R-REQ-4, R-REQ-5):
   `SYT-REC-01` the conformance check on the lab's recording; `SYT-REC-02` the writer refuses
   missing provenance or an origin outside the list; `SYT-REC-03` the same arguments written
   twice give byte-identical files; `SYT-REC-04` an engine-run recording passes the same
   check and Vantage's reader reads recordings from both writers (run on Vantage);
   `ANL-06` exactly one Python recording writer — the check runs in the unit suites of
   `vantage` and `vantage-lab` over their own trees, and its planted violation is a second
   writer in `vantage-lab`. Each `A` check ships a planted-violation case (R-REQ-9). Write
   both halves of every trace link (R-REQ-11).
5. **`RCT_Implementation_Design.md`.** Packages and boxed rows (`[ ]`), anatomy of the
   existing table:
   - `WP-11` (`interfaces`): `python/adas_recording/writer.py::McapRecorder` (MOVE from the
     lab, metadata as arguments, no clock); `scripts/check_recording.py` (the conformance
     check); `scripts/check_one_recording_writer.py` (`ANL-06`); `CMakeLists.txt` installs
     `python/` into the package beside `scripts/` (EXTEND).
   - `WP-12` (`vantage-lab`): `src/lab_tools/recorder.py` keeps the lab's recording edits and
     writes through the `interfaces` writer, found through `index.json`; the lab's unit suite
     runs `check_one_recording_writer.py`.
   - `WP-13` (`vantage`): `src/adas_sim/io/mcap.py` loses its `McapWriter`; the engine-run
     recording passes `check_recording.py`; Vantage's unit suite runs
     `check_one_recording_writer.py`. Blocked on step 8, like `WP-08`..`WP-10`.
   - Re-point `IMP-0031`: the fake car's recorder writes through the new writer row. Keep its
     box.
   - Add the three packages to the package list and to *Blocked, and by what* (`WP-12` waits
     for `WP-11`; `WP-13` for step 8). New UIDs from `IMP-0043`.
6. **`VANTAGE_Lab_Design.md`.** §5.6: the conventions table goes; one paragraph points to
   `RCT_Architecture.md` §6a and states only the lab's own argument values (no logging time;
   sources `mocked`, component ports `simulated`; `source_kind: synthetic`, `run_kind: sim`)
   and that the recorder also writes the scenario's `recording:` edits. §2's `recorder` row and
   §8's `Recorder` and `RCT:IMP-0031` rows: the recorder writes through the `interfaces`
   writer. **Rows already `[x]` keep their box and their text** (they were built as written):
   add one new row `LAB-54` (`[ ]`) in a new package `LAB-WP-09` serving `RCT:IMP-0046` (or
   whichever UID step 5 gives the lab's row): the recorder writes through the `interfaces`
   writer, found through `index.json`. §10: `Q-L4` moves from *Open questions* to *Decided*,
   closed by RCT C6 (`D22`).
7. **`VANTAGE_DEV_PLAN.md`.** §5 diagram: after the `C0` line, add a line aligned with the
   others: `A2  recording contract (C6, D22)   ─┤` (it joins the G2 group: the lab passes
   C6 before G2). §6 table: after row `5`, add `| 5b | RCT recording contract (C6, D22) | 5, 7 |`.
8. Run the exit check.

## Exit check (run all, report output and seconds)
- `python3 .claude/templates/requirements/trace_check.py --set modules/interfaces/docs/resim_contract`
  → PASS, no findings.
- `python3 .claude/templates/requirements/trace_check.py --set modules/interfaces/docs/resim_contract --status`
  → the three new packages `[ ]`, every old package's state unchanged.
- `grep -n -E 'SYS-00(0[1-9]|[12][0-9]|3[0-6])\b' ` over the `git diff` of
  `RCT_System_Requirements.md` → no existing row's text changed (report how you checked).
- `git diff --stat` in `modules/interfaces`, `modules/vantage` and the root → only the
  allowed files.

## Must not
- commit, push, or change files outside "Allowed changes"
- change an existing message, field, layout item, SYS row or test; reopen a decision above
- give a number nobody supplied: mark it `⊘` (R-REQ-10)
- narrate what was done in a design row (R-REQ-14: present or future tense)

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds.
4. Boxes ticked: none expected (all new rows `[ ]`).
5. Deviations from the prompt, each with the reason.
6. Open questions, each with your recommendation; and the list of new UIDs with headlines.
