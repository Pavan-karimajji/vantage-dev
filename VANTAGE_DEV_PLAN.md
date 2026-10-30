# vantage-dev — consolidated plan

The single entry point for the Vantage rebuild. Every other document in this
workspace is placed, named and ordered here. Status is never typed in this file:
it is computed from the checkboxes in the plan and design documents it points to.

Concept (plain English, with examples and evidence):
`C:\ws\lt_learning\sim\vantage_concept.html`.

---

## 1. What we are building, in five lines

1. **Vantage** is the simulation tool: a **launcher** (front end), an
   **orchestrator** (global scheduler), a **runner** (calls components) and a
   **live measurement writer**. Its output boundary is the **live measurement**: shared memory that
   carries everything a viewer needs. Viewers (viz) are not part of this design
   (D13).
2. The orchestrator is **event-driven**: one recorded control message = one run
   (else a new `measurement_counter` on the trigger input named in the run setup);
   every input is picked **by number** (the refSync the car wrote; a named sample not found
   → the newest sample not after that number; a stage with no refSync → "newest
   not after my trigger time"; each fallback badged).
3. The data contract (signal header rule + control input + refSync + component
   state + live measurement) is fixed **first**, because everything else is built against it.
   Detail: `modules/interfaces/docs/resim_contract/RCT_Architecture.md`.
4. The concept is proven on **generated dummy components** (the lab) with a known
   right answer, before any production component depends on it.
5. When Vantage is stable, its content replaces `sim` in 1v-superproject.

## 2. Decisions on the record

| # | Decision | Date |
|---|---|---|
| D1 | `vantage-dev` is a new superproject, sibling of 1v-superproject. Its submodules are the **same** repos as 1v, on a `vantage` branch where they change. Nothing is copied. | 2026-10-30 |
| D2 | The `vantage` component repo is a **fork of `sim` with its history**, restructured to the standard component layout as **one package**. `sim/vantage/` (the viz-dependent app, a second package that only existed to dodge a viz ↔ sim dependency loop) is not carried over (D13). | 2026-10-30 |
| D3 | `sim` in 1v-superproject is **not touched** during development. At migration its content is replaced by `vantage`. | 2026-10-30 |
| D4 | The lab is its own repo, `vantage-lab`. Lab components are **generated build outputs**, not repos. | 2026-10-30 |
| D5 | Vantage gets a **lean new requirement set**, layers **SYS + IMP** only. The sim v2 set is retired with one disposition per row in a migration register. | 2026-10-30 |
| D6 | The contracts (resim contract **and** live measurement layout) are one requirement set (**SYS + IMP**) inside `interfaces`. Prefixes: `RCT` (contracts), `VNT` (Vantage). | 2026-10-30 |
| D7 | No corporate mirror until migration. Personal remotes only. | 2026-10-30 |
| D8 | Working style: one orchestrator (Opus, high) writes prompts for workers and reviews every result; worker models per D19. Promoted to a `.claude` workflow only after first use. | 2026-10-30, amended 2026-10-31 |
| D9 | Proven on the lab first (the test-bench decision). Testing the scheduler on one real function component was the mistake this corrects. | 2026-10-29 |
| D10 | The scheduler is event-driven (§1). In this workspace it supersedes R-SIM-18's base-grid parts (override note in `.claude/rules/sim.md`); the 1v rule is amended at migration. | 2026-10-30 |
| D11 | `.claude/` is a pinned import of selected 1v files (`.claude/IMPORTED.md`); local changes are listed there and back-ported at migration. | 2026-10-30 |
| D12 | Requirement sets live in the module they describe (`interfaces`, `vantage`) so they travel with it at migration; only program documents live in this repo. `selftest_mutations.yaml` is added to a set only when it gets a check worth planting. | 2026-10-30 |
| D13 | **viz is out of this design.** Vantage does not depend on viz, which removes the viz ↔ sim loop and lets vantage be one package. The live measurement (named "board" until 2026-10-30) is Vantage's boundary and must carry **everything viz shows today**, so any viewer can be built on it later; how viz uses it is decided later. `viz` is not a submodule of this workspace. | 2026-10-30 |
| D14 | **What the contract is, after gate G1:** the messages, their fields, the live measurement layout and the RCT SYS rows. A change to any of these goes to the owner first. Filling in the file path of a lab or Vantage design row is a design-row edit, not a contract change. | 2026-10-30 |
| D15 | **The migration register disposes every sim v2 row exactly once.** An implementation (IMP) row inherits the disposition of the SW rows it serves; only exceptions are listed. A whole sim v2 section whose rows all share one fate may get **one** disposition, written as a UID range with the section name and the reason. A check script expands every range to its rows, computes the inheritance and fails on any sim v2 UID that is missing or disposed twice. | 2026-10-30, ranges 2026-10-31 |
| D16 | **`cycle_counter` keeps counting through RESTART; *equal outputs* leave it out.** *Equal outputs* (defined once in the RCT SYS preamble) means the same message count and byte-identical messages once each header's `cycle_counter` is 0. Amends `SYS-0007`, `SYS-0016`, `SYT-CTL-02`, `SYT-RSY-04`. An owner-approved contract change under D14. | 2026-10-30 |
| D17 | **Recorded controls and the 6a choices.** (1) Replaying a recorded control, Vantage copies its `measurement_counter` and `source_timestamp_us`, writes its own `cycle_counter` and sticker OK, forces RESTART on the first run and after a jump, and otherwise passes the recorded `op_mode`; amends `SYS-0011`, `SYT-CTL-06`. (2) The readiness limit is reported in `MeasDescription.readiness_limit_steps` (field 7). (3) A **counter reset** is `measurement_counter` and `cycle_counter` both going back (`counterDistance(prev, cur) < 0` for each): the sender restarted. **Identity broken** is `measurement_counter` going back or repeating with new content while `cycle_counter` keeps counting up; it is badged `KIND_IDENTITY_BROKEN`. Both counters are compared only with `counterDistance`, never with "smaller than" or "restarted from 1". Counter gaps, counter resets and stalled triggers are counted in the engine's event log; badge kinds for them come only when a reader needs them. (4) *Warming up* means a stage started mid-recording, badged until its outputs first equal the recorded outputs, and only when the recording holds them. (5) A step at every instant where any event happens; no pause for now; the live measurement writer ships as a static library first. (1), (2) and the `KIND_IDENTITY_BROKEN` text of (3) are owner-approved contract changes under D14. | 2026-10-30 |
| D18 | **Fallback by counter; breaks by the component under test; the seal; engine run.** (1) A recorded refSync entry whose sample is not found falls back by counter on that input: the newest sample whose `measurement_counter` is not after the wanted one (`counterDistance`), badged `KIND_FALLBACK`. The time rule ("newest not after the trigger time") is only for a stage with no recorded refSync, with one exception: beyond `fallback_max_gap` (a run-setup key, counter steps by `counterDistance`, value ⊘, provisional value from the lab design) the counter fallback takes nothing, the time rule picks the sample, `KIND_FALLBACK` is raised, and the event log records stage, port, wanted counter, found counter and gap. (2) A simulated output that does not copy its control's `measurement_counter` (a `SYS-0001` break by the component under test) goes to the engine's event log (stage, port, step) and the engine run goes on; `KIND_IDENTITY_BROKEN` keeps the D17 (3) meaning. (3) The live measurement is written only by the writer library; its seal call, used by the supervisor after the worker is confirmed dead, writes `outcome` and `status` and nothing else. (4) The run-setup keys `sampling` and `on_missing` are refused at load. (5) A **run** is one run of one component (the contract's meaning); the whole execution is an **engine run**: one outcome, one run id, one live measurement. (2), (3) and the `SYS-0028` wording of (5) are owner-approved under D14. | 2026-10-30 |
| D19 | **Worker models.** Planning documents (requirement sets, design rows, test specs, architecture or contract changes) go to an Opus worker at high effort. Migration-register rows go to a Sonnet worker at high effort, and the orchestrator checks every disposition and range against the frozen architecture before accepting. Code, build and mechanical edits go to a Sonnet worker at medium or high effort. Which agent type does which kind of work: `program/VANTAGE_PROGRAM.md` §1. | 2026-10-31 |
| D20 | **Lab messages and lab calibration (step 7).** (1) `adas.lab.LabSample` and `adas.lab.LabImage` live in `interfaces`, `proto/lab/`, package `adas.lab`, additive, one `sig_header` each, each file headed "lab-only, never a production port" (an owner-approved contract addition under D14). (2) A lab component's maximum input age and recovery runs are not defaults in code: they are the calibration keys `LAB_<C>_MAX_AGE_US` and `LAB_<C>_RECOVERY_RUNS`, given provisional values in `catalogue/provisional.yaml`; the generator refuses a component without them. (3) The lab design's other open questions as it recommends; `Q-L4` is confirmed in step 8. | 2026-10-30 |

## 3. Where everything lives

```
C:\ws\repo\vantage-dev\                         superproject (root holds no source code)
│
├─ VANTAGE_DEV_PLAN.md                          THIS FILE — consolidated plan
├─ README.md                                    what this workspace is, how to clone/build
├─ CLAUDE.md                                    bootstrap context for every AI session here
├─ .claude/                                     pinned import from 1v (IMPORTED.md lists it)
├─ program/                                     how the work is run (orchestration)
│    VANTAGE_PROGRAM.md                         orchestrator entry: roles, gates, prompt template,
│                                               review checklist, escalation, decision log
│    WORKSPACE_Plan.md                          Plan B work packages (checkboxes) + exit gates
│    ORCHESTRATION_LEDGER.md                    dated: prompt sent → worker result → review verdict
├─ scripts/ · setup.bat · toolchains/           root machinery, brought over from 1v and pointed
│                                               at this module list (Plan B, register in
│                                               WORKSPACE_Plan.md §4)
├─ .gitmodules
└─ modules/
     interfaces/      → interfaces repo, branch `vantage`
     │    docs/resim_contract/                  Plan A set (RCT): resim contract + live measurement layout
     │       layers.yaml
     │       RCT_Architecture.md                context: why, message shapes, live measurement layout, rejected
     │                                          options, ECU vs SIL duties, versioning, adoption order
     │       RCT_System_Requirements.md         SYS rows
     │       RCT_Implementation_Design.md       IMP rows (boxed) → work packages
     │       RCT_Test_Spec.md
     toolchain/       → toolchain repo, `main` (branch `vantage` only if a build change is needed)
     shared_config/   → shared_config repo, `main` (ego parameters for config bundles)
     vantage/         → NEW repo, fork of sim
     │    docs/                                 Plan C set (VNT)
     │       layers.yaml
     │       VANTAGE_Architecture.md            context: parts, six rules, naming, threads
     │       VANTAGE_Migration_Register.md      context (register): from sim — reused / replaced /
     │                                          corrected / new; disposition of every sim v2 row
     │       VANTAGE_Lab_Design.md              context, rollup: generator, fake car, catalogue
     │       VANTAGE_System_Requirements.md     SYS rows
     │       VANTAGE_Implementation_Design.md   IMP rows (boxed) → work packages
     │       VANTAGE_Test_Spec.md
     vantage-lab/     → NEW repo: generator, fake car, topology catalogue (code)
```

Requirement sets are checked by the existing module-agnostic checker
(`.claude/templates/requirements/trace_check.py --set <dir>`), driven only by each
set's `layers.yaml` (R-REQ-12). Progress: `--status` on each set.

## 4. The three plans and the lab

### Plan A — resim contract (`interfaces`, RCT)
What every component, in the car and on the PC, must publish so a resim can
reproduce it.
- **Signal header** rule: `measurement_counter` and `source_timestamp_us` copied
  from the run's control input; `cycle_counter` and `sig_status` each sender's
  own; one timestamp (`capture_timestamp_us` retired); wrap-around rules.
- **Control input** (`CycleControl`): per run, written by the scheduler; header +
  op mode (RESTART / RUN).
- **RefSync**: per run, the headers of the inputs actually read. Written by the
  component from what it read, never copied through.
- **Component state**: values and readers fixed (`SUCCESS` retired).
- Parked: state snapshot, error bits. Triggers and previous-cycle edges are
  Vantage's run setup (Plan C), not manifest fields.
- **ECU duties**: what must be logged so "exact" is reachable on car recordings
  (tied to the open camera-ECU logging decision).
- **Adoption order** for components already in 1v (df, vdy, perception-core), so
  merging the `vantage` branch never breaks 1v.
- **Live measurement layout** (D13): the shared-memory contract between Vantage
  and any reader, one layout header in `interfaces` (`cpp/livemeas/`, package
  `adas.livemeas`). It carries everything viz shows today. Its parts and why:
  `RCT_Architecture.md` §6; every field and the layout:
  `RCT_Implementation_Design.md`.

### Plan B — workspace (`program/WORKSPACE_Plan.md`, no requirement layers)
Create `vantage-dev`, the `vantage` fork and `vantage-lab`; bring over root
machinery; restructure `vantage` to the standard component layout as one package
(without `sim/vantage/`); branch on `interfaces`; everything builds with the
shared toolchain.

### Plan C — Vantage (`vantage`, VNT)
Launcher, orchestrator (six rules), runner, per-port sample buffers, live measurement writer
(three C calls, common to every engine), a **live measurement inspector** (a
command-line tool that attaches, dumps and checks the live measurement, used
instead of a viewer to verify it), other engines. Starts from the reuse analysis (seed: 1v
`docs/vantage_event_resim_plan.md`).

### The lab (`vantage-lab`, designed in `VANTAGE_Lab_Design.md`)
Your A, B, C, D components, **generated** from a short description file instead
of hand-written, plus a fake car that produces the known right answer.

**Kept deliberately small:**
- **One** C++ component template and **one** Python script that fills it from a
  YAML file. No code-generation framework, no plug-in system.
- The "algorithm" is plain arithmetic over inputs (and a running sum for
  components with memory), so a wrong input sample always changes the output.
- The fake car reuses the executable model already written
  (in 1v's git-ignored sim study notes)
  as its timing logic.
- First milestone: the running example only (X, Y, Z, A–E). More topologies are
  added as files, one corner case at a time.

## 5. Order and gates

```
B0  create repos (local)            ─┐
B1  workspace builds, unchanged sim ─┤
A   contract set frozen             ─┼─► gate G1: contract frozen + workspace builds
                                     │
C0  architecture + register frozen  ─┤
L1  lab: generator + running example ┼─► gate G2: lab components pass contract tests
L2  lab: fake car recordings        ─┘
C1  orchestrator (six rules)        ───► gate G3: every lab topology exact vs fake car,
                                          single- and multi-threaded identical
C2  livemeas writer + inspector     ───► gate G4: for every lab topology the inspector finds
                                          every live-measurement item in it, and every
                                          failure drill passes (with test readers, no viewer)
C3  other engines (CARLA bridge, CarMaker) via the common live measurement writer
V   viewer on the live measurement ───  later, separate decision (D13)
M   migration into 1v               ───► gate G5: 1v builds and its tests pass with sim
                                          replaced by vantage and branches merged
```

No phase starts before the gate in front of it is green. Each document is frozen
before the next one that depends on it is written.

**How the branches reach 1v at migration (G5).** During development 1v keeps
pointing at `main` of `interfaces`, so df, vdy, perception-core and the demo
build exactly as today. At migration: merge the `vantage` branch of `interfaces`
into its `main` (submodule first), bump 1v's submodule pointers, replace `sim`'s content
with `vantage`, then back-port the `.claude` changes listed in
`.claude/IMPORTED.md`. Plan A keeps every contract change **additive** (new
messages and fields, nothing removed or renamed) and carries an **adoption
order**, so 1v's existing components keep building on the day of the merge and
start writing refSyncs one at a time.

## 6. Writing order for this workspace's documents

| # | Document | Depends on |
|---|---|---|
| 1 | `VANTAGE_DEV_PLAN.md` (this file) | — |
| 2 | `CLAUDE.md` + `.claude/` import (`IMPORTED.md`, `routing.md`) | 1 |
| 2b | `README.md` | 1 |
| 3 | `program/VANTAGE_PROGRAM.md` + `program/ORCHESTRATION_LEDGER.md` | 1, 2 |
| 4 | `program/WORKSPACE_Plan.md` | 3 |
| 5 | Plan A set (`interfaces/docs/resim_contract/`) | 4 (branch exists) |
| 6a | `VANTAGE_Architecture.md` (frozen before 6b) | 5 |
| 6b | `VANTAGE_Migration_Register.md` part 1: sim code reused / replaced / corrected / new; the disposition words; the register check script (D15) | 6a |
| 6c | Register: disposition of every sim v2 CN and SYS row (two worker packages: CN, SYS) | 6b |
| 6d | Register: disposition of every sim v2 SW row (two worker packages, split at SW-0188 / SW-0189) | 6b |
| 6e | Register: disposition of every row of the sim v2 parity set | 6b |
| 7 | `VANTAGE_Lab_Design.md` | 5, 6a |
| 8 | Plan C requirements + design + test spec | 6a–6e, 7 |

## 7. Rules that apply everywhere

All `.claude/rules` of 1v-superproject apply unchanged. The ones most often hit
here: R-GIT-1/2 (submodule first; commit and push only when asked),
R-BUILD-1..6 (standard build, no private build structure), R-REQ (layers,
falsifiable Accept, generated status), R-IFACE-4 (signal header), R-TEST
(run only what the change can break; full gate once before the final commit),
R-STYLE (file headers, minimal diffs). No company names anywhere except
L&T EPS where code requires it. No reference-tool names in tracked files.

## 8. Sources

- Concept: `C:\ws\lt_learning\sim\vantage_concept.html`
- Reuse analysis: 1v-superproject `docs/vantage_event_resim_plan.md`
- Evidence: the sync-and-scheduling notes, the experiments and the scheduler
  executable model, in 1v's git-ignored sim study notes.
