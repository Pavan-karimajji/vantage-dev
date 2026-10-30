# Rules — How Much To Test, and When (R-TEST)

Normative index. Governs **how much of the verification stack a change runs, and
at which moment** — not how to write a test (`skills/gtest_patterns`,
`skills/requirements_management.md`). Applies to every repo, every session.

**Why this exists — measured 2026-09-30:** every unit suite in the repo together
(root `scripts/tests`, toolchain `tests/` + `scripts/tests`, df `scripts/tests`)
plus `check_invariants.py` runs in **about 2 minutes**, and six tests that drive
real Conan/pip account for ~41 s of that. A change that nonetheless took over an
hour to verify spent it on **cold-machine runs, real C++ compiles, release
rebuilds, bundle builds and reruns after failures** — repeated mid-change. The
cost is in *what runs how often*, not in the unit tests.

| ID | Rule |
|---|---|
| R-TEST-1 | **While changing code, run only what the change can break:** the test file(s) of the module you edited plus the test files that import it (find them with `grep`). Not whole suites, not between every edit — at each checkpoint where you believe a piece is finished. |
| R-TEST-2 | **Once, before the final commit of a change, run the full unit gate:** every unit suite of each repo touched, plus `python scripts/check_invariants.py`. About 2 minutes; never skipped, never repeated mid-change. |
| R-TEST-3 | **Tests that drive a real external tool (Conan, pip, CMake, a compiler) are tagged slow** and skipped by default with a printed reason; `ADAS_SLOW_TESTS=1` runs them. They run in the R-TEST-2 gate **only when the change touches the code they exercise** (lockfiles, recipe export, pip/venv creation, CMake invocation). A skip is never silent. |
| R-TEST-4 | **System tests run once, before merge, and only when they cover what changed.** The cold-machine check (`scripts/cold_machine_check.py`) is the system test for setup/build/bundle/lock machinery, and **`COLD-1` in `check_invariants.py` decides whether it is due**: when COLD-1 is red, run exactly the mode(s) it names, once, after every other change of the branch is committed; when it is clean, do not run it. A change that ships nothing to components (tests, docs, a rule file, a component's algorithm code) must not turn COLD-1 red — if it does, the gate is watching too much and that is the thing to fix. Never run it "to see if it still works" mid-change. |
| R-TEST-5 | **Artifacts are built when they are the deliverable, never as a check.** Releasing a new `adas-build-tools`/`adas-toolchain` version, bumping pins or making an offline bundle happens once, when that *is* the change — not to probe whether something works. A released version is never rebuilt (D16), so an exploratory release is a permanent one. |
| R-TEST-6 | **WSL / Linux runs only for changes that can behave differently there** — path handling, a platform branch, the `ubuntu_gcc` bundle, shell launchers. A Windows-only tool (`cold_machine_check.py`) is not run under WSL; its **unit tests** must still pass there (use `PurePath`/`PureWindowsPath` for string logic, `skipUnless(win32)` only for what truly needs Windows). |
| R-TEST-7 | **Report durations, not just verdicts.** A verification report lists each suite/step with its seconds; the cold check records per-step seconds in `scripts/cold_run_record.json`. When a run is slow, read those numbers before deciding what to cut — a guess about where time goes is how the wrong thing gets skipped. |

**A failure means rerun the failing scope only** — the failing test file under
R-TEST-1, or the failing cold-check step's own command — then the R-TEST-2 gate
once more at the end. Rerunning a whole system test after a one-line fix is the
single most expensive habit this rule exists to stop.

See also: `workflows/change_build_machinery.md` (where R-TEST-4 is applied),
`rules/git.md` (R-GIT-1 commit order), `skills/gtest_patterns`.
