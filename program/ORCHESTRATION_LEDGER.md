# Orchestration ledger

History of the program: one entry per prompt sent and per verdict given, newest
at the bottom. It records what happened; status always comes from the plan
documents' checkboxes (`VANTAGE_PROGRAM.md` §3).

## Entry format

```
### <YYYY-MM-DD> · <WP id> · <prompt | verdict | decision>
- Worker: <model, effort>                      (prompt entries)
- Prompt: <one line: goal>                     (prompt entries)
- Result: <done / not done; key evidence>      (verdict entries)
- Verdict: <accept | rework (n) | escalate>     (verdict entries)
- Why: <one line>
- Next: <the next WP id or the question asked>
```

## Entries

### 2026-10-30 · BOOT · decision
- Result: workspace created locally (`git init`, no remote, nothing committed);
  `VANTAGE_DEV_PLAN.md`, `README.md`, `CLAUDE.md`, `.claude/` import
  (`IMPORTED.md`, `routing.md`), `program/VANTAGE_PROGRAM.md` and this ledger written.
- Why: plan §6 writing order, steps 1–3.
- Next: `program/WORKSPACE_Plan.md` (plan §6 step 4).

### 2026-10-30 · BOOT · decision
- Result: D13 recorded (viz out of this design; board is Vantage's boundary).
  `program/WORKSPACE_Plan.md` written (B0.1–B2.5). Remote `origin` set to
  `github.com/Pavan-karimajji/vantage-dev` (reachable, empty; nothing pushed).
- Why: plan §6 step 4; the viz ↔ sim dependency loop found while checking sim's
  build made the separate `sim/vantage` package unnecessary once viz is out.
- Next: owner reviews `WORKSPACE_Plan.md`; then B0.1 (owner creates `vantage`
  and `vantage-lab` repos).

### 2026-10-30 · B0.1 · verdict
- Result: owner created `vantage` and `vantage-lab` on GitHub; both reachable, empty.
  First local commit `05dc171`. B0.4/B2.2 corrected: the recipe reads package
  name and version from `project()` in `CMakeLists.txt`, not `conf/build.yml`.
- Verdict: accept
- Why: owner step done and verified with `git ls-remote`.
- Next: B0.2–B1.1, run directly by this session (owner's instruction 2026-10-30).

### 2026-10-30 · B0.2–B1.1 · verdict
- Result: `vantage` = sim history to `a3fa0b9` (439 commits), tag `seed-from-sim`;
  `vantage-lab` README commit `af584ec`; `interfaces` branch `vantage` = `83b7fe9`
  + one-line version bump to 1.1.0 (`d3b76bb`); submodules added in vantage-dev:
  interfaces `d3b76bb` (vantage), toolchain `f061dfd`, shared_config `5634d3c`,
  vantage `a3fa0b9`, vantage-lab `af584ec`. All seeds pushed.
- Verdict: accept
- Why: every pointer equals WORKSPACE_Plan.md §1 / B0; `git submodule status` clean.
- Next: B1.2 (root machinery), or start Plan A writing now that its home exists.

### 2026-10-30 · B1.2–B2.4 · verdict
- Result: root machinery from 1v `d191172` imported and adapted (register:
  WORKSPACE_Plan.md §4); `check_invariants.py` clean; root test suite 830 passed,
  24 named skips. Owner decision: isolation by aggregate builds, no separate
  `CONAN_HOME`. `vantage`: viz-dependent sub-package and launchers removed,
  package `adas-vantage`, standard layout (`3f34a11`); two df-owned Python tests
  skip when df is absent (`1112191`).
  Evidence (vs2026): aggregate `--with-all` build ok and the cache got no
  `adas-vantage`; standalone gtest 218/218 (1v sim: 218; the one skip is skipped
  in 1v too); component `sil` builds `simengine`; Python suite 1036 passed,
  0 failed, 78 named skips. Test builds need `setup.py --prepare vantage`, which
  put `adas-interfaces/1.1.0` into the cache (1v only requests 1.0.0); the
  Python environment needed `--remotes on` (no offline bundle here).
- Verdict: accept
- Why: every exit check of B1.2–B2.4 met; findings recorded, none hidden.
- Next: B2.5 (ubuntu_gcc in WSL).

### 2026-10-30 · B2.5 · verdict
- Result: ubuntu_gcc gtest 223/223 passed (5 Linux-only tests more than vs2026),
  built in a Linux-native clone `~/ws/vantage-dev`. Two machine facts found:
  a venv under `/mnt/c` cannot bootstrap pip, and Ubuntu's Python ships no pip
  wheel, so Linux needs `misc/offline_bundle/` (copied from 1v; gitignored).
  Both recorded in `README.md`.
- Verdict: accept
- Why: exit check met; Plan B complete (B0.1–B2.5 all `[x]`).
- Next: owner pushes `vantage-dev` (`d8d45de` + this commit; the push was
  refused by the session's permission check); then Plan A writing.

### 2026-10-30 · PLAN-A · decision
- Result: Plan A written in the orchestrator session together with the owner
  (no worker; a deviation from §1, because every contract choice was an owner
  decision taken in discussion). Contracts C1–C5 settled: header rule (counter
  and time copied from `control`, own `cycle_counter` and sticker,
  `capture_timestamp_us` retired), `CycleControl` (RESTART for one run / RUN,
  scheduler only), `RefSync` (renamed from "receipt"), `CompState` (bad input =
  ERROR, `SUCCESS` retired, consumers read stickers only), live measurement
  (`MeasStatus` / `MeasDescription` / `MeasCycle` / `MeasBulk`, renamed from
  "board"). `RCT_Architecture.md`, `RCT_System_Requirements.md` (SYS-0001..0036),
  `RCT_Test_Spec.md` committed (interfaces `4730ea5`, vantage-dev `1439c3c`); 1v
  plan docs annotated "decided, not built" (df `3448c94`, 1v `15fc4d9`).
  Concept pages updated: `C:\ws\lt_learning\sim\vantage_concept.html`,
  `C:\ws\lt_learning\df\component_state_machine_proposal.html`.
- Why: plan §6 step 5.
- Next: owner review of `RCT_Implementation_Design.md`.

### 2026-10-30 · PLAN-A · decision
- Result: `RCT_Implementation_Design.md` written, UNCOMMITTED, awaiting owner
  review: field tables (`ANL-01` compares the protos with them), live
  measurement layout, IMP-0001..0039 in WP-01..WP-10. WP-01..05 are in
  `interfaces` and can be built; WP-06/07 (lab) wait for
  `VANTAGE_Lab_Design.md`, WP-08..10 (vantage) for `VANTAGE_Architecture.md`.
  `trace_check --set modules/interfaces/docs/resim_contract`: PASS, 75
  requirements, no findings. Not pushed: vantage-dev `d8d45de..1439c3c`
  (4 commits), interfaces `4730ea5`, df `3448c94`, 1v `15fc4d9`.
- Why: plan §6 step 5 completed in draft.
- Next: control handed to a new orchestrator session (WSL). Its first steps:
  owner review of the design → commit → gate G1 → plan §6 step 6
  (`VANTAGE_Architecture.md` + `VANTAGE_Migration_Register.md`) by worker prompt;
  WP-01..05 may be prompted in parallel once the owner freezes the contract.

### 2026-10-30 · PLAN-A · decision
- Result: new orchestrator session (WSL) took over. Owner reviewed
  `RCT_Implementation_Design.md` and approved it: (a) filling in the file path of
  a lab or Vantage design row is a design-row edit, not a contract change; the
  contract is the messages, the fields, the layout and the SYS rows (to be D14);
  (b) no shared control writer in `interfaces`, so the fake car stays an
  independent check; (c) `adas.livemeas` enum values are prefixed. Plan §4's
  live-measurement list is to become a pointer to RCT in the same commit.
  Isolation of the writer's crash outcome goes to the Vantage architecture worker,
  ALL_CAPS lab keys (`max_age_us`, `recovery_runs`) to the lab design worker.
  WP-01..05 may run in parallel with plan §6 step 6, once G1 is declared.
- Why: orchestrator review found two design faults to fix before freezing:
  IMP-0005 (WP-01) wires two protos only WP-02 creates, and choice (b) is not
  written in the design.
- Next: PRE-G1 prompt (design fixes, D14, §4 trim), then commit, then G1.

### 2026-10-30 · PRE-G1 · prompt
- Worker: sonnet, medium
- Prompt: `program/prompts/PRE-G1.md` — split IMP-0005 (new IMP-0040 in WP-02),
  record (b) and (c) in the design, add D14, cut plan §4's live-measurement list
  to a pointer.
- Next: review PRE-G1 against VANTAGE_PROGRAM.md §5.

### 2026-10-30 · PRE-G1 · verdict
- Result: done. IMP-0005 now wires only the two `adas.common` protos; new
  IMP-0040 (WP-02) wires the two `adas.livemeas` protos; choices (b) and (c)
  written into the design; D14 added; plan §4's live-measurement list cut to a
  pointer. `trace_check`: PASS, 76 requirements, no findings; WP-02 0/3, 40 rows.
  Deviation: edits made with an asserted-unique Python script, not the Edit tool
  (exact matches across wrapped lines and CRLF); the design file is LF, kept LF.
- Verdict: accept
- Why: every allowed-file and exit-check item holds; diff re-read by the orchestrator.
- Next: owner approves the commit (interfaces, then vantage-dev), then G1.

### 2026-10-30 · PRE-G1 · decision
- Result: owner approved both commits; the plan's two citations of a 1v
  study-notes folder whose name carries a reference tool's name are replaced in
  the same commit (exact path kept outside tracked files). Whether to rewrite the
  one pushed commit that contains it (`1337aaa`) is the owner's call; the
  orchestrator never force-pushes. Step 6 split into 6a–6e (architecture first and
  frozen; 6b also delivers a register check script: every sim v2 UID exactly once,
  IMP rows inheriting the disposition of the SW rows they serve, exceptions listed,
  inheritance computed) — to be D15.
- Why: owner answers to the orchestrator's four questions.
- Next: PRE-G1b prompt, then the commits.

### 2026-10-30 · PRE-G1b · prompt
- Worker: sonnet, medium
- Prompt: `program/prompts/PRE-G1b.md` — remove the folder name from two plan
  lines, split writing-order row 6 into 6a–6e, add D15.
- Next: review PRE-G1b, then commit interfaces and vantage-dev.

### 2026-10-30 · PRE-G1b · verdict
- Result: done. The plan no longer names the 1v study-notes folder (§4, §8);
  writing step 6 is rows 6a–6e (7 depends on 5, 6a; 8 on 6a–6e, 7); D15 added.
  CRLF kept. Diff re-read by the orchestrator; no reference name left.
- Verdict: accept
- Why: every exit-check item holds.
- Next: commit vantage-dev (interfaces `1c326e2` committed first), then G1.

### 2026-10-30 · G1 · decision
- Result: gate G1 declared green by the orchestrator (owner's instruction).
  Contract frozen: interfaces `1c326e2` (RCT architecture, SYS-0001..0036, test
  spec, implementation design), vantage-dev `2f48ca0`; from here a contract
  change goes to the owner first (D14). Workspace builds: Plan B B0.1–B2.5 all
  `[x]` (vs2026 and ubuntu_gcc evidence in the B1.2–B2.5 verdicts). Nothing in
  `vantage` or `vantage-lab` uses the two retired fields (grep), so 1.1.0 cannot
  break them.
- Why: both halves of G1 (`VANTAGE_DEV_PLAN.md` §5) hold.
- Next: in parallel, 6a (`VANTAGE_Architecture.md`) and WP-01; WP-02..05 one at a
  time after WP-01 in interfaces (shared build tree and CMake list).

### 2026-10-30 · WP-01 · prompt
- Worker: sonnet, high
- Prompt: `program/prompts/WP-01.md` — `CycleControl`, `RefSync`/`RefSyncEntry`
  protos, the two retirements, CMake list; rows `[~]` until `WP-05`'s checks.
- Next: review WP-01; then WP-02 and WP-04.

### 2026-10-30 · 6a · prompt
- Worker: sonnet, high
- Prompt: `program/prompts/6a.md` — `VANTAGE_Architecture.md`: parts, run setup,
  six rules, input selection, engine step, threads, failures (decides who writes
  the crash outcome), writer and inspector, code layout incl. paths for
  RCT IMP-0032..0039.
- Next: review 6a; owner freezes it; then 6b.

### 2026-10-30 · WP-01 · verdict
- Result: done. `CycleControl`, `RefSync`, `RefSyncEntry` exactly as the field
  tables; `SignalHeader` field 5 and `CompState.State` 4 removed and reserved by
  number and name; C1/C4 comments; CMake list. vs2026 gtest build 51 s, ctest
  15/15; `check_invariants` clean (SIG-1 on the real tree); `trace_check` PASS,
  WP-01 started 0/5 (rows `[~]`, closed by WP-05's checks). Gap: interfaces
  Python tests (`tests/python`, 16 cases) not run — no Windows Python here has
  pytest; a WSL run with the Windows protoc only fails on Linux temp paths, so it
  is not evidence either way.
- Verdict: accept (gap recorded; the Python tests belong to the R-TEST-2 gate
  before the interfaces commit)
- Why: contract content verified line by line against the tables; build green.
- Next: WP-02; owner asked how the Python tests get an environment.

### 2026-10-30 · WP-02 · prompt
- Worker: sonnet, high
- Prompt: `program/prompts/WP-02.md` — `adas.livemeas` `MeasDescription` and
  `MeasCycle` protos, CMake list; rows `[~]` until their tests exist.
- Next: review WP-02; then WP-04, WP-03, WP-05.

### 2026-10-30 · WP-02 · verdict
- Result: done. `adas.livemeas` `MeasDescription` (+ `MeasStage`, `MeasPort`,
  `MeasBundle`, `MeasOverride`) and `MeasCycle` (+ `MeasPortValue`,
  `MeasBulkRef`, `MeasBadge`) match the field tables in every name, number, type
  and value (orchestrator grep); CMake list; vs2026 gtest build, ctest 15/15;
  `check_invariants` clean; `trace_check` PASS, WP-02 started 0/3.
- Verdict: accept
- Why: every exit-check item holds. (Worker asked about the 1.1.0 version: already
  set by `d3b76bb`.)
- Next: WP-03. WP-04 held: a contract conflict found while writing its prompt
  (SYS-0003 vs SYS-0007 on `cycle_counter` after a mid-run RESTART) goes to the owner.

### 2026-10-30 · WP-03 · prompt
- Worker: sonnet, high
- Prompt: `program/prompts/WP-03.md` — `cpp/livemeas/livemeas_layout.hpp`
  (structs, offsets, slot helpers, `checkAttach`) plus new design row IMP-0041:
  a layout unit test, because nothing in interfaces would otherwise compile the
  header before Vantage's writer exists (a design-row edit, D14).
- Next: review WP-03; WP-04 after the owner's cycle_counter decision.

### 2026-10-30 · WP-03 · verdict
- Result: done. `cpp/livemeas/livemeas_layout.hpp`: the three structs exactly as
  the design table (sizes 80/32/24, align 8, asserted; atomics asserted
  lock-free), offsets, `beginSlot`/`endSlot`/`tryCopySlot` (orchestrator checked
  the memory orders: correct sequence-lock pattern, length bounded before the
  copy), `checkAttach`. `kMagic` "LVMS" (0x534D564C), suffix `_bulk`. New row
  IMP-0041 + `test_livemeas_layout.cpp` (9 cases, one with a writer thread).
  vs2026 ctest 24/24; `check_invariants` clean; `trace_check` PASS, 77 reqs.
  Deviations accepted: `tryCopySlot` copies header + payload (keeps step/port
  consistent with the payload); IMP-0041's close tail shortened to stay under the
  60-word cap.
- Verdict: accept
- Why: every exit-check item holds. Input carried to WP-09: the writer must make
  `descriptionCapacity`, `cycleSlotSize`, `bulkSlotSize` multiples of 8.
- Next: WP-04 waits for the owner's cycle_counter decision. 6a was stopped by the
  owner before writing its file; not relaunched.

### 2026-10-30 · RESTART · decision
- Result: orchestrator session restarted from `/mnt/c/ws/repo/vantage-dev` (the
  previous one ran from 1v-superproject by mistake); its program memory moved to
  this project's memory folder. Owner answers to the five open questions:
  (1) `cycle_counter` keeps counting through RESTART; *equal outputs* leave it out,
  defined once in the SYS preamble and used by `SYS-0007` and `SYS-0016`
  (owner-approved contract change, D14) — prompt RCT-A1. (2) 6a held until this
  restart and RCT-A1 are done. (3) pytest goes into a separate environment, never
  `modules/interfaces/.venv-win32` (owned by the build bootstrap); the Python tests
  run before the WP-05 commit. (4) one interfaces commit after WP-05. (5) rewriting
  `1337aaa` left to the orchestrator.
- Decision on (5): no rewrite now. The study-notes folder name is in the plan in
  all three pushed superproject commits (`05dc171`, `da1f23c`, `1337aaa`) and also
  in the pushed `vantage` repo (current `.gitignore` lines 118-119 and three
  inherited sim commits). Rewriting the superproject alone would not make the
  program shareable, and rewriting `vantage` cuts its shared history with 1v sim.
  Raised to the owner as one pre-share question.
- Next: RCT-A1; then WP-04.

### 2026-10-30 · RCT-A1 · prompt
- Worker: sonnet, high
- Prompt: `program/prompts/RCT-A1.md` — define *equal outputs* (byte-identical
  except `cycle_counter`) in the SYS preamble; use it in `SYS-0007`, `SYS-0016`,
  `SYT-CTL-02`, `SYT-RSY-04`; add D16.
- Next: review RCT-A1; then WP-04 and the 6a relaunch.

### 2026-10-30 · RCT-A1 · verdict
- Result: done. SYS preamble defines *equal outputs* (same message count, each
  pair byte-identical once both headers' `cycle_counter` is 0); `SYS-0007` and
  `SYS-0016` Accept use it; `SYT-CTL-02.c1` / `SYT-RSY-04.c1` cite it, FAIL "any
  byte differs outside `cycle_counter`"; D16 added. CRLF kept; only the three
  allowed files changed. `trace_check` PASS, 77 requirements, 36 tests (rerun by
  the orchestrator). The one other "byte-identical", `SYS-0026` (reader suspended
  vs. no reader), compares two fresh runs of one setup: counters agree, left as is.
- Verdict: accept
- Why: every exit-check item holds; diff re-read by the orchestrator.
- Next: WP-04 (unblocked); 6a relaunch waits on the owner's two stated inputs.

### 2026-10-30 · WP-04 · prompt
- Worker: sonnet, high
- Prompt: `program/prompts/WP-04.md` — `counter.hpp`, `cycle_stamp.hpp` (own
  count never reset by RESTART, D16), `ref_sync_builder.hpp`; `SYT-HDR-05` as a
  unit test (`IMP-0012`); new row `IMP-0042` + `test_component_kit.cpp`, because
  nothing in interfaces would otherwise compile the stamp and builder before a
  lab component exists (same reason as `IMP-0041`, a design-row edit, D14).
- Next: review WP-04; then WP-05 (needs the separate pytest environment).

### 2026-10-30 · WP-04 · verdict
- Result: done except one finding. `counter.hpp` (`counterDistance` branches on
  the unsigned difference; orchestrator checked the `INT32_MIN` edge),
  `cycle_stamp.hpp` (own count never reset), `ref_sync_builder.hpp` (allocates only
  in the constructor, `assert` on index). vs2026 build 14.8 s, ctest 31/31 incl.
  `Counter.SYT_HDR_05_c1_WrapAround`, 2 `Counter` + 5 `ComponentKit` cases;
  `check_invariants` clean 6.7 s. Boxes: `IMP-0011`/`-0012` `[x]`; `IMP-0013`..`-0015`,
  `IMP-0042` and WP-04 `[~]`. `trace_check`: `C-WORDS IMP-0042` 72 > 60 — the
  row text came from the orchestrator's prompt. The worker dropped an own-count
  wrap test that could not fail (correct), so "wrapping" leaves the row.
- Verdict: rework (1) — shorten IMP-0042's Artifact cell only (prompt's fault).
- Why: `trace_check` must be clean.
- Next: review the rework; then WP-05.

### 2026-10-30 · WP-04 · verdict
- Result: rework 1 done. IMP-0042's Artifact cell shortened ("wrapping" dropped);
  nothing else changed. `trace_check` PASS, 78 requirements (77 + `IMP-0042`; the
  prompt's 77 was the orchestrator's miscount), 36 tests, no findings (rerun by the
  orchestrator); WP-04 started 2/6.
- Verdict: accept
- Why: every exit-check item holds.
- Next: WP-05.

### 2026-10-30 · WP-05 · prompt
- Worker: sonnet, high
- Prompt: `program/prompts/WP-05.md` — `check_rct_schema.py` (`--fields`,
  `--compat 83b7fe9`, `--reserved`), `check_signal_header.py --message`,
  `check_livemeas_layout.py`, `test_rct_checks.py` (`ANL-01`..`-05`, `.c1` and
  planted `.c2`); pytest in a venv outside every repo (`C:\ws\venvs\rct-pytest`,
  owner decision); the exit check is the full R-TEST-2 gate for interfaces.
- Next: review WP-05; then propose the one interfaces commit (WP-01..05, RCT-A1)
  and the vantage-dev pointer bump.

### 2026-10-30 · WP-05 · verdict
- Result: done. `check_rct_schema.py` (`--fields` 12 messages/6 enums,
  `--compat 83b7fe9` 53 messages/27 enums, `--reserved`), `check_signal_header.py
  --message` (minimal diff), `check_livemeas_layout.py` (one defining file over
  interfaces, vantage, vantage-lab), `test_rct_checks.py` `ANL-01`..`-05` `.c1`/`.c2`
  all pass. Venv `C:\ws\venvs\rct-pytest` (pytest 9.2.0, PyYAML 6.0.3). R-TEST-2
  gate: pytest `tests/python` 17 passed; vs2026 ctest 31/31 (10.9 s);
  `check_invariants` clean (5.4 s); `trace_check` PASS, 78 reqs, WP-01 and WP-05
  `[x]`, WP-02..04 `[~]` (rows closed by `SYT-LMS` / lab tests).
  The worker's 9 "errors" in `test_gen_sil_ports.py` are not failures: it is a
  standalone script (its docstring: run directly), so pytest misreads its `tmp`
  parameter as a fixture. Run as documented by the orchestrator: 9/9 pass, 0.4 s.
  Deviation accepted: `IMP-0041`'s closing sentence shortened for `C-WORDS`.
- Verdict: accept
- Why: every exit-check item holds; the Python gap from WP-01 is closed.
- Follow-up (not urgent): `test_gen_sil_ports.py` is collected by pytest by
  name; a one-line fix (rename the parameter, or exclude the file) keeps
  `pytest tests/python` honest. Owner to decide.
- Next: propose the interfaces commit (WP-01..05 + RCT-A1), then the vantage-dev
  pointer bump.

### 2026-10-30 · OWNER · decision
- Result: owner answers.
  (1) Commits approved as proposed (interfaces contract commit, then the vantage-dev
  pointer), after one WP-03 fix from the owner's own review: `tryCopySlot`
  computes `slotSize - sizeof(Header)` unchecked; a damaged segment with a slot
  smaller than its header wraps it and the copy reads past the slot. Guard + unit
  test, gate rerun, then commit.
  (2) Inputs for later steps, recorded here so they do not depend on a chat:
  **6a** — `MeasStatus.outcome = crash` cannot be written by a writer that crashed
  itself; the architecture decides who sets it, which comes down to how processes
  are isolated (in-process vs. subprocess stages, R-SIM-19). (Already 6a stated
  input 4.) **Step 7 (`VANTAGE_Lab_Design.md`), not 6a** — the lab template's knobs
  `max_age_us` and `recovery_runs` (`IMP-0024`/`IMP-0025`) are calibration keys:
  ALL_CAPS with prefix and unit suffix (R-NAME-3).
  (3) `vantage/.gitignore`: do not delete the study-notes rule (at migration vantage
  replaces sim inside 1v, where the folder exists on disk); replace it with
  `/misc/*_bench/` and a comment naming no tool. History is left for the
  screening before anything is shared.
  (4) `test_gen_sil_ports.py`: smallest change that stops pytest collecting it,
  as its own commit, separate from the contract commit (approved).
- Next: WP-03-R1, GSP-1, VG-1 in parallel; 6a prompt refreshed (D16) and relaunched.

### 2026-10-30 · WP-03-R1 · prompt
- Worker: sonnet, high
- Prompt: `program/prompts/WP-03-R1.md` — `tryCopySlot` returns false before
  reading the header when `slotSize < sizeof(Header)`; one unit test; R-TEST-2
  gate for interfaces.
- Next: review; then the contract commit.

### 2026-10-30 · GSP-1 · prompt
- Worker: sonnet, medium
- Prompt: `program/prompts/GSP-1.md` — module-level `__test__ = False` in
  `test_gen_sil_ports.py`; still 9/9 when run directly.
- Next: review; its own interfaces commit after the contract commit.

### 2026-10-30 · VG-1 · prompt
- Worker: sonnet, medium
- Prompt: `program/prompts/VG-1.md` — `vantage/.gitignore` study-notes rule
  becomes `/misc/*_bench/`, comment names no tool.
- Next: review; commit proposed to the owner (not yet approved).

### 2026-10-30 · VG-1 · verdict
- Result: done. `vantage/.gitignore`: rule `/misc/*_bench/`, two-line comment
  naming no tool or folder, README reference dropped; `check-ignore` matches;
  no file in the vantage tree names the old folder any more (orchestrator grep). LF kept.
- Verdict: accept
- Why: every exit-check item holds; diff re-read by the orchestrator.
- Next: commit in `vantage`, then the vantage-dev pointer, when the owner approves.

### 2026-10-30 · GSP-1 · verdict
- Result: done. One line `__test__ = False` (with reason) in
  `test_gen_sil_ports.py`; `pytest tests/python` 17 passed, no errors; run
  directly 9/9.
- Verdict: accept
- Why: every exit-check item holds.
- Next: its own interfaces commit, after the contract commit (approved).

### 2026-10-30 · 6a · prompt
- Worker: sonnet, high
- Prompt: `program/prompts/6a.md` relaunched, unchanged except: D1–D16; stated
  input 6 (D16: compare *equal outputs* as the RCT SYS preamble defines them);
  interfaces read-only wording. The owner's crash-outcome input is stated input 4.
- Next: review 6a; owner freezes it; then 6b.

### 2026-10-30 · WP-03-R1 · verdict
- Result: done. `tryCopySlot` returns false as its first statement when
  `slotSize < sizeof(Header)`, before reading the header (orchestrator read it);
  new case `LivemeasLayout.CopyFromASlotSmallerThanItsHeaderFails` (cycle and bulk,
  output buffer untouched). R-TEST-2 gate: vs2026 ctest 32/32 (14 s); pytest 17
  passed; `test_gen_sil_ports.py` 9/9; `check_invariants` clean (6 s);
  `trace_check` PASS, 78 reqs.
- Verdict: accept
- Why: every exit-check item holds.
- Next: the approved commits.

### 2026-10-30 · COMMIT · decision
- Result: committed (owner-approved), nothing pushed: interfaces `d212700`
  (WP-01..05, RCT-A1, WP-03-R1), interfaces `e374f4d` (GSP-1), then the vantage-dev
  pointer bump with D16, this ledger and the prompts. `vantage/.gitignore` (VG-1)
  stays uncommitted until the owner approves it.
- Next: 6a running; review it when it reports.

### 2026-10-30 · 6a · verdict
- Result: done. `modules/vantage/docs/VANTAGE_Architecture.md` (759 lines, all 14
  sections); no Shall/Accept; every cited `RCT:` UID exists; every `(E)` path
  exists; no grid assumption (R-SIM-18 listed as superseded); uses *equal outputs*
  (D16); crash outcome decided: the batch supervisor seals crash and run timeout,
  the worker writes pass/fail/call timeout, the developer face writes none and a
  reader reports "writer gone". `IMP-0032`..`IMP-0039` mapped to files and symbols.
  Orchestrator checks: fault 4 confirmed as a conflict inside the frozen contract —
  `RCT_Architecture.md` row "recorded control: handed over unchanged, except
  RESTART on the first run" vs `SYS-0010` (scheduler's own count in every control)
  and `SYS-0011` (RESTART also after a jump); 6a follows the architecture row.
  Fault 1 confirmed: `RCT:Q3` says the live measurement reports the readiness
  limit; `MeasDescription` has no field for it.
- Verdict: escalate (contract questions under D14; otherwise ready to freeze)
- Why: two contract faults need the owner; 6a's §3.2 and the `IMP-0032` mapping
  change with the answer to fault 4.
- Next: owner answers faults 1, 2, 4 and the five design confirmations; then a
  contract fix (RCT-A2) and a 6a rework, then the freeze.

### 2026-10-30 · HANDOFF · decision
- Result: owner decisions on the 6a escalation (D14), recorded here in full. The
  next orchestrator session starts from this entry. **Add D17 to
  `VANTAGE_DEV_PLAN.md` §2 in the next accepted change** (VANTAGE_PROGRAM §8),
  covering decisions 1-3 and 5.
  1. **Recorded controls (fault 4): the SYS rows win, plus one case.** When
     replaying a recorded control, Vantage copies `measurement_counter` and
     `source_timestamp_us` from it, writes its own `cycle_counter` and sticker OK,
     forces RESTART on the first run and after a jump, and otherwise passes the
     **recorded** `op_mode`, so a restart the car sent mid-recording is reproduced.
  2. **Readiness limit (fault 1):** add `uint32 readiness_limit_steps = 7` to
     `MeasDescription`; the field table and `ANL-01` follow.
  3. **Missing-sample signs (fault 2):** counter gap, counter reset and stalled
     trigger are counted in the engine's event log now; badge kinds come only when
     a reader needs them. The concept page must not promise "N samples missing" yet.
  4. **refSync comparison (fault 3): accepted as 6a wrote it.** A re-run's refSync
     is compared only on each entry's counter and time.
  5. **The 6a choices.** Confirmed:
     - a step at every instant where any event happens;
     - no pause for now;
     - the live measurement writer ships as a static library first.

     **Warming up: changed.** It means a stage started mid-recording, badged until
     its outputs first equal the recorded outputs, and only when the recording
     holds them. "Every input matched by refSync" is what `KIND_FALLBACK` reports.

     **Seek:** must not give `MeasStatus.runId` a second meaning (one `runId` per
     writer start). Orchestrator check: 6a gives it none. `simEngineSeek` keeps
     the writer open and step numbers continue, but 6a does not yet say this in
     words.
  6. `vantage/.gitignore`: committed, `vantage` `bf227d9` (main, the declared
     branch), pointer `93648c2`. Nothing pushed.
- **RCT-A2 must do** (contract fix, `modules/interfaces`, sonnet high):
  - **`SYS-0011`:** amend to "RESTART for exactly the first run of a component and
    the first run after a jump; otherwise RUN, or the recorded `op_mode` when
    recorded controls are replayed". Keep Shall+Accept ≤ 60 words.
  - **`SYT-CTL-06`:** add a case `.c2`, a RESTART the recording carries mid-run is
    passed through. It needs a fixture that has one; name it, or add one to the
    catalogue.
  - **`RCT_Architecture.md` line 166:** correct "handed over unchanged, except
    `op_mode = RESTART` on the first run" to decision 1.
  - **Design row `IMP-0032`:** its Artifact says "a recorded control unchanged
    except RESTART on the first run and after a jump". Correct it to decision 1;
    this is a design-row edit.
  - **`MeasDescription` field 7 `readiness_limit_steps`:** add it in
    `proto/livemeas/meas_description.proto` and in the design's *Message fields*
    table. Mention it in the `IMP-0006` Artifact if needed.
  - **`RCT_Architecture.md` `Q3`:** state where the limit is reported (field 7);
    its value stays ⊘.
  - **Exit check, the R-TEST-2 gate:**
    - vs2026 build and ctest;
    - `C:\ws\venvs\rct-pytest` pytest on `tests/python`, plus
      `test_gen_sil_ports.py` run directly;
    - `check_rct_schema.py --fields`, `--compat 83b7fe9` and `--reserved`. The
      new field is additive, so `--compat` still passes;
    - `check_invariants`;
    - `trace_check`.
  - Commit only with the owner's yes: interfaces first, then the pointer.
- **6a fixes must do** (`modules/vantage/docs/VANTAGE_Architecture.md`, still
  untracked, rework 1 of 6a, sonnet high):
  - **§3.2 and the `IMP-0032` row of §11:** control writing per decision 1.
  - **§4:** the readiness limit maps to `MeasDescription.readiness_limit_steps`.
  - **§9 and §3.2:** gap, reset and stalled trigger are event-log counts (decision 3).
  - **Warming up:** redefine per decision 5 everywhere it appears (§2.2, §6/§7,
    the badge mapping).
  - **Seek:** say in words that `simEngineSeek` keeps the writer open,
    `runId` does not change and step numbers continue.
  - **§14:** close faults 1-4 and the confirmed choices, each citing D17; keep
    the remaining open questions.
  - Exit check as in `program/prompts/6a.md`.
- **Concept-page divergences:** `program/CONCEPT_PAGE_DIVERGENCES.md`, 11 rows plus
  two "also check" items from decisions 1 and 5. The orchestrator updates the page
  (`C:\ws\lt_learning\sim\vantage_concept.html`) after 6a is frozen.
- **Working copy at handoff:**
  - **Committed:** interfaces `d212700`, `e374f4d`; vantage `bf227d9`;
    vantage-dev `c80a7e9`, `93648c2`.
  - **Not committed:**
    - this ledger's entries from the 6a verdict on;
    - `program/CONCEPT_PAGE_DIVERGENCES.md`;
    - `modules/vantage/docs/VANTAGE_Architecture.md` (6a, awaiting fixes and
      freeze; this is why `modules/vantage` shows `?`).
  - Commit them with the RCT-A2 pointer bump, on the owner's yes.
- **Next, in order:**
  1. RCT-A2, then review it and commit with the owner's yes.
  2. The 6a fixes, then review them; the owner freezes 6a; commit it with the
     owner's yes, `vantage` first, then the pointer.
  3. Update the concept page from `program/CONCEPT_PAGE_DIVERGENCES.md`.
  4. 6b, `VANTAGE_Migration_Register.md` part 1 and its check script (D15).
  5. Step 7, `VANTAGE_Lab_Design.md`. Owner input: the template's `max_age_us`
     and `recovery_runs` (`IMP-0024`/`IMP-0025`) are calibration keys, so ALL_CAPS
     with prefix and unit suffix (R-NAME-3).
  6. Then the build packages unblocked by them: WP-06/07 (lab), WP-08..10
     (Vantage), per plan §6.
- Open follow-up: none besides the above. RCT-A1, GSP-1, VG-1 and WP-01..05 are
  closed.
- Why: the owner moves to a fresh orchestrator session that sees only the repo; no
  more workers launched in this one.
- Next: RCT-A2.

### 2026-10-30 · RCT-A2 · prompt
- Worker: sonnet, high
- Prompt: `program/prompts/RCT-A2.md` — HANDOFF decisions 1 and 2 into the
  contract: `SYS-0011`, `SYT-CTL-06.c2` with new fixture `F-LAB-RESTART`,
  `RCT_Architecture.md` (`op_mode` row, line 166, `MeasDescription` row, `Q3`),
  `IMP-0032`, `MeasDescription.readiness_limit_steps = 7` (proto + field table);
  D17 added to the plan (decisions 1-3 and 5). Exit check: the interfaces R-TEST-2
  gate. Two places beyond the HANDOFF list, found by grep: the `op_mode` row
  (line 56) and the `MeasDescription` contents row (line 293). `IMP-0030` (the fake
  car, "RESTART only on the first run") is left alone; what it needs for
  `F-LAB-RESTART` is an input to step 7.
- Next: review RCT-A2; then propose the commit (interfaces, then the pointer with
  D17, the ledger and the untracked program files).

### 2026-10-30 · RCT-A2 · verdict
- Result: done. `SYS-0011` (headline, Shall, Accept per decision 1; within the
  word caps), fixture `F-LAB-RESTART`, `SYT-CTL-06.c2` (cites the Accept, FAIL
  stated), `RCT_Architecture.md` lines 56, 166, 293 and `Q3`, `IMP-0032` Artifact,
  `MeasDescription.readiness_limit_steps = 7` (proto + field table), D17 in the
  plan. Orchestrator read the whole diff: only the allowed lines changed; line
  endings kept. R-TEST-2 gate: vs2026 ctest 32/32 (23 s); pytest 17 passed (4 s);
  `test_gen_sil_ports.py` 9/9; `check_rct_schema.py --fields`, `--compat 83b7fe9`,
  `--reserved` PASS; `check_invariants` clean (9 s); `trace_check` PASS, 78 reqs,
  36 tests (rerun by the orchestrator). Grep found no other "unchanged control" or
  "RESTART only on the first run" sentence except `IMP-0030`.
- Verdict: accept
- Why: every exit-check item holds; diff re-read by the orchestrator.
- Input to step 7 (lab design): `IMP-0030` (fake car scheduler) says "RESTART only
  on the first run"; to build `F-LAB-RESTART` it must also send RESTART for one
  named component at one scripted run. WP-07 and WP-08 must build that fixture.
- Next: propose the commit (interfaces, then the vantage-dev pointer with D17, the
  ledger, `CONCEPT_PAGE_DIVERGENCES.md` and `prompts/RCT-A2.md`); then the 6a fixes.

### 2026-10-30 · OWNER · decision
- Result: owner accepts RCT-A2 with two text fixes before the commit, no field
  numbers change: (1) `KIND_WARMING_UP` means D17 (4) — "stage: started
  mid-recording; badged until its outputs first equal the recorded outputs, only
  when the recording holds them"; (2) `readiness_limit_steps` 0 = "never waits"
  (0 is a real limit; the run setup always has one and the writer always writes
  it), "not set" dropped in the proto comment, the field table and `Q3`. Then
  trace_check and `check_rct_schema --fields`, then both commits as proposed, then
  the 6a fixes.
- Orchestrator addition: the same old warming-up text is the `KIND_WARMING_UP`
  comment in `meas_cycle.proto`; fixed with it (one fact in one place). For 6a:
  its §6 "`readiness_limit_steps` is a positive integer" must become "0 = never waits".
- Next: RCT-A2-R1.

### 2026-10-30 · RCT-A2-R1 · prompt
- Worker: sonnet, medium
- Prompt: `program/prompts/RCT-A2-R1.md` — the two owner text fixes in the field
  table, both proto comments and `Q3`.
- Next: review; then the two commits.

### 2026-10-30 · RCT-A2-R1 · verdict
- Result: done. `KIND_WARMING_UP` reads D17 (4) in the field table and in
  `meas_cycle.proto` (comment moved above the value); `readiness_limit_steps`
  "0 = never waits" in the proto comment, the field table and `Q3`; "not set" and
  "started cold" gone (grep). Comments and table text only, no field changed.
  `trace_check` PASS, 78 reqs, 36 tests (rerun by the orchestrator);
  `check_rct_schema.py --fields` PASS. The two extra files in the worker's diff
  stat are RCT-A2's own (SYS and test spec), as the prompt expected.
- Verdict: accept
- Why: every exit-check item holds; diff re-read by the orchestrator.
- Next: the two approved commits; then 6a-R1.

### 2026-10-30 · COMMIT · decision
- Result: committed (owner-approved), nothing pushed: interfaces `c42782d`
  (RCT-A2 + R1), then the vantage-dev pointer bump with D17, this ledger,
  `CONCEPT_PAGE_DIVERGENCES.md` and the RCT-A2 / RCT-A2-R1 prompts.
  `VANTAGE_Architecture.md` stays untracked until the owner freezes 6a.
- Next: 6a-R1.

### 2026-10-30 · 6a-R1 · prompt
- Worker: sonnet, high
- Prompt: `program/prompts/6a-R1.md` — rework 1 of 6a: control writing (D17 (1)),
  readiness limit field 7 and 0 = never waits (D17 (2), owner review), gap / reset /
  stalled trigger as event-log counts stated once in §6 (D17 (3)), refSync
  comparison stated in §7 (owner decision 4), warming up (D17 (4)), seek keeps the
  writer and `runId`, §14 split into open and closed-by-the-owner with numbers kept.
- Next: review 6a-R1; owner freezes 6a; commit `vantage`, then the pointer.

### 2026-10-30 · 6a-R1 · verdict
- Result: done. Orchestrator read every reworked passage: §3.2 states D17 (1) in
  full; §2.3, §4 map the limit to field 7; §5 "0 = never waits", refused at load
  when missing; §6 states gap / reset / stalled trigger once; §7 states the refSync
  comparison and the seek (writer open, same `runId`, steps continue); warming up
  per D17 (4) in §6, §7, §14, Parked; §14 split, numbers kept (open 5, 6, 8, 11;
  closed 1-4, 7, 9, 10, 12). Exit checks pass; LF kept; only the one file.
  Accepted deviations: §11 control row now points to §3.2 (it described the old
  behaviour); preamble D1..D17.
- Findings: (a) wording: §2.4 "a recorded control is its model" is unclear; §3.2
  repeats "never handed over unchanged" after the full statement, and its *Writes*
  names the event log twice. (b) a real gap the worker raised: D17 (3) counts a
  "counter reset" in the event log, but the contract's `KIND_IDENTITY_BROKEN`
  means "measurement counter went back", and nothing defines how a reset differs
  from going back. Deciding it may touch the contract's text (D14).
- Verdict: escalate (b) to the owner; (a) goes into the same rework 2.
- Next: owner answers (b); then 6a-R2 (wording + the answer); then the freeze.

### 2026-10-30 · OWNER · decision
- Result: owner chooses option A, approved under D14, with an exact rule. Both
  counters compared with `counterDistance` (wrap-aware), never "smaller than" or
  "restarted from 1". **Counter reset:** `measurement_counter` and `cycle_counter`
  both go back (`counterDistance(prev, cur) < 0` for each); the sender restarted;
  event log, no badge. **Identity broken:** `measurement_counter` goes back or
  repeats with new content while `cycle_counter` keeps counting up;
  `KIND_IDENTITY_BROKEN`. RCT-A3: that kind's "Means" cell and proto comment gain
  "while its sender's cycle_counter keeps counting" (text only). D17 (3) states the
  rule once; 6a cites it. The three wording faults go into 6a rework 2; then 6a
  comes to the owner for the freeze.
- Next: RCT-A3 and 6a-R2 in parallel (disjoint files).

### 2026-10-30 · RCT-A3 · prompt
- Worker: sonnet, medium
- Prompt: `program/prompts/RCT-A3.md` — `KIND_IDENTITY_BROKEN` text in the field
  table and `meas_cycle.proto`; D17 (3) rewritten with the rule.
- Next: review; commit with the 6a freeze, on the owner's yes.

### 2026-10-30 · 6a-R2 · prompt
- Worker: sonnet, medium
- Prompt: `program/prompts/6a-R2.md` — rework 2 of 6a: §2.4 control cell, §3.2
  duplicate sentence and *Writes*, §3.4 and §6 cite D17 (3) for reset vs. identity
  broken.
- Next: review; owner freezes 6a.

### 2026-10-30 · 6a-R2 · verdict
- Result: done. Orchestrator read each edit: §2.4 control cell; §3.2 duplicate
  sentence gone, *Writes* names the event log once; §3.4 and the §6 table row and
  paragraph cite `D17 (3)` and define nothing themselves; no "goes back", "went
  back", "smaller", "restarted from" left; LF; only the one file. Cosmetic, left
  as is: §3.2 line 179 is one long source line after the deletion, and it cites
  `D17` where the §14 rows cite `D17 (1)`.
- Verdict: accept
- Why: every exit-check item holds.
- Next: RCT-A3 review; then 6a to the owner for the freeze.

### 2026-10-30 · RCT-A3 · verdict
- Result: done. `KIND_IDENTITY_BROKEN` "Means" cell and its `meas_cycle.proto`
  comment (moved above the value, as `KIND_WARMING_UP`) end "while its sender's
  cycle_counter keeps counting"; D17 (3) states the owner's rule word for word; D17's
  last sentence names the (3) text change under D14. Text only. Orchestrator read
  the diff; `trace_check` PASS, 78 reqs, 36 tests (rerun); `check_rct_schema.py
  --fields` PASS; line endings kept.
- Verdict: accept
- Why: every exit-check item holds.
- Next: owner freezes 6a; then the commits (interfaces RCT-A3, vantage 6a, the
  vantage-dev pointers with D17 (3), ledger and prompts).

### 2026-10-30 · OWNER · decision
- Result: 6a not frozen; rework 3 with five items (D18): (1) a named sample not
  found falls back by counter (newest not after the wanted `measurement_counter`,
  `counterDistance`), `KIND_FALLBACK`; the time rule only for a stage with no
  recorded refSync; the orchestrator brings a recommendation on a maximum gap.
  (2, D14) `KIND_IDENTITY_BROKEN` keeps D17 (3); an output not copying its
  control's counter (`SYS-0001` break) goes to the event log (stage, port, step),
  the engine run goes on. (3, D14) the live measurement is written only by the
  writer library; its seal call (supervisor, worker confirmed dead) writes
  `outcome` and `status` only — RCT-A4, text only. (4) `sampling`, `on_missing`
  refused at load. (5) "run" = one component run; "engine run" = the whole
  execution, in 6a and the RCT live measurement rows.
- Owner rule: the orchestrator checks the reference material before deciding or
  escalating, says "reference does X" in one line, and never passes reference
  paths or names to workers or tracked files.
- Reference check (gap limit): established practice takes the newest sample not
  newer than the wanted id within a fixed maximum gap, wrap-aware; beyond it, an
  error naming the port. Recommendation to the owner with the freeze.
- Orchestrator design input to 6a-R3: the counter fallback may use read-ahead
  samples (the counter keeps it causal); the time rule never does.
- Next: RCT-A4 and 6a-R3 in parallel (disjoint files).

### 2026-10-30 · RCT-A4 · prompt
- Worker: sonnet, medium
- Prompt: `program/prompts/RCT-A4.md` — seal and writer-only wording (§6, §7),
  "engine run" in the §0/§6 live measurement rows and two design cells, §4 fallback
  bullet, plan §1 item 2, D18. SYS/test hits on "run" are reported, not changed.
- Next: review; then 6a and RCT-A4 to the owner.

### 2026-10-30 · 6a-R3 · prompt
- Worker: sonnet, high
- Prompt: `program/prompts/6a-R3.md` — rework 3 of 6a: counter fallback and time
  rule, open question 13 (maximum gap), SYS-0001 breaks to the event log, seal per
  RCT §7, `sampling`/`on_missing` refused, "engine run" sweep.
- Next: review; then the freeze.

### 2026-10-30 · RCT-A4 · verdict
- Result: done. Orchestrator read the diff: §0 C5 row and names rows, §6 parts rows
  and "without touching the engine run" use "engine run"; §6 and §7 say the live
  measurement is written only through the writer library and its seal call writes
  `outcome` and `status` only (one sentence each, the duplicate from a spurious
  edit error removed); §4 refSync bullet describes the counter fallback; design
  cells `MeasDescription.stages`, `MeasBadge.count` say "engine run"; plan §1 item 2
  and D18 added. No SYS row, field or box changed. `trace_check` PASS, 78 reqs
  (rerun); `check_rct_schema.py --fields` PASS; line endings kept.
- Open for the owner: `SYS-0028` headline ("a new run") and Shall ("each writer
  start a new run id") mean the engine run; a SYS edit needs the owner (D14).
- Verdict: accept
- Why: every exit-check item holds.
- Next: 6a-R3 review; then 6a + RCT-A4 to the owner.

### 2026-10-30 · 6a-R3 · verdict
- Result: done. Orchestrator read §2.2 (new *engine run*, *counter fallback*,
  *time rule*, *seal* rows), §5 rules 3-4, all of §6, all of §9 and the §14
  changes: the counter fallback searches the buffer including read-ahead, the time
  rule never does; a `SYS-0001` break goes to the event log and the engine run goes
  on; `KIND_IDENTITY_BROKEN` is D17 (3) only; "a contract break" is gone from *fail*;
  the seal cites `RCT_Architecture.md` §7 once and stays `sealAbandoned`;
  `sampling`/`on_missing` gone and refused at load; "engine run" for the whole
  execution (40 lines); open question 13 added, not decided. Exit checks pass; LF;
  only the one file. Accepted deviations: `SampleBuffer::NewestCounterNotAfter` in
  §11 and §3.4 (the counter fallback needs it); §6 steps renumbered; one "finds no
  sample" row per rule.
- Verdict: accept
- Why: every exit-check item holds.
- Next: 6a and RCT-A4 to the owner for the freeze; open: question 13 (maximum
  gap), `SYS-0028` wording.

### 2026-10-30 · OWNER · decision
- Result: (1) question 13: option (a) — run-setup key `fallback_max_gap` (counter
  steps, `counterDistance`), value ⊘, provisional value from the lab design; beyond
  it the time rule picks the sample, `KIND_FALLBACK`, event log records stage,
  port, wanted counter, found counter and gap; D18 (1) states the exception once,
  6a cites it. (2) `SYS-0028`: "a new engine run", "each engine run a new run id"
  (D14, text only). (3) 6a frozen once this rework is accepted. (4) pushed commit
  `1337aaa` stays; its history is for the screening before sharing; no force-push.
  Then, if all checks are green: grep every file to commit for reference names and
  paths (stop if found); record the freeze and gate state here; commit interfaces
  (`vantage`), vantage (`main`), vantage-dev; push in the same order with normal
  pushes only, stop on any auth or network failure, prove each push with
  `git ls-remote`. Do not touch 1v-superproject. Then the concept page and 6b, plus
  more if possible.
- Next: RCT-A5 and 6a-R4 in parallel.

### 2026-10-30 · RCT-A5 · prompt
- Worker: sonnet, medium
- Prompt: `program/prompts/RCT-A5.md` — D18 (1) maximum-gap exception, `SYS-0028`
  headline and Shall, the §4 refSync bullet.
- Next: review.

### 2026-10-30 · 6a-R4 · prompt
- Worker: sonnet, medium
- Prompt: `program/prompts/6a-R4.md` — `fallback_max_gap` in §2.3, §4, §6; question
  13 moved to *Closed by the owner*.
- Next: review; 6a frozen on accept.

### 2026-10-30 · 6a-R4 · verdict
- Result: done. Orchestrator read each edited line: `fallback_max_gap` in §2.3 and
  the §4 `⊘` table; §2.2 time rule row and §6 steps 3-4 state the beyond-gap case
  and cite `D18 (1)`; one new badge row; question 13 closed (kept number), open
  question 6 lists the key. Exit checks pass; LF; only the one file.
- Verdict: accept
- Why: every exit-check item holds.
- Next: RCT-A5 review; then the 6a freeze record, the reference scan, commits, push.

### 2026-10-30 · RCT-A5 · verdict
- Result: done. Orchestrator read the diff: `SYS-0028` headline "a new engine run",
  Shall "each engine run a new run id" (Accept unchanged); `RCT_Architecture.md` §4
  bullet: the time serves only the time rule, for a stage with no recorded refSync
  or beyond the counter fallback's maximum gap; D18 (1) states the `fallback_max_gap`
  exception once; D18's last sentence names the `SYS-0028` wording. `trace_check`
  PASS, 78 reqs, 36 tests (rerun by the orchestrator); CRLF kept.
- Verdict: accept
- Why: every exit-check item holds.

### 2026-10-30 · 6a · decision
- Result: **6a frozen** (owner, 2026-10-30, on acceptance of 6a-R4):
  `modules/vantage/docs/VANTAGE_Architecture.md` after reworks R1-R4 (D17, D18).
  Gate state: **G1** green (contract frozen; amended since only by owner-approved
  RCT-A1..A5 under D14). **C0** (architecture + register frozen) not yet: the
  register (6b-6e) is next. **G2-G5** not green. Plan A status: WP-01, WP-05 done;
  WP-02..04 started (closed by lab and live-measurement tests); WP-06..10 open,
  WP-08..10 now unblocked by 6a, WP-06/07 still wait for the lab design (step 7).
- Next: reference scan of every file to commit and every unpushed commit; commits
  (interfaces, vantage, vantage-dev); push in the same order; then the concept
  page, 6b and step 7.

### 2026-10-30 · COMMIT · decision
- Result: reference scan (orchestrator, every file in this commit set and in every
  unpushed commit of the three branches): files committed now are clean; the
  `@author` lines are the L&T EPS file-header exception. **One hit in an unpushed
  superproject commit:** `toolchains/aarch64_qcc_qnx.cmake` line 1 names the
  reference platform; it came in with `bc787c9` (root machinery copied from 1v) and
  is not on the remote yet. Committed (owner-approved), nothing force-pushed:
  interfaces `132727e` (RCT-A3..A5), vantage `548e7fe` (6a frozen), then this
  vantage-dev commit (both pointers, D17 (3), D18, ledger, prompts).
- Next: push interfaces `vantage` and vantage `main` (clean); hold the vantage-dev
  push and ask the owner about the toolchain-file hit.

### 2026-10-30 · PUSH · decision
- Result: pushed (normal pushes, nothing forced), each proven with `git ls-remote`:
  interfaces `vantage` `d3b76bb..132727e` (remote head `132727e`); vantage `main`
  `1112191..548e7fe` (remote head `548e7fe`). **vantage-dev `main` held** (local
  `943f78c`, remote `1337aaa`): the reference scan hit in `bc787c9`
  (`toolchains/aarch64_qcc_qnx.cmake` line 1) goes to the owner first.
- Next: owner decides the toolchain-file hit; meanwhile CP-1, 6b and 7 in parallel.

### 2026-10-30 · CP-1 · prompt
- Worker: sonnet, high
- Prompt: `program/prompts/CP-1.md` — the concept page follows 6a and D16-D18; done
  rows deleted from `CONCEPT_PAGE_DIVERGENCES.md`. A backup of the page is in the
  orchestrator's scratchpad.
- Next: review.

### 2026-10-30 · 6b · prompt
- Worker: sonnet, high
- Prompt: `program/prompts/6b.md` — register part 1 (words, sim code table, empty row
  sections for 6c-6e) and `check_migration_register.py` (D15) with planted
  violations. Orchestrator fixed the qualified UIDs (`SIM:`, `PARITY:`), the row words
  (carried, moved, superseded, retired), the code words (reused, corrected, replaced,
  retired) and the table formats so the document and the script agree.
- Next: review; owner freezes 6b before 6c-6e.

### 2026-10-30 · 7 · prompt
- Worker: sonnet, high
- Prompt: `program/prompts/7.md` — `VANTAGE_Lab_Design.md`: description file,
  template and generator in the standard build, fake car (timing per the executable
  model, described in our words), catalogue and every RCT fixture, provisional `⊘`
  values, `IMP-0022..0031` mapping, `LAB-WP`/`LAB-nn` build order, proposed
  `IMP-0030` text for `F-LAB-RESTART`.
- Next: review; owner freezes it before WP-06/07.

### 2026-10-30 · 6b · verdict
- Result: done. Register part 1 (words, 88-row sim code table grounded in ARCH §3/§11,
  four empty row sections with `Scope:` lines, how to check);
  `check_migration_register.py` (9 checks) and 23 tests. Orchestrator reran:
  `--selftest` 9 of 9 caught; plain run: universe 1572 (SIM CN 389, SYS 270, SW 375,
  IMP 375; PARITY STK 16, SYS 39, SW 54, IMP 54), only `C-MISSING`, as expected.
  Read §1-§3 and sampled the code table. Accepted deviations: files as well as
  directories in the code table; `Scope:` lines per section; comma lists for
  `superseded`.
- Findings: (a) a hard-coded `NEW_FILES` skip list would grow with every new script —
  rework: take the sim code universe from the `seed-from-sim` tag. (b) new files carry
  `COMPONENT: VANTAGE` (R-NAME-6) but the inherited `scripts/check_headers.py` demands
  `SIM`: 2 violations in the vantage gate — owner decision. (c) sim code 6a does not
  decide (worker's list) — owner confirms at the freeze. (d) 6c holds 659 rows (389
  `CN` + 270 `SYS`): propose splitting it into two packages.
- Verdict: rework (1) for (a); (b)-(d) to the owner.
- Next: 6b-R1.

### 2026-10-30 · 6b-R1 · prompt
- Worker: sonnet, medium
- Prompt: `program/prompts/6b-R1.md` — code universe from `git ls-tree seed-from-sim`;
  `NEW_FILES` removed; `C-SEED` when the tag is missing.
- Next: review; owner freezes 6b.

### 2026-10-30 · 6b-R1 · verdict
- Result: done. `NEW_FILES` gone; the code universe is `git ls-tree seed-from-sim`
  (`read_seed_entries`), injectable for tests; `C-SEED` when the tag is missing; a
  retired seed path is accepted. pytest 25 passed; `--selftest` 9 of 9. It found a
  real gap: `scripts/freeze.py`, `gui.py`, `vantage_native.py` existed at the seed and
  were removed in Plan B (`3f34a11`), so no row covers them. The worker patched the
  script once with a heredoc (house rule broken; result checked by the tests and the
  orchestrator's read of `read_seed_entries`).
- Verdict: accept; the three rows go to 6b-R2.
- Next: 6b-R2.

### 2026-10-30 · 6b-R2 · prompt
- Worker: sonnet, medium
- Prompt: `program/prompts/6b-R2.md` — three `retired` rows in §3.
- Next: review; owner freezes 6b.

### 2026-10-30 · 7 · verdict
- Result: done. `VANTAGE_Lab_Design.md` (718 lines, all 10 sections). Orchestrator read
  §4 (template: `exec` with every path reaching `publish`, RESTART, `inputTrusted`,
  fault and recovery, calibration load, odd-multiplier arithmetic so one wrong sample
  always changes the output), §4.3 (generator at configure time inside the one standard
  build, one library and bundle folder per component, `index.json`), §5 (Python fake car
  via `ctypes`, independent of `adas_sim`; task clock per the model; control logged at
  the nominal time, run at the start time, so the late-consumer case is recordable;
  closed list of 7 scenario verbs, each tied to a fixture or drill; deterministic mcap,
  no wall clock) and §7 (five provisional values, marked). Every RCT fixture covered;
  calibration keys ALL_CAPS with unit suffix. Accepted additions: `camera` topology
  (`F-CAM`), a reference re-run so `SYT-RSY-04` can pass in the lab, hang/crash keys for
  the failure drills.
- Owner decisions before the freeze: `Q-L1` (lab messages `adas.lab.LabSample`,
  `LabImage` in `interfaces/proto/lab/` — a contract addition, D14), `Q-L2` (new
  `IMP-0030` text), `Q-L3`..`Q-L9` (worker recommendations).
- Verdict: accept (pending the owner's answers and freeze)
- Why: every exit-check item holds.
- Next: CP-1, 6b-R2; then the owner's decisions.

### 2026-10-30 · 6b-R2 · verdict
- Result: done. Three `retired` rows (`scripts/freeze.py`, `gui.py`,
  `vantage_native.py`), each once (orchestrator grep; a duplicate pair from a false
  ENOENT was removed by the worker); checker: no finding but the expected `C-MISSING`.
- Verdict: accept
- Next: CP-1; then the owner freezes 6b and 7.

### 2026-10-30 · CP-1 · verdict
- Result: done. Concept page (outside every repo; backup in the orchestrator's
  scratchpad) follows 6a and D16-D18 in chapters 2-20 and the quiz: orchestrator +
  runner, recorded control rule, equal outputs, counter fallback, time rule and
  maximum gap, counter reset vs identity broken, SYS-0001 breaks logged, seal, engine
  run, no pause, no plug-in bundle. HTML parses; script passes `node --check`;
  orchestrator spot-checked the new glossary and ch. 8 text. Divergence file: "None open."
- Open for the owner: `MeasStatus.status` still lists `paused` in the contract while
  6a has no pause (6a keeps it unused); the page's "31 of 31" model result predates
  D16/D18 (not re-run).
- Verdict: accept
- Next: owner — toolchain-file hit (`TCF-1`) and the vantage-dev push; freeze of 6b and 7 with their
  open questions; commit of the new files.

### 2026-10-30 · STATE · decision
- Result: state at the end of this session's run.
  - Pushed: interfaces `vantage` `132727e`, vantage `main` `548e7fe`.
  - Committed, not pushed: vantage-dev `main` `943f78c` (held: `TCF-1` in `bc787c9`).
  - Not committed: `modules/vantage/docs/VANTAGE_Migration_Register.md`,
    `scripts/check_migration_register.py`, `tests/unit/test_check_migration_register.py`
    (6b, awaiting freeze); `modules/vantage/docs/VANTAGE_Lab_Design.md` (7, awaiting
    freeze); this ledger's entries since `943f78c`; prompts `CP-1`, `6b`, `6b-R1`,
    `6b-R2`, `7`; `program/CONCEPT_PAGE_DIVERGENCES.md` ("None open").
  - Next, in order: owner answers (`TCF-1`; `check_headers` token; 6b code dispositions;
    6c split; lab `Q-L1`..`Q-L9`); freeze 6b and 7; land the `IMP-0022`..`0031` design-row
    edits incl. `IMP-0030` (D14 design-row edits) and `Q-L1` if approved; then 6c (split
    in two), 6d (two packages), 6e; WP-06/07 (lab) and WP-08..10 (Vantage) per plan §6.

### 2026-10-30 · OWNER · decision
- Result: owner decisions, **all not done yet**; a fresh orchestrator session carries
  them out. Add the plan-level ones to `VANTAGE_DEV_PLAN.md` §2 (D15 change, D19 if
  needed) in the next accepted change.
  1. **`TCF-1` — option (a)** (not done yet). Fix line 1 of
     `toolchains/aarch64_qcc_qnx.cmake` to a neutral wording (for example "ARM64 QNX
     cross-compile toolchain"), rescan every unpushed file, then push vantage-dev.
     History stays for the screening. 1v carries the same line; the owner handles 1v;
     never touch 1v.
  2. **`check_headers.py`** (not done yet): a small package so it expects
     `COMPONENT: VANTAGE` (R-NAME-6); clears the 2 violations from 6b's new files.
  3. **6b** (not done yet): 6c split into CN and SYS, and 6d split at
     `SW-0188`/`SW-0189`, both approved. The ~15 sim-code dispositions 6a does not
     decide go to the owner as a table, one row each with a recommendation, approved
     per row.
  4. **D15 changed** (approved; not done yet): the register may give ONE disposition to
     a whole sim v2 section whose rows all share one fate, written as a UID range with
     the section name and the reason. `check_migration_register.py` expands each range
     to its rows, so every row is still disposed exactly once (none missing, none
     twice). `IMP` rows still inherit from the `SW` rows they serve. Lands in
     `VANTAGE_DEV_PLAN.md` D15 and in the script with tests (a planted overlap and a
     planted gap must both fail) **before 6c starts**.
  5. **Step 7 frozen once these land** (not done yet): `Q-L1` approved under D14 —
     `adas.lab.*` in `interfaces/proto/lab/`, each file headed "lab-only, never a
     production port"; `Q-L2`..`Q-L9` as recommended, except: max-age and recovery are
     **not engine defaults** — they are provisional lab values for ALL_CAPS calibration
     keys (R-NAME-3), marked provisional, and the engine refuses a setup without them.
     Also land `IMP-0030`'s new text (`Q-L2`) and the `IMP-0022`..`0031` file/symbol
     re-pointing (design-row edits).
  6. **Small points** (not done yet): `MeasStatus.status` `paused` kept, with a comment
     that nothing writes it until the developer face gets pause. Concept page "31 of
     31" kept, with a note that it was measured before D16-D18 and will be re-run on
     the lab. `program/CONCEPT_PAGE_DIVERGENCES.md`: delete.
  7. **Order of work after these:** commit and push vantage, then vantage-dev; start the
     lab build packages (`LAB-WP-01` onward); run 6c-6e and step 8 alongside them. The
     Vantage engine code (WP-08..10) waits for step 8's freeze and gate G2.

### 2026-10-30 · HANDOFF · decision
- Result: closing entry of this orchestrator session. No worker is running.
- **Decisions to carry out:** the OWNER entry just above, items 1-7, all not done yet.
- **Committed and pushed** (proven with `git ls-remote`):
  - interfaces `vantage` at `132727e` (RCT-A1..A5, WP-01..05, GSP-1, WP-03-R1;
    pushed range `d3b76bb..132727e`).
  - vantage `main` at `548e7fe` (6a frozen, VG-1; pushed range `1112191..548e7fe`).
- **Committed, not pushed:** vantage-dev `main` at `943f78c` (remote still `1337aaa`;
  8 commits, `bc787c9` holds the `TCF-1` line — decision 1).
- **Not committed:**
  - `modules/vantage`: `docs/VANTAGE_Migration_Register.md`,
    `scripts/check_migration_register.py`, `tests/unit/test_check_migration_register.py`
    (6b + R1 + R2, accepted, awaiting decisions 3-4 and the freeze);
    `docs/VANTAGE_Lab_Design.md` (7, accepted, awaiting decision 5).
  - vantage-dev: this ledger since `943f78c`; prompts `CP-1`, `6b`, `6b-R1`, `6b-R2`,
    `7`; `program/CONCEPT_PAGE_DIVERGENCES.md` (to be deleted, decision 6).
  - Outside every repo: the concept page `C:\ws\lt_learning\sim\vantage_concept.html`,
    updated by CP-1; the previous version is kept at
    `C:\ws\lt_learning\sim\backup\vantage_concept_before_CP-1.html`.
- **Gates:** G1 green. 6a frozen. C0 waits for the register (6b freeze, 6c-6e). G2-G5
  not green. Plan A status: WP-01, WP-05 done; WP-02..04 started; WP-06..10 open.
- **Open questions:** the ~15 undecided sim-code dispositions (decision 3, a table for
  the owner); the protobuf duplicate-registration risk when the fake car loads several
  lab libraries in one process (checked at `LAB-WP-02`); the lab's recording conventions
  (`Q-L4`) to confirm in step 8; the `MeasCycle` size is an estimate, not a measurement.
- **Next steps, in order:**
  1. `TCF-1` fix, rescan, push vantage-dev (decision 1).
  2. `check_headers` package (decision 2).
  3. D15 change in the plan + range support in `check_migration_register.py` with
     planted overlap and gap tests (decision 4); the sim-code disposition table to the
     owner (decision 3); then freeze 6b.
  4. Step 7 landings: `adas.lab.*` protos in `interfaces/proto/lab/` (lab-only header),
     max-age/recovery as provisional calibration keys the engine requires, `IMP-0030`
     text and `IMP-0022`..`0031` re-pointing; then freeze 7 (decision 5).
  5. Small points (decision 6): `paused` comment, "31 of 31" note, delete the
     divergence file.
  6. Commit and push vantage, then vantage-dev; interfaces too if step 4 changed it
     (submodule first).
  7. Lab build packages from `LAB-WP-01`; alongside them 6c (CN, SYS as two packages),
     6d (two packages at `SW-0188`/`0189`), 6e, then step 8. Vantage engine code
     (WP-08..10) waits for step 8's freeze and gate G2.
- Reminder for the next session: reference paths are in the orchestrator's memory
  only; check the reference before deciding or escalating and say "reference does X";
  never pass reference paths to workers or tracked files. Edit/Write calls on this
  filesystem may return a false ENOENT: verify, never retry blindly, never send
  parallel edits to one file.

### 2026-10-31 · OWNER · decision
- Result: owner answers at the start of this session.
  1. Decision 1 includes committing the `TCF-1` fix and pushing vantage-dev once the
     rescan is clean.
  2. **Worker models** (new): planning documents (requirement sets, design rows, test
     specs, architecture or contract changes, step 8 included) → `opus`, effort high
     (`vantage-planner`). Register rows (6c-6e) → `sonnet`, effort high
     (`vantage-builder`); the orchestrator reviews every disposition and range against
     6a before accepting. Code, build and mechanical edits → `sonnet`, medium or high
     (`vantage-builder` high, `vantage-mechanic` medium). Lands in
     `program/VANTAGE_PROGRAM.md` §1 and as D19 in the plan.
  3. For this round: commit and push each repo once its package is accepted (vantage,
     then vantage-dev; interfaces for `Q-L1`), grep before every commit, normal pushes
     only, `git ls-remote` after each push. The 6b disposition table and anything else
     needing a D14 decision goes to the owner before acting. Never touch 1v-superproject.
- Next: the HANDOFF steps in order: `TCF-1`, `HDR-1`, D15 ranges, step 7 landings.

### 2026-10-31 · TCF-1 · prompt
- Worker: vantage-mechanic (sonnet, medium)
- Prompt: `program/prompts/TCF-1.md` — line 1 of `toolchains/aarch64_qcc_qnx.cmake`
  becomes `# ARM64 QNX cross-compile toolchain` (decision 1).
- Next: review; rescan; commit; push vantage-dev.

### 2026-10-31 · HDR-1 · prompt
- Worker: vantage-builder (sonnet, high)
- Prompt: `program/prompts/HDR-1.md` — `check_headers.py` expects `COMPONENT: VANTAGE`;
  `SIM` stays accepted only on files present at `seed-from-sim` (inherited files are
  not re-headed); clears 6b's two violations (decision 2).
- Next: review.

### 2026-10-31 · TCF-1 · verdict
- Result: done. Line 1 of `toolchains/aarch64_qcc_qnx.cmake` reads `# ARM64 QNX
  cross-compile toolchain`; one line changed. The label for this package was renamed
  from the platform word to `TCF-1` everywhere in this ledger and in its prompt file,
  because the old label was itself the word being removed.
- Verdict: accept
- Next: rescan, then push vantage-dev.

### 2026-10-31 · HDR-1 · verdict
- Result: done. `check_headers.py` accepts `VANTAGE` everywhere, `SIM` only on paths in
  the `seed-from-sim` tree (read once, injectable); missing tag prints one line and
  accepts `SIM` nowhere. pytest `test_a1_check_headers.py` 14 passed; `check_headers`
  clean (300 Python, 63 C++). Accepted deviation: one existing test now writes
  `VANTAGE` into its non-seed temp file. Not done (not asked): a test of the missing-tag
  line.
- Verdict: accept
- Next: commit vantage.

### 2026-10-31 · PLN-1 · prompt
- Worker: vantage-mechanic (sonnet, medium)
- Prompt: `program/prompts/PLN-1.md` — D8 amended, D15 section ranges, new D19 (worker
  models), §6 rows 6c/6d split, program §1 table per the owner's worker-model decision;
  delete `program/CONCEPT_PAGE_DIVERGENCES.md` (decision 6).
- Next: review.

### 2026-10-31 · PLN-1 · verdict
- Result: done. Plan rows D8, D15, D19, 6c, 6d and program §1 (four rows plus the
  "one place they are set" sentence) word for word; CRLF kept; divergence file deleted,
  no other reference to it outside the ledger and prompts.
- Verdict: accept
- Next: commit vantage-dev.

### 2026-10-31 · COMMIT · decision
- Result: R-TEST-2 gate (Windows Python 3.14, which carries every test dependency;
  the rct-pytest venv lacks `jsonschema`, the vantage build venv lacks `pytest`):
  vantage `tests/unit` 1037 passed, 16 skipped (44 s); `check_invariants.py` clean
  (7.6 s). Reference scan of the committed files: clean. Committed and pushed vantage
  `main` `548e7fe..9c9ec00` (HDR-1), remote head `9c9ec00`.
  Reference scan of every vantage-dev file in the unpushed range and in this commit:
  clean except the old toolchain label (fixed by TCF-1) and benign "derived from"
  wording. **Found, not caused by this push:** the imported
  `.claude/agents/threat-screening.md` and `ip-provenance-scan.md` list the screened
  terms and the local reference path by design; both are on the remote since the
  first commit `05dc171`. Goes to the owner.
- Next: commit and push vantage-dev (TCF-1, PLN-1, pointer, ledger, prompts, agents).

### 2026-10-31 · REG-R1 · prompt
- Worker: vantage-builder (sonnet, high)
- Prompt: `program/prompts/REG-R1.md` — section rows in the register (D15): one
  disposition for a whole sim v2 section, expanded by the script; `C-RANGE`; planted
  overlap (`C-DUPLICATE`) and gap (`C-RANGE` + `C-MISSING`) tests (decision 4).
- Next: review; then 6b freeze with the sim-code table.

### 2026-10-31 · REG-R1 · verdict
- Result: done. Section rows (`..` in the UID cell) expand before every other row check;
  `Context.sections` maps each UID to its section label (`§N` or heading text, headings in
  code fences ignored); `C-RANGE` for malformed, reversed, `IMP`, empty, mixed-kind, no
  label, or not exactly one whole section (subsections included). Orchestrator reran:
  `--selftest` 10 of 10; plain run only `C-MISSING` (1572); 36 tests pass; register §2.1
  paragraph and §5 row read.
- Notes for 6c-6e prompts: section numbers repeat across documents (a section row is bound
  to one set and kind by its terms); three unnumbered headings hold live rows
  (`PART C — CONSTRAINTS`, 15 SYS rows; `Library loading splits in two`; `The design
  rows`): writers take labels from the script's `ctx.sections`, never retype them.
- Verdict: accept
- Next: 6b freeze waits for the owner's code-disposition table (decision 3).

### 2026-10-31 · L7-1 · prompt
- Worker: vantage-planner (opus, high)
- Prompt: `program/prompts/L7-1.md` — step 7 decisions: `Q-L1` consequences in the lab
  design, lab messages in the RCT fields tables, max-age/recovery as provisional
  calibration keys the generator requires, `IMP-0030` text, `IMP-0022`..`0031` re-pointed,
  `paused` note in the RCT layout table, open questions down to `Q-L4`, D20 in the plan.
  Reading of "the engine refuses a setup without them": the values are component
  calibration (`RCT:IMP-0024/0025`), so no code default anywhere and the lab generator
  refuses a component without them; a built bundle missing one keeps `SYS-0019`'s ERROR.
- Next: review; then freeze 7.

### 2026-10-31 · SP-1 · prompt
- Worker: vantage-mechanic (sonnet, medium)
- Prompt: `program/prompts/SP-1.md` — `paused` note on `MeasStatus.status` in
  `livemeas_layout.hpp`; concept page "31 of 31" note (backup first) (decision 6).
- Next: review.

### 2026-10-31 · SP-1 · verdict
- Result: done. `MeasStatus.status` comment in `livemeas_layout.hpp` carries the `paused`
  note (one line); concept page sentence has the "measured before D16-D18, re-run on the
  lab" note; backup `vantage_concept_before_SP-1.html` beside the earlier one; HTML parses.
- Verdict: accept
- Next: commit with interfaces after LAB-WP-01.

### 2026-10-31 · L7-1 · verdict
- Result: done. Lab design: `calibration` key removed from the description (values only in
  `catalogue/provisional.yaml`), generator refuses a component without them, formula moved
  to §7 as the provisional value's reason; §7 rows for both keys; lab messages point to
  `interfaces`; §4.3 command corrected to `build.bat -P base -t sil -p vs2026` (orchestrator
  catch: `-p` is the platform); `IMP-0030` proposal replaced by a pointer; open questions
  down to `Q-L4`. RCT design: *Lab-only messages* table (`LabSample` 1-2, `LabImage` 1-4),
  `paused` note, `IMP-0022`..`0031` re-pointed (`vantage-lab: <path>::<symbol>`), Box/UID/
  Serves/WP/Change/Tests cells unchanged (worker's script check). Plan: D20. trace_check
  PASS (78 reqs, 36 tests); `--status` unchanged; `--fields` FAIL (2) only on the two
  `adas.lab.*` rows, closed by `LAB-05`.
- Accepted deviations: `IMP-0030` tightened to 58 words (cap 60; the dropped clause is
  implied by "per run one control" and `IMP-0031`); new row `LAB-54` (`LAB-WP-02`) writes
  the calibration part of `provisional.yaml`, so the generator's refusal does not wait for
  `LAB-37` (`LAB-WP-06`); `LabImage.width`/`height` typed `uint32`.
- Orchestrator decisions on its questions: `adas-interfaces` stays `1.1.0` (only on the
  unmerged `vantage` branch; additive); `LAB-05` also wires `adas_generate_protos` (added
  to the LAB-WP-01 prompt). Left for a later design-row edit: `IMP-0028` still says "a
  component's description file" (the description sits in the topology file, `Q-L5`).
- Verdict: accept
- Next: step 7 frozen; LAB-WP-01.

### 2026-10-31 · 7 · decision
- Result: **step 7 frozen** (owner decision 5: frozen once its landings land; landed by
  L7-1). Interfaces is committed after LAB-WP-01 so `--fields` is never committed red.
- Next: LAB-WP-01; then commits interfaces, vantage, vantage-lab, vantage-dev.

### 2026-10-31 · LAB-WP-01 · prompt
- Worker: vantage-builder (sonnet, high)
- Prompt: `program/prompts/LAB-WP-01.md` — `vantage-lab` as a standard component (stub,
  build.yml, copied machinery, CMake, pyproject), configuring with no topology; the two
  lab protos in `interfaces` wired into `adas_generate_protos`; `CPY-1`, `--fields`,
  `check_signal_header --message` clean.
- Next: review.

### 2026-10-31 · LAB-WP-01 · verdict
- Result: done. `vantage-lab`: 6-line stub (`adas-toolchain/1.0.6`), `conf/build.yml`
  (`base.sil`, vs2026 + ubuntu_gcc, `adas-interfaces/1.1.0`, `protobuf/3.21.12`,
  `shared-library`, `src/platform/lab_sil`, `python_envs.lab`), copied machinery via
  `sync_copy_files.py` (dry run named only lab files), CMake with an empty
  `lab_add_topology`, `pyproject.toml`. `interfaces`: `proto/lab/lab_sample.proto`,
  `lab_image.proto` (header "lab-only, never a production port"), wired into
  `adas_generate_protos`. Evidence: interfaces vs2026 ctest 32/32 (18 s); `--fields`
  clean (14 messages, 6 enums); `check_signal_header --message adas.lab.*` PASS; lab
  `build.py -t sil -p vs2026` PASS (22 s, nothing to compile); `check_invariants` clean
  (10 s); trace_check PASS; orchestrator: interfaces `tests/python` 17 passed (3 s).
- Accepted deviations: `CMakePresets.json` and `requirements.lock` (made by
  `lock_python_env.py`) are needed by the standard build; the sync tool also places
  `gui.bat`, `setup.bat`, `scripts/setup.py`. Design text to follow (a later design-row
  edit, with `IMP-0028`'s wording): `LAB-03` lists eight copied files; `LAB-04`/`LAB-06`
  (or §8) name the presets and the lock file. `ubuntu_gcc` not yet built (R-TEST-6).
- Verdict: accept
- Next: commits; LAB-WP-02.

### 2026-10-31 · COMMIT · decision
- Result: reference scan of every committed file: clean. Pushed, normal pushes, each
  proven with `git ls-remote`: interfaces `vantage` `132727e..835cb07` (L7-1 RCT edits,
  SP-1, LAB-05); vantage-lab `main` `af584ec..b3f7f28` (LAB-WP-01); vantage `main`
  `9c9ec00..85a4587` (lab design, frozen, LAB-WP-01 ticked). The 6b files stay
  uncommitted until the owner freezes 6b.
- Next: vantage-dev commit (three pointers, D20, ledger, prompts); LAB-WP-02 running.

### 2026-10-31 · LAB-WP-02 · prompt
- Worker: vantage-builder (sonnet, high)
- Prompt: `program/prompts/LAB-WP-02.md` — topology loader, generator, provisional
  calibration file, template, `lab_add_topology`, the running example (scenario `base`):
  five libraries with bundles and `index.json`; all loaded into one process (the protobuf
  duplicate-registration risk); unit tests under `tests/unit/` (the design names no file
  for them — recorded here as an accepted gap).
- Next: review.

### 2026-10-31 · LAB-WP-02 · verdict
- Result: done. `topology.py` (every §3 check, plus type checks, unknown keys, file stem),
  `generate.py` (files of §4.2; refuses a component without its two keys; writes only on
  change), `catalogue/provisional.yaml` (calibration part, `status: provisional`),
  template (`exec` matches §4.1 line for line; orchestrator read it), `lab_add_topology`,
  `catalogue/running_example.yaml` (`base`). Five libraries A..E with bundles and
  `index.json`; all five load in one process, no protobuf duplicate registration;
  manifests carry `control`, inputs, `out`, `refSync`, `compState`, build id, bundle hash.
  Evidence: build 25 s; `tests/unit` 35 passed (orchestrator rerun 1.8 s); WSL 30 passed,
  5 skipped (Windows DLLs); `check_invariants` clean (8.5 s). Scratch run (not committed)
  showed RESTART, arithmetic, memory, ERROR and recovery, refSync, missing key, crash, hang.
- Accepted deviations: `setup.py --prepare vantage-lab` re-created the stale cached
  `adas-interfaces/1.1.0` (R-BUILD-7 refresh, no tracked lock changed); an empty-mapping
  `ego_params.yaml` per component because `adas_pack_config_bundle` requires one;
  `provisional.yaml` skipped by `lab_add_topology`; the ports header holds small helpers.
- Carried forward: `generate.py` has its own reader of `provisional.yaml`'s calibration part
  — `LAB-WP-06` must reuse it for `load_provisional`, not write a second one; making
  `EGO_PARAMS_YAML` optional in `interfaces` is a later small package (not contract).
- Verdict: accept
- Next: committed and pushed vantage-lab `b3f7f28..344835c`, vantage `85a4587..8603785`;
  LAB-WP-03.

### 2026-10-31 · LAB-WP-03 · prompt
- Worker: vantage-builder (sonnet, high)
- Prompt: `program/prompts/LAB-WP-03.md` — `LabLibrary`/`AdasPortSet` over `ctypes`,
  `MessageFactory` from the manifest's descriptor set, `LabHarness`, and the six `F-HARN`
  contract tests (`SYT-HDR-03`, `SYT-CTL-01/02`, `SYT-RSY-02/03`, `SYT-CST-06`); RCT rows
  ticked only when every listed test passes.
- Next: review.
- Note (orchestrator, process): the reference grep for the vantage-dev commit `05d1b1b`
  was run right after the push instead of before it; result clean.

### 2026-10-31 · LAB-WP-03 · verdict
- Result: done. `abi.py` (`AdasPort`/`AdasPortSet` mirror `adas_sil_abi.h`, offsets asserted;
  `LabLibrary`, `load_index`), `messages.py` (`MessageFactory` on a private
  `DescriptorPool`), `LabHarness` (incl. a fresh process per run), and one test per case of
  `SYT-HDR-03`, `SYT-CTL-01/02`, `SYT-RSY-02/03`, `SYT-CST-06`, plus two planted
  violations. Orchestrator rerun: `tests` 45 passed (3.5 s); trace_check PASS.
  RCT: `IMP-0024` `[x]`; `WP-06` `[~]` (rollup, `C-WPROLL`).
- Known weakness, accepted for now: `SYT-HDR-03.c2` needs the own count to start at
  `0xFFFFFFFF` and the design gives no hook, so the harness finds the `CycleStamp` triple in
  instance memory and overwrites it (refuses unless exactly one match). Cleaner option for
  later: a lab-only calibration key for the count start (a design-row edit), offered to the
  owner. `SYT-CST-06` shows the sticker decides; it cannot show a `compState` input is
  ignored because the template has none (by design, `IMP-0024`).
- Verdict: accept
- Next: pushed vantage-lab `344835c..79289e8`, interfaces `vantage` `835cb07..a0d5141`,
  vantage `8603785..dd67cd7`; LAB-WP-04.

### 2026-10-31 · LAB-WP-04 · prompt
- Worker: vantage-builder (sonnet, high)
- Prompt: `program/prompts/LAB-WP-04.md` — fake car on the running example (`Task`,
  `SourceTask`, `Bus`, `Car.run`, `ControlWriter`, `startComponent`, `McapRecorder`), the
  `car` verb, `SYT-HDR-01/02/04`, `SYT-CTL-05`, `SYT-RSY-01` and a byte-identical double run.
- Next: review.

### 2026-10-31 · LAB-WP-04 · verdict
- Result: done. `car.py` (`Task`, `SourceTask`, `Bus`, `ControlWriter`, `Car.run`,
  `startComponent`), `recorder.py` (`McapRecorder`), the `car` verb, 20 tests. Running
  example `base`, seed 1: 478 source, 621 each of control, data out, refSync, compState;
  89470 bytes; a second run in a new process is byte-identical, seed 2 differs.
  `SYT-HDR-01/02/04`, `SYT-CTL-05`, `SYT-RSY-01` pass, each with a planted violation.
  Orchestrator rerun: `tests` 65 passed (4.7 s); trace_check PASS; no wall clock or unseeded
  random in car or recorder. RCT: `IMP-0013`, `IMP-0015`, `IMP-0029` `[x]`; `IMP-0031` and
  `WP-07` `[~]`. The prompt's `_pb2` grep was too broad: `descriptor_pb2` is the protobuf
  runtime's own module, not generated bindings — accepted.
- Accepted deviations: a scenario with unbuilt verbs is refused, not ignored; a tick starts
  only if its start is within `duration_ms`; input-triggered starts exist but are untested
  until `data_triggered` (`LAB-47`).
- Queued for the design-row package: `RCT:IMP-0030` must be trimmed so a `closed by`
  sentence fits its 60-word cap (it stays `[ ]` meanwhile). `Q-L4`: the recorder follows
  Vantage's current mcap reader conventions (read, not imported) — confirm in step 8.
- Verdict: accept
- Next: pushed vantage-lab `79289e8..f4eb017`, interfaces `a0d5141..b0e028a`, vantage
  `dd67cd7..5b97fe7`; LAB-WP-05.

### 2026-10-31 · LAB-WP-05 · prompt
- Worker: vantage-builder (sonnet, high)
- Prompt: `program/prompts/LAB-WP-05.md` — `car.restart`, `silent`, `invalid`; scenarios
  `restart` and `fault`; `bundle_variant`; `SYT-CTL-07`, `SYT-CST-01`..`05`.
- Next: review.

### 2026-10-31 · LAB-WP-05 · verdict
- Result: done with one red test outside the worker's files (the loader test still
  expected only `base`); fixed by LAB-WP-05-R1. `ControlWriter` scripted restarts,
  `SourceTask` silent/invalid windows (half-open, on nominal time; a silent sample does not
  advance the counter), `parse_car_script` (other verbs refused), scenarios `restart` and
  `fault` verbatim, `bundle_variant` (never writes the source; refuses overlaps, unknown or
  conflicting keys). `SYT-CTL-07`, `SYT-CST-01`..`05` pass with planted violations. Fault
  run, B, seed 1: first ERROR 500 ms (`input in_Z not trusted`), RUNNING again 2220 ms after
  2 trusted runs (`LAB_B_RECOVERY_RUNS` = 2). RCT: `IMP-0014`, `0022`, `0025`, `0026`,
  `0028`, `0042` `[x]` (orchestrator checked each row's listed tests pass); `WP-04` `[x]`.
- Queued for the design-row package: §5.5 says windows cut on the sample's source time;
  `SYT-CST-02.c2` Steps define the first INVALID-window run by the `refSync` sticker.
- Verdict: accept

### 2026-10-31 · LAB-WP-05-R1 · prompt and verdict
- Worker: vantage-mechanic (sonnet, medium). Prompt: `program/prompts/LAB-WP-05-R1.md` — the
  loader test lists `base`, `restart`, `fault`. Result: one line changed; lab `tests` 83
  passed (orchestrator rerun 3.8 s). Verdict: accept.
- Next: pushed vantage-lab `f4eb017..0225866`, interfaces `b0e028a..628ed2d`, vantage
  `5b97fe7..e7e34d3`; LAB-WP-06.

### 2026-10-31 · LAB-WP-06 · prompt
- Worker: vantage-builder (sonnet, high)
- Prompt: `program/prompts/LAB-WP-06.md` — run setups (`ARCH §2.3` keys only), the run-setup
  provisional values, one reader of `provisional.yaml`, `equal_outputs`, `ReferenceResim`
  (any cut and order; `use_ref_sync=False` counts mismatches), `SYT-RSY-04` on every case;
  closes `G2` without Vantage.
- Next: review.

### 2026-10-31 · LAB-WP-06 · verdict
- Result: done. `setup_writer.py` (`load_provisional` is the only reader of
  `provisional.yaml`, moved out of `generate.py`; `write_run_setup` with a
  `.run.provisional.json` sidecar marking the provisional values), `run_setup:` part of
  `provisional.yaml`, `compare.equal_outputs`, `reference.ReferenceResim`, verbs `setup` and
  `reference`, `tests/test_catalogue.py`. `tests` 126 passed, 2 skipped (jump: a Vantage host
  call); `SYT-RSY-04` passes on `base` (`cut_c`, `all_simulated`), `restart`, `fault`;
  `use_ref_sync=False` counts 83/83/83/71 mismatching runs. RCT `IMP-0027`, `IMP-0031` `[x]`.
- Finding (orchestrator): the re-run fed every component the **recorded** sample even when
  the producer was simulated, so the cut and run-order tests could not fail (R-REQ-5).
  Reference model check: its resim feeds a simulated producer's own re-run outputs
  downstream, matched by counter, with readiness waiting. Rework (1).
- Accepted as is: the provisional sidecar; `limits.*` and `coherence_verdict` as provisional
  values; `outputs.path` and `outputs.livemeas` on every case; `RUN_SPEC_SCHEMA` one constant.
- For step 8 (Vantage requirements): the run setup `schema` version string (ARCH §2.3 gives
  none); how Vantage finds a `config`-variant bundle (the setup carries only its hash).
- Verdict: rework (1)
- Next: LAB-WP-06-R1.

### 2026-10-31 · LAB-WP-06-R1 · prompt
- Worker: vantage-builder (sonnet, high), the same agent continued
- Prompt: `program/prompts/LAB-WP-06-R1.md` — live feed of simulated outputs with readiness
  waiting and a reported deadlock; two planted violations only a live feed catches; `lab/`
  git-ignored.
- Next: review; then commit LAB-WP-06 and DR-1.

### 2026-10-31 · LAB-WP-06-R1 · verdict
- Result: done. Simulated producers' re-run outputs feed their consumers by refSync counter;
  a run waits in event order; a stall raises an error naming component, run, input and
  counter. Planted (a): `A` re-run with a key removed makes `A` and `B` differ (a recorded
  feed would leave `B` equal); with `A` measured all equal. Planted (b): a deleted `A` run
  is reported under three orders. `lab/` git-ignored. Orchestrator rerun: 128 passed,
  2 skipped (7.3 s); trace_check PASS; no Vantage import.
- Verdict: accept
- Gate note: the lab's part of `G2` is done (§6.4's first group passes on the lab with no
  Vantage). `G2` itself also needs `C0` (register frozen), so it is **not green yet**.
- Next: pushed vantage-lab `0225866..2a6df14`, interfaces `628ed2d..7b7e61a`, vantage
  `e7e34d3..ff366bc`; DR-1, then LAB-WP-07.

### 2026-10-31 · DR-1 · prompt
- Worker: vantage-planner (opus, high)
- Prompt: `program/prompts/DR-1.md` — design rows follow the build: `LAB-03` eight copied
  files, presets and lock file named, `tests/unit/` in §8, §5.5 window edges on source time,
  `RCT:IMP-0028` wording, `RCT:IMP-0030` tightened and `[~]`, `SYT-CST-02` Steps sentence.
- Next: review.

### 2026-10-31 · DR-1 · verdict (with rework 1)
- Result: done. Lab design: `LAB-03`, §4.3 and §8 list the eight copied files; `LAB-04` and
  §8 *CMake* name `CMakePresets.json`; `LAB-06` and §8 *Build stub* name `requirements.lock`
  (made by `scripts/lock_python_env.py`); §8 *Tests* adds `tests/unit/`; §5.5 window edges
  on source time. RCT: `IMP-0028` and the *Blocked* prose say "topology file";
  `IMP-0030` tightened to 59 words, `[~]` closed by `SYT-CTL-04`/`06` on Vantage (`WP-08`);
  `SYT-CST-02` Steps define the first INVALID-window run by the `refSync` sticker. No SYS
  row, message, field, layout item or case changed. Rework 1 (same worker,
  `program/prompts/DR-1-R1.md`): the two leftovers. trace_check PASS.
- Verdict: accept
- Next: pushed interfaces `7b7e61a..102519a`, vantage `ff366bc..569add8`; LAB-WP-07.

### 2026-10-31 · LAB-WP-07 · prompt
- Worker: vantage-builder (sonnet, high)
- Prompt: `program/prompts/LAB-WP-07.md` — the eight topologies of §6.1 after the running
  example, each with its corner case shown to happen; `SYT-RSY-04` on all; `loop_no_edge`
  refused at load.
- Next: review. `LAB-WP-08` waits in part for Vantage (`simengine --supervise`, `LAB-53`).

### 2026-10-31 · LAB-WP-07 · verdict
- Result: done. Eight catalogue files with §6.1's numbers (25 libraries over 9 topologies);
  each corner case shown to happen (`late_consumer` seed 2 holds the 100/102 ms example;
  `feedback` reads `B`'s previous run; `data_triggered` 66 runs for 66 `X` samples;
  `rates_not_multiple` runs on 20/30/70 ms; `measured_middle` `cut_m`); `loop_no_edge`
  accepted only with `expect: refused_at_load`. `SYT-RSY-04` passes on every case with 0
  mismatches by refSync; without refSync `late_consumer` differs in 28 runs and `feedback`
  in 100. Orchestrator rerun: 192 passed, 2 skipped (12.3 s). No RCT box moved.
- Accepted deviation: `feedback.yaml` declares `B` before `A` so `previous_cycle` matters.
- Note for the design owner: `rates_not_multiple` periods share the 10 ms source period, so
  a common divisor exists; the case still shows that no stage needs a shared grid.
- Verdict: accept
- Next: pushed vantage-lab `2a6df14..7f0cf1a`, vantage `569add8..c3293c6`; LAB-WP-08a.

### 2026-10-31 · LAB-WP-08a · prompt
- Worker: vantage-builder (sonnet, high)
- Prompt: `program/prompts/LAB-WP-08a.md` — `LAB-49`..`LAB-52`: camera topology with a big
  frame, `renumber`, `counter_jump`, `drop_sample`, `drop_ref_sync`, drill scenarios and the
  `hang`/`crash` cases; `LAB-53` (supervised run) waits for Vantage's `simengine --supervise`,
  so `LAB-WP-08` stays `[~]`.
- Next: review.

### 2026-10-31 · LAB-WP-08a · verdict
- Result: built `LAB-49`..`LAB-52`: `camera` topology (64x48 ramp, one 65536-byte frame),
  `renumber`, `counter_jump`, `drop_sample`, `drop_ref_sync`, drill scenarios and the
  `hang`/`crash` cases; 17 drill tests pass. Gate red on one stale test outside the
  worker's files (it asserted `renumber`/`drop_ref_sync` are refused). Drill results:
  `missing_sample` gap 3 (within `fallback_max_gap` 6), `missing_run` gap 10 (beyond),
  `counter_jump` X 49 → 1050 with equal outputs by refSync, `no_ref_sync` without the 621
  refSync messages. `LAB-WP-08` `[~]`, closed by `LAB-53` and the supervised `hang`/`crash`.
- Findings: (1) the §6.2 `renumber [A]` drill cannot break identity — `A` is clock-started,
  so its trigger counter already equals its run count (0 of 149 runs differ); (2)
  `no_ref_sync` mismatches cannot be counted because the reference re-run demands a
  `refSync` topic even with `use_ref_sync=False`.
- Orchestrator decisions: fix the stale test; allow the reference fix; **design-row edit
  (fixture only, no new verb):** the `renumber` drill moves to `data_triggered` with a
  `counter_jump` on `X` and `renumber: [T]` — reported to the owner.
- Accepted: `counter_jump` lives in `SourceTask`; `drop_sample` on source ports only;
  `big_frame` sets the pixel length; the car's hand-built `LabImage` descriptor, checked
  against `lab_image.proto` by a test.
- Verdict: rework (1)
- Next: LAB-WP-08a-R1 (same worker, `program/prompts/LAB-WP-08a-R1.md`).

### 2026-10-31 · LAB-WP-08a-R1 · verdict
- Result: done. Stale test updated; `ReferenceResim._plan` allows a missing `refSync` only
  with `use_ref_sync=False`; `renumber` drill in `data_triggered` (`expect: diverges`):
  `T`'s outputs differ from its control's counter in 57 of 66 runs (every run from the jump
  on), the refSync re-run reports it at run 10; `no_ref_sync` counts 82 differing runs.
  Lab design §6.2 row replaced and the sentence added; no other row changed. Orchestrator
  rerun: 224 passed, 14 skipped (14 s); trace_check PASS.
- Verdict: accept
- Next: pushed vantage-lab and vantage (see the commit lines below this session's summary).
  **Lab state:** `LAB-WP-01`..`07` `[x]`; `LAB-WP-08` `[~]`, closed by `LAB-53`, which needs
  Vantage's `simengine --supervise`. Nothing more in the lab is buildable now.

### 2026-10-31 · STATE · decision
- Result: end of this session's run. Everything pushed; no worker running.
- **Waiting on the owner:** (1) the 6b sim-code disposition table (17 rows, in the session
  summary) → 6b freeze → 6c-CN, 6c-SYS, 6d-1, 6d-2, 6e (prompts drafted, untracked, one at a
  time); (2) the two screening agent files on the remote (`05dc171`); (3) optional: a
  lab-only calibration key for the own-count start (`SYT-HDR-03.c2`); (4) the `renumber`
  drill fixture move (done, reported).
- **For step 8:** run setup `schema` version string; how Vantage finds a `config`-variant
  bundle; `Q-L4` recording conventions; `rates_not_multiple` still shares a 10 ms divisor.
- **Small packages for later:** `EGO_PARAMS_YAML` optional in `interfaces`; the car's
  hand-built `LabImage` descriptor could come from a manifest.
- Gates: G1 green; G2's lab part done, G2 waits for C0 (register). Plan A: WP-01, WP-04,
  WP-05 done; WP-02, 03, 06, 07 started (closed by Vantage-side tests); WP-08..10 wait for
  step 8 and G2.

### 2026-10-31 · OWNER · decision
- Result: owner decisions, **all not done yet**; the next orchestrator session carries them out.
  1. **6b table approved as recommended, except** (not done yet):
     - row 5 `src/adas_sim/diagnostics/`: split per file, one line per file. `evidence.py` and
       `explain.py` go with the viewer (6a §13, moved out); `console.py`, `determinism.py`,
       `diagnostics.py` and `summary.py` use the Session or two-clock model and are corrected
       or retired; the rest reused.
     - row 8 `src/adas_sim/io/`: reused, limited to reading a recording's topic index and
       schemas for the launcher; data for a run is read only by the C++ reader.
     - row 16 `scripts/check_anl_sw36.py`: corrected — its rule (R-SIM-23) stands, but it cites
       sim v2 ids; step 8 gives it a new id.
     Then 6b is frozen, and 6c-CN, 6c-SYS, 6d-1, 6d-2, 6e run one at a time.
  2. **Screening agents** (not done yet): drop `.claude/agents/threat-screening.md` and
     `ip-provenance-scan.md` from vantage-dev, and the "Before any push" row in
     `.claude/routing.md`; record it in `.claude/IMPORTED.md`. Screening runs from 1v. The
     history stays.
  3. **`SYT-HDR-03.c2` through the kit** (not done yet): `CycleStamp` takes the first count in
     its constructor (production 0); the lab template passes a lab-only calibration key. A
     design-row edit of `RCT:IMP-0013`, not a contract change. The harness memory overwrite is
     then removed.
  4. **`EGO_PARAMS_YAML` stays required** (R-SIM-3a) (not done yet): lab bundles carry the real
     `shared_config` ego file instead of an empty one.
  5. **The orchestrator's other choices and the queued design-row fixes: approved.**
  6. **Reference grep before a push, never after** (not done yet). It slipped twice, so the next
     session adds a local pre-push hook in each of the four repos that runs the grep and refuses
     the push on a hit. Hook and term list stay untracked (inside `.git`, never committed).
     Report it to the owner before installing.
  7. **Time of `LAB-WP-04`** (not done yet): it took 4 h 44 min. Find where the time went
     (R-TEST-7) before the next long package, and fix the cause if it will repeat.
- Next: closing HANDOFF below.

### 2026-10-31 · HANDOFF · decision
- Result: closing entry of this orchestrator session. No worker is running.
- **Decisions to carry out:** the OWNER entry just above, items 1-7, all not done yet.
- **Committed and pushed** (each local head equals `git ls-remote origin` at closing):
  - vantage-dev `main` at `c643da3` before this entry's commit (session range
    `1337aaa..c643da3`; this entry's commit is pushed on top, hash in the owner report).
  - vantage `main` at `5580e71` (session range `548e7fe..5580e71`: HDR-1, lab design frozen,
    `LAB-WP-01`..`08` boxes, DR-1).
  - interfaces `vantage` at `102519a` (session range `132727e..102519a`: lab messages (D20),
    L7-1, SP-1, RCT boxes from the lab, DR-1).
  - vantage-lab `main` at `5bfe2e7` (session range `af584ec..5bfe2e7`: `LAB-WP-01`..`07`,
    `LAB-WP-08` part 1).
- **Not committed:**
  - `modules/vantage`: `docs/VANTAGE_Migration_Register.md`, `scripts/check_migration_register.py`,
    `tests/unit/test_check_migration_register.py` (6b + R1 + R2 + REG-R1; decision 1 changes
    rows 5, 8, 16, then freeze). Do not touch until then.
  - vantage-dev: none after this commit.
- **Prompts drafted, not sent** (committed with this entry): `program/prompts/6c-CN.md`,
  `6c-SYS.md`, `6d-1.md`, `6d-2.md`, `6e.md` — register rows, `vantage-builder`, one at a time;
  the orchestrator checks every disposition and range against 6a before accepting (D19).
- **Package states:**
  - Program steps: 6a frozen; 6b accepted, awaiting decision 1 and freeze; 6c-6e not started;
    7 frozen (D20); 8 not started.
  - Lab (`VANTAGE_Lab_Design.md` §9): `LAB-WP-01`..`07` `[x]`; `LAB-WP-08` `[~]`, closed by
    `LAB-53` (`supervise.py`) and the supervised `hang`/`crash` cases, which need Vantage's
    `simengine --supervise`.
  - Plan A (`trace_check --status`): packages 3 done (WP-01, 04, 05), 4 started (WP-02, 03, 06,
    07: closed by Vantage-side tests), 3 open (WP-08..10: wait for step 8 and G2); design rows
    27 done, 6 started, 9 open of 42.
  - Gates: G1 green. G2: the lab's part done (§6.4's first group passes on the lab alone);
    G2 also needs C0 (register frozen). G3-G5 not green.
- **Open questions:**
  - For step 8: (a) the run setup `schema` version string (ARCH §2.3 gives none; the lab uses
    one constant, `RUN_SPEC_SCHEMA`); (b) how Vantage finds a `config`-variant bundle (the run
    setup carries only its hash); (c) `Q-L4`, the lab's recording conventions; (d)
    `rates_not_multiple` periods still share a 10 ms divisor.
  - Later, small: the car builds `LabImage`'s descriptor by hand (checked against the proto by
    a test); it could come from a manifest.
- **Next steps, in order:**
  1. Decision 7: find where `LAB-WP-04`'s 4 h 44 min went (R-TEST-7); fix a cause that will
     repeat, before the next long package.
  2. Decision 6: design the pre-push hook for the four repos, report it to the owner, install
     only on a yes.
  3. Decision 2: drop the two screening agents and the routing row; record in `IMPORTED.md`.
  4. Decision 1: the three 6b changes (rows 5, 8, 16), checker clean, freeze 6b; commit and push
     vantage, then vantage-dev.
  5. Decisions 3 and 4: `CycleStamp` first count (RCT `IMP-0013` design-row edit, kit, template
     key, harness without the memory overwrite); lab bundles carry the real `shared_config` ego
     file.
  6. 6c-CN → 6c-SYS → 6d-1 → 6d-2 → 6e, one at a time; then C0; then step 8 (planner), which
     also answers the four open questions; then the Vantage engine (WP-08..10) and `LAB-53`.
- Reminder for the next session: reference paths are in the orchestrator's memory only; check the
  reference before deciding or escalating and say "reference does X"; never pass reference paths
  to workers or tracked files. Windows Python (`cmd.exe /c python`) carries every test
  dependency. Edit/Write on this filesystem may report a false ENOENT: verify, never retry blindly.

### 2026-10-31 · OWNER · decision
- Result: owner answers at the start of this (fourth) session.
  1. **Order changed:** decision 7 → 6 → 2 → 1 (6b freeze) → 6c-CN, 6c-SYS, 6d-1, 6d-2, 6e →
     decisions 3 and 4 (lab clean-up, nothing waits on them; after 6e or alongside step 8) →
     C0 → step 8.
  2. For this round: commit and push each package once it is accepted, under the owner rules,
     **only after the pre-push hook is installed**.
  3. Brought to the owner before acting: the hook design, the 6b freeze, the `IMP-0013` edit,
     and anything that needs a D14 decision.
- Next: decision 7 (where `LAB-WP-04`'s time went), read-only, by the orchestrator.

### 2026-10-31 · OWNER-7 · decision
- Result: where `LAB-WP-04`'s 4 h 44 min went, measured from the worker's transcript
  (R-TEST-7). Real work about 9 min: 40 tool calls, 2.5 min of tool time, the rest model
  turns. **275.5 min was one stalled reply**: a streamed answer stopped mid-stream at
  21:00 UTC and the worker only resumed at 01:36, when it was told to repeat it. No build,
  test or Conan step was slow. Across all 46 worker transcripts of this workspace this is the
  only stall; every other worker's longest gap is under 10 min.
- Cause: outside the program (the model stream), rare, and can repeat. What made it cost
  hours was that nobody noticed.
- Fix: the orchestrator now starts a watchdog next to every worker it launches. It watches the
  worker's transcript and wakes the orchestrator when nothing has been written to it for
  15 min; the orchestrator then reads the tail, and stops and relaunches a stalled worker.
- Next: decision 6, the pre-push hook design, to the owner.

### 2026-10-31 · OWNER-6 · decision
- Result: pre-push hook designed and tested in the session scratchpad, not installed; brought
  to the owner. One `sh` script, a copy in each of the four repos' hook folders; one term list
  at `vantage-dev/.git/reference_terms.txt` (whole-word and anywhere entries). It scans only
  the commits being pushed (message, added lines, file names) and refuses on a hit or when the
  term list is missing. Tests: a planted commit refused with 3 hits (message, line, file
  name); `continue`/`contiguous`/`container` pass; clean ranges pass in 1-5 s. Current heads:
  only the two screening agent files hit (decision 2 removes them).
- Next: owner yes → install in all four repos; then decision 2.

### 2026-10-31 · OWNER · decision
- Result: owner answers on decisions 7 and 6, and two new points; none done yet.
  1. **Decision 7 accepted**, refined: on a watchdog alert, first check whether a command of
     the worker is still running (a long build writes nothing until it returns); stop and
     relaunch only if nothing is.
  2. **Decision 6: install the hook in all four repos**, after two checks: a push of a new
     branch or a tag (no remote sha) scans every commit not already on the remote, never
     zero and never only the tip; script and term list have LF line endings. Prove the
     planted refusal in each repo without pushing, test once under Windows Git, report.
     Then decision 2.
  3. **A — hold the 6b freeze for two rows:** `src/adas_sim/cli/record.py` and
     `src/adas_sim/sources/` change from `retired` to `replaced`. The in-process Python run
     path stays retired; the job (make a recording from a scenario) moves to the
     scenario-to-recording script of D22. Check that no other 6b row retires a
     recording-producing job without naming a successor. (6b is not frozen: it lands in the
     decision-1 package.)
  4. **B — draft D21 (launcher window) and D22 (recording writer)** for plan §2, with where
     each lands in §4 and §5, and bring them to the owner before writing them in. D21: a thin
     window over the launcher model (ARCH §3.1), no logic in it (R-SIM-16), narrows D13 from
     "no window" to "no viewer", built after C1. D22: no new writer library; vantage-lab's
     `McapRecorder` is the one writer for every recording; its conventions (Lab Design §5.6)
     become Vantage's input contract in step 8, closing `Q-L4`; two items for the owner: (1) a
     scenario-to-recording script building real interface messages, (2) whether
     `McapRecorder` moves into vantage once anything outside the lab uses it. Check the
     reference first, one line each. No reference tool, product or package names in any file.
- Next: hook checks and install; decision 2; then A and B drafts to the owner.

### 2026-10-31 · OWNER-6 · verdict
- Result: pre-push hook installed in all four repos (`.git/hooks/pre-push` and
  `.git/modules/modules/<name>/hooks/pre-push`); term list `vantage-dev/.git/reference_terms.txt`;
  nothing tracked. LF only (no CR in either file). Two fixes found by the checks: an annotated
  tag's message is now scanned (a tag name with `/` broke the first version), and a git
  command that fails refuses the push instead of passing silently. A new branch or tag is
  compared with the remote being pushed to (`--remotes=<remote>`, all remotes for a URL).
  Tests on a scratch remote (real `git push`): planted commit two below the tip of a new
  branch, refused; planted in the middle of an update, refused; planted tag message
  (also with `/` in the name), refused; clean tag on an unpushed planted commit, refused;
  clean branch, clean tag and a tag on a pushed commit, accepted; missing term list, refused.
  In each of the four repos (loose objects only, no ref touched): planted commit below a
  clean tip, refused (0.8-1.4 s); current head as a new branch, nothing new, accepted.
  Windows Git 2.54 from `modules/interfaces` to a temp bare repo: planted refused (2.0 s),
  clean accepted (1.6 s); temp repo deleted.
- Verdict: accept
- Next: decision 2 (`SCR-1`, vantage-mechanic).

### 2026-10-31 · SCR-1 · prompt
- Worker: vantage-mechanic
- Prompt: `program/prompts/SCR-1.md` — delete the two screening agents, the routing row,
  the `IMPORTED.md` agents cell and a local-change row, the `VANTAGE_PROGRAM.md` §1
  sentence. `.gitignore` keeps its lines (they stop a re-copied file being tracked again).
- Next: review; meanwhile the owner's points A and B (reference check, drafts).

### 2026-10-31 · SCR-1 · verdict
- Result: done (63 s). Both agent files deleted; the routing row gone; `IMPORTED.md` agents cell
  `low-effort-worker` and the 2026-10-31 local-change row; `VANTAGE_PROGRAM.md` §1 sentence
  reworded. Diff read: exactly those lines. `.gitignore` untouched. The exit-check grep in the
  prompt could not filter (`grep -rn .` prints no `./` prefix): a prompt error, the worker
  applied the filter by hand; only the new `IMPORTED.md` row remains.
- Verdict: accept
- Next: commit and push vantage-dev (decision 2 done); then decision 1 with point A.

### 2026-10-31 · 6b-R3 · prompt
- Worker: vantage-builder
- Prompt: `program/prompts/6b-R3.md` — owner decision 1: `diagnostics/` split into 13 file
  rows, `io/` reused for the topic index and schemas only, `check_anl_sw36.py` corrected.
  Point A's two rows (`cli/record.py`, `sources/`) wait for the owner's answer on D22, which
  names their successor.
- Next: review; meanwhile the A finding and the D21/D22 drafts to the owner.

### 2026-10-31 · OWNER-A-B · decision
- Result: brought to the owner, not acted on.
  - **A, the check:** of the retired 6b rows, three make recordings: `cli/record.py` and
    `sources/` (the owner's two) and `cli/run.py` (`sim run --record`, same `Recorder`). For
    `cli/run.py` a successor already exists in 6a: an engine run writes its own recording
    (`outputs.path`, ARCH §2.3, §3.3) — recommended `replaced`. Also `scripts/gui.py` (a
    launcher window) has a successor if D21 is approved — recommended `replaced` then.
  - **Reference:** its configuration window picks per component simulate / measure / an
    alternate input path / "alone" (pulls in declared feeders), the wiring file and a
    two-stage export, writes config files a command line also accepts, and starts the run.
    Its car logger and its simulation write one recording format with the data description
    embedded; stage results are exported into that same format.
  - **Conflicts found while drafting:** (1) 6a §1 says "no window and no viewer" — D21
    amends a frozen line; (2) an engine run writes its recording through the C++ writer
    (6a), so `McapRecorder` cannot be the only writer — drafted as one set of conventions,
    two writers, one conformance test; (3) vantage's Python `io/mcap.py` holds its own
    `McapWriter` (from sim) — moving `McapRecorder` in should replace it, not sit beside it;
    (4) `McapRecorder`'s metadata is lab-fixed (`synthetic`, `sim`, `mocked`) — it becomes
    arguments.
- Next: owner answers D21, D22, items (1)-(2), and the two extra rows; 6b-R3 in review.

### 2026-10-31 · 6b-R3 · verdict
- Result: done (107 s). `diagnostics/` as 13 file rows; `io/` reused, limited to the topic
  index and schemas; `check_anl_sw36.py` corrected. `C-CODE` clean (0.65 s); self-test 10 of
  10 caught. Rows read by the orchestrator; claims checked at `seed-from-sim`: `console.py`
  (30 lines) and `summary.py` (91) hold no `Session`, tick or two-clock use, so `reused`;
  `estimate.py` (`tick_count`) and `logging.py` (`tick=`) count ticks, so `corrected`.
- Deviations, to the owner with the freeze: (1) the owner's premise that `console.py` and
  `summary.py` use the Session model does not hold in the code — `reused`; (2) a
  `src/adas_sim/diagnostics/` directory row was kept because `C-CODE` demands one per entry
  under `src/adas_sim/`; its word carries no fact once all 13 files have rows.
  Recommendation: the checker accepts a directory whose every entry has its own row, and the
  directory row goes (planted test for both cases).
- Verdict: accept (rows); the directory row waits for the owner.
- Next: owner answers on D21/D22, the extra rows and these two points; then the 6b freeze.

### 2026-10-31 · OWNER · decision
- Result: owner answers for the 6b freeze, D21 and D22; none done yet. One package applies them
  all and brings the freeze; 6b freezes on the owner's yes; then 6c-CN onward.
  1. `console.py`, `summary.py`: `reused` (the owner's premise was wrong).
  2. The `src/adas_sim/diagnostics/` directory row goes; the register check accepts a directory
     whose every entry has its own row, with a planted test for each case.
  3. **D21 approved as drafted**, including 6a §1 "no window and no viewer" → "no viewer"
     (D14-approved).
  4. **D22 approved: one set of conventions, two writers, one conformance test.** C++: the
     engine's writer (6a), for an engine run's output recording. Python: `McapRecorder`, its
     metadata (`source_kind`, `run_kind`, provenance) turned into arguments; it replaces
     vantage's `io/mcap.py` `McapWriter` — the `io/` row says so and keeps reading the topic
     index and schemas. The conformance test proves both writers follow the conventions and
     that Vantage's reader accepts both.
  5. Item (1), the scenario-to-recording script: yes, planned, built after step 8.
  6. **Item (2): the Python writer moves to `interfaces`**, not vantage: the lab is Vantage's
     independent oracle and must not depend on Vantage; every user of the writer (lab,
     scenario script, bridges, car logger) is a producer, and producers already depend on
     `interfaces`. The recording conventions become an **additive RCT contract (approved
     under D14)**, and `Q-L4` closes there, not in step 8. The orchestrator drafts where in
     the RCT set it lands and which RCT rows change, and brings it with the freeze.
  7. `cli/run.py` → `replaced` by `outputs.path`; `scripts/gui.py` → `replaced` by D21.
- Next: read RCT, plan §4-§5, ARCH §1 and the checker; prompt the one package (6b-R4).

### 2026-10-31 · 6b-R4 · prompt
- Worker: vantage-builder
- Prompt: `program/prompts/6b-R4.md` — the owner's answers in one package: the register's
  `diagnostics/` directory row deleted, `io/` corrected (its `McapWriter` gives way to the
  Python writer in `interfaces`), `cli/record.py` and `sources/` replaced by
  `src/adas_sim/scenario/record.py`, `cli/run.py` by `src/simengine/main.cpp`
  (`outputs.path`), `scripts/gui.py` by `src/adas_sim/launcher/window.py`; the check accepts a
  directory fully covered by its files' rows (two planted tests); plan D21, D22 and their §4/§5
  lines; ARCH §1 "no viewer" and two §11 (N) rows naming the two new files (the register
  check requires a `replaced` target to be named in ARCH — flagged to the owner with the freeze).
- Next: review; meanwhile draft the RCT placement of the recording contract.

### 2026-10-31 · 6b-R4 · verdict
- Result: done (173 s). Register: `diagnostics/` directory row gone; `io/` corrected,
  `cli/record.py` and `sources/` replaced by `src/adas_sim/scenario/record.py`, `cli/run.py` by
  `src/simengine/main.cpp`, `scripts/gui.py` by `src/adas_sim/launcher/window.py`. Check: a
  directory with no row is covered when every file under it at the seed has a row, else each
  uncovered file is named; two tests and one self-test case. Plan: D21, D22, §4 (Plan A
  bullet, Plan C paragraph, lab bullet), §5 `C1s`/`C1w`. ARCH: §1 "no viewer … launcher window
  (`D21`)", `src/adas_sim/scenario/` in New directories, two §11 (N) rows. Diffs read; texts as
  given. Orchestrator rerun: code kinds clean (0.47 s), self-test 11/11, tests 38 passed (0.18 s).
- Verdict: accept
- Next: R-TEST-2 gate; the 6b freeze and the RCT placement of C6 to the owner.

### 2026-10-31 · 6b · decision
- Result: R-TEST-2 gate before the freeze commit: `modules/vantage` `tests/unit` 1050 passed,
  16 skipped (42.6 s, Windows Python); `check_invariants.py` clean (10.8 s, Windows Python; under
  WSL `SIG-1` cannot run, no `protoc`). Freeze and the RCT placement of the recording contract
  (C6) brought to the owner; nothing committed.
- Next: owner yes → commit and push vantage (register, check, tests, ARCH), then vantage-dev
  (plan, ledger, prompts, pointer); then 6c-CN.

### 2026-10-31 · OWNER · decision
- Result: owner answers; none done yet.
  1. **6b freeze: yes**; both commits as proposed (grep first; the hook checks at push).
  2. **C6 placement approved as drafted**; the lab finds the writer through `index.json`
     (choice 2a). The frozen 6a §11 rows and the Lab Design edits are approved.
  3. Corrections for `RCT-C6`: (a) `SYS-0039` contradicted `R-SIM-24` — reworded: the writer
     reads no clock, so the same arguments give a byte-identical file; the logging time is
     metadata passed in by the caller (the lab passes none); a car or HIL recording keeps its
     real logging time; `SYT-REC-03` stays. (b) `SYS-0040`: the closed origin list is
     measured / truth / mocked / simulated / overridden (`R-SIM-15`). (c) `ANL-06`: a third
     writer would appear in vantage or vantage-lab, not in interfaces — say where the check
     runs so it covers those repos, and plant the violation in one of them.
  4. Then `RCT-C6` (planner), then 6c-CN.
- Next: commit and push vantage, then vantage-dev (6b frozen).

### 2026-10-31 · 6b · decision
- Result: **6b frozen** (owner yes). vantage `111402d` pushed (`5580e71..111402d`): register,
  its check and tests, ARCH §1/§11. vantage-dev: plan (D21, D22), ledger, prompts, pointer.
- Next: `RCT-C6` (vantage-planner), then 6c-CN.

### 2026-10-31 · RCT-C6 · prompt
- Worker: vantage-planner
- Prompt: `program/prompts/RCT-C6.md` — contract area C6 `REC` (additive, D14-approved): RCT
  §6a in architecture, SYS (from `SYS-0037`) and test spec (`SYT-REC-01..04`, `ANL-06` run in
  vantage and vantage-lab, planted in vantage-lab); `WP-11` (interfaces), `WP-12` (lab),
  `WP-13` (vantage, after step 8), `IMP-0031` re-pointed; owner's three corrections built in
  (writer reads no clock; five origin tags; where `ANL-06` runs). Lab design: §5.6 points to
  C6, new `LAB-54`/`LAB-WP-09`, built rows keep their box, `Q-L4` decided. Plan §5 `A2`, §6 `5b`.
- Next: review; then 6c-CN.

### 2026-10-31 · 6c-6e · decision
- Result: the five drafted register prompts (`6c-CN`, `6c-SYS`, `6d-1`, `6d-2`, `6e`) gain two
  rules after the D10 rule: **D21** — a row on choosing stages, implementations, wiring,
  overrides or cuts in a window, or starting a run from one, is `carried` (the launcher
  window), not `superseded` by D13, which takes only what draws or views results; **D22 / RCT
  C6** — a row on what a recording must hold is `moved` to the C6 `RCT:SYS` rows, making a
  recording from a scenario is `carried` (the scenario script), the Python run path's own
  recorder is `superseded` by D22. Their context line names RCT §6a. Why: both decisions came
  after the prompts were drafted; without the rules a worker would send launcher-window rows
  to D13.
- Next: `RCT-C6` review, then 6c-CN.

### 2026-10-31 · OWNER · decision
- Result: refinement of the D21 and D22 rules in the 6c-6e prompts (applied next):
  (1) the window owns only how a choice is shown and entered; the rule behind a choice
  (feasible cuts, closing a gap by default, refusing a bad selection) is `carried` to the
  launcher model (ARCH §3.1), not to the window; (2) a row on what a recording must hold that
  no C6 row states is reported as an open question, never given a new obligation by the worker.
- Next: patch the five prompts; `RCT-C6` still running.

### 2026-10-31 · RCT-C6 · verdict
- Result: done (786 s). RCT §6a in architecture, SYS (`SYS-0037`..`0043`) and test spec
  (`SYT-REC-01`..`04`, `ANL-06`); `IMP-0043`..`0048` in `WP-11`..`13`, `IMP-0031` re-pointed
  (box kept); `layers.yaml` area `REC`, total 91; lab design §5.6 points to C6, `LAB-WP-09`
  (`LAB-55`, `LAB-56`), `Q-L4` decided; plan `A2` and step `5b`. Orchestrator rerun:
  trace_check PASS, 91 requirements, 41 tests (0.2 s); diffs read; no reference term; no
  narration. Accepted deviations: a seventh SYS row (`SYS-0043`, one Python writer, so
  `ANL-06` serves a row); lab rows `LAB-55`/`56` (`LAB-54` existed; `LAB-56` places the lab's
  REC tests); counts updated where they would be false.
- **To the owner before commit (D14, content beyond the approved draft):** (1) one clock in
  the recording — `publish_time` equals `log_time`, `manifest_version` 1 — consistent with F2,
  but it retires R-SIM-14's recording-level capture clock here (the inherited reader treats
  version >= 2 as "publish_time is capture time"); (2) `record_policies` in `manifest`
  (R-SIM-6); (3) the optional logging time is `created_utc` (the key the reader already
  reads). Worker questions with recommendations: drill recordings without `refSync` declare
  those ports `excluded`; `SYS-0041`'s refusal binds the Python writer, presence is checked on
  both writers' output. Lab design header "D1..D20" → next lab design edit.
- Verdict: accept (content), commit held for the owner.
- Next: 6c-CN in parallel (register §4.1 only; no file overlap).

### 2026-10-31 · 6c-CN · prompt
- Worker: vantage-builder
- Prompt: `program/prompts/6c-CN.md` — dispose every live `SIM:CN` row in register §4.1
  (rules incl. D21/D22 and the owner's refinement); the orchestrator checks every disposition
  and range against 6a (D19).
- Next: review.

### 2026-10-31 · 6c-CN · verdict
- Result: done (624 s). 389 live `SIM:CN` rows disposed in 209 rows (32 section, 177 single):
  carried 265, superseded 87, retired 26, moved 11; checker: no `SIM:CN` finding, self-test
  11/11. Orchestrator read all 209 rows against 6a and checked the doubtful ones at source:
  `CN-0099` (out-of-process hosting later) superseded by ARCH §9's isolated stage — right;
  `CN-0228`/`0251` (parallel only across recordings) superseded by ARCH §8 — right.
  Wrong: `CN-0069` moved to `RCT:SYS-0033`, which states only the 1.0.0 → 1.1.0 instance, not
  the versioning rule → `carried`; `CN-0359`'s Why names `scheduler/` as the replacement →
  the orchestrator.
- **Process:** the worker ran `git checkout -p` (no input, nothing changed) and a `pkill` that
  killed its own shell; the orchestrator verified every working copy: RCT-C6's changes, the
  plan, the prompts and the ledger intact. Rework prompts now name the forbidden commands.
- **Found while reviewing:** 6a §13's `R-SIM-14` row is cut mid-sentence ("The envelope
  field stays as the codec's |") and keeps the envelope's capture field — it contradicts
  C6's one clock; added to the owner's question 1 on C6.
- Owner questions from the worker (with the orchestrator's recommendation): `CN-0309` unit
  conversion contradicts `R-SIM-23` (retire it, rule wins); `CN-0304` carried without
  unit/scale; `CN-0021` trace catalogue only partly stated by `SYS-0037` (rate, group, size
  not); `CN-0111`/`0240`/`0319` are Vantage's artifacts, carried, no C6 row.
- Verdict: rework (1)
- Next: `6c-CN-R1` (same worker, `program/prompts/6c-CN-R1.md`).

### 2026-10-31 · 6c-CN-R1 · verdict
- Result: done. `CN-0069` carried (the contract states only the rule's first instance);
  `CN-0359` Why names the orchestrator (ARCH §11). Orchestrator read both rows; checker: no
  `SIM:CN` finding; self-test 11/11. Words now carried 266, superseded 87, retired 26, moved 10.
- Verdict: accept
- Next: owner answers on C6 and the 6c-CN questions; then commit C6 + 6c-CN; then 6c-SYS.

### 2026-10-31 · OWNER · decision
- Result: owner answers on C6 and 6c-CN; none done yet. One package applies them; then commit
  C6 and 6c-CN (interfaces, vantage, vantage-dev) and start 6c-SYS.
  1. **One clock per recording: yes (D14-approved).** The cut 6a §13 `R-SIM-14` row says one
     clock. vantage-dev's `.claude/rules/sim.md` gets an R-SIM-14 override note, recorded in
     `.claude/IMPORTED.md`, as for the grid.
  2. `record_policies` in `manifest`: yes. 3. `created_utc` as the optional logging time: yes.
  4. Drill recordings declare their missing `refSync` ports `excluded`: yes.
  5. `SYS-0041` split as recommended: yes.
  6. `CN-0309` retired (R-SIM-23 wins); `CN-0304` carried without unit and scale.
  7. `CN-0021`: "every port with its record policy" → `RCT:SYS-0037`; rate is the manifest's
     declared period (R-SIM-18); group and size are the open ECU-logging decision (RCT §13),
     retired here with that reason.
  8. `CN-0111`, `CN-0240`, `CN-0319`: carried to VNT; step 8 states them as Vantage's
     metadata on top of C6.
  9. Out of their section ranges: `CN-0083` retired (Vantage never corrects a recorded time;
     it matches by counter, D18, and uses the sender's time, C1); `CN-0084` superseded by D18
     and the per-port sample buffers (`buffer_depth`); `CN-0222` retired (state is not
     exposed by the ABI, the snapshot is parked in RCT, R-SIM-17 allows only recompute from
     the start; the checkpoint is progress, not state). **The 6c-SYS worker applies the same
     check: a row inside a carried section range that contradicts a rule or decision gets its
     own row.**
- Next: package `C6CN-R1`; the same check added to the 6c-SYS, 6d-1, 6d-2 and 6e prompts.

### 2026-10-31 · C6CN-R1 · prompt
- Worker: vantage-builder
- Prompt: `program/prompts/C6CN-R1.md` — R-SIM-14 override 2 in `.claude/rules/sim.md` and its
  `IMPORTED.md` row; 6a §13 `R-SIM-14` row says one clock; lab design header `D1..D22`, the
  `drop_ref_sync` drill lists its `refSync` ports `excluded`; register `CN-0021`, `0083`,
  `0084`, `0111`, `0222`, `0240`, `0304`, `0309`, `0319` as the owner decided, §8.1 and §18.2
  ranges skip the three taken out. `CN-0021` keeps one word (`moved`), its Why carrying the
  owner's split, because a UID is disposed exactly once (D15).
- The 6c-SYS, 6d-1, 6d-2 and 6e prompts gain the owner's in-section check.
- Next: review; commit C6 + 6c-CN; 6c-SYS.

### 2026-10-31 · C6CN-R1 · verdict
- Result: every edit in (90 s); exit check red: two `C-RANGE` — the §8.1 and §18.2 section
  rows skip `CN-0083`/`0084`/`0222`. The checker is right: D15 gives one disposition only to a
  whole section of one fate, so a section row never skips a UID; the prompt's "the ranges skip
  it" was the orchestrator's error (the worker's proposed checker change would have widened
  D15 without the owner). The same wording in the four remaining register prompts corrected:
  that section is listed row by row.
- Verdict: rework (1)
- Next: `C6CN-R2` (same worker): §8.1 and §18.2 row by row.

### 2026-10-31 · C6CN-R2 · verdict
- Result: done (39 s). §8.1 and §18.2 listed row by row (22 rows read by the orchestrator);
  `C-RANGE` gone, no `SIM:CN` finding, self-test 11/11. `CN-0303` stays `carried`, its
  capture-time capability dropped (D22) — right. Noted, not reworked: several §18.2 Whys
  restate the row instead of saying why it is kept (a third pass would be a second rework).
- R-TEST-2 gate: RCT trace_check PASS (0.2 s); root `scripts/tests` 831 passed, 24 skipped
  (69 s); `modules/vantage` `tests/unit` 1050 passed, 16 skipped (44 s); `check_invariants.py`
  clean (9.8 s); all on Windows Python.
- Verdict: accept
- Next: commit and push interfaces (C6), vantage (lab design, ARCH, register 6c-CN), vantage-dev.

### 2026-10-31 · C6-6c-CN · decision
- Result: committed and pushed: interfaces `vantage` `e5ab5ef` (`102519a..e5ab5ef`, C6);
  vantage `main` (lab design, ARCH §13, register 6c-CN); vantage-dev (plan `A2`/`5b`,
  `.claude/rules/sim.md` override 2 and `IMPORTED.md`, ledger, prompts, pointers).
- Next: 6c-SYS.

### 2026-10-31 · 6c-SYS · prompt
- Worker: vantage-builder
- Prompt: `program/prompts/6c-SYS.md` — dispose every live `SIM:SYS` row in register §4.1
  (rules incl. D21/D22, the owner's window/model refinement, the in-section check); the
  orchestrator checks every disposition and range against 6a (D19).
- Next: review.

### 2026-10-31 · 6c-SYS · verdict
- Result: done (431 s). 270 live `SIM:SYS` rows in 204 rows (14 section, 190 single): carried
  211, superseded 45, moved 4, retired 10; §4.1 listed 659 of 659, self-test 11/11. Orchestrator
  read all 204 rows against 6a and the owner's 6c-CN answers (consistent: `SYS-0007`/`0008`/
  `0014`/`0019`/`0218`/`0229` follow `CN-0083`/`0084`/`0304`/`0309`/`0222`/`0023`); checked at
  source `SYS-0012` (readers of another tool's output — carried, right), `SYS-0120` (= RCT
  `SYS-0037`, moved, right). Wrong: `SYS-0029` moved, but the contract states only the header
  fields, not simulation time, producer, mode, repeat → `carried`; `SYS-0058` (hosting out of
  process) superseded by ARCH §9, but the isolated stage meets it → `carried`.
- Worker's open questions, all with a best word given; for the owner: `SYS-0289..0291` /
  `CN-0400..0402` safety-evidence stance carried (plan and 6a silent); `SYS-0033`/`CN-0299`
  `unknown` origin is Vantage's reader tag, not in the contract list. The rest (layout halves
  carried with the viewer part named; `SYS-0252` three extension points) are step 8 wording.
- Verdict: rework (1)
- Next: `6c-SYS-R1` (same worker); then commit 6c; then 6d-1.

### 2026-10-31 · 6c-SYS-R1 · verdict
- Result: done (19 s). `SYS-0029` and `SYS-0058` carried; rows read; §4.1 listed 659 of 659,
  no finding but the 6d/6e `C-MISSING`; self-test 11/11; checker tests 38 passed;
  `check_invariants.py` clean (9.5 s). SYS words: carried 213, superseded 44, moved 3,
  retired 10.
- Verdict: accept. **6c done.**
- Next: commit and push vantage, then vantage-dev; then 6d-1.

### 2026-10-31 · 6d-1 · prompt
- Worker: vantage-builder
- Prompt: `program/prompts/6d-1.md` — dispose every live `SIM:SW` row up to `SW-0188` in register
  §4.2 (IMP rows inherit; rules incl. D21/D22, the window/model refinement, the in-section
  check); the orchestrator checks every disposition and range against 6a (D19).
- Next: review.

### 2026-10-31 · 6d-1 · verdict
- Result: done (366 s). 188 live `SIM:SW` rows (`SW-0001`..`0188`) in 163 rows (6 section, 157
  single): carried 150, superseded 32, retired 3, moved 3; 189 IMP rows inherit; §4.2 missing 0,
  no other finding; self-test 11/11; checker tests 38 passed. Orchestrator read all 163 rows
  against 6a and their parents (D10 grid, D18 selection, D22/ARCH §13 one clock, R-SIM-23,
  launcher model): consistent. Checked `SW-0147` (bounded, explicit restart) against ARCH §3.7
  — it forbids only turning a clean failure into a pass by retrying, and writes an attempt
  manifest: carried is right. The worker's questions follow parents already decided.
- Verdict: accept
- Next: commit and push vantage, then vantage-dev; then 6d-2.

### 2026-10-31 · 6d-2 · prompt
- Worker: vantage-builder
- Prompt: `program/prompts/6d-2.md` — dispose every live `SIM:SW` row from `SW-0189` in register
  §4.3 (IMP rows inherit); same rules; §4.1 and §4.2 committed as the parents' record.
- Next: review.

### 2026-10-31 · 6d-2 · verdict
- Result: done (371 s). 187 live `SIM:SW` rows (`SW-0189`..`0429`, 41 of them scattered in
  earlier sections) in 185 rows (1 section, 184 single): carried 149, superseded 24, retired 10,
  moved 4; 186 IMP rows inherit; §4.3 missing 0; self-test 11/11. Orchestrator read all 185 rows
  against 6a and the parents. Checked at source: `SW-0233` (three verbs — an engine run executes
  and writes its own recording, so all three still exist: carried right); `SW-0298`/`0352`/
  `0353` (= `RCT:SYS-0026`) and `SW-0355` (= `RCT:SYS-0030`) moved right; `SW-0356` (the player
  detects a dead engine) superseded by ARCH §9/§10 right — the player is gone and the
  heartbeat, seal and inspector replace the mechanism (not the `SYS-0058` case, where 6a meets
  the same obligation).
- Verdict: accept
- Next: commit and push vantage, then vantage-dev; then 6e.

### 2026-10-31 · 6e · prompt
- Worker: vantage-builder
- Prompt: `program/prompts/6e.md` — dispose every live row of the sim v2 parity set in register
  §4.4; same rules; §4.1-§4.3 committed as the parents' record.
- Next: review; then C0.
