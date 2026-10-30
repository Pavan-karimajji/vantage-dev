# Workflow: change_build_machinery

Enforces **R-BUILD-6**. The machinery files are shared across every
component, so a change to one is a change to **all** — but the three file
categories reach components by different mechanisms, and conflating them is
the mistake this workflow exists to prevent.

**Before merging a change to setup or build machinery, run `scripts/cold_machine_check.py`**
(RD-14, `remove_develop_mode_plan.md`) — one command, real proof against a
scratch CONAN_HOME and a second empty `adas-local`, that a fresh machine can
still get from `setup.bat` to a real `df` build with no manual steps. **Once,
before merge, after the branch's last other commit — not after every edit**
(`rules/testing.md` R-TEST-4: `COLD-1` in `check_invariants.py` names the
mode(s) that are due; run exactly those).

## Which category are you changing?

| Category | Files | Mechanism |
|---|---|---|
| **Recipe logic** | `modules/toolchain/base_recipe.py` (`AdasComponent`) | `python_requires` — one source, imported. Components adopt by bumping a version pin. |
| **Build-tools logic** | `modules/toolchain/adas_build_tools/*.py` (`cli.py`, `config.py`, `conan_ops.py`, `builder.py`, `logging_utils.py`, `gui.py`) | Installable Python package (`adas-build-tools`), pinned per component via `conf/build_tools.version`. **Not** copy-distributed — same pin-and-adopt shape as recipe logic, not the fan-out shape below. |
| **Copy-distributed** | `build.bat`, `build.sh`, component `scripts/build.py`, `scripts/build_gui.py`, `.clang-format` | Copied from `modules/toolchain/copy_files/`, held identical by `CPY-1`. `scripts/build.py`/`build_gui.py` are the **bootstrap stubs only** — they find/create `.venv`, install the pinned `adas_build_tools`, and exec into it. A change to what a build actually *does* almost never belongs here — see Category B (build-tools logic) instead. |

A component's own `conanfile.py` is a 6-line stub and is **never** the place
to make a machinery change. (The root `scripts/build.py` dispatcher is
superproject-only and changes independently of all three.)

**The mistake this categorization exists to prevent:** editing
`modules/toolchain/copy_files/scripts/build.py` to fix a build-logic bug
(a wrong `conan install` flag, a Conan auto-provisioning bug, an
`ensure_conan_environment()` fix, a CLI argument change). That file is a
~150-line stub — `find_component_root()`/`read_pin()`/`ensure_venv()`/
`exec_into_venv()` and nothing else. The actual logic lives in
`adas_build_tools/`, is Category B below, and needs its own version bump
+ publish, not a fan-out.

## A — Recipe logic (`base_recipe.py`)

1. **Edit `modules/toolchain/base_recipe.py`.** Never a component's
   `conanfile.py`, and never a per-component hook — per-component
   difference belongs in that component's `conf/build.yml`.
2. **Bump `modules/toolchain/VERSION`** and publish:
   `conan export .` then `conan upload adas-toolchain/<ver> -r adas-local
   --confirm`. Commit inside `modules/toolchain` first (`R-GIT-1`).
3. **Bump every component's pin in one coordinated pass** — the
   `python_requires = "adas-toolchain/<ver>"` line, one per component.
   Coordinated, not per-component-on-its-own-schedule: an old and a new
   recipe genuinely can diverge in behaviour in ways `conf/build.yml`
   doesn't paper over (e.g. a `layout()` bugfix). This is R-BUILD-6's stated
   exception — the *change* lands once, the *adoption* is the pass.
4. **Verify per component, cheaply first:** `conan inspect .` and
   `conan graph info . -o project=base --format=json` before and after. The
   only legitimate differences are the `python_requires` node and the
   `package_id` it shifts.
5. **Then build for real** in at least two components with different
   `package_type` branches (e.g. `df` shared-library + `shared_config`
   pure-data): `build.bat -t sil -p vs2026` and `-t gtest -p vs2026`.

## B — Build-tools logic (`adas_build_tools/`)

Same pin-and-adopt shape as Category A, for the Python package instead of
the C++ recipe. This is where a `conan install`/cmake-invocation bug, an
`ensure_conan_environment()`/Conan auto-provisioning fix, a CLI argument
change, or a GUI (`gui.py`) fix belongs — **not** the stub in Category C.

1. **Edit the relevant module under `modules/toolchain/adas_build_tools/`**
   (`cli.py`, `config.py`, `conan_ops.py`, `builder.py`, `logging_utils.py`,
   `gui.py`). Add/update its unit test in `modules/toolchain/tests/`.
2. **Bump the version** in `modules/toolchain/pyproject.toml`.
3. **Publish, by whichever mechanism the pin you're testing against uses**
   (`docs/imp_design.md` §3 — both are live, permanent options):
   - *Git-tag pin* (`vX.Y.Z`): `git tag vX.Y.Z && git push origin vX.Y.Z`
     — no separate build step, `pip install git+...@vX.Y.Z` builds on
     install.
   - *Conan pin* (bare `X.Y.Z`): also bump the literal `version` in
     `modules/toolchain/conan_package/conanfile.py` to match (it does
     **not** derive from `pyproject.toml` automatically — see that file's
     own docstring for why), then `cd conan_package && conan create .
     --build=missing && conan upload adas-build-tools/<ver> -r adas-local
     --confirm`.
4. **Bump the pin in whichever component(s) you're rolling this out to**
   — `conf/build_tools.version`, one component at a time, its own
   schedule (same independence `conf/build.yml`'s own pin bumps already
   have). Not a fan-out: a component not yet touched keeps working on its
   old pin.
5. **Rebuild for real:** `build.bat -t sil -p vs2026` and `-t gtest -p
   vs2026` in at least the component(s) whose pin you bumped, ideally with
   `.venv` removed first to force a real reinstall against the new pin.

## C — Copy-distributed files

1. **Edit `modules/toolchain/copy_files/<file>`** — the canonical copy.
   Never hand-edit a component's copy; that is what reintroduces drift.
2. **Fan out:** `python modules/toolchain/scripts/sync_copy_files.py`,
   then review the diff in each touched component. `modules/sim/vantage` is
   invisible to this script by design, not by gap: since WP-24
   (`modules/toolchain/docs/imp_design.md` §8), vantage carries none of
   these copy-distributed files at all — it is built through `modules/sim`'s
   own `conf/build.yml`-declared `subcomponents:` list instead. Do not
   hand-copy anything into `modules/sim/vantage/`.
3. **Prove identity:** `python scripts/check_invariants.py` — `CPY-1` must
   be clean. (`python modules/toolchain/scripts/check_copy_files.py` alone
   gives the per-file detail, including the declared Option-A gaps it
   passes on.) A partial rollout is a defect.
4. **Rebuild the affected targets** in at least two components to confirm
   nothing regressed.

## All three paths

**Commit per submodule, then bump the superproject pointer** — in
dependency order (`workflows/submodule_commit_order.md`).

Formatting-only (`.clang-format`) changes land in a dedicated commit with no
logic touched, build+tests verified after (R-BUILD-5).

## Failure cases

- "I'll update the others later" → for copy-distributed files the copies
  have drifted and `CPY-1` is red; for a pin bump the fleet is split across
  two recipe versions. Do all repos in the same pass or don't ship it.
- **Editing `copy_files/scripts/build.py`/`build_gui.py` to fix a
  build-logic bug** → those are ~150-line bootstrap stubs now
  (`find_component_root()`/`read_pin()`/`ensure_venv()`/`exec_into_venv()`
  and nothing else); the actual logic is Category B
  (`adas_build_tools/`), needs its own version bump + publish.
- **Editing a component's `conanfile.py` to change behaviour** → it is a
  6-line stub; there is nothing there to edit. The change belongs in
  `base_recipe.py` (shared) or `conf/build.yml` (per-component).
- Per-component difference creeping into `base_recipe.py` → it belongs in
  `conf/build.yml`, not the shared recipe.
- Adding a new copy-distributed file → add it to `COPY_FILES` in
  `modules/toolchain/scripts/_shared.py`. That is the only step; both
  scripts read it.
