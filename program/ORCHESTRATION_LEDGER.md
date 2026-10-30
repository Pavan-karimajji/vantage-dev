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
