# Skill: build_grammar

The build command grammar. Enforces `R-VAR-*`. Backing docs:
`docs/build_grammar.md`, `docs/sw_build_architecture.md`,
`docs/project_variant_model.md`.

## Four axes, always explicit

```
<module>   -t <target>   -p <platform>   [-P <project>]
 which       kind of        toolchain       calibration
 component   deliverable    (vs2026)        (base | …)
```

`-t` and `-p` are **required, never inferred** — a default would make a YAML
list's *order* load-bearing. `-P` defaults to `base`.

## Two paths

- **Path 1 — per component (always works):**
  `cd modules/<c> && build.bat -t sil -p vs2026 [-P base] [--clean]`.
  `build.bat`/`build.sh` are thin passthroughs to the byte-identical
  component `scripts/build.py` (R-BUILD-2/3). Flow: `conan install` →
  `cmake --preset <target>-<platform>` → `cmake --build` → `ctest` (for gtest).
- **Path 2 — superproject dispatcher:**
  `python scripts/build.py <module>|all -t <target> -p <platform> [-P <project>]`.
  Delegates to Path 1 with output under `ws/`. `all`/`--modules a,b` fans out;
  `--with`/`--with-all` builds one aggregate solution. Modes are told apart by
  **which flags are present**, never by guessing what a word means.

## Where each axis is declared

- **project** → `projects/<name>/` calibration data (R-VAR-4), selected by
  `-o project=` Conan option + `-DADAS_PROJECT`. Never an env var.
- **target + platform** → each component's own `conf/build.yml`
  (`variants.<project>.<target>.platforms`). No central roster (R-VAR-2).
- **presets** → `<target>-<platform>` (e.g. `sil-vs2026`); no hardcoded
  per-target preset table.

## Fan-out semantics

A module missing `conf/build.yml` or not declaring the requested target+platform
is **skipped with a reason** in a batch, but **errors** if named directly.
A batch tolerates gaps; an explicit request must never silently do nothing.
