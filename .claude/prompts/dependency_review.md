# Prompt: dependency_review

Review lens for build/dependency integrity. Rules: `rules/build.md` (R-BUILD-*),
`rules/variant.md` (R-VAR-*), `rules/math.md` (R-MATH-*).

## Focus areas

- Is every component's `conanfile.py` a six-line `python_requires` stub, and do
  all of them pin the **same** `adas-toolchain/X.Y.Z`? A split fleet across two
  recipe versions is the drift this mechanism replaced. (R-BUILD-1)
- Are the copy-distributed files (component `scripts/build.py`, `build.bat`/`.sh`,
  `build_gui.py`, `.clang-format`) byte-identical across components?
  (`CPY-1`, R-BUILD-2..6)
- Does per-component difference live in `conf/build.yml`, never in the recipe?
- Is `project` a Conan **option**, not an env var? (R-VAR-4)
- Is math taken from `mathlib` (not reimplemented), and linked guarded/optional?
  (R-MATH-1/3)
- Is the dependency graph acyclic with `mathlib` at the base and everyone on
  `interfaces`?

## Validation criteria

- `python scripts/check_invariants.py` clean — `CPY-1` covers the copied files.
- `grep -h '^ *python_requires = ' modules/*/conanfile.py | sort -u` yields
  exactly one line (8 components, one pin).
- Fan-out build declares every real module (no silent skip — R-VAR-2).

## Risks to check

- A component-specific hook creeping into `base_recipe.py` (it belongs in that
  component's `conf/build.yml`), or logic added to a component's stub at all.
- Partial machinery rollout (drift) — see `workflows/change_build_machinery.md`.
