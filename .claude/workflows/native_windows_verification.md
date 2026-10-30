# Workflow: Native-Windows / Real-GL Verification

Some verification in this repo cannot be done from a WSL session at all, and
must not be attempted here even partially. This workflow says what those
cases are, how to tell you're in one, and the exact procedure that closed
`VZ-18`'s live `cm_viz` gap (2026-08-21) so it doesn't have to be
rediscovered.

## When this applies

- Anything that opens a **real GL/GLFW window** (`viz_player` interactively,
  screenshots, `df_viz`'s own render thread with no
  `DF_VIZ_DISABLE_WINDOW=1`). **Never attempt this under WSL** — it has
  crashed the user's PC before (see `project_wsl_toolchain_gaps` memory).
  Headless verification (`DF_VIZ_DISABLE_WINDOW=1`, `--explain`, `ctest`)
  stays fine under WSL; only the real window is off-limits.
- Anything needing **CarMaker's own SDK** (`cm_viz`, a live TestRun) — it is
  Windows-only, full stop. There is no headless-under-WSL variant.
- A `vs2026` build/test cell of `docs/*_Sync_Plan_v0.1.md` §4.3's matrix —
  `ubuntu_gcc` cells run fine under WSL (`scripts/build.py` works there now,
  `WP-20`), but `vs2026` itself needs the MSVC toolchain.

## How to tell which situation you're in

1. `ListAgents` — look for a peer session that is confirmed to be running
   **natively on Windows** (not another WSL/Linux session of the same
   project). Nothing here labels this automatically; if unsure, ask the peer
   session directly what platform it's on before delegating real work to it.
2. If a native-Windows peer exists: `SendMessage` it the exact task,
   self-contained (it has no memory of this conversation) — state the goal,
   the repo state it should assume, and ask it to report back the **raw**
   evidence (build output, log file contents), not just a pass/fail summary.
3. If no such peer exists: hand the **exact commands** to the user and ask
   them to run them and paste back the raw output. Never accept "it worked"
   without the underlying log — this repo's own discipline throughout
   (`R-REQ-6`) is that a claim without the evidence behind it doesn't count,
   and a wrapper's own reported status can be wrong (see the `cmapi` quirk
   below) even when the thing under test is fine.

## The `cm_viz` / CarMaker verification procedure (proven 2026-08-21)

1. **Conan auth**, if `adas-local` rejects credentials:
   `conan remote login adas-local demo -p demo`.
2. **Republish whatever package changed**, locally, before building the
   consumer: `conan create .` in the changed module (e.g. `modules/viz` after
   a `conf/build.yml` fix) — a consumer building against the Conan cache
   won't see an uncommitted/unpublished fix otherwise.
3. **Build `cm_viz` on native `vs2026`** — deploys `CarMaker.win64.exe` +
   `df_sil.dll` + `df_viz.dll` together into `bin/`. `scripts/build.py`'s own
   `cm` target, or the CMake project directly if iterating.
4. **Run a real TestRun headless via CarMaker's own Python API** — do not
   drive this through the CarMaker GUI. `bsd/bsd_tos_left_straight` is the
   TestRun this procedure last used.
5. **Verify from the raw CarMaker log, not the wrapper's status field.** A
   clean pass reads: `df_viz host: loaded` → `df_viz host: Init ok` → the
   full simulated duration → `SIM_END` → clean `User_ShutDown`/
   `User_Cleanup`, no errors in between.
6. **Known false-negative, don't chase it as part of a `df_viz` change:**
   `run_cm_testrun.py`'s `cmapi` wrapper reports `ExecutionState.running`
   instead of `.success` after a run that is clean by every measure above —
   reproducible, a harness quirk unrelated to `df_viz`/`AdasViz::host`. If
   this is what you're actually asked to fix, it needs its own investigation
   (not attempted yet); otherwise, read the raw log and don't let this field
   report a false failure.

## The defect this procedure caught, once, worth re-checking after any `viz` `conf/build.yml` change

`modules/viz/conf/build.yml`'s `recipe.components` block can silently omit a
component whose CMake target genuinely exists (found: `host:` was missing
entirely, so a freshly published `adas-viz` package never exported
`AdasViz::host`, and `df`'s CarMaker link failed with "target was not
found" — invisible until someone actually tried linking it, because nothing
short of a real consumer build exercises Conan's exported-component list).
After adding a new CMake target under `modules/viz/cpp/viz/`, confirm its
Conan component is declared here too, before assuming a downstream consumer
will be able to link it.
