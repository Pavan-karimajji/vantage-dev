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
