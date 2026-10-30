# Rules — Variant / Build Model (R-VAR)

Normative index. Detail: `docs/project_variant_model.md`, `docs/build_grammar.md`,
`docs/project_scoped_params.md`, `docs/sw_build_architecture.md`. Deep pattern:
`skills/build_grammar.md`.

| ID | Rule |
|---|---|
| R-VAR-1 | Four independent axes: **project** (calibration) · **target** (deliverable kind: `sil`, later `production`) · **platform** (toolchain, e.g. `vs2026`) · **module** (component). Both `-t` and `-p` are always named explicitly, never inferred. |
| R-VAR-2 | **No central module roster.** A project exists iff some module's `conf/build.yml` declares it; the dispatcher derives project→modules by scanning. A missing central roster is unrepresentable by design. |
| R-VAR-3 | Per-component build data lives in `modules/<name>/conf/build.yml` (`variants.<project>.<target>.platforms`, `requires`, `tool_requires`, `enabled_functions`, `package_id_extra`). |
| R-VAR-4 | Project **calibration data** lives in `projects/<name>/` (`default.yaml`, `ego_params.yaml`); `base` is the no-specific-program fallback. Passed as an `-o project=` Conan **option** (never an env var) and `-DADAS_PROJECT`. |
| R-VAR-5 | Function selection is **compile-time** via the `ENABLED_FUNCTIONS` CMake list + `ADAS_FN_<X>_ENABLED` defines — never a runtime registry (certification-driven). |
| R-VAR-6 | **A feature switched per product variant is compile-time, in `src/project/<project>/<fn>_cfg.h`** (`#define <FN>_CFG_<FEATURE>_ENABLED 0/1`), selected by `ADAS_PROJECT` on the function's include path. Every project defines every switch (a missing one is an `#error`). Code reads it **only** through `component/<fn>/<fn>_variant.hpp` as a `constexpr bool`, branching with an ordinary/`if constexpr` condition so **both paths always compile**; the logic it gates takes the decision as an argument, so both variants stay unit-tested in every build. The DLL reports every switch in `ComponentManifest.compile_switches` (a compile-time choice is not in the config bundle, R-SIM-3a). The calibration values the feature uses stay in `default.yaml`. A YAML key is for calibration and experiments, never for a variant decision. |

See also: `rules/build.md`, `workflows/add_function.md`, `rules/sim.md`
(R-SIM-4 — a component's SIL port manifest is generated from
`ENABLED_FUNCTIONS`, so it cannot drift from what was compiled).
