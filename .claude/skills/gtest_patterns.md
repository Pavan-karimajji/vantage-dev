# Skill: gtest_patterns

Test conventions. Backing docs: `docs/df_swr_tests.md`, `docs/build_regression_tests.md`.

## Layout

- `tests/unit/` **mirrors `src/component/` 1:1** — one test dir per function/module.
- Tests are gated by the same `ENABLED_FUNCTIONS` `IN_LIST` guard as the source,
  so disabling a function cleanly drops its tests instead of breaking the build
  (R-VAR-5).
- Built and run via the `gtest` target: `build.bat -t gtest -p vs2026`
  → `ctest --preset gtest-vs2026`.

## What to test

- **Component logic** in isolation — pure `exec(dtS)` calls with hand-built
  `ReqPorts`, asserting `ProPorts`. No middleware, no disk.
- **DLL round-trip** at the boundary — serialize protobuf in, call the C-API,
  deserialize out (the `InterfaceCApiTest` pattern).
- **Boundary contract tests** (BCT) — e.g. the SIL DLL links no
  simulator/middleware libs (`dumpbin /dependents`, BCT-05).

## Conventions

- Test files snake_case, `<thing>_test.cpp`; header block per R-STYLE-1.
- Use `mathlib` types directly in assertions; keep fixtures allocation-light.
- New function ⇒ its tests land with it (`workflows/add_function.md`).

Template: `templates/gtest_template.cpp`.
