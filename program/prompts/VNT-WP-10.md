# VNT-WP-10 — C1: the launcher reads the run-setup values from the run configuration (vantage branch `c1`)

## Context (read these, nothing else unless a step needs it)
- Working copy: `/mnt/c/ws/repo/vantage-dev`; `modules/vantage` is on branch **`c1`** — stay on
  it. Never commit, and never run `git checkout`, `git switch`, `git stash`, `git reset`,
  `git rm`, `git restore`, `pkill` or `kill`.
- **Owner conditions for `c1`:** every commit builds the whole of vantage and passes its full unit
  suite; every test stays green except the `c327be2` expected-red list — **which this package turns
  green**.
- `modules/vantage/docs/VANTAGE_Implementation_Design.md` row `IMP-0052` (`WP-10`) and its
  *Blocked* note; `VANTAGE_System_Requirements.md` `SYS-0048`; `VANTAGE_Test_Spec.md` `SYT-RUN-10`,
  fixture `F-RUN-CONFIG`; `VANTAGE_Architecture.md` §2.3, §3.1, §4; `D18 (4)`, `D22`
- What exists: `src/adas_sim/runspec/emit.py` (`RunSetupValues`, `emit_run_spec`, `WP-01`); the
  three callers that cannot supply it yet: `src/adas_sim/cli/resim.py`, `orchestrate/worker.py`,
  `check/runner.py`; `tests/unit/test_c3_check.py`'s provisional-values fixture; the expected-red
  tests named in `c327be2`'s commit message (`git -C modules/vantage show -s c327be2`)
- `.claude/rules/*` as before (no defaults in code; R-NAME-3 for any calibration-like key)

## Goal
`Pipeline.load` reads the run-setup values from the pipeline file (a `run_setup:` block plus
per-stage, per-port and per-input keys) and `Pipeline.setup_values` returns them; a missing one is
an `AuthoringError` naming it before any setup is written, with no default; the three callers pass
them on; `test_c3_check`'s fixture is gone; the expected-red tests pass.

## Steps
1. `IMP-0052` as written: `src/adas_sim/graph/pipeline.py::Pipeline.load`, `Pipeline.setup_values`;
   the three callers. Any pipeline file in `tests/` that these tests load gains the values it needs
   (taken from the lab's provisional numbers or written for the test — never a code default).
2. `SYT-RUN-10`: its `.c1` (each value removed in turn: an error naming it, no setup written) and
   `.c2` (all given: `sim resim`, the batch worker and `sim check` each write exactly the configured
   values), in `tests/` beside the other launcher tests (name the file).
3. Remove `test_c3_check.py`'s provisional-values fixture; its tests pass through the real path.
4. **Show the expected-red tests pass.** They skip in this checkout for lack of a stub paired with
   `simengine`. Build vantage (`-t gtest` builds the stub), copy the stub where those tests look for
   it (as the `WP-01` worker did), run each expected-red test by node id, then delete the copy and
   say so. Report each node id's result.
5. Builds and suites: `-t sil`, `-t gtest`, `-t package` (vs2026); C++ and Python unit suites (counts
   before and after, `py -3` as the earlier runs); `tests/system`; root `check_invariants.py`.
6. Boxes: `IMP-0052` and `WP-10` `[x]` only if step 4 shows every expected-red test passing and the
   fixture is gone; otherwise `[~]` saying what is left.

## Report back in this shape
1. Done / not done, in one line.
2. Files changed, one line each with what changed.
3. Exit check output: each command, pass/fail, seconds, counts before and after; each expected-red
   node id with its result.
4. Boxes set.
5. Deviations and open questions, each with your recommendation.
