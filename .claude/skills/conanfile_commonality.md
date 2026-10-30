# Skill: conanfile_commonality

Keep the build machinery common. Enforces `R-BUILD-*`. Backing docs:
`modules/toolchain/docs/toolchain_plan.md`,
`docs/KT/how_to_add_a_component.md`.

## Two mechanisms, not one

A new component **never writes or edits machinery**. It arrives two ways:

- **`conanfile.py` — imported, not copied.** A 6-line stub pinning
  `adas-toolchain/X.Y.Z` and inheriting `AdasComponent`; the recipe body
  lives once in `modules/toolchain/base_recipe.py`. Conan enforces the
  version match, so this category cannot drift.
- **Copied, held identical by `CPY-1`** (`scripts/check_invariants.py`):
  `scripts/build.py`, `build.bat`, `build.sh`, `scripts/build_gui.py`,
  `.clang-format` — sourced from `modules/toolchain/copy_files/`.

The split is structural, not stylistic: a component must run `build.bat`
**before** any `conan install` has happened, so those files cannot
themselves arrive through Conan.

The **only** files a new component author writes are its own `src/` +
`CMakeLists.txt` (code), its own `conf/build.yml` (data), and the six-line
`conanfile.py`.

## Where per-component difference goes — `conf/build.yml`, not the recipe

Everything that differs between components is data in `conf/build.yml`:

```yaml
variants:
  base:
    requires:      [ protobuf/3.21.12, adas-interfaces/1.0.0 ]   # + optional adas-mathlib, adas-shared-config
    tool_requires: [ protobuf/3.21.12 ]
    enabled_functions: [ aeb ]        # df only
    package_id_extra:  [ ... ]        # only if per-project selection folds into package identity
    sil:   { platforms: [ { build: vs2026 } ] }
    gtest: { platforms: [ { build: vs2026 } ] }
```

The recipe reads these generically (`requirements()`/`build_requirements()`
loop over the data). **Never add a component-specific hook** to a recipe — add
a key to `conf/build.yml` instead.

## Two component shapes

- **Produces a compiled artifact (DLL/lib):** `package_type = "shared-library"`,
  real `build()`/`package()`/`package_info()` — follow `df`/`vdy`.
- **Data only (YAML/config):** `package_type = "unknown"`, no `build()`, no
  `settings` — follow `shared_config`.

## Gotchas

- `project` must be a real Conan **option** (`-o project=…`), never an env var —
  an env var is invisible to `package_id`, so two projects would collide on
  publish.
- Recipes **never name a remote** — remotes are client config
  (`conan remote add`). This keeps the recipe portable across local/Artifactory.
- A change to any machinery file is cross-repo (R-BUILD-6) —
  see `workflows/change_build_machinery.md`. Which mechanism you are
  changing decides the procedure: `base_recipe.py` + a coordinated pin bump,
  or `copy_files/` + `sync_copy_files.py`.
- **Never edit a component's `conanfile.py` to change behaviour** — it is a
  stub. Shared logic goes in `base_recipe.py`; per-component difference goes
  in `conf/build.yml`.
