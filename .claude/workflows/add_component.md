# Workflow: add_component

**Canonical procedure: `docs/KT/how_to_add_a_component.md`** (full 9-step guide).
This file is the short operational index; follow the KT doc for detail.

## Goal

Stand up a new `modules/<name>` component that builds `sil`/`gtest`, packages
via Conan, and wires into the platform — **without editing any shared machinery**
(R-BUILD-1..5).

## Step 0 — ask which design documents this component gets

**Before creating anything.** A component is where the reasoning is cheapest to
write and most expensive to reconstruct later, so the question is asked once,
here, and the answer is recorded in `layers.yaml`'s `context:` block
(`R-REQ-17`) rather than left to whoever writes the first requirement.

Put it to the user as a question, not an assumption:

| Ask | Warranted when | Skip when |
|---|---|---|
| **Concept** (`<M>_Concept.md`) — the problem, the domain, the mathematics | there is a derivation, a regulation, a threshold anybody will later ask *"why that number?"* about | the behaviour is self-evident from the requirement rows |
| **Architecture** (`<M>_Architecture.md`) — ports, interfaces, structure | the component introduces an interface, or its decomposition is a real choice | it has one input, one output and no internal structure worth naming |
| **Change register** (`<M>_Change_Register.md`) — the thinking before any UID | modifying something that already exists, where most of the work is deciding what *not* to change | building something new, where the concept document already carries the thinking |
| **Reference** (`reg/`, `ref/`) — retrieved standards or datasheets | the design answers to an external document | nothing external binds it |

**An explicit "no" is the useful answer too** — omitting the `context:` block is
honest, exactly as omitting an `STK` category is (`R-REQ-16`). What is not
acceptable is an analysis document that exists but is undeclared: nothing then
tells a reader to read it first, and no check can tell when it has gone stale.

## Steps

1. **Create the submodule** — new repo, register in root `.gitmodules`.
2. **Get the machinery — two mechanisms, never hand-written** (R-BUILD-6):
   - `conanfile.py`: write the 6-line stub —
     `python_requires = "adas-toolchain/X.Y.Z"` +
     `python_requires_extend = "adas-toolchain.AdasComponent"`. No recipe
     logic; there is none to copy.
   - `scripts/build.py`, `build.bat`/`build.sh`, `scripts/build_gui.py`,
     `.clang-format`: `python modules/toolchain/scripts/sync_copy_files.py`
     copies them from `modules/toolchain/copy_files/`. Never edit a copy —
     `CPY-1` fails on drift.
3. **Write only your own files** — `src/component/**` (middleware-free, R-ARCH-2),
   `src/platform/<name>_sil/**` (C-API DLL root, R-ARCH-5), `CMakeLists.txt`,
   `CMakePresets.json`, `tests/unit/**` (mirrors `component/` 1:1).
4. **Write `conf/build.yml`** — the component's only build-difference file
   (`requires`/`tool_requires`/platforms; `enabled_functions` if applicable).
   All per-component variation lives here (R-VAR-3, `skills/conanfile_commonality`).
5. **Pick the recipe shape** — set `recipe.type` in `conf/build.yml`:
   compiled artifact → `shared-library`/`static-library` (follow `df`/`vdy`);
   data-only → `unknown` (follow `shared_config`). `AdasComponent` branches
   on it; you never write the branch.
6. **Consume `shared_config`** only if you need cross-component calibration.
7. **Register with the dispatcher** — declare your project(s) in `conf/build.yml`;
   the root `scripts/build.py` derives the roster by scanning (R-VAR-2).
8. **Wire into `sil`** if it's a SIL deliverable (`workflows/sil_integration.md`).
9. **Optional:** dev-ops GUI + Conan publishing.

## Validation

- `build.bat -t sil -p vs2026` and `-t gtest -p vs2026` both green.
- `python scripts/check_invariants.py` clean — `CPY-1` proves your copied
  machinery files match `modules/toolchain/copy_files/`.
- Your `conanfile.py` is the six-line stub, pinning the same
  `adas-toolchain/X.Y.Z` every other component pins.
- Add the `.claude/`/`CLAUDE.md` per spec §6.2 (mostly empty; points to root).

## Failure cases

- Real logic in `build.bat` → the item-10 mistake; revert to the one-liner.
- A component-specific hook in `conanfile.py` → there is nothing to hook; the
  stub has no body. Per-component difference goes in `conf/build.yml`, shared
  recipe behaviour in `modules/toolchain/base_recipe.py`.
- Middleware/IO in `src/component/**` → move to `src/platform/`.
