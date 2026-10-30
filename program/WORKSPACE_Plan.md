# Plan B — workspace

Creates `vantage-dev` as a working superproject: the repos, the submodules, the
root machinery, an isolated build, and `vantage` restructured to one standard
package. **Build structure only: no behaviour change.** What Vantage *does* is
Plan C; this plan only makes the place where that work happens.

Placement and gates: `VANTAGE_DEV_PLAN.md` §3, §5. How each step is run:
`VANTAGE_PROGRAM.md`. Status = the `Box` column below (`[x]` done, `[ ]` not
started, `[~]` started and says what closes it).

## 1. Sources

All seeds are taken from 1v-superproject at commit `d191172` (2026-10-28):

| Repo | Seed | 1v pointer |
|---|---|---|
| interfaces | branch `vantage` created from that commit | `83b7fe9` |
| toolchain | `main` at that commit | `f061dfd` |
| shared_config | `main` at that commit | `5634d3c` |
| sim → **vantage** | full history pushed to the new `vantage` repo | `a3fa0b9` |

Remotes (personal account, D7): `vantage-dev` exists. `vantage` and `vantage-lab`
are created by the owner (B0.1).

## 2. Two safety rules for the whole plan

1. **1v must never see vantage-dev's packages.** vantage-dev builds **aggregate only**
   (`--with-all`, B1.4), so its first-party modules never enter the Conan cache. A first-party package changed here gets a **version 1v
   does not use** (`adas-interfaces/1.1.0` on the `vantage` branch; the fork is
   named `adas-vantage/0.1.0`, not `adas-sim`). Without both, R-BUILD-7's refresh
   rule could hand 1v a newer same-version revision built from this workspace.
2. **Nothing is published or pushed without the owner.** No upload to the team
   Conan remote from this workspace until migration. Every push in this plan is an
   owner step.

## 3. Work packages

| Box | WP | Lands | Who | Done when |
|---|---|---|---|---|
| [x] | **B0.1** | GitHub repos `vantage` and `vantage-lab` exist, empty | owner | both `git ls-remote` reachable |
| [x] | **B0.2** | `vantage` repo holds sim's full history; tag `seed-from-sim` on the seed commit | worker (medium) prepares, owner pushes | `git log` of `vantage` ends at sim `a3fa0b9`; tag present on the remote |
| [x] | **B0.3** | `vantage-lab` repo with a one-paragraph `README.md` (its content is designed in Plan C, `VANTAGE_Lab_Design.md`) | worker (medium) prepares, owner pushes | remote has the README commit |
| [x] | **B0.4** | branch `vantage` on `interfaces`, created from `83b7fe9`, its package version bumped to `1.1.0` in `project(adas-interfaces VERSION …)` of its `CMakeLists.txt` (the recipe reads name and version from there); nothing else changed | worker (medium) prepares, owner pushes | branch on the remote; the diff from `83b7fe9` is the version line only |
| [x] | **B1.1** | submodules in vantage-dev: `modules/interfaces` (branch `vantage`), `modules/toolchain` (`main` @ `f061dfd`), `modules/shared_config` (`main` @ `5634d3c`), `modules/vantage`, `modules/vantage-lab`; `.gitmodules` carries each `branch =` | worker (medium) | `git submodule status` shows the five pointers listed in §1 / B0 |
| [x] | **B1.2** | root machinery copied from 1v `d191172`: `scripts/` (build dispatcher, setup, submodule init, Conan helpers, invariant checks and their tests), `setup.bat`, `toolchains/`; recorded in §4 | worker (medium) | files present; §4 lists every copied path |
| [x] | **B1.3** | root machinery adapted to this module list, minimal changes only: a check or step that names a module absent here (df CarMaker checks, df DLL lookups) **skips with a printed reason** instead of failing; every change listed in §4 for back-port | worker (high) | `python scripts/check_invariants.py` exits clean, each skip printed with its reason |
| [x] | **B1.4** | isolation by **aggregate builds**: normal builds go through the superproject dispatcher with `--with-all`, so first-party modules compile in-tree and are not packaged. Test builds are standalone (the dispatcher forces tests off in an aggregate), so `setup.py --prepare vantage` puts `adas-interfaces/1.1.0` — a version 1v never requests — into the cache. No separate `CONAN_HOME` (owner decision 2026-10-30). Commands in `README.md` | worker (high) | the cache holds no `adas-vantage`, and of `adas-interfaces` only 1v's `1.0.0` and this workspace's `1.1.0` |
| [x] | **B1.5** | `README.md` "Clone and build" section filled in | worker (medium) | a fresh clone + the written steps reaches B2.4's build |
| [x] | **B2.1** | in `vantage`: `vantage/` sub-package, `subcomponents:` key, `vantage.bat` and the scripts that only launch that app removed (D13); listed in Plan C's migration register as "not carried" | worker (high) | `grep -rn "subcomponents\|adas-vantage-app\|vantage_app" conf src scripts` empty; sim's own unit tests still pass |
| [x] | **B2.2** | in `vantage`: package renamed `adas-vantage/0.1.0` via `project(adas-vantage VERSION 0.1.0 …)` in `CMakeLists.txt` (the recipe's identity source) and its `requires` moved to `adas-interfaces/1.1.0` in `conf/build.yml`; the `AdasSim::` targets and code names kept as they are (renaming code is Plan C) | worker (high) | `conan graph info` names `adas-vantage/0.1.0`; requires `adas-interfaces/1.1.0` |
| [x] | **B2.3** | in `vantage`: standard component layout checked against `.claude/workflows/new_component.md` — 6-line conanfile stub, `conf/build.yml`, `conf/build_tools.version`, byte-identical copied files (`build.bat`, `build.sh`, `scripts/build.py`, `.clang-format`) | worker (medium) | `CPY-1` clean for `vantage` |
| [x] | **B2.4** | the workspace builds: `interfaces` (`package`), then `vantage` (`sil` and `gtest`, vs2026) | worker (medium) | both builds pass; `vantage` gtest suite passes with the same count as sim in 1v at `a3fa0b9`, minus only tests removed by B2.1 (each named) |
| [ ] | **B2.5** | Linux build of `vantage` (`ubuntu_gcc`, WSL) | worker (medium) | build + gtest pass (R-TEST-6: platform build is in scope here) |

**Gate G1 (workspace half):** every box above is `[x]`.

## 4. Imported root machinery (register)

Filled by B1.2 and B1.3. One row per copied path; local changes marked for
back-port to 1v at migration.

| Path | Source (1v `d191172`) | Local change | Back-port |
|---|---|---|---|
| `scripts/` (20 files), `scripts/tests/` (42 files) | `git archive d191172 scripts` | see rows below | — |
| `setup.bat`, `gui.bat`, `toolchains/`, `.clang-format` | `git archive d191172` | none | — |
| `.gitattributes`, `.gitignore` | 1v root | none | — |
| `scripts/cold_run_record.json` | — | **not imported**: it records cold runs of 1v commits; with no record COLD-1 passes by design | none |
| `scripts/check_invariants.py` | 1v | `_PYF1_TEST_PAIRS`: five keys `modules/sim/…` → `modules/vantage/…` (same test files, new home) | yes, with the sim → vantage rename |
| `scripts/check_invariants.py` | 1v | `main()`: a `SKIPPED: modules/<x>` finding is a printed note, not a violation, when `<x>` is not a submodule of this superproject (df here); a declared-but-missing module still fails | yes (harmless in 1v, where every named module is declared) |
| `scripts/tests/test_build_dispatcher.py` | 1v | `StaleCacheRefsTests`: example module `sim` → `vantage` (logic tests that need an existing module folder) | yes, with the rename |
| `scripts/tests/test_cold_machine_check.py` (7 tests), `test_bundle_tool_envs.py` (1), `test_bundle_guide.py` (2), `test_check_conan_resolution_cache_first.py` (1), `test_make_offline_bundle.py` (1) | 1v | skip with a printed reason unless `modules/df` is declared: they assert 1v's own module set (df's DLL, CARLA, viz pins) | yes (no-op in 1v, where df is declared) |

## 5. Not in this plan

- Renaming code (`simcore` namespace, `AdasSim::` targets, `COMPONENT: SIM`
  headers): Plan C, as one deliberate change.
- What survives from sim's Python package (`src/adas_sim`) and its tests: Plan C's
  migration register decides, row by row.
- Lab components, generator, fake car: Plan C (`VANTAGE_Lab_Design.md`).
- Any `viz` work (D13).
