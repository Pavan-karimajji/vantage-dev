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
